"""Safe, descriptive names for locally managed media. No external files are renamed."""
from pathlib import Path
import re
import uuid
from collections import defaultdict
from backup_manager import create_backup

ROOT = Path(__file__).resolve().parent.parent
CATEGORIES = ('games', 'movies', 'shows', 'books', 'cds')
MEDIA_FIELDS = ('cover_path', 'background_path', 'hero_path', 'logo_path', 'image_path', 'screenshot_path')

def clean_name(name):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', str(name or 'Untitled'))
    value = re.sub(r'\s+', ' ', value).strip(' .-')[:95].rstrip(' .') or 'Untitled'
    if value.split('.')[0].upper() in {'CON','PRN','AUX','NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}:
        value = '_' + value
    return value

def _columns(db, table):
    return {r[1] for r in db.execute(f'PRAGMA table_info({table})')}

def _references(db):
    refs = defaultdict(list)
    for category in CATEGORIES:
        cols = _columns(db, category)
        if not {'id','name'}.issubset(cols): continue
        for field in MEDIA_FIELDS:
            if field not in cols: continue
            for id_, name, path in db.execute(f'SELECT id, name, {field} FROM {category} WHERE {field} IS NOT NULL'):
                if path: refs[str(path)].append((category, field, id_, name, field.removesuffix('_path').title()))
    if {'id','game_id','image_path'}.issubset(_columns(db, 'game_screenshots')):
        for id_, game_id, name, path in db.execute('SELECT s.id,s.game_id,g.name,s.image_path FROM game_screenshots s JOIN games g ON g.id=s.game_id'):
            if path: refs[str(path)].append(('game_screenshots','image_path',id_,name,'Screenshot'))
    if {'id','category','item_id','image_path'}.issubset(_columns(db, 'artwork_library')):
        for id_, category, item_id, path in db.execute('SELECT id,category,item_id,image_path FROM artwork_library'):
            if path: refs[str(path)].append(('artwork_library','image_path',id_,None,'Artwork'))
    if {'game_id','logo_path','background_path'}.issubset(_columns(db, 'game_detail_art')):
        for game_id, title, logo, background in db.execute(
            'SELECT d.game_id,g.name,d.logo_path,d.background_path '
            'FROM game_detail_art d JOIN games g ON g.id=d.game_id'):
            if logo: refs[str(logo)].append(('game_detail_art','logo_path',game_id,title,'Logo'))
            if background: refs[str(background)].append(('game_detail_art','background_path',game_id,title,'Background'))
    return refs

def plan_renames(db, root=ROOT):
    root=Path(root).resolve()
    assets=(root/'assets').resolve()
    refs=_references(db)
    proposed=[]; skipped=[]; occupied=set()
    counters=defaultdict(int)
    for raw, usages in sorted(refs.items()):
        if raw.lower().startswith(('http://','https://')):
            skipped.append((raw,'Remote URL')); continue
        path=Path(raw)
        source=(path if path.is_absolute() else root/path).resolve()
        if not source.is_relative_to(assets) or not source.is_file() or source.is_symlink():
            skipped.append((raw,'External or missing file')); continue
        # One file can be referenced by multiple records. Do not guess its ownership.
        owners={('games',u[2]) if u[0]=='game_detail_art' else (u[0],u[2]) for u in usages if u[0] != 'artwork_library'}
        if len(owners)>1:
            skipped.append((raw,'Shared by multiple entries')); continue
        primary=next((u for u in usages if u[3]),None)
        if primary is None:
            # Artwork library references have no name: resolve category and item id.
            art=next((u for u in usages if u[0]=='artwork_library'),None)
            if art and art[1]=='image_path':
                cat=db.execute('SELECT category,item_id FROM artwork_library WHERE id=?',(art[2],)).fetchone()
                if cat and cat[0] in CATEGORIES:
                    row=db.execute(f'SELECT name FROM {cat[0]} WHERE id=?',(cat[1],)).fetchone()
                    if row: primary=(cat[0],'image_path',cat[1],row[0],'Artwork')
        if primary is None:
            skipped.append((raw,'No matching collection title')); continue
        kind,field,item_id,title,role=primary
        # Determine role from the saved filename folder and selected-cover references.
        if any(u[0]=='game_detail_art' and u[1]=='logo_path' for u in usages): role='Logo'
        elif any(u[0]=='game_detail_art' and u[1]=='background_path' for u in usages): role='Background'
        elif kind=='game_screenshots': role='Screenshot'
        elif any(u[0] in CATEGORIES and u[1]=='cover_path' for u in usages): role='Cover'
        elif role=='Artwork': role='Artwork'
        stem=f'{clean_name(title)} - {role}'
        key=(kind,item_id,role)
        counters[key]+=1
        # Unique stable suffix prevents overwrites and accommodates multiple artworks.
        suffix=f' {counters[key]:02d}' if role in ('Artwork','Screenshot') or counters[key]>1 else ''
        target=source.with_name(f'{stem}{suffix}{source.suffix.lower()}')
        if target==source: continue
        n=2
        while target.exists() or target in occupied:
            target=source.with_name(f'{stem}{suffix} ({n}){source.suffix.lower()}'); n+=1
        occupied.add(target)
        proposed.append((raw,source,target))
    return proposed,skipped

def rename_existing(db, root=ROOT):
    root=Path(root).resolve()
    planned,skipped=plan_renames(db,root)
    if not planned: return 0,skipped,None
    safety=create_backup(db)
    moved=[]
    try:
        # One transaction for every DB reference; reverse filesystem moves on failure.
        db.execute('BEGIN IMMEDIATE')
        for raw,source,target in planned:
            source.rename(target)
            moved.append((source,target))
            rel=target.relative_to(root).as_posix()
            for table in CATEGORIES:
                for field in MEDIA_FIELDS:
                    if field in _columns(db,table):
                        db.execute(f'UPDATE {table} SET {field}=? WHERE {field}=?',(rel,raw))
            for field in ('logo_path','background_path'):
                if field in _columns(db,'game_detail_art'):
                    db.execute(f'UPDATE game_detail_art SET {field}=? WHERE {field}=?',(rel,raw))
            for table in ('artwork_library','game_screenshots'):
                if 'image_path' in _columns(db,table):
                    db.execute(f'UPDATE {table} SET image_path=? WHERE image_path=?',(rel,raw))
        db.commit()
    except Exception:
        db.rollback()
        for source,target in reversed(moved):
            if target.exists(): target.rename(source)
        raise
    return len(moved),skipped,safety

