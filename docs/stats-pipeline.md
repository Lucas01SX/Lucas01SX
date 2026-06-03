# Stats Pipeline — Decision Record

## Context

GitHub profile READMEs commonly use external services to render stats cards
(github-readme-stats, streak-stats.demolab.com, etc.). These services are
third-party Vercel deployments that depend on GitHub API rate limits and uptime
they do not control.

In June 2026, both services were tested and confirmed broken — images returned
broken placeholders consistently, regardless of token configuration.

## Decision

Generate the stats SVG locally via a GitHub Action that:

1. Calls the GitHub GraphQL API directly using the built-in `GITHUB_TOKEN`
   (no PAT required, no external service)
2. Renders a static SVG with a tokyonight theme to `assets/stats.svg`
3. Commits the file back to the repo only when the content changes (idempotent)

The script (`scripts/generate_stats.py`) uses Python stdlib only — no `pip`
dependencies, no supply chain surface beyond the two pinned Actions.

## Consequences

- Stats are updated weekly (Monday 6:00 UTC) or on manual dispatch
- The generated SVG is committed to the repo (build artifact alongside source)
- `total_repos` uses `totalCount` from the API — unaffected by pagination, always exact
- `total_stars` aggregates over the first 100 repository nodes, ordered by descending
  star count; only zero-star repos fall off for profiles with more than 100 repositories
- If the Action fails, the last committed SVG remains visible — no broken image
- `URLError`, `HTTPError`, and `json.JSONDecodeError` are caught and re-raised as
  `RuntimeError` with enriched messages — the Action step still fails, and the
  enriched message is the error signal

## Actions pinned

| Action | Tag | Commit SHA |
|---|---|---|
| `actions/checkout` | v4.2.2 | `11bd71901bbe5b1630ceea73d27597364c9af683` |
| `actions/setup-python` | v5.6.0 | `a26af69be951a213d495a4c3e4e4022e16d87065` |

SHAs should be updated when upgrading action versions.
