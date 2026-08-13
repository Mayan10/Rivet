resource "aws_ecs_cluster" "main" {
  name = "rivet-${var.environment}"
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/rivet-${var.environment}/api"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/rivet-${var.environment}/worker"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "migrate" {
  name              = "/ecs/rivet-${var.environment}/migrate"
  retention_in_days = 30
}

# Execution role: what ECS itself uses to pull the image and write logs,
# plus read the Secrets Manager entries a task definition's own
# `secrets` block references (that resolution happens before the
# container starts, on ECS's behalf, not the application's).
resource "aws_iam_role" "ecs_execution" {
  name = "rivet-${var.environment}-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "read-app-secrets"
  role = aws_iam_role.ecs_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.database_url.arn,
        aws_secretsmanager_secret.app_secret_key.arn,
        aws_secretsmanager_secret.stripe_secret_key.arn,
        aws_secretsmanager_secret.stripe_webhook_secret.arn,
      ]
    }]
  })
}

# Task role: what the running application uses (boto3's default
# credential chain picks this up automatically inside a Fargate task) --
# only S3 access to the artifacts bucket. Postgres/Redis auth is via
# connection string, not IAM, so nothing else is needed here.
resource "aws_iam_role" "ecs_task" {
  name = "rivet-${var.environment}-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "artifacts-bucket-access"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
      Resource = ["${aws_s3_bucket.artifacts.arn}/*"]
    }]
  })
}

# Every container definition below shares this env/secrets shape --
# built once so api/worker/migrate can't drift, mirroring
# docker-compose.yml's &service-env anchor.
locals {
  container_secrets = [
    { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
    { name = "SECRET_KEY", valueFrom = aws_secretsmanager_secret.app_secret_key.arn },
    { name = "STRIPE_SECRET_KEY", valueFrom = aws_secretsmanager_secret.stripe_secret_key.arn },
    { name = "STRIPE_WEBHOOK_SECRET", valueFrom = aws_secretsmanager_secret.stripe_webhook_secret.arn },
  ]

  container_environment = [
    { name = "ENV", value = var.environment },
    { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0" },
    { name = "STORAGE_BACKEND", value = "s3" },
    { name = "S3_BUCKET", value = aws_s3_bucket.artifacts.bucket },
    { name = "S3_REGION", value = var.aws_region },
    { name = "COOKIE_SECURE", value = var.certificate_arn != "" ? "true" : "false" },
  ]
}

resource "aws_ecs_task_definition" "api" {
  family                   = "rivet-${var.environment}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name        = "api"
    image       = var.container_image
    essential   = true
    # No `command` override -- runs the Dockerfile's own default CMD.
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment  = local.container_environment
    secrets      = local.container_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "api"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "rivet-${var.environment}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name        = "worker"
    image       = var.container_image
    essential   = true
    command     = ["python", "-m", "rivet_service.jobs.worker"]
    environment = local.container_environment
    secrets     = local.container_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.worker.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "worker"
      }
    }
  }])
}

# Not an aws_ecs_service -- run on demand via `aws ecs run-task` as the
# release step before rolling out new api/worker task revisions
# (scripts/release.sh runs inside this container; docs/runbook.md has
# the exact command).
resource "aws_ecs_task_definition" "migrate" {
  family                   = "rivet-${var.environment}-migrate"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name        = "migrate"
    image       = var.container_image
    essential   = true
    command     = ["scripts/release.sh"]
    environment = local.container_environment
    secrets     = local.container_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.migrate.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "migrate"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "rivet-${var.environment}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name    = "api"
    container_port    = 8000
  }

  depends_on = [aws_lb_listener.http]
}

resource "aws_ecs_service" "worker" {
  name            = "rivet-${var.environment}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }
}
