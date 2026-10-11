"""Album listings group editions without merging or rewriting saved records."""
from database import connection, get_setting
import unicodedata

def key(row):
    identity=tuple(' '.join(unicodedata.normalize('NFKC',str(row.get(k) or '')).split()).casefold() for k in ('artist','name'))
    if get_setting('group_album_editions','1')!='1' or row.get('keep_separate') or not all(identity):
        return ('record',int(row['id']))
    return ('album',*identity)

def all_records():
    cur=connection.execute('SELECT * FROM cds ORDER BY release_year,id')
    names=[c[0] for c in cur.description]
    return [dict(zip(names,r)) for r in cur]

def editions(item_id):
    rows=all_records();record=next((r for r in rows if r['id']==int(item_id)),None)
    return [r for r in rows if key(r)==key(record)] if record else []

def groups(ordered_ids=None):
    rows=all_records();by_id={r['id']:r for r in rows};by_key={}
    for r in rows:by_key.setdefault(key(r),[]).append(r)
    result=[];seen=set()
    for ident in list(by_id) if ordered_ids is None else ordered_ids:
        r=by_id.get(int(ident))
        if r is None or key(r) in seen:continue
        seen.add(key(r));members=by_key[key(r)]
        result.append({'id':r['id'],'name':r['name'],'members':members,'cover_path':r.get('cover_path') or next((m['cover_path'] for m in members if m.get('cover_path')),None)})
    return result

def edition_labels(rows):
    return [f"#{r['id']} · {r.get('release_year') or 'Year unknown'} · {'Physical + Digital' if r.get('owned_physical') and r.get('owned_digital') else 'Physical' if r.get('owned_physical') else 'Digital' if r.get('owned_digital') else 'Ownership unset'} · {r.get('label') or ''} · {r.get('barcode') or ''}" for r in rows]
