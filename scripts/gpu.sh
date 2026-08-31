#!/bin/bash
# Detects GPU usage % for NVIDIA (nvidia-smi) or AMD (sysfs gpu_busy_percent).
# Prints "" (nothing) if no supported GPU is found, which hides the module.

if command -v nvidia-smi &>/dev/null; then
    usage=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -n1)
    if [ -n "$usage" ]; then
        echo "󰢮 ${usage}%"
        exit 0
    fi
fi

# AMD fallback
amd_path=$(find /sys/class/drm/card*/device/gpu_busy_percent 2>/dev/null | head -n1)
if [ -n "$amd_path" ] && [ -r "$amd_path" ]; then
    usage=$(cat "$amd_path")
    echo "󰢮 ${usage}%"
    exit 0
fi

exit 1
