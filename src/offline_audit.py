"""Read-only audit of saved metadata and local artwork references."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
TABLES = ('games', 'movies', 'shows', 'books')
MEDIA_FIELDS = ('cover_path', 'background_path', 'hero_path', 'logo_path', 'image_path', 'screenshot_path')

def audit_collection(connection, root=ROOT):
    root = Path(root).resolve()
    report = {'entries': 0, 'descriptions': 0, 'media_references': 0,
              'media_present': 0, 'missing': [], 'categories': {}, 'external_media': [], 'outside_media': [], 'unreferenced_media': [], 'stored_media': 0}
    def check_media(value, label):
        if not value: return
        report['media_references'] += 1
        raw = str(value).strip()
        if raw.lower().startswith(('https://', 'http://')):
            report['external_media'].append(f'{label}: {raw}')
            return
        path = Path(raw)
        if not path.is_absolute(): path = root / path
        # Resolve for checking, without modifying anything.
        path = path.resolve()
        if not path.is_relative_to(root):
            report['outside_media'].append(f'{label}: {raw}')
        if path.is_file(): report['media_present'] += 1
        else: report['missing'].append(f'{label}: {value}')
    for table in TABLES:
        columns = {r[1] for r in connection.execute(f'PRAGMA table_info({table})')}
        if not columns: continue
        fields = ['id'] + (['description'] if 'description' in columns else []) + [f for f in MEDIA_FIELDS if f in columns]
        rows = connection.execute(f"SELECT {', '.join(fields)} FROM {table}").fetchall()
        report['entries'] += len(rows)
        report['categories'][table] = len(rows)
        for row in rows:
            record = dict(zip(fields,row))
            if record.get('description'): report['descriptions'] += 1
            for field in MEDIA_FIELDS:
                check_media(record.get(field), f"{table} #{record['id']} {field}")
    for table in ('game_screenshots', 'artwork_library'):
        cols = {r[1] for r in connection.execute(f'PRAGMA table_info({table})')}
        if 'image_path' in cols:
            for (path,) in connection.execute(f'SELECT image_path FROM {table}'):
                check_media(path, table)
    # Audit every file under assets, including media not currently selected as a cover.
    assets = root / 'assets'
    if assets.is_dir():
        report['stored_media'] = sum(1 for f in assets.rglob('*') if f.is_file() and not f.is_symlink())
    return report

def format_audit(report):
    lines = [f"Collection entries: {report['entries']}",
             f"Locally saved descriptions: {report['descriptions']}",
             f"Media references: {report['media_references']}",
             f"Media files found: {report['media_present']}",
             f"Missing media files: {len(report['missing'])}",
             f"Media files stored in assets/: {report['stored_media']}",
             f"Remote-only image references: {len(report['external_media'])}",
             f"Media references outside app folder: {len(report['outside_media'])}", '', 'Entries by category:']
    lines += [f'  {name.title()}: {count}' for name,count in report['categories'].items()]
    if report['missing']:
        lines += ['', 'Missing file references:']
        lines += ['  '+item for item in report['missing']]
    if report['external_media']:
        lines += ['', 'Remote images (not guaranteed available offline):']
        lines += ['  '+item for item in report['external_media']]
    if report['outside_media']:
        lines += ['', 'Files outside the app folder (not included in portable backups):']
        lines += ['  '+item for item in report['outside_media']]
    lines += ['', 'Descriptions and other metadata are stored in the local SQLite database.',
              'Saved artwork in assets/ is included in backups.',
              'External paths or URLs are not automatically copied into backups.',
              'Read-only check. No changes to your collection were made.']
    return '\n'.join(lines)
