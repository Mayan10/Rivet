# Production image (Phase 12, docs/saas-buildout.md section 10):
# "multi-stage, non-root user, one image, two entrypoints (api, worker)."
#
# One image serves both roles -- docker-compose.yml and the ECS task
# definitions (deploy/terraform/ecs.tf) select which by overriding the
# container's command at the orchestrator level, not by building two
# images:
#   api:    uvicorn rivet_service.main:app --host 0.0.0.0 --port 8000
#   worker: python -m rivet_service.jobs.worker
#
# Migrations are never run from this image's own entrypoint (booting two
# containers at once would race to apply them) -- see scripts/release.sh
# and docs/runbook.md.

FROM python:3.12-slim AS builder

WORKDIR /app

# Build-time only: compiling any wheel that needs it (e.g. psycopg's
# non-binary fallback, on a platform with no prebuilt wheel) shouldn't
# require a compiler in the final image.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY packages/engine ./packages/engine
COPY apps/api ./apps/api

RUN pip install --no-cache-dir --prefix=/install ".[service]"


FROM python:3.12-slim

# Never run the process that's reachable from the internet as root.
RUN useradd --create-home --uid 1000 rivet
WORKDIR /app

COPY --from=builder /install /usr/local
# rivet_service/rivet are already importable from the site-packages copy
# above (a real, non-editable install) -- this copy exists only because
# alembic.ini's script_location is a path relative to the container's
# working directory (apps/api/rivet_service/db/migrations), not an
# importable module path. Only the service tree is needed for migrations.
COPY apps/api ./apps/api
COPY alembic.ini ./
COPY scripts ./scripts

USER rivet
EXPOSE 8000

CMD ["uvicorn", "rivet_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
