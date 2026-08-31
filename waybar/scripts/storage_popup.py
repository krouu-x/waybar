#!/usr/bin/env python3
"""
Custom storage popup for Waybar, styled to match the pill theme.
Same toggle pattern as volume_popup.py: click the storage pill to open,
click it again to close.

Requires:
    - python-gobject, gtk3, gtk-layer-shell (see volume_popup.py for install)
    - lsblk / findmnt (util-linux — installed by default on virtually every distro)

Optional (for drive temperature):
    - nvme-cli   (NVMe drives)   — sudo pacman -S nvme-cli
    - smartmontools (SATA/other) — sudo pacman -S smartmontools

Temperature commands usually need root. Without a permission workaround
the popup will just show "N/A" for temperature rather than failing —
everything else (usage bars, model, mountpoints) works unprivileged.
To enable temperature without typing a password, add a narrowly-scoped
passwordless sudoers rule, e.g.:
    yourname ALL=(root) NOPASSWD: /usr/bin/nvme smart-log /dev/nvme0n1
then change the nvme call below to prefix with "sudo".
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell

import subprocess
import os
import re
import shutil
import sys
import signal

LOCK_FILE = "/tmp/storage-popup.lock"

MARGIN_TOP = 0
# This pill lives on the LEFT side of the bar (user, cpu, memory, gpu,
# storage), so we anchor to the left edge instead of the right.
# Tune this so the popup sits under the storage pill specifically.
MARGIN_LEFT = 230

PSEUDO_FSTYPES = {
    "tmpfs", "devtmpfs", "proc", "sysfs", "cgroup2", "overlay", "squashfs",
    "efivarfs", "pstore", "bpf", "tracefs", "debugfs", "mqueue",
    "hugetlbfs", "fuse.portal", "autofs", "securityfs", "configfs",
    "fusectl", "binfmt_misc",
}


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


def format_bytes(n):
    n = float(n)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def list_mounts():
    mounts = []
    seen = set()
    try:
        with open("/proc/mounts") as f:
            lines = f.readlines()
    except OSError:
        return mounts

    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        device, mountpoint, fstype = parts[0], parts[1], parts[2]
        if not device.startswith("/dev/"):
            continue
        if fstype in PSEUDO_FSTYPES:
            continue
        if device in seen:
            continue
        seen.add(device)
        try:
            usage = shutil.disk_usage(mountpoint)
        except OSError:
            continue
        if usage.total == 0:
            continue
        mounts.append({
            "device": device,
            "mountpoint": mountpoint,
            "total": usage.total,
            "used": usage.used,
            "percent": usage.used / usage.total * 100,
        })

    mounts.sort(key=lambda m: m["mountpoint"])
    return mounts


def get_root_base_device():
    out = run(["findmnt", "-no", "SOURCE", "/"]).strip()
    m = re.match(r"(/dev/nvme\d+n\d+)p?\d*$", out)
    if m:
        return m.group(1)
    m = re.match(r"(/dev/[a-zA-Z]+)\d*$", out)
    if m:
        return m.group(1)
    return out or "/dev/sda"


def get_model(base_device):
    out = run(["lsblk", "-ndo", "MODEL", base_device]).strip()
    return out or "Unknown drive"


def get_temperature(base_device):
    name = os.path.basename(base_device)
    if name.startswith("nvme"):
        out = run(["nvme", "smart-log", base_device])
        m = re.search(r"temperature\s*:\s*(\d+)\s*C", out, re.IGNORECASE)
        if m:
            return f"{m.group(1)}\u00b0C"
    else:
        out = run(["smartctl", "-A", base_device])
        m = re.search(r"Temperature_Celsius.*?(\d+)\s*$", out, re.MULTILINE)
        if m:
            return f"{m.group(1)}\u00b0C"
    return None


CSS = b"""
window.storage-popup {
    background-color: rgba(24, 25, 30, 0.95);
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}
box.storage-box { padding: 12px 16px; }
label.storage-icon {
    color: #c3a6ff;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 20px;
}
label.storage-title {
    color: #abb2bf;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 13px;
}
label.storage-model {
    color: #6b7280;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 11px;
}
label.storage-mount {
    color: #abb2bf;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 12px;
}
label.storage-size {
    color: #6b7280;
    font-family: "JetBrainsMono Nerd Font";
    font-size: 10px;
}
progressbar.storage-bar trough {
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    min-height: 6px;
}
progressbar.storage-bar progress {
    background-color: #c3a6ff;
    border-radius: 6px;
    min-height: 6px;
}
separator.storage-sep {
    background: rgba(255, 255, 255, 0.08);
    min-height: 1px;
}
"""


class StoragePopup(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_decorated(False)
        self.set_resizable(False)
        self.get_style_context().add_class("storage-popup")

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, MARGIN_TOP)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, MARGIN_LEFT)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.get_style_context().add_class("storage-box")
        outer.set_size_request(280, -1)

        base_device = get_root_base_device()
        model = get_model(base_device)
        temp = get_temperature(base_device)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Label(label="\U000F02CA")  # 󰋊
        icon.get_style_context().add_class("storage-icon")
        header.pack_start(icon, False, False, 0)

        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label=os.path.basename(base_device))
        title.set_xalign(0)
        title.get_style_context().add_class("storage-title")
        text_col.pack_start(title, False, False, 0)

        model_sub = f"{model}" + (f" \u00b7 {temp}" if temp else " \u00b7 temp: N/A")
        model_label = Gtk.Label(label=model_sub)
        model_label.set_xalign(0)
        model_label.get_style_context().add_class("storage-model")
        text_col.pack_start(model_label, False, False, 0)

        header.pack_start(text_col, True, True, 0)
        outer.pack_start(header, False, False, 0)

        sep = Gtk.Separator()
        sep.get_style_context().add_class("storage-sep")
        outer.pack_start(sep, False, False, 0)

        self.mount_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.pack_start(self.mount_list, False, False, 0)

        self.add(outer)
        self.connect("destroy", self.on_destroy)
        self.connect("focus-out-event", lambda *_: self.destroy())

        self.refresh_mounts()
        GLib.timeout_add(5000, self.poll_refresh)

    def refresh_mounts(self):
        for child in list(self.mount_list.get_children()):
            child.destroy()

        mounts = list_mounts()
        if not mounts:
            empty = Gtk.Label(label="No mounted drives found")
            empty.get_style_context().add_class("storage-mount")
            self.mount_list.pack_start(empty, False, False, 0)
        else:
            for m in mounts:
                row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

                top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                mp_label = Gtk.Label(label=m["mountpoint"])
                mp_label.set_xalign(0)
                mp_label.get_style_context().add_class("storage-mount")
                top_row.pack_start(mp_label, True, True, 0)

                pct_label = Gtk.Label(label=f"{m['percent']:.0f}%")
                pct_label.get_style_context().add_class("storage-size")
                top_row.pack_start(pct_label, False, False, 0)
                row.pack_start(top_row, False, False, 0)

                bar = Gtk.ProgressBar()
                bar.get_style_context().add_class("storage-bar")
                bar.set_fraction(min(1.0, m["percent"] / 100))
                row.pack_start(bar, False, False, 0)

                size_label = Gtk.Label(
                    label=f"{format_bytes(m['used'])} / {format_bytes(m['total'])} \u00b7 {m['device']}"
                )
                size_label.set_xalign(0)
                size_label.get_style_context().add_class("storage-size")
                row.pack_start(size_label, False, False, 0)

                self.mount_list.pack_start(row, False, False, 0)

        self.mount_list.show_all()
        return False

    def poll_refresh(self):
        self.refresh_mounts()
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
    win = StoragePopup()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
