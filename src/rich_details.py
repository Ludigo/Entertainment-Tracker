"""Unified, scrollable Edit dialog for Movies, Shows and Books."""
from window_style import install as polish_dialog
import math
import tkinter as tk
from tkinter import ttk
from database import connection
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED, BORDER
from utils import format_time, parse_time

# The former Extra Details dialog is the base; core fields from the original
# category editors now live here too. Artwork is deliberately edited separately.
FIELDS = {
    'movies': [('name', 'Movie name', 'required'), ('runtime', 'Runtime (H:MM:SS)', 'duration'),
               ('watch_count', 'Watch count', 'count'), ('type', 'Type', 'text'), ('genre', 'Genre', 'text'),
               ('completed', 'Completed', 'bool'), ('in_progress', 'In progress', 'bool'), ('owned', 'Owned', 'bool'),
               ('release_year', 'Release year', 'int'), ('director', 'Director', 'text'),
               ('cast_members', 'Cast', 'multiline'), ('rating', 'Rating', 'text'),
               ('price_paid', 'Price paid (£)', 'money'), ('description', 'Description', 'multiline'),
               ('notes', 'Personal notes', 'multiline')],
    'shows': [('name', 'Show name', 'required'), ('season', 'Season', 'count'),
              ('runtime', 'Season runtime (H:MM:SS)', 'duration'), ('episode_count', 'Episode count', 'count'),
              ('episode_reached', 'Episode reached', 'count'), ('watch_count', 'Watch count', 'count'),
              ('completed', 'Completed', 'bool'), ('in_progress', 'In progress', 'bool'), ('owned', 'Owned', 'bool'),
              ('type', 'Type', 'text'), ('genre', 'Genre', 'text'), ('release_year', 'Release year', 'int'),
              ('network', 'Network / service', 'text'), ('rating', 'Rating', 'text'),
              ('price_paid', 'Price paid (£)', 'money'), ('description', 'Description', 'multiline'),
              ('notes', 'Personal notes', 'multiline')],
    'books': [('name', 'Book name', 'required'), ('page_count', 'Page count', 'count'),
              ('reading_time', 'Reading time (H:MM:SS)', 'duration'), ('read_count', 'Read count', 'count'),
              ('completed', 'Completed', 'bool'), ('in_progress', 'In progress', 'bool'), ('owned', 'Owned', 'bool'),
              ('type', 'Type', 'text'), ('genre', 'Genre', 'text'), ('author', 'Author', 'text'),
              ('series', 'Series', 'text'), ('release_year', 'Release year', 'int'),
              ('price_paid', 'Price paid (£)', 'money'), ('publisher', 'Publisher', 'text'),
              ('isbn', 'ISBN', 'text'), ('rating', 'Rating', 'text'),
              ('description', 'Description', 'multiline'), ('notes', 'Personal notes', 'multiline')],
}


class InvalidField(ValueError):
    def __init__(self, key, message):
        self.key = key
        super().__init__(message)


def parse_values(kind, raw_values):
    values = {}
    for key, label, field_type in FIELDS[kind]:
        raw = str(raw_values[key]).strip()
        try:
            if field_type == 'bool':
                if raw not in ('0', '1'):
                    raise ValueError(f'{label} must be selected or unselected.')
                value = int(raw)
            elif field_type == 'required':
                if not raw:
                    raise ValueError(f'Please enter a {label.lower()}.')
                value = raw
            elif field_type == 'duration':
                try:
                    value = parse_time(raw)
                except (ValueError, OverflowError):
                    raise ValueError(f'{label} must use H:MM:SS (minutes and seconds 00–59).')
                if not math.isfinite(value):
                    raise ValueError(f'{label} is too large.')
            elif field_type in ('int', 'count'):
                try:
                    value = int(raw) if raw else None
                except ValueError:
                    raise ValueError(f'{label} must be a whole number.')
                maximum = 9999 if field_type == 'int' else 9223372036854775807
                if (value is None and field_type == 'count') or (value is not None and not 0 <= value <= maximum):
                    raise ValueError(f'{label} must be between 0 and {maximum}.')
            elif field_type == 'money':
                try:
                    value = float(raw.replace('£', '').replace(',', '')) if raw else None
                except ValueError:
                    raise ValueError(f'{label} must be a valid amount.')
                if value is not None and (not math.isfinite(value) or value < 0):
                    raise ValueError(f'{label} must be a finite, non-negative amount.')
            else:
                value = raw or None
            values[key] = value
        except (ValueError, OverflowError) as exc:
            raise InvalidField(key, str(exc)) from exc
    if kind == 'shows' and values['episode_reached'] > values['episode_count']:
        raise InvalidField('episode_reached', 'Episode reached cannot exceed episode count.')
    return values


def save_values(kind, item_id, raw_values):
    values = parse_values(kind, raw_values)
    assignments = ', '.join(f'{field}=?' for field in values)
    with connection:
        updated = connection.execute(f'UPDATE {kind} SET {assignments} WHERE id=?', (*values.values(), item_id))
        if updated.rowcount != 1:
            raise ValueError('This item is no longer in the collection.')
    return values


def open_rich_editor(parent, kind, item_id, accent, refresh):
    if kind not in FIELDS:
        return
    row = connection.execute(f'SELECT * FROM {kind} WHERE id=?', (item_id,)).fetchone()
    if row is None:
        return
    columns = [x[1] for x in connection.execute(f'PRAGMA table_info({kind})')]
    record = dict(zip(columns, row))
    window = tk.Toplevel(parent)
    polish_dialog(window)
    window.title(f"Edit — {record['name']}")
    window.geometry('610x660')
    window.minsize(480, 450)
    window.configure(bg=BG)
    window.transient(parent.winfo_toplevel())
    previous_grab = window.grab_current()
    window.grab_set()
    header = tk.Frame(window, bg=BG, padx=22, pady=18)
    header.pack(fill='x')
    tk.Label(header, text='Edit ' + kind[:-1].title(), bg=BG, fg=TEXT,
             font=('Arial', 19, 'bold')).pack(anchor='w')
    tk.Label(header, text=record['name'], bg=BG, fg=MUTED,
             wraplength=540, justify='left').pack(anchor='w', pady=(3, 0))
    # Footer stays visible while the form itself scrolls.
    actions = tk.Frame(window, bg=BG, padx=20, pady=12)
    actions.pack(side='bottom', fill='x')
    status = tk.Label(actions, text='', bg=BG, fg='#d96a76', wraplength=540, justify='left')
    status.pack(anchor='w', fill='x', pady=(0, 8))
    buttons = tk.Frame(actions, bg=BG)
    buttons.pack(fill='x')
    body = tk.Frame(window, bg=PANEL)
    body.pack(fill='both', expand=True, padx=20)
    canvas = tk.Canvas(body, bg=PANEL, highlightthickness=0)
    bar = ttk.Scrollbar(body, orient='vertical', command=canvas.yview)
    canvas.configure(yscrollcommand=bar.set)
    bar.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    fields = tk.Frame(canvas, bg=PANEL, padx=18, pady=10)
    ident = canvas.create_window((0, 0), window=fields, anchor='nw')
    fields.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda e: canvas.itemconfigure(ident, width=e.width))
    widgets, variables = {}, {}
    for key, label, field_type in FIELDS[kind]:
        if field_type == 'bool':
            variable = tk.IntVar(master=window, value=1 if record.get(key) else 0)
            widget = tk.Checkbutton(fields, text=label, variable=variable, bg=PANEL, fg=TEXT,
                                    selectcolor=PANEL_ALT, activebackground=PANEL, activeforeground=TEXT,
                                    font=('Arial', 10))
            widget.pack(anchor='w', pady=(8, 0))
            variables[key] = variable
        else:
            tk.Label(fields, text=label, bg=PANEL, fg=TEXT,
                     font=('Arial', 10, 'bold')).pack(anchor='w', pady=(12, 3))
            if field_type == 'multiline':
                widget = tk.Text(fields, height=4, bg=PANEL_ALT, fg=TEXT,
                                 insertbackground=TEXT, relief='flat', wrap='word', padx=9, pady=7)
                widget.insert('1.0', record.get(key) or '')
            else:
                widget = tk.Entry(fields, bg=PANEL_ALT, fg=TEXT, insertbackground=TEXT,
                                  relief='flat', font=('Arial', 11), highlightbackground=BORDER, highlightthickness=1)
                value = record.get(key)
                if field_type == 'duration':
                    value = format_time(value or 0)
                elif field_type == 'count':
                    value = value or 0
                widget.insert(0, '' if value is None else str(value))
            widget.pack(fill='x', ipady=5)
        widgets[key] = widget

    def raw_values():
        return {key: (variables[key].get() if field_type == 'bool' else
                      widgets[key].get('1.0', 'end-1c') if field_type == 'multiline' else widgets[key].get())
                for key, label, field_type in FIELDS[kind]}
    initial = raw_values()
    closing = {'prompt': None, 'done': False}
    wheel_tag = f'EditWheel{id(window)}'
    def wheel(event):
        number = getattr(event, 'num', None)
        delta = getattr(event, 'delta', 0)
        if number not in (4, 5) and not delta:
            return
        canvas.yview_scroll(-3 if number == 4 or delta > 0 else 3, 'units')
        return 'break'
    for event in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
        window.bind_class(wheel_tag, event, wheel)
    def wheel_tags(widget):
        tags = widget.bindtags()
        widget.bindtags((tags[0], wheel_tag) + tags[1:])
        for child in widget.winfo_children():
            wheel_tags(child)
    wheel_tags(fields)
    canvas.bind('<MouseWheel>', wheel)
    canvas.bind('<Button-4>', wheel)
    canvas.bind('<Button-5>', wheel)

    def finish():
        if closing['done']:
            return
        closing['done'] = True
        for event in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            window.unbind_class(wheel_tag, event)
        window.destroy()
        if previous_grab is not None:
            try:
                if previous_grab.winfo_exists():
                    previous_grab.grab_set()
            except tk.TclError:
                pass

    def close(event=None):
        if closing['done']:
            return 'break'
        if raw_values() == initial:
            finish()
            return 'break'
        if closing['prompt'] is not None:
            closing['prompt'].lift()
            return 'break'
        prompt = tk.Toplevel(window)
        closing['prompt'] = prompt
        polish_dialog(prompt)
        prompt.title('Unsaved Changes')
        prompt.geometry('430x210')
        prompt.configure(bg=PANEL)
        prompt.transient(window)
        tk.Label(prompt, text='Discard unsaved changes?', bg=PANEL, fg=TEXT,
                 font=('Arial', 14, 'bold')).pack(anchor='w', padx=20, pady=(20, 10))
        tk.Label(prompt, text='Keep editing or discard your changes.', bg=PANEL, fg=MUTED,
                 wraplength=390).pack(anchor='w', padx=20)
        controls = tk.Frame(prompt, bg=PANEL)
        controls.pack(side='bottom', fill='x', padx=20, pady=20)
        def keep(event=None):
            prompt.destroy()
            closing['prompt'] = None
            window.grab_set()
            return 'break'
        def discard():
            prompt.destroy()
            closing['prompt'] = None
            finish()
        tk.Button(controls, text='Keep Editing', command=keep, bg=accent, fg='white',
                  relief='flat', padx=12, pady=8).pack(side='right')
        tk.Button(controls, text='Discard Changes', command=discard, bg=PANEL_ALT, fg=TEXT,
                  relief='flat', padx=12, pady=8).pack(side='right', padx=(0, 8))
        prompt.protocol('WM_DELETE_WINDOW', keep)
        prompt.bind('<Escape>', keep)
        prompt.grab_set()
        return 'break'

    def save():
        try:
            save_values(kind, item_id, raw_values())
        except InvalidField as exc:
            status.configure(text=str(exc))
            widget = widgets[exc.key]
            widget.configure(highlightbackground='#d96a76', highlightthickness=2)
            widget.focus_set()
            canvas.update_idletasks()
            position = max(0, widget.winfo_y())
            height = max(1, fields.winfo_reqheight())
            canvas.yview_moveto(position / height)
            return
        except Exception as exc:
            status.configure(text=f'Could not save: {exc}')
            return
        finish()
        refresh()

    tk.Button(buttons, text='Save Changes', command=save, bg=accent, fg='white',
              relief='flat', padx=20, pady=9).pack(side='right')
    tk.Button(buttons, text='Cancel', command=close, bg=PANEL_ALT, fg=TEXT,
              relief='flat', padx=20, pady=9).pack(side='right', padx=9)
    window.protocol('WM_DELETE_WINDOW', close)
    window.bind('<Escape>', close)
    widgets['name'].focus_set()
    return window
