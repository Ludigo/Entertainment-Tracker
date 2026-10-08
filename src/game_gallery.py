"""Local per-game screenshots with a horizontal, navigable gallery."""
from window_style import install as polish_dialog

from pathlib import Path
import shutil
from media_naming import clean_name
import tkinter as tk
from tkinter import filedialog
from database import PROJECT_ROOT, connection, cursor
from modal import app_messagebox as messagebox
from theme import PANEL, PANEL_ALT, TEXT, MUTED, BORDER
GALLERY_BG = "#292E35"

try:
    from PIL import Image, ImageTk, ImageOps
except ImportError:
    Image = ImageTk = ImageOps = None

SCREENSHOTS_ROOT = PROJECT_ROOT / "assets" / "screenshots" / "games"
SCREENSHOTS_ROOT.mkdir(parents=True, exist_ok=True)
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class GameGallery(tk.Frame):
    def __init__(self, parent, game_id, accent):
        super().__init__(parent, bg=GALLERY_BG)
        self.game_id = game_id
        self.accent = accent
        self.offset = 0
        self.photos = []
        self.refresh()

    def refresh(self):
        for child in self.winfo_children():
            child.destroy()
        cursor.execute("SELECT id, image_path FROM game_screenshots "
                       "WHERE game_id=? ORDER BY id", (self.game_id,))
        self.items = cursor.fetchall()
        self.offset = min(self.offset, max(0, len(self.items) - 2))
        heading = tk.Frame(self, bg=GALLERY_BG)
        heading.pack(fill="x", pady=(0, 8))
        tk.Label(heading, text="GAMEPLAY SCREENSHOTS", bg=GALLERY_BG, fg=self.accent,
                 font=("Arial", 10, "bold")).pack(side="left")
        tk.Button(heading, text="+ Add", command=self.add, bg=PANEL_ALT,
                  fg=TEXT, relief="flat", padx=9).pack(side="right", padx=(6, 0))
        if not self.items:
            tk.Label(self, text="No screenshots yet. Add gameplay images from your PC.",
                     bg=GALLERY_BG, fg=MUTED, font=("Arial", 10)).pack(anchor="w", pady=8)
            return
        nav = tk.Frame(self, bg=GALLERY_BG)
        nav.pack(fill="x")
        tk.Button(nav, text="‹", command=lambda: self.move(-1), bg=PANEL_ALT,
                  fg=TEXT, relief="flat", width=3,
                  state="normal" if self.offset else "disabled").pack(side="left", padx=(0, 5))
        strip = tk.Frame(nav, bg=GALLERY_BG)
        strip.pack(side="left", fill="x", expand=True)
        self.photos = []
        for shot_id, relative in self.items[self.offset:self.offset+2]:
            frame = tk.Frame(strip, bg=PANEL_ALT, padx=4, pady=4)
            frame.pack(side="left", fill="x", expand=True, padx=3)
            path = PROJECT_ROOT / relative
            if Image is not None and path.is_file():
                try:
                    with Image.open(path) as im:
                        image = ImageOps.contain(im.convert("RGB"), (235, 132))
                    photo = ImageTk.PhotoImage(image)
                    self.photos.append(photo)
                    tk.Button(frame, image=photo, command=lambda p=path: self.preview(p),
                              bg=PANEL_ALT, relief="flat", bd=0,
                              cursor="hand2").pack()
                except (OSError, ValueError):
                    tk.Label(frame, text="Image unavailable", bg=PANEL_ALT, fg=MUTED).pack()
            else:
                tk.Button(frame, text=path.name if path.exists() else "Missing image",
                          command=lambda p=path: self.preview(p),
                          bg=PANEL_ALT, fg=TEXT, relief="flat").pack()
            tk.Button(frame, text="Remove", command=lambda sid=shot_id: self.remove(sid),
                      bg=PANEL_ALT, fg=MUTED, relief="flat").pack(pady=(4, 0))
        tk.Button(nav, text="›", command=lambda: self.move(1), bg=PANEL_ALT,
                  fg=TEXT, relief="flat", width=3,
                  state="normal" if self.offset+2 >= len(self.items) else "disabled").pack(
                      side="right", padx=(5, 0))
        tk.Label(self, text=f"{self.offset+1}–{min(self.offset+2, len(self.items))} of {len(self.items)}",
                 bg=GALLERY_BG, fg=MUTED, font=("Arial", 9)).pack(anchor="e", pady=(5, 0))

    def move(self, step):
        self.offset = max(0, min(self.offset + step, max(0, len(self.items) - 2)))
        self.refresh()

    def add(self):
        filenames = filedialog.askopenfilenames(
            parent=self.winfo_toplevel(), title="Choose Gameplay Screenshots",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")])
        if not filenames:
            return
        try:
            for filename in filenames:
                source = Path(filename)
                if source.suffix.lower() not in EXTENSIONS:
                    continue
                cursor.execute("INSERT INTO game_screenshots(game_id, image_path) "
                               "VALUES (?, '')", (self.game_id,))
                shot_id = cursor.lastrowid
                row = connection.execute("SELECT name FROM games WHERE id=?", (self.game_id,)).fetchone()
                title = clean_name(row[0] if row else f"Game {self.game_id}")
                destination = SCREENSHOTS_ROOT / f"{title} - Screenshot {shot_id:02d}{source.suffix.lower()}"
                shutil.copy2(source, destination)
                cursor.execute("UPDATE game_screenshots SET image_path=? WHERE id=?",
                               (destination.relative_to(PROJECT_ROOT).as_posix(), shot_id))
            connection.commit()
            self.offset = max(0, self.count() - 2)
            self.refresh()
        except Exception as exc:
            connection.rollback()
            messagebox.showerror("Screenshots", f"Could not import screenshot.\\n\\n{exc}")

    def count(self):
        cursor.execute("SELECT COUNT(*) FROM game_screenshots WHERE game_id=?", (self.game_id,))
        return cursor.fetchone()[0]

    def remove(self, shot_id):
        if not messagebox.askyesno("Remove Screenshot", "Remove this screenshot from the game?"):
            return
        cursor.execute("SELECT image_path FROM game_screenshots WHERE id=? AND game_id=?",
                       (shot_id, self.game_id))
        row = cursor.fetchone()
        if row is None:
            return
        cursor.execute("DELETE FROM game_screenshots WHERE id=?", (shot_id,))
        connection.commit()
        path = PROJECT_ROOT / row[0]
        if path.is_file() and SCREENSHOTS_ROOT in path.parents:
            try:
                path.unlink()
            except OSError:
                pass
        self.refresh()

    def preview(self, path):
        if Image is None:
            messagebox.showinfo("Screenshot Preview", "Install Pillow for image previews: py -m pip install pillow")
            return
        if not path.is_file():
            messagebox.showerror("Screenshot Preview", "Image file is missing.")
            return
        window = tk.Toplevel(self)
        polish_dialog(window)
        window.title(path.name)
        window.configure(bg="#101216")
        window.geometry("1000x650")
        with Image.open(path) as im:
            image = ImageOps.contain(im.convert("RGB"), (950, 590))
        photo = ImageTk.PhotoImage(image)
        label = tk.Label(window, image=photo, bg="#101216")
        label.image = photo
        label.pack(fill="both", expand=True, padx=15, pady=15)
        tk.Button(window, text="Close", command=window.destroy,
                  bg=PANEL_ALT, fg=TEXT, relief="flat").pack(pady=(0, 10))
