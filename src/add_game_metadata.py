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
from database import connection, PROJECT_ROOT, get_setting, set_setting
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


def choose_local_cover(parent,role='Cover'):
    filename=filedialog.askopenfilename(parent=parent,title='Choose Game '+role,initialdir=import_folder('artwork'),
                                       filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.bmp'),('All files','*.*')])
    if not filename:return None
    try:remember_import_folder('artwork',[filename])
    except Exception:pass
    return validated_cover(Path(filename).read_bytes(),Path(filename).name)


def preview_cover(parent,cover,role='Artwork'):
    if not cover:return
    win=tk.Toplevel(parent);polish_dialog(win);win.title('Proposed Game '+role)
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


def image_digest(image):
    return hashlib.sha256(image['raw']).hexdigest()


def staged_signature(metadata,cover,extras=(),lock_cover=False,roles=None):
    return (tuple(sorted(metadata.items())),image_digest(cover) if cover else None,
            tuple(sorted({image_digest(image) for image in extras})),bool(lock_cover),
            tuple((key,image_digest((roles or {})[key]) if (roles or {}).get(key) else None)
                  for key in ('background_path','logo_path')))


def create_game(values, metadata=None, cover=None, extras=(), lock_cover=False, roles=None):
    """No downloads on Save; reviewed bytes and SQLite changes commit together."""
    from artwork_preferences import lock_key
    metadata=metadata or {};created=[];images=[];seen=set();paths={}
    roles={key:(roles or {}).get(key) for key in ('background_path','logo_path')}
    if cover:cover=validated_cover(cover['raw'],cover['label'],cover['source'])
    for image in ([cover] if cover else [])+list(extras)+[image for image in roles.values() if image]:
        image=validated_cover(image['raw'],image['label'],image['source'])
        digest=image_digest(image)
        if digest not in seen:images.append(image);seen.add(digest)
    try:
        with connection:
            result=connection.execute('INSERT INTO games (name,platform,playtime,price_paid,completed,backlog,started,description) VALUES (?,?,?,?,?,?,?,?)',values)
            game_id=result.lastrowid
            for field in METADATA_FIELDS:
                value=metadata.get(field)
                if value is not None and str(value).strip():
                    if field=='release_year':value=int(value)
                    connection.execute(f'UPDATE games SET {field}=? WHERE id=?',(value,game_id))
            for index,image in enumerate(images):
                folder=PROJECT_ROOT/'assets'/'artwork'/'games';folder.mkdir(parents=True,exist_ok=True)
                role='Cover' if cover and index==0 else 'Artwork'
                target=folder/f'{clean_name(values[0])} - {role} - {uuid.uuid4().hex[:12]}{image["ext"]}'
                created.append(target);target.write_bytes(image['raw'])
                path=target.relative_to(PROJECT_ROOT).as_posix()
                paths[image_digest(image)]=path
                connection.execute('INSERT INTO artwork_library(category,item_id,image_path,width,height,source) VALUES(?,?,?,?,?,?)',
                                   ('games',game_id,path,image['w'],image['h'],image['source']))
                if cover and index==0:connection.execute('UPDATE games SET cover_path=? WHERE id=?',(path,game_id))
            if any(roles.values()):
                connection.execute('CREATE TABLE IF NOT EXISTS game_detail_art (game_id INTEGER PRIMARY KEY, logo_path TEXT, background_path TEXT)')
                connection.execute('INSERT INTO game_detail_art(game_id,logo_path,background_path) VALUES(?,?,?)',
                                   (game_id,paths.get(image_digest(roles['logo_path'])) if roles['logo_path'] else None,
                                    paths.get(image_digest(roles['background_path'])) if roles['background_path'] else None))
            if cover and lock_cover:
                connection.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                                   (lock_key('games',game_id,'cover_path'),'1'))
        return game_id
    except Exception:
        for target in created:target.unlink(missing_ok=True)
        raise


def review_text(parent,label,current,proposed):
    win=tk.Toplevel(parent);polish_dialog(win);win.title(label+' — Full Metadata Preview')
    win.geometry('820x650');win.configure(bg=BG);win.transient(parent.winfo_toplevel())
    previous=win.grab_current();win.grab_set()
    def close(event=None):
        win.destroy()
        if previous is not None:
            try:
                if previous.winfo_exists():previous.grab_set()
            except tk.TclError:pass
        return 'break'
    win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',close)
    frame=tk.Frame(win,bg=BG);frame.pack(fill='both',expand=True,padx=14,pady=14)
    text=tk.Text(frame,wrap='word',bg=PANEL,fg=TEXT,relief='flat',padx=12,pady=12)
    scroll=ttk.Scrollbar(frame,command=text.yview);scroll.pack(side='right',fill='y')
    text.configure(yscrollcommand=scroll.set);text.pack(fill='both',expand=True)
    text.insert('1.0',f'CURRENT {label.upper()}\n\n{current or "(empty)"}\n\nPROPOSED {label.upper()}\n\n{proposed}')
    text.configure(state='disabled')
    tk.Button(win,text='Close',command=close,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=15,pady=7).pack(pady=(0,12))
    return win


def artwork_role_option(parent,text,variable,value):
    """Draw explicit checked/unchecked states, independent of native radio themes."""
    row=tk.Frame(parent,bg=PANEL,cursor='hand2')
    indicator=tk.Canvas(row,width=18,height=18,bg=PANEL,highlightthickness=0)
    indicator.pack(side='left')
    indicator.create_oval(2,2,16,16,outline=TEXT,width=1)
    dot=indicator.create_oval(6,6,12,12,outline='white',fill='white')
    label=tk.Label(row,text=text,bg=PANEL,fg=TEXT);label.pack(side='left',padx=4)
    def refresh(*args):
        indicator.itemconfigure(dot,state='normal' if variable.get()==value else 'hidden')
    def select(event=None):
        variable.set(value);row.focus_set();return 'break'
    trace=variable.trace_add('write',refresh)
    def cleanup(event):
        if event.widget is row:
            try:variable.trace_remove('write',trace)
            except tk.TclError:pass
    row.configure(takefocus=True)
    for widget in (row,indicator,label):widget.bind('<Button-1>',select)
    row.bind('<space>',select);row.bind('<Return>',select)
    row.bind('<FocusIn>',lambda event:indicator.configure(highlightthickness=1,highlightbackground=TEXT))
    row.bind('<FocusOut>',lambda event:indicator.configure(highlightthickness=0))
    row.bind('<Destroy>',cleanup)
    refresh();row.pack(anchor='w',padx=10,pady=1)
    return row


def choose_artwork(parent,accent,available,cover,extras,on_choose,roles=None):
    """All choices are downloaded bytes; filters never discard selections."""
    images=list(available);seen={image_digest(image) for image in images}
    for image in ([cover] if cover else [])+list(extras)+[image for image in (roles or {}).values() if image]:
        if image_digest(image) not in seen:images.append(image);seen.add(image_digest(image))
    win=tk.Toplevel(parent);polish_dialog(win);win.title('Choose Available Game Artwork')
    win.geometry('900x720');win.minsize(650,500);win.configure(bg=BG);win.transient(parent.winfo_toplevel())
    previous=win.grab_current();win.grab_set()
    def close(event=None):
        win.destroy()
        if previous is not None:
            try:
                if previous.winfo_exists():previous.grab_set()
            except tk.TclError:pass
        return 'break'
    win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',close)
    tk.Label(win,text='Choose artwork roles; tick extra images to keep in Artwork Manager. Click any image to preview.',bg=BG,fg=TEXT,
             wraplength=820,justify='left').pack(anchor='w',padx=16,pady=12)
    sizes={'All sizes':0,'512 px+':512,'1280 px+':1280,'1920 px+':1920,'3840 px+':3840}
    shapes=('All shapes','Portrait','Landscape','Square')
    saved_minimum=get_setting('add_game_art_minimum','All sizes')
    saved_shape=get_setting('add_game_art_shape','All shapes')
    minimum=tk.StringVar(value=saved_minimum if saved_minimum in sizes else 'All sizes')
    shape=tk.StringVar(value=saved_shape if saved_shape in shapes else 'All shapes')
    chosen=tk.StringVar(value=image_digest(cover) if cover else '')
    role_choices={key:tk.StringVar(value=image_digest(image) if image else '') for key,image in (roles or {}).items()
                  if key in ('background_path','logo_path')}
    if roles is not None:
        for key in ('background_path','logo_path'):role_choices.setdefault(key,tk.StringVar(value=''))
    selected={image_digest(image):tk.BooleanVar(value=any(image_digest(extra)==image_digest(image) for extra in extras)) for image in images}
    toolbar=tk.Frame(win,bg=BG);toolbar.pack(fill='x',padx=16)
    tk.Label(toolbar,text='Minimum width:',bg=BG,fg=TEXT).pack(side='left')
    combo=ttk.Combobox(toolbar,textvariable=minimum,values=list(sizes),state='readonly',width=14);combo.pack(side='left',padx=8)
    shape_combo=ttk.Combobox(toolbar,textvariable=shape,values=shapes,state='readonly',width=14);shape_combo.pack(side='left',padx=8)
    count=tk.StringVar();tk.Label(win,textvariable=count,bg=BG,fg=MUTED,wraplength=820).pack(anchor='w',padx=16,pady=4)
    frame=tk.Frame(win,bg=BG);frame.pack(fill='both',expand=True,padx=16,pady=12)
    canvas=tk.Canvas(frame,bg=BG,highlightthickness=0);scroll=ttk.Scrollbar(frame,command=canvas.yview);scroll.pack(side='right',fill='y')
    canvas.configure(yscrollcommand=scroll.set);canvas.pack(fill='both',expand=True)
    rows=tk.Frame(canvas,bg=BG);window_id=canvas.create_window(0,0,window=rows,anchor='nw')
    rows.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda event:canvas.itemconfigure(window_id,width=event.width))
    photos=[]
    def render(event=None):
        from artwork_manager import classify
        for child in rows.winfo_children():child.destroy()
        photos.clear();visible=[image for image in images if image['w']>=sizes[minimum.get()] and
                               (shape.get()=='All shapes' or classify(image['w'],image['h'])==shape.get())]
        count.set(f'{len(visible)} of {len(images)} images · selections retained when filtering')
        for image in visible:
            row=tk.Frame(rows,bg=PANEL);row.pack(fill='x',pady=5)
            with Image.open(io.BytesIO(image['raw'])) as picture:thumbnail=ImageOps.contain(picture.convert('RGBA'),(200,160))
            photo=ImageTk.PhotoImage(thumbnail);photos.append(photo)
            preview=tk.Label(row,image=photo,bg=PANEL,cursor='hand2');preview.pack(side='left',padx=10,pady=10)
            preview.bind('<Button-1>',lambda event,image=image:preview_cover(win,image))
            tk.Label(row,text=f"{image['label']}\n{image['w']} × {image['h']} · {len(image['raw'])/1024:.1f} KB",
                     bg=PANEL,fg=TEXT,wraplength=400,justify='left').pack(anchor='w',padx=10,pady=(12,6))
            artwork_role_option(row,'Use as cover',chosen,image_digest(image))
            for key,var in role_choices.items():
                artwork_role_option(row,'Use as '+('background' if key=='background_path' else 'logo'),var,image_digest(image))
            tk.Checkbutton(row,text='Save in artwork collection',variable=selected[image_digest(image)],bg=PANEL,fg=TEXT,
                           selectcolor=PANEL_ALT).pack(anchor='w',padx=10,pady=(0,10))
        if not visible:tk.Label(rows,text='No available images match these filters. Change the filters to see more.',bg=BG,fg=MUTED).pack(pady=25)
        canvas.yview_moveto(0)
    def filter_changed(event=None):
        try:
            set_setting('add_game_art_minimum',minimum.get());set_setting('add_game_art_shape',shape.get())
        except Exception:pass
        render()
    combo.bind('<<ComboboxSelected>>',filter_changed);shape_combo.bind('<<ComboboxSelected>>',filter_changed)
    footer=tk.Frame(win,bg=BG);footer.pack(fill='x',padx=16,pady=(0,14))
    def apply():
        cover=next((image for image in images if image_digest(image)==chosen.get()),None)
        extras=[image for image in images if selected[image_digest(image)].get() and image is not cover]
        if roles is None:on_choose(cover,extras)
        else:on_choose(cover,extras,{key:next((image for image in images if image_digest(image)==var.get()),None)
                                    for key,var in role_choices.items()})
    tk.Button(footer,text='Use Choices',command=apply,bg=accent,fg='white',relief='flat',padx=14,pady=8).pack(side='right')
    tk.Button(footer,text='Close',command=close,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=14,pady=8).pack(side='right',padx=8)
    clear=tk.Menubutton(footer,text='Clear role ▾',bg=PANEL_ALT,fg=TEXT,relief='flat',padx=12,pady=8)
    clear.pack(side='left');menu=tk.Menu(clear,tearoff=False,bg=PANEL_ALT,fg=TEXT);clear.configure(menu=menu)
    menu.add_command(label='Cover',command=lambda:chosen.set(''))
    for key,var in role_choices.items():menu.add_command(label='Background' if key=='background_path' else 'Logo',command=lambda var=var:var.set(''))
    render();return win


def open_search(parent,accent,current_values,on_apply):
    """Search existing Steam provider, review choices and stage them in the form."""
    from metadata_finder import search_provider,enrich
    from artwork_manager import fetch,options
    win=tk.Toplevel(parent);polish_dialog(win);win.title('Add Game — Steam Search and Review')
    win.geometry('980x760');win.minsize(750,590);win.configure(bg=BG)
    win.transient(parent.winfo_toplevel());previous_grab=win.grab_current();win.grab_set()
    state={'closed':False,'generation':0,'item':None,'cover':None,'checks':{},'photo':None,'busy':False,
           'available':list(current_values().get('_available',())),'extras':list(current_values().get('_extras',())),
           'roles':dict(current_values().get('_roles',{}))}
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
    lock_cover=tk.BooleanVar(value=bool(current_values().get('_lock_cover')))
    tk.Checkbutton(right,text='Protect chosen cover',variable=lock_cover,bg=PANEL_ALT,fg=TEXT,
                   selectcolor=PANEL).pack(side='bottom',pady=3,before=cover_label)
    artwork_info=tk.StringVar(value='No extra images selected')
    tk.Label(right,textvariable=artwork_info,bg=PANEL_ALT,fg=MUTED,wraplength=215).pack(side='bottom',pady=5,before=cover_label)
    def artwork_choices():
        if state['busy']:status.set('Wait for the artwork request to finish.');return
        if not state['available'] and not state['cover'] and not state['extras'] and not any(state['roles'].values()):
            status.set('Select a Steam result with available artwork first.');return
        def chosen(cover,extras,roles):
            show_cover(cover,bool(cover));state['extras']=extras;state['roles']=roles
            artwork_info.set(f'{len(extras)} extras · Background: '+('yes' if roles.get('background_path') else 'no')+
                             ' · Logo: '+('yes' if roles.get('logo_path') else 'no'))
            status.set('Artwork choices staged here. Apply Selected to Form transfers them to Add Game.')
        choose_artwork(win,accent,state['available'],state['cover'] if use_cover.get() else None,state['extras'],chosen,roles=state['roles'])
    tk.Button(right,text='Choose available artwork…',command=artwork_choices,bg=PANEL,fg=TEXT,relief='flat',
              padx=8,pady=6).pack(side='bottom',pady=5,before=cover_label)
    def show_cover(cover,selected=False):
        state['cover']=cover;state['photo']=None;use_cover.set(bool(cover and selected))
        cover_check.configure(state='normal' if cover else 'disabled')
        if cover:
            with Image.open(io.BytesIO(cover['raw'])) as image:
                picture=ImageOps.contain(image.convert('RGBA'),(215,260))
            state['photo']=ImageTk.PhotoImage(picture)
            cover_label.configure(image=state['photo'],text='')
        else:cover_label.configure(image='',text='No cover preview available. You can choose a local image or continue without artwork.')
    def resize_cover(event):
        cover=state['cover']
        if not cover or event.width<10 or event.height<10:return
        with Image.open(io.BytesIO(cover['raw'])) as image:
            picture=ImageOps.contain(image.convert('RGBA'),(max(1,event.width-8),max(1,event.height-8)))
        state['photo']=ImageTk.PhotoImage(picture);cover_label.configure(image=state['photo'])
    cover_label.bind('<Configure>',resize_cover)
    def local_cover():
        try:
            cover=choose_local_cover(win)
            if cover:show_cover(cover,True)
        except Exception as exc:messagebox.showerror('Cover',str(exc),parent=win)
    tk.Button(right,text='Choose from PC…',command=local_cover,bg=PANEL,fg=TEXT,relief='flat',padx=10,pady=6).pack(side='bottom',pady=(0,10),before=cover_label)
    def clear_review():
        for child in fields.winfo_children():child.destroy()
        state['checks'].clear();state['item']=None;state['available']=[];show_cover(None)
    def review(item,available,warning=''):
        clear_review();state['item']=item
        state['available']=available
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
            if key=='description' or len(str(value))>900 or len(str(existing.get(key) or ''))>350:
                tk.Button(row,text='Read full '+label.lower()+'…',command=lambda key=key,label=label,value=value:
                          review_text(win,label,current_values().get(key),value),bg=PANEL_ALT,fg=TEXT,relief='flat').pack(anchor='w',padx=22,pady=4)
        show_cover(available[0] if available else None,not bool(existing.get('_cover')))
        artwork_info.set(f"{len(available)} available · {len(state['extras'])} extras selected")
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
        state['generation']+=1;state['busy']=True;clear_review();status.set('Loading details and available artwork…')
        original=dict(items[index])
        def work():
            item=enrich('games',original)
            item=dict(item,name=item.get('title',''),platform='PC')
            available=[];seen=set();failed=0
            if Image is not None:
                for label,url in options('games',item):
                    try:
                        raw,w,h,ext=fetch(url);image=validated_cover(raw,label,url)
                        digest=image_digest(image)
                        if digest not in seen:available.append(image);seen.add(digest)
                    except Exception:failed+=1
            warning=f'{failed} artwork options unavailable; metadata can still be used.' if failed else ''
            return item,available,warning
        def done(value,error):
            state['busy']=False
            if error:status.set('Could not load details. Manual entry remains available. '+error);return
            review(*value)
        background(work,done)
    def apply():
        if state['busy']:status.set('Wait for the current search/details request to finish.');return
        item=state['item']
        if item is None and not state['cover'] and not state['extras'] and not any(state['roles'].values()):
            status.set('Choose a Steam result or a local cover first.');return
        updates={key:item[key] for key,var in state['checks'].items() if var.get()} if item else {}
        cover=state['cover'] if use_cover.get() else None
        extras_changed={image_digest(image) for image in state['extras']}!={image_digest(image) for image in current_values().get('_extras',())}
        roles_changed=staged_signature({},None,roles=state['roles'])!=staged_signature({},None,roles=current_values().get('_roles'))
        if not updates and not cover and not state['extras'] and not extras_changed and not roles_changed:
            status.set('Tick at least one field or choose artwork to apply.');return
        on_apply(updates,cover,list(state['extras']),lock_cover.get() if cover else None,dict(state['roles']),list(state['available']))
        status.set('Selection applied to Add Game. You can review another result or close this window; Save Game completes the addition.')
    tk.Button(toolbar,text='Search Steam',command=search,bg=accent,fg='white',relief='flat',padx=12,pady=6).pack(side='left',padx=(10,0))
    entry.bind('<Return>',lambda event:search());results.bind('<<TreeviewSelect>>',selected)
    footer=tk.Frame(win,bg=BG);footer.pack(fill='x',padx=18,pady=14)
    tk.Button(footer,text='Apply Selected to Form',command=apply,bg=accent,fg='white',relief='flat',padx=14,pady=8).pack(side='right')
    tk.Button(footer,text='Close / Manual Entry',command=close,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=14,pady=8).pack(side='right',padx=8)
    entry.focus_set();state['poll_id']=win.after(100,poll)
    return win
