# Rivet web

The Next.js front end for [Rivet](../../README.md) — currently the public
marketing surface (landing, pricing, legal) with the API client and design
system in place for the product UI.

It talks to the FastAPI service in `src/rivet_service/` over HTTP and holds
no engine logic of its own. Nothing here imports Python; nothing in `src/`
imports from here.

## Running it

From the repo root, once:

```bash
bun install
```

Then either run the whole dev loop (this app on :3000 plus the backend on
:8000, via mprocs):

```bash
bun run dev
```

…or just this app, if a backend is already running or you're working on
pages that don't call the API:

```bash
bun run --cwd apps/web dev
# -> http://localhost:3000
```

The backend half of `bun run dev` expects the Python venv at the repo root
(`.venv/`) with the service extra installed — see the root
[`CONTRIBUTING.md`](../../CONTRIBUTING.md). This app itself is pure
Bun/Next and ignores the venv entirely.

## Configuration

Copy `.env.example` to `.env.local`:

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL of the FastAPI backend. Defaults to `http://localhost:8000`, which matches `mprocs.yaml`. |
| `NEXT_PUBLIC_SITE_URL` | Public origin of this site, used for canonical URLs, Open Graph, the sitemap, robots, and JSON-LD. |

`NEXT_PUBLIC_SITE_URL` must be set on every non-local deployment. A
production build without it warns and falls back to localhost rather than
silently baking a broken origin into SEO metadata — see `lib/site.ts`,
which is the single source of truth for the origin. Don't read
`process.env` for it anywhere else.

## Layout

```
app/
├── (marketing)/      # landing, pricing, privacy, terms
├── layout.tsx        # root layout + metadata
├── globals.css       # Tailwind v4 + design tokens
├── opengraph-image.tsx
├── sitemap.ts
└── robots.ts
components/
├── site/             # composed page sections (header, footer, pricing, …)
└── ui/               # shadcn primitives
lib/
├── api.ts            # fetch wrapper for the backend (cookie sessions)
├── plans.ts          # plan tiers, mirroring the backend
├── site.ts           # public origin resolution
└── utils.ts
```

Stack: Next.js 16 (App Router, RSC), React 19, Tailwind v4, shadcn/ui on
Base UI, lucide icons.

`lib/plans.ts` mirrors `src/rivet_service/billing/plans.py`, which is the
source of truth for what a plan actually entitles you to. The copy here
exists so the pricing page renders without a backend round-trip — when
tiers change, change both.

## Conventions

- Component return types are inferred, not annotated. Annotate
  non-component utilities (`lib/`) as normal.
- The regression gate is a full type-check plus lint, not unit tests:

  ```bash
  bun run --cwd apps/web lint
  bun run --cwd apps/web build
  ```

  CI (`.github/workflows/web.yml`) runs exactly these two on any change
  under `apps/web/`.
- Add tests only for non-trivial logic (data helpers, `lib/` utilities) —
  not for presentational components or pages.
- Frontend work goes on the `frontend` branch and touches only this
  folder. See the root [`AGENTS.md`](../../AGENTS.md) for the branch
  workflow and the layering rules.
