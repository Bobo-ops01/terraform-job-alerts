
import json
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger()
logger.setLevel(logging.INFO)

JOBICY_API = "https://jobicy.com/api/jobs"


TITLE_KEYWORDS = [
    "cloud engineer",
    "cloud support",
    "aws",
    "devops",
    "site reliability",
    "platform engineer",
    "infrastructure engineer",
    "terraform",
    "kubernetes",
    "python developer",
    "python engineer",
    "software engineer",
    "systems engineer",
    "machine learning engineer",
    "ai engineer",
    "ml engineer",
]

SENIOR_KEYWORDS = [
    "senior",
    "sr.",
    "staff",
    "principal",
    "director",
    "lead",
    "manager",
    "head of",
    "chief",
    "vp ",
]

LEVEL_PATTERN = re.compile(
    r"\b(?:intern|internship|junior|entry|graduate|trainee|associate|apprentice)s?\b"
)

OPEN_LOCATIONS = ["anywhere", "worldwide", "africa", "kenya", "emea"]


def is_relevant(job):
    """Keep junior or intern tech roles that are open to Nairobi."""

    title = job.get("jobTitle", "").lower().strip()
    level = job.get("jobLevel", "").lower().strip()
    geo = str(job.get("jobGeo", "")).lower()

    if any(word in title for word in SENIOR_KEYWORDS):
        return False

    if level in ["senior", "director", "lead", "executive"]:
        return False

    if not any(keyword in title for keyword in TITLE_KEYWORDS):
        return False

    if not any(place in geo for place in OPEN_LOCATIONS):
        return False

    return bool(LEVEL_PATTERN.search(f"{title} {level}"))



class HTMLTextParser(HTMLParser):
    """Extract readable text from HTML job descriptions."""

    def __init__(self):
        super().__init__()
        self.text_parts = []

    def handle_data(self, data):
        self.text_parts.append(data)

    def get_text(self):
        return " ".join(self.text_parts)


def clean_html(value):
    parser = HTMLTextParser()
    parser.feed(value or "")
    return parser.get_text()


def fetch_jobs():
    """Retrieve recent remote job listings from Jobicy."""

    params = urlencode({"count": 100})
    url = f"{JOBICY_API}?{params}"

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Terraform-Job-Alerts/1.0",
        },
    )

    with urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not data.get("success", False):
        raise RuntimeError("Jobicy API returned an unsuccessful response")

    return data.get("jobs", [])




def lambda_handler(event, context):
    logger.info("Job Alerts Lambda started")

    jobs = fetch_jobs()

    matching_jobs = [
        job for job in jobs
        if is_relevant(job)
    ]

    # Keep the most recent 25 matching opportunities.
    matching_jobs = matching_jobs[:25]

    results = []

    for job in matching_jobs:
        results.append({
            "id": job.get("id"),
            "title": job.get("jobTitle"),
            "company": job.get("companyName"),
            "location": job.get("jobGeo"),
            "level": job.get("jobLevel"),
            "published": job.get("pubDate"),
            "url": job.get("url"),
            "source": "Jobicy",
        })

    logger.info("Retrieved %s jobs", len(jobs))
    logger.info("Found %s relevant jobs", len(results))

    return {
        "statusCode": 200,
        "body": json.dumps({
            "source": "Jobicy",
            "total_jobs_retrieved": len(jobs),
            "matching_jobs": len(results),
            "jobs": results,
        }),
    }


