# Artifact storage (storage/s3.py). Private -- downloads only ever go
# through the API's own presigned-URL flow (section 6), never a public
# bucket URL.
resource "aws_s3_bucket" "artifacts" {
  bucket = "rivet-artifacts-${var.environment}"
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Free-tier history is 7 days (billing/plans.py); paid tiers are
# unlimited. This bucket-wide rule can't see plan tier, so it doesn't
# enforce that -- it's a much longer backstop against unbounded storage
# growth from orphaned artifacts (a generation whose DB row was deleted
# but whose S3 objects survived some bug), not a product-facing retention
# policy. Actual per-plan retention enforcement is a future phase's job
# (a scheduled cleanup task reading Entitlements.history_retention_days),
# not something Terraform can express.
resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    id     = "backstop-expiry"
    status = "Enabled"
    filter {}
    expiration { days = 365 }
  }
}
