from dataclasses import dataclass


@dataclass(frozen=True)
class WifiNetwork:
    ssid: str
    bssid: str
    signal: int
    channel: int | None
    frequency_mhz: int | None
    security: str
    in_use: bool = False

    @property
    def band(self) -> str:
        if self.frequency_mhz is None:
            return "---"

        if 2400 <= self.frequency_mhz < 2500:
            return "2.4G"

        if 4900 <= self.frequency_mhz < 5900:
            return "5G"

        if 5925 <= self.frequency_mhz < 7125:
            return "6G"

        return "---"
