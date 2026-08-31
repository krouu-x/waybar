#!/bin/bash
# Prints icon + percentage used of the root filesystem for the Waybar pill.
pct=$(df --output=pcent / | tail -n1 | tr -d '% ')
echo "󰋊 ${pct}%"
