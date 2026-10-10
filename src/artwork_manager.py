"""Original-size artwork collection and selectable image gallery."""
from window_style import install as polish_dialog

import io
import hashlib
import re
import threading
import uuid
from media_naming import clean_name
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from database import PROJECT_ROOT, connection, get_setting, set_setting
from artwork_preferences import (is_locked,set_locked,require_unlocked,is_favourite,set_favourite,
                                 import_folder,remember_import_folder,relink_artwork)
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

def artwork_window_size(value, screen_width, screen_height):
    """Restore size only; keep the window reachable on the current display."""
    match = re.fullmatch(r'(\d+)x(\d+)', value or '')
    width, height = map(int, match.groups()) if match else (920, 710)
    return f'{min(max(690, width), max(690, screen_width - 60))}x{min(max(510, height), max(510, screen_height - 80))}'


def artwork_matches_search(entry, query):
    names = [entry['label'], entry.get('path') or '', entry.get('origin_path') or '']
    return query.strip().casefold() in ' '.join(Path(name).name for name in names).casefold()


def artwork_digest(raw):
    return hashlib.sha256(raw).hexdigest()


def artwork_file_details(entry):
    name = Path(entry.get('path') or entry.get('origin_path') or entry['label']).name
    if entry.get('missing'):return f"{name} · File missing — use Collection actions → Relink missing image"
    size = len(entry['raw'])
    amount = f'{size / 1048576:.2f} MB' if size >= 1048576 else f'{size / 1024:.1f} KB'
    return f"{name} · {entry['w']} × {entry['h']} pixels · {amount}"


def store(kind, item_id, raw, w, h, ext, source, set_cover=True):
    if kind not in CATEGORIES: raise ValueError('Unknown category')
    if set_cover:require_unlocked(kind,item_id,'cover_path')
    # Exact copies within this item's collection reuse their existing local file.
    digest = artwork_digest(raw)
    for (existing,) in connection.execute(
            'SELECT image_path FROM artwork_library WHERE category=? AND item_id=?',
            (kind, item_id)).fetchall():
        try:
            if artwork_digest((PROJECT_ROOT / existing).read_bytes()) != digest:
                continue
        except (OSError, TypeError):
            continue
        if set_cover:
            select_saved(kind, item_id, existing)
        return existing
    folder = ART_ROOT / kind
    folder.mkdir(parents=True, exist_ok=True)
    title_row = connection.execute(f'SELECT name FROM {kind} WHERE id=?', (item_id,)).fetchone()
    title = clean_name(title_row[0] if title_row else f'{kind} {item_id}')
    role = 'Cover' if set_cover else 'Artwork'
    target = folder / f'{title} - {role} - {uuid.uuid4().hex[:8]}{ext}'
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
    require_unlocked(kind,item_id,'cover_path')
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
    win.geometry(artwork_window_size(get_setting('artwork_window_size','920x710'),
                                     win.winfo_screenwidth(),win.winfo_screenheight()))
    win.minsize(690,510); win.configure(bg=BG)
    win.transient(parent.winfo_toplevel())
    previous_grab=win.grab_current()
    win._artwork_changed=False
    manager_closed={'value':False}
    def close_manager(event=None):
        if manager_closed['value']:
            return 'break'
        manager_closed['value']=True
        changed=win._artwork_changed
        try:set_setting('artwork_window_size',f'{win.winfo_width()}x{win.winfo_height()}')
        except Exception:pass
        win.destroy()
        if previous_grab is not None:
            try:
                if previous_grab.winfo_exists():previous_grab.grab_set()
            except tk.TclError:pass
        if changed and on_saved:on_saved()
        return 'break'
    win.protocol('WM_DELETE_WINDOW',close_manager)
    win.grab_set()
    tk.Label(win,text='Artwork Manager',bg=BG,fg=TEXT,font=('Arial',20,'bold')).pack(anchor='w',padx=18,pady=(15,4))
    tk.Label(win,text='Click to select an image. Ctrl-click to select several, then Save Selected to keep them locally.',
             bg=BG,fg=MUTED,wraplength=850,justify='left').pack(anchor='w',padx=18)
    toolbar=tk.Frame(win,bg=BG); toolbar.pack(fill='x',padx=18,pady=12)
    shape_values=['All','Portrait','Landscape','Square']
    saved_shape=get_setting('artwork_filter_shape','All')
    shape=tk.StringVar(value=saved_shape if saved_shape in shape_values else 'All'); status=tk.StringVar(value='Loading artwork…')
    ttk.Combobox(toolbar,textvariable=shape,values=['All','Portrait','Landscape','Square'],state='readonly',width=15).pack(side='left')
    minimum_widths={'All sizes':0,'512 px+':512,'1280 px+':1280,'1920 px+':1920,'3840 px+':3840}
    saved_width=get_setting('artwork_filter_width','All sizes')
    minimum_width=tk.StringVar(value=saved_width if saved_width in minimum_widths else 'All sizes')
    tk.Label(toolbar,text='Minimum width:',bg=BG,fg=TEXT).pack(side='left',padx=(14,5))
    ttk.Combobox(toolbar,textvariable=minimum_width,values=list(minimum_widths),
                 state='readonly',width=13).pack(side='left')
    role_values=['All roles','Current Cover'] + (['Current Logo','Current Background'] if kind=='games' else ['Current Background'] if kind in ('movies','shows') else [])
    saved_role=get_setting('artwork_filter_role_'+kind,'All roles')
    role_filter=tk.StringVar(value=saved_role if saved_role in role_values else 'All roles')
    ttk.Combobox(toolbar,textvariable=role_filter,values=role_values,state='readonly',width=19).pack(side='left',padx=10)
    search_row=tk.Frame(win,bg=BG);search_row.pack(fill='x',padx=18,pady=(0,8))
    tk.Label(search_row,text='Filename search:',bg=BG,fg=TEXT).pack(side='left',padx=(0,8))
    filename_search=tk.StringVar(value='')
    favourites_only=tk.BooleanVar(value=False)
    ttk.Entry(search_row,textvariable=filename_search).pack(side='left',fill='x',expand=True)
    tk.Checkbutton(search_row,text='Favourites only',variable=favourites_only,bg=BG,fg=TEXT,
                   selectcolor=PANEL,activebackground=BG).pack(side='left',padx=8)
    tk.Button(search_row,text='Reset filters',command=lambda:reset_filters(),bg=PANEL_ALT,
              fg=TEXT,relief='flat',padx=10,pady=4).pack(side='right',padx=(10,0))
    tk.Label(win,textvariable=status,bg=BG,fg=MUTED).pack(anchor='w',padx=18)
    outer=tk.Frame(win,bg=BG);outer.pack(fill='both',expand=True,padx=18)
    canvas=tk.Canvas(outer,bg=BG,highlightthickness=0); scroll=ttk.Scrollbar(outer,command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
    gallery=tk.Frame(canvas,bg=BG);window_id=canvas.create_window((0,0),window=gallery,anchor='nw')
    gallery.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window_id,width=e.width))
    entries=[]; photos=[]; selected={'index':None,'indices':set()}
    gallery_columns=[3]
    info=tk.StringVar(value='Choose an image to preview it.')
    tk.Label(win,textvariable=info,bg=BG,fg=TEXT,wraplength=850).pack(anchor='w',padx=18,pady=6,before=outer)
    preview_frame=tk.Frame(win,bg=PANEL)
    preview_frame.pack(fill='x',padx=18,pady=(0,8),before=outer)
    selected_preview=tk.Label(preview_frame,text='Click an artwork thumbnail below to preview it here.',
                              bg=PANEL,fg=MUTED)
    selected_preview.pack(fill='x',pady=(4,0))
    preview_details=tk.StringVar(value='')
    details_label=tk.Label(preview_frame,textvariable=preview_details,bg=PANEL,fg=TEXT,
                           wraplength=850,justify='left',anchor='w')
    details_label.pack(fill='x',padx=8,pady=(4,8))
    preview_frame.bind('<Configure>',lambda event:details_label.configure(wraplength=max(100,event.width-16)))
    preview_state={'photo':None}
    def matches_filters(entry):
        return ((not favourites_only.get() or is_favourite(kind,item_id,entry.get('path') or entry.get('origin_path')))
                and artwork_matches_search(entry,filename_search.get())
                and (shape.get()=='All' or entry['shape']==shape.get())
                and entry['w']>=minimum_widths.get(minimum_width.get(),0)
                and (role_filter.get()=='All roles' or role_filter.get() in assignment_labels(entry,current_assignments())))
    def clear_preview():
        preview_details.set('')
        preview_state['photo']=None
        selected_preview.configure(image='',text='Click an artwork thumbnail below to preview it here.')
        info.set('Choose an image to preview it.')
    def current_assignments():
        row=connection.execute(f'SELECT cover_path FROM {kind} WHERE id=?',(item_id,)).fetchone()
        assigned={'Current Cover':row[0] if row else None}
        if kind=='games':
            from details import _game_art_paths
            logo,background=_game_art_paths(item_id)
            assigned.update({'Current Logo':logo,'Current Background':background})
        if kind in ('movies','shows'):
            from movie_cinematic import background_path
            assigned['Current Background']=background_path(item_id,kind)
        return assigned
    def assignment_labels(entry,assigned):
        paths={entry.get('path'),entry.get('origin_path')} - {None}
        return [label for label,path in assigned.items() if path and path in paths]
    def display():
        for child in gallery.winfo_children():child.destroy()
        photos.clear()
        visible=[(i,e) for i,e in enumerate(entries) if matches_filters(e)]
        selected['indices'].intersection_update(i for i,e in visible)
        if selected['index'] is not None and selected['index'] not in [i for i,e in visible]:
            selected['index']=None
            clear_preview()
        elif selected['index'] is None:
            clear_preview()
        if selected['index'] is not None:
            preview_details.set(artwork_file_details(entries[selected['index']]))
        if not visible:
            tk.Label(gallery,text='No artwork in this filter.',bg=BG,fg=MUTED).pack(pady=35)
        assigned=current_assignments()
        for pos,(i,e) in enumerate(visible):
            cell=tk.Frame(gallery,bg=accent if i in selected['indices'] else PANEL,padx=7,pady=7)
            cell.grid(row=pos//gallery_columns[0],column=pos%gallery_columns[0],padx=8,pady=8,sticky='n')
            photo=None
            if not e.get('missing'):
                with Image.open(io.BytesIO(e['raw'])) as im:
                    im.thumbnail((220,155),Image.Resampling.LANCZOS)
                    photo=ImageTk.PhotoImage(im.copy())
                photos.append(photo)
            btn=tk.Button(cell,image=photo or '',text='Missing image' if e.get('missing') else '',
                          bg=PANEL,fg=MUTED,relief='flat',command=lambda j=i:choose(j),cursor='hand2')
            def extend_selection(event,j=i):
                choose(j,extend=True)
                return 'break'
            btn.bind('<Control-Button-1>',extend_selection)
            btn.pack()
            tk.Label(cell,text=e['label'][:27],bg=cell['bg'],fg=TEXT).pack()
            tk.Label(cell,text=f"{e['w']} × {e['h']} · {e['shape']}",bg=cell['bg'],fg=TEXT).pack()
            if is_favourite(kind,item_id,e.get('path') or e.get('origin_path')):
                tk.Label(cell,text='★ Favourite',bg=cell['bg'],fg=TEXT).pack()
            roles=assignment_labels(e,assigned)
            roles=[label+' 🔒' if is_locked(kind,item_id,{'Current Cover':'cover_path','Current Logo':'logo_path','Current Background':'background_path'}[label]) else label for label in roles]
            if roles:
                tk.Label(cell,text='\n'.join(roles),bg=cell['bg'],fg=TEXT,
                         font=('Arial',9,'bold')).pack(pady=(4,0))
        status.set(f'{len(visible)} shown · {len(entries)} available · {len(selected["indices"])} selected')
    def choose(i,extend=False):
        if extend:
            if i in selected['indices']:
                selected['indices'].remove(i)
                if not selected['indices']:
                    selected['index']=None
                    clear_preview()
                    display()
                    return
                i=selected['index'] if selected['index'] in selected['indices'] else max(selected['indices'])
            else:
                selected['indices'].add(i)
        else:
            selected['indices']={i}
        selected['index']=i;e=entries[i]
        if e.get('missing'):
            preview_state['photo']=None
            selected_preview.configure(image='',text='This saved artwork file is missing.')
            preview_details.set(artwork_file_details(e))
            display()
            info.set('Use Collection actions → Relink missing image to choose a replacement.')
            return
        try:
            from add_game_metadata import preview_picture
            picture=preview_picture(e['raw'],get_setting('art_preview_background','Dark'),(620,150),upscale=False)
            preview_state['photo']=ImageTk.PhotoImage(picture)
            selected_preview.configure(image=preview_state['photo'],text='')
        except (OSError,ValueError,Image.DecompressionBombError):
            selected['indices'].discard(i)
            selected['index']=None
            clear_preview()
            display()
            info.set('This image could not be previewed. Choose another image.')
            return
        preview_details.set(artwork_file_details(e))
        info.set(f"Selected: {e['label']} — {e['w']} × {e['h']} ({e['shape']}). Original resolution will be preserved.")
        display()
    def reset_filters():
        favourites_only.set(False)
        filename_search.set('')
        shape.set('All')
        minimum_width.set('All sizes')
        role_filter.set('All roles')
        canvas.yview_moveto(0)
    filename_search.trace_add('write',lambda *_:display())
    favourites_only.trace_add('write',lambda *_:display())
    def filter_changed(key,variable):
        try:set_setting(key,variable.get())
        except Exception:
            info.set('Could not remember this filter. It still applies to this window.')
        display()
    for variable,key in [(shape,'artwork_filter_shape'),(minimum_width,'artwork_filter_width'),
                         (role_filter,'artwork_filter_role_'+kind)]:
        variable.trace_add('write',lambda *_,v=variable,k=key:filter_changed(k,v))
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
    win.bind('<Escape>',close_manager)
    def add_image(raw,w,h,ext,label,source,path=None,origin_path=None):
        digest=artwork_digest(raw)
        for i,entry in enumerate(entries):
            if entry.get('digest')==digest:
                if path:entry['path']=path
                if origin_path:entry['origin_path']=origin_path
                return i,False
        entries.append(dict(digest=digest,raw=raw,w=w,h=h,ext=ext,label=label,source=source,path=path,
                            origin_path=origin_path,shape=classify(w,h)))
        return len(entries)-1,True
    def load_saved():
        entries.clear();selected['index']=None;selected['indices'].clear()
        rows=connection.execute('SELECT image_path,width,height,source FROM artwork_library WHERE category=? AND item_id=? ORDER BY id DESC',(kind,item_id)).fetchall()
        seen=set()
        def load_path(path,w=0,h=0,source='Local file',registered=False):
            if not path or path in seen:return
            seen.add(path)
            try:
                raw=(PROJECT_ROOT/path).read_bytes()
                with Image.open(io.BytesIO(raw)) as im:
                    width,height=im.size;fmt=im.format;im.verify()
                if fmt not in ('JPEG','PNG','WEBP','BMP') or width*height>60_000_000:raise ValueError('Invalid image')
                add_image(raw,width,height,{'JPEG':'.jpg','PNG':'.png','WEBP':'.webp','BMP':'.bmp'}[fmt],
                          Path(path).name,source,path=path if registered else None,
                          origin_path=None if registered else path)
            except Exception:
                entries.append(dict(raw=None,digest=None,w=w or 0,h=h or 0,ext=Path(path).suffix,
                                    label=Path(path).name,source=source,path=path if registered else None,
                                    origin_path=None if registered else path,shape=classify(w or 0,h or 0),missing=True))
        for path,w,h,source in rows:load_path(path,w,h,source or 'Local file',True)
        for path in current_assignments().values():load_path(path)
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
        filenames=filedialog.askopenfilenames(parent=win,title='Choose Artwork Images',initialdir=import_folder('artwork'),
                    filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.bmp'),('All files','*.*')])
        if not filenames:return
        try:remember_import_folder('artwork',filenames)
        except Exception:pass
        added=[];rejected=[];duplicates=0
        for filename in filenames:
            try:
                raw=Path(filename).read_bytes()
                with Image.open(io.BytesIO(raw)) as im:
                    w,h=im.size;fmt=im.format
                    if fmt not in ('JPEG','PNG','WEBP','BMP'):raise ValueError('Use JPEG, PNG, WebP or BMP')
                    if w*h>60_000_000:raise ValueError('Image dimensions too large')
                    im.verify()
                index,is_new=add_image(raw,w,h,{'JPEG':'.jpg','PNG':'.png','WEBP':'.webp','BMP':'.bmp'}[fmt],Path(filename).name,'Local file')
                if is_new:added.append(index)
                else:duplicates+=1
            except Exception as exc:
                rejected.append(f'{Path(filename).name}: {exc}')
        if added:
            reset_filters()
            choose(added[-1])
            selected['indices']=set(added)
            display()
            info.set(f'{len(added)} images ready to review. Ctrl-click to adjust selection, then Save Selected.')
        if duplicates:
            messagebox.showinfo('Duplicate Artwork',f'{duplicates} exact duplicate(s) skipped. Existing images remain in the collection.',parent=win)
        if rejected:
            messagebox.showwarning('Some Images Not Added',
                                   f'{len(rejected)} image(s) could not be added.\n\n'+'\n'.join(rejected[:3]),parent=win)
    def full_preview():
        i=selected['index']
        if i is None:return
        e=entries[i]
        if e.get('missing'):
            messagebox.showinfo('Missing Artwork','Relink this image first.',parent=win);return
        popup=tk.Toplevel(win);popup.title(e['label']);popup.configure(bg=BG)
        polish_dialog(popup)
        popup.geometry('850x650')
        saved=get_setting('art_preview_background','Dark')
        mode=tk.StringVar(value=saved if saved in ('Dark','Checkerboard') else 'Dark')
        controls=tk.Frame(popup,bg=BG);controls.pack(fill='x',padx=10,pady=(10,0))
        tk.Label(controls,text='Preview background:',bg=BG,fg=TEXT).pack(side='left')
        choice=ttk.Combobox(controls,textvariable=mode,values=('Dark','Checkerboard'),state='readonly',width=16)
        choice.pack(side='left',padx=8)
        lbl=tk.Label(popup,bg=BG);lbl.pack(fill='both',expand=True,padx=10,pady=10)
        def render(event=None):
            from add_game_metadata import preview_picture
            lbl.image=ImageTk.PhotoImage(preview_picture(e['raw'],mode.get(),(800,520),upscale=False))
            lbl.configure(image=lbl.image)
            if event is not None:set_setting('art_preview_background',mode.get())
        choice.bind('<<ComboboxSelected>>',render);render()
        tk.Label(popup,text=f"{e['w']} × {e['h']} · {e['shape']}",bg=BG,fg=TEXT).pack(pady=10)
    def save_selected(make_cover):
        if make_cover and len(selected['indices'])>1:
            messagebox.showinfo('Choose One Image','Click one image to assign it as the cover.',parent=win)
            return
        i=selected['index']
        if i is None:messagebox.showinfo('Select Artwork','Choose an image first.',parent=win);return
        e=entries[i]
        if e.get('missing'):
            messagebox.showinfo('Missing Artwork','Relink this image first.',parent=win);return
        try:
            if e['path']:
                if make_cover:select_saved(kind,item_id,e['path'])
            else:
                saved_path=store(kind,item_id,e['raw'],e['w'],e['h'],e['ext'],e['source'],make_cover)
                e['path']=saved_path
            win._artwork_changed=True
            display()
            info.set('Artwork saved. You can keep choosing images or close this window when finished.')
        except Exception as exc:messagebox.showerror('Artwork Save Failed',str(exc),parent=win)
    def save_collection():
        indices=sorted(selected['indices'])
        if not indices:
            messagebox.showinfo('Select Artwork','Select one or more images first.',parent=win)
            return
        saved=already_saved=missing=0
        try:
            for i in indices:
                e=entries[i]
                if e.get('missing'):
                    missing+=1
                    continue
                if e['path']:
                    already_saved+=1
                    continue
                # Batch collection saves never replace assigned artwork.
                e['path']=store(kind,item_id,e['raw'],e['w'],e['h'],e['ext'],e['source'],set_cover=False)
                win._artwork_changed=True
                saved+=1
        except Exception as exc:
            display()
            messagebox.showerror('Artwork Save Failed',
                                 f'{saved} saved; {already_saved} already local.\n'
                                 f'Could not save {e["label"]}: {exc}\n\n'
                                 'Successful saves are kept. You can retry without saving them twice.',parent=win)
            return
        messagebox.showinfo('Artwork Saved',f'{saved} saved · {already_saved} already local · {missing} missing skipped.\n'
                           'Your assigned cover, logo and background were preserved.',parent=win)
        display()
        info.set(f'{saved} saved · {already_saved} already local · {missing} missing skipped. Continue choosing artwork or close when finished.')
    def set_role(role):
        if kind != 'games' and not (kind in ('movies','shows') and role=='background_path'): return
        if len(selected['indices'])>1:
            messagebox.showinfo('Choose One Image','Click one image to assign its artwork role.',parent=win)
            return
        i=selected['index']
        if i is None:
            messagebox.showinfo('Select Artwork','Select an image first.',parent=win);return
        try:
            require_unlocked(kind,item_id,role)
            e=entries[i]
            if e.get('missing'):raise ValueError('Relink this missing image first.')
            if not e['path']:
                e['path']=store(kind,item_id,e['raw'],e['w'],e['h'],e['ext'],e['source'],set_cover=False)
                win._artwork_changed=True
            if kind in ('movies','shows'):
                from movie_cinematic import set_background
                set_background(item_id,e['path'],kind)
            else:
                from details import _set_game_art
                _set_game_art(item_id,role,e['path'])
            win._artwork_changed=True
            display()
            info.set('Logo saved.' if role=='logo_path' else 'Background saved.')
        except Exception as exc: messagebox.showerror('Artwork',str(exc),parent=win)

    def remove_selected():
        if len(selected['indices'])>1:
            messagebox.showinfo('Choose One Image','Click one image to remove it. Batch selection is for saving.',parent=win)
            return
        i=selected['index']
        if i is None:
            messagebox.showinfo('Remove Artwork','Select an image first.',parent=win);return
        e=entries[i]
        if not e['path']:
            entries.pop(i);selected['index']=None;selected['indices'].clear();display();return
        path=e['path']
        refs=[]
        if connection.execute(f'SELECT 1 FROM {kind} WHERE id=? AND cover_path=?',(item_id,path)).fetchone():
            refs.append('cover')
        if kind=='games':
            from details import _game_art_paths
            logo,bg=_game_art_paths(item_id)
            if path==logo:refs.append('logo')
            if path==bg:refs.append('background')
        if kind in ('movies','shows'):
            from movie_cinematic import background_path
            if path==background_path(item_id,kind):refs.append('background')
        try:
            for role,label in [('cover_path','cover'),('logo_path','logo'),('background_path','background')]:
                if label in refs:require_unlocked(kind,item_id,role)
        except ValueError as exc:
            messagebox.showwarning('Artwork Locked',str(exc),parent=win);return
        note=('This image is currently assigned as '+', '.join(refs)+'. Its assignment will be cleared.\n\n') if refs else ''
        if not messagebox.askyesno('Delete Saved Artwork',note+'Permanently delete this saved image from the collection?',parent=win):return
        try:
            with connection:
                connection.execute('DELETE FROM artwork_library WHERE category=? AND item_id=? AND image_path=?',(kind,item_id,path))
                if 'cover' in refs:
                    connection.execute(f'UPDATE {kind} SET cover_path=NULL WHERE id=? AND cover_path=?',(item_id,path))
                if kind in ('movies','shows') and 'background' in refs:
                    connection.execute(f'UPDATE {kind} SET background_path=NULL WHERE id=? AND background_path=?',(item_id,path))
                if kind=='games':
                    from details import _set_game_art
                    if 'logo' in refs:_set_game_art(item_id,'logo_path',None)
                    if 'background' in refs:_set_game_art(item_id,'background_path',None)
            win._artwork_changed=True
            # Only delete managed collection files; never delete arbitrary imported files.
            absolute=(PROJECT_ROOT/path).resolve()
            if absolute.is_relative_to(ART_ROOT.resolve()) and not connection.execute(
                'SELECT 1 FROM artwork_library WHERE image_path=? LIMIT 1',(path,)).fetchone():
                absolute.unlink(missing_ok=True)
            entries.pop(i);selected['index']=None;selected['indices'].clear();display()
            win._artwork_changed=True
        except Exception as exc:messagebox.showerror('Delete Failed',str(exc),parent=win)

    def clear_assignment(role):
        try:
            require_unlocked(kind,item_id,role)
            label={'cover_path':'Current Cover','logo_path':'Current Logo',
                   'background_path':'Current Background'}.get(role)
            if label is None or (kind!='games' and role!='cover_path' and not (kind in ('movies','shows') and role=='background_path')):return
            path=current_assignments().get(label)
            # Keep older assigned images available in the collection after clearing.
            for e in entries:
                if path and e.get('origin_path')==path and not e['path'] and not e.get('missing'):
                    e['path']=store(kind,item_id,e['raw'],e['w'],e['h'],e['ext'],e['source'],set_cover=False)
                    win._artwork_changed=True
            if role=='cover_path':
                with connection:
                    connection.execute(f'UPDATE {kind} SET cover_path=NULL WHERE id=?',(item_id,))
            elif kind in ('movies','shows') and role=='background_path':
                from movie_cinematic import set_background
                set_background(item_id,None,kind)
            elif kind=='games' and role in ('logo_path','background_path'):
                from details import _set_game_art
                _set_game_art(item_id,role,None)
            else:return
            win._artwork_changed=True
            display()
            info.set('Artwork assignment cleared. No image files were deleted.')
        except Exception as exc:messagebox.showerror('Artwork',str(exc),parent=win)

    def toggle_protection(role):
        try:
            assigned=current_assignments()
            label={'cover_path':'Current Cover','logo_path':'Current Logo','background_path':'Current Background'}[role]
            locked=is_locked(kind,item_id,role)
            if not locked and not assigned.get(label):
                messagebox.showinfo('Artwork Protection','Assign artwork to this role first.',parent=win);return
            set_locked(kind,item_id,role,not locked)
            display()
            info.set(label+(' unlocked.' if locked else ' locked against replacement.'))
        except Exception as exc:messagebox.showerror('Artwork Protection',str(exc),parent=win)
    def toggle_favourite():
        i=selected['index']
        if i is None or len(selected['indices'])!=1:
            messagebox.showinfo('Choose One Image','Select one image first.',parent=win);return
        try:
            e=entries[i];path=e.get('path') or e.get('origin_path')
            if not path:
                if e.get('missing'):raise ValueError('Relink this image first.')
                path=store(kind,item_id,e['raw'],e['w'],e['h'],e['ext'],e['source'],set_cover=False)
                e['path']=path;win._artwork_changed=True
            value=not is_favourite(kind,item_id,path)
            set_favourite(kind,item_id,path,value)
            display();info.set('Added to favourites.' if value else 'Removed from favourites.')
        except Exception as exc:messagebox.showerror('Artwork Favourite',str(exc),parent=win)
    def relink_selected():
        i=selected['index']
        if i is None or len(selected['indices'])!=1:
            messagebox.showinfo('Choose One Image','Select one missing image first.',parent=win);return
        e=entries[i]
        if not e.get('missing'):
            messagebox.showinfo('Relink Artwork','This image is available. Select a missing image to repair.',parent=win);return
        filename=filedialog.askopenfilename(parent=win,title='Relink Missing Artwork',initialdir=import_folder('artwork'),
                                           filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.bmp'),('All files','*.*')])
        if not filename:return
        try:
            try:remember_import_folder('artwork',[filename])
            except Exception:pass
            path=relink_artwork(kind,item_id,e.get('path') or e.get('origin_path'),filename)
            win._artwork_changed=True
            reset_filters();load_saved()
            index=next((j for j,entry in enumerate(entries) if entry.get('path')==path),None)
            if index is not None:choose(index)
            info.set('Artwork relinked and copied locally. Original files were preserved.')
        except Exception as exc:messagebox.showerror('Relink Failed',str(exc),parent=win)

    actions=tk.Frame(win,bg=BG);actions.pack(fill='x',padx=18,pady=(8,10),before=outer)
    for label,command in [('Add from PC',add_local),('Full Preview',full_preview),('Save Selected',save_collection)]:
        tk.Button(actions,text=label,command=command,bg=accent if label=='Set as Cover' else PANEL_ALT,fg=TEXT,relief='flat',padx=12,pady=8).pack(side='left',padx=(0,8))
    role_actions=tk.Frame(win,bg=BG);role_actions.pack(fill='x',padx=18,pady=(0,12),before=outer)
    assign_button=tk.Menubutton(actions,text='Assign artwork ▾',bg=PANEL_ALT,fg=TEXT,
                                relief='flat',padx=12,pady=8,cursor='hand2')
    assign_button.pack(side='left',padx=(0,8))
    assign_menu=tk.Menu(assign_button,tearoff=False,bg=PANEL_ALT,fg=TEXT,
                        activebackground=accent,activeforeground='white')
    assign_button.configure(menu=assign_menu)
    assign_menu.add_command(label='Set as Cover',command=lambda:save_selected(True))
    if kind=='games':
        for label,role in [('Set as Logo','logo_path'),('Set as Background','background_path')]:
            assign_menu.add_command(label=label,command=lambda r=role:set_role(r))
    if kind in ('movies','shows'):
        assign_menu.add_command(label='Set as Background',command=lambda:set_role('background_path'))
    clear_menu=tk.Menu(assign_menu,tearoff=False,bg=PANEL_ALT,fg=TEXT,
                       activebackground=accent,activeforeground='white')
    clear_menu.add_command(label='Clear Cover',command=lambda:clear_assignment('cover_path'))
    if kind=='games':
        for label,role in [('Clear Logo','logo_path'),('Clear Background','background_path')]:
            clear_menu.add_command(label=label,command=lambda r=role:clear_assignment(r))
    if kind in ('movies','shows'):
        clear_menu.add_command(label='Clear Background',command=lambda:clear_assignment('background_path'))
    protection_menu=tk.Menu(assign_menu,tearoff=False,bg=PANEL_ALT,fg=TEXT,
                            activebackground=accent,activeforeground='white')
    for label,role in [('Cover','cover_path')]+([('Logo','logo_path'),('Background','background_path')] if kind=='games' else [('Background','background_path')] if kind in ('movies','shows') else []):
        protection_menu.add_command(label='Lock / Unlock '+label,command=lambda r=role:toggle_protection(r))
    assign_menu.add_cascade(label='Protection',menu=protection_menu)
    assign_menu.add_separator()
    assign_menu.add_cascade(label='Clear assignment',menu=clear_menu)
    collection_button=tk.Menubutton(role_actions,text='Collection actions ▾',bg=PANEL_ALT,fg=TEXT,
                                    relief='flat',padx=10,pady=8)
    collection_button.pack(side='left',padx=(0,8))
    collection_menu=tk.Menu(collection_button,tearoff=False,bg=PANEL_ALT,fg=TEXT,
                            activebackground=accent,activeforeground='white')
    collection_menu.add_command(label='Favourite / Unfavourite',command=toggle_favourite)
    collection_menu.add_command(label='Relink missing image',command=relink_selected)
    collection_button.configure(menu=collection_menu)
    tk.Button(role_actions,text='Delete Image',command=remove_selected,bg='#7e303c',fg=TEXT,
              relief='flat',padx=10,pady=8).pack(side='left',padx=(0,5))
    tk.Button(actions,text='Close',command=close_manager,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=12,pady=8).pack(side='right')
