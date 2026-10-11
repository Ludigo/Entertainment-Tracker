"""Share saved artwork references across every season of a grouped show."""
from database import connection


def share(item_id):
    from show_series import seasons
    records=seasons(item_id)
    ids=[r['id'] for r in records]
    if not ids:return
    marks=','.join('?' for _ in ids)
    rows=connection.execute(f"SELECT image_path,width,height,source FROM artwork_library WHERE category='shows' AND item_id IN ({marks}) ORDER BY id",ids).fetchall()
    images={r[0]:r for r in rows}
    for record in records:
        for role in ('cover_path','background_path','logo_path'):
            path=record.get(role)
            if path:images.setdefault(path,(path,0,0,'Saved season artwork'))
    with connection:
        for ident in ids:
            for path,width,height,source in images.values():
                connection.execute("""INSERT INTO artwork_library(category,item_id,image_path,width,height,source)
                    SELECT 'shows',?,?,?,?,? WHERE NOT EXISTS
                    (SELECT 1 FROM artwork_library WHERE category='shows' AND item_id=? AND image_path=?)""",
                    (ident,path,width,height,source,ident,path))


def remove(item_id,path):
    """Remove a shared image atomically, honouring each season's artwork locks."""
    from show_series import seasons
    from artwork_preferences import require_unlocked
    records=seasons(item_id)
    for record in records:
        for role in ('cover_path','background_path','logo_path'):
            if record.get(role)==path:require_unlocked('shows',record['id'],role)
    with connection:
        for record in records:
            ident=record['id']
            connection.execute("DELETE FROM artwork_library WHERE category='shows' AND item_id=? AND image_path=?",(ident,path))
            for role in ('cover_path','background_path','logo_path'):
                connection.execute(f'UPDATE shows SET {role}=NULL WHERE id=? AND {role}=?',(ident,path))


def assign(item_id,role,path):
    """Apply a summary artwork choice to every season in one transaction."""
    if role not in ('cover_path','background_path','logo_path'):raise ValueError('Invalid show artwork role')
    from show_series import seasons
    from artwork_preferences import require_unlocked
    records=seasons(item_id)
    for record in records:require_unlocked('shows',record['id'],role)
    share(item_id)
    if path and not connection.execute("SELECT 1 FROM artwork_library WHERE category='shows' AND item_id=? AND image_path=?",(item_id,path)).fetchone():
        raise ValueError('Choose artwork from the shared show collection.')
    with connection:
        for record in records:
            connection.execute(f'UPDATE shows SET {role}=? WHERE id=?',(path,record['id']))
