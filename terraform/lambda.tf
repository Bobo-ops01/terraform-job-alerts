resource "aws_lambda_function" "job_alerts" {
  function_name = "job-alerts-function"
  role          = aws_iam_role.job_alerts_lambda.arn

  runtime = "python3.12"
  handler = "src.lambda_function.lambda_handler"

  filename         = "${path.module}/function.zip"
  source_code_hash = filebase64sha256("${path.module}/function.zip")

  timeout     = 30
  memory_size = 128

  tags = {
    Project = "terraform-job-alerts"
  }
}
