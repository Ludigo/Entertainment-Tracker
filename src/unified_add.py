"""Single-window collection drafts. Only Save writes collection rows or artwork."""
import copy
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from database import connection, get_setting, set_setting
from rich_details import FIELDS, parse_values, InvalidField
from theme import PANEL, PANEL_ALT, TEXT, MUTED
from window_style import install
from utils import format_time
from add_game_metadata import normalise_match, image_digest

LABELS = {'games':'Game', 'movies':'Movie', 'shows':'Show', 'books':'Book'}


def duplicate_items(kind, values):
    if kind not in (*LABELS, 'cds'):
        raise ValueError('Unknown category')
    columns = {'games':'platform', 'books':'author,isbn', 'cds':'artist',
               'movies':'release_year', 'shows':'season,release_year'}[kind]
    result = []
    for row in connection.execute(f'SELECT id,name,{columns} FROM {kind}'):
        same_title = normalise_match(row[1]) == normalise_match(values['name'])
        if kind == 'books':
            isbn = lambda value: ''.join(c for c in str(value or '').upper() if c.isalnum())
            same_isbn = bool(isbn(values.get('isbn')) and isbn(values.get('isbn')) == isbn(row[3]))
            same_author = not values.get('author') or not row[2] or normalise_match(row[2]) == normalise_match(values['author'])
            match = same_isbn or (same_title and same_author)
        elif kind in ('games','cds'):
            key = 'platform' if kind == 'games' else 'artist'
            match = same_title and (not values.get(key) or not row[2] or normalise_match(row[2]) == normalise_match(values[key]))
        elif kind == 'shows':
            match = same_title and row[2] == values['season'] and (not values.get('release_year') or not row[3] or row[3] == values['release_year'])
        else:
            match = same_title and (not values.get('release_year') or not row[2] or row[2] == values['release_year'])
        if match: result.append(row)
    return result


def create_item(kind, raw, stage):
    values = parse_values(kind, raw)
    if kind == 'games':
        from add_game_metadata import create_game
        fields = ('name','platform','playtime','price_paid','completed','backlog','started','description')
        return create_game(tuple(values[k] for k in fields), values, stage['cover'],
                           stage['extras'], stage['locks']['cover_path'],
                           {'background_path':stage['background'], 'logo_path':stage.get('logo')}, stage['locks'])
    from add_media_metadata import create_media
    item_id = create_media(kind, raw, stage['cover'], stage['background'], stage['extras'], lock_roles=stage['locks'])
    return item_id


def provider_details(kind, item, token='', season=None):
    """Metadata arrives independently of image bytes; no collection writes."""
    if item.get('source') == 'TMDB' and kind in ('movies','shows'):
        from add_media_metadata import load_tmdb
        return load_tmdb(kind, dict(item), token, season, download_artwork=False)
    from provider_artwork import enrich_with_artwork
    from artwork_manager import options
    item = enrich_with_artwork(kind, copy.deepcopy(item), token)
    fields = {key:item[key] for key,_,_ in FIELDS[kind] if item.get(key) is not None}
    fields['name'] = item.get('title','')
    if kind == 'games' and item.get('source') == 'Steam': fields['platform'] = 'PC'
    if isinstance(fields.get('runtime'), (int,float)): fields['runtime'] = format_time(fields['runtime'])
    return {'fields':fields, 'image_options':options(kind,item), 'seasons':[],
            'warning':item.get('artwork_warning','')}


class ArtworkDraft:
    def __init__(self, editor, parent, game=False):
        self.editor=editor;self.photos={};self.parent=parent
        self.roles=['cover','background']+(['logo'] if game else [])
        from draft_artwork_ui import build_artwork_tab
        self.locks={role+'_path':tk.IntVar(master=editor.win,value=int(editor.stage['locks'][role+'_path'])) for role in self.roles}
        self.table,self.info=build_artwork_tab(editor.win,parent,LABELS[editor.kind],self.roles,
            self.local,self.preview,self.preview_role,self.clear,self.assign,self.locks,self.lock_changed)

    def lock_changed(self):
        self.editor.stage['locks'].update({key:bool(var.get()) for key,var in self.locks.items()})
        self.editor.status.set('Artwork protection applied to draft. Save to keep it.')

    def add(self, images):
        known={image_digest(i) for i in self.editor.stage['available']}
        for image in images:
            digest=image_digest(image)
            if digest not in known:self.editor.stage['available'].append(image);known.add(digest)
        self.render()

    def local(self,role):
        from add_game_metadata import choose_local_cover
        try:image=choose_local_cover(self.editor.win,role.title())
        except Exception as exc:self.editor.status.set('Artwork unavailable: '+str(exc));return
        if image:
            self.add([image]);self.editor.stage[role]=image;self.render()
            self.editor.status.set(role.title()+' selected for draft. Save to keep it.')

    def selected(self):
        selected=self.table.selection()
        return self.editor.stage['available'][int(selected[0])] if selected else None

    def assign(self,role):
        image=self.selected()
        if not image:self.editor.status.set('Select an image thumbnail first.');return
        stage=self.editor.stage
        if role=='extra':
            digest=image_digest(image)
            if any(image_digest(i)==digest for i in stage['extras']):stage['extras']=[i for i in stage['extras'] if image_digest(i)!=digest]
            else:stage['extras'].append(image)
        else:stage[role]=image
        self.render();self.editor.status.set('Artwork selection applied to draft. Save completes the changes.')

    def clear(self,role):
        self.editor.stage[role]=None;self.render();self.editor.status.set(role.title()+' cleared in draft.')

    def preview_role(self,role):
        from add_game_metadata import preview_cover
        preview_cover(self.editor.win,self.editor.stage[role],role.title())

    def preview(self):
        from add_game_metadata import preview_cover
        image=self.selected()
        if image:preview_cover(self.editor.win,image,'Artwork')
        else:self.editor.status.set('Select a thumbnail to preview.')

    def render(self):
        from PIL import ImageTk
        from add_game_metadata import preview_picture
        stage=self.editor.stage;selection=tuple(self.table.selection());position=self.table.yview()[0]
        for row in self.table.get_children():self.table.delete(row)
        for index,image in enumerate(stage['available']):
            digest=image_digest(image)
            if digest not in self.photos:self.photos[digest]=ImageTk.PhotoImage(preview_picture(image['raw'],'Checkerboard',(124,100)),master=self.editor.win)
            roles=[role.title() for role in self.roles if stage.get(role) and image_digest(stage[role])==digest]
            if any(image_digest(i)==digest for i in stage['extras']):roles.append('Extra')
            self.table.insert('','end',iid=str(index),image=self.photos[digest],values=(image['label']+(' · '+', '.join(roles) if roles else ''),f"{image['w']} × {image['h']}"))
        for ident in selection:
            if self.table.exists(ident):self.table.selection_add(ident)
        self.table.yview_moveto(position)
        self.info.set('\n'.join(role.title()+': '+(stage[role]['label'] if stage.get(role) else 'None') for role in self.roles)+f"\n{len(stage['extras'])} extra images selected · {len(stage['available'])} available")


class AddDraft:
    def __init__(self,parent,kind,accent,on_saved,initial=None):
        if kind not in LABELS:raise ValueError('Unknown collection section')
        self.kind=kind;self.parent=parent;self.accent=accent;self.on_saved=on_saved
        self.closed=False;self.busy=False;self.generation=0;self.queue=queue.Queue();self.cancel=threading.Event();self.job=None
        self.stage={'cover':None,'background':None,'logo':None,'extras':[],'available':[],
                    'locks':{'cover_path':False,'background_path':False,'logo_path':False}}
        self.items=[];self.details={};self.proposed={};self.review_original={};self.checks={};self.options=[];self.art_index=0;self.seasons=[];self.item=None
        self.win=tk.Toplevel(parent);install(self.win);self.win.title('Add '+LABELS[kind]);self.win.geometry('700x760');self.win.minsize(600,680);self.win.configure(bg=PANEL)
        self.win.transient(parent.winfo_toplevel());self.previous=self.win.grab_current();self.win.grab_set();self.win._add_draft=self
        self.win.protocol('WM_DELETE_WINDOW',self.close);self.win.bind('<Escape>',self.close)
        header=tk.Frame(self.win,bg=PANEL,padx=20,pady=16);header.pack(fill='x')
        tk.Label(header,text='ADD '+LABELS[kind].upper(),bg=PANEL,fg=TEXT,font=('Arial',15,'bold')).pack(anchor='w')
        tk.Label(header,text='Review metadata and artwork before saving. Your changes stay in this draft.',bg=PANEL,fg=MUTED,wraplength=630,justify='left').pack(anchor='w',pady=(4,8))
        tk.Button(header,text='Find Metadata & Artwork…',command=self.find,bg=accent,fg='white',relief='flat',padx=12,pady=8).pack(anchor='w')
        footer=tk.Frame(self.win,bg=PANEL,padx=20,pady=12);footer.pack(side='bottom',fill='x')
        self.status=tk.StringVar(value='New draft. Nothing is saved yet.')
        tk.Label(footer,textvariable=self.status,bg=PANEL,fg=MUTED,wraplength=620,justify='left').pack(fill='x',pady=(0,8))
        tk.Button(footer,text='Save '+LABELS[kind],command=self.save,bg=accent,fg='white',relief='flat',padx=20,pady=9).pack(side='right')
        tk.Button(footer,text='Cancel',command=self.close,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=18,pady=9).pack(side='right',padx=8)
        self.tabs=ttk.Notebook(self.win);self.tabs.pack(fill='both',expand=True,padx=20)
        self.metadata=tk.Frame(self.tabs,bg=PANEL);self.tabs.add(self.metadata,text='Metadata')
        canvas=tk.Canvas(self.metadata,bg=PANEL,highlightthickness=0);bar=ttk.Scrollbar(self.metadata,command=canvas.yview);bar.pack(side='right',fill='y');canvas.configure(yscrollcommand=bar.set);canvas.pack(side='left',fill='both',expand=True)
        form=tk.Frame(canvas,bg=PANEL,padx=16,pady=8);ident=canvas.create_window((0,0),window=form,anchor='nw');form.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(ident,width=e.width))
        self.widgets={};self.variables={};self.types={key:typ for key,_,typ in FIELDS[kind]}
        for key,label,typ in FIELDS[kind]:
            value=(initial or {}).get(key)
            if typ=='bool':
                var=tk.IntVar(master=self.win,value=int(bool(value)));self.variables[key]=var
                w=tk.Checkbutton(form,text=label,variable=var,bg=PANEL,fg=TEXT,selectcolor=PANEL_ALT)
            else:
                tk.Label(form,text=label,bg=PANEL,fg=TEXT,font=('Arial',10,'bold')).pack(anchor='w',pady=(10,3))
                w=tk.Text(form,height=4,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT,wrap='word') if typ=='multiline' else tk.Entry(form,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT)
                w.insert('1.0' if typ=='multiline' else 0,str(value) if value is not None else '0:00:00' if typ=='duration' else '0' if typ=='count' else '')
            w.pack(fill='x',pady=2);self.widgets[key]=w
        def wheel(event):
            if self.tabs.select()!=str(self.metadata):return
            canvas.yview_scroll(-3 if getattr(event,'num',0)==4 or getattr(event,'delta',0)>0 else 3,'units');return 'break'
        for widget in [canvas,form,*form.winfo_children()]:
            for sequence in ('<MouseWheel>','<Button-4>','<Button-5>'):widget.bind(sequence,wheel,add='+')
        self.arttab=tk.Frame(self.tabs,bg=PANEL);self.tabs.add(self.arttab,text='Artwork')
        self.art=ArtworkDraft(self,self.arttab,kind=='games');self.finder=None
        self.initial=self.signature();self.widgets['name'].focus_set();self.job=self.win.after(80,self.poll)

    def raw(self):
        return {key:self.variables[key].get() if typ=='bool' else self.widgets[key].get('1.0','end-1c') if typ=='multiline' else self.widgets[key].get() for key,_,typ in FIELDS[self.kind]}

    def signature(self):
        stage=self.stage
        return (tuple(self.raw().items()),tuple(image_digest(stage[r]) if stage[r] else None for r in ('cover','background','logo')),tuple(image_digest(i) for i in stage['extras']),tuple(stage['locks'].items()))

    def find(self):
        if self.finder is None:
            self.finder=tk.Frame(self.tabs,bg=PANEL);self.tabs.add(self.finder,text='Find Metadata')
            self.build_finder()
        self.tabs.select(self.finder)
        return self.finder

    def build_finder(self):
        from metadata_finder import providers
        from search_shortcuts import bind_enter
        top=tk.Frame(self.finder,bg=PANEL);top.pack(fill='x',padx=18,pady=14)
        self.provider=tk.StringVar(value={'games':'Steam','books':'Open Library','movies':'TMDB','shows':'TMDB'}[self.kind])
        ttk.Combobox(top,textvariable=self.provider,values=providers(self.kind),state='readonly',width=14).pack(side='left',padx=(0,8))
        self.query=tk.StringVar(value=self.raw()['name'])
        entry=tk.Entry(top,textvariable=self.query,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT);entry.pack(side='left',fill='x',expand=True)
        bind_enter(entry,self.search)
        tk.Button(top,text='Search',command=self.search,bg=self.accent,fg='white',padx=12).pack(side='left',padx=8)
        self.token=tk.StringVar(value=get_setting('tmdb_token',''))
        if self.kind in ('movies','shows'):
            auth=tk.Frame(self.finder,bg=PANEL);auth.pack(fill='x',padx=18,pady=(0,10))
            tk.Label(auth,text='TMDB token:',bg=PANEL,fg=MUTED).pack(side='left')
            tk.Entry(auth,textvariable=self.token,show='•',bg=PANEL_ALT,fg=TEXT,width=38,insertbackground=TEXT).pack(side='left',padx=8)
            tk.Button(auth,text='Save Token Locally',command=self.save_token).pack(side='bottom',anchor='w',pady=3)
            tk.Label(auth,text='Other providers need no token.',bg=PANEL,fg=MUTED).pack(side='bottom',anchor='w',pady=3)
        self.results=tk.Listbox(self.finder,bg=PANEL_ALT,fg=TEXT,height=4,exportselection=False)
        self.results.pack(fill='x',padx=18);self.results.bind('<<ListboxSelect>>',self.selected)
        self.season_var=tk.StringVar(value='');self.season_box=ttk.Combobox(self.finder,textvariable=self.season_var,state='readonly')
        if self.kind=='shows':self.season_box.pack(fill='x',padx=18,pady=5)
        self.season_box.bind('<<ComboboxSelected>>',self.select_season)
        self.finder_status=tk.StringVar(value='Search by title or ISBN barcode. Select the edition you own.' if self.kind=='books' else 'Search by title. Barcode lookup is available for books and albums; other sections support manual barcode entry.')
        tk.Label(self.finder,textvariable=self.finder_status,bg=PANEL,fg=MUTED,wraplength=630,justify='left').pack(fill='x',padx=18,pady=10)
        reviewbody=tk.Frame(self.finder,bg=PANEL)
        buttons=tk.Frame(self.finder,bg=PANEL);buttons.pack(side='bottom',fill='x',padx=18,pady=6)
        self.art_button=tk.Button(buttons,text='Load Artwork',command=self.load_art,bg=PANEL_ALT,fg=TEXT);self.art_button.grid(row=0,column=0,sticky='ew',padx=3,pady=3)
        tk.Button(buttons,text='View Source Entry',command=self.view_source,bg=PANEL_ALT,fg=TEXT).grid(row=0,column=1,sticky='ew',padx=3,pady=3)
        tk.Button(buttons,text='Review Loaded Artwork…',command=self.review_art,bg=PANEL_ALT,fg=TEXT).grid(row=1,column=0,sticky='ew',padx=3,pady=3)
        tk.Button(buttons,text='Apply Checked Fields',command=self.apply,bg=self.accent,fg='white').grid(row=1,column=1,sticky='ew',padx=3,pady=3)
        tk.Button(buttons,text='Back to Metadata',command=lambda:self.tabs.select(self.metadata),bg=PANEL_ALT,fg=TEXT).grid(row=2,column=0,columnspan=2,sticky='ew',padx=3,pady=3)
        buttons.columnconfigure(0,weight=1);buttons.columnconfigure(1,weight=1)
        reviewbody.pack(fill='both',expand=True,padx=18)
        canvas=tk.Canvas(reviewbody,bg=PANEL,highlightthickness=0);scroll=ttk.Scrollbar(reviewbody,command=canvas.yview);scroll.pack(side='right',fill='y');canvas.configure(yscrollcommand=scroll.set);canvas.pack(fill='both',expand=True)
        self.review_canvas=canvas
        self.review=tk.Frame(canvas,bg=PANEL);ident=canvas.create_window((0,0),window=self.review,anchor='nw');self.review.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(ident,width=e.width))
        self.status.trace_add('write',lambda *args:self.finder_status.set(self.status.get()) if not self.closed else None)

    def review_art(self):
        self.tabs.select(self.arttab);self.art.render()
        self.status.set('Select an image, then assign Cover, Background or Extra. Save '+LABELS[self.kind]+' keeps your choices.')

    def view_source(self):
        if not self.item:self.status.set('Choose a search result first.');return
        import re
        import webbrowser
        from urllib.parse import quote
        source=self.item.get('source');ident=str(self.item.get('detail') or '')
        url=None
        if source=='Steam' and ident.isdecimal():url='https://store.steampowered.com/app/'+ident
        elif source=='TMDB' and ident.isdecimal():url='https://www.themoviedb.org/'+('movie/' if self.kind=='movies' else 'tv/')+ident
        elif source=='Open Library' and re.fullmatch(r'https://openlibrary.org/(works|books)/[A-Za-z0-9]+',ident):url=ident
        elif source=='Google Books' and re.fullmatch(r'[A-Za-z0-9_-]+',str(self.item.get('google_id') or '')):url='https://books.google.com/books?id='+quote(self.item['google_id'])
        elif source=='Wikipedia':url='https://en.wikipedia.org/wiki/'+quote(self.item.get('title','').replace(' ','_'))
        if url:webbrowser.open(url)
        else:self.status.set('This provider did not supply a supported source link.')

    def save_token(self):
        set_setting('tmdb_token',self.token.get().strip());self.status.set('TMDB token saved locally. Collection draft remains unsaved.')

    def background(self,work,done):
        self.busy=True;generation=self.generation
        def run():
            try:value,error=work(),None
            except Exception as exc:value,error=None,str(exc)
            self.queue.put((generation,done,value,error))
        threading.Thread(target=run,daemon=True).start()

    def poll(self):
        if self.closed:return
        try:
            while True:
                generation,done,value,error=self.queue.get_nowait()
                if generation==self.generation:self.busy=False;done(value,error)
        except queue.Empty:pass
        self.job=self.win.after(80,self.poll)

    def reset_review(self):
        self.proposed={};self.checks={};self.options=[];self.art_index=0
        self.art_button.configure(text='Load Artwork')
        for child in self.review.winfo_children():child.destroy()

    def search(self):
        if self.busy:self.status.set('Wait for the current request to finish.');return
        query=self.query.get().strip()
        if not query:self.status.set('Enter a search title first.');return
        from metadata_finder import search_provider
        provider=self.provider.get();token=self.token.get();self.generation+=1;self.reset_review();self.item=None;self.seasons=[];self.season_box.configure(values=());self.season_var.set('')
        self.results.delete(0,'end')
        self.items=[];self.status.set('Searching '+provider+'…')
        def done(value,error):
            if error:self.status.set('Search failed: '+error+'. Manual entry is available.');return
            self.items=value
            for item in value:self.results.insert('end',item['title']+' — '+str(item.get('subtitle') or ''))
            self.status.set(f'{len(value)} results. Choose an edition to review.' if value else 'No matches. Try another query/provider or enter metadata manually.')
        self.background(lambda:search_provider(self.kind,query,provider,token),done)

    def selected(self,event=None):
        if self.busy:return
        selected=self.results.curselection()
        if not selected:return
        self.item=copy.deepcopy(self.items[int(selected[0])]);self.seasons=[];self.season_box.configure(values=());self.season_var.set('');self.load_detail()

    def select_season(self,event=None):
        if self.busy or not self.item:return
        index=self.season_box.current()
        if 0<=index<len(self.seasons):self.load_detail(self.seasons[index]['season_number'])

    def load_detail(self,season=None):
        self.reset_review();self.status.set('Loading edition metadata…');item=copy.deepcopy(self.item);token=self.token.get();self.generation+=1
        key=(item.get('source'),str(item.get('detail') or item.get('google_id') or item.get('title')),season,token)
        def done(value,error):
            if error:self.status.set('Metadata unavailable: '+error);return
            self.details[key]=copy.deepcopy(value)
            if self.kind=='shows' and item.get('source')=='TMDB' and season is None:
                self.seasons=value['seasons'];self.season_box.configure(values=[f"{s['season_number']} — {s.get('name') or 'Season'}" for s in self.seasons]);self.status.set(value.get('warning') or 'Choose a season before applying metadata.');return
            self.show_review(value)
        if key in self.details:done(copy.deepcopy(self.details[key]),None)
        else:self.background(lambda:provider_details(self.kind,item,token,season),done)

    def show_review(self,value):
        self.reset_review();self.proposed=value['fields'];self.options=list(dict((url,(label,url)) for label,url in value.get('image_options',[])).values());self.review_original=self.raw()
        from add_media_metadata import populated
        for key,label,typ in FIELDS[self.kind]:
            proposed=self.proposed.get(key)
            if proposed is None or str(proposed).strip()=='':continue
            var=tk.IntVar(master=self.win,value=int(not populated(self.review_original[key])));self.checks[key]=var
            text=label+': '+str(self.review_original[key] or 'Unrecorded')+' → '+str(proposed)
            tk.Checkbutton(self.review,text=text,variable=var,bg=PANEL,fg=TEXT,selectcolor=PANEL_ALT,anchor='w',wraplength=460,justify='left').pack(fill='x',pady=3)
        def wheel(event):
            if self.tabs.select()!=str(self.finder):return
            self.review_canvas.yview_scroll(-3 if getattr(event,'num',0)==4 or getattr(event,'delta',0)>0 else 3,'units');return 'break'
        widgets=[self.review_canvas,self.review]
        for row in self.review.winfo_children():widgets.extend([row,*row.winfo_children()])
        for widget in widgets:
            for sequence in ('<MouseWheel>','<Button-4>','<Button-5>'):widget.bind(sequence,wheel,add='+')
        self.status.set('Review ready. Filled fields are unchecked; apply only what you choose. Artwork loads separately.'+(' '+value['warning'] if value.get('warning') else ''))

    def apply(self):
        if self.busy:self.status.set('Wait for the request to finish.');return
        keys=[key for key,var in self.checks.items() if var.get()]
        if not keys:self.status.set('Tick at least one field to apply.');return
        current=self.raw()
        if any(str(current[k])!=str(self.review_original[k]) for k in keys):
            if not messagebox.askyesno('Draft fields changed','Some checked fields changed since review. Replace them with the proposed values?',parent=self.win):return
        for key in keys:
            value=self.proposed[key]
            if key in self.variables:self.variables[key].set(int(bool(value)))
            else:
                start='1.0' if self.types[key]=='multiline' else 0
                self.widgets[key].delete(start,'end');self.widgets[key].insert(start,str(value))
            self.review_original[key]=self.raw()[key]
        self.status.set(f'{len(keys)} field(s) applied to draft. Nothing is saved until Save {LABELS[self.kind]}.')

    def load_art(self):
        if self.busy:self.status.set('Wait for the request to finish.');return
        batch=self.options[self.art_index:self.art_index+20]
        if not batch:self.status.set('No further artwork supplied for this edition. Local images can be added in Artwork.');return
        from cd_artwork import collect_images
        from add_game_metadata import validated_cover
        self.status.set('Loading artwork in parallel…');self.generation+=1
        def work():
            images,failed=collect_images(batch,self.cancel)
            return [validated_cover(raw,label,url) for raw,w,h,ext,label,url in images],failed
        def done(value,error):
            if error:self.status.set('Artwork unavailable: '+error);return
            self.art_index+=len(batch);images,failed=value;self.art.add(images)
            self.art_button.configure(text='Load More Artwork' if self.art_index<len(self.options) else 'Artwork Loaded')
            self.tabs.select(self.arttab);self.status.set(f'{len(images)} artwork previews loaded · {failed} failed. Choose roles here; Save keeps them.')
        self.background(work,done)

    def save(self):
        if self.busy:self.status.set('Wait for the request to finish before saving.');return
        try:
            raw=self.raw();values=parse_values(self.kind,raw);matches=duplicate_items(self.kind,values)
            if matches:
                labels='\n'.join(f'#{r[0]} · {r[1]}' for r in matches[:8])
                if not messagebox.askyesno('Possible Duplicate','Matching entries already exist:\n'+labels+'\n\nSave another copy or edition?',parent=self.win):self.status.set('Draft retained. Review it or save another copy.');return
            item_id=create_item(self.kind,raw,self.stage)
        except InvalidField as exc:
            self.tabs.select(self.metadata);self.widgets[exc.key].focus_set();self.status.set(str(exc));return
        except Exception as exc:self.status.set('Save failed; draft retained: '+str(exc));return
        messagebox.showinfo(LABELS[self.kind]+' saved',values['name']+' saved successfully. Metadata and selected artwork are stored locally.',parent=self.win)
        self.finish();self.on_saved();return item_id

    def finish(self):
        self.closed=True;self.cancel.set();self.generation+=1
        if self.job:self.win.after_cancel(self.job)
        self.win.destroy()
        if self.previous is not None:
            try:
                if self.previous.winfo_exists():self.previous.grab_set()
            except tk.TclError:pass

    def close(self,event=None):
        if self.closed:return 'break'
        if self.signature()!=self.initial and not messagebox.askyesno('Unsaved Draft','Discard this unsaved metadata and artwork draft?',parent=self.win):return 'break'
        self.finish();return 'break'


def open_add(parent,kind,accent,on_saved,initial=None):
    return AddDraft(parent,kind,accent,on_saved,initial).win
