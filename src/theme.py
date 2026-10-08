import tkinter as tk
from tkinter import ttk

BG = "#17191d"
PANEL = "#202329"
PANEL_ALT = "#292d34"
TEXT = "#f2f2f2"
MUTED = "#a9adb5"
BORDER = "#363b44"
DEFAULT_ACCENT = "#B23A48"


def configure_ttk(root, accent):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                    foreground=TEXT, rowheight=28, borderwidth=0,
                    relief="flat")
    style.configure("Treeview.Heading", background=PANEL_ALT, foreground=TEXT,
                    relief="flat", font=("Arial", 10, "bold"))
    style.map("Treeview", background=[("selected", accent)],
              foreground=[("selected", "white")])
    style.map("Treeview.Heading", background=[("active", BORDER)])

    # Fully themed scrollbar: avoids the bright native Windows borders/arrows.
    style.configure("Dark.Vertical.TScrollbar",
                    background=PANEL_ALT, troughcolor=BG, bordercolor=BG,
                    lightcolor=PANEL_ALT, darkcolor=PANEL_ALT,
                    arrowcolor=MUTED, relief="flat", borderwidth=0)
    style.map("Dark.Vertical.TScrollbar",
              background=[("active", accent), ("pressed", accent)],
              arrowcolor=[("active", TEXT), ("pressed", TEXT)])

    # Remove the thin focus/border ring some ttk themes draw around Treeviews.
    try:
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    except tk.TclError:
        pass


    # Flat combobox: remove clam's native white outline.
    try:
        style.layout("Filter.TCombobox", [
            ("Combobox.field", {"sticky": "nswe", "children": [
                ("Combobox.downarrow", {"side": "right", "sticky": "ns"}),
                ("Combobox.padding", {"sticky": "nswe", "children": [
                    ("Combobox.textarea", {"sticky": "nswe"})
                ]})
            ]})
        ])
    except tk.TclError:
        pass
    style.configure("Filter.TCombobox", fieldbackground=PANEL_ALT,
                    background=PANEL_ALT, foreground=TEXT,
                    arrowcolor=TEXT, borderwidth=0, padding=5)
    style.map("Filter.TCombobox",
              fieldbackground=[("readonly", PANEL_ALT)],
              foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", PANEL_ALT)],
              selectforeground=[("readonly", TEXT)])


def apply_theme(widget, accent):
    """Apply the app palette to existing Tk widgets recursively."""
    configure_ttk(widget.winfo_toplevel(), accent)
    for child in widget.winfo_children():
        try:
            if isinstance(child, tk.Toplevel):
                child.configure(bg=BG)
            elif isinstance(child, (tk.Frame, tk.LabelFrame)):
                child.configure(bg=BG)
            elif isinstance(child, tk.Label):
                child.configure(bg=BG, fg=TEXT)
            elif isinstance(child, tk.Button):
                child.configure(bg=PANEL_ALT, fg=TEXT, activebackground=accent,
                                activeforeground="white", relief="flat",
                                bd=0, cursor="hand2")
                if not getattr(child, "_et_hover_installed", False):
                    child._et_hover_installed = True
                    def on_enter(event, button=child):
                        if str(button.cget("state")) != "disabled":
                            from database import get_setting
                            colour = get_setting("accent_color", DEFAULT_ACCENT)
                            button.configure(bg=colour, fg="white")
                    def on_leave(event, button=child):
                        if str(button.cget("state")) != "disabled":
                            button.configure(bg=PANEL_ALT, fg=TEXT)
                    child.bind("<Enter>", on_enter, add="+")
                    child.bind("<Leave>", on_leave, add="+")
            elif isinstance(child, tk.Entry):
                child.configure(bg=PANEL_ALT, fg=TEXT, insertbackground=TEXT,
                                relief="flat", bd=6)
            elif isinstance(child, tk.Checkbutton):
                child.configure(bg=BG, fg=TEXT, selectcolor=PANEL_ALT,
                                activebackground=BG, activeforeground=TEXT)
            elif isinstance(child, tk.Scrollbar):
                child.configure(bg=PANEL_ALT, activebackground=accent,
                                troughcolor=BG, relief="flat", bd=0)
        except tk.TclError:
            pass
        apply_theme(child, accent)
