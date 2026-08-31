#!/usr/bin/env python3
"""
Custom battery / power popup for Waybar, styled to match the pill theme.
Same toggle pattern as volume_popup.py.

Requires:
    - python-gobject, gtk3, gtk-layer-shell (see volume_popup.py for install)
    - upower (battery status)
    - power-profiles-daemon (optional — enables the profile switcher buttons;
      the popup still works fine without it, it just hides those buttons)

Install (Arch):   sudo pacman -S gtk-layer-shell python-gobject gtk3 upower power-profiles-daemon
Install (Fedora): sudo dnf install gtk3-layer-shell python3-gobject gtk3 upower power-profiles-daemon
Install (Ubuntu): sudo apt install gir1.2-gtk-layer-shell-0.1 python3-gi gir1.2-gtk-3.0 upower power-profiles-daemon
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

LOCK_FILE = "/tmp/battery-popup.lock"

MARGIN_TOP = 0
# Tune this so the popup sits under the battery pill specifically.
MARGIN_RIGHT = 100


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
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_battery_path():
    out = run(["upower", "-e"])
    for line in out.splitlines():
        if "battery" in line.lower():
            return line.strip()
    return None


def get_battery_info():
    path = get_battery_path()
    if not path:
        return {"percentage": None, "state": "unknown", "time": None}

    out = run(["upower", "-i", path])
    info = {"percentage": None, "state": "unknown", "time": None}

    m = re.search(r"percentage:\s+(\d+)%", out)
    if m:
        info["percentage"] = int(m.group(1))

    m = re.search(r"state:\s+(\S+)", out)
    if m:
        info["state"] = m.group(1)

    m = re.search(r"time to (?:empty|full):\s+(.+)", out)
    if m:
        info["time"] = m.group(1).strip()

    return info


def has_power_profiles():
    out = run(["powerprofilesctl", "list"])
    return bool(out.strip())


def get_active_profile():
    out = run(["powerprofilesctl", "get"])
    return out.strip()


def set_profile(name):
    run(["powerprofilesctl", "set", name])


BATTERY_ICONS = ["\U000F007A", "\U000F007C", "\U000F007E", "\U000F0080", "\U000F0082", "\U000F0079"]


def icon_for(percentage, charging):
    if charging:
        return "\U000F0084"  # 󰂄
    if percentage is None:
        return BATTERY_ICONS[-1]
    idx = min(len(BATTERY_ICONS) - 1, percentage // 20)
    return BATTERY_ICONS[idx]


CSS = b"""
window.battery-popup {
    background-color: rgba(24, 25, 30, 0.95);
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}
box.battery-box { padding: 12px 16px; }
label.battery-icon {
    color: #7bc29a;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 22px;
}
label.battery-pct {
    color: #abb2bf;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 16px;
}
label.battery-sub {
    color: #6b7280;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 11px;
}
button.profile-btn {
    background: rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    border: none;
    color: #abb2bf;
    padding: 4px 8px;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 11px;
}
button.profile-btn.active {
    background: #7bc29a;
    color: #18191e;
}
separator.battery-sep {
    background: rgba(255, 255, 255, 0.08);
    min-height: 1px;
}
"""


class BatteryPopup(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_decorated(False)
        self.set_resizable(False)
        self.get_style_context().add_class("battery-popup")

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, MARGIN_TOP)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, MARGIN_RIGHT)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.get_style_context().add_class("battery-box")
        outer.set_size_request(240, -1)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.icon_label = Gtk.Label()
        self.icon_label.get_style_context().add_class("battery-icon")
        header.pack_start(self.icon_label, False, False, 0)

        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.pct_label = Gtk.Label()
        self.pct_label.set_xalign(0)
        self.pct_label.get_style_context().add_class("battery-pct")
        text_col.pack_start(self.pct_label, False, False, 0)

        self.sub_label = Gtk.Label()
        self.sub_label.set_xalign(0)
        self.sub_label.get_style_context().add_class("battery-sub")
        text_col.pack_start(self.sub_label, False, False, 0)

        header.pack_start(text_col, True, True, 0)
        outer.pack_start(header, False, False, 0)

        self.profiles_row = None
        if has_power_profiles():
            outer.pack_start(Gtk.Separator(), False, False, 0)
            self.profiles_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            for name, label in [
                ("power-saver", "saver"),
                ("balanced", "balanced"),
                ("performance", "perf"),
            ]:
                btn = Gtk.Button(label=label)
                btn.get_style_context().add_class("profile-btn")
                btn.connect("clicked", self.on_profile_click, name)
                self.profiles_row.pack_start(btn, True, True, 0)
            outer.pack_start(self.profiles_row, False, False, 0)

        self.add(outer)
        self.connect("destroy", self.on_destroy)
        self.connect("focus-out-event", lambda *_: self.destroy())

        self.refresh()
        GLib.timeout_add(3000, self.poll_refresh)

    def refresh(self):
        info = get_battery_info()
        pct = info["percentage"]
        state = info["state"]
        charging = state in ("charging", "fully-charged")

        self.icon_label.set_text(icon_for(pct, charging))
        self.pct_label.set_text(f"{pct}%" if pct is not None else "N/A")

        sub_parts = [state.replace("-", " ")]
        if info["time"]:
            sub_parts.append(info["time"])
        self.sub_label.set_text(" · ".join(sub_parts))

        if self.profiles_row:
            active = get_active_profile()
            for btn in self.profiles_row.get_children():
                label = btn.get_label()
                name = {"saver": "power-saver", "balanced": "balanced", "perf": "performance"}[label]
                ctx = btn.get_style_context()
                if name == active:
                    ctx.add_class("active")
                else:
                    ctx.remove_class("active")

        return False

    def on_profile_click(self, _btn, name):
        set_profile(name)
        GLib.timeout_add(300, self.refresh)

    def poll_refresh(self):
        self.refresh()
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
    win = BatteryPopup()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
