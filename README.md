<div align="center">

# RADAR BOURSE — رادار بورس

**A professional, self-hosted board-reading and market-monitoring platform for the Tehran Stock Exchange (TSE).**

Inspired by [tablokhani.com](https://tablokhani.com)

[![CI](https://github.com/aresmaeily/shekar-saham/actions/workflows/ci.yml/badge.svg)](https://github.com/aresmaeily/shekar-saham/actions/workflows/ci.yml)
[![Windows validation](https://github.com/aresmaeily/shekar-saham/actions/workflows/windows.yml/badge.svg)](https://github.com/aresmaeily/shekar-saham/actions/workflows/windows.yml)
[![Windows installer](https://github.com/aresmaeily/shekar-saham/actions/workflows/windows-installer.yml/badge.svg)](https://github.com/aresmaeily/shekar-saham/actions/workflows/windows-installer.yml)
[![Release](https://img.shields.io/github/v/release/aresmaeily/shekar-saham)](https://github.com/aresmaeily/shekar-saham/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**English** | [فارسی](README.fa.md)

</div>

## What is RADAR BOURSE?

RADAR BOURSE is a web-based analytical workbench for TSE traders. It continuously watches the market and surfaces what matters at the right time: smart-money entries, unusual trading volume, symbols likely to hit the buy limit (queue) from negative prices, report-driven fundamental candidates, and early exit warnings based on money outflow, heavy supply and weakening buyer strength.

The system is fully self-hosted: a **FastAPI** backend with dedicated board-reading and signal engines, and an **RTL Persian dashboard** (32 analysis views, light/dark themes) served by the same process. A desktop experience is available as an Electron-based Windows installer, and the stack can also run under Docker. When the upstream market data sources are unreachable, the platform automatically falls back to a demo data generator so the entire UI and all algorithms remain testable — and the UI always discloses the current data trust level (live vs. demo) in a banner.

## Key capabilities

- **Smart-money radar** — hot-money detection for large retail trades (> 200M IRR), a "hot money plus" band (100–200M), and big-player in/out movements tracked on 10-minute windows.
- **Signal hunting** — *entry hunt* combines suspicious volume, buyer power and near-limit negative prices; *exit alerts* track money outflow, elevated sell ratio and weakening per-capita buying.
- **Custom screening** — a filter DSL for user-defined screens, a fundamental filter (P/E, EPS, market cap), and industry/sector group liquidity flow.
- **Analysis views** — market map, per-symbol pages with Pro charts, suspicious-volume and supply/demand analysis, institutional vs. retail behavior breakdown.
- **Alerts** — configurable alert rules with Telegram and Bale delivery.
- **Strategy and research** — backtesting, an options module, and a prediction registry with calibration metrics (Brier score / ECE).
- **Forex Pro** — gold and global instruments (GC1 / COMEX, DXY / TVC, S&P 500, US100, US30, Brent) via broker feeds, with a value-profile indicator.
- **Delivery** — web dashboard, Windows installer (Electron), Docker image, and an experimental Android wrapper (Capacitor).

> Note: the experimental AI Studio module ships **disabled by default** and only activates via an explicit owner-level configuration flag.

## Quick start

### Option A — Windows installer (desktop)

Download the latest installer from [**Releases**](https://github.com/aresmaeily/shekar-saham/releases). The installer is built automatically by CI from an exact source SHA (build provenance — source SHA, size and SHA-256 — is recorded in the public build log and in `RELEASE_PROVENANCE.json` inside the app).

> The installer is **unsigned** (no code-signing certificate), so Windows SmartScreen may show a warning: choose *More info → Run anyway*. The desktop shell bundles the FastAPI backend and serves the dashboard locally.

### Option B — Docker

```bash
./install.sh --docker        # build and run with Docker Compose
# or
docker compose up --build
```

Then open `http://localhost:8000`.

### Option C — From source (Python 3.10+)

```bash
cd backend
pip install -r requirements.txt

# start the server (automatically uses demo data if TSETMC is unreachable)
python -m app.main

# open http://127.0.0.1:8000
```

A one-shot helper is also available: `./install.sh` (native venv install + run), `./install.sh --check` (prerequisites only).

### Configuration (optional environment variables)

| Variable | Values | Purpose |
|----------|--------|---------|
| `DATA_SOURCE` | `mock` \| `tsetmc` \| `brsapi` | Market data source selection |
| `BRSAPI_KEY` | your key | BrsApi access (free key from brsapi.ir) |
| `TSETMC_BASE` | URL | TSETMC CDN base (default `https://cdn.tsetmc.com`) |
| `POLL_SECONDS` | integer | Market data polling interval |

## Data sources

1. **Priority 1** — direct connection to the public TSETMC endpoints (`cdn.tsetmc.com` / MarketWatch).
2. **Priority 2** — BrsApi (free API key).
3. **Development mode** — a demo generator with a realistic Tehran Stock Exchange symbol structure.

When neither source is reachable (for example outside Iran's network), the system switches to demo data automatically; the trust banner in the UI always states whether the displayed data is live or synthetic.

## Core modules (tablokhani-style tools)

| # | Module | Description |
|---|--------|-------------|
| 1 | Hot Money | Large retail trades > 200M IRR |
| 2 | Hot Money Plus | 100–200M IRR band |
| 3 | Market Play | Large / mid / small retail behavior |
| 4 | Big Players Movements | Hot-money in/out on 10-minute windows |
| 5 | Entry Hunt | Suspicious volume + buyer power + near-limit negative price |
| 6 | Exit Alert | Money outflow, high sell ratio, weakening per-capita strength |
| 7 | Fundamental Filter | P/E, EPS, market cap |
| 8 | Industry Hunt | Group/sector liquidity flow |

## Project structure

```
radar-bourse/
├── backend/          # FastAPI + analytical engines
│   └── app/
│       ├── api/      # REST endpoints
│       ├── engines/  # board-reading and signal algorithms
│       ├── data/     # data sources (TSETMC / BrsApi / demo)
│       ├── models/   # data models
│       ├── core/     # settings and infrastructure
│       └── services/ # business services
├── frontend/         # RTL Persian dashboard (vanilla JS + design tokens)
├── electron/         # Windows desktop shell + installer build
├── android-app/      # experimental Capacitor wrapper
├── e2e/              # end-to-end tests
├── data/             # cache and sample data
├── docs/             # structured docs: STATUS, architecture, design, governance
├── scripts/          # helper and validation scripts
├── Dockerfile / docker-compose.yml / entrypoint.sh
├── install.sh / start.sh
└── CHANGELOG.md      # release history (details: docs/CHANGELOG.md)
```

## Development and testing

The project runs a large automated test battery in CI on every push to `main`/`develop`:

- **test-backend** — pyflakes lint, the full pytest battery (3,200+ tests: unit + contract), and `pip-audit` dependency scanning (`cd backend && python -m pytest tests/ -q`).
- **build-docker** — the Docker image is built on every push.
- **windows-validation** — the Windows shell is validated end-to-end.
- **build-installer** — the actual (unsigned) NSIS installer artifact is built, with provenance recorded in the public log.

## Documentation

| Document | Content |
|----------|---------|
| [docs/STATUS.md](docs/STATUS.md) | Current project status |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | Detailed stage-by-stage change records |
| [CHANGELOG.md](CHANGELOG.md) | Release history summary |
| [docs/design/](docs/design/) | Design system, UI/UX audits and browser evidence |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup and contribution workflow |
| [SECURITY.md](SECURITY.md) | Security policy and vulnerability reporting |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards |

## Disclaimer

This software is an **analysis aid**, not a definitive buy/sell signal system. Trading decisions and their outcomes are the sole responsibility of the user.

## License

Released under the [MIT License](LICENSE).
