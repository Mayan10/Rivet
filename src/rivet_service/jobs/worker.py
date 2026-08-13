"""RQ worker entrypoint: ``python -m rivet_service.jobs.worker``.
Replaces docker-compose.yml's Phase 6 placeholder ("no jobs defined yet,
see Phase 8").
"""

from __future__ import annotations

import logging

from rq import Worker

from .queue import QUEUE_NAME, get_redis_connection

logging.basicConfig(level=logging.INFO)


def main() -> None:
    connection = get_redis_connection()
    worker = Worker([QUEUE_NAME], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
