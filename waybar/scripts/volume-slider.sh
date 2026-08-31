#!/usr/bin/env bash
# ~/.config/waybar/scripts/volume-slider.sh
#
# Waybar has no native GTK slider widget, so this fakes one by drawing
# a track of dashes with a circle "knob" placed according to the real
# system volume (from pactl). Output is Pango markup consumed by a
# custom module with "return-type": "json".

WIDTH=12   # number of track characters

get_volume() {
    pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null \
        | grep -oP '\d+(?=%)' | head -n1
}

get_mute() {
    pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null | grep -q "yes" && echo 1 || echo 0
}

vol=$(get_volume)
[ -z "$vol" ] && vol=0
muted=$(get_mute)

pos=$(( vol * (WIDTH - 1) / 100 ))
[ "$pos" -lt 0 ] && pos=0
[ "$pos" -gt $((WIDTH - 1)) ] && pos=$((WIDTH - 1))

track=""
for i in $(seq 0 $((WIDTH - 1))); do
    if [ "$i" -eq "$pos" ]; then
        track="${track}●"
    else
        track="${track}─"
    fi
done

if [ "$muted" = "1" ]; then
    text=" ${track}"
    tooltip="Muted"
else
    text=" ${track}"
    tooltip="Volume: ${vol}%"
fi

printf '{"text": "%s", "tooltip": "%s", "class": "%s"}\n' \
    "$text" "$tooltip" "$([ "$muted" = "1" ] && echo muted || echo normal)"
