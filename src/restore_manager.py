"""Conservative, restart-only collection restoration."""
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime, timezone
from contextlib import closing

ROOT = Path(__file__).resolve().parent.parent
PENDING = ROOT / 'backups' / 'pending_restore.json'


def validate_backup(path):
    path = Path(path).resolve()
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or 'data/entertainment.db' not in names:
            raise ValueError('Invalid backup: missing database or duplicate entries')
        for item in archive.infolist():
            name = item.filename
            parts = Path(name).parts
            if (name.startswith('/') or '\\' in name or '..' in parts or
                    (parts and parts[0] not in ('assets', 'data', 'backup_info.json')) or
                    (parts and parts[0] == 'data' and name != 'data/entertainment.db') or
                    (parts and parts[0] == 'assets' and len(parts) < 2 and not item.is_dir())):
                raise ValueError('Unexpected path inside backup')
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Backup contains a symbolic link')
        if archive.testzip() is not None:
            raise ValueError('Backup failed ZIP integrity check')
        with tempfile.TemporaryDirectory(prefix='et_verify_') as tmp:
            db = Path(tmp) / 'check.db'
            db.write_bytes(archive.read('data/entertainment.db'))
            with closing(sqlite3.connect(db)) as con:
                if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup database failed SQLite integrity check')
    return path


def schedule_restore(path):
    source = validate_backup(path)
    PENDING.parent.mkdir(parents=True, exist_ok=True)
    # Keep a private copy so the original ZIP cannot change before restart.
    queued = PENDING.parent / 'restore_queued.zip'
    if source != queued.resolve():
        with tempfile.NamedTemporaryFile(dir=PENDING.parent, suffix='.zip', delete=False) as tmp:
            staged = Path(tmp.name)
        try:
            shutil.copy2(source, staged)
            validate_backup(staged)
            os.replace(staged, queued)
        finally:
            staged.unlink(missing_ok=True)
    with tempfile.NamedTemporaryFile(dir=PENDING.parent, mode='w', encoding='utf8', delete=False) as tmp:
        pending_tmp = Path(tmp.name)
        json.dump({'file': queued.name}, tmp)
    os.replace(pending_tmp, PENDING)


def apply_pending_restore():
    """Called before opening SQLite, when no app DB connection exists."""
    if not PENDING.exists():
        return None
    queued = PENDING.parent / json.loads(PENDING.read_text(encoding='utf8'))['file']
    if queued.name != 'restore_queued.zip' or queued.parent != PENDING.parent:
        raise ValueError('Unexpected restore request')
    validate_backup(queued)
    from backup_manager import create_backup
    database = ROOT / 'data' / 'entertainment.db'
    assets = ROOT / 'assets'
    with tempfile.TemporaryDirectory(prefix='et_restore_', dir=ROOT) as temp:
        temp = Path(temp)
        with ZipFile(queued) as archive:
            archive.extractall(temp / 'incoming')
        incoming = temp / 'incoming'
        new_db = incoming / 'data' / 'entertainment.db'
        new_assets = incoming / 'assets'
        new_assets.mkdir(exist_ok=True)
        # Full pre-restore recovery archive, including current artwork.
        safety_dir = ROOT / 'backups'
        safety_dir.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        safety = safety_dir / f'pre_restore_safety_{stamp}.zip'
        with ZipFile(safety, 'w', ZIP_DEFLATED) as archive:
            if database.is_file():
                archive.write(database, 'data/entertainment.db')
            if assets.exists():
                for item in assets.rglob('*'):
                    if item.is_file() and not item.is_symlink():
                        archive.write(item, item.relative_to(ROOT).as_posix())
        with ZipFile(safety) as archive:
            if archive.testzip() is not None:
                raise IOError('Safety backup integrity check failed')
        old_db = temp / 'old.db'
        old_assets = temp / 'old_assets'
        moved_db = False
        moved_assets = False
        try:
            database.parent.mkdir(exist_ok=True)
            if database.exists():
                os.replace(database, old_db)
                moved_db = True
            if assets.exists():
                os.replace(assets, old_assets)
                moved_assets = True
            os.replace(new_db, database)
            os.replace(new_assets, assets)
        except Exception:
            if database.exists():
                database.unlink()
            if assets.exists():
                shutil.rmtree(assets)
            if moved_db:
                os.replace(old_db, database)
            if moved_assets:
                os.replace(old_assets, assets)
            raise
    PENDING.unlink(missing_ok=True)
    queued.unlink(missing_ok=True)
    return safety
