from __future__ import annotations

import subprocess

from pocket_wifi.models import WifiNetwork


class NetworkManagerError(RuntimeError):
    pass


class NetworkManager:
    def __init__(self, interface: str = "wlan0") -> None:
        self.interface = interface

    def scan(self, rescan: bool = False) -> list[WifiNetwork]:
        if rescan:
            subprocess.run(
                ["nmcli", "device", "wifi", "rescan", "ifname", self.interface],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

        result = self._run(
            [
                "nmcli",
                "-t",
                "-f",
                "IN-USE,SSID,BSSID,SIGNAL,CHAN,FREQ,SECURITY",
                "device",
                "wifi",
                "list",
                "ifname",
                self.interface,
            ]
        )

        rows: list[WifiNetwork] = []

        for line in result.stdout.splitlines():
            if not line.strip():
                continue

            parts = self._split_terse(line)

            if len(parts) != 7:
                continue

            in_use, ssid, bssid, signal_text, chan_text, freq_text, security = parts

            if not ssid:
                continue

            try:
                signal = int(signal_text)
            except ValueError:
                signal = 0

            try:
                channel = int(chan_text)
            except ValueError:
                channel = None

            try:
                frequency = int(freq_text)
            except ValueError:
                frequency = None

            rows.append(
                WifiNetwork(
                    ssid=ssid,
                    bssid=bssid,
                    signal=signal,
                    channel=channel,
                    frequency_mhz=frequency,
                    security=security or "Open",
                    in_use=in_use == "*",
                )
            )

        # Keep the strongest AP for each SSID for the connect screen.
        strongest: dict[str, WifiNetwork] = {}

        for network in rows:
            current = strongest.get(network.ssid)

            if (
                current is None
                or network.signal > current.signal
                or network.in_use
            ):
                strongest[network.ssid] = network

        return sorted(
            strongest.values(),
            key=lambda item: (
                not item.in_use,
                -item.signal,
                item.ssid.lower(),
            ),
        )

    def active_ssid(self) -> str:
        result = self._run(
            [
                "nmcli",
                "-t",
                "-f",
                "ACTIVE,SSID",
                "device",
                "wifi",
                "list",
                "ifname",
                self.interface,
            ],
            raise_on_error=False,
        )

        if result.returncode != 0:
            return ""

        for line in result.stdout.splitlines():
            parts = self._split_terse(line)

            if len(parts) >= 2 and parts[0] == "yes":
                return parts[1]

        return ""

    def connect(
        self,
        ssid: str,
        password: str | None = None,
    ) -> None:
        # Prefer an existing saved connection first.
        saved = self._run(
            ["nmcli", "connection", "up", "id", ssid],
            raise_on_error=False,
        )

        if saved.returncode == 0:
            return

        command = [
            "nmcli",
            "device",
            "wifi",
            "connect",
            ssid,
            "ifname",
            self.interface,
        ]

        if password:
            command += ["password", password]

        self._run(command)

    def forget(self, ssid: str) -> None:
        self._run(
            ["nmcli", "connection", "delete", "id", ssid]
        )

    def device_status(self) -> str:
        result = self._run(
            [
                "nmcli",
                "-t",
                "-f",
                "GENERAL.STATE",
                "device",
                "show",
                self.interface,
            ],
            raise_on_error=False,
        )

        if result.returncode != 0:
            return "Unavailable"

        text = result.stdout.strip()

        if ":" in text:
            text = text.split(":", 1)[1]

        return text or "Unknown"

    @staticmethod
    def _split_terse(line: str) -> list[str]:
        parts: list[str] = []
        current: list[str] = []
        escaped = False

        for char in line:
            if escaped:
                current.append(char)
                escaped = False
                continue

            if char == "\\":
                escaped = True
                continue

            if char == ":":
                parts.append("".join(current))
                current = []
                continue

            current.append(char)

        parts.append("".join(current))
        return parts

    @staticmethod
    def _run(
        command: list[str],
        raise_on_error: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        if raise_on_error and result.returncode != 0:
            message = (result.stderr or result.stdout).strip()

            raise NetworkManagerError(
                message or f"Command failed: {' '.join(command)}"
            )

        return result
