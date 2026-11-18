resource "aws_iam_role" "job_alerts_lambda" {
  name = "job-alerts-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "lambda.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name    = "job-alerts-lambda-role"
    Project = "terraform-job-alerts"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role = aws_iam_role.job_alerts_lambda.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "job_alerts_s3" {
  name        = "job-alerts-s3-access"
  description = "Allow Lambda to access the job alerts S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "s3:ListBucket"
        ]

        Resource = aws_s3_bucket.job_alerts.arn
      },
      {
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]

        Resource = "${aws_s3_bucket.job_alerts.arn}/state/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_s3_access" {
  role       = aws_iam_role.job_alerts_lambda.name
  policy_arn = aws_iam_policy.job_alerts_s3.arn
}

resource "aws_iam_policy" "job_alerts_bedrock" {
  name        = "job-alerts-bedrock-access"
  description = "Allow Lambda to invoke the selected Bedrock model"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "bedrock:InvokeModel"
        ]

        Resource = "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-micro-v1:0"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_bedrock_access" {
  role       = aws_iam_role.job_alerts_lambda.name
  policy_arn = aws_iam_policy.job_alerts_bedrock.arn
}

resource "aws_iam_policy" "job_alerts_sns" {
  name        = "job-alerts-sns-access"
  description = "Allow Lambda to publish job alert notifications"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "sns:Publish"
        ]

        Resource = aws_sns_topic.job_alerts.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_sns_access" {
  role       = aws_iam_role.job_alerts_lambda.name
  policy_arn = aws_iam_policy.job_alerts_sns.arn
}
