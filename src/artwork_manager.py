"""Original-size artwork collection and selectable image gallery."""
from window_style import install as polish_dialog

import io
import threading
import uuid
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from database import PROJECT_ROOT, connection
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED
try:
    from PIL import Image, ImageTk, ImageOps
except ImportError:
    Image = ImageTk = ImageOps = None

ART_ROOT = PROJECT_ROOT / 'assets' / 'artwork'
CATEGORIES = ('games', 'movies', 'shows', 'books')

def classify(w, h):
    if w > h * 1.12: return 'Landscape'
    if h > w * 1.12: return 'Portrait'
    return 'Square'

def options(kind, result):
    """Offer known provider images; do not pretend a provider has alternatives."""
    cover = result.get('cover') or ''
    choices = []
    if cover: choices.append(('Provider artwork', cover))
    if kind == 'games' and result.get('source') == 'Steam':
        appid = str(result.get('detail', ''))
        if appid.isdecimal():
            base = f'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}'
            choices.extend([('Steam portrait grid', base + '/library_600x900.jpg'),
                            ('Steam landscape header', base + '/header.jpg'),
                            ('Steam landscape hero', base + '/library_hero.jpg')])
    if kind == 'books' and 'covers.openlibrary.org/b/id/' in cover:
        choices.append(('Open Library medium cover', cover.replace('-L.jpg','-M.jpg')))
    # Remove repeated URLs, preserving provider order.
    return list(dict((url, (label, url)) for label, url in choices if url.startswith('https://')).values())

def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent':'EntertainmentTracker/1.0'})
    with urllib.request.urlopen(request, timeout=12) as response:
        if not response.headers.get('Content-Type','').lower().startswith('image/'):
            raise ValueError('Not an image')
        raw = response.read(12 * 1024 * 1024 + 1)
    if len(raw) > 12 * 1024 * 1024: raise ValueError('Image exceeds 12 MB')
    if Image is None: raise RuntimeError('Pillow is required: pip install pillow')
    with Image.open(io.BytesIO(raw)) as img:
        img.verify()
    with Image.open(io.BytesIO(raw)) as img:
        w, h = img.size
        if w < 80 or h < 80: raise ValueError('Image is too small')
        if w * h > 60_000_000: raise ValueError('Image dimensions are too large')
        fmt = (img.format or '').upper()
    if fmt not in ('JPEG', 'PNG', 'WEBP'): raise ValueError('Unsupported image format')
    return raw, w, h, {'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[fmt]

def store(kind, item_id, raw, w, h, ext, source, set_cover=True):
    if kind not in CATEGORIES: raise ValueError('Unknown category')
    folder = ART_ROOT / kind
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'{item_id}_{uuid.uuid4().hex}{ext}'
    target.write_bytes(raw)
    rel = target.relative_to(PROJECT_ROOT).as_posix()
    try:
        with connection:
            connection.execute('INSERT INTO artwork_library (category,item_id,image_path,width,height,source) VALUES (?,?,?,?,?,?)',
                               (kind,item_id,rel,w,h,source))
            if set_cover:
                connection.execute(f'UPDATE {kind} SET cover_path=? WHERE id=?',(rel,item_id))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return rel

def select_saved(kind, item_id, path):
    if not connection.execute('SELECT 1 FROM artwork_library WHERE category=? AND item_id=? AND image_path=?',
                              (kind,item_id,path)).fetchone():
        raise ValueError('Artwork not in this collection')
    with connection:
        connection.execute(f'UPDATE {kind} SET cover_path=? WHERE id=?',(path,item_id))

def open_manager(parent, kind, item_id, title, accent, results=None, on_saved=None):
    if Image is None:
        messagebox.showerror('Artwork Manager', 'Install Pillow first: pip install pillow',parent=parent)
        return
    win=tk.Toplevel(parent); win.title('Artwork Manager — '+title)
    polish_dialog(win)
    win.geometry('920x710'); win.minsize(690,510); win.configure(bg=BG)
    win.transient(parent.winfo_toplevel())
    win.grab_set()
    tk.Label(win,text='Artwork Manager',bg=BG,fg=TEXT,font=('Arial',20,'bold')).pack(anchor='w',padx=18,pady=(15,4))
    tk.Label(win,text='Manage covers, logos and fan art in one place. Choose an image, then assign its role.',
             bg=BG,fg=MUTED,wraplength=850,justify='left').pack(anchor='w',padx=18)
    toolbar=tk.Frame(win,bg=BG); toolbar.pack(fill='x',padx=18,pady=12)
    shape=tk.StringVar(value='All'); status=tk.StringVar(value='Loading artwork…')
    ttk.Combobox(toolbar,textvariable=shape,values=['All','Portrait','Landscape','Square'],state='readonly',width=15).pack(side='left')
    tk.Label(toolbar,textvariable=status,bg=BG,fg=MUTED).pack(side='left',padx=14)
    outer=tk.Frame(win,bg=BG);outer.pack(fill='both',expand=True,padx=18)
    canvas=tk.Canvas(outer,bg=BG,highlightthickness=0); scroll=ttk.Scrollbar(outer,command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
    gallery=tk.Frame(canvas,bg=BG);window_id=canvas.create_window((0,0),window=gallery,anchor='nw')
    gallery.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window_id,width=e.width))
    entries=[]; photos=[]; selected={'index':None}
    gallery_columns=[3]
    info=tk.StringVar(value='Choose an image to preview it.')
    tk.Label(win,textvariable=info,bg=BG,fg=TEXT,wraplength=850).pack(anchor='w',padx=18,pady=6,before=outer)
    def display():
        for child in gallery.winfo_children():child.destroy()
        photos.clear()
        visible=[(i,e) for i,e in enumerate(entries) if shape.get()=='All' or e['shape']==shape.get()]
        if not visible:
            tk.Label(gallery,text='No artwork in this filter.',bg=BG,fg=MUTED).pack(pady=35)
        for pos,(i,e) in enumerate(visible):
            cell=tk.Frame(gallery,bg=PANEL if selected['index']!=i else accent,padx=7,pady=7)
            cell.grid(row=pos//gallery_columns[0],column=pos%gallery_columns[0],padx=8,pady=8,sticky='n')
            with Image.open(io.BytesIO(e['raw'])) as im:
                im.thumbnail((220,155),Image.Resampling.LANCZOS)
                photo=ImageTk.PhotoImage(im.copy())
            photos.append(photo)
            btn=tk.Button(cell,image=photo,bg=PANEL,relief='flat',command=lambda j=i:choose(j),cursor='hand2')
            btn.pack()
            tk.Label(cell,text=e['label'][:27],bg=cell['bg'],fg=TEXT).pack()
            tk.Label(cell,text=f"{e['w']} × {e['h']} · {e['shape']}",bg=cell['bg'],fg=TEXT).pack()
        status.set(f'{len(visible)} images shown · {len(entries)} available')
    def choose(i):
        selected['index']=i;e=entries[i]
        info.set(f"Selected: {e['label']} — {e['w']} × {e['h']} ({e['shape']}). Original resolution will be preserved.")
        display()
    shape.trace_add('write',lambda *_:display())
    def resize_gallery(event):
        cols=max(1,event.width//265)
        if cols != gallery_columns[0]:
            gallery_columns[0]=cols
            display()
    canvas.bind('<Configure>', lambda e:(canvas.itemconfigure(window_id,width=e.width),resize_gallery(e)))
    def wheel(event):
        canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
    def bind_wheel(event): canvas.bind_all('<MouseWheel>', wheel)
    def unbind_wheel(event): canvas.unbind_all('<MouseWheel>')
    canvas.bind('<Enter>',bind_wheel)
    canvas.bind('<Leave>',unbind_wheel)
    win.bind('<Escape>',lambda e:win.destroy())
    def add_image(raw,w,h,ext,label,source,path=None):
        entries.append(dict(raw=raw,w=w,h=h,ext=ext,label=label,source=source,path=path,shape=classify(w,h)))
    def load_saved():
        for path,w,h,source in connection.execute('SELECT image_path,width,height,source FROM artwork_library WHERE category=? AND item_id=? ORDER BY id DESC', (kind,item_id)).fetchall():
            try:
                absolute=PROJECT_ROOT/path
                if absolute.exists():
                    raw=absolute.read_bytes()
                    with Image.open(io.BytesIO(raw)) as im: fmt=im.format
                    add_image(raw,w,h,{'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}.get(fmt,'.jpg'),'Saved · '+(source or 'local'),source or 'local',path)
            except Exception:pass
        display()
    load_saved()
    def download_candidates(candidates):
        status.set('Checking online artwork…')
        def work():
            found=[]
            for label,url in candidates:
                try:
                    raw,w,h,ext=fetch(url)
                    found.append((raw,w,h,ext,label,url))
                except Exception:continue
            try:win.after(0,lambda:finish(found))
            except RuntimeError:pass
        def finish(found):
            if not win.winfo_exists():return
            for raw,w,h,ext,label,url in found:add_image(raw,w,h,ext,label,url)
            display()
        threading.Thread(target=work,daemon=True).start()
    if results:download_candidates(results)
    def add_local():
        filename=filedialog.askopenfilename(parent=win,filetypes=[('Images','*.png *.jpg *.jpeg *.webp'),('All files','*.*')])
        if not filename:return
        try:
            raw=Path(filename).read_bytes()
            with Image.open(io.BytesIO(raw)) as im:
                w,h=im.size;fmt=im.format
            if fmt not in ('JPEG','PNG','WEBP'):raise ValueError('Use JPEG, PNG or WebP')
            if w*h>60_000_000:raise ValueError('Image dimensions too large')
            add_image(raw,w,h,{'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[fmt],Path(filename).name,'Local file')
            choose(len(entries)-1)
        except Exception as exc:messagebox.showerror('Image Error',str(exc),parent=win)
    def full_preview():
        i=selected['index']
        if i is None:return
        e=entries[i];popup=tk.Toplevel(win);popup.title(e['label']);popup.configure(bg=BG)
        polish_dialog(popup)
        popup.geometry('850x650')
        with Image.open(io.BytesIO(e['raw'])) as im:
            im.thumbnail((800,575),Image.Resampling.LANCZOS)
            photo=ImageTk.PhotoImage(im.copy())
        lbl=tk.Label(popup,image=photo,bg=BG);lbl.image=photo;lbl.pack(fill='both',expand=True,padx=10,pady=10)
        tk.Label(popup,text=f"{e['w']} × {e['h']} · {e['shape']}",bg=BG,fg=TEXT).pack(pady=10)
    def save_selected(make_cover):
        i=selected['index']
        if i is None:messagebox.showinfo('Select Artwork','Choose an image first.',parent=win);return
        e=entries[i]
        try:
            if e['path']:
                if make_cover:select_saved(kind,item_id,e['path'])
            else:
                saved_path=store(kind,item_id,e['raw'],e['w'],e['h'],e['ext'],e['source'],make_cover)
                e['path']=saved_path
            if on_saved:on_saved()
            win.destroy()
        except Exception as exc:messagebox.showerror('Artwork Save Failed',str(exc),parent=win)
    def set_role(role):
        if kind != 'games': return
        i=selected['index']
        if i is None:
            messagebox.showinfo('Select Artwork','Select an image first.',parent=win);return
        try:
            e=entries[i]
            if not e['path']:
                e['path']=store(kind,item_id,e['raw'],e['w'],e['h'],e['ext'],e['source'],set_cover=False)
            from details import _set_game_art
            _set_game_art(item_id,role,e['path'])
            if on_saved:on_saved()
            win.destroy()
        except Exception as exc: messagebox.showerror('Artwork',str(exc),parent=win)

    def remove_selected():
        i=selected['index']
        if i is None:
            messagebox.showinfo('Remove Artwork','Select an image first.',parent=win);return
        e=entries[i]
        if not e['path']:
            entries.pop(i);selected['index']=None;display();return
        path=e['path']
        refs=[]
        if connection.execute(f'SELECT 1 FROM {kind} WHERE id=? AND cover_path=?',(item_id,path)).fetchone():
            refs.append('cover')
        if kind=='games':
            from details import _game_art_paths
            logo,bg=_game_art_paths(item_id)
            if path==logo:refs.append('logo')
            if path==bg:refs.append('background')
        note=('This image is currently assigned as '+', '.join(refs)+'. Its assignment will be cleared.\n\n') if refs else ''
        if not messagebox.askyesno('Delete Saved Artwork',note+'Permanently delete this saved image from the collection?',parent=win):return
        try:
            with connection:
                connection.execute('DELETE FROM artwork_library WHERE category=? AND item_id=? AND image_path=?',(kind,item_id,path))
                if 'cover' in refs:
                    connection.execute(f'UPDATE {kind} SET cover_path=NULL WHERE id=? AND cover_path=?',(item_id,path))
                if kind=='games':
                    from details import _set_game_art
                    if 'logo' in refs:_set_game_art(item_id,'logo_path',None)
                    if 'background' in refs:_set_game_art(item_id,'background_path',None)
            # Only delete managed collection files; never delete arbitrary imported files.
            absolute=(PROJECT_ROOT/path).resolve()
            if absolute.is_relative_to(ART_ROOT.resolve()) and not connection.execute(
                'SELECT 1 FROM artwork_library WHERE image_path=? LIMIT 1',(path,)).fetchone():
                absolute.unlink(missing_ok=True)
            entries.pop(i);selected['index']=None;display()
            if on_saved:on_saved()
        except Exception as exc:messagebox.showerror('Delete Failed',str(exc),parent=win)

    actions=tk.Frame(win,bg=BG);actions.pack(fill='x',padx=18,pady=(8,10),before=outer)
    for label,command in [('Add from PC',add_local),('Full Preview',full_preview),('Save to Collection',lambda:save_selected(False)),('Set as Cover',lambda:save_selected(True))]:
        tk.Button(actions,text=label,command=command,bg=accent if label=='Set as Cover' else PANEL_ALT,fg=TEXT,relief='flat',padx=12,pady=8).pack(side='left',padx=(0,8))
    role_actions=tk.Frame(win,bg=BG);role_actions.pack(fill='x',padx=18,pady=(0,12),before=outer)
    if kind=='games':
        for label,role in [('Set as Logo','logo_path'),('Set as Background','background_path')]:
            tk.Button(role_actions,text=label,command=lambda r=role:set_role(r),bg=PANEL_ALT,fg=TEXT,
                      relief='flat',padx=9,pady=8).pack(side='left',padx=(0,5))
    tk.Button(role_actions,text='Delete Image',command=remove_selected,bg='#7e303c',fg=TEXT,
              relief='flat',padx=10,pady=8).pack(side='left',padx=(0,5))
    tk.Button(actions,text='Close',command=win.destroy,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=12,pady=8).pack(side='right')
