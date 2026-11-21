import json
import logging
import os
import re
import time
from urllib.parse import urlencode
from urllib.error import URLError
from urllib.request import Request, urlopen

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
sns = boto3.client("sns")
bedrock = boto3.client("bedrock-runtime")

BUCKET = os.environ.get("BUCKET")
TOPIC_ARN = os.environ.get("TOPIC_ARN")
MODEL_ID = os.environ.get("MODEL_ID", "amazon.nova-micro-v1:0")

JOBICY_API = "https://jobicy.com/api/jobs"
SEEN_KEY = "state/seen_jobs.json"
MAX_SEEN = 500

PROFILE = (
    "A beginner in cloud and DevOps who builds hands-on AWS, Terraform "
    "and Python projects and is looking for an internship or entry-level role."
)

TITLE_KEYWORDS = [
    "cloud engineer", "cloud support", "aws", "devops", "site reliability",
    "platform engineer", "infrastructure engineer", "terraform", "kubernetes",
    "python developer", "python engineer", "software engineer",
    "systems engineer", "machine learning engineer", "ai engineer",
    "ml engineer",
]

SENIOR_KEYWORDS = [
    "senior", "sr.", "staff", "principal", "director", "lead", "manager",
    "head of", "chief", "vp ",
]

OPEN_LOCATIONS = ["anywhere", "worldwide", "africa", "kenya", "emea"]


def is_relevant(job):
    """Cheap checks only: tech title, not senior, open to Nairobi."""

    title = job.get("jobTitle", "").lower().strip()
    level = job.get("jobLevel", "").lower().strip()
    geo = str(job.get("jobGeo", "")).lower()

    if any(word in title for word in SENIOR_KEYWORDS):
        return False

    if level in ["senior", "director", "lead", "executive"]:
        return False

    if not any(keyword in title for keyword in TITLE_KEYWORDS):
        return False

    return any(place in geo for place in OPEN_LOCATIONS)


def fetch_jobs_broad():
    """Retrieve recent remote job listings from Jobicy."""

    url = f"{JOBICY_API}?{urlencode({'count': 100})}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Terraform-Job-Alerts/1.0",
        },
    )

    data = None
    for attempt in range(1, 4):
        try:
            with urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
            break
        except (URLError, TimeoutError) as error:
            logger.warning("Jobicy attempt %s failed: %s", attempt, error)
            if attempt == 3:
                raise
            time.sleep(2 * attempt)

    if not data.get("success", False):
        raise RuntimeError("Jobicy API returned an unsuccessful response")

    return data.get("jobs", [])


SEARCH_TAGS = ["devops", "aws", "terraform", "cloud", "kubernetes", "python"]
JOBICY_V2 = "https://jobicy.com/api/v2/remote-jobs"


def fetch_query(params):
    """One Jobicy query with retry. Returns a list of jobs."""
    url = f"{JOBICY_V2}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "job-alerts/1.0"})
    for attempt in range(1, 4):
        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8")).get("jobs", [])
        except (URLError, TimeoutError) as error:
            logger.warning("Jobicy %s attempt %s failed: %s", params, attempt, error)
            if attempt == 3:
                raise
            time.sleep(2 * attempt)


def fetch_jobs():
    """Run targeted searches and merge the results, de-duplicated by job ID."""
    merged = {}
    failures = 0
    queries = 0
    for tag in SEARCH_TAGS:
        for geo in (None, "anywhere"):
            params = {"count": 50, "tag": tag}
            if geo:
                params["geo"] = geo
            queries += 1
            try:
                for job in fetch_query(params):
                    merged[job["id"]] = job
            except (URLError, TimeoutError):
                failures += 1
            time.sleep(0.5)
    if failures == queries:
        raise RuntimeError("All Jobicy queries failed")
    return list(merged.values())


def summarize(job):
    return {
        "id": job.get("id"),
        "title": job.get("jobTitle"),
        "company": job.get("companyName"),
        "location": job.get("jobGeo"),
        "level": job.get("jobLevel"),
        "published": job.get("pubDate"),
        "url": job.get("url"),
        "summary": (job.get("jobExcerpt") or "")[:300],
    }


def load_seen():
    try:
        body = s3.get_object(Bucket=BUCKET, Key=SEEN_KEY)["Body"].read()
        return json.loads(body.decode("utf-8"))
    except ClientError as error:
        if error.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return []
        raise


def save_seen(ids):
    s3.put_object(
        Bucket=BUCKET,
        Key=SEEN_KEY,
        Body=json.dumps(ids[-MAX_SEEN:]),
        ContentType="application/json",
    )


def rate_jobs(jobs):
    """Ask Bedrock whether each job is realistic for this candidate."""

    items = [
        {k: j[k] for k in ("id", "title", "company", "level", "location", "summary")}
        for j in jobs
    ]
    prompt = (
        "You are screening job postings for this candidate: " + PROFILE + "\n"
        "For each posting, decide whether it is realistic for this candidate. "
        'Answer ONLY with a JSON array of objects with keys "id" (number), '
        '"fit" ("good", "stretch" or "no") and "reason" (one short sentence). '
        "Use only the text given and do not invent facts.\n\n"
        + json.dumps(items)
    )

    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 1000, "temperature": 0.1},
    )
    text = response["output"]["message"]["content"][0]["text"].strip()
    text = re.sub(r"^`{3}(?:json)?\s*|\s*`{3}$", "", text)

    return {int(r["id"]): r for r in json.loads(text)}


def build_message(shortlist, ratings):
    lines = ["New roles that match your search. Source: Jobicy (https://jobicy.com)", ""]

    for number, job in enumerate(shortlist, start=1):
        rating = ratings.get(job["id"], {})
        lines.append(f"{number}. {job['title']} - {job['company']}")
        if rating:
            lines.append(f"   Fit: {rating.get('fit')} - {rating.get('reason')}")
        lines.append(f"   Location: {job['location']} | Level: {job['level']}")
        lines.append(f"   {job['url']}")
        lines.append("")

    return "\n".join(lines)


def lambda_handler(event, context):
    logger.info("Job Alerts Lambda started")
    dry_run = bool((event or {}).get("dry_run"))

    jobs = fetch_jobs()
    candidates = [summarize(j) for j in jobs if is_relevant(j)]
    logger.info("Retrieved %s jobs, %s candidates", len(jobs), len(candidates))

    if dry_run:
        return {"statusCode": 200, "dry_run": True, "candidates": candidates}

    seen = load_seen()
    seen_ids = set(seen)
    new_jobs = [j for j in candidates if j["id"] not in seen_ids]

    if not new_jobs:
        logger.info("No new jobs, nothing to send")
        return {"statusCode": 200, "sent": 0}

    try:
        ratings = rate_jobs(new_jobs)
    except Exception:
        logger.exception("Bedrock rating failed, sending unrated jobs")
        ratings = {}

    shortlist = [
        j for j in new_jobs
        if ratings.get(j["id"], {}).get("fit", "good") != "no"
    ]

    if shortlist:
        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject=f"{len(shortlist)} new cloud/DevOps role(s) for you",
            Message=build_message(shortlist, ratings),
        )

    save_seen(seen + [j["id"] for j in new_jobs])
    logger.info("Sent %s of %s new jobs", len(shortlist), len(new_jobs))
    return {"statusCode": 200, "sent": len(shortlist)}
