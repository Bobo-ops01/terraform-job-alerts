data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/build/function.zip"
  excludes    = ["__pycache__/**", "*.bak"]
}

resource "aws_lambda_function" "job_alerts" {
  function_name = "job-alerts-function"
  role          = aws_iam_role.job_alerts_lambda.arn

  runtime = "python3.12"
  handler = "lambda_function.lambda_handler"

  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  timeout     = 60
  memory_size = 256

  environment {
    variables = {
      BUCKET    = aws_s3_bucket.job_alerts.id
      TOPIC_ARN = aws_sns_topic.job_alerts.arn
      MODEL_ID  = "amazon.nova-micro-v1:0"
    }
  }

  tags = {
    Project = "terraform-job-alerts"
  }
}
