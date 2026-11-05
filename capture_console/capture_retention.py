"""Delete expired, registered archives without touching runtime identity or active captures."""

import logging
import shutil
import sqlite3
from pathlib import Path


HISTORY_LIMIT = 7
TERMINAL_STATUSES = {"stopped", "failed"}
logger = logging.getLogger(__name__)


def _archive_path(row, root, sessions):
    path = Path(row["outdir"])
    if (not path.is_absolute() or ".." in path.parts or path.is_symlink()
            or path.parent.resolve() != root or not path.name.startswith(("web-", "ios-"))):
        raise ValueError("archive is not a managed capture directory")
    resolved = path.resolve()
    if resolved.parent != root:
        raise ValueError("archive is outside the capture root")
    for other in sessions:
        if other["id"] == row["id"]:
            continue
        other_path = Path(other["outdir"]).resolve()
        if resolved == other_path or resolved in other_path.parents or other_path in resolved.parents:
            raise ValueError("archive overlaps another capture")
    return path


def prune_capture_history(store):
    result = {"deleted": [], "errors": []}
    root = store.db_path.parent.resolve() / "captures"
    try:
        # Serialize status transitions and cleaners until files and rows agree.
        with store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            sessions = [dict(row) for row in conn.execute("SELECT id, status, outdir FROM capture_sessions ORDER BY id DESC")]
            expired = [row for row in sessions if row["status"] in TERMINAL_STATUSES][HISTORY_LIMIT:]
            for row in expired:
                try:
                    if root.is_symlink():
                        raise ValueError("capture root must not be a symbolic link")
                    path = _archive_path(row, root, sessions)
                    if path.exists():
                        if not path.is_dir():
                            raise ValueError("archive path is not a directory")
                        shutil.rmtree(path)
                    # A crash after file removal leaves the row available for a safe retry.
                    conn.execute("DELETE FROM capture_sessions WHERE id=?", (row["id"],))
                    result["deleted"].append(row["id"])
                except (OSError, ValueError, RuntimeError) as exc:
                    logger.warning("Capture history cleanup deferred for #%s: %s", row["id"], exc)
                    result["errors"].append({"id": row["id"], "reason": str(exc)})
    except (OSError, sqlite3.Error) as exc:
        logger.warning("Capture history cleanup deferred: %s", exc)
        result["deleted"] = []
        result["errors"].append({"id": None, "reason": str(exc)})
    return result
