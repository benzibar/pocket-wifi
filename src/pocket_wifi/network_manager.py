from __future__ import annotations

import subprocess

from pocket_wifi.models import ConnectionInfo, WifiNetwork


class NetworkManagerError(RuntimeError):
    pass


class NetworkManager:
    def __init__(self, interface: str = "wlan0") -> None:
        self.interface = interface

    def scan(self, rescan: bool = False) -> list[WifiNetwork]:
        rows = self.scan_access_points(rescan=rescan)
        strongest: dict[str, WifiNetwork] = {}
        for network in rows:
            current = strongest.get(network.ssid)
            if current is None or network.signal > current.signal or network.in_use:
                strongest[network.ssid] = network
        return sorted(
            strongest.values(),
            key=lambda item: (not item.in_use, -item.signal, item.ssid.lower()),
        )

    def scan_access_points(self, rescan: bool = False) -> list[WifiNetwork]:
        if rescan:
            subprocess.run(
                ["nmcli", "device", "wifi", "rescan", "ifname", self.interface],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        result = self._run([
            "nmcli", "-t", "-f",
            "IN-USE,SSID,BSSID,SIGNAL,CHAN,FREQ,SECURITY",
            "device", "wifi", "list", "ifname", self.interface,
        ])
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
            rows.append(WifiNetwork(
                ssid=ssid,
                bssid=bssid,
                signal=signal,
                channel=channel,
                frequency_mhz=frequency,
                security=security or "Open",
                in_use=in_use == "*",
            ))
        return rows

    def network_by_bssid(self, bssid: str) -> WifiNetwork | None:
        for network in self.scan_access_points():
            if network.bssid.lower() == bssid.lower():
                return network
        return None

    def active_ssid(self) -> str:
        result = self._run([
            "nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi", "list",
            "ifname", self.interface,
        ], raise_on_error=False)
        if result.returncode != 0:
            return ""
        for line in result.stdout.splitlines():
            parts = self._split_terse(line)
            if len(parts) >= 2 and parts[0] == "yes":
                return parts[1]
        return ""

    def connection_info(self) -> ConnectionInfo:
        ssid = self.active_ssid()

        result = self._run([
            "nmcli", "-t", "-f",
            "IP4.ADDRESS,IP4.GATEWAY,IP4.DNS",
            "device", "show", self.interface,
        ], raise_on_error=False)

        ip_address = "---"
        gateway = "---"
        dns_servers: list[str] = []

        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue

                parts = self._split_terse(line)
                if len(parts) < 2:
                    continue

                key = parts[0]
                value = ":".join(parts[1:]).strip()

                if key.startswith("IP4.ADDRESS") and value:
                    ip_address = value.split("/", 1)[0]
                elif key == "IP4.GATEWAY" and value:
                    gateway = value
                elif key.startswith("IP4.DNS") and value:
                    dns_servers.append(value)

        signal: int | None = None

        try:
            for network in self.scan_access_points():
                if network.in_use:
                    signal = network.signal
                    if not ssid:
                        ssid = network.ssid
                    break
        except NetworkManagerError:
            pass

        return ConnectionInfo(
            interface=self.interface,
            ssid=ssid,
            ip_address=ip_address,
            gateway=gateway,
            dns_servers=tuple(dns_servers),
            signal=signal,
        )

    def saved_connection_name(self, ssid: str) -> str | None:
        result = self._run([
            "nmcli", "-t", "-f", "NAME,TYPE,802-11-wireless.ssid", "connection", "show"
        ], raise_on_error=False)
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            parts = self._split_terse(line)
            if len(parts) >= 3 and parts[1] in {"802-11-wireless", "wifi"} and parts[2] == ssid:
                return parts[0]
        return None

    def connect(self, ssid: str, password: str | None = None) -> None:
        saved_name = self.saved_connection_name(ssid)
        if saved_name:
            saved = self._run(["nmcli", "connection", "up", "id", saved_name], raise_on_error=False)
            if saved.returncode == 0:
                return
            if password is None:
                message = (saved.stderr or saved.stdout).strip()
                raise NetworkManagerError(message or f"Could not activate saved connection: {saved_name}")
        command = [
            "nmcli", "device", "wifi", "connect", ssid,
            "ifname", self.interface,
        ]
        if password:
            command += ["password", password]
        self._run(command)

    def forget(self, ssid: str) -> None:
        saved_name = self.saved_connection_name(ssid)
        if not saved_name:
            raise NetworkManagerError(f"No saved connection for {ssid}")
        self._run(["nmcli", "connection", "delete", "id", saved_name])

    def device_status(self) -> str:
        result = self._run([
            "nmcli", "-t", "-f", "GENERAL.STATE", "device", "show", self.interface
        ], raise_on_error=False)
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
            elif char == "\\":
                escaped = True
            elif char == ":":
                parts.append("".join(current))
                current = []
            else:
                current.append(char)
        parts.append("".join(current))
        return parts

    @staticmethod
    def _run(command: list[str], raise_on_error: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if raise_on_error and result.returncode != 0:
            message = (result.stderr or result.stdout).strip()
            raise NetworkManagerError(message or f"Command failed: {' '.join(command)}")
        return result
