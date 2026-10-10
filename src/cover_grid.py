"""Reusable, paginated cover-grid view for all four libraries."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from database import PROJECT_ROOT, cursor
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED, BORDER
from database import get_setting

try:
    from PIL import Image, ImageTk, ImageOps
except ImportError:
    Image = ImageTk = ImageOps = None

PAGE_SIZE = 60
CARD_WIDTH = 256
ART_WIDTH = 252
ART_HEIGHT = 354

class CoverGrid(tk.Frame):
    def __init__(self, parent, kind, open_detail):
        super().__init__(parent, bg=BG)
        self.kind = kind
        self.open_detail = open_detail
        self.rows = []
        self.page = 0
        self.photos = []
        # Determine the initial column count BEFORE the first render.
        # Previously a one-column grid flashed before <Configure> rebuilt it.
        available = max(450, parent.winfo_toplevel().winfo_width() - 280)
        self.columns = max(1, (available - 18) // (CARD_WIDTH + 6))
        self._resize_job = None

        self.header = tk.Frame(self, bg=BG)
        self.header.pack(side="top", fill="x", padx=18, pady=(8, 2))
        tk.Label(self.header, text="YOUR COLLECTION", bg=BG, fg=MUTED,
                 font=("Arial", 10, "bold")).pack(side="left")
        self.count_label = tk.Label(self.header, bg=BG, fg=MUTED,
                                    font=("Arial", 10))
        self.count_label.pack(side="right")

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical",
                                       style="Dark.Vertical.TScrollbar",
                                       command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="top", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.inner_id = self.canvas.create_window((6, 4), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._resized)
        # A class binding works for the canvas AND its nested cover tiles,
        # without taking over mouse-wheel events elsewhere in the app.
        self._wheel_tag = f"CoverWheel{id(self)}"
        self.bind_class(self._wheel_tag, "<MouseWheel>", self._wheel)
        self.bind_class(self._wheel_tag, "<Button-4>", self._wheel)
        self.bind_class(self._wheel_tag, "<Button-5>", self._wheel)
        self._install_wheel_tag(self.canvas)
        self._install_wheel_tag(self.inner)

        self.footer = tk.Frame(self, bg=BG)
        self.footer.pack(side="bottom", fill="x", pady=7)
        self.prev = tk.Button(self.footer, text="← Previous", command=lambda: self.change_page(-1),
                              bg=PANEL_ALT, fg=TEXT, relief="flat", bd=0, padx=12, pady=7)
        self.prev.pack(side="left", padx=12)
        self.status = tk.Label(self.footer, bg=BG, fg=MUTED)
        self.status.pack(side="left", expand=True)
        self.next = tk.Button(self.footer, text="Next →", command=lambda: self.change_page(1),
                              bg=PANEL_ALT, fg=TEXT, relief="flat", bd=0, padx=12, pady=7)
        self.next.pack(side="right", padx=12)

    def _install_wheel_tag(self, widget):
        tags = widget.bindtags()
        if self._wheel_tag not in tags:
            widget.bindtags((tags[0], self._wheel_tag) + tags[1:])

    def _wheel(self, event):
        if getattr(self,'cancel_return_restore',None):self.cancel_return_restore()
        if not self.canvas.winfo_exists():
            return
        if getattr(event, "num", None) == 4:
            steps = -1
        elif getattr(event, "num", None) == 5:
            steps = 1
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return
            steps = -max(1, abs(delta) // 120) if delta > 0 else max(1, abs(delta) // 120)
        self.canvas.yview_scroll(steps, "units")
        return "break"

    def _resized(self, event):
        self.canvas.itemconfigure(self.inner_id, width=max(1, event.width - 12))
        columns = max(1, (event.width - 18) // (CARD_WIDTH + 6))
        if columns != self.columns:
            self.columns = columns
            if self._resize_job:
                self.after_cancel(self._resize_job)
            self._resize_job = self.after(100, self.render)

    def set_search(self, search="", platform=None, sort="Name: A–Z", status="All Statuses", filtered_ids=None):
        ordering = {
            "Name: A–Z": "name COLLATE NOCASE ASC, id ASC",
            "Name: Z–A": "name COLLATE NOCASE DESC, id DESC",
            "Most Played": "playtime DESC, name COLLATE NOCASE",
            "Least Played": "playtime ASC, name COLLATE NOCASE",
            "Recently Added": "id DESC",
            "Oldest Added": "id ASC",
            "Platform": "platform COLLATE NOCASE, name COLLATE NOCASE",
        }
        if self.kind == "games":
            sql = "SELECT id, name, cover_path FROM games WHERE name LIKE ?"
            params = [f"%{search}%"]
            if platform and platform != "All Platforms":
                sql += " AND platform = ?"
                params.append(platform)
            conditions = {"Backlog": "backlog = 1", "Completed": "completed = 1",
                          "Started": "started = 1", "Not Started": "started = 0",
                          "Not Completed": "completed = 0"}
            if status in conditions:
                sql += " AND " + conditions[status]
            sql += " ORDER BY " + ordering.get(sort, ordering["Name: A–Z"])
            cursor.execute(sql, params)
        else:
            cursor.execute(
                f"SELECT id, name, cover_path FROM {self.kind} WHERE name LIKE ? "
                "ORDER BY name COLLATE NOCASE", (f"%{search}%",))
        self.rows = cursor.fetchall()
        if filtered_ids is not None:
            lookup = {row[0]: row for row in self.rows}
            self.rows = [lookup[ident] for ident in filtered_ids if ident in lookup]
        if self.kind == 'shows':
            from show_series import groups
            listings=groups([row[0] for row in self.rows])
            self.show_season_counts={g['id']:len({r['season'] for r in g['members']}) for g in listings}
            self.rows=[(g['id'],g['name'],g['cover_path']) for g in listings]
        self.page = 0
        self.render()

    def change_page(self, offset):
        if getattr(self,'cancel_return_restore',None):self.cancel_return_restore()
        new_page = self.page + offset
        if 0 <= new_page < max(1, (len(self.rows) + PAGE_SIZE - 1) // PAGE_SIZE):
            self.page = new_page
            self.render()
            self.canvas.yview_moveto(0)

    def _photo(self, cover_path):
        if not cover_path or Image is None:
            return None
        try:
            path = (PROJECT_ROOT / cover_path).resolve()
            if not path.is_file() or not path.is_relative_to(PROJECT_ROOT.resolve()):
                return None
            with Image.open(path) as source:
                image = (ImageOps.pad(source.convert("RGB"), (ART_WIDTH, ART_HEIGHT), color="#202329")
                         if self.kind == "cds" else ImageOps.fit(source.convert("RGB"), (ART_WIDTH, ART_HEIGHT)))
                photo = ImageTk.PhotoImage(image)
                self.photos.append(photo)
                return photo
        except (OSError, ValueError):
            return None

    def render(self):
        if not self.winfo_exists():
            return
        for child in self.inner.winfo_children():
            child.destroy()
        self.photos.clear()
        cols = max(1, self.columns)
        self.count_label.configure(text=f"{len(self.rows):,} titles")
        for col in range(cols):
            self.inner.grid_columnconfigure(col, weight=0)
        subset = self.rows[self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE]
        for index, (item_id, name, cover_path) in enumerate(subset):
            accent = get_setting("accent_color", "#B23A48")
            card = tk.Frame(self.inner, bg=PANEL, width=CARD_WIDTH, height=ART_HEIGHT + 20,
                            highlightbackground=BORDER, highlightthickness=1,
                            cursor="hand2")
            card.grid(row=index // cols, column=index % cols, padx=3, pady=3, sticky="nw")
            card.grid_propagate(False)
            self._install_wheel_tag(card)

            image_holder = tk.Frame(card, bg=PANEL_ALT, width=ART_WIDTH, height=ART_HEIGHT,
                                    highlightthickness=2, highlightbackground=PANEL_ALT,
                                    highlightcolor=PANEL_ALT)
            image_holder.pack(pady=0)
            image_holder.pack_propagate(False)
            self._install_wheel_tag(image_holder)
            photo = self._photo(cover_path)
            if photo:
                picture = tk.Label(image_holder, image=photo, bg=PANEL_ALT,
                                   bd=0, cursor="hand2")
            else:
                picture = tk.Label(image_holder, text="NO ARTWORK",
                                   bg=PANEL_ALT, fg=MUTED,
                                   font=("Arial", 11, "bold"),
                                   justify="center", cursor="hand2")
            picture.pack(fill="both", expand=True)
            if self.kind=='shows':
                count=getattr(self,'show_season_counts',{}).get(item_id,1)
                tk.Label(card,text=name[:23]+f' · {count} season'+('s' if count!=1 else ''),
                         bg=PANEL,fg=TEXT,font=('Arial',9)).pack(fill='x')
            self._install_wheel_tag(picture)

            # Keep hover visually static: no border, font, size or padding changes.
            # Hover-triggered geometry changes caused the entire grid to jump.
            def highlight(_event, holder=image_holder):
                if holder.winfo_exists():
                    holder.configure(highlightbackground=get_setting("accent_color", "#B23A48"))
            def unhighlight(_event, holder=image_holder):
                if holder.winfo_exists():
                    holder.configure(highlightbackground=PANEL_ALT)
            picture.bind("<Enter>", highlight)
            picture.bind("<Leave>", unhighlight)
            for widget in (card, image_holder, picture):
                widget.bind("<Button-1>", lambda event, ident=item_id: self.open_detail(ident))
        total_pages = max(1, (len(self.rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        self.status.configure(text=f"{len(self.rows):,} items  •  Page {self.page + 1} of {total_pages}")
        self.prev.configure(state="normal" if self.page > 0 else "disabled")
        self.next.configure(state="normal" if self.page + 1 < total_pages else "disabled")
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

