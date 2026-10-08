"""Shared, schema-aware filters for all four entertainment libraries."""
import tkinter as tk
from tkinter import ttk
from database import cursor, get_setting, set_setting
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED, BORDER

SORTS = ('Title A–Z', 'Title Z–A', 'Recently Added', 'Oldest Added', 'Year: Newest', 'Year: Oldest')
FIELDS = {
 'games': [('Platform','platform'), ('Release year','release_year')],
 'movies': [('Director','director'), ('Release year','release_year')],
 'shows': [('Genre','genre'), ('Type','type'), ('Release year','release_year')],
 'books': [('Genre','genre'), ('Author','author'), ('Type','type'), ('Release year','release_year')],
}
STATUSES = {'games':('All statuses','Backlog','Completed','Started','Not started','Not completed'),
 'movies':('All statuses','Watched','Unwatched'),
 'shows':('All statuses','Watching','Completed','Not started'),
 'books':('All statuses','Reading','Finished','Not started')}

def columns(kind):
 cursor.execute('PRAGMA table_info('+kind+')')
 return {row[1] for row in cursor.fetchall()}

def where_clause(kind, search, state):
 cols=columns(kind)
 query='name LIKE ?'
 params=['%'+search+'%']
 if kind=='books' and 'author' in cols:
  query='(name LIKE ? OR author LIKE ?)'
  params.append('%'+search+'%')
 for field,var in state['extra'].items():
  val=var.get()
  if field in cols and val!='All':
   query+=' AND '+field+' = ?';params.append(val)
 status=state['status'].get()
 rules={'games':{'Backlog':'backlog = 1','Completed':'completed = 1','Started':'started = 1','Not started':'started = 0','Not completed':'completed = 0'},
 'movies':{'Watched':'watch_count > 0','Unwatched':'watch_count = 0'},
 'shows':{'Watching':'in_progress = 1','Completed':'completed = 1','Not started':'in_progress = 0 AND completed = 0'},
 'books':{'Reading':'in_progress = 1','Finished':'completed = 1','Not started':'in_progress = 0 AND completed = 0'}}
 rule=rules[kind].get(status)
 if rule:query+=' AND ('+rule+')'
 sort=state['sort'].get()
 ordering={'Title A–Z':'name COLLATE NOCASE ASC, id ASC','Title Z–A':'name COLLATE NOCASE DESC, id DESC',
 'Recently Added':'id DESC','Oldest Added':'id ASC',
 'Year: Newest':'release_year DESC, name COLLATE NOCASE','Year: Oldest':'release_year ASC, name COLLATE NOCASE'}
 order=ordering.get(sort,ordering['Title A–Z'])
 if 'release_year' not in cols and sort.startswith('Year:'):order=ordering['Title A–Z']
 return query,params,order

def build_filters(parent, kind, refresh):
    """Compact, consistent library toolbar with a fixed action row."""
    accent = get_setting('accent_color', '#B23A48')
    frame = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    frame.pack(fill='x', padx=20, pady=(5, 12))
    inner = tk.Frame(frame, bg=PANEL)
    inner.pack(fill='x', padx=18, pady=(14, 12))
    state = {'extra': {}}

    heading = tk.Frame(inner, bg=PANEL)
    heading.pack(fill='x', pady=(0, 13))
    tk.Label(heading, text='REFINE YOUR COLLECTION', bg=PANEL, fg=TEXT,
             font=('Arial', 10, 'bold')).pack(side='left')
    tk.Frame(heading, bg=accent, width=3, height=16).pack(side='left', padx=(0, 10), before=heading.winfo_children()[0])
    tk.Label(heading, text=kind.upper(), bg=PANEL, fg=MUTED,
             font=('Arial', 9)).pack(side='right')

    def combo(host, label, choices, setting, column, width=19):
        cell = tk.Frame(host, bg=PANEL)
        cell.grid(row=0, column=column, sticky='ew', padx=(0, 12))
        tk.Label(cell, text=label.upper(), bg=PANEL, fg=MUTED,
                 font=('Arial', 8, 'bold')).pack(anchor='w', pady=(0, 6))
        saved = get_setting(setting, choices[0])
        var = tk.StringVar(value=saved if saved in choices else choices[0])
        box = ttk.Combobox(cell, textvariable=var, values=choices, width=width,
                           state='readonly', style='Filter.TCombobox')
        box.pack(fill='x', ipady=2)
        box.bind('<<ComboboxSelected>>', lambda _event: (set_setting(setting, var.get()), refresh()))
        return var

    top = tk.Frame(inner, bg=PANEL)
    top.pack(fill='x')
    top.grid_columnconfigure(0, weight=1, uniform='filters')
    top.grid_columnconfigure(1, weight=1, uniform='filters')
    top.grid_columnconfigure(2, weight=0)
    state['status'] = combo(top, 'Status', STATUSES[kind], kind+'_filter_status', 0)
    state['sort'] = combo(top, 'Sort by', SORTS, kind+'_filter_sort', 1)

    advanced = tk.Frame(inner, bg=PANEL)
    available = columns(kind)
    advanced.grid_columnconfigure(0, weight=1, uniform='advanced')
    advanced.grid_columnconfigure(1, weight=1, uniform='advanced')
    advanced.grid_columnconfigure(2, weight=1, uniform='advanced')
    # Use rows of three; no horizontal overflow as additional filters are added.
    index = 0
    for label, field in FIELDS[kind]:
        if field not in available:
            continue
        cursor.execute('SELECT DISTINCT '+field+' FROM '+kind+' WHERE '+field+
                       " IS NOT NULL AND TRIM(CAST("+field+" AS TEXT)) != '' ORDER BY "+field+' COLLATE NOCASE')
        choices = ['All'] + [str(row[0]) for row in cursor.fetchall()]
        if len(choices) <= 1:
            continue
        cell = tk.Frame(advanced, bg=PANEL)
        cell.grid(row=index//3, column=index%3, sticky='ew', padx=(0, 12), pady=(0, 10))
        tk.Label(cell, text=label.upper(), bg=PANEL, fg=MUTED,
                 font=('Arial', 8, 'bold')).pack(anchor='w', pady=(0, 6))
        setting = kind+'_filter_'+field
        saved = get_setting(setting, 'All')
        var = tk.StringVar(value=saved if saved in choices else 'All')
        select = ttk.Combobox(cell, textvariable=var, values=choices, state='readonly',
                              style='Filter.TCombobox', width=14)
        select.pack(fill='x', ipady=2)
        select.bind('<<ComboboxSelected>>', lambda _event, v=var, key=setting:
                    (set_setting(key, v.get()), refresh()))
        state['extra'][field] = var
        index += 1

    actions = tk.Frame(top, bg=PANEL)
    actions.grid(row=0, column=2, sticky='se', pady=(0, 1))
    def toggle():
        if advanced.winfo_manager():
            advanced.pack_forget()
            toggle_button.configure(text='Advanced  +')
        else:
            advanced.pack(fill='x', pady=(15, 0))
            toggle_button.configure(text='Advanced  −')
    toggle_button = tk.Button(actions, text='Advanced  +', command=toggle,
                              bg=PANEL_ALT, fg=TEXT, activebackground=BORDER,
                              activeforeground=TEXT, relief='flat', bd=0,
                              padx=13, pady=8, cursor='hand2')
    toggle_button.pack(side='left', padx=(0, 8))

    def reset():
        state['status'].set(STATUSES[kind][0])
        state['sort'].set(SORTS[0])
        set_setting(kind+'_filter_status', state['status'].get())
        set_setting(kind+'_filter_sort', state['sort'].get())
        for field, var in state['extra'].items():
            var.set('All')
            set_setting(kind+'_filter_'+field, 'All')
        refresh()
    tk.Button(actions, text='Clear filters', command=reset, bg=PANEL_ALT, fg=TEXT,
              activebackground=BORDER, activeforeground=TEXT, relief='flat',
              bd=0, padx=13, pady=8, cursor='hand2').pack(side='left')

    footer = tk.Frame(inner, bg=PANEL)
    footer.pack(fill='x', pady=(14, 0))
    tk.Frame(footer, bg=BORDER, height=1).pack(fill='x', pady=(0, 10))
    count = tk.Label(footer, text='', bg=PANEL, fg=MUTED,
                     font=('Arial', 9))
    count.pack(anchor='w')
    state['count'] = count
    return state
