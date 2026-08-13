variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type        = string
  default     = "staging"
  description = "Short name used in resource names/tags. One state file/module instance per environment -- see docs/runbook.md for how to add production later."
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "az_count" {
  type        = number
  default     = 2
  description = "RDS and ALB both require subnets in at least 2 AZs."
}

variable "container_image" {
  type        = string
  description = "Full ECR image URI:tag to deploy, e.g. 123456789012.dkr.ecr.us-east-1.amazonaws.com/rivet-service:abc1234. Produced by CI (see .github/workflows/ci.yml's \"Build image\" step -- pushing it is Phase 12's one remaining CI gap, see docs/runbook.md) or pushed by hand for a first deploy."
}

variable "api_desired_count" {
  type    = number
  default = 1
}

variable "worker_desired_count" {
  type    = number
  default = 1
}

variable "api_cpu" {
  type    = number
  default = 512 # 0.5 vCPU -- Fargate task-size units (1024 = 1 vCPU)
}

variable "api_memory" {
  type    = number
  default = 1024 # MiB
}

variable "worker_cpu" {
  type    = number
  default = 1024 # generation is CPU-bound (section 6) -- gets a full vCPU, not a fraction
}

variable "worker_memory" {
  type    = number
  default = 2048
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro" # staging-sized; resize for production
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 20
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "certificate_arn" {
  type        = string
  default     = ""
  description = "ACM certificate ARN for the ALB's HTTPS listener. Empty means HTTP-only (fine for a first staging deploy behind no real domain yet; never leave production on HTTP -- section 5's cookie_secure setting requires HTTPS to even work correctly)."
}
