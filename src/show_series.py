"""One library listing per saved show title; season rows remain independent."""
from database import connection


def title_key(title):
    return ' '.join(str(title or '').split()).casefold()


def all_records():
    columns=[r[1] for r in connection.execute('PRAGMA table_info(shows)')]
    return [dict(zip(columns,row)) for row in connection.execute('SELECT * FROM shows ORDER BY season,id')]


def seasons(item_id):
    rows=all_records();record=next((r for r in rows if r['id']==int(item_id)),None)
    if record is None:return []
    key=title_key(record['name'])
    return [r for r in rows if title_key(r['name'])==key]


def groups(ordered_ids=None):
    rows=all_records();by_id={r['id']:r for r in rows};by_title={}
    for r in rows:by_title.setdefault(title_key(r['name']),[]).append(r)
    order=list(by_id) if ordered_ids is None else list(ordered_ids)
    result=[];seen=set()
    for ident in order:
        r=by_id.get(ident)
        if not r:continue
        key=title_key(r['name'])
        if key in seen:continue
        seen.add(key);members=by_title[key]
        result.append({'id':ident,'name':r['name'],'cover_path':r.get('cover_path') or next((m['cover_path'] for m in members if m.get('cover_path')),None),'members':members})
    return result


def season_labels(records):
    counts={}
    for r in records:counts[r['season']]=counts.get(r['season'],0)+1
    return [('Specials' if r['season']==0 else f'Season {r["season"]}')+
            (f' · copy #{r["id"]}' if counts[r['season']]>1 else '') for r in records]


def totals(records):
    runtime=sum(r.get('runtime') or 0 for r in records)
    watched=sum((r.get('runtime') or 0)*(r.get('watch_count') or 0)+
                ((r.get('runtime') or 0)*(r.get('episode_reached') or 0)/r['episode_count'] if r.get('episode_count') else 0) for r in records)
    return {'runtime':runtime,'watched':watched,'episodes':sum(r.get('episode_count') or 0 for r in records),
            'reached':sum(r.get('episode_reached') or 0 for r in records),
            'completed':all(r.get('completed') for r in records),
            'in_progress':any(r.get('in_progress') for r in records),
            'owned':all(r.get('owned') for r in records),
            'seasons':len({r['season'] for r in records})}


def matches_status(records,status):
    if status=='Completed':return all(r.get('completed') for r in records)
    if status=='Watching':return any(r.get('in_progress') for r in records)
    if status=='Not started':return all(not r.get('in_progress') and not r.get('completed') for r in records)
    return True


def choose_season(parent,item_id,accent,on_choose):
    records=seasons(item_id)
    if not records:return
    if len(records)==1:return on_choose(records[0]['id'])
    import tkinter as tk
    from tkinter import ttk
    from theme import PANEL,PANEL_ALT,TEXT
    from window_style import install
    win=tk.Toplevel(parent);install(win);win.title('Choose Season to Edit')
    win.geometry('440x190');win.configure(bg=PANEL);win.transient(parent.winfo_toplevel())
    previous=win.grab_current();win.grab_set()
    def close(event=None):
        win.destroy()
        if previous is not None and previous.winfo_exists():previous.grab_set()
        return 'break'
    tk.Label(win,text=records[0]['name'],bg=PANEL,fg=TEXT,wraplength=400).pack(padx=18,pady=16)
    combo=ttk.Combobox(win,state='readonly',values=season_labels(records));combo.pack(fill='x',padx=18);combo.current(0)
    def edit():
        index=combo.current()
        if index<0:return
        ident=records[index]['id'];close();on_choose(ident)
    tk.Button(win,text='Edit Season Metadata',command=edit,bg=accent,fg='white',relief='flat',pady=8).pack(side='right',padx=18,pady=18)
    tk.Button(win,text='Cancel',command=close,bg=PANEL_ALT,fg=TEXT,relief='flat',pady=8).pack(side='right')
    win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',close)
