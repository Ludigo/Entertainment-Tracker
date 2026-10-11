"""Collection fields, edition-aware actions and exports; never touch credentials."""
import csv
import os
import tempfile
import unicodedata
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from database import connection
from theme import PANEL, PANEL_ALT, TEXT, MUTED

KINDS=('games','movies','shows','books','cds')
COMMON_FIELDS=[('estimated_value','Estimated value (£)','money'),('wishlist','On wishlist','bool'),('tags','Tags (comma-separated)','text'),
               ('purchase_date','Purchase date (YYYY-MM-DD)','date'),
               ('purchase_shop','Shop / seller','text'),('condition','Condition','text')]


def has_tag(value,tag):
    return int(str(tag).casefold() in [part.strip().casefold() for part in str(value or '').split(',')])

connection.create_function('collection_has_tag',2,has_tag,deterministic=True)

def migrate():
    for kind in KINDS:
        columns={r[1] for r in connection.execute('PRAGMA table_info('+kind+')')}
        for field,declaration in [('wishlist','INTEGER NOT NULL DEFAULT 0'),('tags','TEXT'),
                                  ('purchase_date','TEXT'),('purchase_shop','TEXT'),('condition','TEXT'),('barcode','TEXT')]:
            if field not in columns:connection.execute(f'ALTER TABLE {kind} ADD COLUMN {field} {declaration}')
    connection.execute('CREATE TABLE IF NOT EXISTS cd_track_plays ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, cd_id INTEGER NOT NULL, '
        'disc INTEGER NOT NULL, track INTEGER NOT NULL, title TEXT NOT NULL, '
        'duration_seconds INTEGER NOT NULL, played_at TEXT NOT NULL)')


def normalise_tags(value):
    tags=[];seen=set()
    for part in str(value or '').replace('\n',',').split(','):
        tag=' '.join(unicodedata.normalize('NFKC',part).split())
        if tag and tag.casefold() not in seen:tags.append(tag);seen.add(tag.casefold())
    return ', '.join(tags) or None


def tag_choices(kind):
    if kind not in KINDS:raise ValueError('Unknown category')
    tags={}
    for row in connection.execute('SELECT tags FROM '+kind+' WHERE tags IS NOT NULL'):
        for tag in row[0].split(','):
            if tag.strip():tags.setdefault(tag.strip().casefold(),tag.strip())
    return sorted(tags.values(),key=str.casefold)


def expand_ids(kind, ids):
    ids=list(dict.fromkeys(int(i) for i in ids))
    if kind=='shows':
        from show_series import seasons
        return list(dict.fromkeys(row['id'] for ident in ids for row in seasons(ident)))
    if kind=='cds':
        from cd_series import editions
        return list(dict.fromkeys(row['id'] for ident in ids for row in editions(ident)))
    return ids


def quick_update(kind,item_id,field,value):
    if kind not in KINDS or field not in ('owned_physical','owned_digital','wishlist','completed'):
        raise ValueError('Invalid quick action')
    if field=='completed' and kind=='cds':raise ValueError('Albums use play counts rather than completion flags')
    if value not in (0,1):raise ValueError('Choose selected or unselected')
    with connection:
        if kind=='movies' and field=='completed':
            result=connection.execute('UPDATE movies SET completed=?,watch_count=CASE WHEN ?=1 THEN MAX(watch_count,1) ELSE 0 END WHERE id=?',(value,value,item_id))
        else:
            result=connection.execute(f'UPDATE {kind} SET {field}=? WHERE id=?',(value,item_id))
        if result.rowcount!=1:raise ValueError('This item no longer exists')


def export_rows(kind, ids, destination):
    if kind not in KINDS:raise ValueError('Unknown category')
    ids=expand_ids(kind,ids)
    columns=[r[1] for r in connection.execute('PRAGMA table_info('+kind+')') if r[1] not in ('cover_path','background_path','executable')]
    rows=[]
    for ident in ids:
        row=connection.execute(f'SELECT {",".join(columns)} FROM {kind} WHERE id=?',(ident,)).fetchone()
        if row:rows.append(row)
    destination=Path(destination);temporary=None
    def cell(value):
        # Prevent spreadsheet formulas in user/provider text. Numeric values stay numeric.
        if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):return "'"+value
        return value
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8-sig',newline='',dir=destination.parent,delete=False) as handle:
            temporary=Path(handle.name);writer=csv.writer(handle);writer.writerow(columns)
            writer.writerows([[cell(value) for value in row] for row in rows])
        os.replace(temporary,destination)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    return len(rows)


def choose_record(parent,kind,ids,on_choose):
    records=expand_ids(kind,ids)
    if not records:messagebox.showinfo('Select item','Select an item in List view, or right-click a cover.',parent=parent);return
    if len(records)==1:return on_choose(records[0])
    from window_style import install
    win=tk.Toplevel(parent);install(win);win.title('Choose '+('Edition' if kind=='cds' else 'Season' if kind=='shows' else 'Item'))
    win.geometry('560x210');win.configure(bg=PANEL);win.transient(parent.winfo_toplevel());previous=win.grab_current();win.grab_set()
    labels=[]
    for ident in records:
        cursor=connection.execute('SELECT * FROM '+kind+' WHERE id=?',(ident,));row=dict(zip([d[0] for d in cursor.description],cursor.fetchone()))
        labels.append(f"#{ident} · {row['name']}"+(' · Season '+str(row['season']) if kind=='shows' else ' · '+str(row.get('release_year') or 'Year unknown')+' · '+str(row.get('label') or '')+' · '+str(row.get('barcode') or '') if kind=='cds' else ''))
    tk.Label(win,text='Choose the specific record to update. Other editions and seasons are retained.',bg=PANEL,fg=TEXT,wraplength=520).pack(padx=18,pady=16)
    box=ttk.Combobox(win,values=labels,state='readonly');box.pack(fill='x',padx=18);box.current(0)
    def close():
        win.destroy()
        if previous is not None and previous.winfo_exists():previous.grab_set()
    def apply():
        index=box.current()
        if index<0:return
        ident=records[index];close();on_choose(ident)
    tk.Button(win,text='Continue',command=apply,bg=PANEL_ALT,fg=TEXT,pady=8).pack(side='right',padx=18,pady=18)
    tk.Button(win,text='Cancel',command=close,bg=PANEL_ALT,fg=TEXT,pady=8).pack(side='right')
    win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',lambda e:close())


def install_tools(parent,kind,get_ids,get_selected,refresh,grid=None):
    tools=tk.Frame(parent,bg=PANEL);tools.pack(fill='x',padx=20,pady=5)
    status=tk.StringVar(value='Quick actions apply to one edition/season. Export includes every record in the visible listings.')
    def export():
        ids=get_ids()
        if not ids:messagebox.showinfo('Nothing to export','No items match the current filters.',parent=parent);return
        path=filedialog.asksaveasfilename(parent=parent,title='Export filtered collection',defaultextension='.csv',initialfile=kind+'_filtered.csv',filetypes=[('CSV','*.csv')])
        if not path:return
        try:count=export_rows(kind,ids,path)
        except Exception as exc:messagebox.showerror('Export failed',str(exc),parent=parent);return
        status.set(f'{count} records exported successfully.')
    def menu_for(ident,x=None,y=None):
        row=connection.execute(f'SELECT owned_physical,owned_digital,wishlist'+(',watch_count>0' if kind=='movies' else ',completed' if kind!='cds' else '')+f' FROM {kind} WHERE id=?',(ident,)).fetchone()
        if not row:return
        menu=tk.Menu(parent,tearoff=False)
        def apply(field,value):
            try:quick_update(kind,ident,field,value);refresh();status.set('Quick action saved for record #'+str(ident)+'.')
            except Exception as exc:messagebox.showerror('Could not save',str(exc),parent=parent)
        for index,(field,label) in enumerate([('owned_physical','Physical ownership'),('owned_digital','Digital ownership'),('wishlist','Wishlist')]+([('completed','Watched' if kind=='movies' else 'Completed')] if kind!='cds' else [])):
            menu.add_command(label=('Unmark ' if row[index] else 'Mark ')+label,command=lambda f=field,v=int(not row[index]):apply(f,v))
        menu.add_separator()
        def metadata():
            from rich_details import open_rich_editor
            from database import get_setting
            open_rich_editor(parent,kind,ident,get_setting('accent_color','#B23A48'),refresh)
        menu.add_command(label='Edit tags & purchase details…',command=metadata)
        try:menu.tk_popup(x if x is not None else parent.winfo_pointerx(),y if y is not None else parent.winfo_pointery())
        finally:menu.grab_release()
    tk.Button(tools,text='Quick Actions ▾',command=lambda:choose_record(parent,kind,get_selected(),menu_for),bg=PANEL_ALT,fg=TEXT,relief='flat',pady=7,padx=12).pack(side='left')
    def workspace():
        from collection_manager import open_workspace
        open_workspace(parent,kind,get_ids(),refresh)
    tk.Button(tools,text='Collection Tools…',command=workspace,bg=PANEL_ALT,fg=TEXT,relief='flat',pady=7,padx=12).pack(side='left',padx=5)
    tk.Button(tools,text='Export Filtered CSV…',command=export,bg=PANEL_ALT,fg=TEXT,relief='flat',pady=7,padx=12).pack(side='right')
    tk.Label(tools,textvariable=status,bg=PANEL,fg=MUTED,wraplength=460,justify='left').pack(side='left',padx=12)
    if grid is not None:grid.quick_actions=lambda ident,x,y:choose_record(parent,kind,[ident],lambda chosen:menu_for(chosen,x,y))
    return tools
