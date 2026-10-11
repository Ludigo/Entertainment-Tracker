"""In-window tools for the exact saved records behind a filtered library."""
import tkinter as tk
from tkinter import ttk,filedialog
from datetime import date
from pathlib import Path
from database import connection,PROJECT_ROOT,get_setting
from theme import BG,PANEL,PANEL_ALT,TEXT,MUTED
from utils import format_time
from collection_manager_data import (records,bulk_update,purchase,values_summary,duplicates,
    different_edition,shelves,create_shelf,shelf_change,missing_fields,sessions,correct_session)

def open_workspace(parent,kind,ids,refresh,tab=None):
    from collection_tools import expand_ids
    ids=expand_ids(kind,ids)
    old=getattr(parent,'_collection_workspace',None)
    if old is not None and old.winfo_exists():old.destroy()
    page=tk.Frame(parent,bg=BG);page.place(relx=0,rely=0,relwidth=1,relheight=1);page.lift()
    parent._collection_workspace=page;accent=get_setting('accent_color','#B23A48')
    status=tk.StringVar(value='Select saved records below. Actions affect only selected IDs, including individual seasons/editions.')
    def close():page.destroy();parent._collection_workspace=None;refresh()
    top=tk.Frame(page,bg=BG);top.pack(fill='x',padx=18,pady=12)
    tk.Button(top,text='← Library',command=close,bg=PANEL_ALT,fg=TEXT).pack(side='left')
    tk.Label(top,text=kind.title()+' · Collection Tools',bg=BG,fg=TEXT,font=('Arial',18,'bold')).pack(side='left',padx=15)
    amount=tk.StringVar();tk.Label(page,textvariable=amount,bg=BG,fg=MUTED,wraplength=1100,justify='left').pack(fill='x',padx=18)
    selector=tk.Frame(page,bg=BG);selector.pack(fill='x',padx=18,pady=7)
    table=ttk.Treeview(selector,columns=('id','title','edition','ownership'),show='headings',height=5,selectmode='extended')
    for name,label,width in [('id','ID',55),('title','Title',330),('edition','Platform / artist / season',260),('ownership','Ownership',160)]:
        table.heading(name,text=label);table.column(name,width=width,stretch=name!='id')
    scroll=ttk.Scrollbar(selector,command=table.yview);table.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');table.pack(fill='x',expand=True)
    controls=tk.Frame(page,bg=BG);controls.pack(fill='x',padx=18)
    tk.Button(controls,text='Select all shown records',command=lambda:table.selection_set(table.get_children()),bg=PANEL_ALT,fg=TEXT).pack(side='left')
    tk.Button(controls,text='Clear selection',command=lambda:table.selection_remove(table.selection()),bg=PANEL_ALT,fg=TEXT).pack(side='left',padx=5)
    def chosen():return list(map(int,table.selection()))
    def export():
        from collection_tools import export_rows
        dest=filedialog.asksaveasfilename(parent=page,title='Export current filtered collection',defaultextension='.csv',initialfile=kind+'_filtered.csv',filetypes=[('CSV','*.csv')])
        if dest:
            try:status.set(str(export_rows(kind,ids,dest))+' records exported.')
            except Exception as exc:status.set('Export failed: '+str(exc))
    tk.Button(controls,text='Export filtered CSV…',command=export,bg=PANEL_ALT,fg=TEXT).pack(side='right')
    book=ttk.Notebook(page);book.pack(fill='both',expand=True,padx=18,pady=12)
    tabs={}
    for name in ['Bulk edit','Duplicates','Missing & artwork','Shelves','Purchase','Sessions']:
        frame=tk.Frame(book,bg=PANEL,padx=12,pady=10);book.add(frame,text=name);tabs[name]=frame
    def label(host,text):tk.Label(host,text=text,bg=PANEL,fg=MUTED,wraplength=900,justify='left').pack(anchor='w',pady=4)
    def entry(host,title,value=''):
        line=tk.Frame(host,bg=PANEL);line.pack(fill='x',pady=4)
        tk.Label(line,text=title,bg=PANEL,fg=TEXT,width=28,anchor='w').pack(side='left')
        var=tk.StringVar(value=value);tk.Entry(line,textvariable=var,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT).pack(side='left',fill='x',expand=True)
        return var
    def button(host,text,fn):
        def guarded():
            try:fn()
            except Exception as exc:status.set('Could not save: '+str(exc))
        widget=tk.Button(host,text=text,command=guarded,bg=PANEL_ALT,fg=TEXT,pady=6);widget.pack(anchor='w',pady=5);return widget
    def reload():
        keep=table.selection();table.delete(*table.get_children())
        for row in records(kind,ids):
            edition=row.get('platform') or row.get('artist') or row.get('author') or ('Season '+str(row.get('season')) if kind=='shows' else str(row.get('release_year') or ''))
            owned='Physical + Digital' if row.get('owned_physical') and row.get('owned_digital') else 'Physical' if row.get('owned_physical') else 'Digital' if row.get('owned_digital') else 'Unspecified' if row.get('owned') else 'Not owned'
            table.insert('','end',iid=str(row['id']),values=(row['id'],row['name'],edition,owned))
        table.selection_set([i for i in keep if table.exists(i)]);amount.set(values_summary(kind,ids));load_duplicates();load_queue();load_sessions()

    bulk=tabs['Bulk edit'];label(bulk,'Choose one field, enter its proposed value, then review the selected records before applying. Tags replace the existing tag list. Blank value clears text or estimated value. Nothing is deleted.')
    fields={'Physical ownership':'owned_physical','Digital ownership':'owned_digital','Wishlist':'wishlist','Tags':'tags','Condition':'condition','Estimated value (£)':'estimated_value'}
    if kind=='games':fields['Backlog']='backlog'
    field=tk.StringVar(value=next(iter(fields)));ttk.Combobox(bulk,textvariable=field,values=list(fields),state='readonly').pack(anchor='w')
    value=entry(bulk,'Value (flags: 1=yes, 0=no)');review=tk.StringVar();label_widget=tk.Label(bulk,textvariable=review,bg=PANEL,fg=TEXT,wraplength=950,justify='left');label_widget.pack(anchor='w',pady=6)
    pending={}
    def review_bulk():
        selected=chosen()
        if not selected:raise ValueError('Select records first.')
        pending.update(ids=selected,field=fields[field.get()],value=value.get(),rows=records(kind,selected))
        review.set('Will update '+str(len(selected))+' records: '+', '.join('#'+str(r['id'])+' '+r['name'] for r in pending['rows'])[:600]+'\n'+field.get()+' → '+(value.get() or '(clear)'))
    def apply_bulk():
        if not pending or pending['ids']!=chosen() or pending['field']!=fields[field.get()] or pending['value']!=value.get():raise ValueError('Review this selection and proposed value first.')
        if records(kind,pending['ids'])!=pending['rows']:raise ValueError('Records changed since review. Review again.')
        n=bulk_update(kind,pending['ids'],pending['field'],pending['value']);pending.clear();review.set('');reload();status.set(str(n)+' records updated.')
    button(bulk,'Review bulk change',review_bulk);button(bulk,'Apply reviewed change',apply_bulk)

    duplicate=tabs['Duplicates'];label(duplicate,'Possible duplicates are suggestions. Select a pair to compare its saved metadata below. Different edition keeps both records and hides this pair from future reviews; albums also stay separate.')
    pairs=[];pairbox=ttk.Combobox(duplicate,state='readonly',width=75);pairbox.pack(fill='x')
    comparison=tk.Text(duplicate,height=5,bg=PANEL_ALT,fg=TEXT,wrap='word');comparison.pack(fill='both',expand=True,pady=6)
    def compare(event=None):
        index=pairbox.current()
        if not 0<=index<len(pairs):return
        comparison.configure(state='normal');comparison.delete('1.0','end')
        first,second=pairs[index]
        comparison.insert('end',f"Record #{first['id']}  |  Record #{second['id']}\n")
        for key in ['name','platform','artist','author','season','release_year','barcode','label','price_paid','owned_physical','owned_digital','description','notes']:
            if key in first:comparison.insert('end',f"{key}: {first.get(key) or '—'}  |  {second.get(key) or '—'}\n")
        comparison.configure(state='disabled')
    pairbox.bind('<<ComboboxSelected>>',compare)
    def load_duplicates():
        pairs[:]=duplicates(kind,ids);pairbox.configure(values=[f"#{a['id']} / #{b['id']} · {a['name']}" for a,b in pairs])
        if pairs:pairbox.current(0);compare()
        else:pairbox.set('No unreviewed possible duplicates');comparison.configure(state='normal');comparison.delete('1.0','end');comparison.configure(state='disabled')
    def mark_different():
        i=pairbox.current()
        if not 0<=i<len(pairs):raise ValueError('Select a pair.')
        a,b=pairs[i];different_edition(kind,a['id'],b['id']);reload();status.set('Both records retained; pair marked as different editions.')
    def reset_duplicates():
        with connection:connection.execute('DELETE FROM duplicate_exceptions WHERE kind=?',(kind,))
        load_duplicates();status.set('Duplicate review decisions reset. Album separation flags remain in Album Metadata.')
    button(duplicate,'Different edition · keep both',mark_different);button(duplicate,'Reset review decisions',reset_duplicates)

    shelf=tabs['Shelves'];label(shelf,'Shelves work across collections without changing tags. Membership applies to selected saved records. Use the Shelf filter in the library to view a shelf.')
    shelf_name=entry(shelf,'New shelf name');shelf_box=ttk.Combobox(shelf,state='readonly',width=35);shelf_box.pack(anchor='w',pady=5);shelf_rows=[]
    def load_shelves():
        shelf_rows[:]=shelves();shelf_box.configure(values=[name for ident,name in shelf_rows])
        if shelf_rows:shelf_box.current(0)
    def add_shelf():create_shelf(shelf_name.get());load_shelves();status.set('Shelf created.')
    def member(add):
        i=shelf_box.current()
        if not 0<=i<len(shelf_rows):raise ValueError('Choose a shelf.')
        n=shelf_change(kind,chosen(),shelf_rows[i][0],add);status.set(str(n)+' shelf memberships '+('added.' if add else 'removed.'))
    button(shelf,'Create shelf',add_shelf);button(shelf,'Add selected records to shelf',lambda:member(True));button(shelf,'Remove selected records from shelf',lambda:member(False));load_shelves()

    buy=tabs['Purchase'];label(buy,'Purchase selected wishlist entries. Price is per saved record; review the IDs first. This records ownership, clears Wishlist and saves price, shop and date together.')
    price=entry(buy,'Price paid per record (£)','0');shop=entry(buy,'Shop / seller');purchased=entry(buy,'Purchase date (YYYY-MM-DD)',date.today().isoformat())
    physical=tk.IntVar(value=1);digital=tk.IntVar(value=0)
    for title,var in [('Physical',physical),('Digital',digital)]:tk.Checkbutton(buy,text=title,variable=var,bg=PANEL,fg=TEXT,selectcolor=PANEL_ALT).pack(anchor='w')
    buy_review=tk.StringVar();tk.Label(buy,textvariable=buy_review,bg=PANEL,fg=TEXT,wraplength=900).pack(anchor='w');buy_pending={}
    def review_purchase():
        rows=records(kind,chosen())
        if not rows or any(not r.get('wishlist') for r in rows):raise ValueError('Select only wishlist records.')
        buy_pending.update(ids=chosen(),values=(price.get(),shop.get(),purchased.get(),physical.get(),digital.get()),rows=rows)
        buy_review.set('Purchase '+str(len(rows))+' records: '+', '.join('#'+str(r['id']) for r in rows)+' · £'+price.get()+' each · '+purchased.get())
    def apply_purchase():
        vals=(price.get(),shop.get(),purchased.get(),physical.get(),digital.get())
        if not buy_pending or buy_pending['ids']!=chosen() or buy_pending['values']!=vals or records(kind,chosen())!=buy_pending['rows']:raise ValueError('Review the current purchase first.')
        n=purchase(kind,chosen(),*vals);buy_pending.clear();buy_review.set('');reload();status.set(str(n)+' purchases saved.')
    button(buy,'Review purchase',review_purchase);button(buy,'Save reviewed purchase',apply_purchase)

    queue=tabs['Missing & artwork'];queue_rows=[];position=[0];photo=[None]
    queue_mode=tk.StringVar(value='Missing artwork');ttk.Combobox(queue,textvariable=queue_mode,values=['Missing artwork','Missing metadata'],state='readonly').pack(anchor='w')
    queue_heading=tk.StringVar();tk.Label(queue,textvariable=queue_heading,bg=PANEL,fg=TEXT,wraplength=1000).pack(anchor='w',pady=6)
    preview=tk.Label(queue,bg=PANEL_ALT,fg=MUTED);preview.pack(anchor='w')
    def current():
        if not queue_rows:raise ValueError('No entries need review in this filtered collection.')
        return queue_rows[position[0]]
    def draw_queue():
        photo[0]=None;preview.configure(image='',text='No cover preview')
        if not queue_rows:queue_heading.set('No matching entries need review.');return
        row=current();queue_heading.set(f"{position[0]+1} / {len(queue_rows)} · #{row['id']} · {row['name']}\nMissing: "+', '.join(missing_fields(kind,row)))
        try:
            from PIL import Image,ImageTk,ImageOps
            path=Path(row.get('cover_path') or '');path=path if path.is_absolute() else PROJECT_ROOT/path
            with Image.open(path) as source:picture=ImageOps.contain(source.convert('RGBA'),(260,130))
            photo[0]=ImageTk.PhotoImage(picture);preview.configure(image=photo[0],text='')
        except (OSError,ValueError):pass
    def load_queue():
        old=queue_rows[position[0]]['id'] if queue_rows and position[0]<len(queue_rows) else None
        queue_rows[:]=[r for r in records(kind,ids) if any(f in ('cover_path','background_path') for f in missing_fields(kind,r))] if queue_mode.get()=='Missing artwork' else [r for r in records(kind,ids) if any(f!='background_path' for f in missing_fields(kind,r))]
        position[0]=next((i for i,r in enumerate(queue_rows) if r['id']==old),min(position[0],max(0,len(queue_rows)-1)));draw_queue()
    queue_mode.trace_add('write',lambda *a:load_queue())
    def move(delta):position[0]=max(0,min(len(queue_rows)-1,position[0]+delta));draw_queue()
    nav=tk.Frame(queue,bg=PANEL);nav.pack(fill='x',pady=5)
    for title,delta in [('← Previous',-1),('Skip / Next →',1)]:tk.Button(nav,text=title,command=lambda delta=delta:move(delta),bg=PANEL_ALT,fg=TEXT).pack(side='left',padx=3)
    role=tk.StringVar(value='Cover');ttk.Combobox(nav,textvariable=role,values=['Cover','Background','Logo'],state='readonly',width=12).pack(side='left',padx=8)
    def assign_local():
        row=current();key={'Cover':'cover_path','Background':'background_path','Logo':'logo_path'}[role.get()]
        from artwork_preferences import require_unlocked
        require_unlocked(kind,row['id'],key)
        path=filedialog.askopenfilename(parent=page,title='Choose '+role.get(),filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.bmp')])
        if not path:return
        from add_game_metadata import validated_cover
        from artwork_manager import store
        item=validated_cover(Path(path).read_bytes(),Path(path).name)
        saved=store(kind,row['id'],item['raw'],item['w'],item['h'],item['ext'],'Local artwork review',set_cover=key=='cover_path')
        if key!='cover_path':
            if kind=='games':
                from details import _set_game_art
                _set_game_art(row['id'],key,saved)
            else:
                from movie_cinematic import set_background,set_logo
                (set_logo if key=='logo_path' else set_background)(row['id'],saved,kind)
        reload();status.set(role.get()+' saved; queue position retained.')
    def metadata():
        row=current()
        if kind=='cds':
            from cd_editor import open_editor
            open_editor(page,accent,reload,item_id=row['id'])
        else:
            from metadata_finder import open_finder
            open_finder(page,kind,row['id'],row['name'],accent,on_saved=reload)
    button(queue,'Choose artwork from PC…',assign_local);button(queue,'Find metadata & artwork…',metadata)

    history=tabs['Sessions'];label(history,'Correct saved game, book or album sessions. Dates require a timezone offset. Duration changes adjust the tracked total by the difference, preserving other recorded/manual time. No full-play/completion counts are changed.')
    history_rows=[];sessionbox=ttk.Combobox(history,state='readonly',width=80);sessionbox.pack(fill='x')
    started=entry(history,'Start (ISO date/time + offset)');duration=entry(history,'Duration (H:MM:SS)');note=entry(history,'Note')
    expected={}
    def load_session(event=None):
        i=sessionbox.current()
        if not 0<=i<len(history_rows):return
        row=history_rows[i];expected.clear();expected.update(row);started.set(row['started_at']);duration.set(format_time(row['duration_seconds']/3600));note.set(row.get('note') or '')
    def load_sessions():
        keep=expected.get('id');history_rows[:]=sessions(kind,chosen() or ids)
        sessionbox.configure(values=[f"#{r['id']} · Record #{r[next(k for k in ('game_id','book_id','cd_id') if k in r)]} · {r['started_at']} · {format_time(r['duration_seconds']/3600)}" for r in history_rows])
        if history_rows:sessionbox.current(next((i for i,r in enumerate(history_rows) if r['id']==keep),0));load_session()
        else:sessionbox.set('No timed sessions in this selection');expected.clear()
    sessionbox.bind('<<ComboboxSelected>>',load_session)
    table.bind('<<TreeviewSelect>>',lambda e:load_sessions())
    def save_session():
        if not expected:raise ValueError('Select a session first.')
        root=page.winfo_toplevel();timer=getattr(root,'manual_timer',None);tracker=getattr(root,'game_tracker',None)
        if timer is not None and timer.kind is not None or tracker is not None and tracker.active:raise ValueError('Stop active timers before correcting session history.')
        correct_session(kind,expected['id'],started.get(),duration.get(),note.get(),dict(expected));reload();status.set('Session corrected and tracked total updated.')
    button(history,'Save session correction',save_session)
    tk.Label(page,textvariable=status,bg=BG,fg=MUTED,wraplength=1150,justify='left').pack(fill='x',padx=18,pady=(0,10))
    reload()
    if tab in tabs:book.select(tabs[tab])
    return page
