#!/bin/bash
# Exit 1 (silently) if there's no active player -> Waybar hides the whole pill
playerctl status &>/dev/null || exit 1

status=$(playerctl status 2>/dev/null)
[ "$status" = "Stopped" ] && exit 1

artist=$(playerctl metadata artist 2>/dev/null)
title=$(playerctl metadata title 2>/dev/null)

# guard against a player that exists but has no metadata yet
[ -z "$title" ] && exit 1

echo "♪ ${artist} — ${title}"
