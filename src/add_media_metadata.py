"""Metadata-first Movie/Show creation: review in memory, commit only on Save."""
import copy
import hashlib
import queue
import threading
import uuid
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from database import connection, PROJECT_ROOT, get_setting, set_setting
from rich_details import FIELDS, parse_values, InvalidField
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED, BORDER
from window_style import install as polish_dialog
from utils import format_time


def duplicates(kind, values):
    from add_game_metadata import normalise_match
    if kind not in ('movies', 'shows'):raise ValueError('Invalid category')
    columns='id,name,release_year'+(',season' if kind=='shows' else '')
    matches=[]
    for row in connection.execute(f'SELECT {columns} FROM {kind}'):
        if normalise_match(row[1])!=normalise_match(values['name']):continue
        if kind=='shows' and row[3]!=values['season']:continue
        if values.get('release_year') and row[2] and values['release_year']!=row[2]:continue
        matches.append(row)
    return matches


def create_media(kind, raw_values, cover=None, background=None, extras=()):
    if kind not in ('movies','shows'):raise ValueError('Invalid category')
    from add_game_metadata import validated_cover, image_digest
    from media_naming import clean_name
    values=parse_values(kind,raw_values)
    staged=[image for image in [cover,background,*extras] if image]
    images={image_digest(image):validated_cover(image['raw'],image['label'],image['source']) for image in staged}
    created=[];paths={}
    try:
        with connection:
            keys=list(values)
            item_id=connection.execute(f'INSERT INTO {kind} ({",".join(keys)}) VALUES ({",".join("?" for _ in keys)})',tuple(values.values())).lastrowid
            folder=PROJECT_ROOT/'assets'/'artwork'/kind
            if images:folder.mkdir(parents=True,exist_ok=True)
            for digest,image in images.items():
                target=folder/f'{clean_name(values["name"])} - {uuid.uuid4().hex[:12]}{image["ext"]}'
                created.append(target);target.write_bytes(image['raw'])
                path=target.relative_to(PROJECT_ROOT).as_posix();paths[digest]=path
                connection.execute('INSERT INTO artwork_library(category,item_id,image_path,width,height,source) VALUES(?,?,?,?,?,?)',
                                   (kind,item_id,path,image['w'],image['h'],image['source']))
            connection.execute(f'UPDATE {kind} SET cover_path=?,background_path=? WHERE id=?',
                               (paths.get(image_digest(cover)) if cover else None,paths.get(image_digest(background)) if background else None,item_id))
        return item_id
    except Exception:
        for target in created:target.unlink(missing_ok=True)
        raise


def load_tmdb(kind, item, token, season=None):
    """Strict detail reads; missing episode runtimes never become guessed totals."""
    from metadata_finder import get_json, HEADERS, plain
    if not token.strip():raise ValueError('Enter a TMDB API Read Access Token.')
    section='movie' if kind=='movies' else 'tv'
    ident=str(item['detail'])
    if not ident.isdecimal():raise ValueError('Invalid TMDB result')
    headers=dict(HEADERS,Authorization='Bearer '+token.strip())
    data=get_json(f'https://api.themoviedb.org/3/{section}/{ident}?append_to_response=credits,images&language=en-GB&include_image_language=en,null',headers)
    fields={'name':data.get('title') or data.get('name') or item['title'],
            'description':plain(data.get('overview')),
            'release_year':str(data.get('release_date') or data.get('first_air_date') or '')[:4],
            'genre':', '.join(x['name'] for x in data.get('genres',[]))}
    warning='';seasons=[s for s in data.get('seasons',[]) if type(s.get('season_number')) is int]
    season_data=None
    if kind=='movies':
        if isinstance(data.get('runtime'),(int,float)) and data['runtime']>0:fields['runtime']=format_time(data['runtime']/60)
        fields['director']=', '.join(x['name'] for x in (data.get('credits') or {}).get('crew',[]) if x.get('job')=='Director')
        fields['cast_members']=', '.join(x['name'] for x in (data.get('credits') or {}).get('cast',[])[:8])
    else:
        fields['network']=', '.join(x['name'] for x in data.get('networks',[]))
        if season is None:return {'fields':fields,'seasons':seasons,'images':[],'warning':'Choose a season to review its episode count and artwork.'}
        if type(season) is not int or season<0:raise ValueError('Invalid season')
        season_data=get_json(f'https://api.themoviedb.org/3/tv/{ident}/season/{season}?append_to_response=images&language=en-GB&include_image_language=en,null',headers)
        episodes=season_data.get('episodes')
        fields['season']=season
        if isinstance(episodes,list):
            fields['episode_count']=len(episodes)
            runtimes=[e.get('runtime') for e in episodes]
            if runtimes and all(type(r) in (int,float) and r>0 for r in runtimes):fields['runtime']=format_time(sum(runtimes)/60)
            else:warning='Season runtime unavailable: one or more episode runtimes are missing. Enter it manually if known.'
        else:warning='Episode count and runtime unavailable; enter them manually if known.'
        if season_data.get('overview'):fields['description']=plain(season_data['overview'])
        if season_data.get('air_date'):fields['release_year']=str(season_data['air_date'])[:4]
    urls=[]
    for source in [season_data,data]:
        if not source:continue
        for key,label,size in [('poster_path','Poster','w780'),('backdrop_path','Background','original')]:
            if source.get(key):urls.append((label,f'https://image.tmdb.org/t/p/{size}'+source[key]))
        for key,label,size in [('posters','Poster','w780'),('backdrops','Background','original')]:
            for image in (source.get('images') or {}).get(key,[])[:5]:
                if image.get('file_path'):urls.append((label,f'https://image.tmdb.org/t/p/{size}'+image['file_path']))
    from artwork_manager import fetch
    from add_game_metadata import validated_cover
    images=[];seen=set();failures=0
    for label,url in urls:
        if url in seen:continue
        seen.add(url)
        try:
            raw,*_=fetch(url);images.append(validated_cover(raw,'TMDB '+label,url))
        except Exception:failures+=1
    if failures:warning+=' Some artwork could not be downloaded; metadata can still be applied.'
    return {'fields':fields,'seasons':seasons,'images':images,'warning':warning.strip()}


def populated(value):
    return str(value or '').strip() not in ('','0','0:00:00','00:00:00')


def open_add_media(parent, kind, accent, refresh):
    from add_game_metadata import choose_local_cover, preview_cover, choose_artwork, image_digest
    if kind not in ('movies','shows'):raise ValueError('Invalid category')
    win=tk.Toplevel(parent);polish_dialog(win);win.title('Add '+('Movie' if kind=='movies' else 'Show'))
    win.geometry('640x740');win.minsize(480,520);win.configure(bg=PANEL);win.transient(parent.winfo_toplevel())
    previous=win.grab_current();win.grab_set()
    stage={'cover':None,'background':None,'extras':[],'available':[]}
    session={'query':'','results':[],'details':{},'selected':None,'season':None}
    closed={'value':False};widgets={};variables={}
    def signature():
        return (tuple(raw().items()),tuple(image_digest(stage[k]) if stage[k] else None for k in ('cover','background')),tuple(image_digest(i) for i in stage['extras']))
    def finish():
        closed['value']=True;win.destroy()
        if previous is not None:
            try:
                if previous.winfo_exists():previous.grab_set()
            except tk.TclError:pass
    def close(event=None):
        if signature()!=initial and not messagebox.askyesno('Unsaved Changes','Discard the unsaved metadata and artwork?',parent=win):return 'break'
        finish();return 'break'
    win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',close)
    tk.Label(win,text='Find metadata first, or enter your details manually.',bg=PANEL,fg=TEXT,font=('Arial',13,'bold')).pack(anchor='w',padx=18,pady=12)
    top=tk.Frame(win,bg=PANEL);top.pack(fill='x',padx=18)
    status=tk.StringVar(value='Nothing is saved until you press Save.')
    tk.Button(top,text='Find on TMDB…',command=lambda:open_search(win,kind,accent,raw,apply,stage,session),bg=accent,fg='white',relief='flat',pady=8).pack(side='left')
    art=tk.Menubutton(top,text='Artwork ▾',bg=PANEL_ALT,fg=TEXT,relief='flat',pady=8,padx=14);art.pack(side='left',padx=8)
    menu=tk.Menu(art,tearoff=False);art.configure(menu=menu)
    def summary():status.set('Staged: '+('cover' if stage['cover'] else 'no cover')+' · '+('background' if stage['background'] else 'no background')+f" · {len(stage['extras'])} extra images. Save to keep them.")
    def local(role):
        try:
            image=choose_local_cover(win,role.title())
            if image:stage[role]=image;summary()
        except Exception as e:messagebox.showerror('Artwork',str(e),parent=win)
    def clear(role):stage[role]=None;summary()
    def choices():
        def chosen(cover,extras,roles):stage.update(cover=cover,background=roles['background_path'],extras=extras);summary()
        choose_artwork(win,accent,stage['available'],stage['cover'],stage['extras'],chosen,roles={'background_path':stage['background']},media_label='Movie' if kind=='movies' else 'Show',role_keys=('background_path',))
    menu.add_command(label='Review available artwork…',command=choices)
    for role in ('cover','background'):
        menu.add_command(label='Choose local '+role+'…',command=lambda r=role:local(r))
        menu.add_command(label='Preview '+role,command=lambda r=role:preview_cover(win,stage[r],r.title()))
        menu.add_command(label='Clear '+role,command=lambda r=role:clear(r))
    area=tk.Frame(win,bg=PANEL);area.pack(fill='both',expand=True,padx=18,pady=10)
    canvas=tk.Canvas(area,bg=PANEL,highlightthickness=0);bar=ttk.Scrollbar(area,command=canvas.yview);bar.pack(side='right',fill='y');canvas.configure(yscrollcommand=bar.set);canvas.pack(side='left',fill='both',expand=True)
    form=tk.Frame(canvas,bg=PANEL);ident=canvas.create_window(0,0,window=form,anchor='nw')
    form.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(ident,width=e.width))
    for key,label,typ in FIELDS[kind]:
        if typ=='bool':
            var=tk.IntVar(master=win,value=0);variables[key]=var;w=tk.Checkbutton(form,text=label,variable=var,bg=PANEL,fg=TEXT,selectcolor=PANEL_ALT)
        else:
            tk.Label(form,text=label,bg=PANEL,fg=TEXT).pack(anchor='w',pady=(8,2))
            w=tk.Text(form,height=4,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT) if typ=='multiline' else tk.Entry(form,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT)
            if typ!='multiline':w.insert(0,'0:00:00' if typ=='duration' else '0' if typ=='count' else '')
        w.pack(fill='x',pady=2);widgets[key]=w
    def wheel(e):
        if win.grab_current() is not win:return
        canvas.yview_scroll(-3 if getattr(e,'num',0)==4 or getattr(e,'delta',0)>0 else 3,'units');return 'break'
    for w in [canvas,form,*form.winfo_children()]:
        for ev in ('<MouseWheel>','<Button-4>','<Button-5>'):w.bind(ev,wheel,add='+')
    def raw():return {k:variables[k].get() if t=='bool' else widgets[k].get('1.0','end-1c') if t=='multiline' else widgets[k].get() for k,_,t in FIELDS[kind]}
    def apply(values,cover,background,extras,available):
        for key,value in values.items():
            if key not in widgets:continue
            w=widgets[key];multi=next(t for k,_,t in FIELDS[kind] if k==key)=='multiline'
            w.delete('1.0' if multi else 0,'end');w.insert('1.0' if multi else 0,str(value))
        stage.update(cover=cover,background=background,extras=extras,available=available);summary()
    initial=signature()
    def save():
        try:
            values=parse_values(kind,raw());matches=duplicates(kind,values)
            if matches:
                labels='\n'.join(str(r[1])+(f' — Season {r[3]}' if kind=='shows' else '')+(f' ({r[2]})' if r[2] else '') for r in matches[:8])
                if not messagebox.askyesno('Possible duplicate','Already in your library:\n'+labels+'\n\nAdd another copy anyway?',parent=win):return
            create_media(kind,raw(),stage['cover'],stage['background'],stage['extras'])
        except InvalidField as e:
            status.set(str(e));widgets[e.key].focus_set();return
        except Exception as e:status.set('Save failed: '+str(e));return
        finish();refresh()
    footer=tk.Frame(win,bg=PANEL);footer.pack(fill='x',padx=18,pady=12)
    tk.Label(footer,textvariable=status,bg=PANEL,fg=MUTED,wraplength=400,justify='left').pack(fill='x')
    tk.Button(footer,text='Save',command=save,bg=accent,fg='white',relief='flat',padx=20,pady=8).pack(side='right',pady=8)
    tk.Button(footer,text='Cancel',command=close,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=16,pady=8).pack(side='right',padx=8)
    widgets['name'].focus_set()
    return win


def open_search(parent,kind,accent,current,on_apply,stage,session):
    from metadata_finder import search_provider
    from add_game_metadata import choose_artwork
    win=tk.Toplevel(parent);polish_dialog(win);win.title('TMDB Search & Review');win.geometry('900x740');win.minsize(700,540);win.configure(bg=PANEL);win.transient(parent)
    previous=win.grab_current();win.grab_set()
    state={'closed':False,'busy':False,'job':None,'item':None,'checks':{},'original':{},'cover':stage['cover'],'background':stage['background'],'extras':list(stage['extras']),'available':list(stage['available'])}
    inbox=queue.Queue()
    def close(event=None):
        state['closed']=True
        if state['job']:win.after_cancel(state['job'])
        win.destroy()
        if previous is not None and previous.winfo_exists():previous.grab_set()
        return 'break'
    win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',close)
    toolbar=tk.Frame(win,bg=PANEL);toolbar.pack(fill='x',padx=14,pady=10)
    query=tk.StringVar(value=session['query'] or str(current()['name']));token=tk.StringVar(value=get_setting('tmdb_token',''))
    tk.Entry(toolbar,textvariable=query,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT).pack(side='left',fill='x',expand=True)
    search_button=tk.Button(toolbar,text='Search TMDB',bg=accent,fg='white',relief='flat');search_button.pack(side='left',padx=8)
    tk.Label(win,text='TMDB API Read Access Token (saved locally)',bg=PANEL,fg=MUTED).pack(anchor='w',padx=14)
    tk.Entry(win,textvariable=token,show='•',bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT).pack(fill='x',padx=14,pady=(2,8))
    status=tk.StringVar();tk.Label(win,textvariable=status,bg=PANEL,fg=MUTED,wraplength=850,justify='left').pack(fill='x',padx=14)
    def token_changed(*a):
        try:set_setting('tmdb_token',token.get())
        except Exception:status.set('Token could not be saved locally; it can still be used for this search.')
    token.trace_add('write',token_changed)
    body=tk.Frame(win,bg=PANEL);body.pack(fill='both',expand=True,padx=14,pady=8)
    results=tk.Listbox(body,bg=PANEL_ALT,fg=TEXT,width=30,exportselection=False);results.pack(side='left',fill='y')
    resultbar=ttk.Scrollbar(body,command=results.yview);resultbar.pack(side='left',fill='y');results.configure(yscrollcommand=resultbar.set)
    right=tk.Frame(body,bg=PANEL);right.pack(side='left',fill='both',expand=True,padx=(12,0))
    season_var=tk.StringVar();season_box=ttk.Combobox(right,textvariable=season_var,state='readonly');season_numbers=[]
    if kind=='shows':
        tk.Label(right,text='Season (including Specials when available)',bg=PANEL,fg=TEXT).pack(anchor='w');season_box.pack(fill='x',pady=6)
    review_canvas=tk.Canvas(right,bg=PANEL,highlightthickness=0);rb=ttk.Scrollbar(right,command=review_canvas.yview);rb.pack(side='right',fill='y');review_canvas.configure(yscrollcommand=rb.set);review_canvas.pack(fill='both',expand=True)
    rows=tk.Frame(review_canvas,bg=PANEL);rid=review_canvas.create_window(0,0,window=rows,anchor='nw');rows.bind('<Configure>',lambda e:review_canvas.configure(scrollregion=review_canvas.bbox('all')));review_canvas.bind('<Configure>',lambda e:review_canvas.itemconfigure(rid,width=e.width))
    def wheel(e):
        if win.grab_current() is not win:return
        review_canvas.yview_scroll(-3 if getattr(e,'num',0)==4 or getattr(e,'delta',0)>0 else 3,'units');return 'break'
    def show_review(data):
        for w in rows.winfo_children():w.destroy()
        state['checks']={};state['item']=data['fields'];state['original']=current().copy();state['available']=data['images']
        for key,label,typ in FIELDS[kind]:
            value=data['fields'].get(key)
            if value is None or value=='':continue
            check=tk.BooleanVar(value=not populated(state['original'].get(key)));state['checks'][key]=check
            tk.Checkbutton(rows,text=label,variable=check,bg=PANEL,fg=TEXT,selectcolor=PANEL_ALT).pack(anchor='w',pady=(6,0))
            tk.Label(rows,text='Current: '+str(state['original'].get(key) or '(empty)')+'\nProposed: '+str(value),bg=PANEL,fg=MUTED,wraplength=460,justify='left',anchor='w').pack(fill='x')
        for w in [review_canvas,rows,*rows.winfo_children()]:
            for ev in ('<MouseWheel>','<Button-4>','<Button-5>'):w.bind(ev,wheel,add='+')
        review_canvas.yview_moveto(0);status.set(data['warning'] or 'Tick fields to apply. Existing values are unchecked. Choose artwork separately.')
    def background(work,done):
        if state['busy']:return
        state['busy']=True;search_button.configure(state='disabled');apply_button.configure(state='disabled');season_box.configure(state='disabled');results.configure(state='disabled');status.set('Loading…')
        def run():
            try:inbox.put((done,work(),None))
            except Exception as e:inbox.put((done,None,str(e)))
        threading.Thread(target=run,daemon=True).start()
    def poll():
        state['job']=None
        if state['closed']:return
        try:
            done,value,error=inbox.get_nowait();state['busy']=False;search_button.configure(state='normal');apply_button.configure(state='normal');season_box.configure(state='readonly');results.configure(state='normal');done(value,error)
        except queue.Empty:pass
        state['job']=win.after(80,poll)
    def clear_review():
        state['item']=None;state['checks']={}
        for w in rows.winfo_children():w.destroy()
    def display_results():
        results.delete(0,'end')
        for item in session['results']:results.insert('end',item['title']+' '+str(item.get('subtitle') or ''))
    def search():
        if state['busy']:return
        q=query.get().strip();t=token.get()
        if not q:status.set('Enter a title first.');return
        def done(value,error):
            if error:status.set(error);return
            session.update(query=q,results=value,selected=None,season=None);display_results();clear_review();season_box.configure(values=());season_var.set('');status.set(f'{len(value)} results. Select a match.' if value else 'No matches. Try another title or enter details manually.')
        background(lambda:search_provider(kind,q,'TMDB',t),done)
    def load(item,season=None):
        key=(str(item['detail']),season);t=token.get()
        def done(value,error):
            if error:status.set(error);clear_review();return
            session['details'][key]=copy.deepcopy(value)
            if kind=='shows' and season is None:
                season_numbers[:]=[s['season_number'] for s in value['seasons']]
                season_box.configure(values=[f'{s["season_number"]} — {s.get("name") or "Season"}' for s in value['seasons']]);season_var.set('');clear_review();status.set(value['warning']);return
            show_review(value)
        if key in session['details']:done(copy.deepcopy(session['details'][key]),None)
        else:background(lambda:load_tmdb(kind,item,t,season),done)
    def selected(event=None):
        if state['busy']:return
        selection=results.curselection()
        if not selection:return
        item=session['results'][selection[0]];session['selected']=selection[0];session['season']=None;clear_review();load(item)
    def season_selected(event=None):
        if state['busy'] or session['selected'] is None:return
        index=season_box.current()
        if index<0:return
        number=season_numbers[index];session['season']=number;clear_review();load(session['results'][session['selected']],number)
    def artwork():
        if state['busy']:return
        def chosen(cover,extras,roles):
            state.update(cover=cover,background=roles['background_path'],extras=extras)
            status.set('Artwork choices staged for Apply; search and results are retained.')
        choose_artwork(win,accent,state['available'],state['cover'],state['extras'],chosen,roles={'background_path':state['background']},media_label='Movie' if kind=='movies' else 'Show',role_keys=('background_path',))
    def apply():
        if state['busy']:return
        selected_values={k:state['item'][k] for k,v in state['checks'].items() if v.get()} if state['item'] else {}
        latest=current()
        if any(str(latest[k])!=str(state['original'].get(k)) for k in selected_values):
            if not messagebox.askyesno('Review changed values','Some selected form fields changed since review. Replace them with the selected TMDB values?',parent=win):return
        on_apply(selected_values,state['cover'],state['background'],state['extras'],state['available']);status.set('Applied to the Add form. Nothing is saved until Save. Continue reviewing or close this window.')
    footer=tk.Frame(win,bg=PANEL);footer.pack(fill='x',padx=14,pady=12)
    tk.Button(footer,text='Choose artwork…',command=artwork,bg=PANEL_ALT,fg=TEXT,relief='flat',pady=8).pack(side='left')
    apply_button=tk.Button(footer,text='Apply selected',command=apply,bg=accent,fg='white',relief='flat',pady=8);apply_button.pack(side='right')
    tk.Button(footer,text='Close',command=close,bg=PANEL_ALT,fg=TEXT,relief='flat',pady=8).pack(side='right',padx=8)
    search_button.configure(command=search);results.bind('<<ListboxSelect>>',selected);season_box.bind('<<ComboboxSelected>>',season_selected)
    display_results()
    if session['selected'] is not None and session['selected']<len(session['results']):
        index=session['selected'];results.selection_set(index);results.see(index);item=session['results'][index];number=session['season'];load(item)
        if kind=='shows' and number is not None:
            info=session['details'].get((str(item['detail']),None),{});season_numbers[:]=[s['season_number'] for s in info.get('seasons',[])];season_box.configure(values=[f'{s["season_number"]} — {s.get("name") or "Season"}' for s in info.get('seasons',[])])
            if number in season_numbers:season_box.current(season_numbers.index(number))
    state['job']=win.after(80,poll)
    return win
