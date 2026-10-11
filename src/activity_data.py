"""In-window collection activity, with transactional progress and dated goals."""
from datetime import datetime
import random
import math
from database import connection
from collection_visibility import visible_sections, SECTIONS
from utils import format_time

KINDS=tuple(SECTIONS)
PROGRESS={
    'games':('completed','in_progress','backlog','started'),
    'movies':('completed','in_progress','watch_count'),
    'shows':('completed','in_progress','watch_count','episode_reached'),
    'books':('completed','in_progress','read_count','page_reached'),
}
GOALS={'games':'Games completed','shows':'Episodes watched','books':'Books completed'}


def migrate():
    connection.execute('''CREATE TABLE IF NOT EXISTS activity_goal_events (
        id INTEGER PRIMARY KEY, kind TEXT NOT NULL, item_id INTEGER NOT NULL,
        amount INTEGER NOT NULL, happened_at TEXT NOT NULL DEFAULT (datetime('now','localtime')))''')
    connection.execute('''CREATE TABLE IF NOT EXISTS activity_monthly_goals (
        month TEXT NOT NULL,kind TEXT NOT NULL,target INTEGER NOT NULL,
        PRIMARY KEY(month,kind))''')
    for kind in KINDS:
        if 'added_at' not in {r[1] for r in connection.execute(f'PRAGMA table_info({kind})')}:
            connection.execute(f'ALTER TABLE {kind} ADD COLUMN added_at TEXT')
        connection.execute(f'''CREATE TRIGGER IF NOT EXISTS activity_added_{kind}
            AFTER INSERT ON {kind} WHEN NEW.added_at IS NULL
            BEGIN UPDATE {kind} SET added_at=datetime('now','localtime') WHERE id=NEW.id; END''')
    for kind in ('games','books'):
        connection.execute(f'''CREATE TRIGGER IF NOT EXISTS activity_complete_{kind}
            AFTER UPDATE OF completed ON {kind}
            WHEN NEW.completed=1 AND COALESCE(OLD.completed,0)=0
            BEGIN INSERT INTO activity_goal_events(kind,item_id,amount)
                VALUES('{kind}',NEW.id,1); END''')
    def viewed(prefix):
        return f'''(CASE WHEN COALESCE({prefix}.watch_count,0)>0
            THEN {prefix}.watch_count*COALESCE({prefix}.episode_count,0)+COALESCE({prefix}.episode_reached,0)
            WHEN {prefix}.completed=1 THEN COALESCE({prefix}.episode_count,0)
            ELSE COALESCE({prefix}.episode_reached,0) END)'''
    new,old=viewed('NEW'),viewed('OLD')
    connection.execute(f'''CREATE TRIGGER IF NOT EXISTS activity_episodes
        AFTER UPDATE OF episode_reached,watch_count,completed ON shows
        WHEN NEW.episode_count IS OLD.episode_count AND {new}>{old}
        BEGIN INSERT INTO activity_goal_events(kind,item_id,amount)
            VALUES('shows',NEW.id,{new}-{old}); END''')


def records(kind):
    if kind not in KINDS:raise ValueError('Unknown section')
    cur=connection.execute(f'SELECT * FROM {kind}')
    return [dict(zip([c[0] for c in cur.description],row),kind=kind) for row in cur]


def get_record(kind,ident):
    if kind not in KINDS:raise ValueError('Unknown section')
    cur=connection.execute(f'SELECT * FROM {kind} WHERE id=?',(ident,));row=cur.fetchone()
    if row is None:raise ValueError('This item is no longer in your collection.')
    return dict(zip([c[0] for c in cur.description],row),kind=kind)


def label(record):
    title=record['name']
    if record['kind']=='shows':title+=' · '+('Specials' if record['season']==0 else f"Season {record['season']}")
    if record['kind']=='cds' and record.get('artist'):title+=' · '+record['artist']
    return title


def progress_text(r):
    kind=r['kind']
    if kind=='games':return format_time(r.get('playtime') or 0)+' played'
    if kind=='shows':return f"{r.get('episode_reached') or 0} / {r.get('episode_count') or '?'} episodes · {r.get('watch_count') or 0} full watches"
    if kind=='books':return f"{r.get('page_reached') or 0} / {r.get('page_count') or '?'} pages · {r.get('read_count') or 0} full reads"
    if kind=='movies':return f"{r.get('watch_count') or 0} watches · "+format_time(r.get('runtime') or 0)
    return f"{r.get('play_count') or 0} full plays · "+format_time(r.get('listening_time') or 0)+' listened'


def continue_records():
    rows=[]
    for kind in visible_sections():
        if kind=='cds':continue
        rows.extend(r for r in records(kind) if not r.get('completed') and
                    (r.get('in_progress') or kind=='shows' and r.get('episode_reached') or
                     kind=='books' and r.get('page_reached')))
    return sorted(rows,key=lambda r:(r['name'].casefold(),r.get('season',0),r['id']))


def recent_records(limit=100,kind="All"):
    rows=[r for category in visible_sections() if kind in ("All",category) for r in records(category)]
    return sorted(rows,key=lambda r:(bool(r.get('added_at')),r.get('added_at') or '',r['id']),reverse=True)[:limit]


def duration_minutes(r):
    kind=r['kind']
    if kind=='movies':return (r.get('runtime') or 0)*60 or None
    if kind=='shows':
        if r.get('runtime') and r.get('episode_count'):return r['runtime']*60/r['episode_count']
    if kind=='cds':
        rows=connection.execute('SELECT duration_seconds FROM cd_tracks WHERE cd_id=?',(r['id'],)).fetchall()
        if rows and all(row[0] and row[0]>0 for row in rows):return sum(row[0] for row in rows)/60
    return None


def pick_candidates(kind='All',platform='',genre='',minutes=0,include_unknown=False):
    minutes=float(minutes or 0)
    if not math.isfinite(minutes) or minutes<0:raise ValueError('Available minutes must be a finite number of zero or more.')
    rows=[];seen_shows=set();seen_albums=set()
    for category in visible_sections():
        if kind not in ('All',category):continue
        for r in sorted(records(category),key=lambda r:(r.get('season',0),r['id'])):
            if r.get('wishlist'):continue
            if category=='cds':
                if r.get('play_count'):continue
            elif r.get('completed') or category=='movies' and r.get('watch_count'):continue
            if platform and platform.casefold() not in str(r.get('platform') or '').casefold():continue
            if genre and genre.casefold() not in str(r.get('genre') or '').casefold():continue
            duration=duration_minutes(r)
            if minutes and (duration is None and not include_unknown or duration is not None and duration>minutes):continue
            if category=='shows':
                from show_series import title_key
                key=title_key(r['name'])
                if key in seen_shows:continue
                seen_shows.add(key)
            if category=='cds':
                from cd_series import key as album_key
                key=album_key(r)
                if key in seen_albums:continue
                seen_albums.add(key)
            rows.append(r)
    return rows


def choose_candidate(rows,previous=None):
    if not rows:return None
    alternatives=[r for r in rows if (r['kind'],r['id'])!=previous]
    return random.choice(alternatives or rows)


def quick_progress(kind,ident,action,value=None):
    if kind not in PROGRESS:raise ValueError('Open album details to log listening activity.')
    if kind not in visible_sections():raise ValueError('This collection section is hidden.')
    r=get_record(kind,ident);updates={}
    if action=='start':
        updates=dict(in_progress=1,completed=0)
        if kind=='games':updates['started']=1
        if r.get('completed'):
            if kind=='shows':updates.update(episode_reached=0,watch_count=max(r.get('watch_count') or 0,1))
            if kind=='books':updates.update(page_reached=0,read_count=max(r.get('read_count') or 0,1))
    elif action in ('finish','episode','pages'):
        if r.get('completed') and kind!='movies':raise ValueError('Already completed. Use Start again to begin a new pass.')
        if action=='episode':
            if kind!='shows':raise ValueError('Choose a show season to log an episode.')
            total=r.get('episode_count') or 0
            if total<=0:raise ValueError('Set this season’s episode count in Metadata first.')
            reached=(r.get('episode_reached') or 0)+1
            if reached>total:raise ValueError('Episode progress is already at the season total.')
            updates=dict(episode_reached=reached,in_progress=1)
            if reached==total:action='finish'
        if action=='pages':
            if kind!='books':raise ValueError('Choose a book to update pages.')
            try:reached=int(str(value).strip())
            except (TypeError,ValueError):raise ValueError('Enter a whole page number.')
            total=r.get('page_count') or 0
            if reached<0 or total and reached>total:raise ValueError('Pages must be between zero and the saved page count.')
            updates=dict(page_reached=reached,in_progress=int(reached>0))
            if total and reached==total:action='finish'
        if action=='finish':
            updates=dict(completed=1,in_progress=0)
            if kind=='games':updates.update(started=1,backlog=0)
            if kind=='shows':updates.update(watch_count=(r.get('watch_count') or 0)+1,episode_reached=0)
            if kind=='books':updates.update(read_count=(r.get('read_count') or 0)+1,page_reached=r.get('page_count') or r.get('page_reached'))
            if kind=='movies':updates['watch_count']=(r.get('watch_count') or 0)+1
    else:raise ValueError('Unknown progress action')
    columns=PROGRESS[kind];before={key:r.get(key) for key in columns}
    start=connection.execute('SELECT COALESCE(MAX(id),0) FROM activity_goal_events').fetchone()[0]
    with connection:
        connection.execute(f'UPDATE {kind} SET '+','.join(f'{key}=?' for key in updates)+' WHERE id=?',(*updates.values(),ident))
    after=get_record(kind,ident)
    events=[row[0] for row in connection.execute('SELECT id FROM activity_goal_events WHERE id>?',(start,))]
    return dict(kind=kind,id=ident,before=before,after={key:after.get(key) for key in columns},events=events)


def undo_progress(token):
    kind,ident=token['kind'],token['id'];r=get_record(kind,ident)
    if any(r.get(key)!=value for key,value in token['after'].items()):
        raise ValueError('Progress has changed since this action. Undo is no longer available.')
    start=connection.execute('SELECT COALESCE(MAX(id),0) FROM activity_goal_events').fetchone()[0]
    with connection:
        connection.execute(f'UPDATE {kind} SET '+','.join(f'{key}=?' for key in token['before'])+' WHERE id=?',(*token['before'].values(),ident))
        connection.execute('DELETE FROM activity_goal_events WHERE id>?',(start,))
        for event in token['events']:connection.execute('DELETE FROM activity_goal_events WHERE id=?',(event,))


def month_key():return datetime.now().strftime('%Y-%m')


def goal_rows(month=None):
    month=month or month_key();rows=[]
    for kind in visible_sections():
        if kind not in GOALS:continue
        target=connection.execute('SELECT target FROM activity_monthly_goals WHERE month=? AND kind=?',(month,kind)).fetchone()
        amount=connection.execute('SELECT COALESCE(SUM(amount),0) FROM activity_goal_events WHERE kind=? AND substr(happened_at,1,7)=?',(kind,month)).fetchone()[0]
        rows.append(dict(kind=kind,label=GOALS[kind],target=target[0] if target else 0,amount=amount))
    return rows


def save_goals(values,month=None):
    month=month or month_key();datetime.strptime(month,'%Y-%m')
    clean={}
    for kind,value in values.items():
        if kind not in GOALS:raise ValueError('Invalid goal')
        try:target=int(str(value).strip())
        except (ValueError,TypeError):raise ValueError('Goals must be whole numbers.')
        if not 0<=target<=100000:raise ValueError('Goals must be between 0 and 100,000. Use 0 to disable a target.')
        clean[kind]=target
    with connection:
        for kind,target in clean.items():
            connection.execute('INSERT INTO activity_monthly_goals(month,kind,target) VALUES(?,?,?) ON CONFLICT(month,kind) DO UPDATE SET target=excluded.target',(month,kind,target))
