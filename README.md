# Pocket Wi-Fi

PocketTerm Wi-Fi scanning, connection management and diagnostics.

## v0.2.2

- Home screen now shows current SSID, device IP address, router/default gateway, DNS, signal and interface
- Compact nearby-network list for the PocketTerm display
- Network detail view with BSSID, signal, channel, band, frequency and security
- Reconnects saved NetworkManager profiles by their real connection name
- Connects to new secured and open networks
- Forget saved networks
- Live per-access-point signal monitor (`M`), updating every 2 seconds
- Keyboard-first navigation with `Q`/Esc back

## Run

```bash
source .venv/bin/activate
pocket-wifi
```


## v0.2.2

- Added dedicated Network status screen with IP, router/default gateway, DNS, signal, channel, band, security and interface.
- Added green field labels throughout the main status display and Network screen.
