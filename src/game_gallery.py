"""Local per-game screenshots with a horizontal, navigable gallery."""
from window_style import install as polish_dialog

from pathlib import Path
import shutil
import hashlib
import uuid
from media_naming import clean_name
from artwork_preferences import import_folder, remember_import_folder
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


def screenshot_digest(path):
    """Recognise exact file copies without relying on their names."""
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_screenshot(path):
    path = Path(path)
    if path.suffix.lower() not in EXTENSIONS or not path.is_file():
        raise ValueError('Choose a supported image file.')
    if Image is not None:
        with Image.open(path) as image:
            if image.format not in ('PNG', 'JPEG', 'WEBP', 'BMP'):
                raise ValueError('Choose a PNG, JPEG, WebP or BMP image.')
            if image.width * image.height > 60_000_000:
                raise ValueError('Image exceeds 60 megapixels.')
            dimensions = image.size
            image.verify()
    else:
        dimensions = None
    return screenshot_digest(path), dimensions


class GameGallery(tk.Frame):
    def __init__(self, parent, game_id, accent, grid_view=False):
        super().__init__(parent, bg=GALLERY_BG)
        self.grid_view = grid_view
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
        if self.grid_view:
            self.render_grid()
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

    def render_grid(self):
        """Scrollable manager grid; the details page retains its compact strip."""
        from tkinter import ttk
        container = tk.Frame(self, bg=GALLERY_BG)
        container.pack(fill='both', expand=True)
        canvas = tk.Canvas(container, bg=GALLERY_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        body = tk.Frame(canvas, bg=GALLERY_BG)
        window_id = canvas.create_window(0, 0, window=body, anchor='nw')
        body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        cards = []
        for shot_id, relative in self.items:
            path = PROJECT_ROOT / relative
            card = tk.Frame(body, bg=PANEL_ALT, padx=6, pady=6)
            cards.append(card)
            photo = None
            if Image is not None and path.is_file():
                try:
                    with Image.open(path) as image:
                        photo = ImageTk.PhotoImage(ImageOps.contain(image.convert('RGB'), (220, 124)))
                    self.photos.append(photo)
                except (OSError, ValueError):
                    pass
            thumbnail=tk.Button(card, image=photo or '', text='' if photo else 'Image unavailable',
                                command=lambda p=path: self.preview(p), bg=PANEL_ALT, fg=TEXT,
                                relief='flat', cursor='hand2')
            thumbnail.pack()
            name_label=tk.Label(card, text=path.name, bg=PANEL_ALT, fg=MUTED,wraplength=220)
            name_label.pack(pady=4)
            menu=tk.Menu(card,tearoff=False,bg=PANEL_ALT,fg=TEXT,
                         activebackground=self.accent,activeforeground='white')
            menu.add_command(label='Preview',command=lambda p=path:self.preview(p))
            menu.add_command(label='Remove',command=lambda sid=shot_id:self.remove(sid))
            def show_menu(event,context=menu):
                try:context.tk_popup(event.x_root,event.y_root)
                finally:context.grab_release()
                return 'break'
            for widget in (card,thumbnail,name_label):
                widget.bind('<Button-3>',show_menu)
        layout = {'columns': None}
        def resize(event):
            canvas.itemconfigure(window_id, width=event.width)
            columns = max(1, event.width // 250)
            if columns != layout['columns']:
                layout['columns'] = columns
                for index, card in enumerate(cards):
                    card.grid(row=index // columns, column=index % columns,
                              padx=6, pady=6, sticky='n')
        canvas.bind('<Configure>', resize)
        def wheel(event):
            canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
            return 'break'
        # Window-local binding avoids affecting other galleries or dialogs.
        top = self.winfo_toplevel()
        binding = top.bind('<MouseWheel>', wheel, add='+')
        def cleanup(event):
            if event.widget is canvas:
                try:top.unbind('<MouseWheel>', binding)
                except tk.TclError:pass
        canvas.bind('<Destroy>', cleanup)
        tk.Label(self, text=f'{len(self.items)} screenshots · Click to preview · Right-click for actions', bg=GALLERY_BG,
                 fg=MUTED).pack(anchor='e', pady=4)

    def move(self, step):
        self.offset = max(0, min(self.offset + step, max(0, len(self.items) - 2)))
        self.refresh()

    def add(self):
        filenames = filedialog.askopenfilenames(
            parent=self.winfo_toplevel(), title="Choose Gameplay Screenshots",
            initialdir=import_folder('screenshots'),
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")])
        if not filenames:
            return
        try:remember_import_folder('screenshots',filenames)
        except Exception:pass
        known = self.existing_digests()
        candidates = []
        for filename in filenames:
            path = Path(filename)
            try:
                digest, dimensions = validate_screenshot(path)
                reason = 'Exact duplicate — skipped' if digest in known else ''
                known.add(digest)
                candidates.append(dict(path=path, digest=digest, dimensions=dimensions,
                                       reason=reason))
            except Exception as exc:
                candidates.append(dict(path=path, digest=None, dimensions=None,
                                       reason=f'Unavailable: {exc}'))
        self.review_import(candidates)

    def existing_digests(self):
        known = set()
        rows = connection.execute('SELECT image_path FROM game_screenshots WHERE game_id=?',
                                  (self.game_id,)).fetchall()
        for (relative,) in rows:
            try:
                known.add(screenshot_digest(PROJECT_ROOT / relative))
            except (OSError, TypeError):
                continue
        return known

    def review_import(self, candidates):
        dialog = tk.Toplevel(self)
        dialog.title('Review Screenshot Import')
        dialog.geometry('700x540')
        dialog.minsize(600, 430)
        dialog.configure(bg=PANEL)
        dialog.transient(self.winfo_toplevel())
        polish_dialog(dialog)
        tk.Label(dialog, text='Choose screenshots to import', bg=PANEL, fg=TEXT,
                 font=('Arial', 15, 'bold')).pack(anchor='w', padx=18, pady=(16, 6))
        tk.Label(dialog, text='Untick images you do not want. Click a filename to preview. Exact copies are skipped.',
                 bg=PANEL, fg=MUTED, wraplength=640, justify='left').pack(anchor='w', padx=18)
        footer = tk.Frame(dialog, bg=PANEL)
        footer.pack(side='bottom', fill='x', padx=18, pady=16)
        summary = tk.Label(dialog, text='', bg=PANEL, fg=MUTED)
        summary.pack(side='bottom', anchor='w', padx=18, pady=6)
        container = tk.Frame(dialog, bg=PANEL)
        container.pack(fill='both', expand=True, padx=18, pady=12)
        canvas = tk.Canvas(container, bg=PANEL, highlightthickness=0)
        from tkinter import ttk
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        body = tk.Frame(canvas, bg=PANEL)
        window_id = canvas.create_window(0, 0, window=body, anchor='nw')
        body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window_id, width=e.width))
        choices = []
        def update_count():
            count = sum(variable.get() for candidate, variable in choices)
            skipped = sum(bool(candidate['reason']) for candidate, variable in choices)
            summary.configure(text=f'{count} selected · {skipped} duplicate or unavailable')
            import_button.configure(state='normal' if count else 'disabled')
        for candidate in candidates:
            row = tk.Frame(body, bg=PANEL_ALT, padx=10, pady=8)
            row.pack(fill='x', pady=4)
            enabled = not candidate['reason']
            variable = tk.BooleanVar(value=enabled)
            choices.append((candidate, variable))
            tk.Checkbutton(row, variable=variable, bg=PANEL_ALT, selectcolor=PANEL,
                           activebackground=PANEL_ALT, state='normal' if enabled else 'disabled',
                           command=update_count).pack(side='left')
            label = tk.Label(row, text=candidate['path'].name, bg=PANEL_ALT, fg=TEXT,
                             cursor='hand2' if candidate['digest'] else 'arrow', anchor='w')
            label.pack(fill='x')
            if candidate['digest']:
                label.bind('<Button-1>', lambda e, p=candidate['path']: self.preview(p))
            dimensions = candidate['dimensions']
            detail = candidate['reason'] or (f'{dimensions[0]} × {dimensions[1]} pixels' if dimensions else 'Ready to import')
            tk.Label(row, text=detail, bg=PANEL_ALT, fg=MUTED, anchor='w',
                     wraplength=540, justify='left').pack(fill='x')
        def import_selected():
            selected = [candidate for candidate, variable in choices if variable.get() and not candidate['reason']]
            if not selected:
                return
            if self.import_candidates(selected):
                dialog.destroy()
        import_button = tk.Button(footer, text='Import Selected', command=import_selected,
                                  bg=self.accent, fg='white', relief='flat', padx=14, pady=8)
        import_button.pack(side='right')
        tk.Button(footer, text='Cancel', command=dialog.destroy, bg=PANEL_ALT, fg=TEXT,
                  relief='flat', padx=14, pady=8).pack(side='right', padx=(0, 8))
        dialog.bind('<Escape>', lambda e: dialog.destroy())
        update_count()

    def import_candidates(self, candidates):
        created = []
        try:
            known = self.existing_digests()
            imported = duplicates = 0
            for candidate in candidates:
                source = candidate['path']
                digest, dimensions = validate_screenshot(source)
                if digest != candidate['digest']:
                    raise ValueError(f'{source.name} changed after review. Choose the files again.')
                if digest in known:
                    duplicates += 1
                    continue
                cursor.execute("INSERT INTO game_screenshots(game_id, image_path) "
                               "VALUES (?, '')", (self.game_id,))
                shot_id = cursor.lastrowid
                row = connection.execute("SELECT name FROM games WHERE id=?", (self.game_id,)).fetchone()
                title = clean_name(row[0] if row else f"Game {self.game_id}")
                destination = SCREENSHOTS_ROOT / f"{title} - Screenshot {shot_id:02d} - {uuid.uuid4().hex[:8]}{source.suffix.lower()}"
                created.append(destination)
                shutil.copy2(source, destination)
                if screenshot_digest(destination) != digest:
                    raise ValueError(f'{source.name} changed while being imported. Choose the files again.')
                cursor.execute("UPDATE game_screenshots SET image_path=? WHERE id=?",
                               (destination.relative_to(PROJECT_ROOT).as_posix(), shot_id))
                known.add(digest)
                imported += 1
            connection.commit()
        except Exception as exc:
            connection.rollback()
            for destination in created:
                destination.unlink(missing_ok=True)
            messagebox.showerror('Screenshots', f'Could not import screenshots.\n\n{exc}')
            return False
        self.offset = max(0, self.count() - 2)
        self.refresh()
        messagebox.showinfo('Screenshots', f'{imported} imported · {duplicates} exact duplicates skipped.')
        return True

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
