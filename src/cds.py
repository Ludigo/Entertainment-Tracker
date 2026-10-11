"""CD and digital album collection, tracklists and listening activity."""
import math
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from database import connection, get_setting, set_setting
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED, BORDER
from utils import format_time, parse_time
from form_safety import SafeFormModal
from cover_grid import CoverGrid

FIELDS = [('name', 'Album title'), ('artist', 'Artist'), ('release_year', 'Release year'),
          ('genre', 'Genre'), ('label', 'Label'), ('barcode', 'Barcode'), ('disc_count', 'Disc count'),
          ('price_paid', 'Price paid (£)'), ('listening_time', 'Listening time (H:MM:SS)'),
          ('play_count', 'Full album plays'), ('description', 'Description'), ('notes', 'Notes')]


def record(item_id):
    cur = connection.execute('SELECT * FROM cds WHERE id=?', (item_id,))
    row = cur.fetchone()
    return dict(zip([x[0] for x in cur.description], row)) if row else None


def tracks_for(item_id):
    return [dict(zip(('disc', 'track', 'name', 'duration_seconds'), r)) for r in
            connection.execute('SELECT disc,track,name,duration_seconds FROM cd_tracks WHERE cd_id=? ORDER BY disc,track', (item_id,))]


def track_text(tracks):
    return '\n'.join(f"{t['disc']} | {t['track']} | {t['name']} | " +
                     (format_time(t['duration_seconds'] / 3600) if t['duration_seconds'] is not None else '')
                     for t in tracks)


def parse_tracks(text, discs):
    result, seen = [], set()
    for index, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split('|', 2)
        bits = [x.strip() for x in parts[:2] + parts[2].rsplit('|', 1)] if len(parts) == 3 else []
        if len(bits) != 4:
            raise ValueError(f'Track line {index}: use Disc | Track | Title | H:MM:SS (duration can be blank).')
        try:
            disc, number = int(bits[0]), int(bits[1])
            seconds = round(parse_time(bits[3]) * 3600) if bits[3] else None
        except (ValueError,OverflowError):
            raise ValueError(f'Track line {index}: invalid disc, track number or duration.')
        if not 1 <= disc <= min(discs,9223372036854775807) or not 1 <= number <= 9223372036854775807 or not bits[2] or (disc, number) in seen:
            raise ValueError(f'Track line {index}: check disc count, title and unique positive track numbers.')
        seen.add((disc, number))
        result.append({'disc': disc, 'track': number, 'name': bits[2], 'duration_seconds': seconds})
    return result


def validate(raw, text):
    from rich_details import FIELDS as FORM_FIELDS, parse_values
    values=parse_values('cds',{k:raw.get(k,0 if typ=='bool' else '') for k,_,typ in FORM_FIELDS['cds']})
    return values,parse_tracks(text,values['disc_count'])


def save_album(values, tracks, item_id=None, artwork=None, expected=None):
    from cd_storage import save_album as commit
    return commit(values,tracks,item_id,artwork,expected)


def log_album_play(item_id):
    row = record(item_id)
    if not row:
        raise ValueError('This album no longer exists.')
    tracks = tracks_for(item_id)
    if not tracks or any(t['duration_seconds'] is None for t in tracks):
        raise ValueError('Enter every track duration before logging a timed full-album play. You can edit play count separately.')
    seconds = sum(t['duration_seconds'] for t in tracks)
    from manual_timer import stamp
    end = stamp()
    with connection:
        connection.execute('UPDATE cds SET play_count=play_count+1,listening_time=listening_time+? WHERE id=?', (seconds / 3600,item_id))
        connection.execute('INSERT INTO cd_sessions (cd_id,started_at,ended_at,duration_seconds,source,note) VALUES (?,?,?,?,?,?)',
                           (item_id,end,end,seconds,'album play','Full album play logged from track durations'))
    return seconds


def delete_album(item_id, timer=None):
    if timer and timer.kind == 'cds' and timer.item_id == item_id:
        raise ValueError('Stop and save this album’s timer before deleting it.')
    with connection:
        connection.execute('DELETE FROM cd_track_plays WHERE cd_id=?', (item_id,))
        connection.execute('DELETE FROM cd_tracks WHERE cd_id=?', (item_id,))
        connection.execute('DELETE FROM cd_sessions WHERE cd_id=?', (item_id,))
        connection.execute("DELETE FROM artwork_library WHERE category='cds' AND item_id=?", (item_id,))
        connection.execute('DELETE FROM cds WHERE id=?', (item_id,))


def open_editor(parent, accent, on_saved, item_id=None, initial=None, initial_tracks=None):
    from cd_editor import open_editor as editor
    return editor(parent,accent,on_saved,item_id,initial,initial_tracks)


def open_cds(parent, accent, on_open_detail=None, restore_library=False):
    page=tk.Frame(parent,bg=BG);page.pack(fill='both',expand=True)
    tk.Label(page,text='CDs & Albums Library',font=('Arial',20),bg=BG,fg=TEXT).pack(pady=15)
    bar=tk.Frame(page,bg=PANEL,highlightbackground=BORDER,highlightthickness=1);bar.pack(fill='x',padx=20,pady=5)
    query=tk.StringVar();mode=tk.StringVar(value=get_setting('view_cds','Covers'))
    tk.Label(bar,text='Search:',font=('Arial',11),bg=PANEL,fg=MUTED).pack(side='left')
    search_adapter=tk.Entry(bar,textvariable=query,width=35,font=('Arial',11),bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT,relief='flat',highlightthickness=0)
    search_adapter.pack(side='left',padx=10)
    tk.Button(bar,text='Search',command=lambda:refresh(),bg=PANEL_ALT,fg=TEXT,relief='flat').pack(side='left',padx=4)
    tk.Button(bar,text='Show All',command=lambda:query.set(''),bg=PANEL_ALT,fg=TEXT,relief='flat').pack(side='left',padx=4)
    from library_filters import build_filters
    import library_filters
    filters=build_filters(page,'cds',lambda:refresh())
    ownership=filters['status'];sort=filters['sort']
    listing=tk.Frame(page,bg=BG)
    table=ttk.Treeview(listing,columns=('ID','Album','Artist','Year','Ownership','Plays','Listening'),show='headings')
    for name in table['columns']:table.heading(name,text=name);table.column(name,width=150)
    table.column('ID',width=0,stretch=False)
    table.configure(displaycolumns=('Album','Artist','Year','Ownership','Plays','Listening'))
    scrollbar=ttk.Scrollbar(listing,orient='vertical',command=table.yview);scrollbar.pack(side='right',fill='y');table.configure(yscrollcommand=scrollbar.set);table.pack(fill='both',expand=True)
    grid=CoverGrid(page,'cds',lambda ident:detail(ident))
    summary=tk.Label(page,bg=BG,fg=MUTED);summary.pack(side='bottom',anchor='w',padx=20,pady=8)
    def refresh():
        library_filters.refresh_choices('cds',filters)
        for child in table.get_children():table.delete(child)
        condition={'All':'1','Physical':'owned_physical=1','Digital':'owned_digital=1','Both':'owned_physical=1 AND owned_digital=1','Not owned':'owned_physical=0 AND owned_digital=0'}[ownership.get()]
        ordering={'Title':'name COLLATE NOCASE','Artist':'artist COLLATE NOCASE,name COLLATE NOCASE','Year':'release_year DESC,name COLLATE NOCASE','Most played':'play_count DESC,name COLLATE NOCASE','Listening time':'listening_time DESC,name COLLATE NOCASE'}[sort.get()]
        from library_filters import where_clause
        extra_query,params,_=where_clause('cds','',filters)
        cur=connection.execute('SELECT id,name,artist,release_year,owned_physical,owned_digital,play_count,listening_time FROM cds WHERE (name LIKE ? OR artist LIKE ? OR barcode LIKE ?) AND '+condition+' AND '+extra_query+' ORDER BY '+ordering,tuple('%'+query.get()+'%' for _ in range(3))+tuple(params))
        rows=cur.fetchall()
        from cd_series import groups
        listings=groups([r[0] for r in rows])
        ids={g['id'] for g in listings}
        for r in rows:
            if r[0] not in ids:continue
            table.insert('','end',iid=str(r[0]),values=(r[0],r[1],r[2] or '',r[3] or '', 'Both' if r[4] and r[5] else 'Physical' if r[4] else 'Digital' if r[5] else 'Not owned',r[6],format_time(r[7])))
        summary.configure(text=f'{len(listings)} albums · {len(rows)} matching editions • {sum(r[6] for r in rows)} full album plays • {format_time(sum(r[7] for r in rows))} listened')
        filters['count'].configure(text=f'{len(listings)} album listings · {len(rows)} matching editions. Open a listing to choose another edition.')
        if mode.get()=='Covers':grid.set_search('',filtered_ids=[r[0] for r in rows])
    def update_toggle():
        for label,button in toggle_buttons.items():
            button.configure(bg=accent if label==mode.get() else PANEL_ALT,fg='white' if label==mode.get() else MUTED,activebackground=accent if label==mode.get() else BORDER,activeforeground='white',font=('Arial',10,'bold' if label==mode.get() else 'normal'))
    def switch(value):
        mode.set(value);set_setting('view_cds',value)
        update_toggle()
        listing.pack_forget();grid.pack_forget()
        (grid if value=='Covers' else listing).pack(fill='both',expand=True,padx=12,pady=10);refresh()
    def edit(ident=None):
        open_editor(page,accent,lambda new_id:refresh(),ident)
    add_button=tk.Button(bar,text='Add Album',command=lambda:edit(),bg=PANEL_ALT,fg=TEXT,relief='flat')
    add_button.pack(side='right',padx=4)
    def edit_selected():
        selected=table.selection()
        if selected:
            from collection_tools import choose_record
            choose_record(page,'cds',[int(selected[0])],edit)
    tk.Button(bar,text='Edit Album',command=edit_selected,bg=PANEL_ALT,fg=TEXT,relief='flat').pack(side='right',padx=4)
    toggle_buttons={}
    view_tools=tk.Frame(bar,bg=PANEL);view_tools.pack(side='right',before=add_button,padx=(8,0))
    for label in ('List','Covers'):
        button=tk.Button(view_tools,text='☷  List' if label=='List' else '▦  Covers',command=lambda value=label:switch(value),relief='flat',bd=0,cursor='hand2',width=9 if label=='List' else 11)
        button.pack(side='left',padx=2,pady=2);toggle_buttons[label]=button
        button._et_hover_installed=True
        button.bind('<Enter>',lambda e,b=button:b.configure(bg=accent,fg='white'))
        button.bind('<Leave>',lambda e:update_toggle())
    query.trace_add('write',lambda *args:refresh())
    def double(event):
        ident=table.identify_row(event.y)
        if ident and table.identify_region(event.x,event.y)=='cell':detail(int(ident))
    table.bind('<Double-1>',double)
    def detail(ident):
        if on_open_detail:on_open_detail(ident)
        else:open_detail(page,ident,accent,refresh)
    from collection_tools import install_tools
    collection_tools_bar=install_tools(page,'cds',lambda:[int(r) for r in table.get_children()],lambda:[int(r) for r in table.selection()],refresh,grid)
    from library_header import polish
    polish(page,bar,collection_tools_bar,'cds',mode)
    switch(mode.get())
    page.after_idle(update_toggle)
    from library_return import install
    from search_shortcuts import bind_enter
    bind_enter(search_adapter,refresh)
    filter_adapter={'status':ownership,'sort':sort,'extra':filters['extra']}
    on_open_detail=install(page,'cds',on_open_detail,grid,table,search_adapter,mode,switch,
                           lambda search='':refresh(),filter_adapter,restore=restore_library)
    return page


def open_detail(parent, item_id, accent, refresh):
    from details import show_detail
    return show_detail(parent,'cds',item_id,accent,refresh)
