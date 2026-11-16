resource "aws_sns_topic" "job_alerts" {
  name = "job-alerts-notifications"

  tags = {
    Project = "terraform-job-alerts"
  }
}
