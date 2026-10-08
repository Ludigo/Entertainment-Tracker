"""Safe, field-scoped bulk editing across all four collections."""
from window_style import install as polish_dialog

import tkinter as tk
from tkinter import ttk, messagebox
from database import connection
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED, DEFAULT_ACCENT

FIELDS = {
    'games': [('platform','Platform','text'),('completed','Completed','bool'),('backlog','Backlog','bool'),('started','Started','bool'),('in_progress','In Progress','bool')],
    'movies': [('completed','Completed','bool'),('in_progress','In Progress','bool'),('owned','Owned','bool'),('type','Type','text'),('genre','Genre','text')],
    'shows': [('completed','Completed','bool'),('in_progress','In Progress','bool'),('owned','Owned','bool'),('type','Type','text'),('genre','Genre','text')],
    'books': [('completed','Completed','bool'),('in_progress','In Progress','bool'),('owned','Owned','bool'),('type','Type','text'),('genre','Genre','text')],
}


def apply_changes(kind, ids, changes):
    """Update only explicitly chosen fields, atomically."""
    if kind not in FIELDS: raise ValueError('Unknown collection')
    allowed = {name for name, _, _ in FIELDS[kind]}
    if not ids or not changes or any(c not in allowed for c in changes):
        raise ValueError('Select entries and permitted fields')
    ids = sorted({int(i) for i in ids})
    assignments = ', '.join(f'{field} = ?' for field in changes)
    placeholders = ','.join('?' for _ in ids)
    with connection:
        result = connection.execute(
            f'UPDATE {kind} SET {assignments} WHERE id IN ({placeholders})',
            list(changes.values()) + ids)
    return result.rowcount


def open_bulk_edit(parent, kind, on_done=None):
    if kind not in FIELDS: raise ValueError(kind)
    dialog = tk.Toplevel(parent.winfo_toplevel())
    polish_dialog(dialog)
    dialog.title(f'Bulk Edit — {kind.title()}')
    screen_h = dialog.winfo_screenheight()
    screen_w = dialog.winfo_screenwidth()
    dialog.geometry(f'{min(760, max(580, screen_w - 80))}x{min(690, max(480, screen_h - 130))}')
    dialog.minsize(580, 480)
    dialog.configure(bg=BG)
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()
    # A real two-row grid reserves the footer independently of the content.
    # The entry list shrinks when the display is short; buttons never get clipped.
    dialog.grid_rowconfigure(0, weight=1)
    dialog.grid_rowconfigure(1, weight=0)
    dialog.grid_columnconfigure(0, weight=1)
    body = tk.Frame(dialog, bg=BG)
    body.grid(row=0, column=0, sticky='nsew')
    footer = tk.Frame(dialog, bg=BG)
    footer.grid(row=1, column=0, sticky='ew', padx=22, pady=(6, 10))
    tk.Label(body, text=f'Bulk Edit {kind.title()}', bg=BG, fg=TEXT,
             font=('Arial', 20, 'bold')).pack(anchor='w', padx=22, pady=(18, 4))
    tk.Label(body, text='Choose entries, then tick only the fields you want to change. Other details stay untouched.',
             bg=BG, fg=MUTED, wraplength=710, justify='left').pack(anchor='w', padx=22, pady=(0, 10))
    search = tk.StringVar()
    search_box = tk.Entry(body, textvariable=search, bg=PANEL_ALT, fg=TEXT,
                          insertbackground=TEXT, relief='flat')
    search_box.pack(fill='x', padx=22, ipady=7)
    tk.Label(body, text='Search by title • Ctrl/Shift-click to select multiple • Select Visible selects search results',
             bg=BG, fg=MUTED, font=('Arial', 9)).pack(anchor='w', padx=22, pady=(5, 5))
    area = tk.Frame(body, bg=BG)
    area.pack(fill='both', expand=True, padx=22)
    tree = ttk.Treeview(area, columns=('title','extra'), show='headings', selectmode='extended', height=10)
    tree.heading('title', text='Title')
    tree.heading('extra', text='Platform / Season' if kind in ('games','shows') else 'Collection')
    tree.column('title', width=420)
    tree.column('extra', width=150)
    bar = ttk.Scrollbar(area, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side='right', fill='y')
    tree.pack(fill='both', expand=True)
    extra = 'platform' if kind == 'games' else 'season' if kind == 'shows' else "''"
    rows = connection.execute(f'SELECT id, name, {extra} FROM {kind} ORDER BY name COLLATE NOCASE, id').fetchall()
    # Preserve selected IDs across search updates.
    selected = set()
    visible = set()
    refreshing = [False]
    def refresh(*_):
        term = search.get().casefold().strip()
        refreshing[0] = True
        for item in tree.get_children(): tree.delete(item)
        visible.clear()
        for id_, name, detail in rows:
            if term in str(name).casefold() or term in str(detail or '').casefold():
                tree.insert('', 'end', iid=str(id_), values=(name, detail or ''))
                visible.add(id_)
        for id_ in selected & visible: tree.selection_add(str(id_))
        count.configure(text=f'{len(selected)} selected · {len(visible)} visible')
        refreshing[0] = False
    def selection_changed(_=None):
        if refreshing[0]: return
        selected.difference_update(visible)
        selected.update(int(item) for item in tree.selection())
        count.configure(text=f'{len(selected)} selected · {len(visible)} visible')
    tree.bind('<<TreeviewSelect>>', selection_changed)
    search.trace_add('write', refresh)
    controls = tk.Frame(body, bg=BG)
    controls.pack(fill='x', padx=22, pady=8, before=area)
    count = tk.Label(controls, bg=BG, fg=TEXT)
    count.pack(side='right')
    def select_visible():
        selected.update(visible)
        for item in tree.get_children(): tree.selection_add(item)
        count.configure(text=f'{len(selected)} selected · {len(visible)} visible')
    def clear_selection():
        selected.clear()
        tree.selection_remove(tree.selection())
        count.configure(text='0 selected')
    tk.Button(controls, text='Select Visible', command=select_visible, bg=PANEL_ALT, fg=TEXT,
              relief='flat', padx=10).pack(side='left')
    tk.Button(controls, text='Clear Selection', command=clear_selection, bg=PANEL_ALT, fg=TEXT,
              relief='flat', padx=10).pack(side='left', padx=8)
    tk.Label(body, text='FIELDS TO UPDATE', bg=BG, fg=TEXT, font=('Arial', 11, 'bold')).pack(anchor='w', padx=22, pady=(6, 4), before=area)
    form = tk.Frame(body, bg=PANEL, padx=15, pady=12)
    form.pack(fill='x', padx=22, before=area)
    choices = {}
    for index, (field, label, kind_field) in enumerate(FIELDS[kind]):
        line = tk.Frame(form, bg=PANEL)
        line.grid(row=index, column=0, sticky='ew', pady=3)
        enabled = tk.BooleanVar(value=False)
        tk.Checkbutton(line, text=label, variable=enabled, bg=PANEL, fg=TEXT,
                       selectcolor=PANEL_ALT, activebackground=PANEL, activeforeground=TEXT,
                       width=17, anchor='w').pack(side='left')
        value = tk.StringVar(value='Yes' if kind_field == 'bool' else '')
        if kind_field == 'bool':
            widget = ttk.Combobox(line, textvariable=value, values=('Yes','No'), state='readonly', width=16)
        else:
            widget = tk.Entry(line, textvariable=value, bg=PANEL_ALT, fg=TEXT,
                              insertbackground=TEXT, relief='flat', width=26)
        widget.pack(side='left', padx=8)
        choices[field] = (enabled, value, kind_field)
    def save():
        selection = sorted(selected)
        changes = {}
        for field, (enabled, value, kind_field) in choices.items():
            if enabled.get():
                changes[field] = (1 if value.get() == 'Yes' else 0) if kind_field == 'bool' else value.get().strip()
        if not selection or not changes:
            messagebox.showwarning('Bulk Edit', 'Select entries and at least one field to change.', parent=dialog)
            return
        summary = '\n'.join(f'{field}: {value}' for field, value in changes.items())
        if not messagebox.askyesno('Confirm Bulk Edit',
                                  f'Update {len(selection)} {kind} entries?\n\n{summary}\n\nOnly these fields will change.',
                                  parent=dialog): return
        try: updated = apply_changes(kind, selection, changes)
        except Exception as exc:
            messagebox.showerror('Bulk Edit Failed', str(exc), parent=dialog)
            return
        dialog.destroy()
        messagebox.showinfo('Bulk Edit Complete', f'Updated {updated} entries.', parent=parent.winfo_toplevel())
        if on_done: on_done()
    tk.Button(footer, text='Apply Changes', command=save, bg=DEFAULT_ACCENT, fg='white',
              relief='flat', padx=18, pady=9).pack(side='right')
    tk.Button(footer, text='Cancel', command=dialog.destroy, bg=PANEL_ALT, fg=TEXT,
              relief='flat', padx=18, pady=9).pack(side='right', padx=8)
    refresh()
    dialog.bind('<Escape>', lambda event: dialog.destroy())
    search_box.focus_set()
