"""Games-style album metadata and Add workflow with a staged track/artwork draft."""
import copy
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from database import connection, PROJECT_ROOT, get_setting, set_setting
from rich_details import FIELDS, InvalidField
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED, BORDER
from utils import format_time, parse_time
from window_style import install


def open_editor(parent, accent, on_saved, item_id=None, initial=None, initial_tracks=None):
    editor=AlbumEditor(parent,accent,on_saved,item_id,initial,initial_tracks)
    return editor.win


class AlbumEditor:
    def __init__(self,parent,accent,on_saved,item_id,initial,initial_tracks):
        from cds import record, tracks_for
        self.parent=parent;self.accent=accent;self.on_saved=on_saved;self.item_id=item_id
        self.original=record(item_id) if item_id is not None else {}
        if item_id is not None and not self.original:raise ValueError('This album no longer exists.')
        self.row=dict(self.original or {});self.row.update(initial or {})
        self.tracks=copy.deepcopy(initial_tracks if initial_tracks is not None else tracks_for(item_id) if item_id else [])
        self.stage={'cover':None,'background':None,'extras':[],'available':[],'changed':set()}
        self.provider={k:self.row.get(k) for k in ('provider_source','provider_id','provider_url')}
        self.search_session={'query':'','provider':get_setting('cd_metadata_provider','MusicBrainz'),'rows':[],'selected':None,'detail':None}
        self.closed=False;self.jobs=set();self.cancel=threading.Event()
        self.win=tk.Toplevel(parent);install(self.win);self.win.title(('Album Metadata — '+self.row['name']) if item_id else 'Add Album')
        self.win.geometry('700x760');self.win.minsize(540,540);self.win.configure(bg=PANEL)
        self.win.transient(parent.winfo_toplevel());self.previous=self.win.grab_current();self.win.grab_set();self.win._cd_editor=self
        header=tk.Frame(self.win,bg=PANEL,padx=20,pady=16);header.pack(fill='x')
        tk.Label(header,text='ALBUM METADATA' if item_id else 'ADD ALBUM',bg=PANEL,fg=TEXT,font=('Arial',15,'bold')).pack(anchor='w')
        tk.Label(header,text='Review metadata, tracks and artwork before saving. Your changes stay in this draft.',bg=PANEL,fg=MUTED,wraplength=630,justify='left').pack(anchor='w',pady=(4,8))
        tk.Button(header,text='Find Metadata & Artwork…',command=self.find,bg=accent,fg='white',relief='flat',padx=12,pady=8).pack(anchor='w')
        footer=tk.Frame(self.win,bg=PANEL,padx=20,pady=12);footer.pack(side='bottom',fill='x')
        self.status=tk.StringVar(value='');tk.Label(footer,textvariable=self.status,bg=PANEL,fg=MUTED,wraplength=620,justify='left').pack(fill='x',pady=(0,8))
        tk.Button(footer,text='Save Metadata' if item_id else 'Save Album',command=self.save,bg=accent,fg='white',relief='flat',padx=20,pady=9).pack(side='right')
        tk.Button(footer,text='Cancel',command=self.close,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=18,pady=9).pack(side='right',padx=8)
        tabs=ttk.Notebook(self.win);tabs.pack(fill='both',expand=True,padx=20)
        meta=tk.Frame(tabs,bg=PANEL);tabs.add(meta,text='Metadata')
        canvas=tk.Canvas(meta,bg=PANEL,highlightthickness=0);scroll=ttk.Scrollbar(meta,command=canvas.yview)
        scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
        form=tk.Frame(canvas,bg=PANEL,padx=16,pady=8);ident=canvas.create_window((0,0),window=form,anchor='nw')
        form.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(ident,width=e.width))
        self.widgets={};self.variables={};self.types={key:typ for key,_,typ in FIELDS['cds']}
        for key,label,typ in FIELDS['cds']:
            value=self.row.get(key)
            if typ=='bool':
                var=tk.IntVar(master=self.win,value=int(bool(value)));self.variables[key]=var
                widget=tk.Checkbutton(form,text=label,variable=var,bg=PANEL,fg=TEXT,selectcolor=PANEL_ALT)
            else:
                tk.Label(form,text=label,bg=PANEL,fg=TEXT,font=('Arial',10,'bold')).pack(anchor='w',pady=(10,3))
                if typ=='multiline':
                    widget=tk.Text(form,height=4,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT,wrap='word',padx=9,pady=7)
                    widget.insert('1.0',value or '')
                else:
                    widget=tk.Entry(form,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT,relief='flat')
                    value=format_time(value or 0) if typ=='duration' else str(value if value is not None else 1 if key=='disc_count' else 0 if typ=='count' else '')
                    widget.insert(0,value)
            widget.pack(fill='x',pady=2);self.widgets[key]=widget
        def wheel(event):
            if self.win.grab_current() is self.win:
                canvas.yview_scroll(-3 if getattr(event,'num',0)==4 or getattr(event,'delta',0)>0 else 3,'units');return 'break'
        for widget in [canvas,form,*form.winfo_children()]:
            for ev in ('<MouseWheel>','<Button-4>','<Button-5>'):widget.bind(ev,wheel,add='+')
        tracktab=tk.Frame(tabs,bg=PANEL);tabs.add(tracktab,text='Tracklist')
        tk.Label(tracktab,text='Manage tracks by disc and track number. Leave unknown durations blank.',bg=PANEL,fg=MUTED,wraplength=610).pack(anchor='w',padx=12,pady=12)
        row=tk.Frame(tracktab,bg=PANEL);row.pack(fill='x',padx=12,pady=(0,8))
        for text,command in [('Add Track',lambda:self.track_dialog()),('Edit Track',self.edit_track),('Remove Track',self.remove_track)]:
            tk.Button(row,text=text,command=command,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=10,pady=7).pack(side='left',padx=3)
        trackbody=tk.Frame(tracktab,bg=PANEL);trackbody.pack(fill='both',expand=True,padx=12,pady=(0,12))
        self.table=ttk.Treeview(trackbody,columns=('Disc','Track','Title','Duration'),show='headings',selectmode='browse')
        for key in self.table['columns']:
            self.table.heading(key,text=key);self.table.column(key,width=80 if key!='Title' else 260,stretch=key=='Title')
        trackscroll=ttk.Scrollbar(trackbody,command=self.table.yview);trackscroll.pack(side='right',fill='y');self.table.configure(yscrollcommand=trackscroll.set);self.table.pack(fill='both',expand=True)
        self.table.bind('<Double-1>',lambda e:self.edit_track() if self.table.identify_region(e.x,e.y)=='cell' else None)
        self.render_tracks()
        arttab=tk.Frame(tabs,bg=PANEL);tabs.add(arttab,text='Artwork')
        self.art_summary=tk.StringVar(value='');tk.Label(arttab,textvariable=self.art_summary,bg=PANEL,fg=TEXT,justify='left',wraplength=600).pack(anchor='w',padx=16,pady=16)
        for text,command in [('Review Available Artwork…',self.review_art),('Choose Local Cover…',lambda:self.local('cover')),
                             ('Choose Local Background…',lambda:self.local('background')),('Preview Cover',lambda:self.preview('cover')),
                             ('Preview Background',lambda:self.preview('background')),('Clear Cover',lambda:self.clear('cover')),
                             ('Clear Background',lambda:self.clear('background'))]:
            tk.Button(arttab,text=text,command=command,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=12,pady=8).pack(fill='x',padx=16,pady=3)
        tk.Label(arttab,text='Original images are saved locally only when you save this album. Extra selected images join Artwork Collection.',bg=PANEL,fg=MUTED,wraplength=600,justify='left').pack(anchor='w',padx=16,pady=12)
        self._load_saved_art();self.summary();self.initial=self.signature()
        self.win.protocol('WM_DELETE_WINDOW',self.close);self.win.bind('<Escape>',self.close)
        self.widgets['name'].focus_set()

    def raw(self):
        return {key:self.variables[key].get() if typ=='bool' else self.widgets[key].get('1.0','end-1c') if typ=='multiline' else self.widgets[key].get() for key,_,typ in FIELDS['cds']}

    def signature(self):
        from add_game_metadata import image_digest
        return (tuple(self.raw().items()),tuple((t['disc'],t['track'],t['name'],t['duration_seconds']) for t in self.tracks),
                tuple(image_digest(self.stage[k]) if self.stage[k] else None for k in ('cover','background')),
                tuple(image_digest(x) for x in self.stage['extras']),tuple(sorted(self.stage['changed'])),tuple(self.provider.items()))

    def _load_saved_art(self):
        if not self.item_id:return
        from add_game_metadata import validated_cover,image_digest
        rows=connection.execute("SELECT image_path,source FROM artwork_library WHERE category='cds' AND item_id=?",(self.item_id,)).fetchall()
        by_path={};seen=set()
        for path,source in rows+[(self.row.get(key+'_path'),'Saved '+key) for key in ('cover','background')]:
            if not path or path in by_path:continue
            try:
                full=(PROJECT_ROOT/path).resolve()
                if not full.is_relative_to(PROJECT_ROOT.resolve()):continue
                image=validated_cover(full.read_bytes(),Path(path).name,source or 'Local file')
                by_path[path]=image;digest=image_digest(image)
                if digest not in seen:self.stage['available'].append(image);seen.add(digest)
            except Exception:pass
        for key in ('cover','background'):self.stage[key]=by_path.get(self.row.get(key+'_path'))

    def summary(self):
        def role(key):
            image=self.stage[key]
            return image['label'] if image else 'Saved image unavailable (retained)' if key not in self.stage['changed'] and self.row.get(key+'_path') else 'None'
        self.art_summary.set('Cover: '+role('cover')+'\nBackground: '+role('background')+f'\n{len(self.stage["extras"])} extra images selected · {len(self.stage["available"])} available')

    def render_tracks(self):
        for ident in self.table.get_children():self.table.delete(ident)
        self.tracks.sort(key=lambda t:(t['disc'],t['track']))
        for index,t in enumerate(self.tracks):
            self.table.insert('','end',iid=str(index),values=(t['disc'],t['track'],t['name'],format_time(t['duration_seconds']/3600) if t['duration_seconds'] is not None else 'Unknown'))

    def edit_track(self):
        selected=self.table.selection()
        if selected:self.track_dialog(int(selected[0]))

    def remove_track(self):
        selected=self.table.selection()
        if selected and messagebox.askyesno('Remove Track','Remove the selected track from this draft?',parent=self.win):
            self.tracks.pop(int(selected[0]));self.render_tracks()

    def track_dialog(self,index=None):
        original=self.tracks[index] if index is not None else {}
        dialog=tk.Toplevel(self.win);install(dialog);dialog.title('Edit Track' if index is not None else 'Add Track');dialog.geometry('440x370');dialog.configure(bg=PANEL);dialog.transient(self.win);dialog.grab_set()
        inputs={}
        defaults={'disc':1,'track':max((t['track'] for t in self.tracks if t['disc']==1),default=0)+1,'name':'','duration':''}
        for key,label in [('disc','Disc number'),('track','Track number'),('name','Track title'),('duration','Duration (H:MM:SS, blank if unknown)')]:
            tk.Label(dialog,text=label,bg=PANEL,fg=TEXT).pack(anchor='w',padx=20,pady=(10,3))
            var=tk.StringVar(value=format_time(original['duration_seconds']/3600) if key=='duration' and original.get('duration_seconds') is not None else original.get(key,defaults[key]))
            inputs[key]=var;tk.Entry(dialog,textvariable=var,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT).pack(fill='x',padx=20)
        status=tk.Label(dialog,bg=PANEL,fg=MUTED,wraplength=390);status.pack(padx=20,pady=8)
        def close():dialog.destroy();self.win.grab_set()
        def save():
            from cds import parse_tracks
            try:
                discs=int(self.raw()['disc_count'])
                line=' | '.join(inputs[key].get() for key in ('disc','track','name','duration'))
                track=parse_tracks(line,discs)[0]
                if any(i!=index and (t['disc'],t['track'])==(track['disc'],track['track']) for i,t in enumerate(self.tracks)):
                    raise ValueError('This disc/track number is already used.')
            except (ValueError,IndexError) as exc:status.configure(text=str(exc));return
            if index is None:self.tracks.append(track)
            else:self.tracks[index]=track
            self.render_tracks();close()
        actions=tk.Frame(dialog,bg=PANEL);actions.pack(fill='x',padx=20,pady=6)
        tk.Button(actions,text='Save Track',command=save,bg=self.accent,fg='white').pack(side='right')
        tk.Button(actions,text='Cancel',command=close,bg=PANEL_ALT,fg=TEXT).pack(side='right',padx=8)
        dialog.protocol('WM_DELETE_WINDOW',close);dialog.bind('<Escape>',lambda e:close())

    def local(self,role):
        from add_game_metadata import validated_cover
        filename=filedialog.askopenfilename(parent=self.win,title='Choose Album '+role.title(),filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.bmp')])
        if not filename:return
        try:
            image=validated_cover(Path(filename).read_bytes(),Path(filename).name)
            self.stage[role]=image;self.stage['changed'].add(role);self.stage['available'].append(image);self.summary()
        except Exception as exc:self.status.set(str(exc))

    def preview(self,role):
        from add_game_metadata import preview_cover
        preview_cover(self.win,self.stage[role],role.title())

    def clear(self,role):
        self.stage[role]=None;self.stage['changed'].add(role);self.summary()

    def review_art(self):
        from add_game_metadata import choose_artwork,image_digest
        if not self.stage['available']:
            self.status.set('Find a release and load its artwork, or choose an image from your PC.');return
        old={key:image_digest(self.stage[key]) if self.stage[key] else None for key in ('cover','background')}
        def chosen(cover,extras,roles):
            for key,image in [('cover',cover),('background',roles.get('background_path'))]:
                digest=image_digest(image) if image else None
                if digest!=old[key]:self.stage['changed'].add(key)
                self.stage[key]=image
            self.stage['extras']=extras;self.summary()
        choose_artwork(self.win,self.accent,self.stage['available'],self.stage['cover'],self.stage['extras'],chosen,
                       roles={'background_path':self.stage['background']},media_label='Album',role_keys=('background_path',))

    def apply_metadata(self,data,keys,with_tracks):
        for key in keys:
            if key not in self.widgets or data['fields'].get(key) is None:continue
            multi=self.types[key]=='multiline';widget=self.widgets[key]
            widget.delete('1.0' if multi else 0,'end');widget.insert('1.0' if multi else 0,str(data['fields'][key]))
        if with_tracks:self.tracks=copy.deepcopy(data['tracks']);self.render_tracks()
        self.provider={'provider_source':data['source'],'provider_id':str(data['id']),'provider_url':data.get('url')}

    def find(self):
        return ReleaseFinder(self).win

    def finish(self):
        self.closed=True;self.cancel.set()
        for job in self.jobs:
            try:self.win.after_cancel(job)
            except tk.TclError:pass
        self.win.destroy()
        if self.previous is not None:
            try:
                if self.previous.winfo_exists():self.previous.grab_set()
            except tk.TclError:pass

    def close(self,event=None):
        if self.closed:return 'break'
        if self.signature()!=self.initial and not messagebox.askyesno('Unsaved Changes','Discard unsaved album metadata, tracks and artwork?',parent=self.win):return 'break'
        self.finish();return 'break'

    def save(self):
        from cds import validate,track_text,save_album
        try:
            timer=getattr(self.parent.winfo_toplevel(),'manual_timer',None)
            if self.item_id and timer and timer.kind=='cds' and timer.item_id==self.item_id:
                raise ValueError('Stop and save this album’s timer before editing its listening total.')
            values,tracks=validate(self.raw(),track_text(self.tracks));values.update(self.provider)
            if self.item_id is None:
                matches=connection.execute("SELECT id FROM cds WHERE lower(trim(name))=lower(?) AND lower(trim(COALESCE(artist,'')))=lower(?)",(values['name'],values['artist'] or '')).fetchall()
                if matches and not messagebox.askyesno('Possible Duplicate','This title and artist already exist. Save another edition/copy?',parent=self.win):return
            new_id=save_album(values,tracks,self.item_id,self.stage,self.original)
        except InvalidField as exc:
            self.status.set(str(exc));self.widgets[exc.key].focus_set();return
        except Exception as exc:self.status.set('Could not save: '+str(exc));return
        self.finish();self.on_saved(new_id)


class ReleaseFinder:
    def __init__(self,editor):
        self.editor=editor;self.session=editor.search_session;self.closed=False;self.generation=0;self.queue=queue.Queue();self.job=None
        self.cancel=threading.Event();self.art_busy=False;self.options=[];self.art_index=0;self.art_failures=0
        self.win=tk.Toplevel(editor.win);install(self.win);self.win.title('Album Metadata & Artwork Finder');self.win.geometry('920x740');self.win.minsize(700,560);self.win.configure(bg=BG)
        self.win.transient(editor.win);self.win.grab_set();self.win._cd_finder=self
        top=tk.Frame(self.win,bg=BG);top.pack(fill='x',padx=18,pady=14)
        raw=editor.raw();self.query=tk.StringVar(value=self.session.get('query') or (raw['name']+' '+(raw['artist'] or '')).strip())
        self.provider=tk.StringVar(value=self.session.get('provider') if self.session.get('provider') in ('MusicBrainz','Discogs') else 'MusicBrainz')
        ttk.Combobox(top,textvariable=self.provider,values=['MusicBrainz','Discogs'],state='readonly',width=14).pack(side='left',padx=(0,8))
        tk.Entry(top,textvariable=self.query,bg=PANEL,fg=TEXT,insertbackground=TEXT).pack(side='left',fill='x',expand=True)
        tk.Button(top,text='Search',command=self.search,bg=editor.accent,fg='white',padx=12).pack(side='left',padx=8)
        auth=tk.Frame(self.win,bg=BG);auth.pack(fill='x',padx=18,pady=(0,10))
        tk.Label(auth,text='Discogs token:',bg=BG,fg=MUTED).pack(side='left')
        self.token=tk.StringVar(value=get_setting('discogs_token',''))
        tk.Entry(auth,textvariable=self.token,show='•',bg=PANEL,fg=TEXT,width=38).pack(side='left',padx=8)
        tk.Button(auth,text='Save Token Locally',command=lambda:self.save_token()).pack(side='left')
        tk.Label(auth,text='MusicBrainz needs no token.',bg=BG,fg=MUTED).pack(side='left',padx=10)
        self.results=tk.Listbox(self.win,bg=PANEL,fg=TEXT,height=7,exportselection=False)
        self.results.pack(fill='x',padx=18);self.results.bind('<<ListboxSelect>>',self.selected)
        self.status=tk.StringVar(value='Search by album/artist or barcode. Select the edition you own.')
        tk.Label(self.win,textvariable=self.status,bg=BG,fg=MUTED,wraplength=850,justify='left').pack(fill='x',padx=18,pady=10)
        reviewbody=tk.Frame(self.win,bg=BG);reviewbody.pack(fill='both',expand=True,padx=18)
        self.canvas=tk.Canvas(reviewbody,bg=BG,highlightthickness=0);scroll=ttk.Scrollbar(reviewbody,command=self.canvas.yview);scroll.pack(side='right',fill='y');self.canvas.configure(yscrollcommand=scroll.set);self.canvas.pack(fill='both',expand=True)
        self.review=tk.Frame(self.canvas,bg=BG);ident=self.canvas.create_window((0,0),window=self.review,anchor='nw')
        self.review.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')));self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(ident,width=e.width))
        self.checks={};self.track_choice=tk.IntVar(value=0);self.snapshot={}
        buttons=tk.Frame(self.win,bg=BG);buttons.pack(fill='x',padx=18,pady=14)
        self.load_btn=tk.Button(buttons,text='Load Artwork',command=self.load_art,bg=PANEL_ALT,fg=TEXT);self.load_btn.pack(side='left')
        tk.Button(buttons,text='View Source Release',command=self.view_source,bg=PANEL_ALT,fg=TEXT).pack(side='left',padx=8)
        tk.Button(buttons,text='Review Loaded Artwork…',command=editor.review_art,bg=PANEL_ALT,fg=TEXT).pack(side='left',padx=8)
        tk.Button(buttons,text='Apply Checked Fields',command=self.apply,bg=editor.accent,fg='white').pack(side='right')
        tk.Button(buttons,text='Close',command=self.close,bg=PANEL_ALT,fg=TEXT).pack(side='right',padx=8)
        if editor.provider.get('provider_id'):
            tk.Button(top,text='Saved Release',command=self.saved_release).pack(side='right')
        self.detail=self.session.get('detail');self.render_results()
        if self.detail:self.render_review()
        self.win.protocol('WM_DELETE_WINDOW',self.close);self.win.bind('<Escape>',self.close)
        self.win.bind('<Destroy>',self.destroyed,add='+');self.poll()

    def view_source(self):
        if not self.detail:return
        source=self.detail.get('source');ident=str(self.detail.get('id',''))
        from cd_metadata import release_id
        try:release_id({'source':source,'id':ident})
        except ValueError:return
        import webbrowser
        webbrowser.open(('https://www.discogs.com/release/' if source=='Discogs' else 'https://musicbrainz.org/release/')+ident)

    def save_token(self):
        set_setting('discogs_token',self.token.get().strip());self.status.set('Discogs token saved locally.' if self.token.get().strip() else 'Discogs token cleared.')

    def submit(self,action):
        self.generation+=1;generation=self.generation
        self.detail=None;self.checks.clear();self.cancel.set();self.cancel=threading.Event();self.art_busy=False
        for child in self.review.winfo_children():child.destroy()
        self.status.set('Loading metadata…')
        def work():
            try:self.queue.put((generation,'result',action()))
            except Exception as exc:self.queue.put((generation,'error',str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def search(self):
        from cd_metadata import search
        query,provider,token=self.query.get(),self.provider.get(),self.token.get().strip()
        self.session.update(query=query,provider=provider,selected=None,detail=None,rows=[])
        self.results.delete(0,'end');set_setting('cd_metadata_provider',provider)
        self.submit(lambda:('search',search(query,provider,token)))

    def render_results(self):
        self.results.delete(0,'end')
        for row in self.session['rows']:self.results.insert('end',str(row.get('title',''))+' — '+row.get('subtitle',''))
        index=self.session.get('selected')
        if index is not None and index<len(self.session['rows']):self.results.selection_set(index)

    def selected(self,event=None):
        from cd_metadata import load_release
        indices=self.results.curselection()
        if not indices:return
        index=indices[0];self.session['selected']=index
        item=dict(self.session['rows'][index]);token=self.token.get().strip()
        self.submit(lambda:('detail',load_release(item,token)))

    def saved_release(self):
        from cd_metadata import load_release
        source=self.editor.provider['provider_source'];ident=self.editor.provider['provider_id'];token=self.token.get().strip()
        self.provider.set(source);self.submit(lambda:('detail',load_release({'source':source,'id':ident},token)))

    def render_review(self):
        for child in self.review.winfo_children():child.destroy()
        self.checks.clear();self.snapshot=self.editor.raw()
        for key,value in self.detail['fields'].items():
            if key not in self.editor.widgets or value in (None,''):continue
            old=self.snapshot.get(key,'');empty=str(old or '').strip() in ('','0','0:00:00')
            # Disc count is real entered data, so keep it unless the user chooses replacement.
            self.checks[key]=tk.IntVar(value=int(empty))
            text=key.replace('_',' ').title()+': '+str(old or 'Unrecorded')+' → '+str(value)
            tk.Checkbutton(self.review,text=text,variable=self.checks[key],bg=BG,fg=TEXT,selectcolor=PANEL,anchor='w',wraplength=800,justify='left').pack(fill='x',pady=3)
        self.track_choice.set(not bool(self.editor.tracks))
        tk.Checkbutton(self.review,text=f'Replace tracklist ({len(self.detail["tracks"])} tracks; unknown durations stay blank)',variable=self.track_choice,bg=BG,fg=TEXT,selectcolor=PANEL).pack(anchor='w',pady=8)
        # Empty new-album disc count can follow the chosen imported tracklist.
        if not self.editor.item_id and not self.editor.tracks and str(self.snapshot.get('disc_count'))=='1' and 'disc_count' in self.checks:
            self.checks['disc_count'].set(1)
        self.options=list(self.detail.get('artwork_options',[]));self.art_index=0
        self.status.set(self.detail.get('warning') or 'Metadata ready. Artwork loads separately when you choose Load Artwork.')
        self.load_btn.configure(text='Load Artwork',state='normal')

    def apply(self):
        if not self.detail:return
        current=self.editor.raw();keys=[key for key,var in self.checks.items() if var.get()]
        changed=[key for key in keys if current.get(key)!=self.snapshot.get(key)]
        if changed and not messagebox.askyesno('Entered Metadata Changed','Replace values changed since this review opened?',parent=self.win):return
        self.editor.apply_metadata(self.detail,keys,bool(self.track_choice.get()))
        self.status.set('Checked fields applied to the draft. Save Album/Metadata commits your changes.')

    def load_art(self):
        if not self.detail or self.art_busy:return
        from cd_metadata import load_artwork
        generation=self.generation;detail=copy.deepcopy(self.detail);token=self.token.get().strip()
        if not detail.get('artwork_loaded'):
            self.art_busy=True;self.load_btn.configure(state='disabled');self.status.set('Finding release image URLs… metadata remains available.')
            def work():
                try:self.queue.put((generation,'artwork',load_artwork(detail,token)))
                except Exception as exc:self.queue.put((generation,'art_error',str(exc)))
            threading.Thread(target=work,daemon=True).start()
        else:self.start_batch()

    def start_batch(self):
        from cd_artwork import download_batch
        if self.art_index>=len(self.options):
            self.status.set(self.detail.get('warning') or 'No more images for this release. Try another edition/provider or local artwork.');self.load_btn.configure(state='normal');return
        batch=self.options[self.art_index:self.art_index+8];self.art_index+=len(batch);self.art_busy=True
        self.load_btn.configure(state='disabled');self.status.set(f'Loading {len(batch)} images in parallel; received images are available for review.')
        generation=self.generation;cancel=self.cancel
        def emit(kind,value):self.queue.put((generation,kind,value))
        threading.Thread(target=lambda:download_batch(batch,cancel,emit),daemon=True).start()

    def poll(self):
        self.job=None
        if self.closed:return
        try:
            for _ in range(12):
                generation,kind,value=self.queue.get_nowait()
                if generation!=self.generation:continue
                if kind=='error':self.status.set(value)
                elif kind=='result':
                    mode,data=value
                    if mode=='search':self.session['rows']=data;self.render_results();self.status.set(f'{len(data)} releases. Select an edition to review.')
                    else:self.detail=data;self.session['detail']=data;self.render_review()
                elif kind=='artwork':
                    self.detail=value;self.session['detail']=value;self.options=list(value['artwork_options']);self.art_index=0;self.art_busy=False
                    if value.get('warning'):self.status.set(value['warning'])
                    self.start_batch()
                elif kind=='image':
                    from add_game_metadata import validated_cover,image_digest
                    raw,w,h,ext,label,url=value
                    image=validated_cover(raw,label,url)
                    if not any(image_digest(x)==image_digest(image) for x in self.editor.stage['available']):self.editor.stage['available'].append(image)
                    self.editor.summary();self.status.set(f'{len(self.editor.stage["available"])} images available to review. Only selected images are saved.')
                elif kind=='failure':self.art_failures+=1
                elif kind in ('done','art_error'):
                    self.art_busy=False;self.load_btn.configure(state='normal',text='Load More Artwork' if self.art_index<len(self.options) else 'Load Artwork')
                    self.status.set(value if kind=='art_error' else f'{len(self.editor.stage["available"])} available images · {self.art_failures} failed downloads. Review loaded artwork or load more.')
        except queue.Empty:pass
        self.job=self.win.after(100,self.poll)

    def destroyed(self,event):
        if event.widget is self.win:
            self.closed=True;self.generation+=1;self.cancel.set()
            if self.job:
                try:self.win.after_cancel(self.job)
                except tk.TclError:pass
                self.job=None

    def close(self,event=None):
        if self.closed:return 'break'
        self.closed=True;self.generation+=1;self.cancel.set();self.session['detail']=self.detail
        if self.job:self.win.after_cancel(self.job)
        self.win.destroy()
        if self.editor.win.winfo_exists():self.editor.win.grab_set()
        return 'break'
