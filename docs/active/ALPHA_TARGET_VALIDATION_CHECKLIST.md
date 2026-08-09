# ALPHA TARGET VALIDATION CHECKLIST — RADAR BOURSE

This checklist is for the Windows target machine. It was prepared repository-side only; target-specific statuses remain NOT VERIFIED until executed on Windows.

| Area | Item | Required? | Validation Command / Method | Status | Notes |
|---|---|---:|---|---|---|
| OS | Windows version | REQUIRED | `Get-CimInstance Win32_OperatingSystem` | NOT VERIFIED | Target required |
| OS | Architecture x64 | REQUIRED | `$env:PROCESSOR_ARCHITECTURE` | NOT VERIFIED | x64 recommended |
| PowerShell | PowerShell available | REQUIRED | `$PSVersionTable` | NOT VERIFIED | Needed for scripts |
| Python | Python installed | REQUIRED | `python --version` | NOT VERIFIED | 3.10+ minimum; 3.13 used locally |
| Python | pip available | REQUIRED | `python -m pip --version` | NOT VERIFIED | Required for dependencies |
| Git | Git installed | REQUIRED | `git --version` | NOT VERIFIED | Needed for clone/sync path |
| Node | Node installed | OPTIONAL | `node --version` | NOT VERIFIED | Required for Electron only |
| npm | npm installed | OPTIONAL | `npm --version` | NOT VERIFIED | Required for Electron only |
| Browser | Modern browser available | REQUIRED | Manual launch | NOT VERIFIED | UI validation |
| Disk | >= 5GB free | REQUIRED | `Get-PSDrive` | NOT VERIFIED | Recommended minimum |
| Memory | >= 4GB recommended | RECOMMENDED | `Get-CimInstance Win32_OperatingSystem` | NOT VERIFIED | Lower may still run |
| Network | localhost available | REQUIRED | `Invoke-WebRequest http://127.0.0.1:<port>` after start | NOT VERIFIED | Backend local access |
| Network | outbound HTTPS to TSETMC | OPTIONAL for live | provider validation | NOT VERIFIED | Required for live TSETMC |
| Network | outbound HTTPS to BRSAPI | OPTIONAL for live | provider validation | BLOCKED | Requires BRSAPI_KEY |
| Port | Port 8000 free | REQUIRED unless changed | `Get-NetTCPConnection -LocalPort 8000` | NOT VERIFIED | Change PORT if occupied |
| Firewall | localhost access | REQUIRED | Browser/curl/Invoke-WebRequest | NOT VERIFIED | No firewall changes now |
| Firewall | LAN access | OPTIONAL | Windows Firewall rule if needed | NOT VERIFIED | Only if remote LAN access desired |
| Permissions | Write project dir | REQUIRED | create test file or app startup | NOT VERIFIED | Do not write during audit unless approved |
| Permissions | Write data dir | REQUIRED | app startup or safe dir check | NOT VERIFIED | DB requires write |
| Long paths | Long path compatibility | RECOMMENDED | `git config --system core.longpaths true` if needed | NOT VERIFIED | Do not change without approval |
| Database | SQLite initialization | REQUIRED | backend first start | NOT VERIFIED | No manual migration command |
| Backend | Import/startup | REQUIRED | `scripts/windows/start.ps1` | NOT VERIFIED | Target only |
| Frontend | Static files served | REQUIRED | Browser `/` | NOT VERIFIED | Target only |
| Electron | Runtime validation | OPTIONAL | `npm start` | NOT VERIFIED | Optional alpha path |
| WebSocket | `/ws/live` available | REQUIRED for live panel | Browser/API validation | NOT VERIFIED | Auth may be required |
| Security | Private mode configured | REQUIRED for private alpha | `.env` status only | NOT VERIFIED | Do not print secrets |
| Security | Auth works | REQUIRED if private | login flow | NOT VERIFIED | Target only |
| Data Provider | DATA_SOURCE=mock | OPTIONAL fallback | provider validator | NOT VERIFIED | Non-live |
| Data Provider | DATA_SOURCE=tsetmc | OPTIONAL live attempt | provider validator | NOT VERIFIED | Must not claim live unless trust live |
| Data Provider | DATA_SOURCE=brsapi | OPTIONAL live attempt | provider validator | BLOCKED | BRSAPI_KEY missing currently |
