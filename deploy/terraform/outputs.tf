output "api_url" {
  value       = "http://${aws_lb.api.dns_name}"
  description = "Point scripts/smoke_test.sh at this (or https://... once certificate_arn is set and a real domain CNAMEs to it)."
}

output "ecr_repository_url" {
  value = aws_ecr_repository.rivet_service.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "migrate_task_definition_arn" {
  value       = aws_ecs_task_definition.migrate.arn
  description = "Pass to `aws ecs run-task` as the release step -- see docs/runbook.md."
}

output "db_endpoint" {
  value       = aws_db_instance.main.endpoint
  description = "Host:port only -- the full connection string (with credentials) lives in Secrets Manager, not in plan/apply output."
}
