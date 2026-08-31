# Waybar setup (Arch + Hyprland)

Reproduces: media/mpris pill + hostname pill on the left, clock + a
drawn "slider" in the center, and volume/battery/bluetooth/wifi on the
right, all as dark capsules floating on a translucent teal bar.

**Note on the slider:** Waybar has no built-in GTK slider widget. The
one in the screenshot is faked with a script that draws a track of `─`
characters and moves a `●` knob to match your real system volume
(scroll on it to actually change volume). If your rice's slider is
draggable, it's an overlay tool like `wl-gammarelay-rs` + `eww`/`ags`
sitting on top of Waybar, not Waybar itself — happy to build that
version instead if you want real dragging.

## 1. Install packages

```bash
sudo pacman -S waybar playerctl pipewire pipewire-pulse pavucontrol \
    networkmanager network-manager-applet bluez bluez-utils blueman \
    ttf-jetbrains-mono-nerd
```

Enable services:

```bash
sudo systemctl enable --now NetworkManager
sudo systemctl enable --now bluetooth
```

## 2. Copy the files

```bash
mkdir -p ~/.config/waybar/scripts
cp config.jsonc ~/.config/waybar/config.jsonc
cp style.css ~/.config/waybar/style.css
cp scripts/volume-slider.sh ~/.config/waybar/scripts/volume-slider.sh
chmod +x ~/.config/waybar/scripts/volume-slider.sh
```

## 3. Launch Waybar with Hyprland

Add to `~/.config/hypr/hyprland.conf`:

```
exec-once = waybar
```

Then reload Hyprland (`hyprctl reload`) or log out/in.

## 4. Sanity-check each module

```bash
waybar -l debug   # run in foreground, watch for module errors
playerctl status  # should print Playing/Paused if a player is open
pactl info        # confirms @DEFAULT_SINK@ resolves
hostname          # should print your machine's hostname (shown as
                   # the second left pill, e.g. "ariadne")
```

## Tweak points

- **Colors**: all in the `@define-color` block at the top of
  `style.css` — swap `bar-bg`, `pill-bg`, `accent-purple`,
  `accent-cyan`, `accent-pink` to taste.
- **Transparency/diagonal line**: that comes from your wallpaper
  showing through the semi-transparent bar background, not from
  Waybar itself — it's just `rgba(23, 148, 130, 0.92)`. Lower the
  alpha to let more wallpaper show through.
- **Icons**: all Nerd Font glyphs. If any render as boxes, your font
  fallback isn't picking up the Nerd Font patch — confirm
  `ttf-jetbrains-mono-nerd` is installed and set as a fallback in
  `fontconfig`, or hardcode `font-family` in `style.css` to a Nerd
  Font you have.
- **Bluetooth "on" text**: matches the screenshot's plain "on" label;
  swap `format-connected` if you want device names instead.
