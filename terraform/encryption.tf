resource "aws_s3_bucket_server_side_encryption_configuration" "job_alerts" {
  bucket = aws_s3_bucket.job_alerts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
