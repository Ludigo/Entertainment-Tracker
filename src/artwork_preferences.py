"""Local artwork locks, favourites and import-folder preferences."""
import hashlib
from pathlib import Path
from database import connection, get_setting, set_setting

CATEGORIES = ('games', 'movies', 'shows', 'books')
ROLES = ('cover_path', 'logo_path', 'background_path')


def lock_key(kind, item_id, role):
    if kind not in CATEGORIES or role not in ROLES:
        raise ValueError('Invalid artwork role')
    return f'art_lock_{kind}_{int(item_id)}_{role}'


def is_locked(kind, item_id, role):
    return get_setting(lock_key(kind, item_id, role), '0') == '1'


def set_locked(kind, item_id, role, locked):
    set_setting(lock_key(kind, item_id, role), '1' if locked else '0')


def require_unlocked(kind, item_id, role):
    if is_locked(kind, item_id, role):
        raise ValueError('Artwork is locked. Unlock this role in Artwork Manager → Assign artwork → Protection first.')


def install_artwork_guards():
    """Database guards cover every writer, including future import workflows."""
    connection.execute('CREATE TABLE IF NOT EXISTS game_detail_art (game_id INTEGER PRIMARY KEY, logo_path TEXT, background_path TEXT)')
    for kind in CATEGORIES:
        connection.execute(f'''CREATE TRIGGER IF NOT EXISTS protect_{kind}_cover
            BEFORE UPDATE OF cover_path ON {kind}
            WHEN NEW.cover_path IS NOT OLD.cover_path AND
              (SELECT value FROM settings WHERE key='art_lock_{kind}_'||OLD.id||'_cover_path')='1'
            BEGIN SELECT RAISE(ABORT, 'Artwork is locked. Unlock its role in Artwork Manager first.'); END''')
    for kind in ('movies', 'shows', 'books'):
        connection.execute(f'''CREATE TRIGGER IF NOT EXISTS protect_{kind}_background
            BEFORE UPDATE OF background_path ON {kind}
            WHEN NEW.background_path IS NOT OLD.background_path AND
              (SELECT value FROM settings WHERE key='art_lock_{kind}_'||OLD.id||'_background_path')='1'
            BEGIN SELECT RAISE(ABORT, 'Artwork is locked. Unlock its role in Artwork Manager first.'); END''')
    for role in ('logo_path', 'background_path'):
        connection.execute(f'''CREATE TRIGGER IF NOT EXISTS protect_game_{role}
            BEFORE UPDATE OF {role} ON game_detail_art
            WHEN NEW.{role} IS NOT OLD.{role} AND
              (SELECT value FROM settings WHERE key='art_lock_games_'||OLD.game_id||'_{role}')='1'
            BEGIN SELECT RAISE(ABORT, 'Artwork is locked. Unlock its role in Artwork Manager first.'); END''')
    connection.commit()


def favourite_key(kind, item_id, path):
    digest = hashlib.sha256(str(path).encode('utf-8')).hexdigest()
    return f'art_favourite_{kind}_{int(item_id)}_{digest}'


def is_favourite(kind, item_id, path):
    return bool(path) and get_setting(favourite_key(kind, item_id, path), '0') == '1'


def set_favourite(kind, item_id, path, value):
    set_setting(favourite_key(kind, item_id, path), '1' if value else '0')


def import_folder(purpose):
    value = get_setting('import_folder_' + purpose, '')
    return value if value and Path(value).is_dir() else None


def remember_import_folder(purpose, filenames):
    if filenames:
        set_setting('import_folder_' + purpose, str(Path(filenames[0]).resolve().parent))


def relink_artwork(kind, item_id, old_path, filename):
    """Copy a validated replacement locally, then repair this item's references."""
    from PIL import Image
    import io
    from database import PROJECT_ROOT
    from artwork_manager import store
    if kind not in CATEGORIES:raise ValueError('Invalid category')
    row=connection.execute(f'SELECT cover_path FROM {kind} WHERE id=?',(item_id,)).fetchone()
    assigned={'cover_path':row[0] if row else None}
    if kind in ('movies','shows','books'):
        row=connection.execute(f'SELECT background_path FROM {kind} WHERE id=?',(item_id,)).fetchone()
        if row:assigned['background_path']=row[0]
    if kind=='games':
        row=connection.execute('SELECT logo_path,background_path FROM game_detail_art WHERE game_id=?',(item_id,)).fetchone()
        if row:assigned.update(zip(('logo_path','background_path'),row))
    registered=connection.execute('SELECT 1 FROM artwork_library WHERE category=? AND item_id=? AND image_path=?',(kind,item_id,old_path)).fetchone()
    if not registered and old_path not in assigned.values():raise ValueError('Artwork no longer belongs to this item.')
    roles=[role for role,path in assigned.items() if path==old_path]
    for role in roles:require_unlocked(kind,item_id,role)
    raw=Path(filename).read_bytes()
    with Image.open(io.BytesIO(raw)) as image:
        width,height=image.size;fmt=image.format
        if fmt not in ('PNG','JPEG','WEBP','BMP') or width*height>60_000_000:
            raise ValueError('Choose a PNG, JPEG, WebP or BMP image under 60 megapixels.')
        image.verify()
    new_path=store(kind,item_id,raw,width,height,{'PNG':'.png','JPEG':'.jpg','WEBP':'.webp','BMP':'.bmp'}[fmt],'Relinked local file',set_cover=False)
    favourite=is_favourite(kind,item_id,old_path)
    with connection:
        if 'cover_path' in roles:
            connection.execute(f'UPDATE {kind} SET cover_path=? WHERE id=?',(new_path,item_id))
        for role in roles:
            if role!='cover_path':
                table,id_column=(kind,'id') if kind in ('movies','shows','books') else ('game_detail_art','game_id')
                connection.execute(f'UPDATE {table} SET {role}=? WHERE {id_column}=?',(new_path,item_id))
        if new_path!=old_path:
            connection.execute('DELETE FROM artwork_library WHERE category=? AND item_id=? AND image_path=?',(kind,item_id,old_path))
        if favourite:
            connection.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(favourite_key(kind,item_id,new_path),'1'))
    # Neither the selected original nor any old file is removed.
    return new_path

