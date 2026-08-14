"""Redis + RQ (docs/saas-buildout.md section 6: "simpler than Celery and
enough for this shape of work").
"""

from __future__ import annotations

import redis
from rq import Queue

from ..config import get_settings

QUEUE_NAME = "generations"


def get_redis_connection() -> redis.Redis:
    return redis.from_url(get_settings().redis_url)


def get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=get_redis_connection())
