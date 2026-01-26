#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   run_nohup.sh [outputfile] <command...>
#
# If outputfile is omitted, empty, or "auto", a random /tmp file is created.

# --- Determine if first argument is a logfile or part of the command ----

OUTFILE=""
if [ $# -ge 1 ]; then
    case "$1" in
        ""|"auto")
            OUTFILE=""
            shift
            ;;
        -*)
            # Looks like part of a command, not a file
            OUTFILE=""
            ;;
        *)
            # If it contains a slash or typical filename characters, treat as filename
            if [[ "$1" == */* || "$1" == *.log || "$1" == *.txt ]]; then
                OUTFILE="$1"
                shift
            fi
            ;;
    esac
fi

# If no outfile was provided, create a random temp file
if [ -z "${OUTFILE}" ]; then
    set +o pipefail
    RAND_SUFFIX="$(tr -dc 'a-f0-9' < /dev/urandom | head -c 6)"
    set -o pipefail
    OUTFILE="/tmp/nohup_$(date '+%Y%m%d_%H%M%S')_${RAND_SUFFIX}.log"
fi

# Remaining args are the command
if [ $# -lt 1 ]; then
    echo "ERROR: No command provided."
    echo "Usage: $0 [outputfile] <command...>"
    exit 1
fi

CMD=("$@")

if ! command -v "${CMD[0]}" >/dev/null 2>&1; then
    echo "ERROR: Command not found: ${CMD[0]}" >&2
    echo "Invocation was: ${CMD[*]}" >&2
    exit 127
fi


mkdir -p "$(dirname "$OUTFILE")"

(
    # Allow user command to fail without breaking footer
    set +e

    START_TS="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "======== COMMAND STARTED at ${START_TS} ========"
    echo "Command: ${CMD[*]}"
    echo ""

    "${CMD[@]}"
    EXITCODE=$?

    END_TS="$(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    echo "======== COMMAND FINISHED at ${END_TS} (exit code: ${EXITCODE}) ========"
) >"$OUTFILE" 2>&1 &

PID=$!
echo "Started PID: $PID"
echo "Output file: $OUTFILE"
echo ""
echo "To monitor output:"
echo "  tail -F '$OUTFILE'"