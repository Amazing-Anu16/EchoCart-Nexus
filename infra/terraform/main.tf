terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for deployment"
}

variable "allowed_origins" {
  type        = list(string)
  default     = ["*"]
  description = "Allowed CORS origins for the MCP server"
}

variable "image_uri" {
  type        = string
  description = "ECR Image URI for the EchoCart MCP container"
}

provider "aws" {
  region = var.aws_region
}

# -----------------------------------------------------------------------------
# IAM Role & Execution Policy
# -----------------------------------------------------------------------------
resource "aws_iam_role" "lambda_exec" {
  name = "echocart-mcp-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# -----------------------------------------------------------------------------
# AWS Lambda Function (Container Image)
# -----------------------------------------------------------------------------
resource "aws_lambda_function" "echocart_mcp" {
  function_name = "echocart-nexus-mcp"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = var.image_uri
  timeout       = 60
  memory_size   = 1024

  environment {
    variables = {
      PORT                         = "8080"
      AWS_LWA_PORT                 = "8080"
      AWS_LWA_INVOKE_MODE          = "response_stream"
      AWS_LWA_READINESS_CHECK_PATH = "/health"
      ALLOWED_ORIGINS              = join(",", var.allowed_origins)
      LOG_LEVEL                    = "INFO"
    }
  }
}

# -----------------------------------------------------------------------------
# AWS Lambda Function URL with Response Streaming & CORS
# -----------------------------------------------------------------------------
resource "aws_lambda_function_url" "mcp_url" {
  function_name      = aws_lambda_function.echocart_mcp.function_name
  authorization_type = "NONE"
  invoke_mode        = "RESPONSE_STREAM"

  cors {
    allow_credentials = false
    allow_origins     = var.allowed_origins
    allow_methods     = ["POST", "GET", "OPTIONS", "DELETE"]
    allow_headers = [
      "Content-Type",
      "MCP-Protocol-Version",
      "Mcp-Method",
      "Mcp-Name",
      "Mcp-Session-Id",
      "Authorization",
      "Accept"
    ]
    expose_headers = [
      "MCP-Protocol-Version",
      "Mcp-Method",
      "Mcp-Name",
      "Mcp-Session-Id",
      "Content-Security-Policy"
    ]
    max_age = 86400
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Log Group
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.echocart_mcp.function_name}"
  retention_in_days = 14
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------
output "function_url" {
  description = "Public Streamable HTTP MCP Server Function URL"
  value       = aws_lambda_function_url.mcp_url.function_url
}

output "mcp_endpoint" {
  description = "Endpoint for MCP Client connection"
  value       = "${aws_lambda_function_url.mcp_url.function_url}mcp"
}
