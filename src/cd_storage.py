"""Commit album, tracks and staged local artwork in one transaction."""
import uuid
from database import connection, PROJECT_ROOT


def save_album(values, tracks, item_id=None, artwork=None, expected=None):
    from add_game_metadata import validated_cover, image_digest
    from artwork_preferences import require_unlocked
    from media_naming import clean_name
    values=dict(values)
    permitted={r[1] for r in connection.execute('PRAGMA table_info(cds)')} - {'id','cover_path','background_path'}
    if not set(values).issubset(permitted):raise ValueError('Invalid album metadata field.')
    artwork=artwork or {}
    changed=set(artwork.get('changed',())) if item_id else {'cover','background'}
    if not changed.issubset({'cover','background'}):raise ValueError('Invalid artwork role.')
    images=[image for image in artwork.get('extras',[]) if image]
    for key in changed:
        if artwork.get(key):images.append(artwork[key])
    checked={image_digest(i):validated_cover(i['raw'],i['label'],i['source']) for i in images}
    created=[]; paths={}
    try:
        with connection:
            if item_id is None:
                keys=list(values)
                item_id=connection.execute('INSERT INTO cds ('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+')',tuple(values.values())).lastrowid
            else:
                row=connection.execute('SELECT cover_path,background_path,listening_time FROM cds WHERE id=?',(item_id,)).fetchone()
                if row is None:raise ValueError('This album no longer exists.')
                if expected:
                    if row[2]!=expected.get('listening_time',row[2]):
                        raise ValueError('Listening time changed. Reopen Metadata to retain the latest total.')
                    for index,key in enumerate(('cover','background')):
                        if key in changed and row[index]!=expected.get(key+'_path'):
                            raise ValueError('Artwork changed. Reopen Metadata before replacing that role.')
                for key in changed:require_unlocked('cds',item_id,key+'_path')
                assignments=','.join(k+'=?' for k in values)
                connection.execute('UPDATE cds SET '+assignments+' WHERE id=?',(*values.values(),item_id))
                connection.execute('DELETE FROM cd_tracks WHERE cd_id=?',(item_id,))
            connection.executemany('INSERT INTO cd_tracks (cd_id,disc,track,name,duration_seconds) VALUES (?,?,?,?,?)',
                [(item_id,t['disc'],t['track'],t['name'],t['duration_seconds']) for t in tracks])
            # Reuse byte-identical registered artwork within this album.
            for (path,) in connection.execute("SELECT image_path FROM artwork_library WHERE category='cds' AND item_id=?",(item_id,)):
                try:
                    import hashlib
                    paths[hashlib.sha256((PROJECT_ROOT/path).read_bytes()).hexdigest()]=path
                except (OSError,TypeError):pass
            for digest,image in checked.items():
                if digest in paths:continue
                folder=PROJECT_ROOT/'assets'/'artwork'/'cds';folder.mkdir(parents=True,exist_ok=True)
                target=folder/f'{clean_name(values["name"])} - Artwork - {uuid.uuid4().hex[:12]}{image["ext"]}'
                created.append(target);target.write_bytes(image['raw'])
                path=target.relative_to(PROJECT_ROOT).as_posix();paths[digest]=path
                connection.execute('INSERT INTO artwork_library(category,item_id,image_path,width,height,source) VALUES(?,?,?,?,?,?)',
                    ('cds',item_id,path,image['w'],image['h'],image['source']))
            for key in changed:
                image=artwork.get(key)
                path=paths[image_digest(image)] if image else None
                connection.execute('UPDATE cds SET '+key+'_path=? WHERE id=?',(path,item_id))
        return item_id
    except Exception:
        for path in created:path.unlink(missing_ok=True)
        raise
