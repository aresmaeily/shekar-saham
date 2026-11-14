# Contributing to RADAR BOURSE

Thank you for considering contributing to RADAR BOURSE. This document describes the development setup, the testing discipline, and the pull-request workflow.

## Development setup

Requirements: Python 3.10+ (CI uses 3.13), Git, and optionally Docker and Node.js (for the Electron shell).

```bash
# backend
cd backend
pip install -r requirements.txt
python -m app.main          # start at http://127.0.0.1:8000
```

If TSETMC / BrsApi is unreachable, the app falls back to demo data automatically; set `DATA_SOURCE=mock` to force it.

## Testing discipline

Every push to `main`/`develop` runs four CI jobs (`ci.yml`, `windows.yml`, `windows-installer.yml`): test-backend, build-docker, windows-validation, and build-installer. Before opening a PR, please run at least:

```bash
cd backend
python -m pytest tests/ -q          # full battery
python -m pyflakes app/             # lint
node --check ../frontend/js/*.js    # frontend syntax (where applicable)
python ../scripts/validate_frontend_static.py   # frontend contract validator
```

Rules the project enforces on itself:

- Never weaken, skip or delete an existing test assertion to make CI pass. Fix the code, or record the reason explicitly in the changelog.
- Keep the trust/disclosure behavior intact: the UI must never present demo/mock data as live data.
- Feature flags `AI2_ENABLED` and `SCHEDULER_ENABLED` default to disabled; do not flip them in a contribution.

## Pull-request workflow

1. Fork / create a feature branch off `main`.
2. Keep changes focused; one logical change per PR.
3. Ensure all four required checks pass on your branch.
4. Write a descriptive commit message (what changed and why).
5. For UI changes, include before/after notes and mention accessibility (RTL, contrast, keyboard focus).

## Reporting issues

- Bugs: open a GitHub issue with the affected version, environment, and minimal reproduction steps.
- Security vulnerabilities: **do not** open a public issue — follow [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
