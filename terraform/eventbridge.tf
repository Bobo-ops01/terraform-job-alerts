
resource "aws_iam_role" "eventbridge_scheduler" {
  name = "job-alerts-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "scheduler.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project = "terraform-job-alerts"
  }
}

resource "aws_iam_role_policy" "eventbridge_invoke_lambda" {
  name = "job-alerts-scheduler-invoke-lambda"
  role = aws_iam_role.eventbridge_scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "lambda:InvokeFunction"
        ]

        Resource = aws_lambda_function.job_alerts.arn
      }
    ]
  })
}

resource "aws_scheduler_schedule" "job_alerts_daily" {
  name                         = "job-alerts-daily-schedule"
  description                  = "Run the job alerts Lambda every day at 8 AM Nairobi time"
  schedule_expression          = "cron(0 8 * * ? *)"
  schedule_expression_timezone = "Africa/Nairobi"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.job_alerts.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn
  }
}

