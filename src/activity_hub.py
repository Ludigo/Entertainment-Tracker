"""Continue, picks, goals and recent additions inside the existing app window."""
import tkinter as tk
from tkinter import ttk
from theme import BG,PANEL,PANEL_ALT,TEXT,MUTED
from collection_visibility import visible_sections,SECTIONS
from activity_data import (continue_records,recent_records,pick_candidates,choose_candidate,
    label,progress_text,duration_minutes,quick_progress,undo_progress,goal_rows,save_goals,month_key)

TABS=('Continue','Pick Something','Goals','Recent Additions')


def open_hub(parent,accent,on_open,state=None):
    state=state if state is not None else {}
    state.setdefault('tab','Continue');state.setdefault('kind','All')
    page=tk.Frame(parent,bg=BG);page.pack(fill='both',expand=True)
    page.grid_columnconfigure(0,weight=1);page.grid_rowconfigure(3,weight=1)
    header=tk.Frame(page,bg=BG);header.grid(row=0,column=0,sticky='ew',padx=20,pady=(18,8))
    tk.Label(header,text='Continue & Explore',font=('Arial',22,'bold'),bg=BG,fg=TEXT).pack(anchor='w')
    tk.Label(header,text='Pick your next activity, update progress and keep your goals in view.',bg=BG,fg=MUTED,wraplength=700,justify='left').pack(anchor='w',pady=(4,0))
    tabs=tk.Frame(page,bg=BG);tabs.grid(row=1,column=0,sticky='ew',padx=20,pady=8)
    controls=tk.Frame(page,bg=PANEL,padx=12,pady=10);controls.grid(row=2,column=0,sticky='ew',padx=20)
    body=tk.Frame(page,bg=BG);body.grid(row=3,column=0,sticky='nsew',padx=20,pady=10)
    footer=tk.Frame(page,bg=PANEL,padx=12,pady=10);footer.grid(row=4,column=0,sticky='ew',padx=20,pady=(0,14))
    status=tk.StringVar(value='Select an item to open details or update its progress here.')
    tk.Label(footer,textvariable=status,bg=PANEL,fg=MUTED,wraplength=760,justify='left',anchor='w').pack(fill='x')
    progress_panel=tk.Frame(footer,bg=PANEL);progress_panel.pack(fill='x',pady=(8,0))
    selection_label=tk.StringVar();tk.Label(progress_panel,textvariable=selection_label,bg=PANEL,fg=TEXT,font=('Arial',10,'bold'),wraplength=760,justify='left').pack(anchor='w')
    progress_buttons=tk.Frame(progress_panel,bg=PANEL);progress_buttons.pack(fill='x',pady=(6,0))
    undo_button=tk.Button(footer,text='Undo Last Progress Update',bg=PANEL_ALT,fg=TEXT,relief='flat',padx=10,pady=6)
    data={'tree':None,'rows':{},'selected':None,'undo':state.get('undo'),'pick':None}
    tab_buttons={}
    def button(parent,text,command,primary=False):
        b=tk.Button(parent,text=text,command=command,bg=accent if primary else PANEL_ALT,fg='white' if primary else TEXT,
                    activebackground=accent,activeforeground='white',relief='flat',padx=10,pady=7,cursor='hand2')
        b.pack(side='left',padx=(0,7));return b
    def undo():
        try:
            if data['undo'] is None:return
            undo_progress(data['undo']);data['undo']=None;state['undo']=None;undo_button.pack_forget()
            build();status.set('Last progress update undone.')
        except ValueError as exc:status.set(str(exc))
    undo_button.configure(command=undo)
    def update(record,action,value=None):
        try:
            data['undo']=quick_progress(record['kind'],record['id'],action,value)
            state['undo']=data['undo']
            if state['tab']=='Pick Something' and action=='start':
                state.update(tab='Continue',kind=record['kind'],selection=(record['kind'],record['id']))
            undo_button.pack(anchor='w',pady=(8,0));build()
            status.set('Progress saved. Undo is available below.')
        except Exception as exc:
            status.set(str(exc))
    def open_selected():
        r=data['selected']
        if r:
            state['selection']=(r['kind'],r['id']);on_open(r['kind'],r['id'])
    def selected(event=None):
        tree=data['tree'];ids=tree.selection() if tree else ()
        r=data['rows'].get(ids[0]) if ids else None;data['selected']=r
        for child in progress_buttons.winfo_children():child.destroy()
        selection_label.set(label(r) if r else '')
        if r is None:return
        state['selection']=(r['kind'],r['id'])
        button(progress_buttons,'Open Details',open_selected,True)
        kind=r['kind']
        if kind=='cds':
            tk.Label(progress_buttons,text='Log listening in album details.',bg=PANEL,fg=MUTED).pack(side='left');return
        if r.get('completed'):
            button(progress_buttons,'Start Again',lambda:update(r,'start'))
            if kind=='movies':button(progress_buttons,'Log Another Watch',lambda:update(r,'finish'))
            return
        if not r.get('in_progress'):button(progress_buttons,'Start',lambda:update(r,'start'))
        if kind=='shows':button(progress_buttons,'+1 Episode',lambda:update(r,'episode'),True)
        if kind=='books':
            entry=tk.Entry(progress_buttons,width=7,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT)
            entry.insert(0,str(r.get('page_reached') or 0));entry.pack(side='left',padx=(0,5),ipady=5)
            button(progress_buttons,'Save Pages',lambda:update(r,'pages',entry.get()))
            entry.bind('<Return>',lambda e:update(r,'pages',entry.get()))
        button(progress_buttons,'Finish Season' if kind=='shows' else 'Mark Finished' if kind=='games' else 'Finish Book' if kind=='books' else 'Log Full Watch',lambda:update(r,'finish'))
    def make_table(rows,recent=False):
        host=tk.Frame(body,bg=PANEL);host.pack(fill='both',expand=True)
        host.grid_columnconfigure(0,weight=1);host.grid_rowconfigure(0,weight=1)
        columns=('Title','Section','Progress')+(('Added','Purchased','Price') if recent else ())
        tree=ttk.Treeview(host,columns=columns,show='headings',selectmode='browse');data['tree']=tree;data['rows']={}
        for col in columns:
            tree.heading(col,text=col);tree.column(col,width=300 if col=='Title' else 210 if col=='Progress' else 150,minwidth=100)
        tree.grid(row=0,column=0,sticky='nsew')
        bar=ttk.Scrollbar(host,orient='vertical',command=tree.yview);bar.grid(row=0,column=1,sticky='ns')
        xbar=ttk.Scrollbar(host,orient='horizontal',command=tree.xview);xbar.grid(row=1,column=0,sticky='ew')
        tree.configure(yscrollcommand=bar.set,xscrollcommand=xbar.set)
        for r in rows:
            key=f"{r['kind']}:{r['id']}";data['rows'][key]=r
            values=(label(r),SECTIONS[r['kind']],progress_text(r))
            if recent:values+=(r.get('added_at') or 'Date unknown',r.get('purchase_date') or 'Not recorded',
                               'Not recorded' if r.get('price_paid') is None else f"£{r['price_paid']:,.2f}")
            tree.insert('','end',iid=key,values=values)
        tree.bind('<<TreeviewSelect>>',selected);tree.bind('<Double-1>',lambda e:open_selected());tree.bind('<Return>',lambda e:open_selected())
        previous=state.get('selection');key=f'{previous[0]}:{previous[1]}' if previous else None
        if key in data['rows']:tree.selection_set(key);tree.see(key);selected()
        if not rows:
            status.set('No matching items. Try another filter, or start an item from Recent Additions.')
    def filter_section():
        visible=visible_sections();choices=['All']+[SECTIONS[k] for k in visible]
        old=state.get('kind','All')
        if old not in visible:state['kind']='All'
        value=SECTIONS.get(old,'All') if old in visible else 'All'
        var=tk.StringVar(value=value)
        tk.Label(controls,text='Section',bg=PANEL,fg=MUTED).pack(side='left',padx=(0,6))
        combo=ttk.Combobox(controls,values=choices,textvariable=var,state='readonly',width=13);combo.pack(side='left',padx=(0,12))
        def changed(event=None):
            state['kind']=next((k for k in visible if SECTIONS[k]==var.get()),'All');build()
        combo.bind('<<ComboboxSelected>>',changed)
    def scrolling_body():
        host=tk.Frame(body,bg=BG);host.pack(fill='both',expand=True)
        canvas=tk.Canvas(host,bg=BG,highlightthickness=0,yscrollincrement=24)
        bar=ttk.Scrollbar(host,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        inner=tk.Frame(canvas,bg=BG);ident=canvas.create_window(0,0,window=inner,anchor='nw')
        inner.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(ident,width=e.width))
        tag=f'HubScroll{id(canvas)}'
        def wheel(event):
            number=getattr(event,'num',None);delta=getattr(event,'delta',0)
            if number not in (4,5) and not delta:return
            canvas.yview_scroll(-3 if number==4 or delta>0 else 3,'units');return 'break'
        for event in ('<MouseWheel>','<Button-4>','<Button-5>'):canvas.bind_class(tag,event,wheel)
        def add_tags(widget):
            widget.bindtags((tag,)+tuple(t for t in widget.bindtags() if t!=tag))
            for child in widget.winfo_children():add_tags(child)
        inner._hub_bind_wheel=lambda:add_tags(inner)
        def ready():
            if canvas.winfo_exists():add_tags(inner)
        job=canvas.after_idle(ready)
        def cleanup(event):
            if event.widget is canvas:
                canvas.after_cancel(job)
                for name in ('<MouseWheel>','<Button-4>','<Button-5>'):canvas.unbind_class(tag,name)
        canvas.bind('<Destroy>',cleanup)
        return inner
    def goals():
        progress_panel.pack_forget()
        rows=goal_rows();entries={};holder=scrolling_body()
        if not rows:status.set('Enable Games, Shows or Books in Settings to use completion goals.')
        box=tk.Frame(holder,bg=PANEL,padx=18,pady=16);box.pack(fill='x')
        tk.Label(box,text='Monthly goals · '+month_key(),font=('Arial',16,'bold'),bg=PANEL,fg=TEXT).pack(anchor='w')
        tk.Label(box,text='Progress is counted from dated changes recorded after this update. Older completions have no date and are not added to this month. Set a target to 0 to turn it off.',bg=PANEL,fg=MUTED,wraplength=700,justify='left').pack(anchor='w',pady=(8,14))
        for r in rows:
            row=tk.Frame(box,bg=PANEL);row.pack(fill='x',pady=7)
            tk.Label(row,text=r['label'],bg=PANEL,fg=TEXT,width=22,anchor='w').pack(side='left')
            entry=tk.Entry(row,width=8,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT);entry.insert(0,str(r['target']));entry.pack(side='left',ipady=6);entries[r['kind']]=entry
            tk.Label(row,text=f"   {r['amount']} / {r['target']}" if r['target'] else f"   {r['amount']} this month · target off",bg=PANEL,fg=accent).pack(side='left')
            if r['target']:
                ttk.Progressbar(box,value=min(100,r['amount']/r['target']*100),maximum=100).pack(fill='x',pady=(0,6))
        def save():
            try:save_goals({kind:entry.get() for kind,entry in entries.items()});build();status.set('Monthly goals saved.')
            except ValueError as exc:status.set(str(exc))
        actions=tk.Frame(box,bg=PANEL);actions.pack(fill='x',pady=14);button(actions,'Save Goals',save,True)
        for entry in entries.values():entry.bind('<Return>',lambda e:save())
        status.set('Goals are saved for this month. Hidden sections are excluded.')
    def picks():
        progress_panel.pack_forget()
        holder=scrolling_body()
        visible=visible_sections();kind=state.get('pick_kind','All')
        if kind not in visible:kind='All'
        section=tk.StringVar(value=SECTIONS.get(kind,'All'))
        platform=tk.StringVar(value=state.get('platform',''));genre=tk.StringVar(value=state.get('genre',''))
        minutes=tk.StringVar(value=state.get('minutes',''));unknown=tk.BooleanVar(value=state.get('unknown',False))
        line=tk.Frame(holder,bg=PANEL,padx=14,pady=14);line.pack(fill='x');filter_entries=[]
        for name,var,width in [('Section',section,13),('Platform',platform,15),('Genre',genre,17),('Minutes available',minutes,8)]:
            row=tk.Frame(line,bg=PANEL);row.pack(fill='x',pady=4)
            tk.Label(row,text=name,bg=PANEL,fg=TEXT,width=20,anchor='w').pack(side='left')
            if name=='Section':widget=ttk.Combobox(row,values=['All']+[SECTIONS[k] for k in visible],textvariable=var,state='readonly',width=width)
            else:widget=tk.Entry(row,textvariable=var,width=width,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT)
            widget.pack(side='left',ipady=5)
            if name!='Section':filter_entries.append(widget)
        tk.Checkbutton(line,text='Include items with unknown length when filtering by time',variable=unknown,bg=PANEL,fg=TEXT,selectcolor=PANEL_ALT,activebackground=PANEL).pack(anchor='w',pady=8)
        tk.Label(line,text='Uses unfinished/unplayed collection items, excluding the wishlist. Time compares a movie, one average show episode, or a full album with recorded track lengths. Game/book length is unknown. Leave minutes blank for any length.',bg=PANEL,fg=MUTED,wraplength=700,justify='left').pack(anchor='w',pady=6)
        result_box=tk.Frame(holder,bg=PANEL,padx=14,pady=14);result_box.pack(fill='x',pady=12)
        def choose():
            try:
                kind=next((k for k in visible if SECTIONS[k]==section.get()),'All')
                state.update(pick_kind=kind,platform=platform.get(),genre=genre.get(),minutes=minutes.get(),unknown=unknown.get())
                rows=pick_candidates(kind,platform.get().strip(),genre.get().strip(),minutes.get().strip() or 0,unknown.get())
                r=choose_candidate(rows,state.get('last_pick'))
                for child in result_box.winfo_children():child.destroy()
                if r is None:status.set('No matching backlog items. Widen your filters or include unknown lengths.');return
                state['last_pick']=(r['kind'],r['id']);data['pick']=r
                tk.Label(result_box,text=label(r),bg=PANEL,fg=TEXT,font=('Arial',17,'bold'),wraplength=700,justify='left').pack(anchor='w')
                duration=duration_minutes(r)
                tk.Label(result_box,text=SECTIONS[r['kind']]+' · '+progress_text(r)+(' · '+f'{duration:.0f} minutes' if duration else ' · length unknown'),bg=PANEL,fg=MUTED,wraplength=700,justify='left').pack(anchor='w',pady=8)
                actions=tk.Frame(result_box,bg=PANEL);actions.pack(fill='x')
                button(actions,'Open Details',lambda:on_open(r['kind'],r['id']),True)
                if r['kind']!='cds':button(actions,'Start This',lambda:update(r,'start'))
                holder._hub_bind_wheel()
                status.set(f'Picked from {len(rows)} matching items. Pick Again avoids repeating the same item when alternatives exist.')
            except (ValueError,OverflowError) as exc:status.set('Check your filters: '+str(exc))
        buttons=tk.Frame(line,bg=PANEL);buttons.pack(fill='x',pady=8);button(buttons,'Pick Something / Pick Again',choose,True)
        for entry in filter_entries:entry.bind('<Return>',lambda e:choose())
        status.set('Choose filters, then pick something from your collection.')
    def build():
        for frame in (controls,body,progress_buttons):
            for child in frame.winfo_children():child.destroy()
        data['tree']=None;data['rows']={};data['selected']=None;selection_label.set('')
        progress_panel.pack(fill='x',pady=(8,0))
        tab=state['tab']
        for name,b in tab_buttons.items():b.configure(bg=accent if name==tab else PANEL_ALT,fg='white' if name==tab else TEXT)
        if tab=='Goals':goals();return
        if tab=='Pick Something':picks();return
        filter_section();rows=continue_records() if tab=='Continue' else recent_records(kind=state.get("kind","All"))
        if state.get('kind','All')!='All':rows=[r for r in rows if r['kind']==state['kind']]
        make_table(rows,tab=='Recent Additions')
        tk.Label(controls,text=f'{len(rows)} items'+(' · last 100 records; older dates unknown' if tab=='Recent Additions' else ' · shows listed by season'),bg=PANEL,fg=MUTED).pack(side='left')
        if rows:status.set('Select a row to update progress here. Double-click opens details in this window.')
    def change_tab(name):state['tab']=name;build()
    for name in TABS:tab_buttons[name]=button(tabs,name,lambda n=name:change_tab(n))
    def fit_labels(event):
        width=max(200,event.width-72)
        def visit(widget):
            if isinstance(widget,tk.Label) and int(widget.cget('wraplength') or 0)>0:
                widget.configure(wraplength=width)
            for child in widget.winfo_children():visit(child)
        visit(page)
    page.bind('<Configure>',fit_labels)
    build()
    if data['undo']:undo_button.pack(anchor='w',pady=(8,0))
    return page
