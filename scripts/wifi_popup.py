#!/usr/bin/env python3

"""
Custom WiFi popup for Waybar, styled to match the pill theme.

Requires:
    - python-gobject
    - gtk3
    - gtk-layer-shell
    - NetworkManager / nmcli

Install (Arch):
    sudo pacman -S gtk-layer-shell python-gobject gtk3 networkmanager

Install (Fedora):
    sudo dnf install gtk3-layer-shell python3-gobject gtk3 NetworkManager

Install (Ubuntu):
    sudo apt install gir1.2-gtk-layer-shell-0.1 python3-gi gir1.2-gtk-3.0 network-manager
"""

import gi
import subprocess
import os
import sys
import signal
import fcntl

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")

from gi.repository import Gtk, Gdk, GLib, GtkLayerShell


LOCK_FILE = "/tmp/wifi-popup.lock"

MARGIN_TOP = 0
MARGIN_RIGHT = 0


# ------------------------------------------------------------
# Command helper
# ------------------------------------------------------------

def run(cmd, timeout=6):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout, result.stderr, result.returncode

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "", "timeout", 1


# ------------------------------------------------------------
# Wi-Fi state
# ------------------------------------------------------------

def get_radio_state():
    out, _, code = run(["nmcli", "radio", "wifi"])

    if code != 0:
        return False

    return out.strip() == "enabled"


def set_radio(on):
    run([
        "nmcli",
        "radio",
        "wifi",
        "on" if on else "off"
    ])


# ------------------------------------------------------------
# Current Wi-Fi connection
# ------------------------------------------------------------

def get_current_ssid():
    out, _, code = run([
        "nmcli",
        "-t",
        "-f",
        "active,ssid",
        "dev",
        "wifi"
    ])

    if code != 0:
        return None

    for line in out.splitlines():
        if line.startswith("yes:"):
            return line.split(":", 1)[1]

    return None


def get_wifi_device():
    """
    Return the device name of the currently connected Wi-Fi interface.
    Example: wlan0 / wlp2s0
    """

    out, _, code = run([
        "nmcli",
        "-t",
        "-f",
        "DEVICE,TYPE,STATE",
        "device",
        "status"
    ])

    if code != 0:
        return None

    for line in out.splitlines():
        parts = line.split(":")

        if len(parts) < 3:
            continue

        device = parts[0]
        dev_type = parts[1]
        state = parts[2]

        if dev_type == "wifi" and state == "connected":
            return device

    return None


def get_current_ip():
    """
    Get the IPv4 address of the currently connected Wi-Fi device.
    """

    wifi_device = get_wifi_device()

    if not wifi_device:
        return None

    out, _, code = run([
        "nmcli",
        "-t",
        "-f",
        "IP4.ADDRESS",
        "device",
        "show",
        wifi_device
    ])

    if code != 0:
        return None

    for line in out.splitlines():

        if line.startswith("IP4.ADDRESS"):
            try:
                address = line.split(":", 1)[1]
                return address.split("/", 1)[0]

            except (IndexError, ValueError):
                return None

    return None


# ------------------------------------------------------------
# Available networks
# ------------------------------------------------------------

def list_networks():

    out, _, code = run([
        "nmcli",
        "-t",
        "-f",
        "SSID,SIGNAL,SECURITY",
        "device",
        "wifi",
        "list"
    ])

    if code != 0:
        return []

    seen = set()
    networks = []

    for line in out.splitlines():

        # nmcli escapes ':' as '\:'
        parts = []
        current = ""
        escaped = False

        for char in line:

            if escaped:
                current += char
                escaped = False

            elif char == "\\":
                escaped = True

            elif char == ":":
                parts.append(current)
                current = ""

            else:
                current += char

        parts.append(current)

        if len(parts) < 3:
            continue

        ssid = parts[0]
        signal_strength = parts[1]
        security = parts[2]

        if not ssid or ssid in seen:
            continue

        seen.add(ssid)

        try:
            sig = int(signal_strength)
        except ValueError:
            sig = 0

        networks.append(
            (
                ssid,
                sig,
                bool(security)
            )
        )

    networks.sort(
        key=lambda network: network[1],
        reverse=True
    )

    return networks


# ------------------------------------------------------------
# Connect
# ------------------------------------------------------------

def connect(ssid, password=None):

    cmd = [
        "nmcli",
        "device",
        "wifi",
        "connect",
        ssid
    ]

    if password:
        cmd += [
            "password",
            password
        ]

    return run(cmd, timeout=15)


# ------------------------------------------------------------
# CSS
# ------------------------------------------------------------

CSS = b"""
window.wifi-popup {
    background-color: rgba(24, 25, 30, 0.95);
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}

box.wifi-box {
    padding: 12px 14px;
}

label.wifi-icon {
    color: #e06c75;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 18px;
}

label.wifi-title {
    color: #abb2bf;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 13px;
}

label.wifi-current {
    color: #e06c75;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 11px;
}

label.wifi-ssid {
    color: #abb2bf;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 12px;
}

button.wifi-connect {
    background: rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    border: none;
    color: #abb2bf;
    padding: 2px 10px;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 11px;
}

button.wifi-connect:hover {
    background: rgba(255, 255, 255, 0.12);
}

button.wifi-connect.connected {
    background: #e06c75;
    color: #18191e;
}

entry.wifi-pw {
    background: rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    border: none;
    color: #abb2bf;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 11px;
}
"""


# ------------------------------------------------------------
# Popup window
# ------------------------------------------------------------

class WifiPopup(Gtk.Window):

    def __init__(self):

        super().__init__(
            type=Gtk.WindowType.TOPLEVEL
        )

        self.set_decorated(False)
        self.set_resizable(False)

        self.get_style_context().add_class(
            "wifi-popup"
        )

        # Layer shell
        GtkLayerShell.init_for_window(self)

        GtkLayerShell.set_layer(
            self,
            GtkLayerShell.Layer.OVERLAY
        )

        GtkLayerShell.set_anchor(
            self,
            GtkLayerShell.Edge.TOP,
            True
        )

        GtkLayerShell.set_anchor(
            self,
            GtkLayerShell.Edge.RIGHT,
            True
        )

        GtkLayerShell.set_margin(
            self,
            GtkLayerShell.Edge.TOP,
            MARGIN_TOP
        )

        GtkLayerShell.set_margin(
            self,
            GtkLayerShell.Edge.RIGHT,
            MARGIN_RIGHT
        )

        GtkLayerShell.set_keyboard_mode(
            self,
            GtkLayerShell.KeyboardMode.ON_DEMAND
        )

        # ----------------------------------------------------
        # Main container
        # ----------------------------------------------------

        outer = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8
        )

        outer.get_style_context().add_class(
            "wifi-box"
        )

        outer.set_size_request(
            260,
            -1
        )

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8
        )

        icon = Gtk.Label(
            label="\U000F0928"
        )

        icon.get_style_context().add_class(
            "wifi-icon"
        )

        header.pack_start(
            icon,
            False,
            False,
            0
        )

        title = Gtk.Label(
            label="Wi-Fi"
        )

        title.get_style_context().add_class(
            "wifi-title"
        )

        header.pack_start(
            title,
            True,
            True,
            0
        )

        self.radio_switch = Gtk.Switch()

        self.radio_switch.set_active(
            get_radio_state()
        )

        self.radio_switch.connect(
            "state-set",
            self.on_radio_toggle
        )

        header.pack_end(
            self.radio_switch,
            False,
            False,
            0
        )

        outer.pack_start(
            header,
            False,
            False,
            0
        )

        # ----------------------------------------------------
        # Current connection
        # ----------------------------------------------------

        current = get_current_ssid()
        ip = get_current_ip()

        connection_text = self.get_connection_text(
            current,
            ip
        )

        self.current_label = Gtk.Label(
            label=connection_text
        )

        self.current_label.set_xalign(0)

        self.current_label.get_style_context().add_class(
            "wifi-current"
        )

        outer.pack_start(
            self.current_label,
            False,
            False,
            0
        )

        outer.pack_start(
            Gtk.Separator(),
            False,
            False,
            0
        )

        # ----------------------------------------------------
        # Network list
        # ----------------------------------------------------

        scroller = Gtk.ScrolledWindow()

        scroller.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC
        )

        scroller.set_max_content_height(
            240
        )

        scroller.set_propagate_natural_height(
            True
        )

        self.network_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6
        )

        scroller.add(
            self.network_list
        )

        outer.pack_start(
            scroller,
            False,
            False,
            0
        )

        self.add(outer)

        # ----------------------------------------------------
        # Events
        # ----------------------------------------------------

        self.connect(
            "destroy",
            self.on_destroy
        )

        self.connect(
            "focus-out-event",
            self.on_focus_out
        )

        # ----------------------------------------------------
        # Initial refresh
        # ----------------------------------------------------

        self.refresh_networks()

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def get_connection_text(self, current, ip):

        if current:

            text = f"Connected: {current}"

            if ip:
                text += f"  •  {ip}"

            return text

        return "Not connected"

    # --------------------------------------------------------
    # Radio toggle
    # --------------------------------------------------------

    def on_radio_toggle(self, _switch, state):

        set_radio(state)

        GLib.timeout_add(
            800,
            self.refresh_networks
        )

        return False

    # --------------------------------------------------------
    # Refresh
    # --------------------------------------------------------

    def refresh_networks(self):

        # Remove old rows
        for child in list(
            self.network_list.get_children()
        ):
            child.destroy()

        current = get_current_ssid()
        ip = get_current_ip()

        self.current_label.set_text(
            self.get_connection_text(
                current,
                ip
            )
        )

        # Wi-Fi disabled
        if not get_radio_state():

            label = Gtk.Label(
                label="Wi-Fi disabled"
            )

            label.set_xalign(0)

            label.get_style_context().add_class(
                "wifi-ssid"
            )

            self.network_list.pack_start(
                label,
                False,
                False,
                0
            )

            self.network_list.show_all()

            return False

        # Network list
        for ssid, sig, secured in list_networks():

            row_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=4
            )

            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=8
            )

            lock = "🔒 " if secured else ""

            label_text = (
                f"{lock}{ssid} ({sig}%)"
            )

            name_label = Gtk.Label(
                label=label_text
            )

            name_label.set_xalign(0)

            name_label.get_style_context().add_class(
                "wifi-ssid"
            )

            row.pack_start(
                name_label,
                True,
                True,
                0
            )

            is_current = (
                ssid == current
            )

            button_text = (
                "connected"
                if is_current
                else "connect"
            )

            btn = Gtk.Button(
                label=button_text
            )

            btn.get_style_context().add_class(
                "wifi-connect"
            )

            if is_current:

                btn.get_style_context().add_class(
                    "connected"
                )

            btn.connect(
                "clicked",
                self.on_connect_click,
                ssid,
                secured,
                row_box
            )

            row.pack_start(
                btn,
                False,
                False,
                0
            )

            row_box.pack_start(
                row,
                False,
                False,
                0
            )

            self.network_list.pack_start(
                row_box,
                False,
                False,
                0
            )

        self.network_list.show_all()

        return False

    # --------------------------------------------------------
    # Connect button
    # --------------------------------------------------------

    def on_connect_click(
        self,
        _btn,
        ssid,
        secured,
        row_box
    ):

        # Try without password first
        _out, _err, code = connect(ssid)

        if code != 0 and secured:

            existing = [
                child
                for child in row_box.get_children()
                if (
                    isinstance(child, Gtk.Box)
                    and child.get_name() == "pw-row"
                )
            ]

            if existing:
                return

            # Password row
            pw_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=6
            )

            pw_row.set_name(
                "pw-row"
            )

            entry = Gtk.Entry()

            entry.set_visibility(False)

            entry.get_style_context().add_class(
                "wifi-pw"
            )

            entry.set_placeholder_text(
                "password"
            )

            pw_row.pack_start(
                entry,
                True,
                True,
                0
            )

            confirm = Gtk.Button(
                label="ok"
            )

            confirm.get_style_context().add_class(
                "wifi-connect"
            )

            confirm.connect(
                "clicked",
                self.on_password_confirm,
                ssid,
                entry
            )

            pw_row.pack_start(
                confirm,
                False,
                False,
                0
            )

            entry.connect(
                "activate",
                self.on_password_confirm,
                ssid,
                entry
            )

            row_box.pack_start(
                pw_row,
                False,
                False,
                0
            )

            row_box.show_all()

            entry.grab_focus()

        else:

            GLib.timeout_add(
                800,
                self.refresh_networks
            )

    # --------------------------------------------------------
    # Password confirm
    # --------------------------------------------------------

    def on_password_confirm(
        self,
        _widget,
        ssid,
        entry
    ):

        password = entry.get_text()

        if not password:
            return

        connect(
            ssid,
            password=password
        )

        GLib.timeout_add(
            1000,
            self.refresh_networks
        )

    # --------------------------------------------------------
    # Focus
    # --------------------------------------------------------

    def on_focus_out(self, *_args):

        GLib.idle_add(
            self.destroy
        )

        return False

    # --------------------------------------------------------
    # Destroy
    # --------------------------------------------------------

    def on_destroy(self, *_args):

        Gtk.main_quit()


# ------------------------------------------------------------
# CSS loader
# ------------------------------------------------------------

def load_css():

    provider = Gtk.CssProvider()

    provider.load_from_data(
        CSS
    )

    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    # --------------------------------------------------------
    # Reliable single-instance lock
    # --------------------------------------------------------

    lock_fd = open(
        LOCK_FILE,
        "w"
    )

    try:

        fcntl.flock(
            lock_fd,
            fcntl.LOCK_EX | fcntl.LOCK_NB
        )

    except BlockingIOError:

        # Popup already exists.
        # Kill it to preserve toggle behavior.
        lock_fd.close()

        try:
            with open(LOCK_FILE) as f:
                pid = int(
                    f.read().strip()
                )

            os.kill(
                pid,
                signal.SIGTERM
            )

        except (
            ValueError,
            FileNotFoundError,
            ProcessLookupError,
            PermissionError
        ):
            pass

        sys.exit(0)

    # Write our PID for the toggle mechanism
    lock_fd.seek(0)
    lock_fd.truncate()
    lock_fd.write(
        str(os.getpid())
    )
    lock_fd.flush()

    # --------------------------------------------------------
    # GTK
    # --------------------------------------------------------

    load_css()

    win = WifiPopup()

    win.show_all()

    Gtk.main()

    # flock is released automatically when closed
    lock_fd.close()


if __name__ == "__main__":
    main()