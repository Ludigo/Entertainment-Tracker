"""Stage an Add Game import for explicit review; save everything atomically."""
import io
import hashlib
import queue
import threading
import uuid
import unicodedata
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from database import connection, PROJECT_ROOT
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED
from window_style import install as polish_dialog
from media_naming import clean_name
from artwork_preferences import import_folder, remember_import_folder
try:
    from PIL import Image, ImageTk, ImageOps
except ImportError:
    Image = ImageTk = ImageOps = None

METADATA_FIELDS = ('release_year','release_date','genre','developer','publisher','game_modes','age_rating')
REVIEW_FIELDS = [('name','Title'),('platform','Platform'),('description','Description'),
                 ('release_year','Release year'),('release_date','Release date'),('genre','Genre'),
                 ('developer','Developer'),('publisher','Publisher'),('game_modes','Game modes'),('age_rating','Age rating')]


def normalise_match(value):
    return ' '.join(unicodedata.normalize('NFKC',str(value or '')).casefold().split())


def find_duplicates(title, platform):
    wanted=(normalise_match(title),normalise_match(platform))
    return [(row[0],row[1],row[2]) for row in connection.execute('SELECT id,name,platform FROM games').fetchall()
            if (normalise_match(row[1]),normalise_match(row[2]))==wanted]


def confirm_duplicate(parent,matches,accent):
    win=tk.Toplevel(parent);polish_dialog(win);win.title('Possible Duplicate Game')
    win.geometry('500x300');win.configure(bg=PANEL);win.transient(parent.winfo_toplevel())
    previous_grab=win.grab_current();result={'add':False}
    tk.Label(win,text='This title and platform already exist',bg=PANEL,fg=TEXT,
             font=('Arial',14,'bold'),wraplength=460).pack(anchor='w',padx=18,pady=(18,8))
    names='\n'.join(f'#{row[0]} · {row[1]} ({row[2]})' for row in matches[:5])
    tk.Label(win,text=names,bg=PANEL,fg=MUTED,wraplength=460,justify='left').pack(anchor='w',padx=18)
    tk.Label(win,text='You can still add an intentional extra copy.',bg=PANEL,fg=TEXT,
             wraplength=460).pack(anchor='w',padx=18,pady=12)
    def finish(add=False):
        result['add']=add;win.destroy()
        if previous_grab is not None:
            try:
                if previous_grab.winfo_exists():previous_grab.grab_set()
            except tk.TclError:pass
    actions=tk.Frame(win,bg=PANEL);actions.pack(side='bottom',fill='x',padx=18,pady=18)
    tk.Button(actions,text='Add Another Copy',command=lambda:finish(True),bg=accent,
              fg='white',relief='flat',padx=12,pady=8).pack(side='right')
    keep=tk.Button(actions,text='Keep Editing',command=finish,bg=PANEL_ALT,fg=TEXT,
                   relief='flat',padx=12,pady=8);keep.pack(side='right',padx=8)
    win.protocol('WM_DELETE_WINDOW',finish);win.bind('<Escape>',lambda event:finish())
    win.grab_set();keep.focus_set();win.wait_window()
    return result['add']


def validated_cover(raw, label, source='Local file'):
    if Image is None:raise ValueError('Install Pillow to preview or import artwork.')
    with Image.open(io.BytesIO(raw)) as image:
        width,height=image.size;fmt=image.format
        if fmt not in ('PNG','JPEG','WEBP','BMP') or width*height>60_000_000:
            raise ValueError('Choose a PNG, JPEG, WebP or BMP image under 60 megapixels.')
        image.verify()
    return dict(raw=raw,w=width,h=height,ext={'PNG':'.png','JPEG':'.jpg','WEBP':'.webp','BMP':'.bmp'}[fmt],label=label,source=source)


def choose_local_cover(parent):
    filename=filedialog.askopenfilename(parent=parent,title='Choose Game Cover',initialdir=import_folder('artwork'),
                                       filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.bmp'),('All files','*.*')])
    if not filename:return None
    try:remember_import_folder('artwork',[filename])
    except Exception:pass
    return validated_cover(Path(filename).read_bytes(),Path(filename).name)


def preview_cover(parent,cover):
    if not cover:return
    win=tk.Toplevel(parent);polish_dialog(win);win.title('Proposed Game Cover')
    win.configure(bg=BG);win.geometry('650x610');win.transient(parent.winfo_toplevel())
    with Image.open(io.BytesIO(cover['raw'])) as image:
        picture=ImageOps.contain(image.convert('RGBA'),(610,520))
    photo=ImageTk.PhotoImage(picture)
    previous_grab=win.grab_current()
    def close(event=None):
        win.destroy()
        if previous_grab is not None:
            try:
                if previous_grab.winfo_exists():previous_grab.grab_set()
            except tk.TclError:pass
        return 'break'
    win.protocol('WM_DELETE_WINDOW',close);win.grab_set()
    label=tk.Label(win,image=photo,bg=BG);label.image=photo;label.pack(fill='both',expand=True,padx=12,pady=12)
    tk.Label(win,text=f"{cover['label']} · {cover['w']} × {cover['h']}",bg=BG,fg=TEXT,wraplength=610).pack()
    tk.Button(win,text='Close',command=close,bg=PANEL_ALT,fg=TEXT,relief='flat').pack(pady=10)
    win.bind('<Escape>',close)


def staged_signature(metadata,cover):
    return tuple(sorted(metadata.items())),hashlib.sha256(cover['raw']).hexdigest() if cover else None


def create_game(values, metadata=None, cover=None):
    """No downloads on Save; reviewed bytes and SQLite changes commit together."""
    metadata=metadata or {};created=None
    if cover:cover=validated_cover(cover['raw'],cover['label'],cover['source'])
    try:
        with connection:
            result=connection.execute('INSERT INTO games (name,platform,playtime,price_paid,completed,backlog,started,description) VALUES (?,?,?,?,?,?,?,?)',values)
            game_id=result.lastrowid
            for field in METADATA_FIELDS:
                value=metadata.get(field)
                if value is not None and str(value).strip():
                    if field=='release_year':value=int(value)
                    connection.execute(f'UPDATE games SET {field}=? WHERE id=?',(value,game_id))
            if cover:
                folder=PROJECT_ROOT/'assets'/'artwork'/'games';folder.mkdir(parents=True,exist_ok=True)
                created=folder/f'{clean_name(values[0])} - Cover - {uuid.uuid4().hex[:12]}{cover["ext"]}'
                created.write_bytes(cover['raw'])
                path=created.relative_to(PROJECT_ROOT).as_posix()
                connection.execute('INSERT INTO artwork_library(category,item_id,image_path,width,height,source) VALUES(?,?,?,?,?,?)',
                                   ('games',game_id,path,cover['w'],cover['h'],cover['source']))
                connection.execute('UPDATE games SET cover_path=? WHERE id=?',(path,game_id))
        return game_id
    except Exception:
        if created:created.unlink(missing_ok=True)
        raise


def open_search(parent,accent,current_values,on_apply):
    """Search existing Steam provider, review choices and stage them in the form."""
    from metadata_finder import search_provider,enrich
    from artwork_manager import fetch
    win=tk.Toplevel(parent);polish_dialog(win);win.title('Add Game — Steam Search and Review')
    win.geometry('980x760');win.minsize(750,590);win.configure(bg=BG)
    win.transient(parent.winfo_toplevel());previous_grab=win.grab_current();win.grab_set()
    state={'closed':False,'generation':0,'item':None,'cover':None,'checks':{},'photo':None,'busy':False}
    messages=queue.Queue()
    def close(event=None):
        state['closed']=True;state['generation']+=1
        if state.get('poll_id'):
            try:win.after_cancel(state['poll_id'])
            except tk.TclError:pass
        win.destroy()
        if previous_grab is not None:
            try:
                if previous_grab.winfo_exists():previous_grab.grab_set()
            except tk.TclError:pass
        return 'break'
    win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',close)
    tk.Label(win,text='Find on Steam → Review → Apply to form',bg=BG,fg=TEXT,font=('Arial',17,'bold')).pack(anchor='w',padx=18,pady=(16,8))
    tk.Label(win,text='Nothing is added until you press Save Game in the Add Game form. Manual entry remains available.',
             bg=BG,fg=MUTED,wraplength=920,justify='left').pack(anchor='w',padx=18)
    toolbar=tk.Frame(win,bg=BG);toolbar.pack(fill='x',padx=18,pady=10)
    query=tk.StringVar(value=current_values().get('name',''))
    entry=tk.Entry(toolbar,textvariable=query,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT,relief='flat')
    entry.pack(side='left',fill='x',expand=True,ipady=6)
    status=tk.StringVar(value='Search by title, then select the correct edition.')
    tk.Label(win,textvariable=status,bg=BG,fg=MUTED,wraplength=920,justify='left').pack(fill='x',padx=18,pady=(0,8))
    results=ttk.Treeview(win,columns=('title','source'),show='headings',height=5,selectmode='browse')
    results.heading('title',text='Game');results.heading('source',text='Source')
    results.column('title',width=680);results.column('source',width=120)
    results.pack(fill='x',padx=18,pady=(0,10));items=[]
    body=tk.Frame(win,bg=BG);body.pack(fill='both',expand=True,padx=18)
    left=tk.Frame(body,bg=PANEL);left.pack(side='left',fill='both',expand=True)
    canvas=tk.Canvas(left,bg=PANEL,highlightthickness=0)
    scrollbar=ttk.Scrollbar(left,command=canvas.yview);scrollbar.pack(side='right',fill='y')
    canvas.configure(yscrollcommand=scrollbar.set);canvas.pack(side='left',fill='both',expand=True)
    fields=tk.Frame(canvas,bg=PANEL);window_id=canvas.create_window(0,0,window=fields,anchor='nw')
    fields.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda event:canvas.itemconfigure(window_id,width=event.width))
    right=tk.Frame(body,bg=PANEL_ALT,width=240);right.pack(side='right',fill='y',padx=(12,0));right.pack_propagate(False)
    tk.Label(right,text='PROPOSED COVER',bg=PANEL_ALT,fg=TEXT).pack(pady=10)
    cover_label=tk.Label(right,text='Select a Steam result.',bg=PANEL_ALT,fg=MUTED,wraplength=215)
    cover_label.pack(fill='both',expand=True,padx=8,pady=6)
    cover_label.bind('<Button-1>',lambda event:preview_cover(win,state['cover']) if state['cover'] else None)
    use_cover=tk.BooleanVar(value=False)
    cover_check=tk.Checkbutton(right,text='Use this cover',variable=use_cover,bg=PANEL_ALT,fg=TEXT,selectcolor=PANEL,state='disabled')
    cover_check.pack(side='bottom',pady=6,before=cover_label)
    def show_cover(cover,selected=False):
        state['cover']=cover;state['photo']=None;use_cover.set(bool(cover and selected))
        cover_check.configure(state='normal' if cover else 'disabled')
        if cover:
            with Image.open(io.BytesIO(cover['raw'])) as image:
                picture=ImageOps.contain(image.convert('RGBA'),(215,260))
            state['photo']=ImageTk.PhotoImage(picture)
            cover_label.configure(image=state['photo'],text='')
        else:cover_label.configure(image='',text='No cover preview available. You can choose a local image or continue without artwork.')
    def local_cover():
        try:
            cover=choose_local_cover(win)
            if cover:show_cover(cover,True)
        except Exception as exc:messagebox.showerror('Cover',str(exc),parent=win)
    tk.Button(right,text='Choose from PC…',command=local_cover,bg=PANEL,fg=TEXT,relief='flat',padx=10,pady=6).pack(side='bottom',pady=(0,10),before=cover_label)
    def clear_review():
        for child in fields.winfo_children():child.destroy()
        state['checks'].clear();state['item']=None;show_cover(None)
    def review(item,cover,warning=''):
        clear_review();state['item']=item
        existing=current_values()
        for key,label in REVIEW_FIELDS:
            value=item.get(key)
            if value is None or not str(value).strip():continue
            row=tk.Frame(fields,bg=PANEL);row.pack(fill='x',padx=10,pady=6)
            checked=tk.BooleanVar(value=not bool(existing.get(key)))
            state['checks'][key]=checked
            tk.Checkbutton(row,text=label,variable=checked,bg=PANEL,fg=TEXT,selectcolor=PANEL_ALT,activebackground=PANEL).pack(anchor='w')
            tk.Label(row,text='Current: '+str(existing.get(key) or '(empty)')[:350],bg=PANEL,fg=MUTED,wraplength=450,justify='left',anchor='w').pack(fill='x',padx=22)
            tk.Label(row,text='Proposed: '+str(value)[:900],bg=PANEL,fg=TEXT,wraplength=450,justify='left',anchor='w').pack(fill='x',padx=22)
        show_cover(cover,not bool(existing.get('_cover')))
        status.set('Tick only fields you want to use. Filled manual values are unchecked by default.'+(' '+warning if warning else ''))
    def background(work,done):
        generation=state['generation']
        def run():
            try:value,error=work(),None
            except Exception as exc:value,error=None,str(exc)
            messages.put((generation,done,value,error))
        threading.Thread(target=run,daemon=True).start()
    def poll():
        if state['closed']:return
        try:
            while True:
                generation,done,value,error=messages.get_nowait()
                if generation==state['generation']:done(value,error)
        except queue.Empty:pass
        state['poll_id']=win.after(100,poll)
    def search():
        title=query.get().strip()
        if not title:status.set('Enter a title first.');return
        state['generation']+=1;state['busy']=True
        results.delete(*results.get_children());items.clear();clear_review();status.set('Searching Steam…')
        def done(value,error):
            state['busy']=False
            if error:status.set('Steam search failed. Manual entry is still available. '+error);return
            items.extend(value)
            for i,item in enumerate(items):results.insert('','end',iid=str(i),values=(item['title'],'Steam'))
            status.set(f'{len(items)} matches. Select the correct game, or close and enter it manually.')
        background(lambda:search_provider('games',title,'Steam'),done)
    def selected(event=None):
        selection=results.selection()
        if not selection:return
        index=int(selection[0])
        if not 0<=index<len(items):return
        state['generation']+=1;state['busy']=True;clear_review();status.set('Loading details and cover preview…')
        original=dict(items[index])
        def work():
            item=enrich('games',original)
            item=dict(item,name=item.get('title',''),platform='PC')
            cover=None;warning=''
            if Image is not None and item.get('cover'):
                try:
                    raw,w,h,ext=fetch(item['cover'])
                    cover=validated_cover(raw,'Steam proposed cover',item['cover'])
                except Exception:warning='The cover could not be loaded; metadata can still be used.'
            return item,cover,warning
        def done(value,error):
            state['busy']=False
            if error:status.set('Could not load details. Manual entry remains available. '+error);return
            review(*value)
        background(work,done)
    def apply():
        if state['busy']:status.set('Wait for the current search/details request to finish.');return
        item=state['item']
        if item is None and not state['cover']:status.set('Choose a Steam result or a local cover first.');return
        updates={key:item[key] for key,var in state['checks'].items() if var.get()} if item else {}
        cover=state['cover'] if use_cover.get() else None
        if not updates and not cover:status.set('Tick at least one field or choose a cover to apply.');return
        on_apply(updates,cover)
        status.set('Selection applied to Add Game. You can review another result or close this window; Save Game completes the addition.')
    tk.Button(toolbar,text='Search Steam',command=search,bg=accent,fg='white',relief='flat',padx=12,pady=6).pack(side='left',padx=(10,0))
    entry.bind('<Return>',lambda event:search());results.bind('<<TreeviewSelect>>',selected)
    footer=tk.Frame(win,bg=BG);footer.pack(fill='x',padx=18,pady=14)
    tk.Button(footer,text='Apply Selected to Form',command=apply,bg=accent,fg='white',relief='flat',padx=14,pady=8).pack(side='right')
    tk.Button(footer,text='Close / Manual Entry',command=close,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=14,pady=8).pack(side='right',padx=8)
    entry.focus_set();state['poll_id']=win.after(100,poll)
    return win
