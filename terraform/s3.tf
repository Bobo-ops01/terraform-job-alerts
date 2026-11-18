resource "aws_s3_bucket" "job_alerts" {
  bucket = "bobo-ops01-terraform-job-alerts-use1"

  tags = {
    Name        = "bobo-ops01-terraform-job-alerts-use1"
    Environment = "development"
    Project     = "terraform-job-alerts"
  }
}

resource "aws_s3_bucket_public_access_block" "job_alerts" {
  bucket = aws_s3_bucket.job_alerts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "job_alerts" {
  bucket = aws_s3_bucket.job_alerts.id

  versioning_configuration {
    status = "Enabled"
  }
}
