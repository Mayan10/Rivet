resource "aws_elasticache_subnet_group" "main" {
  name       = "rivet-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "rivet-${var.environment}"
  description           = "Rivet job queue + rate-limit counters (RQ, Phase 8; rate_limit.py, Phase 11)"

  engine         = "redis"
  engine_version = "7.1"
  node_type      = var.redis_node_type

  num_cache_clusters = 1 # staging; production wants >= 2 for failover (docs/runbook.md)

  subnet_group_name = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = false # would require rediss:// + TLS config in redis_url -- not wired up yet, matches local dev's plain redis://
}
