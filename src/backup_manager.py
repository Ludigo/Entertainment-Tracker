"""Local, portable collection backups (database + media)."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
from zipfile import ZipFile, ZIP_DEFLATED
import json
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
DATABASE = ROOT / "data" / "entertainment.db"
BACKUP_DIR = ROOT / "backups"
MEDIA_DIR = ROOT / "assets"
MAX_BACKUPS = 10

def create_backup(connection, *, automatic=False):
    """Snapshot a live SQLite database safely and bundle local media in a ZIP."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    target = BACKUP_DIR / f"entertainment_{timestamp}.zip"
    # Windows keeps SQLite files locked until connections are explicitly closed.
    # sqlite3's context manager commits/rolls back but does NOT close the handle.
    with TemporaryDirectory(prefix="et_backup_") as temp_dir:
        db_snapshot = Path(temp_dir) / "snapshot.sqlite"
        try:
            with closing(sqlite3.connect(db_snapshot)) as destination:
                connection.backup(destination)
            # The destination handle is now closed before ZIP reads the snapshot.
            with ZipFile(target, "w", ZIP_DEFLATED, compresslevel=6) as archive:
                archive.write(db_snapshot, "data/entertainment.db")
                if MEDIA_DIR.is_dir():
                    for media in sorted(MEDIA_DIR.rglob("*")):
                        if media.is_file() and not media.is_symlink():
                            archive.write(media, media.relative_to(ROOT).as_posix())
                archive.writestr("backup_info.json", json.dumps({
                    "format": 1,
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                    "automatic": automatic
                }, indent=2))
            with ZipFile(target) as archive:
                if archive.testzip() is not None:
                    raise IOError("Backup ZIP failed integrity verification")
            existing = sorted(BACKUP_DIR.glob("entertainment_*.zip"), reverse=True)
            for old in existing[MAX_BACKUPS:]:
                old.unlink()
            return target
        except Exception:
            target.unlink(missing_ok=True)
            raise


def automatic_backup_if_due(connection):
    """Create at most one automatic backup per UTC calendar day."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    if BACKUP_DIR.exists():
        for candidate in BACKUP_DIR.glob("entertainment_*.zip"):
            try:
                with ZipFile(candidate) as archive:
                    meta = json.loads(archive.read("backup_info.json"))
                if meta.get("automatic") and candidate.name.startswith(f"entertainment_{today}_"):
                    return None
            except (OSError, ValueError, KeyError):
                continue
    return create_backup(connection, automatic=True)
