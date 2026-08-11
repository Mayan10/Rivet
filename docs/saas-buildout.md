# Rivet: backend build-out spec

Drop this at `docs/saas-buildout.md` in the repo. Work through it one phase per
Claude Code session, not all at once.

---

## 0. Standing rules (put these in `CLAUDE.md` at the repo root)

Claude Code reads `CLAUDE.md` automatically at the start of every session, so
these constraints stick without re-pasting them.

```markdown
# Rivet: working rules

## Hard boundaries
- `src/rivet/core/`, `src/rivet/render/`, `src/rivet/export/` are a PURE
  library. They must never import anything from the service layer, never
  touch the database, network, filesystem (beyond the caller-supplied path),
  environment variables, or a request context. Do not thread `user_id`,
  `org_id`, or plan information into the generator. If a feature seems to
  need it, the answer is a parameter on `GenerationRequest` or a check in
  the service layer before the call, not a change to the engine.
- All new service code lives in `src/rivet_service/`.
- `pytest` must pass at the end of every task. Do not leave a red suite.
- Every schema change goes through an Alembic migration. No manual DDL,
  no `create_all()` outside tests.
- No new runtime dependency without telling me what it is, why the stdlib
  or an existing dep is not enough, and its maintenance status.

## Style
- Existing code style wins. Match it.
- New modules get tests in the same commit.
- Type hints on all public functions.
- Explain your plan before writing code for anything touching auth,
  billing, or the download path. I need to be able to debug these myself.
```

---

## 1. What the engine already is, and what has to wrap it

Right now Rivet is a deterministic, CPU-only, sub-second generator with a
Flask endpoint, ephemeral download tokens, no database, no users, no state.
That is a good starting point. The engine does not need to change at all.

What a subscription service adds around it:

| Concern | Today | Needed |
|---|---|---|
| Identity | none | users, orgs, sessions, API keys |
| Persistence | none | Postgres, projects and generation history |
| Artifacts | temp token | object storage, presigned downloads |
| Concurrency | in-process | job queue, worker processes |
| Money | none | plans, subscriptions, webhooks, quota |
| Limits | none | entitlements, rate limits, input clamps |
| Ops | dev server | containers, migrations, logs, error tracking |

---

## 2. Framework decision: move the API layer to FastAPI

Keep Flask if you want to save a day, but I would move. The reasons are
specific, not taste:

1. Auto-generated OpenAPI. Your frontend dev can codegen a typed client
   instead of you writing API docs by hand and them going stale.
2. Pydantic request validation maps cleanly onto the dataclasses in
   `core/models.py`, so `GenerationRequest` validation stops being manual.
3. Dependency injection gives you one clean place for "who is calling, what
   org, what are they entitled to", used identically by every route.

The API layer is thin (essentially one real endpoint), so the port is small
and it happens before you build eight more endpoints on top of Flask.

---

## 3. Package layout

```
src/rivet/                  # UNCHANGED. Pure engine.
src/rivet_service/
  main.py                   # FastAPI app factory, middleware, routers
  config.py                 # pydantic-settings, all env vars in one place
  db/
    base.py, session.py
    models/                 # SQLAlchemy models
    migrations/             # Alembic
  auth/
    passwords.py, sessions.py, api_keys.py, dependencies.py
  billing/
    plans.py, provider.py, webhooks.py, entitlements.py
  jobs/
    queue.py, worker.py, tasks.py
  storage/
    base.py, s3.py, local.py     # adapter, so local dev needs no cloud
  api/
    v1/                     # routers: auth, projects, generations, billing, meta
    schemas.py, errors.py
```

---

## 4. Data model

Postgres. These are the tables and the fields that matter.

**users**: id (uuid), email (citext unique), password_hash, email_verified_at,
created_at, deleted_at

**organizations**: id, name, created_at. **memberships**: user_id, org_id,
role (owner/admin/member).

Include orgs from day one even though every user starts solo. Retrofitting a
tenancy boundary after you have paying customers is genuinely painful, and
the Studio tier below depends on it.

**api_keys**: id, org_id, name, prefix (shown in UI), key_hash, created_by,
last_used_at, revoked_at. Store a hash, show the full key exactly once.

**plans**: code (free/pro/studio), name, price_cents, currency,
provider_price_id, limits (jsonb). Seeded via migration. Limits live here,
not scattered through `if plan == "pro"` branches.

**subscriptions**: org_id, provider, provider_customer_id,
provider_subscription_id, plan_code, status, current_period_start,
current_period_end, cancel_at_period_end.

**billing_events**: provider_event_id (unique), type, payload, processed_at.
This is what makes webhook handling idempotent. Providers retry, and they
deliver out of order.

**projects**: id, org_id, name, created_by, created_at, archived_at

**generations**: id, project_id, org_id, created_by, status
(queued/running/succeeded/failed), request_json, seed, engine_version,
rulebook_version, error_message, queued_at, started_at, finished_at

**candidates**: id, generation_id, index, score, score_breakdown_json

**artifacts**: id, candidate_id, kind (png/svg/dxf), storage_key,
size_bytes, sha256, watermarked (bool)

**usage_events**: id, org_id, kind (generation/dxf_export), quantity,
generation_id, occurred_at. Append-only. Compute quota by summing over the
current billing period rather than keeping a mutable counter, because a
counter and a subscription period boundary will eventually disagree and you
will not be able to reconstruct the truth.

### Make determinism a product feature

You already guarantee that the same request plus seed gives byte-identical
output across processes. That is worth more here than it is in the repo:

- Store `request_json` + `seed` + `engine_version` + `rulebook_version` on
  every generation. You can then regenerate any historical plan on demand
  instead of storing artifacts forever, and prune old artifacts on a TTL.
- Ship a `RULEBOOK_VERSION` constant in `core/rules.py` now and bump it on
  every rule change. When a customer says "my plan came out different this
  time", you can point at the exact version that produced each one. Without
  this, you have a support problem you cannot answer.

---

## 5. Auth

Two paths, one shared resolution:

- **Web app**: email + password, argon2id hashing, session token in an
  httpOnly + Secure + SameSite=Lax cookie. Email verification and password
  reset via signed, expiring tokens. Add Google OAuth later if your frontend
  dev wants it.
- **Programmatic**: `Authorization: Bearer rvt_live_...`, hashed lookup.
  This is a real selling point given the CLI and library surface already
  exist, but gate it to the paid tier.

Both resolve through one dependency that returns
`(user_or_none, org, entitlements)`. Every route depends on that and nothing
else reads plan codes directly.

Generic error messages on login failure (do not distinguish "no such user"
from "wrong password"). Rate limit login, register, and password reset by IP
and by email.

---

## 6. Jobs and storage

Generation is sub-second on a laptop, which tempts you to keep it
synchronous. Do not. Multi-candidate search on a large plot is CPU-bound,
and CPU-bound work inside your web workers means one expensive request
stalls every other user on that process. This is the single most common way
small Python services fall over.

- **Redis + RQ.** Simpler than Celery and enough for this shape of work.
- `POST /generations` validates, checks quota, writes a `queued` row,
  enqueues, returns `202` with the generation id.
- Worker runs the engine, renders PNG/SVG, exports DXF, uploads each to
  object storage, writes candidate and artifact rows, marks succeeded.
- Client polls `GET /generations/{id}`. Add SSE later if the UX needs it.
- Hard per-job timeout. A pathological request must die, not pin a worker.

**Storage**: an adapter interface with an S3 implementation and a local-disk
implementation, so `docker compose up` needs no cloud account. Cloudflare R2
is the cheap choice in production (S3-compatible, no egress fees, and DXF
downloads are pure egress). Buckets stay private. Downloads go through your
API, which checks entitlement and then issues a short-lived presigned URL.
Artifact keys are uuids, never guessable or sequential.

---

## 7. Entitlements and plans

One function, one dataclass:

```python
@dataclass(frozen=True)
class Entitlements:
    monthly_generations: int
    max_candidates: int
    max_plot_area_sqm: float
    max_rooms: int
    dxf_export: bool
    watermark_previews: bool
    multi_storey: bool
    api_access: bool
    priority_queue: bool
    history_retention_days: int

def entitlements_for(org) -> Entitlements: ...
```

Enforce in three places and nowhere else: request validation (clamp
candidates and plot size), quota check before enqueue, download handler
(DXF gated, watermark applied at render time for free tier).

A starting tier structure, adjust once you have talked to buyers:

| | Free | Pro | Studio |
|---|---|---|---|
| Generations/mo | 5 | 200 | 1,000 |
| Candidates/request | 1 | 3 | 5 |
| PNG/SVG | watermarked | clean | clean |
| DXF export | no | yes | yes |
| Project history | 7 days | unlimited | unlimited |
| API keys | no | no | yes |
| Seats | 1 | 1 | 5+ |

The watermark should be applied in the renderer as an explicit parameter
passed in by the service layer, not by the renderer knowing about plans.

Also set absolute safety ceilings independent of plan: max plot dimension,
max rooms, max candidates. Someone will POST a 500m x 500m plot with 40
rooms and 20 candidates, and it should be rejected at validation, not
discovered when your worker OOMs.

---

## 8. Billing

**Stripe Checkout + Customer Portal** if you are billing internationally in
USD. This is the least code by a wide margin: Stripe hosts the payment page
and the plan management page, and you handle the redirect plus webhooks.

If the entity is Indian and you are pricing in INR, use **Razorpay
Subscriptions** instead. Recurring card payments in India go through the RBI
e-mandate flow, which behaves differently from Stripe's, and Stripe's India
support for recurring international cards has its own constraints. Decide
this before writing the billing module, because it changes the integration
shape, not just the API keys. Check the current rules yourself rather than
trusting any summary, including this one.

Rules that matter regardless of provider:

- **Webhooks are the source of truth.** Never grant access based on the
  post-checkout redirect. The user can close the tab; the webhook still
  fires.
- **Idempotent handler.** Insert into `billing_events` on the provider event
  id with a unique constraint; if the insert conflicts, you have already
  processed it, return 200 and stop.
- **Verify the signature** on every webhook. An unverified billing webhook
  endpoint is an "upgrade myself to Studio for free" endpoint.
- Handle the full state machine: trialing, active, past_due, canceled,
  unpaid. `past_due` should degrade to free-tier limits, not hard-lock the
  account, and it should surface in the UI.
- Store the provider customer id on the org the first time you see it.

---

## 9. API surface for your frontend dev

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/logout
POST   /api/v1/auth/verify-email
POST   /api/v1/auth/request-password-reset
POST   /api/v1/auth/reset-password

GET    /api/v1/me                      -> user, org, plan, entitlements, usage this period

GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}

POST   /api/v1/projects/{id}/generations   -> 202 {generation_id}
GET    /api/v1/generations/{id}            -> status, candidates, scores, preview URLs
GET    /api/v1/generations/{id}/candidates/{n}/download?format=dxf|png|svg
DELETE /api/v1/generations/{id}

GET    /api/v1/api-keys
POST   /api/v1/api-keys
DELETE /api/v1/api-keys/{id}

POST   /api/v1/billing/checkout-session
POST   /api/v1/billing/portal-session
POST   /api/v1/webhooks/stripe

GET    /api/v1/meta/room-types
GET    /api/v1/meta/rules
GET    /healthz
GET    /readyz
```

Consistent error envelope on every 4xx/5xx: `{"error": {"code": "...",
"message": "...", "details": {...}}}`. Codes your frontend will need to
branch on specifically: `quota_exceeded`, `plan_required`,
`validation_failed`, `infeasible_program` (the engine's existing feasibility
warnings, surfaced properly).

Hand your frontend dev the generated OpenAPI spec URL, not a document.

---

## 10. Ops

- Multi-stage `Dockerfile`, non-root user, one image, two entrypoints
  (`api`, `worker`).
- `docker-compose.yml` for local: api, worker, postgres, redis, minio.
  Anyone should be able to clone and `docker compose up`.
- Alembic migrations run as an explicit release step, not on container boot
  (two containers booting at once will race).
- Structured JSON logs, request id on every line, never log secrets or
  full request bodies containing PII.
- Sentry for errors. Set it up on day one, not after the first outage.
- Extend CI: run migrations against a Postgres service container, run the
  full suite, build the image.

**Deploy target.** Railway or Fly.io gets you live fastest with managed
Postgres and Redis attached. AWS (ECS Fargate + RDS + ElastiCache + S3)
costs you a week of setup but lines up with the SAA cert you already hold
and gives you something concrete to talk about. Either is defensible. What
is not defensible is Postgres and Redis self-hosted on the same box as the
app, so do not let Claude Code talk you into a single-VM docker-compose
production deploy.

---

## 11. Security checklist

- Argon2id for passwords, never SHA/bcrypt-with-defaults.
- CORS locked to your frontend origin, credentials allowed, no wildcard.
- CSRF protection on cookie-authenticated state-changing routes.
- Rate limits: unauthenticated endpoints by IP, authenticated by org.
- Input clamps as above, enforced before the job is enqueued.
- Presigned URLs expire in minutes, not hours.
- Secrets from environment only. Add a CI check that fails on committed
  secrets.
- Account deletion actually deletes: rows, artifacts in object storage, and
  the provider customer record.

---

## 12. Legal, before you charge anyone

This produces drawings people may build from. The MIT-licensed repo
disclaimer is not sufficient once money changes hands.

- Terms of Service and Privacy Policy, accepted at signup with a stored
  timestamp and version.
- The "design guidance, not a stamped drawing, have it reviewed by a
  licensed engineer or architect" language needs to be in the ToS, in the
  UI at export time, and embedded in the DXF title block itself.
- A limitation of liability clause.

I am not a lawyer and this is not legal advice. Get an actual lawyer to
review the ToS before you take the first payment. It is cheap relative to
the downside.

---

## 13. Phase plan

One Claude Code session per phase. Each ends with green tests and a commit.
Do not hand it phases 1 through 7 in one prompt; it will produce a large
volume of code you cannot review, and the phases have dependencies it will
guess at.

**Phase 1: skeleton.** FastAPI app, config, Postgres + Alembic, docker-compose
with all services, `/healthz`, `/readyz`, port the existing generate endpoint
to `/api/v1` behind no auth, CI extended and green. Nothing else. This phase
exists to prove the plumbing works.

**Phase 2: auth.** Users, orgs, memberships, sessions, email verification,
password reset, API keys, `/me`. The `current_context` dependency.

**Phase 3: persistence and jobs.** Projects, generations, candidates,
artifacts. RQ queue and worker. Storage adapter (local + S3). Full async
generate flow with polling and the download endpoint.

**Phase 4: entitlements and quota.** Plans table, `entitlements_for`, usage
events, enforcement at the three points, watermarking, `RULEBOOK_VERSION`.

**Phase 5: billing.** Checkout, portal, webhooks, `billing_events`,
subscription state machine, past_due degradation.

**Phase 6: hardening.** Rate limits, CORS, CSRF, Sentry, structured logging,
input clamps, ToS acceptance, account deletion.

**Phase 7: deploy.** Production Dockerfile, migration release step, staging
environment, smoke test script, runbook in `docs/`.

### Phase prompt template

```
Read CLAUDE.md and docs/saas-buildout.md.

Implement Phase N only: <one-line goal>.

Before writing code:
1. List the files you will create or modify.
2. Tell me the schema changes and show me the migration plan.
3. Flag anything in the spec that is wrong, ambiguous, or that you would
   do differently, and wait for my answer.

Then implement. Constraints:
- Do not touch src/rivet/core, src/rivet/render, src/rivet/export.
- Tests for everything new, in the same commit.
- pytest green before you tell me you are done.
- Do not start Phase N+1.
```

---

## 14. One thing to decide before Phase 1

You are about to build seven phases of infrastructure for a product nobody
has paid for yet. The cheapest possible validation is to deploy Phase 1 as
a public free tool with a "join the waitlist for DXF export" form, and see
whether architects, builders, or homeowners actually sign up. That takes a
weekend and tells you which tier structure above is wrong before you have
written the billing module around it. Phases 2 through 7 are much more
pleasant to build when you know someone is waiting for them.
