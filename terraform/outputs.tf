output "api_url" {
  description = "API Gateway endpoint - replace all localhost:3001"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "rds_endpoint" {
  description = "RDS internal address - connect via SSM tunnel"
  value       = aws_db_instance.main.address
}

output "dashboard_url" {
  description = "Dashboard URL"
  value       = "http://${aws_s3_bucket_website_configuration.dashboard.website_endpoint}"
}

output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.dashboard.id
}

output "bastion_instance_id" {
  description = "Bastion instance ID for SSM tunnel"
  value       = aws_instance.bastion.id
}

output "batch_lambda_name" {
  description = "Batch Lambda function name for manual invocation"
  value       = aws_lambda_function.batch.function_name
}
