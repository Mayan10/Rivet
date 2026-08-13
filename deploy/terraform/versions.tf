# Phase 12 (docs/prompts.md, docs/saas-buildout.md sections 10 & 13):
# a real, reviewable definition of the staging environment -- ECS
# Fargate + RDS + ElastiCache, the deploy target decided 2026-08-12
# (docs/prompts.md section 5).
#
# This module was written and reviewed but never applied against a real
# AWS account in this session (no working credentials were available --
# see docs/runbook.md's "Before you run this" section). Run
# `terraform validate` / `terraform plan` yourself before `apply`.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state, not local -- a solo/small-team project still shouldn't
  # keep Terraform state on one laptop. Create this bucket (and enable
  # versioning + a DynamoDB lock table) once, by hand, before the first
  # `terraform init` -- see docs/runbook.md. Bucket/table names are
  # placeholders; replace them for your own AWS account.
  backend "s3" {
    bucket         = "rivet-terraform-state"
    key            = "staging/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "rivet-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "rivet"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
