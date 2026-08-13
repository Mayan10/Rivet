# Dev-oriented image for local docker-compose use (Phase 6). A hardened,
# non-root, multi-stage production image is Phase 12's job
# (docs/saas-buildout.md section 13) -- this one exists so
# `docker compose up` works for anyone who clones the repo, not to be
# deployed as-is.

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir -e ".[service]"

COPY alembic.ini ./

EXPOSE 8000

CMD ["uvicorn", "rivet_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
