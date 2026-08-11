#!/system/bin/sh

LOG_FILE=/data/local/tmp/ai-capture-root-grant.log
MAGISK_BIN=/debug_ramdisk/magisk

touch "$LOG_FILE"
chmod 0644 "$LOG_FILE"
{
    echo "=== AI Capture root grant ==="
    for attempt in 1 2 3 4 5 6 7 8 9 10; do
        if "$MAGISK_BIN" -v >/dev/null 2>&1; then
            "$MAGISK_BIN" --sqlite "REPLACE INTO settings (key, value) VALUES ('root_access', 3);"
            "$MAGISK_BIN" --sqlite "REPLACE INTO policies (uid, policy, until, logging, notification) VALUES(2000, 2, 0, 1, 0);"
            echo "granted Magisk root to Android shell uid 2000"
            exit 0
        fi
        sleep 1
    done
    echo "Magisk daemon did not become ready"
    exit 1
} >>"$LOG_FILE" 2>&1
