# DATABASE_URL and SECRET_KEY are values Terraform itself generates
# (the RDS password, a random app secret) -- safe to manage end to end.
# STRIPE_SECRET_KEY/STRIPE_WEBHOOK_SECRET come from an external Stripe
# account and are never typed into a .tfvars file (that risks exactly
# the kind of committed-secret leak ci.yml's gitleaks job exists to
# catch) -- Terraform creates the secret container with a placeholder,
# an operator populates the real value once via `aws secretsmanager
# put-secret-value` (docs/runbook.md), and `ignore_changes` stops a
# later `apply` from overwriting it back to the placeholder.

resource "random_password" "app_secret_key" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "database_url" {
  name = "rivet/${var.environment}/database-url"
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = "postgresql+psycopg://${aws_db_instance.main.username}:${random_password.db.result}@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}"
}

resource "aws_secretsmanager_secret" "app_secret_key" {
  name = "rivet/${var.environment}/secret-key"
}

resource "aws_secretsmanager_secret_version" "app_secret_key" {
  secret_id     = aws_secretsmanager_secret.app_secret_key.id
  secret_string = random_password.app_secret_key.result
}

resource "aws_secretsmanager_secret" "stripe_secret_key" {
  name = "rivet/${var.environment}/stripe-secret-key"
}

resource "aws_secretsmanager_secret_version" "stripe_secret_key" {
  secret_id     = aws_secretsmanager_secret.stripe_secret_key.id
  secret_string = "REPLACE_ME"
  lifecycle { ignore_changes = [secret_string] }
}

resource "aws_secretsmanager_secret" "stripe_webhook_secret" {
  name = "rivet/${var.environment}/stripe-webhook-secret"
}

resource "aws_secretsmanager_secret_version" "stripe_webhook_secret" {
  secret_id     = aws_secretsmanager_secret.stripe_webhook_secret.id
  secret_string = "REPLACE_ME"
  lifecycle { ignore_changes = [secret_string] }
}
