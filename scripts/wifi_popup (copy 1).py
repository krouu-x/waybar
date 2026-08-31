#!/usr/bin/env python3
"""
Custom WiFi popup for Waybar, styled to match the pill theme.
Same toggle pattern as volume_popup.py.

Requires:
    - python-gobject, gtk3, gtk-layer-shell (see volume_popup.py for install)
    - NetworkManager (provides `nmcli`)

Install (Arch):   sudo pacman -S gtk-layer-shell python-gobject gtk3 networkmanager
Install (Fedora): sudo dnf install gtk3-layer-shell python3-gobject gtk3 NetworkManager
Install (Ubuntu): sudo apt install gir1.2-gtk-layer-shell-0.1 python3-gi gir1.2-gtk-3.0 network-manager
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

import subprocess
import os
import sys
import signal

LOCK_FILE = "/tmp/wifi-popup.lock"

MARGIN_TOP = 0
# Tune this so the popup sits under the wifi pill specifically (rightmost pill).
MARGIN_RIGHT = 0


def is_running():
    if not os.path.exists(LOCK_FILE):
        return None
    try:
        with open(LOCK_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, FileNotFoundError):
        return None


def close_existing(pid):
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except FileNotFoundError:
            pass


def run(cmd, timeout=6):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout, result.stderr, result.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "", "timeout", 1


def get_radio_state():
    out, _, _ = run(["nmcli", "radio", "wifi"])
    return out.strip() == "enabled"


def set_radio(on):
    run(["nmcli", "radio", "wifi", "on" if on else "off"])


def get_current_ssid():
    out, _, _ = run(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
    for line in out.splitlines():
        if line.startswith("yes:"):
            return line.split(":", 1)[1]
    return None


def list_networks():
    out, _, _ = run(["nmcli", "-t", "-f", "ssid,signal,security", "dev", "wifi", "list"])
    seen = set()
    networks = []
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 3:
            continue
        ssid, signal_strength, security = parts[0], parts[1], parts[2]
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        try:
            sig = int(signal_strength)
        except ValueError:
            sig = 0
        networks.append((ssid, sig, bool(security)))
    networks.sort(key=lambda n: n[1], reverse=True)
    return networks


def connect(ssid, password=None):
    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]
    return run(cmd, timeout=15)


CSS = b"""
window.wifi-popup {
    background-color: rgba(24, 25, 30, 0.95);
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}
box.wifi-box { padding: 12px 14px; }
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


class WifiPopup(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_decorated(False)
        self.set_resizable(False)
        self.get_style_context().add_class("wifi-popup")

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, MARGIN_TOP)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, MARGIN_RIGHT)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.get_style_context().add_class("wifi-box")
        outer.set_size_request(260, -1)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Label(label="\U000F0928")  # 󰤨
        icon.get_style_context().add_class("wifi-icon")
        header.pack_start(icon, False, False, 0)

        title = Gtk.Label(label="Wi-Fi")
        title.get_style_context().add_class("wifi-title")
        header.pack_start(title, True, True, 0)

        self.radio_switch = Gtk.Switch()
        self.radio_switch.set_active(get_radio_state())
        self.radio_switch.connect("state-set", self.on_radio_toggle)
        header.pack_end(self.radio_switch, False, False, 0)

        outer.pack_start(header, False, False, 0)

        current = get_current_ssid()
        self.current_label = Gtk.Label(label=f"Connected: {current}" if current else "Not connected")
        self.current_label.set_xalign(0)
        self.current_label.get_style_context().add_class("wifi-current")
        outer.pack_start(self.current_label, False, False, 0)

        outer.pack_start(Gtk.Separator(), False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_max_content_height(240)
        scroller.set_propagate_natural_height(True)

        self.network_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scroller.add(self.network_list)
        outer.pack_start(scroller, False, False, 0)

        self.add(outer)
        self.connect("destroy", self.on_destroy)
        self.connect("focus-out-event", lambda *_: self.destroy())

        self.refresh_networks()

    def on_radio_toggle(self, _switch, state):
        set_radio(state)
        GLib.timeout_add(800, self.refresh_networks)
        return False

    def refresh_networks(self):
        for child in list(self.network_list.get_children()):
            child.destroy()

        current = get_current_ssid()
        self.current_label.set_text(f"Connected: {current}" if current else "Not connected")

        for ssid, sig, secured in list_networks():
            row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            label_text = f"{ssid} {'🔒' if secured else ''} ({sig}%)"
            name_label = Gtk.Label(label=label_text)
            name_label.set_xalign(0)
            name_label.get_style_context().add_class("wifi-ssid")
            row.pack_start(name_label, True, True, 0)

            is_current = ssid == current
            btn = Gtk.Button(label="connected" if is_current else "connect")
            btn.get_style_context().add_class("wifi-connect")
            if is_current:
                btn.get_style_context().add_class("connected")
            btn.connect("clicked", self.on_connect_click, ssid, secured, row_box)
            row.pack_start(btn, False, False, 0)

            row_box.pack_start(row, False, False, 0)
            self.network_list.pack_start(row_box, False, False, 0)

        self.network_list.show_all()
        return False

    def on_connect_click(self, _btn, ssid, secured, row_box):
        _out, err, code = connect(ssid)
        if code != 0 and secured:
            # Needs a password — reveal an inline entry for this row.
            existing = [c for c in row_box.get_children() if isinstance(c, Gtk.Box) and c.get_name() == "pw-row"]
            if existing:
                return
            pw_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            pw_row.set_name("pw-row")
            entry = Gtk.Entry()
            entry.set_visibility(False)
            entry.get_style_context().add_class("wifi-pw")
            entry.set_placeholder_text("password")
            pw_row.pack_start(entry, True, True, 0)

            confirm = Gtk.Button(label="ok")
            confirm.get_style_context().add_class("wifi-connect")
            confirm.connect("clicked", self.on_password_confirm, ssid, entry)
            pw_row.pack_start(confirm, False, False, 0)
            entry.connect("activate", self.on_password_confirm, ssid, entry)

            row_box.pack_start(pw_row, False, False, 0)
            row_box.show_all()
        else:
            self.refresh_networks()

    def on_password_confirm(self, _widget, ssid, entry):
        password = entry.get_text()
        connect(ssid, password=password)
        self.refresh_networks()

    def on_destroy(self, *_args):
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except FileNotFoundError:
                pass
        Gtk.main_quit()


def load_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


def main():
    existing_pid = is_running()
    if existing_pid:
        close_existing(existing_pid)
        sys.exit(0)

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    load_css()
    win = WifiPopup()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
