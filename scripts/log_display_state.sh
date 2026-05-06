#!/bin/bash
# Capture the Pi's display/framebuffer/console state to a log file.
#
# Designed to run twice per boot:
#   1. From the matchcaller-display-log.service systemd unit, right after
#      console-setup.service finishes (early boot, before getty/auto-login).
#   2. From ~/.bashrc, just before start_matchcaller.sh launches the TUI.
#
# Each invocation appends one timestamped block to the log so we can compare
# state across boots and across the boot/TUI-launch boundary, which is what
# we need to debug the intermittent "TV comes up at the wrong resolution"
# issue (Textual then adds useless scrollbars on a Pi with no input devices).
#
# Usage:
#   log_display_state.sh <stage-label>
# where <stage-label> is e.g. "boot-systemd" or "tty1-bashrc-pre".
#
# Caller does not need to think about sudo — we elevate per-command via
# `sudo -n` and skip cleanly if elevation isn't available.

set +e  # never abort the boot or the TUI launch — just log what we can

STAGE="${1:-unspecified}"
LOG_DIR="${MATCHCALLER_LOG_DIR:-$HOME/matchcaller/logs}"
# When run as root via systemd, $HOME is /root — but the persistent log dir
# lives under abbey's home. Resolve to that path explicitly when we're root.
if [ "$(id -u)" -eq 0 ] && [ ! -d "$LOG_DIR" ] && [ -d /home/abbey/matchcaller/logs ]; then
    LOG_DIR=/home/abbey/matchcaller/logs
fi
LOG_FILE="${LOG_DIR}/display_state.log"

mkdir -p "$LOG_DIR" 2>/dev/null

# Run a command, elevating with `sudo -n` only if we're not already root and
# sudo is available passwordlessly. Caller-friendly: never prompts.
run_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        sudo -n "$@"
    else
        return 126
    fi
}

# --- helpers ---------------------------------------------------------------

dump() {
    local header="$1"
    shift
    printf '\n--- %s ---\n' "$header"
    "$@" 2>&1 || printf '(command failed: %s)\n' "$*"
}

dump_file() {
    local header="$1"
    local path="$2"
    printf '\n--- %s ---\n' "$header"
    if [ ! -e "$path" ]; then
        printf '(missing: %s)\n' "$path"
    elif [ ! -s "$path" ] && [ ! -d "$path" ]; then
        printf '(empty: %s)\n' "$path"
    else
        cat "$path" 2>&1 || printf '(read failed: %s)\n' "$path"
    fi
}

# --- snapshot --------------------------------------------------------------

{
    printf '\n========================================================================\n'
    printf 'STAGE:     %s\n' "$STAGE"
    printf 'WHEN:      %s\n' "$(date -Is 2>/dev/null || date)"
    printf 'UPTIME:    %s\n' "$(awk '{printf "%.1fs since boot", $1}' /proc/uptime 2>/dev/null)"
    printf 'BOOT_ID:   %s\n' "$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)"
    printf 'KERNEL:    %s\n' "$(uname -r)"
    printf 'HOSTNAME:  %s\n' "$(hostname)"
    printf 'CALLER:    uid=%s pid=%s tty=%s\n' "$(id -u)" "$$" "$(tty 2>&1)"
    printf 'TERM:      %s\n' "${TERM:-unset}"
    printf 'COLS/LINES env: %s/%s\n' "${COLUMNS:-unset}" "${LINES:-unset}"

    dump_file 'kernel cmdline'      /proc/cmdline

    dump 'fbset (current mode)'     fbset -i

    dump_file 'fb0/virtual_size'    /sys/class/graphics/fb0/virtual_size
    dump_file 'fb0/mode'            /sys/class/graphics/fb0/mode
    dump_file 'fb0/bits_per_pixel'  /sys/class/graphics/fb0/bits_per_pixel
    dump_file 'fb0/stride'          /sys/class/graphics/fb0/stride

    # DRM connector state — what the kernel sees from the TV via EDID.
    for f in /sys/class/drm/card*-HDMI-A-*/status \
             /sys/class/drm/card*-HDMI-A-*/enabled \
             /sys/class/drm/card*-HDMI-A-*/dpms; do
        [ -e "$f" ] && dump_file "$f" "$f"
    done

    # Mode list (top of the EDID-derived mode table).
    for f in /sys/class/drm/card*-HDMI-A-*/modes; do
        if [ -e "$f" ]; then
            printf '\n--- %s (top 12) ---\n' "$f"
            head -12 "$f" 2>&1
        fi
    done

    # EDID is empty under vc4-fkms (firmware does the handshake), but log the
    # size — if it ever populates, that's itself a useful signal.
    for f in /sys/class/drm/card*-HDMI-A-*/edid; do
        if [ -e "$f" ]; then
            printf '\n--- %s ---\n' "$f"
            printf 'size=%s bytes\n' "$(stat -c%s "$f" 2>/dev/null)"
        fi
    done

    # DRM debugfs gives the *active* plane geometry — actual pixels being
    # scanned out, independent of /sys. Needs root.
    printf '\n--- /sys/kernel/debug/dri/0/state (plane[*], top 40 lines) ---\n'
    if state_out=$(run_root cat /sys/kernel/debug/dri/0/state 2>&1); then
        printf '%s\n' "$state_out" | head -40
    else
        printf '(skipped: needs root, or path missing)\n'
    fi

    # vcgencmd reflects the firmware's view. Under vc4-fkms it's the firmware
    # picking the mode, so this can disagree with /sys in interesting ways.
    if command -v vcgencmd >/dev/null 2>&1; then
        for cmd in 'display_power' 'get_lcd_info' 'dispmanx_list'; do
            printf '\n--- vcgencmd %s ---\n' "$cmd"
            if out=$(run_root vcgencmd $cmd 2>&1); then
                printf '%s\n' "$out"
            else
                printf '(needs root)\n'
            fi
        done
    fi

    # Console font config (what console-setup is meant to load) and the
    # actual TTY size, which is what Textual ultimately reads.
    if [ -r /etc/default/console-setup ]; then
        printf '\n--- /etc/default/console-setup (font lines) ---\n'
        grep -E '^(FONTFACE|FONTSIZE|CHARMAP|CODESET)=' /etc/default/console-setup 2>&1
    fi

    printf '\n--- stty < /dev/tty1 (rows/cols) ---\n'
    if size_out=$(run_root stty -a < /dev/tty1 2>&1); then
        printf '%s\n' "$size_out" | head -1
    else
        printf '(could not read /dev/tty1)\n'
    fi

    # Dmesg lines that tell the framebuffer story. Filter heavily.
    printf '\n--- dmesg (console/fb/drm/hdmi, last 30 matching) ---\n'
    if dmesg_out=$(dmesg -T 2>/dev/null) || dmesg_out=$(run_root dmesg -T 2>/dev/null); then
        printf '%s\n' "$dmesg_out" | grep -iE 'Console: |simple-framebuffer|simplefb|vc4-drm|vc4drmfb|hdmi|edid|fb0|fbcon' | tail -30
    else
        printf '(could not read dmesg)\n'
    fi

    printf '\n=== END %s @ %s ===\n' "$STAGE" "$(date -Is 2>/dev/null || date)"
} >> "$LOG_FILE" 2>&1

# Best-effort rotation: keep the log under ~2MB. Rough but boot-safe.
if [ -f "$LOG_FILE" ]; then
    size=$(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$size" -gt 2097152 ]; then
        mv "$LOG_FILE" "${LOG_FILE}.1" 2>/dev/null
    fi
fi

# Make sure the file ends up owned by abbey, not root, even when systemd
# runs us. Keeps `tail -f` working without sudo from a normal session.
if [ "$(id -u)" -eq 0 ] && [ -e "$LOG_FILE" ]; then
    chown abbey:abbey "$LOG_FILE" 2>/dev/null
    [ -e "${LOG_FILE}.1" ] && chown abbey:abbey "${LOG_FILE}.1" 2>/dev/null
fi

exit 0
