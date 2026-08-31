# Pocket Wi-Fi

PocketTerm Wi-Fi scanning, connection management and diagnostics app.

## v0.1

- Shows current Wi-Fi state and SSID.
- Scans nearby networks through NetworkManager / `nmcli`.
- Sorts current connection first, then strongest signals.
- Shows SSID, signal, channel and band.
- Detail screen shows BSSID, frequency and security.
- Connects to saved networks.
- Prompts for passwords for new secured networks.
- Supports forgetting saved connections.
- Uses `Q` as the normal Back/Exit key.

The project is intentionally structured as a standalone PocketTerm app so future
versions can add passive wireless intelligence and authorised diagnostic
features independently of the launcher.

## Install on PocketTerm

```bash
cd ~/pocketterm/apps
git clone <YOUR-REPOSITORY-URL> pocket-wifi
cd pocket-wifi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
pocket-wifi
```

## Launcher entry

Add this to the PocketTerm launcher's `apps.toml`:

```toml
[[apps]]
name = "Wi-Fi Toolkit"
description = "Wireless scanning and diagnostics"
command = "/home/bdm198/pocketterm/apps/pocket-wifi/.venv/bin/pocket-wifi"
args = []
enabled = true
```
