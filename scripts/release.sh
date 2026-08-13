#!/usr/bin/env bash
# The migration release step (docs/saas-buildout.md section 10: "Alembic
# migrations run as an explicit release step, not on container boot --
# two containers booting at once would race to apply them").
#
# Runs inside the same image as the api/worker containers (it's already
# on the image's PATH -- see the Dockerfile), as a one-off task, before
# the new api/worker task revisions are rolled out. deploy/terraform's
# "migrate" ECS task definition runs exactly this; docs/runbook.md
# documents the sequencing. Never invoked from the image's own CMD or
# from api/worker's startup path.
set -euo pipefail

echo "Running database migrations..."
alembic -c alembic.ini upgrade head
echo "Migrations complete."
