"""Preview-first import for Collection Master workbooks. Standard library only."""
from window_style import install as polish_dialog

import re
from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from datetime import timedelta
from database import connection, cursor
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED

N = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
     "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
     "p": "http://schemas.openxmlformats.org/package/2006/relationships"}

def excel_rows(path):
    with ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.findall(".//m:t", N))
                      for si in root.findall("m:si", N)]
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        relroot = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in relroot}
        for sheet in wb.findall("m:sheets/m:sheet", N):
            name = sheet.attrib["name"]
            if name not in ("Games", "Books", "Shows", "Movies"):
                continue
            target = rels[sheet.attrib[f'{{{N["r"]}}}id']]
            target = target.lstrip("/") if target.startswith("/") else "xl/" + target
            root = ET.fromstring(z.read(target))
            result = []
            for row in root.findall(".//m:sheetData/m:row", N):
                values = {}
                for c in row.findall("m:c", N):
                    col = re.match(r"[A-Z]+", c.attrib["r"]).group()
                    idx = 0
                    for char in col: idx = idx * 26 + ord(char) - 64
                    v = c.find("m:v", N)
                    if c.attrib.get("t") == "inlineStr":
                        val = "".join(t.text or "" for t in c.findall(".//m:t", N))
                    elif v is None or v.text is None:
                        continue
                    elif c.attrib.get("t") == "s":
                        val = shared[int(v.text)]
                    elif c.attrib.get("t") in ("str", "e"):
                        val = v.text
                    else:
                        try: val = float(v.text)
                        except ValueError: val = v.text
                    values[idx] = val
                if values: result.append(values)
            yield name, result

def yes(v):
    return int(str(v or "").strip().lower() in ("yes", "true", "1"))

def number(v, default=0):
    try: return float(v) if v not in ("", None) else default
    except (TypeError, ValueError): return default

def integer(v, default=0):
    n = number(v, default)
    return int(n) if n is not None else None

def hours(v):
    # Excel numeric time is stored as fractions of a day, not hours.
    if isinstance(v, (float, int)): return max(0, float(v) * 24)
    if not v: return 0.0
    text = str(v).strip()
    days = 0
    match = re.match(r"^(\d+)\s+days?,?\s*", text, re.I)
    if match:
        days = int(match.group(1))
        text = text[match.end():]
    try:
        parts = [int(p) for p in text.split(":")]
        if len(parts) == 3:
            return days * 24 + parts[0] + parts[1] / 60 + parts[2] / 3600
        if len(parts) == 2:
            return days * 24 + parts[0] / 60 + parts[1] / 3600
        return days * 24 + float(text)
    except (ValueError, TypeError):
        return days * 24

def clean(v):
    return str(v or "").strip()

def extract(path):
    result = {k: [] for k in ("games", "books", "shows", "movies")}
    for sheet, rows in excel_rows(path):
        if sheet == "Games":
            # Two parallel game tables; the modpack/time scratchpad at X:Y
            # is not a normal game collection and is intentionally excluded.
            for r in rows:
                for start in (2, 12):
                    if clean(r.get(start)).lower() != "platform" or clean(r.get(start+1)).lower() != "title":
                        continue
                    # Header positions are B:I and K:V, data begins next row.
                    break
            for r in rows:
                for start in (2, 12):
                    platform, title = clean(r.get(start)), clean(r.get(start+1))
                    if not title or not platform or platform.lower() == "platform":
                        continue
                    # Avoid summary/footer rows and header-like labels.
                    if title.lower() in ("title", "total", "games"):
                        continue
                    data = dict(name=title, platform=platform,
                                price_paid=number(r.get(start+2), None),
                                completed=yes(r.get(start+3)), backlog=yes(r.get(start+4)),
                                playtime=hours(r.get(start+5)), started=yes(r.get(start+6)),
                                achievements_unlocked=integer(r.get(start+7)),
                                achievements_total=integer(r.get(start+8)))
                    if start == 12:
                        data.update(cex_value=number(r.get(21), None),
                                    release_year=integer(r.get(22), None),
                                    barcode=clean(r.get(23)) or None)
                    result["games"].append(data)
        elif sheet == "Books":
            for r in rows:
                title = clean(r.get(3))
                if not title or title.lower() == "title": continue
                result["books"].append(dict(name=title, type=clean(r.get(2)),
                    price_paid=number(r.get(4), None), owned=yes(r.get(5)),
                    completed=yes(r.get(6)), genre=clean(r.get(7)),
                    page_count=integer(r.get(8)), read_count=integer(r.get(9)),
                    reading_time=hours(r.get(10)), author=clean(r.get(11)),
                    series=clean(r.get(12)), release_year=integer(r.get(13), None),
                    in_progress=0))
        elif sheet == "Shows":
            for r in rows:
                title = clean(r.get(2))
                if not title or title.lower() == "show": continue
                result["shows"].append(dict(name=title, season=integer(r.get(3)),
                    runtime=hours(r.get(4)), episode_count=integer(r.get(5)),
                    episode_reached=integer(r.get(6)), completed=yes(r.get(7)),
                    in_progress=yes(r.get(8)), watch_count=integer(r.get(9)),
                    owned=yes(r.get(10)), type=clean(r.get(11)), genre=clean(r.get(12))))
        else:
            for r in rows:
                title = clean(r.get(2))
                if not title or title.lower() == "movie": continue
                result["movies"].append(dict(name=title, runtime=hours(r.get(3)),
                    completed=yes(r.get(4)), in_progress=yes(r.get(5)),
                    watch_count=integer(r.get(6)), owned=yes(r.get(7)),
                    type=clean(r.get(8)), genre=clean(r.get(9))))
    return result

def key(kind, record):
    if kind == "games": return (record["name"].casefold(), record["platform"].casefold())
    if kind == "shows": return (record["name"].casefold(), record["season"])
    return (record["name"].casefold(),)

def existing_keys(kind):
    if kind == "games": cols = "name, platform"
    elif kind == "shows": cols = "name, season"
    else: cols = "name"
    cursor.execute(f"SELECT {cols} FROM {kind}")
    return {tuple(str(x).casefold() if isinstance(x, str) else x for x in row)
            for row in cursor.fetchall()}

def plan(rows):
    out = {}
    for kind, records in rows.items():
        known = existing_keys(kind)
        fresh, duplicate = [], 0
        for r in records:
            k = key(kind, r)
            if k in known:
                duplicate += 1
            else:
                fresh.append(r)
                known.add(k)
        out[kind] = (fresh, duplicate, len(records))
    return out

def import_plan(preview):
    # All-or-nothing transaction. Never replace existing entries or playtime.
    try:
        with connection:
            for kind, (records, _, _) in preview.items():
                for r in records:
                    cols = list(r)
                    sql = (f"INSERT INTO {kind} ({','.join(cols)}) VALUES "
                           f"({','.join('?' for _ in cols)})")
                    connection.execute(sql, [r[c] for c in cols])
    except Exception:
        raise

def open_import(parent, accent, on_done=None):
    path = filedialog.askopenfilename(parent=parent.winfo_toplevel(),
            title="Choose Collection Master workbook",
            filetypes=[("Excel Workbook", "*.xlsx")])
    if not path: return
    try:
        rows = extract(path)
        preview = plan(rows)
    except Exception as exc:
        messagebox.showerror("Excel Import", f"Could not read this workbook:\n\n{exc}",
                             parent=parent.winfo_toplevel())
        return
    dialog = tk.Toplevel(parent)
    polish_dialog(dialog)
    dialog.title("Preview Excel Import")
    dialog.geometry("640x480")
    dialog.configure(bg=BG)
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()
    tk.Label(dialog, text="Excel Import Preview", bg=BG, fg=TEXT,
             font=("Arial", 20, "bold")).pack(anchor="w", padx=25, pady=(24, 5))
    tk.Label(dialog, text=f"Source: {Path(path).resolve()}",
             bg=BG, fg=MUTED, wraplength=580, justify="left").pack(
                 anchor="w", padx=25, pady=(0, 6))
    tk.Label(dialog, text="Found = read from Excel | New = not already in app | Skipped = duplicate",
             bg=BG, fg=MUTED).pack(anchor="w", padx=25, pady=(0, 15))
    table = ttk.Treeview(dialog, columns=("sheet", "found", "new", "skipped"),
                         show="headings", height=5)
    for col, width in (("sheet", 130), ("found", 95), ("new", 95), ("skipped", 120)):
        table.heading(col, text=col.title())
        table.column(col, width=width, anchor="center")
    table.pack(fill="x", padx=25)
    for kind, (new, duplicates, total) in preview.items():
        table.insert("", "end", values=(kind.title(), total, len(new), duplicates))
    total_new = sum(len(new) for new, _, _ in preview.values())
    found_total = sum(total for _, _, total in preview.values())
    tk.Label(dialog, text=f"{found_total:,} found in workbook  |  {total_new:,} new entries",
             bg=BG, fg=accent, font=("Arial", 13, "bold")).pack(
                 anchor="w", padx=25, pady=(20, 6))
    tk.Label(dialog, text="Excel time values are converted from days to hours. "
             "The Stats sheet and Minecraft modpack scratchpad are ignored. "
             "Games match by title + platform; shows by title + season.",
             bg=BG, fg=MUTED, wraplength=580, justify="left").pack(
                 anchor="w", padx=25)
    if any(total == 0 for _, _, total in preview.values()):
        tk.Label(dialog, text="WARNING: One or more collection sheets returned zero entries. "
                 "Check the source path and sheet headings before importing.",
                 bg=BG, fg="#FFB86C", wraplength=580, justify="left").pack(
                     anchor="w", padx=25, pady=(12, 0))
    actions = tk.Frame(dialog, bg=BG)
    actions.pack(side="bottom", fill="x", padx=25, pady=22)
    def confirm():
        try:
            # Re-check duplicates immediately before committing.
            latest = plan(rows)
            import_plan(latest)
        except Exception as exc:
            messagebox.showerror("Import Failed", f"No changes committed:\n\n{exc}",
                                 parent=dialog)
            return
        imported = sum(len(new) for new, _, _ in latest.values())
        dialog.destroy()
        messagebox.showinfo("Import Complete", f"Imported {imported:,} entries.",
                            parent=parent.winfo_toplevel())
        if on_done: on_done()
    tk.Button(actions, text="Import New Entries", command=confirm,
              state="normal" if total_new and all(total > 0 for _, _, total in preview.values()) else "disabled",
              bg=accent, fg="white", relief="flat", padx=15, pady=9).pack(side="right")
    tk.Button(actions, text="Cancel", command=dialog.destroy,
              bg=PANEL_ALT, fg=TEXT, relief="flat", padx=15, pady=9).pack(
                  side="right", padx=8)
