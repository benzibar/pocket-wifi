from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from pocket_wifi.models import WifiNetwork
from pocket_wifi.network_manager import (
    NetworkManager,
    NetworkManagerError,
)


class PasswordScreen(ModalScreen[str | None]):
    CSS = """
    PasswordScreen {
        align: center middle;
    }

    #password-box {
        width: 90%;
        height: auto;
        border: round cyan;
        padding: 1 2;
    }

    #password-title {
        text-style: bold;
        color: cyan;
    }

    #password-buttons {
        height: auto;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("q", "cancel", "Back"),
    ]

    def __init__(self, ssid: str) -> None:
        super().__init__()
        self.ssid = ssid

    def compose(self) -> ComposeResult:
        with Vertical(id="password-box"):
            yield Static(
                f"CONNECT: {self.ssid}",
                id="password-title",
            )
            yield Input(
                placeholder="Wi-Fi password",
                password=True,
                id="password",
            )

            with Horizontal(id="password-buttons"):
                yield Button(
                    "Connect",
                    id="connect",
                    variant="primary",
                )
                yield Button(
                    "Cancel",
                    id="cancel",
                )

    def on_mount(self) -> None:
        self.query_one("#password", Input).focus()

    def on_input_submitted(
        self,
        event: Input.Submitted,
    ) -> None:
        self.dismiss(event.value)

    def on_button_pressed(
        self,
        event: Button.Pressed,
    ) -> None:
        if event.button.id == "connect":
            self.dismiss(
                self.query_one("#password", Input).value
            )
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SignalMonitorScreen(Screen):
    BINDINGS = [("q", "app.pop_screen", "Back"), ("escape", "app.pop_screen", "Back")]

    CSS = """
    #monitor-root { padding: 1 2; }
    #monitor-title { color: cyan; text-style: bold; }
    #monitor-signal { height: 3; margin-top: 1; }
    #monitor-bar { height: 1; }
    """

    def __init__(self, manager: NetworkManager, network: WifiNetwork) -> None:
        super().__init__()
        self.manager = manager
        self.network = network

    def compose(self) -> ComposeResult:
        with Vertical(id="monitor-root"):
            yield Static(f"SIGNAL: {self.network.ssid}", id="monitor-title")
            yield Static("", id="monitor-signal")
            yield Static("", id="monitor-bar")
            yield Static("\nUpdates every 2 seconds\nQ Back")

    def on_mount(self) -> None:
        self.update_signal()
        self.set_interval(2.0, self.update_signal)

    def update_signal(self) -> None:
        try:
            current = self.manager.network_by_bssid(self.network.bssid)
        except NetworkManagerError as exc:
            self.query_one("#monitor-signal", Static).update(f"Scan failed: {exc}")
            return
        if current is None:
            self.query_one("#monitor-signal", Static).update("Access point not currently visible")
            self.query_one("#monitor-bar", Static).update("")
            return
        self.network = current
        blocks = max(0, min(20, round(current.signal / 5)))
        bar = "#" * blocks + "." * (20 - blocks)
        self.query_one("#monitor-signal", Static).update(
            f"Signal: {current.signal}%\nCH {current.channel or '---'}  {current.band}  {current.frequency_mhz or '---'} MHz"
        )
        self.query_one("#monitor-bar", Static).update(f"[{bar}]")


class NetworkDetailScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("escape", "app.pop_screen", "Back"),
        ("m", "monitor", "Monitor"),
    ]

    CSS = """
    #detail-root {
        padding: 1 2;
    }

    #detail-title {
        color: cyan;
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def __init__(self, network: WifiNetwork, manager: NetworkManager) -> None:
        super().__init__()
        self.network = network
        self.manager = manager

    def compose(self) -> ComposeResult:
        network = self.network

        with Vertical(id="detail-root"):
            yield Static(
                network.ssid,
                id="detail-title",
            )

            yield Static(
                f"BSSID:    {network.bssid}\n"
                f"Signal:   {network.signal}%\n"
                f"Channel:  {network.channel or '---'}\n"
                f"Band:     {network.band}\n"
                f"Freq:     "
                f"{network.frequency_mhz or '---'} MHz\n"
                f"Security: {network.security}\n"
                f"Current:  "
                f"{'Yes' if network.in_use else 'No'}\n\n"
                "M Signal Monitor  Q Back"
            )

    def action_monitor(self) -> None:
        self.app.push_screen(SignalMonitorScreen(self.manager, self.network))


class WifiScanScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("escape", "app.pop_screen", "Back"),
        ("r", "refresh_scan", "Refresh"),
        ("enter", "connect_selected", "Connect"),
        ("i", "details", "Info"),
        ("f", "forget_selected", "Forget"),
        ("m", "monitor_selected", "Monitor"),
    ]

    CSS = """
    #scan-root {
        padding: 0 1;
        height: 1fr;
    }

    #scan-title {
        color: cyan;
        text-style: bold;
        height: 1;
    }

    #scan-current {
        height: 1;
    }

    #network-list {
        height: 1fr;
        border: round $surface;
    }

    #scan-status {
        height: 2;
    }
    """

    def __init__(self, manager: NetworkManager) -> None:
        super().__init__()
        self.manager = manager
        self.networks: list[WifiNetwork] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="scan-root"):
            yield Static(
                "WI-FI NETWORKS",
                id="scan-title",
            )
            yield Static(
                "",
                id="scan-current",
            )
            yield ListView(
                id="network-list"
            )
            yield Static(
                "",
                id="scan-status",
            )

        yield Footer()

    def on_mount(self) -> None:
        self.refresh_networks()

    def action_refresh_scan(self) -> None:
        self.refresh_networks(
            rescan=True
        )

    def refresh_networks(
        self,
        rescan: bool = False,
    ) -> None:
        status = self.query_one(
            "#scan-status",
            Static,
        )

        if rescan:
            status.update(
                "Scanning..."
            )

        try:
            self.networks = (
                self.manager.scan(
                    rescan=rescan
                )
            )
        except NetworkManagerError as exc:
            status.update(
                f"Scan failed: {exc}"
            )
            return

        active = (
            self.manager.active_ssid()
        )

        self.query_one(
            "#scan-current",
            Static,
        ).update(
            f"Current: "
            f"{active or 'Not connected'}"
        )

        network_list = self.query_one(
            "#network-list",
            ListView,
        )

        network_list.clear()

        for network in self.networks:
            connected = (
                " *"
                if network.in_use
                else ""
            )

            label = (
                f"{network.ssid[:22]:<22} "
                f"{network.signal:>3}% "
                f"CH{network.channel or 0:<3} "
                f"{network.band:<4}"
                f"{connected}"
            )

            network_list.append(
                ListItem(
                    Label(label)
                )
            )

        if self.networks:
            status.update(
                "Enter Join  I Info  "
                "M Sig  F Forget  R Scan  Q Back"
            )
        else:
            status.update(
                "No networks found."
            )

    def _selected_network(
        self,
    ) -> WifiNetwork | None:
        network_list = self.query_one(
            "#network-list",
            ListView,
        )

        index = network_list.index

        if (
            index is None
            or index < 0
            or index >= len(self.networks)
        ):
            return None

        return self.networks[index]

    def action_details(self) -> None:
        network = (
            self._selected_network()
        )

        if network is not None:
            self.app.push_screen(
                NetworkDetailScreen(
                    network,
                    self.manager,
                )
            )

    def action_connect_selected(
        self,
    ) -> None:
        network = (
            self._selected_network()
        )

        if network is None:
            return

        if network.in_use:
            self.query_one(
                "#scan-status",
                Static,
            ).update(
                f"Already connected to "
                f"{network.ssid}."
            )
            return

        # Try saved credentials first.
        try:
            self.manager.connect(
                network.ssid
            )

            self.query_one(
                "#scan-status",
                Static,
            ).update(
                f"Connected to "
                f"{network.ssid}."
            )

            self.refresh_networks()
            return

        except NetworkManagerError:
            pass

        if (
            network.security.strip().lower()
            in {"", "open", "--"}
        ):
            self._connect_open(network.ssid)
            return

        self.app.push_screen(
            PasswordScreen(
                network.ssid
            ),
            lambda password: (
                self._connect_with_password(
                    network.ssid,
                    password,
                )
            ),
        )

    def _connect_open(self, ssid: str) -> None:
        status = self.query_one("#scan-status", Static)
        status.update(f"Connecting to {ssid}...")
        try:
            self.manager.connect(ssid)
        except NetworkManagerError as exc:
            status.update(f"Connection failed: {exc}")
            return
        status.update(f"Connected to {ssid}.")
        self.refresh_networks()

    def action_monitor_selected(self) -> None:
        network = self._selected_network()
        if network is not None:
            self.app.push_screen(SignalMonitorScreen(self.manager, network))

    def _connect_with_password(
        self,
        ssid: str,
        password: str | None,
    ) -> None:
        if password is None:
            return

        status = self.query_one(
            "#scan-status",
            Static,
        )

        status.update(
            f"Connecting to {ssid}..."
        )

        try:
            self.manager.connect(
                ssid,
                password=password,
            )
        except NetworkManagerError as exc:
            status.update(
                f"Connection failed: {exc}"
            )
            return

        status.update(
            f"Connected to {ssid}."
        )

        self.refresh_networks()

    def action_forget_selected(
        self,
    ) -> None:
        network = (
            self._selected_network()
        )

        if network is None:
            return

        status = self.query_one(
            "#scan-status",
            Static,
        )

        try:
            self.manager.forget(
                network.ssid
            )
        except NetworkManagerError as exc:
            status.update(
                f"Forget failed: {exc}"
            )
            return

        status.update(
            f"Forgot {network.ssid}."
        )

        self.refresh_networks()


class AboutScreen(Screen):
    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(
            "POCKET WI-FI\n\n"
            "v0.2.1\n\n"
            "Wireless scanning, connection management "
            "and diagnostics for PocketTerm.\n\n"
            "Future versions can add passive wireless "
            "intelligence and authorised diagnostic "
            "features without changing the core launcher.\n\n"
            "Q Back"
        )


class PocketWifi(App):
    TITLE = "Pocket Wi-Fi"

    CSS = """
    Screen {
        layout: vertical;
    }

    #home-root {
        padding: 1 2;
        height: 1fr;
    }

    #home-title {
        color: cyan;
        text-style: bold;
        content-align: center middle;
        margin-bottom: 1;
    }

    #home-status {
        height: 7;
        margin-bottom: 1;
    }

    #home-menu {
        height: 1fr;
        border: round $surface;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    MENU = [
        "Networks",
        "About",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.manager = (
            NetworkManager()
        )

    def compose(self) -> ComposeResult:
        with Vertical(
            id="home-root"
        ):
            yield Static(
                "POCKET WI-FI",
                id="home-title",
            )

            yield Static(
                "",
                id="home-status",
            )

            yield ListView(
                *[
                    ListItem(
                        Label(item)
                    )
                    for item in self.MENU
                ],
                id="home-menu",
            )

        yield Footer()

    def on_mount(self) -> None:
        self._update_status()

    def _update_status(self) -> None:
        state = self.manager.device_status()
        info = self.manager.connection_info()

        signal = (
            f"{info.signal}%"
            if info.signal is not None
            else "---"
        )

        self.query_one(
            "#home-status",
            Static,
        ).update(
            f"Wi-Fi:   {state}\n"
            f"SSID:    {info.ssid or '---'}\n"
            f"IP:      {info.ip_address}\n"
            f"Router:  {info.gateway}\n"
            f"DNS:     {info.dns_text}\n"
            f"Signal:  {signal}\n"
            f"Iface:   {info.interface}"
        )

    def on_list_view_selected(
        self,
        event: ListView.Selected,
    ) -> None:
        index = event.list_view.index

        if index == 0:
            self.push_screen(
                WifiScanScreen(
                    self.manager
                )
            )
        elif index == 1:
            self.push_screen(
                AboutScreen()
            )


def main() -> None:
    PocketWifi().run()


if __name__ == "__main__":
    main()
