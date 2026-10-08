"""Non-invasive visual polish for secondary Tk windows.

No geometry managers, dimensions, callbacks or widget ordering are changed.
"""
import tkinter as tk
from tkinter import ttk
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED, BORDER, DEFAULT_ACCENT, configure_ttk
from database import get_setting


def polish_window(window):
    """Style widgets after a dialog has built its content; safe for existing layouts."""
    accent = get_setting('accent_color', DEFAULT_ACCENT)
    try:
        if not window.winfo_exists():
            return
        configure_ttk(window, accent)
        window.configure(bg=BG)
        for child in window.winfo_children():
            _style(child, accent)
    except tk.TclError:
        pass


def _style(widget, accent):
    try:
        if isinstance(widget, (tk.Button, tk.Menubutton)):
            widget.configure(bg=PANEL_ALT, fg=TEXT, activebackground=accent,
                             activeforeground='white', relief='flat', bd=0,
                             highlightthickness=0, cursor='hand2')
            if not getattr(widget, '_et_dialog_hover', False):
                widget._et_dialog_hover = True
                widget.bind('<Enter>', lambda e, w=widget: w.configure(bg=accent) if str(w.cget('state')) != 'disabled' else None, add='+')
                widget.bind('<Leave>', lambda e, w=widget: w.configure(bg=PANEL_ALT) if str(w.cget('state')) != 'disabled' else None, add='+')
        elif isinstance(widget, (tk.Entry, tk.Spinbox)):
            widget.configure(bg=PANEL_ALT, fg=TEXT, insertbackground=TEXT,
                             highlightthickness=1, highlightbackground=BORDER,
                             highlightcolor=accent, relief='flat')
        elif isinstance(widget, tk.Text):
            widget.configure(bg=PANEL_ALT, fg=TEXT, insertbackground=TEXT,
                             highlightthickness=1, highlightbackground=BORDER,
                             highlightcolor=accent, relief='flat')
        elif isinstance(widget, tk.Checkbutton):
            widget.configure(fg=TEXT, selectcolor=PANEL_ALT, activeforeground=TEXT,
                             highlightthickness=0)
        elif isinstance(widget, ttk.Combobox):
            widget.configure(style='Filter.TCombobox')
        elif isinstance(widget, tk.LabelFrame):
            widget.configure(fg=TEXT, highlightbackground=BORDER)
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        _style(child, accent)


def install(window):
    """Apply after construction and once more for dialogs that populate lazily."""
    window.after_idle(lambda: polish_window(window))
    window.after(120, lambda: polish_window(window))
