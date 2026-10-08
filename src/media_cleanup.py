"""Conservative unused-media discovery and reversible quarantine.

Never deletes media. Uncertain references are kept, not flagged for removal.
"""
from pathlib import Path
from datetime import datetime
import json
import shutil
import sqlite3
import uuid
from urllib.parse import unquote, urlparse
from backup_manager import create_backup

ROOT = Path(__file__).resolve().parent.parent
MEDIA_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.avif', '.ico', '.jfif'}


def _referenced_paths(db, root):
    """Scan all text-like DB columns, including future metadata tables."""
    exact = set()
    basenames = set()
    for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        safe = '"' + table.replace('"', '""') + '"'
        columns = db.execute(f'PRAGMA table_info({safe})').fetchall()
        for col in columns:
            name, declared = col[1], (col[2] or '').upper()
            if not any(t in declared for t in ('TEXT', 'CHAR', 'CLOB', 'VARCHAR')) and not any(k in name.lower() for k in ('path','image','cover','art','logo','hero','background','screen')):
                continue
            field = '"' + name.replace('"', '""') + '"'
            for (value,) in db.execute(f'SELECT {field} FROM {safe} WHERE {field} IS NOT NULL'):
                if not isinstance(value, str) or not value.strip():
                    continue
                value = value.strip()
                if value.startswith(('http://','https://')):
                    continue
                # Exact paths are checked, and embedded path strings protect their basename.
                candidate = Path(value.replace('\\','/'))
                resolved = (candidate if candidate.is_absolute() else root/candidate).resolve()
                exact.add(str(resolved).casefold())
                basenames.add(candidate.name.casefold())
                # Some fields contain JSON arrays of image paths.
                try:
                    decoded = json.loads(value)
                except (ValueError, TypeError):
                    decoded = None
                if isinstance(decoded, (list,dict)):
                    def walk(v):
                        if isinstance(v, str):
                            x=Path(v.replace('\\','/'))
                            basenames.add(x.name.casefold())
                            exact.add(str((x if x.is_absolute() else root/x).resolve()).casefold())
                        elif isinstance(v, dict):
                            for y in v.values(): walk(y)
                        elif isinstance(v, list):
                            for y in v: walk(y)
                    walk(decoded)
    return exact, basenames


def scan_unused(db, root=ROOT):
    root=Path(root).resolve()
    assets=(root/'assets').resolve()
    if not assets.is_dir():
        return []
    exact, names = _referenced_paths(db, root)
    candidates=[]
    for file in sorted(assets.rglob('*')):
        if not file.is_file() or file.is_symlink() or file.suffix.lower() not in MEDIA_EXTS:
            continue
        resolved=file.resolve()
        if not resolved.is_relative_to(assets):
            continue
        # If another database value uses the same basename, err on the safe side.
        if str(resolved).casefold() in exact or file.name.casefold() in names:
            continue
        candidates.append((file.relative_to(root).as_posix(),file.stat().st_size))
    return candidates


def quarantine_unused(db, selected, root=ROOT):
    root=Path(root).resolve()
    assets=(root/'assets').resolve()
    selected=set(selected)
    fresh={path for path,_ in scan_unused(db,root)}
    if not selected or not selected.issubset(fresh):
        raise ValueError('Media references changed; scan again before cleaning.')
    # Back up before any file is moved; database is never modified.
    safety=create_backup(db)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    destination=root/'media_quarantine'/f'{stamp}_{uuid.uuid4().hex[:6]}'
    moved=[]
    try:
        for rel in sorted(selected):
            source=(root/rel).resolve()
            if not source.is_relative_to(assets) or source.is_symlink() or not source.is_file():
                raise ValueError('Media changed during cleanup; nothing else moved.')
            target=destination/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.move(str(source),str(target))
            moved.append((source,target))
        manifest={'backup':safety.name,'files':[str(target.relative_to(destination).as_posix()) for _,target in moved]}
        (destination/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    except Exception:
        for source,target in reversed(moved):
            if target.exists():
                source.parent.mkdir(parents=True,exist_ok=True)
                shutil.move(str(target),str(source))
        raise
    return destination,safety,len(moved)
