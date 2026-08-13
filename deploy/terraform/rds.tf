# Password: generated here and stored in Secrets Manager (secrets.tf),
# never in a .tfvars file or tfstate-adjacent plaintext -- tfstate itself
# still contains it (RDS makes it a computed attribute), which is exactly
# why the S3 backend above has encrypt = true and the bucket must be
# private (see docs/runbook.md's "state bucket" setup step).
resource "random_password" "db" {
  length  = 32
  special = false # simplifies passing it through DATABASE_URL without extra escaping
}

resource "aws_db_subnet_group" "main" {
  name       = "rivet-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "main" {
  identifier     = "rivet-${var.environment}"
  engine         = "postgres"
  engine_version = "16"

  instance_class        = var.db_instance_class
  allocated_storage     = var.db_allocated_storage_gb
  storage_encrypted     = true
  db_subnet_group_name  = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  db_name  = "rivet"
  username = "rivet"
  password = random_password.db.result

  # citext (users.email -- see db/models/user.py) needs to already exist
  # before Alembic's first migration runs CREATE EXTENSION; Postgres
  # grants that on RDS without a superuser, so no extra step needed
  # beyond what the migration already does.

  publicly_accessible = false
  multi_az             = false # staging; set true for production (docs/runbook.md)
  skip_final_snapshot  = var.environment != "production"
  deletion_protection  = var.environment == "production"

  backup_retention_period = 7
}
