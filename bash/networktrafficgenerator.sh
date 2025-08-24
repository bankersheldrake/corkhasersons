#!/bin/bash

# === Argument Parsing ===
RCLONE_PASS="$1"
RCLONE_REMOTE_NAME="$2"
FILESIZE_MB="${3:-10}"
UPLOAD_SUBPATH="${4:-}"

# === Validation ===
if [[ -z "$RCLONE_PASS" || -z "$RCLONE_REMOTE_NAME" ]]; then
    echo "❌ Usage: $0 <RCLONE_CONFIG_PASS> <RCLONE_REMOTE_NAME> [FILESIZE_MB] [UPLOAD_SUBPATH]"
    echo "    RCLONE_CONFIG_PASS and RCLONE_REMOTE_NAME are required."
    exit 1
fi
# === Source URL based on requested file size ===
SOURCE_URL="https://mirror.nforce.com/pub/speedtests/${FILESIZE_MB}mb.bin"

# === Trap Ctrl+C cleanly ===
trap "echo -e '\n🛑 Exiting loop.'; exit 0" SIGINT

while true; do
    RAND_FILE="/tmp/${FILESIZE_MB}mb_$(date +%s)_$RANDOM.bin"

    echo "⬇️  Downloading $SOURCE_URL → $RAND_FILE ..."
    curl -s -o "$RAND_FILE" "$SOURCE_URL"

    if [[ ! -f "$RAND_FILE" ]]; then
        echo "❌ Download failed. Retrying in 5 seconds..."
        sleep 5
        continue
    fi

    if [[ -n "$RCLONE_REMOTE_NAME" ]]; then
        DEST_PATH="${RCLONE_REMOTE_NAME}:${UPLOAD_SUBPATH}"
        echo "⬆️  Uploading to Koofr: ${DEST_PATH:-(root)}"

        export RCLONE_CONFIG_PASS="$RCLONE_PASS"
        if rclone --ask-password=false copy "$RAND_FILE" "$DEST_PATH" 2> /tmp/rclone_error.log; then
            echo "✅ Upload succeeded."
        else
            echo "❌ Upload failed!"
            cat /tmp/rclone_error.log
            if grep -qi 'failed to decrypt configuration file' /tmp/rclone_error.log; then
                echo "⚠️  RCLONE_CONFIG_PASS appears to be incorrect."
            fi
            export RCLONE_CONFIG_PASS="xxxxxxx"
            rm -f "$RAND_FILE"
            sleep 10
            continue
        fi
        export RCLONE_CONFIG_PASS="xxxxxxx"
    else
        echo "⏩ Skipping upload (no RCLONE_REMOTE_NAME set)."
    fi

    echo "🧹  Cleaning up $RAND_FILE ..."
    rm -f "$RAND_FILE"

    echo "⏳ Waiting 5 seconds before next run..."
    sleep 5
done
