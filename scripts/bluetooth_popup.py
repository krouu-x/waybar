#!/usr/bin/env python3
"""
Custom Bluetooth popup for Waybar, styled to match the pill theme.
Same toggle pattern as volume_popup.py: run it once to open, run it again
(e.g. by clicking the bluetooth pill again) to close it.

Requires:
    - python-gobject, gtk3, gtk-layer-shell (see volume_popup.py for install)
    - bluez-utils (provides `bluetoothctl`)

Install (Arch):   sudo pacman -S gtk-layer-shell python-gobject gtk3 bluez-utils
Install (Fedora): sudo dnf install gtk3-layer-shell python3-gobject gtk3 bluez
Install (Ubuntu): sudo apt install gir1.2-gtk-layer-shell-0.1 python3-gi gir1.2-gtk-3.0 bluez
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

import subprocess
import os
import re
import sys
import signal

LOCK_FILE = "/tmp/bluetooth-popup.lock"

MARGIN_TOP = 0
# Tune this so the popup sits under the bluetooth pill specifically.
MARGIN_RIGHT = 20


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


def run(cmd, timeout=4):
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        ).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_power_state():
    out = run(["bluetoothctl", "show"])
    return "Powered: yes" in out


def set_power(on):
    run(["bluetoothctl", "power", "on" if on else "off"])


def list_paired_devices():
    out = run(["bluetoothctl", "devices", "Paired"])
    devices = []
    for line in out.splitlines():
        m = re.match(r"Device\s+([0-9A-Fa-f:]+)\s+(.*)", line.strip())
        if m:
            devices.append((m.group(1), m.group(2)))
    return devices


def is_connected(mac):
    out = run(["bluetoothctl", "info", mac])
    return "Connected: yes" in out


def toggle_connection(mac):
    if is_connected(mac):
        run(["bluetoothctl", "disconnect", mac], timeout=6)
    else:
        run(["bluetoothctl", "connect", mac], timeout=6)


CSS = b"""
window.bt-popup {
    background-color: rgba(24, 25, 30, 0.95);
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}
box.bt-box { padding: 12px 14px; }
label.bt-icon {
    color: #e5c07b;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 18px;
}
label.bt-title {
    color: #abb2bf;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 13px;
}
label.bt-device {
    color: #abb2bf;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 12px;
}
button.bt-connect {
    background: rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    border: none;
    color: #abb2bf;
    padding: 2px 10px;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 11px;
}
button.bt-connect.connected {
    background: #e5c07b;
    color: #18191e;
}
switch.bt-switch {
    border-radius: 999px;
}
separator.bt-sep {
    background: rgba(255, 255, 255, 0.08);
    min-height: 1px;
}
"""


class BluetoothPopup(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_decorated(False)
        self.set_resizable(False)
        self.get_style_context().add_class("bt-popup")

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, MARGIN_TOP)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, MARGIN_RIGHT)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.get_style_context().add_class("bt-box")
        outer.set_size_request(240, -1)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Label(label="\U000F00AF")  # 󰂯
        icon.get_style_context().add_class("bt-icon")
        header.pack_start(icon, False, False, 0)

        title = Gtk.Label(label="Bluetooth")
        title.get_style_context().add_class("bt-title")
        header.pack_start(title, True, True, 0)

        self.power_switch = Gtk.Switch()
        self.power_switch.get_style_context().add_class("bt-switch")
        self.power_switch.set_active(get_power_state())
        self.power_switch.connect("state-set", self.on_power_toggle)
        header.pack_end(self.power_switch, False, False, 0)

        outer.pack_start(header, False, False, 0)
        outer.pack_start(Gtk.Separator(), False, False, 0)

        self.device_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.pack_start(self.device_list, False, False, 0)

        self.add(outer)
        self.connect("destroy", self.on_destroy)
        self.connect("focus-out-event", lambda *_: self.destroy())

        self.refresh_devices()
        GLib.timeout_add(2000, self.poll_refresh)

    def on_power_toggle(self, _switch, state):
        set_power(state)
        GLib.timeout_add(500, self.refresh_devices)
        return False

    def refresh_devices(self):
        for child in list(self.device_list.get_children()):
            child.destroy()

        devices = list_paired_devices()
        if not devices:
            empty = Gtk.Label(label="No paired devices")
            empty.get_style_context().add_class("bt-device")
            self.device_list.pack_start(empty, False, False, 0)
        else:
            for mac, name in devices:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                name_label = Gtk.Label(label=name)
                name_label.set_xalign(0)
                name_label.get_style_context().add_class("bt-device")
                row.pack_start(name_label, True, True, 0)

                connected = is_connected(mac)
                btn = Gtk.Button(label="connected" if connected else "connect")
                btn.get_style_context().add_class("bt-connect")
                if connected:
                    btn.get_style_context().add_class("connected")
                btn.connect("clicked", self.on_connect_click, mac)
                row.pack_start(btn, False, False, 0)

                self.device_list.pack_start(row, False, False, 0)

        self.device_list.show_all()
        return False

    def on_connect_click(self, _btn, mac):
        toggle_connection(mac)
        GLib.timeout_add(300, self.refresh_devices)

    def poll_refresh(self):
        self.power_switch.set_state(get_power_state())
        self.refresh_devices()
        return True

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
    win = BluetoothPopup()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
