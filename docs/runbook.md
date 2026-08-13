# Runbook

Operational reference for `deploy/terraform/` (staging: ECS Fargate + RDS
+ ElastiCache, decided 2026-08-12 -- see `docs/prompts.md` section 5).

**Before you run this**: this module was written and reviewed but never
applied against a real AWS account -- no working AWS credentials were
available in the session that wrote it (`aws sts get-caller-identity`
failed). Run `terraform validate` and `terraform plan` yourself and read
the plan output carefully before the first `apply`. Everything below is
the intended procedure, not a verified one.

## One-time setup

### 1. Terraform state bucket

Terraform state isn't managed by Terraform itself (chicken-and-egg).
Create it once, by hand:

```bash
aws s3 mb s3://rivet-terraform-state --region us-east-1
aws s3api put-bucket-versioning --bucket rivet-terraform-state \
  --versioning-configuration Status=Enabled
aws dynamodb create-table --table-name rivet-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

Bucket/table names must match `deploy/terraform/versions.tf`'s `backend
"s3"` block, or change that block to match yours.

### 2. GitHub OIDC role (for `.github/workflows/deploy.yml`)

`deploy.yml` pushes images to ECR via an assumed IAM role, not stored AWS
access keys. Create an IAM role trusting GitHub's OIDC provider for this
repo, scoped to `ecr:*` on the `rivet-service` repository, then set it as
the `AWS_DEPLOY_ROLE_ARN` repo secret (Settings -> Secrets and
variables -> Actions). AWS's own guide: search "GitHub Actions OIDC AWS"
-- the exact trust policy JSON depends on your account id and this
repo's `org/name`, so it isn't reproduced here.

### 3. First `terraform apply`

```bash
cd deploy/terraform
terraform init
terraform validate
terraform plan -var container_image=<any-placeholder>:latest
terraform apply -var container_image=<any-placeholder>:latest
```

The very first apply needs *some* value for `container_image` even
though nothing has been pushed to ECR yet -- the ECS services will fail
to start until step 5 below, which is expected. `terraform apply`
creates the ECR repository itself, so push before re-running apply with
the real image URI (`terraform output ecr_repository_url`).

### 4. Populate the Stripe secrets

`secrets.tf` creates the Secrets Manager entries with a `REPLACE_ME`
placeholder (real values are never in `.tfvars` or committed anywhere --
that's exactly what `ci.yml`'s `secret-scan` job exists to catch):

```bash
aws secretsmanager put-secret-value \
  --secret-id rivet/staging/stripe-secret-key --secret-string "sk_live_..."
aws secretsmanager put-secret-value \
  --secret-id rivet/staging/stripe-webhook-secret --secret-string "whsec_..."
```

## Deploying a new version

1. **Build and push the image**: run `.github/workflows/deploy.yml`
   manually (Actions tab -> "Build and push image" -> Run workflow), or
   locally:
   ```bash
   docker build -t <ecr_repository_url>:$(git rev-parse --short HEAD) .
   docker push <ecr_repository_url>:$(git rev-parse --short HEAD)
   ```
2. **Apply Terraform with the new image tag**:
   ```bash
   terraform apply -var container_image=<ecr_repository_url>:<tag>
   ```
   This registers new api/worker task definition revisions but does not
   itself guarantee migrations ran first -- do step 3 before this
   finishes rolling traffic to the new revision if the migration isn't
   backward-compatible with the old code (expand/contract, not a
   same-deploy breaking schema change).
3. **Run the migration release step** (`scripts/release.sh`, inside the
   same image -- section 10: "an explicit release step, not on container
   boot"):
   ```bash
   aws ecs run-task \
     --cluster $(terraform output -raw ecs_cluster_name) \
     --task-definition $(terraform output -raw migrate_task_definition_arn) \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[<private-subnet-ids>],securityGroups=[<ecs-tasks-sg-id>]}"
   ```
   Wait for it to reach `STOPPED` with exit code 0 (`aws ecs describe-tasks`)
   before moving on.
4. **Confirm the ECS services stabilized**: `aws ecs describe-services
   --cluster <cluster> --services rivet-staging-api rivet-staging-worker`
   -- `runningCount` should equal `desiredCount` on both.
5. **Smoke test**:
   ```bash
   scripts/smoke_test.sh $(terraform output -raw api_url)
   ```

## Rollback

Task definitions are versioned automatically by ECS (each `apply` or
`register-task-definition` call creates a new revision; old ones aren't
deleted). To roll back:

```bash
aws ecs update-service --cluster <cluster> --service rivet-staging-api \
  --task-definition rivet-staging-api:<previous-revision-number>
aws ecs update-service --cluster <cluster> --service rivet-staging-worker \
  --task-definition rivet-staging-worker:<previous-revision-number>
```

A rollback that also needs the *database* rolled back (the new migration
broke something) is a separate, harder problem -- this is exactly why
migrations should be expand/contract (additive first, destructive later
in a following deploy), so a code rollback alone is usually sufficient.

## Common incident checks

- **`GET /readyz` on the ALB DNS name (`terraform output api_url`)** --
  501/503 means the API is up but can't reach Postgres; check RDS status
  and the `ecs_tasks` -> `rds` security group rule.
- **CloudWatch Logs** -- `/ecs/rivet-staging/api`,
  `/ecs/rivet-staging/worker`, `/ecs/rivet-staging/migrate`. Every line
  is JSON with a `request_id` field (Phase 11) -- grep for one to follow
  a specific request across log lines.
- **ECS service events**: `aws ecs describe-services ...` includes an
  `events` list -- task launch failures, health check failures, and
  deployment circuit-breaker rollbacks all show up there first.
- **Sentry** (if `SENTRY_DSN` is set on the task definitions --
  `secrets.tf`/`ecs.tf` don't wire it up automatically, since no project
  exists yet; add a `sentry_dsn` secret + reference the same way as the
  Stripe ones once you have one).
- **Worker not processing jobs**: check the ElastiCache Redis cluster is
  reachable from the `worker` service's subnets, and that
  `rivet_service.jobs.worker`'s process is actually the running command
  (`aws ecs describe-tasks` -> `overrides.containerOverrides` or the
  task definition's own `command`).

## Adding a production environment

This module is written for one environment per state file (`var.environment`,
defaulted to `"staging"`). Don't widen it into an `if environment ==
"production"` branch inside the existing files -- instantiate the module
again with its own backend `key` (e.g. `production/terraform.tfstate`)
and its own `.tfvars` (larger instance sizes, `multi_az = true` already
conditional on `environment == "production"` in `rds.tf`, a real ACM
certificate, `deletion_protection = true`). Two independent state files
means a mistake in staging can't touch production's resources.
