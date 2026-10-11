"""Transactional collection management; presentation grouping never changes rows."""
import json
import math
import unicodedata
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from database import connection, PROJECT_ROOT

KINDS=('games','movies','shows','books','cds')
SESSIONS={'games':('game_sessions','game_id','playtime'),
          'books':('book_sessions','book_id','reading_time'),
          'cds':('cd_sessions','cd_id','listening_time')}

def migrate():
    for kind in KINDS:
        columns={r[1] for r in connection.execute('PRAGMA table_info('+kind+')')}
        if 'estimated_value' not in columns:connection.execute('ALTER TABLE '+kind+' ADD COLUMN estimated_value REAL')
    connection.execute('CREATE TABLE IF NOT EXISTS collection_shelves(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE COLLATE NOCASE)')
    connection.execute('CREATE TABLE IF NOT EXISTS shelf_members(shelf_id INTEGER NOT NULL,kind TEXT NOT NULL,item_id INTEGER NOT NULL,PRIMARY KEY(shelf_id,kind,item_id))')
    connection.execute('CREATE TABLE IF NOT EXISTS duplicate_exceptions(kind TEXT NOT NULL,first_id INTEGER NOT NULL,second_id INTEGER NOT NULL,PRIMARY KEY(kind,first_id,second_id))')
    connection.execute('CREATE TABLE IF NOT EXISTS filter_presets(kind TEXT NOT NULL,name TEXT NOT NULL COLLATE NOCASE,state TEXT NOT NULL,PRIMARY KEY(kind,name))')
    if 'session_id' not in {r[1] for r in connection.execute('PRAGMA table_info(cd_track_plays)')}:
        connection.execute('ALTER TABLE cd_track_plays ADD COLUMN session_id INTEGER')
    def missing(kind,role,cover,description,year,artist,author,background):
        fields=missing_fields(kind,dict(cover_path=cover,description=description,release_year=year,artist=artist,author=author,background_path=background))
        if role=='Any metadata':return int(any(f!='background_path' for f in fields))
        field={'Cover':'cover_path','Description':'description','Release year':'release_year','Artist / author':'artist' if kind=='cds' else 'author','Background':'background_path'}.get(role)
        return int(field in fields)
    connection.create_function('collection_missing',8,missing)

def records(kind,ids=None):
    if kind not in KINDS:raise ValueError('Unknown collection.')
    cur=connection.execute('SELECT * FROM '+kind+' ORDER BY name COLLATE NOCASE,id')
    rows=[dict(zip([d[0] for d in cur.description],r)) for r in cur]
    if kind=='games':
        art={r[0]:r[1:] for r in connection.execute('SELECT game_id,background_path,logo_path FROM game_detail_art')}
        for row in rows:row.update(background_path=art.get(row['id'],(None,None))[0],logo_path=art.get(row['id'],(None,None))[1])
    if ids is None:return rows
    lookup={r['id']:r for r in rows}
    return [lookup[i] for i in dict.fromkeys(map(int,ids)) if i in lookup]

def selected(kind,ids):
    ids=list(dict.fromkeys(map(int,ids)));rows=records(kind,ids)
    if not ids:raise ValueError('Select at least one saved record.')
    if len(rows)!=len(ids):raise ValueError('A selected record was removed. Reload before applying.')
    return rows

def money(value):
    amount=float(value)
    if not math.isfinite(amount) or amount<0:raise ValueError('Enter a finite, non-negative amount.')
    return amount

def bulk_update(kind,ids,field,value):
    from collection_tools import normalise_tags
    rows=selected(kind,ids)
    allowed={'owned_physical','owned_digital','wishlist','tags','condition','estimated_value'}
    if kind=='games':allowed.add('backlog')
    if field not in allowed:raise ValueError('Unsupported bulk field.')
    if field in ('owned_physical','owned_digital','wishlist','backlog'):
        if str(value) not in ('0','1'):raise ValueError('Choose Yes or No.')
        value=int(value)
    elif field=='estimated_value':value=money(value) if str(value).strip() else None
    elif field=='tags':value=normalise_tags(value)
    else:value=str(value).strip() or None
    with connection:
        for row in rows:
            connection.execute('UPDATE '+kind+' SET '+field+'=? WHERE id=?',(value,row['id']))
            if field in ('owned_physical','owned_digital') and 'owned' in row:
                other='owned_digital' if field=='owned_physical' else 'owned_physical'
                owned=int(bool(value or row.get(other) or (row.get('owned') and not row.get('owned_physical') and not row.get('owned_digital'))))
                connection.execute('UPDATE '+kind+' SET owned=? WHERE id=?',(owned,row['id']))
    return len(rows)

def purchase(kind,ids,price,shop,purchased,physical,digital):
    rows=selected(kind,ids);price=money(price);purchased=date.fromisoformat(purchased).isoformat()
    if not physical and not digital:raise ValueError('Choose Physical, Digital or both.')
    with connection:
        for row in rows:
            if not row.get('wishlist'):raise ValueError('Purchase actions require wishlist entries. Nothing was changed.')
            values={'wishlist':0,'price_paid':price,'purchase_date':purchased,'purchase_shop':str(shop).strip(),
                    'owned_physical':int(bool(physical)),'owned_digital':int(bool(digital))}
            if 'owned' in row:values['owned']=1
            connection.execute('UPDATE '+kind+' SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),row['id']))
    return len(rows)

def values_summary(kind,ids):
    rows=records(kind,ids);paid=[r for r in rows if r.get('price_paid') is not None]
    valued=[r for r in rows if r.get('estimated_value') is not None]
    both=[r for r in rows if r.get('price_paid') is not None and r.get('estimated_value') is not None]
    return f"Paid £{sum(r['price_paid'] for r in paid):,.2f} ({len(paid)} recorded) · Estimated £{sum(r['estimated_value'] for r in valued):,.2f} ({len(valued)} recorded) · Difference £{sum(r['estimated_value']-r['price_paid'] for r in both):+,.2f} ({len(both)} with both)"

def norm(value):return ' '.join(unicodedata.normalize('NFKC',str(value or '')).split()).casefold()

def duplicates(kind,ids):
    rows=records(kind,ids);groups={};result=[]
    secondary={'games':'platform','books':'author','cds':'artist'}.get(kind)
    ignored={tuple(r) for r in connection.execute('SELECT first_id,second_id FROM duplicate_exceptions WHERE kind=?',(kind,))}
    for row in rows:
        k=(norm(row['name']),norm(row.get(secondary)) if secondary else '')
        for other in groups.get(k,[]):
            if kind=='shows' and other.get('season')!=row.get('season'):continue
            pair=tuple(sorted((other['id'],row['id'])))
            if pair not in ignored:result.append((other,row))
        groups.setdefault(k,[]).append(row)
    return result

def different_edition(kind,first,second):
    rows=selected(kind,[first,second]);pair=sorted((int(first),int(second)))
    if len(rows)!=2:raise ValueError('Choose two different records.')
    with connection:
        connection.execute('INSERT OR IGNORE INTO duplicate_exceptions VALUES(?,?,?)',(kind,*pair))
        if kind=='cds':connection.execute('UPDATE cds SET keep_separate=1 WHERE id IN (?,?)',pair)

def shelves():return list(connection.execute('SELECT id,name FROM collection_shelves ORDER BY name COLLATE NOCASE'))

def create_shelf(name):
    name=' '.join(str(name).split())
    if not name:raise ValueError('Enter a shelf name.')
    with connection:cur=connection.execute('INSERT INTO collection_shelves(name) VALUES(?)',(name,))
    return cur.lastrowid

def shelf_change(kind,ids,shelf_id,add=True):
    rows=selected(kind,ids)
    if not connection.execute('SELECT 1 FROM collection_shelves WHERE id=?',(shelf_id,)).fetchone():raise ValueError('Shelf no longer exists.')
    with connection:
        for row in rows:
            if add:connection.execute('INSERT OR IGNORE INTO shelf_members VALUES(?,?,?)',(shelf_id,kind,row['id']))
            else:connection.execute('DELETE FROM shelf_members WHERE shelf_id=? AND kind=? AND item_id=?',(shelf_id,kind,row['id']))
    return len(rows)

def preset_save(kind,name,state):
    if kind not in KINDS or not str(name).strip():raise ValueError('Enter a preset name.')
    with connection:connection.execute('INSERT INTO filter_presets VALUES(?,?,?) ON CONFLICT(kind,name) DO UPDATE SET state=excluded.state',(kind,str(name).strip(),json.dumps(state)))

def presets(kind):return [(r[0],json.loads(r[1])) for r in connection.execute('SELECT name,state FROM filter_presets WHERE kind=? ORDER BY name COLLATE NOCASE',(kind,))]

def missing_fields(kind,row):
    required=['cover_path','description','release_year']
    if kind=='cds':required+=['artist']
    if kind=='books':required+=['author']
    missing=[f for f in required if not str(row.get(f) or '').strip()]
    for role in ('cover_path','background_path'):
        path=row.get(role)
        if path and not str(path).startswith(('http://','https://')):
            path=Path(path);path=path if path.is_absolute() else PROJECT_ROOT/path
            if not path.is_file() and role not in missing:missing.append(role)
    if not row.get('background_path'):missing.append('background_path')
    return missing

def sessions(kind,ids):
    if kind not in SESSIONS:return []
    table,foreign,_=SESSIONS[kind];ids=set(map(int,ids));result=[]
    cur=connection.execute('SELECT * FROM '+table+' ORDER BY started_at DESC,id DESC')
    for row in cur:
        values=dict(zip([d[0] for d in cur.description],row))
        if values[foreign] in ids:result.append(values)
    return result

def correct_session(kind,session_id,started,duration,note,expected):
    from utils import parse_time
    if kind not in SESSIONS:raise ValueError('This section has no timed session records.')
    table,foreign,total_field=SESSIONS[kind]
    seconds=round(parse_time(str(duration))*3600)
    if seconds<0 or seconds>31536000:raise ValueError('Duration must be between zero and one year.')
    start=datetime.fromisoformat(str(started).replace('Z','+00:00'))
    if start.tzinfo is None:raise ValueError('Include the timezone offset, for example +01:00 or Z.')
    start=start.astimezone(timezone.utc)
    end=start+timedelta(seconds=seconds)
    with connection:
        cur=connection.execute('SELECT * FROM '+table+' WHERE id=?',(session_id,));old=cur.fetchone()
        if old is None:raise ValueError('Session was removed.')
        row=dict(zip([d[0] for d in cur.description],old))
        if row!=expected:raise ValueError('Session changed since review. Reload before saving.')
        item=selected(kind,[row[foreign]])[0]
        total=(item.get(total_field) or 0)+(seconds-row['duration_seconds'])/3600
        if total<-1e-8:raise ValueError('Correction would make the tracked total negative. Review existing time first.')
        if kind=='cds' and row['source']=='track listen':
            plays=connection.execute('SELECT id FROM cd_track_plays WHERE session_id=?',(row['id'],)).fetchall()
            if not plays:plays=connection.execute('SELECT id FROM cd_track_plays WHERE cd_id=? AND played_at=? AND duration_seconds=? AND session_id IS NULL',(row[foreign],row['started_at'],row['duration_seconds'])).fetchall()
            if len(plays)!=1:raise ValueError('This track session cannot be matched uniquely to its track history. Nothing was changed.')
            connection.execute('UPDATE cd_track_plays SET played_at=?,duration_seconds=?,session_id=? WHERE id=?',(start.isoformat(),seconds,row['id'],plays[0][0]))
        connection.execute('UPDATE '+table+' SET started_at=?,ended_at=?,duration_seconds=?,note=? WHERE id=?',(start.isoformat(),end.isoformat(),seconds,str(note),session_id))
        connection.execute('UPDATE '+kind+' SET '+total_field+'=? WHERE id=?',(max(0,total),row[foreign]))
    return seconds
