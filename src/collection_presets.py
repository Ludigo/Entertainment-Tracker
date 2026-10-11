"""Inline saved filter presets including each library's search text."""
import tkinter as tk
from tkinter import ttk
from database import connection,set_setting
from theme import PANEL,PANEL_ALT,TEXT,MUTED
from collection_manager_data import presets,preset_save

def snapshot(state):
    return {'status':state['status'].get(),'sort':state['sort'].get(),
            'extra':{k:v.get() for k,v in state['extra'].items()},
            'search':state['search'].get() if state.get('search') is not None else ''}

def apply(kind,state,value):
    for key in ('status','sort'):
        if key in value:state[key].set(value[key]);set_setting(kind+'_filter_'+key,value[key])
    for key,val in value.get('extra',{}).items():
        if key in state['extra']:
            state['extra'][key].set(val);set_setting(kind+'_filter_ownership' if key=='_ownership' else kind+'_filter_'+key,val)
    if state.get('search') is not None:
        state['search'].delete(0,'end');state['search'].insert(0,value.get('search',''))

def install(parent,kind,state,refresh):
    row=tk.Frame(parent,bg=PANEL);row.pack(fill='x',pady=(8,0))
    tk.Label(row,text='Saved views',bg=PANEL,fg=MUTED).pack(side='left',padx=(0,8))
    choice=tk.StringVar();box=ttk.Combobox(row,textvariable=choice,state='readonly',width=20);box.pack(side='left')
    name=tk.StringVar();tk.Entry(row,textvariable=name,bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT,width=20).pack(side='left',padx=7)
    status=tk.StringVar();tk.Label(parent,textvariable=status,bg=PANEL,fg=MUTED).pack(anchor='w')
    def reload():box.configure(values=[label for label,value in presets(kind)])
    def save():
        try:preset_save(kind,name.get(),snapshot(state));reload();choice.set(name.get().strip());status.set('View saved, including search and active filters.')
        except Exception as exc:status.set(str(exc))
    def load():
        value=next((data for label,data in presets(kind) if label==choice.get()),None)
        if value is None:status.set('Choose a saved view.');return
        apply(kind,state,value);refresh();status.set('Saved view applied.')
    def delete():
        with connection:connection.execute('DELETE FROM filter_presets WHERE kind=? AND name=?',(kind,choice.get()))
        reload();choice.set('');status.set('Preset removed; collection retained.')
    for title,fn in [('Save / replace',save),('Load',load),('Delete preset',delete)]:tk.Button(row,text=title,command=fn,bg=PANEL_ALT,fg=TEXT,relief='flat',pady=5).pack(side='left',padx=3)
    reload()
