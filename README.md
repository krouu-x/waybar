# Waybar • Hyprland Setup

> A clean, dark and translucent Waybar setup for **Arch Linux + Hyprland**, designed to look good without requiring you to know how to program.

![Waybar Preview](https://github.com/krouu-x/waybar/blob/main/src/waybar.png)

## ✨ What is this?

This repository contains my personal **Waybar configuration** for Hyprland.

If you're new to Linux customization, think of **Waybar as the bar at the top or bottom of your desktop** that shows useful information such as:

* 🕐 Current time
* 🔊 Volume
* 🔋 Battery
* 📶 Wi-Fi
* 🟦 Bluetooth
* 🎵 Currently playing media
* 💻 Computer hostname
* 🎚️ A visual volume slider

The goal of this setup is simple:

**Install it → start Waybar → enjoy a polished desktop.**

You don't need to write any code to use it.

---

## 🎨 What does it look like?

The setup uses a dark, minimal design with translucent teal elements and rounded "pill" sections.

The Layout with wallpaper looks like this
![Waybar With wallpaper Preview](https://raw.githubusercontent.com/krouu-x/waybar/main/src/Waybar%20with%20whole%20desktop.png)

The exact appearance depends on your wallpaper, screen size and installed fonts.

---

# 📦 Installation

## Requirements

This configuration is intended for:

* **Arch Linux**
* **Hyprland**
* **Waybar**

It also uses a few additional programs for the various modules.

### Install everything

Open a terminal and run:

```bash
sudo pacman -S waybar playerctl pipewire pipewire-pulse pavucontrol \
networkmanager network-manager-applet bluez bluez-utils blueman \
ttf-jetbrains-mono-nerd nvme-cli smartmontools upower \
power-profiles-daemon
git clone --depth 1 https://github.com/krouu-x/waybar /tmp/krouu-waybar &&
cp -r /tmp/krouu-waybar/waybar ~/.config/ &&
rm -rf /tmp/krouu-waybar
```
paste this whole command in your terminal and viola your waybar is set-up!

### What are these packages?

If you're unfamiliar with Linux packages, here's the useful version:

| Package                   | Purpose                               |
| ------------------------- | ------------------------------------- |
| `waybar`                  | Displays the bar                      |
| `playerctl`               | Controls music/media players          |
| `pipewire`                | Handles audio                         |
| `pipewire-pulse`          | PulseAudio compatibility for PipeWire |
| `pavucontrol`             | Graphical audio control               |
| `networkmanager`          | Manages Wi-Fi and networking          |
| `network-manager-applet`  | Network tray/menu                     |
| `bluez`                   | Bluetooth support                     |
| `bluez-utils`             | Bluetooth command-line utilities      |
| `blueman`                 | Bluetooth graphical manager           |
| `ttf-jetbrains-mono-nerd` | Nerd Font icons                       |
| `nvme-cli`                | NVMe drive information                |
| `smartmontools`           | Drive health information              |
| `upower`                  | Battery/power information             |
| `power-profiles-daemon`   | Power profile support                 |

You don't need to understand what all of these do. They simply provide the information and functionality used by the Waybar modules.

---

# ⚙️ Enable networking and Bluetooth

Run:

```bash
sudo systemctl enable --now NetworkManager
sudo systemctl enable --now bluetooth
```

This enables the services now and automatically starts them when you boot.

---

# 📁 Install the configuration

Clone this repository:

```bash
git clone https://github.com/krouu-x/waybar.git
cd waybar
```

Create your Waybar configuration directory:

```bash
mkdir -p ~/.config/waybar/scripts
```

Copy the configuration files:

```bash
cp waybar/config.jsonc ~/.config/waybar/config.jsonc
cp waybar/style.css ~/.config/waybar/style.css
cp waybar/scripts/volume-slider.sh ~/.config/waybar/scripts/volume-slider.sh
```

Make the volume script executable:

```bash
chmod +x ~/.config/waybar/scripts/volume-slider.sh
```

Your configuration should now look like:

```text
~/.config/waybar/
├── config.jsonc
├── style.css
└── scripts/
    └── volume-slider.sh
```

---

# 🚀 Start Waybar

Before making it start automatically, test it manually.

Run:

```bash
waybar
```

If everything works, the bar should appear.

To stop it, press:

```text
Ctrl + C
```

---

# 🏠 Start Waybar automatically with Hyprland

If you use Hyprland, open:

```text
~/.config/hypr/hyprland.lua
```

Add in this function which will look like this:

```ini
hl.on("hyprland.start", function ()
    ....
   hl.exec_cmd("waybar")
end)

```

Then reload Hyprland:

```bash
hyprctl reload
```

Waybar should now start automatically whenever you log into Hyprland.

---

# 🎛️ Customizing the appearance

You don't need to modify the complicated parts of the configuration.

Most visual customization can be done from:

```text
~/.config/waybar/style.css
```

## 🎨 Change the colors

At the top of `style.css` you'll find the color definitions.

Look for:

```css
@define-color bar-bg ...;
@define-color pill-bg ...;
@define-color accent-purple ...;
@define-color accent-cyan ...;
@define-color accent-pink ...;
```

These control the main colors of the setup.

For example, changing the accent colors lets you create your own theme without touching the Waybar configuration.

---

## 🌫️ Change transparency

The bar uses transparency so your wallpaper can show through it.

You may see something similar to:

```css
rgba(23, 148, 130, 0.92)
```

The last number controls transparency.

Generally:

```text
0.1  → very transparent
0.5  → semi-transparent
0.9  → mostly opaque
1.0  → completely opaque
```

Try changing the value and restarting Waybar.

---

# 🔤 Icons look like boxes?

If you see strange squares instead of icons, you probably don't have a suitable Nerd Font installed.

Install the recommended font:

```bash
sudo pacman -S ttf-jetbrains-mono-nerd
```

Then restart Waybar.

The configuration uses **Nerd Font glyphs** for many of its icons.

---

# 🎵 Media controls

The media section uses `playerctl`.

It can display information from compatible media players and allows Waybar to interact with your currently playing media.

If media information isn't appearing, check:

```bash
playerctl status
```

If a supported player is currently running, you should get something such as:

```text
Playing
```

or:

```text
Paused
```

---

# 🔊 Volume slider

The volume slider is implemented using:

```text
scripts/volume-slider.sh
```

This is **not a native draggable GTK slider**.

Instead, the script creates a visual representation of the volume level and updates the knob based on your current system volume.

You can interact with it according to the actions configured in `config.jsonc`.

The audio system is handled through PipeWire/PulseAudio compatibility.

To check that your audio system is responding:

```bash
pactl info
```

---

# 🧪 Troubleshooting

If Waybar doesn't work, don't immediately delete your entire Linux installation. That is generally considered an excessive debugging technique.

Run Waybar in debug mode:

```bash
waybar -l debug
```

This prints useful information about what Waybar is doing.

### Check the individual components

#### Media

```bash
playerctl status
```

#### Audio

```bash
pactl info
```

#### Hostname

```bash
hostname
```

#### Network

```bash
systemctl status NetworkManager
```

#### Bluetooth

```bash
systemctl status bluetooth
```

---

# 🛠️ Common problems

### Waybar doesn't start

Try:

```bash
waybar -l debug
```

Look at the last few lines for an error.

Also make sure Waybar is actually installed:

```bash
waybar --version
```

---

### Icons are missing

Install the Nerd Font:

```bash
sudo pacman -S ttf-jetbrains-mono-nerd
```

Then restart Waybar.

---

### Wi-Fi isn't showing

Check NetworkManager:

```bash
systemctl status NetworkManager
```

If it isn't running:

```bash
sudo systemctl enable --now NetworkManager
```

---

### Bluetooth isn't showing

Check:

```bash
systemctl status bluetooth
```

Then:

```bash
sudo systemctl enable --now bluetooth
```

---

### Volume controls aren't working

Check PipeWire:

```bash
pactl info
```

If PipeWire isn't installed:

```bash
sudo pacman -S pipewire pipewire-pulse
```

---

# 📂 Repository structure

```text
waybar/
├── waybar/
│   ├── config.jsonc
│   ├── style.css
│   ├── scripts/
│   │   └── volume-slider.sh
│   ├── backup/
│   └── files.zip
│
└── README.md
```

### `config.jsonc`

Controls **what Waybar displays and how the modules behave**.

### `style.css`

Controls **how everything looks**: colors, spacing, borders, transparency, fonts, etc.

### `scripts/volume-slider.sh`

Handles the custom volume-slider display and interaction.

### `backup/`

Contains backup material for the configuration.

### `files.zip`

A packaged copy of the configuration files.

---

# 🧑‍💻 For people who want to customize it

You can start without knowing programming.

The two files you'll care about most are:

```text
config.jsonc
style.css
```

Think of them like this:

```text
config.jsonc  →  What is displayed?
style.css     →  What does it look like?
```

For example:

```text
Want different colors?
        ↓
Edit style.css

Want to remove Bluetooth?
        ↓
Edit config.jsonc

Want a different font?
        ↓
Edit style.css

Want to change the order of modules?
        ↓
Edit config.jsonc
```

Make one change at a time and restart Waybar to see the result.

---

# 🔄 Restart Waybar

After changing your configuration, the easiest way to restart it is:

```bash
pkill waybar
waybar &
```

Or, if Waybar is started by Hyprland, you can simply reload/restart it through your normal Hyprland workflow.

---

# 💡 Before changing anything

Make a backup of your working configuration:

```bash
cp ~/.config/waybar/config.jsonc ~/.config/waybar/config.jsonc.backup
cp ~/.config/waybar/style.css ~/.config/waybar/style.css.backup
```

If you break something, you can restore it.

Because configuration files have a remarkable ability to become mysteriously broken after changing one completely innocent-looking character.

---

# 🤝 Contributing

Found a bug, have an improvement, or made a nice variation?

Feel free to:

1. Fork the repository
2. Make your changes
3. Test the configuration
4. Open a pull request

Screenshots are especially useful when submitting visual changes.

---

# ⭐ Credits

This setup is built around **Waybar**, the highly customizable status bar for Wayland compositors. Waybar itself supports many compositors and modules beyond this configuration.

* [Waybar](https://github.com/Alexays/Waybar)
* [Hyprland](https://hyprland.org/)
* [Nerd Fonts](https://www.nerdfonts.com/)
* [Playerctl](https://github.com/altdesktop/playerctl)

---

# 📄 License

This repository contains configuration files intended to be freely used and modified.

If you redistribute or significantly modify this configuration, keeping attribution to the original repository is appreciated.

---

<div align="center">

**Made for Wayland • Built for Hyprland • Customized for humans**

⭐ If this setup helped you, consider starring the repository.

</div>
:::

This version deliberately explains **what each command does**, includes a beginner-friendly package table, troubleshooting, customization guidance, and a clear file structure. It also avoids pretending the custom volume control is a native Waybar slider, which is an important distinction in your existing README.

One thing I'd change before committing it: **replace the placeholder preview image with an actual screenshot of your Waybar**. That will make the GitHub page substantially more convincing.
