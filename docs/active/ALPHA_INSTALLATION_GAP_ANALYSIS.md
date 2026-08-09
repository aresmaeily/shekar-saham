# ALPHA INSTALLATION GAP ANALYSIS — RADAR BOURSE

| ITEM | CURRENT STATE | REQUIRED STATE | GAP | SEVERITY | ACTION | BLOCKING? | OWNER |
|---|---|---|---|---|---|---|---|
| GitHub sync | Remote behind local by 21 commits | Remote HEAD equals approved local HEAD | Authentication unavailable | P0 | Configure secure auth and normal push | Yes for GitHub acquisition | Owner/Release engineer |
| Windows target | Not accessible from current Linux env | Accessible Windows target | Target unavailable | P0 | Provide target access | Yes for target validation | Owner |
| Installation approval | Not granted | Explicit INSTALL approval | Installation locked | P0 | Owner approval required | Yes for install | Owner |
| BRSAPI key | Missing | Secure BRSAPI_KEY if brsapi live required | Credential missing | P1 | Configure on target if needed | No for mock alpha; yes for BRSAPI live | Owner |
| TSETMC live | mock_fallback observed historically | live_verified=true from target | Not verified | P1 | Validate from target network | No for mock alpha; yes for live claim | Release engineer |
| Target `.env` | Not established | Secure `.env` configured | Missing target config | P1 | Create from `.env.example` and fill secrets | Yes for private alpha | Owner/Installer |
| Python on Windows | Not verified | Python 3.10+ / recommended 3.13 | Target not checked | P1 | Run `validate_install.ps1` | Yes | Target engineer |
| Node/npm on Windows | Not verified | Installed if Electron needed | Target not checked | P2 | Run `node --version`, `npm --version` | Only if Electron required | Target engineer |
| Docker | Not available current env | Optional Docker Desktop if Docker path used | Optional path unverified | P3 | Use native install or validate Docker on target | No if native | Target engineer |
| Browser E2E | Not run | Browser validates UI/auth/API | Target not checked | P2 | Run checklist after backend start | Yes for UI acceptance | QA |
| Electron runtime | Not run | Electron opens backend UI | Target not checked | P2 | `npm install`, `npm start` if required | Optional unless desktop alpha required | Target engineer |
| Firewall/LAN | Not configured | localhost works; LAN if needed | Target not checked | P2 | Validate localhost first; add firewall only if approved | No for local-only alpha | Owner/Target admin |
| DB write permission | Not target verified | `data/` writable | Target not checked | P1 | Validate first startup or safe permission check | Yes | Target engineer |
| Rollback | Documented | Tested if approved | Not target tested | P2 | Follow runbook; no destructive test without approval | No before install | Release engineer |
