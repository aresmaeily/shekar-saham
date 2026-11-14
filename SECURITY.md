# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| latest release (v3.0.x) | yes |
| older tags / branches | no |

## Reporting a vulnerability

Please do **not** report security vulnerabilities through public GitHub issues.

Instead, use GitHub's **private vulnerability reporting** for this repository (Security tab → Report a vulnerability), which notifies the maintainer privately.

Include as much of the following as you can:

- Affected version / commit SHA and component (backend API, frontend, Electron shell, Docker setup).
- Step-by-step reproduction or proof-of-concept.
- Impact assessment and any known mitigations.

You will receive an acknowledgment, and the issue will be triaged before any public disclosure. Fixes are released as patch versions with release notes describing the vulnerability at a responsible level of detail.

## Security posture notes

- API keys (e.g. `BRSAPI_KEY`) are read from environment variables only; no secret material is committed to the repository.
- The backend ships security headers (CSP, `X-Content-Type-Options`, `X-Frame-Options`), restrictive CORS defaults, and rate limiting on heavy endpoints.
- The Windows installer is built unsigned by CI from an exact source SHA with provenance (source SHA, size, SHA-256) recorded in the public build log and embedded in the app (`RELEASE_PROVENANCE.json`).
- Demo/mock data mode is always disclosed in the UI trust banner; mock data is never presented as live market data.
