"""Shared metadata editor for non-game libraries; leaves existing forms untouched."""
from window_style import install as polish_dialog

import tkinter as tk
from tkinter import ttk
from database import connection
from modal import app_messagebox as messagebox
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED

FIELDS = {
    "movies": [("release_year", "Release year", "int"), ("director", "Director", "text"),
               ("cast_members", "Cast", "text"), ("rating", "Rating", "text"),
               ("price_paid", "Price paid (£)", "money"), ("notes", "Personal notes", "multiline")],
    "shows": [("release_year", "Release year", "int"), ("network", "Network / service", "text"),
              ("rating", "Rating", "text"), ("price_paid", "Price paid (£)", "money"),
              ("notes", "Personal notes", "multiline")],
    "books": [("author", "Author", "text"), ("series", "Series", "text"),
              ("release_year", "Release year", "int"), ("price_paid", "Price paid (£)", "money"),
              ("publisher", "Publisher", "text"), ("isbn", "ISBN", "text"),
              ("rating", "Rating", "text"), ("notes", "Personal notes", "multiline")],
}

def open_rich_editor(parent, kind, item_id, accent, refresh):
    if kind not in FIELDS:
        return
    row = connection.execute(f"SELECT * FROM {kind} WHERE id=?", (item_id,)).fetchone()
    if row is None:
        return
    columns = [x[1] for x in connection.execute(f"PRAGMA table_info({kind})")]
    record = dict(zip(columns, row))
    window = tk.Toplevel(parent)
    polish_dialog(window)
    window.title(f"Extra Details — {record['name']}")
    window.geometry("610x660")
    window.minsize(480, 450)
    window.configure(bg=BG)
    window.transient(parent.winfo_toplevel())
    window.grab_set()
    header = tk.Frame(window, bg=BG, padx=22, pady=18)
    header.pack(fill="x")
    tk.Label(header, text="Additional Details", bg=BG, fg=TEXT,
             font=("Arial", 19, "bold")).pack(anchor="w")
    tk.Label(header, text=record['name'], bg=BG, fg=MUTED,
             wraplength=540, justify="left").pack(anchor="w", pady=(3, 0))
    body = tk.Frame(window, bg=PANEL)
    body.pack(fill="both", expand=True, padx=20)
    canvas = tk.Canvas(body, bg=PANEL, highlightthickness=0)
    bar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    fields = tk.Frame(canvas, bg=PANEL, padx=18, pady=10)
    ident = canvas.create_window((0, 0), window=fields, anchor="nw")
    fields.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(ident, width=e.width))
    widgets = {}
    for key, label, kind_type in FIELDS[kind]:
        tk.Label(fields, text=label, bg=PANEL, fg=TEXT,
                 font=("Arial", 10, "bold")).pack(anchor="w", pady=(12, 3))
        if kind_type == "multiline":
            widget = tk.Text(fields, height=5, bg=PANEL_ALT, fg=TEXT,
                             insertbackground=TEXT, relief="flat", wrap="word", padx=9, pady=7)
            widget.insert("1.0", record.get(key) or "")
        else:
            widget = tk.Entry(fields, bg=PANEL_ALT, fg=TEXT,
                              insertbackground=TEXT, relief="flat", font=("Arial", 11))
            widget.insert(0, "" if record.get(key) is None else str(record[key]))
        widget.pack(fill="x", ipady=5)
        widgets[key] = widget
    def save():
        values = {}
        try:
            for key, label, kind_type in FIELDS[kind]:
                widget = widgets[key]
                raw = (widget.get("1.0", "end-1c") if kind_type == "multiline"
                       else widget.get()).strip()
                if kind_type == "int":
                    value = int(raw) if raw else None
                    if value is not None and not 0 <= value <= 9999:
                        raise ValueError(f"{label} must be between 0 and 9999")
                elif kind_type == "money":
                    value = float(raw.replace("£", "")) if raw else None
                    if value is not None and value < 0:
                        raise ValueError(f"{label} cannot be negative")
                else:
                    value = raw or None
                values[key] = value
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc), parent=window)
            return
        assignments = ", ".join(f"{field}=?" for field in values)
        try:
            with connection:
                connection.execute(f"UPDATE {kind} SET {assignments} WHERE id=?",
                                   (*values.values(), item_id))
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=window)
            return
        window.destroy()
        refresh()
    actions = tk.Frame(window, bg=BG, padx=20, pady=15)
    actions.pack(fill="x")
    tk.Button(actions, text="Save Details", command=save, bg=accent, fg="white",
              relief="flat", padx=20, pady=9).pack(side="right")
    tk.Button(actions, text="Cancel", command=window.destroy, bg=PANEL_ALT,
              fg=TEXT, relief="flat", padx=20, pady=9).pack(side="right", padx=9)
