# Changelog

All notable changes to RADAR BOURSE are documented in this file. Detailed stage-by-stage records (Persian) live in [docs/CHANGELOG.md](docs/CHANGELOG.md); the inspection-fix report for v0.6 is in [CHANGELOG_V06.md](CHANGELOG_V06.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] — 2026-11-14

First official GitHub Release.

### Added
- **RADAR Design System v1.0** — single-source design tokens (semantic light/dark, typography scale, 4px spacing), grouped navigation (32 routes in 6 logical clusters, zero hidden routes), 35-symbol SVG icon sprite, skeleton/empty states, and a measured WCAG 2.2 AA contrast pass in both themes.
- **Windows desktop installer pipeline** — CI builds the actual (unsigned) NSIS installer from an exact source SHA on every push to `main`, bundles the FastAPI backend + frontend, embeds `RELEASE_PROVENANCE.json` (source SHA, build run URL, size, SHA-256 recorded in the public build log).
- **Prediction registry** — durable, append-only SQLite (WAL) store with per-row tamper evidence, verified backup/restore, restart recovery, and calibration metrics (Brier score / ECE) exposed through the product-loops API.
- **Governed product-loops surface** (`/api/v10/productloops`) — declared dossiers with point-in-time cutoffs, live cross-source quote-conflict detection, governed research permission posture, on-demand product audit probes, and prediction feedback loops.
- **Experimental AI Studio UI module** — ships disabled by default (`AI2_ENABLED=0`, owner-gated).
- **Open-source documentation set** — professional English README with a full Persian edition (`README.fa.md`), MIT LICENSE, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, and this changelog.

### Changed
- Service-worker cache bumped to `v3-0-20` (tokens.css precache); all counter-pin tests updated in step, no assertions weakened.
- Trust banner restyled (calm amber, AA contrast); tables get a sticky header and tabular numerals; responsive breakpoints at 1280/1024/768/560.

### Quality
- Full backend battery: 3,231 passed / 1 skipped / 0 failed; frontend-contract + E2E subset 100/100; real-browser sweep of all 32 tabs with zero console errors, zero page errors, zero horizontal overflow at 1440/768/390.

## [0.6.0] — Production Hardening

See [CHANGELOG_V06.md](CHANGELOG_V06.md) for the full inspection-fix report. Highlights:

### Fixed (P0)
- Flow coverage: polling coverage restored to 600s (`sufficient=True`), big_moves 0 → 9.
- Trust level surfaced in all APIs + banner CSS.
- Security headers (CSP, `X-Content-Type-Options`, `X-Frame-Options`), restrictive CORS (from `*` to localhost), rate limiting (429 after the heavy-endpoint quota), crypto singleton fix, BrsApi key default removed.

### Improved (P1/P2)
- Lock contention split into three short phases (lower p95 latency); fundamental cache (LRU 200 + TTL 300s); circuit breakers for tsetmc/brsapi with metrics; notify dry-run anti-spam; Filter DSL injection returns 400 with an explicit refusal payload; backtest and options risk disclaimers added.

## [0.5.0] and earlier

Initial development releases: phased build-out of the hunting core (smart money, suspicious volume, entry/exit signals, simple fundamentals, dashboard), SQLite snapshots, big-players movements, symbol pages with charts, market map, filter DSL, WebSocket, Telegram/Bale notifications, backtesting and the options module. The BrsApi key default was removed in this era (see CHANGELOG_V06.md).

[3.0.0]: https://github.com/aresmaeily/shekar-saham/releases/tag/v3.0.0
[0.6.0]: https://github.com/aresmaeily/shekar-saham/releases
[0.5.0]: https://github.com/aresmaeily/shekar-saham/releases
