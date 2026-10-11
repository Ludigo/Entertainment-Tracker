"""Track listens retain a snapshot and never increment full-album play count."""
import math
from database import connection

def log_track(item_id,disc,track,seconds=None,timer=None):
    if timer and timer.kind=='cds' and timer.item_id==item_id:
        raise ValueError('Stop and save this album’s timer before logging a track.')
    row=connection.execute('SELECT name,duration_seconds FROM cd_tracks WHERE cd_id=? AND disc=? AND track=?',(item_id,disc,track)).fetchone()
    if not row:raise ValueError('This track no longer exists.')
    duration=row[1] if seconds is None else seconds
    if duration is None or isinstance(duration,bool) or not math.isfinite(duration) or duration<=0 or duration>9223372036854775807:
        raise ValueError('Enter a positive track duration before logging this listen.')
    duration=round(duration)
    if duration<=0:raise ValueError('Duration must be at least one second.')
    from manual_timer import stamp
    end=stamp()
    with connection:
        cur=connection.execute('UPDATE cds SET listening_time=listening_time+? WHERE id=?',(duration/3600,item_id))
        if cur.rowcount!=1:raise ValueError('This album no longer exists.')
        connection.execute('INSERT INTO cd_track_plays(cd_id,disc,track,title,duration_seconds,played_at) VALUES(?,?,?,?,?,?)',(item_id,disc,track,row[0],duration,end))
        connection.execute('INSERT INTO cd_sessions(cd_id,started_at,ended_at,duration_seconds,source,note) VALUES(?,?,?,?,?,?)',(item_id,end,end,duration,'track listen',f'Disc {disc}, track {track}: {row[0]}'))
    return duration

def open_track_listening(parent,item_id,accent,on_saved,timer=None):
    import tkinter as tk
    from tkinter import ttk,messagebox
    from theme import PANEL,PANEL_ALT,TEXT
    from utils import format_time,parse_time
    from window_style import install
    rows=connection.execute('SELECT disc,track,name,duration_seconds FROM cd_tracks WHERE cd_id=? ORDER BY disc,track',(item_id,)).fetchall()
    if not rows:messagebox.showinfo('Track listening','Add a tracklist in Edit Album Metadata first.',parent=parent);return
    win=tk.Toplevel(parent);install(win);win.title('Log Track Listen');win.geometry('600x300');win.configure(bg=PANEL);win.transient(parent.winfo_toplevel());previous=win.grab_current();win.grab_set()
    tk.Label(win,text='Log one track listen. Full-album plays stay unchanged.',bg=PANEL,fg=TEXT).pack(padx=18,pady=18)
    counts={(r[0],r[1]):r[2] for r in connection.execute('SELECT disc,track,COUNT(*) FROM cd_track_plays WHERE cd_id=? GROUP BY disc,track',(item_id,))}
    box=ttk.Combobox(win,state='readonly',values=[f'{r[0]}.{r[1]} · {r[2]} · {counts.get((r[0],r[1]),0)} listens' for r in rows]);box.pack(fill='x',padx=18)
    duration=tk.StringVar();tk.Label(win,text='Duration listened (H:MM:SS)',bg=PANEL,fg=TEXT).pack(anchor='w',padx=18,pady=(18,4));tk.Entry(win,textvariable=duration).pack(fill='x',padx=18)
    def choose(event=None):
        r=rows[box.current()];duration.set(format_time(r[3]/3600) if r[3] is not None else '')
    box.bind('<<ComboboxSelected>>',choose);box.current(0);choose()
    def close():
        win.destroy()
        if previous is not None and previous.winfo_exists():previous.grab_set()
    def save():
        try:
            r=rows[box.current()];log_track(item_id,r[0],r[1],parse_time(duration.get())*3600,timer)
        except (ValueError,OverflowError) as exc:messagebox.showwarning('Track listening',str(exc),parent=win);return
        close();on_saved()
    tk.Button(win,text='Log Listen',command=save,bg=accent,fg='white',relief='flat',pady=8).pack(side='right',padx=18,pady=18)
    tk.Button(win,text='Cancel',command=close,bg=PANEL_ALT,fg=TEXT,relief='flat',pady=8).pack(side='right')
    win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',lambda e:close())
