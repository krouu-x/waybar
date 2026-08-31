#!/usr/bin/env python3
"""
Custom volume popup for Waybar, styled to match the dark-charcoal pill theme.

Behavior: run this script (e.g. from Waybar's on-click). If no popup is open,
it opens one anchored under the top-right of the screen. If a popup is
already open, running the script again closes it instead of opening a
second one — this is the "click the icon again to close" toggle.

Requires:
    - python-gobject (PyGObject)
    - gtk3
    - gtk-layer-shell (+ its GObject introspection typelib)
    - pactl (pulseaudio-utils / pipewire-pulse)

Install (Arch):   sudo pacman -S gtk-layer-shell python-gobject gtk3
Install (Fedora): sudo dnf install gtk3-layer-shell python3-gobject gtk3
Install (Ubuntu): sudo apt install gir1.2-gtk-layer-shell-0.1 python3-gi gir1.2-gtk-3.0
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

LOCK_FILE = "/tmp/volume-popup.lock"

# ---- Position tuning ----------------------------------------------------
# Distance from the top of the screen (should clear your Waybar height).
MARGIN_TOP = 0
# Distance from the right edge — tweak this so it sits under the volume
# pill specifically. Increase to move left, decrease to move right.
MARGIN_RIGHT = 190
# --------------------------------------------------------------------------


def is_running():
    """Return the PID of an already-running popup, or None."""
    if not os.path.exists(LOCK_FILE):
        return None
    try:
        with open(LOCK_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # raises if the process doesn't exist
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


def get_volume():
    out = subprocess.check_output(
        ["pactl", "get-sink-volume", "@DEFAULT_SINK@"]
    ).decode()
    m = re.search(r"(\d+)%", out)
    return int(m.group(1)) if m else 0


def set_volume(val):
    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(val)}%"])


def is_muted():
    out = subprocess.check_output(["pactl", "get-sink-mute", "@DEFAULT_SINK@"]).decode()
    return "yes" in out


def toggle_mute():
    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])


CSS = b"""
window.volume-popup {
    background-color: rgba(24, 25, 30, 0.95);
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}
box.volume-box {
    padding: 12px 16px;
}
label.volume-icon {
    color: #5ec4b6;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 20px;
}
label.volume-icon.muted {
    color: #4b4f5a;
}
label.volume-pct {
    color: #abb2bf;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 13px;
    min-width: 36px;
}
scale trough {
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    min-height: 6px;
}
scale trough highlight {
    background-color: #5ec4b6;
    border-radius: 6px;
}
scale slider {
    background-color: #5ec4b6;
    border-radius: 50%;
    min-width: 14px;
    min-height: 14px;
    border: none;
}
"""


class VolumePopup(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_decorated(False)
        self.set_resizable(False)
        self.get_style_context().add_class("volume-popup")

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, MARGIN_TOP)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, MARGIN_RIGHT)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.get_style_context().add_class("volume-box")

        self.icon_btn = Gtk.Button(label="\U000F057E")  # 󰕾
        self.icon_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.icon_btn.get_style_context().add_class("volume-icon")
        self.icon_btn.connect("clicked", self.on_mute_click)
        box.pack_start(self.icon_btn, False, False, 0)

        adjustment = Gtk.Adjustment(
            value=get_volume(), lower=0, upper=100, step_increment=1, page_increment=5
        )
        self.slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment)
        self.slider.set_draw_value(False)
        self.slider.set_size_request(160, -1)
        self.slider.connect("value-changed", self.on_slider_change)
        box.pack_start(self.slider, True, True, 0)

        self.pct_label = Gtk.Label(label=f"{get_volume()}%")
        self.pct_label.get_style_context().add_class("volume-pct")
        box.pack_start(self.pct_label, False, False, 0)

        self.add(box)
        self.connect("destroy", self.on_destroy)

        # Close if the popup loses focus, like a real OS popup.
        self.connect("focus-out-event", lambda *_: self.destroy())

        GLib.timeout_add(500, self.poll_state)
        self._refresh_icon()

    def on_slider_change(self, widget):
        val = widget.get_value()
        set_volume(val)
        self.pct_label.set_text(f"{int(val)}%")

    def on_mute_click(self, _btn):
        toggle_mute()
        self._refresh_icon()

    def _refresh_icon(self):
        ctx = self.icon_btn.get_style_context()
        if is_muted():
            self.icon_btn.set_label("\U000F0581")  # 󰖁
            ctx.add_class("muted")
        else:
            self.icon_btn.set_label("\U000F057E")  # 󰕾
            ctx.remove_class("muted")

    def poll_state(self):
        vol = get_volume()
        if abs(self.slider.get_value() - vol) > 1:
            self.slider.set_value(vol)
            self.pct_label.set_text(f"{vol}%")
        self._refresh_icon()
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
        # Second click on the icon -> close instead of opening another one.
        close_existing(existing_pid)
        sys.exit(0)

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    load_css()
    win = VolumePopup()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
