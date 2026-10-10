"""All saved listening sessions, displayed in local time."""
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from database import connection
from theme import BG, PANEL, TEXT, MUTED
from utils import format_time
from window_style import install


def open_history(parent,item_id,title,accent):
    win=tk.Toplevel(parent);install(win);win.title('Listening History — '+title);win.geometry('860x540');win.configure(bg=BG)
    tk.Label(win,text='LISTENING HISTORY',bg=BG,fg=accent,font=('Arial',16,'bold')).pack(anchor='w',padx=18,pady=(18,4))
    tk.Label(win,text=title,bg=BG,fg=TEXT,font=('Arial',12,'bold')).pack(anchor='w',padx=18)
    rows=connection.execute('SELECT started_at,duration_seconds,source,note FROM cd_sessions WHERE cd_id=? ORDER BY id DESC',(item_id,)).fetchall()
    tk.Label(win,text=f'{len(rows)} saved sessions · {format_time(sum(r[1] for r in rows)/3600)} recorded in sessions',bg=BG,fg=MUTED).pack(anchor='w',padx=18,pady=8)
    area=tk.Frame(win,bg=BG);area.pack(fill='both',expand=True,padx=18,pady=(0,18))
    table=ttk.Treeview(area,columns=('Date','Duration','Source','Note'),show='headings')
    for key in table['columns']:table.heading(key,text=key);table.column(key,width=160 if key!='Note' else 260)
    scroll=ttk.Scrollbar(area,command=table.yview);scroll.pack(side='right',fill='y');table.configure(yscrollcommand=scroll.set);table.pack(fill='both',expand=True)
    for started,seconds,source,note in rows:
        try:when=datetime.fromisoformat(started).astimezone().strftime('%d %b %Y %H:%M')
        except ValueError:when=str(started)
        table.insert('','end',values=(when,format_time(seconds/3600),source,note))
    return win
