"""Multi-provider metadata finder with explicit, per-field import confirmation."""
from window_style import install as polish_dialog
import html
import json
import time
import urllib.error
import re
import threading
import urllib.parse
import urllib.request
import uuid
import tkinter as tk
from tkinter import ttk, messagebox
from database import PROJECT_ROOT, connection, get_setting, set_setting
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED

HEADERS = {'User-Agent': 'EntertainmentTracker/2.0 (personal metadata lookup)', 'Accept': 'application/json'}
_CACHE = {}
_LAST_GOOGLE_REQUEST = [0.0]
FIELDS = {
    'games': [('description','Description'), ('release_year','Release year'), ('release_date','Release date'), ('genre','Genre'), ('developer','Developer'), ('publisher','Publisher'), ('game_modes','Game modes'), ('age_rating','Age rating'), ('cover_path','Cover art')],
    'movies': [('description','Description'), ('release_year','Release year'), ('director','Director'), ('cast_members','Cast'), ('genre','Genre'), ('cover_path','Cover art')],
    'shows': [('description','Description'), ('release_year','Release year'), ('network','Network'), ('genre','Genre'), ('cover_path','Cover art')],
    'books': [('description','Description'), ('author','Author'), ('release_year','Release year'), ('publisher','Publisher'), ('isbn','ISBN'), ('page_count','Pages'), ('genre','Genre'), ('cover_path','Cover art')],
}

def get_json(url, headers=None):
    request = urllib.request.Request(url, headers=headers or HEADERS)
    now = time.monotonic()
    cached = _CACHE.get(url)
    if cached and now - cached[0] < 900:
        return cached[1]
    if 'www.googleapis.com/books/' in url:
        delay = 2.0 - (now - _LAST_GOOGLE_REQUEST[0])
        if delay > 0: time.sleep(delay)
        _LAST_GOOGLE_REQUEST[0] = time.monotonic()
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                data = json.load(response)
            _CACHE[url] = (time.monotonic(), data)
            return data
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                if attempt < 2:
                    retry = exc.headers.get('Retry-After', '')
                    try: wait = min(12.0, max(2.0, float(retry)))
                    except ValueError: wait = 3.0 * (attempt + 1)
                    time.sleep(wait)
                    continue
                raise RuntimeError('Google Books rate limit reached (HTTP 429). Please try again later, or select Open Library.') from exc
            if exc.code in (401, 403) and 'themoviedb.org' in url:
                raise RuntimeError('TMDB rejected the API token. Paste a valid TMDB API Read Access Token.') from exc
            raise

def plain(value):
    return html.unescape(re.sub(r'<[^>]+>', '', str(value or ''))).strip()

def result(source, title, subtitle='', **fields):
    return dict(source=source, title=title, subtitle=str(subtitle or ''), **fields)

def providers(kind, token=''):
    options = {'games':['Steam','Wikipedia'], 'movies':['Apple iTunes','Wikipedia'],
               'shows':['TVmaze','Wikipedia'], 'books':['Open Library','Google Books','Wikipedia']}[kind]
    if kind in ('movies','shows'):
        options.append('TMDB')
    return options

def search_provider(kind, title, provider, tmdb_token=''):
    q = urllib.parse.quote(title)
    if provider == 'Wikipedia':
        # Public MediaWiki API: no API key required. Useful as an additional
        # fallback source when the category's specialist provider has no match.
        data = get_json('https://en.wikipedia.org/w/api.php?action=query'
            '&generator=search&gsrsearch='+q+'&gsrlimit=12'
            '&prop=pageimages%7Cextracts&piprop=thumbnail&pithumbsize=700'
            '&exintro=1&explaintext=1&exsentences=6&format=json')
        pages = (data.get('query') or {}).get('pages') or {}
        output = []
        for page in sorted(pages.values(), key=lambda x:x.get('index',999)):
            output.append(result(provider, page.get('title',''), 'Wikipedia',
                description=plain(page.get('extract','')),
                cover=(page.get('thumbnail') or {}).get('source','')))
        return output
    if provider == 'Google Books':
        data = get_json('https://www.googleapis.com/books/v1/volumes?q='+q+'&maxResults=15')
        output = []
        for entry in data.get('items', []):
            info = entry.get('volumeInfo') or {}
            isbn = next((i.get('identifier') for i in info.get('industryIdentifiers', []) if i.get('type')=='ISBN_13'), '')
            cover = (info.get('imageLinks') or {}).get('thumbnail', '').replace('http:', 'https:')
            output.append(result(provider, info.get('title',''), ', '.join(info.get('authors', [])),
                description=plain(info.get('description')), author=', '.join(info.get('authors', [])),
                release_year=str(info.get('publishedDate',''))[:4], publisher=info.get('publisher',''),
                isbn=isbn, page_count=info.get('pageCount'), genre=', '.join(info.get('categories', [])),
                cover=cover))
        return output
    if provider == 'Open Library':
        data = get_json(f'https://openlibrary.org/search.json?title={q}&limit=15&fields=key,title,author_name,first_publish_year,cover_i,isbn,publisher,number_of_pages_median')
        return [result(provider, x.get('title',''), ', '.join(x.get('author_name',[])[:2]),
            author=', '.join(x.get('author_name',[])[:3]), release_year=x.get('first_publish_year'),
            publisher=', '.join(x.get('publisher',[])[:2]), isbn=next(iter(x.get('isbn',[])),''),
            page_count=x.get('number_of_pages_median'),
            cover=(f'https://covers.openlibrary.org/b/id/{x["cover_i"]}-L.jpg' if x.get('cover_i') else ''),
            detail=f'https://openlibrary.org{x["key"]}') for x in data.get('docs', [])]
    if provider == 'TVmaze':
        data = get_json(f'https://api.tvmaze.com/search/shows?q={q}')
        return [result(provider, x['show'].get('name',''), str(x['show'].get('premiered') or '')[:4],
            description=plain(x['show'].get('summary')), release_year=str(x['show'].get('premiered') or '')[:4],
            genre=', '.join(x['show'].get('genres') or []),
            network=((x['show'].get('network') or x['show'].get('webChannel') or {}).get('name','')),
            cover=(x['show'].get('image') or {}).get('original') or '') for x in data]
    if provider == 'Apple iTunes':
        data = get_json(f'https://itunes.apple.com/search?term={q}&entity=movie&limit=15')
        return [result(provider, x.get('trackName',''), str(x.get('releaseDate',''))[:4],
            description=plain(x.get('longDescription') or x.get('shortDescription')),
            release_year=str(x.get('releaseDate',''))[:4], genre=x.get('primaryGenreName',''),
            cover=x.get('artworkUrl100','').replace('100x100bb','600x600bb')) for x in data.get('results', [])]
    if provider == 'Steam':
        data = get_json(f'https://store.steampowered.com/api/storesearch/?term={q}&l=english&cc=gb')
        return [result(provider, x.get('name',''), 'Steam',
            cover=f'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{x["id"]}/library_600x900.jpg',
            detail=str(x['id'])) for x in data.get('items', [])]
    if provider == 'TMDB':
        if not tmdb_token.strip():
            raise ValueError('TMDB needs an API Read Access Token. Paste it in the token box before searching.')
        section = 'movie' if kind=='movies' else 'tv'
        headers = dict(HEADERS, Authorization='Bearer '+tmdb_token.strip())
        data = get_json(f'https://api.themoviedb.org/3/search/{section}?query={q}&language=en-GB',headers)
        out=[]
        for x in data.get('results', [])[:15]:
            year = str(x.get('release_date') or x.get('first_air_date') or '')[:4]
            out.append(result(provider,x.get('title') or x.get('name') or '',year,
                description=plain(x.get('overview')),release_year=year,
                cover=('https://image.tmdb.org/t/p/w780'+x['poster_path'] if x.get('poster_path') else ''),
                detail=str(x['id']),tmdb_type=section))
        return out
    raise ValueError('Unknown provider')

def enrich(kind, item, tmdb_token=''):
    if item['source']=='Open Library' and item.get('detail'):
        try:
            data=get_json(item['detail']+'.json')
            value=data.get('description','')
            item['description']=plain(value.get('value','') if isinstance(value,dict) else value)
        except Exception: pass
    elif item['source']=='Steam' and item.get('detail'):
        try:
            data=get_json('https://store.steampowered.com/api/appdetails?appids='+item['detail']+'&l=english&cc=gb')
            info=data.get(item['detail'],{}).get('data') or {}
            item['description']=plain(info.get('short_description'))
            item['release_year']=re.search(r'\b(19|20)\d{2}\b',str((info.get('release_date') or {}).get('date',''))).group(0) if re.search(r'\b(19|20)\d{2}\b',str((info.get('release_date') or {}).get('date',''))) else ''
            # Steam appdetails contains the factual fields, when published.
            # Keep the precise release date only when the provider supplies an
            # unambiguous day/month/year. Never manufacture missing fields.
            from datetime import datetime
            raw_date = str((info.get('release_date') or {}).get('date') or '').strip()
            if not (info.get('release_date') or {}).get('coming_soon'):
                for pattern in ('%d %b, %Y', '%d %B, %Y', '%b %d, %Y',
                                '%B %d, %Y', '%d %b %Y', '%d %B %Y'):
                    try:
                        item['release_date'] = datetime.strptime(raw_date, pattern).date().isoformat()
                        break
                    except ValueError:
                        continue
            item['genre'] = ', '.join(str(x.get('description', '')).strip()
                                      for x in info.get('genres', []) if x.get('description'))
            item['developer'] = ', '.join(info.get('developers') or [])
            item['publisher'] = ', '.join(info.get('publishers') or [])
            modes = ('Single-player', 'Multi-player', 'Co-op', 'Online Co-op',
                     'Local Co-op', 'Shared/Split Screen', 'PvP', 'Online PvP')
            categories = [str(x.get('description') or '') for x in info.get('categories', [])]
            item['game_modes'] = ', '.join(mode for mode in modes if mode in categories)
            ratings = info.get('ratings') or {}
            # Steam's ratings object is keyed by rating authority (e.g. esrb,
            # pegi). Preserve that authority instead of importing bare "M".
            for authority in ('pegi', 'esrb'):
                entry = ratings.get(authority) or ratings.get(authority.upper())
                if not isinstance(entry, dict) or not entry.get('rating'):
                    continue
                rating = str(entry['rating']).strip()
                if authority == 'pegi':
                    match = re.search(r'\b(3|7|12|16|18)\b', rating)
                    if match:
                        item['age_rating'] = 'PEGI ' + match.group(1)
                        break
                else:
                    item['age_rating'] = 'ESRB ' + rating
                    break
            item['cover']=info.get('header_image') or item.get('cover','')
        except Exception: pass
    elif item['source']=='TMDB' and tmdb_token.strip() and item.get('detail'):
        try:
            section=item['tmdb_type']; headers=dict(HEADERS,Authorization='Bearer '+tmdb_token.strip())
            data=get_json(f'https://api.themoviedb.org/3/{section}/{item["detail"]}?append_to_response=credits&language=en-GB',headers)
            item['genre']=', '.join(x['name'] for x in data.get('genres',[]))
            if section=='movie':
                item['director']=', '.join(x['name'] for x in (data.get('credits') or {}).get('crew',[]) if x.get('job')=='Director')
                item['cast_members']=', '.join(x['name'] for x in (data.get('credits') or {}).get('cast',[])[:8])
            else:
                item['network']=', '.join(x['name'] for x in data.get('networks',[]))
        except Exception: pass
    return item

def current_fields(kind, item_id):
    columns=[row[1] for row in connection.execute(f'PRAGMA table_info({kind})')]
    row=connection.execute(f'SELECT * FROM {kind} WHERE id=?',(item_id,)).fetchone()
    if row is None: raise ValueError('Entry not found')
    return dict(zip(columns,row))

def save_fields(kind, item_id, item, selected):
    if kind not in FIELDS: raise ValueError('Invalid category')
    existing=current_fields(kind,item_id)
    updates={}
    cover_file=None
    for field in selected:
        if field not in dict(FIELDS[kind]) or field not in existing: continue
        value=item.get('cover') if field=='cover_path' else item.get(field)
        if value is None or str(value).strip()=='': continue
        if field in ('release_year','page_count'):
            try: value=int(value)
            except (ValueError,TypeError): continue
        if field=='cover_path':
            from artwork_preferences import require_unlocked
            require_unlocked(kind,item_id,'cover_path')
            if not str(value).startswith('https://'): raise ValueError('Cover must use HTTPS')
            request=urllib.request.Request(value,headers=HEADERS)
            with urllib.request.urlopen(request,timeout=15) as response:
                mime=response.headers.get('Content-Type','').lower()
                if not mime.startswith('image/'): raise ValueError('Cover URL did not return an image')
                image=response.read(8*1024*1024+1)
            if len(image)>8*1024*1024 or not image: raise ValueError('Invalid or oversized cover')
            from PIL import Image
            import io
            with Image.open(io.BytesIO(image)) as picture:
                picture.verify()
            folder=PROJECT_ROOT/'assets'/'covers'/kind
            folder.mkdir(parents=True,exist_ok=True)
            suffix='.png' if 'png' in mime else '.webp' if 'webp' in mime else '.jpg'
            cover_file=folder/f'{item_id}_multi_{uuid.uuid4().hex[:12]}{suffix}'
            cover_file.write_bytes(image)
            value=cover_file.relative_to(PROJECT_ROOT).as_posix()
        updates[field]=value
    if not updates:return 0
    try:
        with connection:
            connection.execute(f'UPDATE {kind} SET '+', '.join(f'{key}=?' for key in updates)+' WHERE id=?',(*updates.values(),item_id))
    except Exception:
        if cover_file:cover_file.unlink(missing_ok=True)
        raise
    return len(updates)

def open_finder(parent, kind, item_id, title, accent, on_saved=None):
    win=tk.Toplevel(parent);polish_dialog(win)
    win.title('Multi-Source Metadata Finder');win.geometry('1000x790');win.minsize(750,610)
    win.configure(bg=BG);win.transient(parent.winfo_toplevel())
    previous_grab=win.grab_current()
    changes={'saved':False,'closed':False}
    def close_finder(event=None):
        if changes['closed']:
            return 'break'
        # Include artwork saved in a child manager that is still open.
        changes['saved']=changes['saved'] or any(
            getattr(child,'_artwork_changed',False) for child in win.winfo_children())
        changes['closed']=True
        win.destroy()
        if previous_grab is not None:
            try:
                if previous_grab.winfo_exists():previous_grab.grab_set()
            except tk.TclError:pass
        if changes['saved'] and on_saved:on_saved()
        return 'break'
    win.protocol('WM_DELETE_WINDOW',close_finder)
    win.bind('<Escape>',close_finder)
    win.grab_set()
    tk.Label(win,text='Multi-Source Metadata Finder',bg=BG,fg=TEXT,font=('Arial',19,'bold')).pack(anchor='w',padx=20,pady=(16,8))
    toolbar=tk.Frame(win,bg=BG);toolbar.pack(fill='x',padx=20)
    query=tk.StringVar(value=title)
    token=tk.StringVar(value=get_setting('tmdb_token',''))
    tk.Entry(toolbar,textvariable=query,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT,relief='flat',font=('Arial',12)).pack(side='left',fill='x',expand=True,ipady=7)
    status=tk.StringVar(value=('Search Steam for game details, then review fields before importing.' if kind=='games' else 'Select a source, search, then review each field before importing.'))
    token_storage_error={'value':False}
    def save_token(*_):
        try:
            # Keep exactly what was entered, including an intentionally empty value.
            set_setting('tmdb_token',token.get())
        except Exception:
            token_storage_error['value']=True
            status.set('The TMDB token could not be saved locally. Check that the data folder is writable.')
        else:
            if token_storage_error['value']:
                status.set('TMDB token saved locally.')
            token_storage_error['value']=False
    if kind in ('movies','shows'):
        token.trace_add('write',save_token)
    tk.Label(win,textvariable=status,bg=BG,fg=MUTED,anchor='w',wraplength=940).pack(fill='x',padx=20,pady=8)
    sourcebar=tk.Frame(win,bg=BG);sourcebar.pack(fill='x',padx=20)
    tk.Label(sourcebar,text='Source:',bg=BG,fg=TEXT).pack(side='left')
    source=tk.StringVar(value=providers(kind)[0]);picker=ttk.Combobox(sourcebar,textvariable=source,values=providers(kind),state='readonly',width=18)
    picker.pack(side='left',padx=8)
    # A dark readonly combobox can appear disabled on some Windows themes.
    style=ttk.Style(win)
    style.configure('MetadataSource.TCombobox',
                    fieldbackground=PANEL_ALT, background=PANEL_ALT,
                    foreground=TEXT, arrowcolor=TEXT)
    picker.configure(style='MetadataSource.TCombobox')
    picker.current(0)
    if kind in ('movies','shows'):
        tk.Label(sourcebar,text='TMDB token (saved automatically):',bg=BG,fg=MUTED).pack(side='left',padx=(12,5))
        entry=tk.Entry(sourcebar,textvariable=token,show='•',bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT,relief='flat')
        entry.pack(side='left',fill='x',expand=True)
        # TMDB remains visible even without a token; searching explains the requirement.
    def source_changed(_=None):
        status.set('Source: '+source.get()+'. Click Search to look up this provider.')
    picker.bind('<<ComboboxSelected>>',source_changed)
    results=ttk.Treeview(win,columns=('title','year','source'),show='headings',height=6,selectmode='browse')
    for key,width in (('title',490),('year',130),('source',160)):
        results.heading(key,text=key.title());results.column(key,width=width)
    results.pack(fill='both',expand=False,padx=20,pady=(10,5))
    tk.Label(win,text='FIELD-BY-FIELD PREVIEW — tick only what you want to replace',bg=BG,fg=TEXT,font=('Arial',10,'bold')).pack(anchor='w',padx=20,pady=(12,5))
    frame=tk.Frame(win,bg=PANEL);frame.pack(fill='both',expand=True,padx=20)
    canvas=tk.Canvas(frame,bg=PANEL,highlightthickness=0)
    scrollbar=ttk.Scrollbar(frame,orient='vertical',command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
    inner=tk.Frame(canvas,bg=PANEL);window_id=canvas.create_window(0,0,window=inner,anchor='nw')
    inner.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window_id,width=e.width))
    items=[];selected={'index':None};busy={'value':False};checks={}
    def background(work,done):
        def run():
            try:value,error=work(),None
            except Exception as exc:value,error=None,str(exc)
            try:win.after(0,lambda:done(value,error))
            except RuntimeError:pass
        threading.Thread(target=run,daemon=True).start()
    def show_fields(item):
        for widget in inner.winfo_children():widget.destroy()
        checks.clear()
        existing=current_fields(kind,item_id)
        for key,label in FIELDS[kind]:
            incoming=item.get('cover') if key=='cover_path' else item.get(key)
            if incoming is None or str(incoming).strip()=='':continue
            if key not in existing:continue
            row=tk.Frame(inner,bg=PANEL);row.pack(fill='x',padx=10,pady=5)
            variable=tk.BooleanVar(value=not bool(existing.get(key)))
            checks[key]=variable
            tk.Checkbutton(row,text=label,variable=variable,bg=PANEL,fg=TEXT,selectcolor=PANEL_ALT,
                           activebackground=PANEL).pack(anchor='w')
            old=str(existing.get(key) or '(empty)');new=str(incoming)
            if len(old)>260:old=old[:260]+'…'
            if len(new)>450:new=new[:450]+'…'
            tk.Label(row,text='Current: '+old,bg=PANEL,fg=MUTED,wraplength=830,justify='left',anchor='w').pack(fill='x',padx=23)
            tk.Label(row,text='New: '+new,bg=PANEL,fg=TEXT,wraplength=830,justify='left',anchor='w').pack(fill='x',padx=23)
        if not checks:tk.Label(inner,text='No supported fields supplied by this result.',bg=PANEL,fg=MUTED).pack(pady=12)
    def do_search():
        if busy['value']:return
        title=query.get().strip()
        if not title:status.set('Enter a title first.');return
        busy['value']=True;status.set('Searching '+source.get()+'…')
        results.delete(*results.get_children());items.clear();selected['index']=None
        for w in inner.winfo_children():w.destroy()
        checks.clear()
        def done(value,error):
            busy['value']=False
            if not win.winfo_exists():return
            if error:status.set('Search failed: '+error);return
            items.extend(value)
            for i,item in enumerate(items):results.insert('','end',iid=str(i),values=(item['title'],item['subtitle'],item['source']))
            status.set(f'{len(items)} matches from {source.get()}. Choose the correct edition or title.')
        background(lambda:search_provider(kind,title,source.get(),token.get()),done)
    def chosen(_=None):
        selection=results.selection()
        if not selection:return
        index=int(selection[0]);selected['index']=index
        show_fields(items[index]);status.set('Loading available details…')
        def done(value,error):
            if not win.winfo_exists() or selected['index']!=index:return
            if value:items[index]=value;show_fields(value)
            status.set('Review current vs new values. Only checked fields will be imported.')
        background(lambda:enrich(kind,dict(items[index]),token.get()),done)
    results.bind('<<TreeviewSelect>>',chosen)
    def apply():
        index=selected['index']
        if index is None:messagebox.showinfo('Select Result','Choose a search result first.',parent=win);return
        chosen_fields=[field for field,var in checks.items() if var.get()]
        if not chosen_fields:messagebox.showinfo('No Changes','Tick at least one field to import.',parent=win);return
        if not messagebox.askyesno('Confirm Import',f'Import {len(chosen_fields)} selected field(s) from {items[index]["source"]}?\nExisting checked fields will be replaced.',parent=win):return
        try:count=save_fields(kind,item_id,items[index],chosen_fields)
        except Exception as exc:messagebox.showerror('Import Failed',str(exc),parent=win);return
        if count:
            changes['saved']=True
            show_fields(items[index])
            status.set(f'{count} field(s) imported and saved locally. Continue searching or close when finished.')
        else:status.set('No supported fields could be imported.')
    tk.Button(toolbar,text='Search',command=do_search,bg=accent,fg='white',relief='flat',padx=16,pady=7).pack(side='left',padx=(10,0))
    bottom=tk.Frame(win,bg=BG);bottom.pack(fill='x',padx=20,pady=12)
    def artwork():
        index=selected['index']
        if index is None:messagebox.showinfo('Select Result','Choose a result first.',parent=win);return
        from artwork_manager import open_manager,options
        item=items[index]
        def artwork_saved():
            changes['saved']=True
            current=selected['index']
            if current is not None:show_fields(items[current])
            status.set('Artwork changes saved. Continue importing metadata or close when finished.')
        open_manager(win,kind,item_id,item['title'],accent,results=options(kind,item),on_saved=artwork_saved)
    tk.Button(bottom,text='Artwork Collection…',command=artwork,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=10,pady=8).pack(side='left')
    tk.Button(bottom,text='Close',command=close_finder,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=16,pady=8).pack(side='right')
    tk.Button(bottom,text='Import Checked Fields',command=apply,bg=accent,fg='white',relief='flat',padx=14,pady=8).pack(side='right',padx=10)
    win.after(100,do_search)
