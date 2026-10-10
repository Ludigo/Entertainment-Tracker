import shutil
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

try:
    from PIL import Image, ImageTk, ImageOps, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    Image = ImageTk = ImageOps = None
    PIL_AVAILABLE = False

from database import PROJECT_ROOT, connection, cursor, get_setting
from modal import app_messagebox as messagebox
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED, BORDER
from utils import format_time


# Independent game artwork roles; existing cover artwork is unaffected.
def _game_art_setup():
    connection.execute("""CREATE TABLE IF NOT EXISTS game_detail_art (
        game_id INTEGER PRIMARY KEY, logo_path TEXT, background_path TEXT)""")
    connection.commit()


def _game_art_paths(game_id):
    _game_art_setup()
    row = connection.execute('SELECT logo_path,background_path FROM game_detail_art WHERE game_id=?',
                             (game_id,)).fetchone()
    return row if row else (None, None)


def _set_game_art(game_id, role, path):
    if role not in ('logo_path', 'background_path'):
        raise ValueError('Invalid artwork role')
    from artwork_preferences import require_unlocked
    require_unlocked('games',game_id,role)
    _game_art_setup()
    with connection:
        connection.execute('INSERT OR IGNORE INTO game_detail_art(game_id) VALUES(?)', (game_id,))
        connection.execute('UPDATE game_detail_art SET '+role+'=? WHERE game_id=?', (path, game_id))


def _choose_game_art(parent, game_id, role, refresh):
    from tkinter import ttk
    from artwork_manager import store
    from window_style import install as polish_dialog
    dialog = tk.Toplevel(parent)
    dialog.title('Choose game logo' if role == 'logo_path' else 'Choose background fan art')
    dialog.configure(bg=BG)
    dialog.geometry('680x610')
    dialog.minsize(640, 590)
    polish_dialog(dialog)
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()
    tk.Label(dialog, text='Choose saved artwork or add an image', bg=BG, fg=TEXT,
             font=('Arial', 14, 'bold')).pack(anchor='w', padx=18, pady=(18, 8))
    rows = connection.execute('SELECT image_path,width,height FROM artwork_library '
                              'WHERE category=? AND item_id=? ORDER BY id DESC',
                              ('games', game_id)).fetchall()
    minimum_widths = {'All sizes': 0, '512 px+': 512, '1280 px+': 1280,
                      '1920 px+': 1920, '3840 px+': 3840}
    filters = tk.Frame(dialog, bg=BG)
    filters.pack(fill='x', padx=18, pady=(8, 0))
    tk.Label(filters, text='Minimum width', bg=BG, fg=TEXT).pack(side='left')
    minimum_width = tk.StringVar(value='All sizes')
    filter_box = ttk.Combobox(filters, textvariable=minimum_width,
                             values=list(minimum_widths), state='readonly', width=15)
    filter_box.pack(side='left', padx=10)
    count_label = tk.Label(filters, text='', bg=BG, fg=MUTED)
    count_label.pack(side='right')
    selected = tk.StringVar(value='')
    visible_rows = []
    box = ttk.Combobox(dialog, values=[], textvariable=selected, state='readonly', width=64)
    box.pack(fill='x', padx=18, pady=12)
    preview_area = tk.Frame(dialog, bg=PANEL_ALT, height=250)
    preview_area.pack(fill='x', padx=18)
    preview_area.pack_propagate(False)
    preview = tk.Label(preview_area, text='Choose an image to preview it.', bg=PANEL_ALT,
                       fg=MUTED, wraplength=570)
    preview.pack(fill='both', expand=True)
    preview_state = {'photo': None}
    status = tk.Label(dialog, text='Choose an existing image or import one from your PC.',
                      bg=BG, fg=MUTED, wraplength=570)
    status.pack(anchor='w', padx=18, pady=(10, 0))
    def selected_row():
        index = box.current()
        return visible_rows[index] if 0 <= index < len(visible_rows) else None
    def show_preview(event=None):
        preview.configure(image='', text='No image selected.')
        preview_state['photo'] = None
        use_button.configure(state='disabled')
        row = selected_row()
        if row is None:
            status.configure(text='No artwork matches this filter. Choose All sizes or add an image from your PC.')
            return
        relative, width, height = row
        path = PROJECT_ROOT / relative
        if not path.is_file():
            preview.configure(text='This saved image is missing.')
            status.configure(text='Add an image from your PC to replace the missing artwork.')
            return
        if not PIL_AVAILABLE:
            preview.configure(text='Install Pillow to see artwork previews.')
            status.configure(text=f'{width} × {height} pixels — {path.name}')
            use_button.configure(state='normal')
            return
        try:
            with Image.open(path) as image:
                if image.width * image.height > 60_000_000:
                    raise ValueError('Image exceeds the 60-megapixel limit.')
                picture = image.convert('RGBA')
                picture.thumbnail((580, 230), Image.Resampling.LANCZOS)
            preview_state['photo'] = ImageTk.PhotoImage(picture)
            preview.configure(image=preview_state['photo'], text='')
            status.configure(text=f'{width} × {height} pixels — {path.name}')
            use_button.configure(state='normal')
        except (OSError, ValueError, Image.DecompressionBombError):
            preview.configure(text='This saved image could not be previewed.')
            status.configure(text='Choose another image or add a valid image from your PC.')
    def apply_filter(event=None, preferred_path=None):
        previous = selected_row()
        wanted = preferred_path if preferred_path is not None else (previous[0] if previous else None)
        threshold = minimum_widths.get(minimum_width.get(), 0)
        visible_rows[:] = [row for row in rows if (row[1] or 0) >= threshold]
        box.configure(values=[f'{w} × {h}   •   {Path(path).name}' for path, w, h in visible_rows])
        count_label.configure(text=f'{len(visible_rows)} of {len(rows)} images')
        index = next((i for i, row in enumerate(visible_rows) if row[0] == wanted), 0)
        if visible_rows:
            box.current(index)
        else:
            selected.set('')
        show_preview()
    def save(path):
        _set_game_art(game_id, role, path)
        dialog.destroy()
        refresh()
    def use_saved():
        row = selected_row()
        if row is not None and str(use_button.cget('state')) == 'normal':
            save(row[0])
        else:
            status.configure(text='No image selected.')
    def import_file():
        filename = filedialog.askopenfilename(parent=dialog, filetypes=[('Images','*.png *.jpg *.jpeg *.webp'),('All files','*.*')])
        if not filename: return
        try:
            if not PIL_AVAILABLE: raise RuntimeError('Pillow is required for image imports')
            with Image.open(filename) as img:
                img.verify()
            with Image.open(filename) as img:
                w,h = img.size
                fmt = img.format
            if fmt not in ('JPEG','PNG','WEBP') or w*h > 60_000_000:
                raise ValueError('Please choose a JPEG, PNG or WebP image under 60 megapixels')
            ext = {'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[fmt]
            path = store('games', game_id, Path(filename).read_bytes(), w, h, ext, 'Local file', set_cover=False)
            # Import into the local artwork collection, then preview before assignment.
            rows.insert(0, (path, w, h))
            minimum_width.set('All sizes')
            apply_filter(preferred_path=path)
            status.configure(text=f'{w} × {h} pixels — imported locally. Choose Use selected to apply it.')
        except Exception as exc:
            messagebox.showerror('Artwork', str(exc))
    actions = tk.Frame(dialog, bg=BG)
    actions.pack(side='bottom', fill='x', padx=18, pady=22)
    use_button = tk.Button(actions, text='Use selected', command=use_saved, bg=PANEL_ALT,
                           fg=TEXT, relief='flat', padx=12, pady=9)
    use_button.pack(side='left', padx=(0,8))
    for text, fn in [('Add from PC',import_file),('Remove artwork',lambda:save(None))]:
        tk.Button(actions, text=text, command=fn, bg=PANEL_ALT, fg=TEXT,
                  relief='flat', padx=12, pady=9).pack(side='left', padx=(0,8))
    tk.Button(actions,text='Cancel',command=dialog.destroy,bg=PANEL_ALT,fg=TEXT,
              relief='flat',padx=12,pady=9).pack(side='right')
    box.bind('<<ComboboxSelected>>', show_preview)
    filter_box.bind('<<ComboboxSelected>>', apply_filter)
    current_art = _game_art_paths(game_id)
    apply_filter(preferred_path=current_art[0 if role == 'logo_path' else 1])

COVER_ROOT = PROJECT_ROOT / "assets" / "covers"
for folder in ("games", "movies", "shows", "books"):
    (COVER_ROOT / folder).mkdir(parents=True, exist_ok=True)


def _safe_filename(value):
    cleaned = "".join(c if c.isalnum() or c in " -_.()" else "_" for c in value).strip()
    return cleaned[:90] or "cover"


def _absolute_cover(relative_path):
    if not relative_path:
        return None
    path = PROJECT_ROOT / relative_path
    return path if path.exists() else None


def _copy_cover(kind, item_id, title, source):
    source = Path(source)
    destination_dir = COVER_ROOT / kind
    destination_dir.mkdir(parents=True, exist_ok=True)
    extension = source.suffix.lower() if source.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"} else ".jpg"
    destination = destination_dir / f"{item_id}_{_safe_filename(title)}{extension}"
    shutil.copy2(source, destination)
    return destination.relative_to(PROJECT_ROOT).as_posix()


def _field(parent, label, value, accent):
    box = tk.Frame(parent, bg=PANEL_ALT, padx=14, pady=11)
    box.pack(fill="x", pady=4)
    tk.Label(box, text=label.upper(), font=("Arial", 8, "bold"), bg=PANEL_ALT, fg=MUTED).pack(anchor="w")
    tk.Label(box, text=str(value), font=("Arial", 11, "bold"), bg=PANEL_ALT, fg=TEXT,
             wraplength=520, justify="left").pack(anchor="w", pady=(2, 0))


def show_detail(parent, kind, item_id, accent, on_back, on_edit=None):
    """Render a media detail page inside the existing main content area."""
    # Replace the previous in-app page, including its calendar, before drawing details.
    for child in parent.winfo_children():
        child.destroy()

    table = kind
    cursor.execute(f"SELECT * FROM {table} WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if not item:
        messagebox.showerror("Not Found", "That library item could not be found.")
        on_back()
        return

    # cover_path is always the final column after the migration.
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    record = dict(zip(columns, item))
    cover_path = record.get("cover_path")

    if kind == "games":
        title = item[1]
        subtitle = item[2]
        # Keep factual game metadata distinct from personal tracking fields.
        # Only display values actually stored in this collection.
        game_facts = [("Platform", item[2])]
        if record.get("release_date"):
            # Display British dates without changing the ISO value stored in SQLite.
            from datetime import date as _release_date_type
            stored_release_date = str(record["release_date"]).strip()
            try:
                release_display = _release_date_type.fromisoformat(stored_release_date).strftime("%d %b %Y")
            except ValueError:
                release_display = stored_release_date
            game_facts.append(("Release Date", release_display))
        elif record.get("release_year"):
            game_facts.append(("Release Year", record["release_year"]))
        for label, key in (("Genre", "genre"), ("Developer", "developer"),
                           ("Publisher", "publisher"), ("Game Modes", "game_modes"),
                           ("Age Rating", "age_rating")):
            if record.get(key):
                game_facts.append((label, record[key]))
        activity_fields = [
            ("Recorded Playtime", format_time(item[3])),
            ("Price Paid", "Not recorded" if record.get("price_paid") is None
             else f"£{record['price_paid']:,.2f}"),
            ("Currently Playing", "Yes" if record.get("in_progress") else "No"),
            ("Completed", "Yes" if record.get("completed") else "No"),
            ("In Backlog", "Yes" if record.get("backlog") else "No"),
            ("Started Playing", "Yes" if record.get("started") else "No"),
        ]
        fields = game_facts + activity_fields
    elif kind == "movies":
        title = record["name"]
        subtitle = "Movie"
        fields = [("Runtime", format_time(record.get("runtime") or 0)),
                  ("Watch Count", record.get("watch_count") or 0),
                  ("Tracked Watch Time", format_time((record.get("runtime") or 0) * (record.get("watch_count") or 0))),
                  ("Completed", "Yes" if record.get("completed") else "No"),
                  ("In Progress", "Yes" if record.get("in_progress") else "No"),
                  ("Owned", "Yes" if record.get("owned") else "No"),
                  ("Type", record.get("type") or "—"), ("Genre", record.get("genre") or "—"),
                  ("Release Year", record.get("release_year") or "—"),
                  ("Director", record.get("director") or "—"),
                  ("Cast", record.get("cast_members") or "—"),
                  ("Rating", record.get("rating") or "—"),
                  ("Price Paid", "—" if record.get("price_paid") is None else f"£{record['price_paid']:,.2f}")]
    elif kind == "shows":
        title = record["name"]
        subtitle = f"Season {record.get('season') or 0}"
        runtime = record.get("runtime") or 0
        episodes = record.get("episode_count") or 0
        reached = record.get("episode_reached") or 0
        partial = runtime * reached / episodes if episodes else 0
        fields = [("Season", record.get("season") or 0), ("Season Runtime", format_time(runtime)),
                  ("Episodes", episodes), ("Episode Reached", reached),
                  ("Completed", "Yes" if record.get("completed") else "No"),
                  ("In Progress", "Yes" if record.get("in_progress") else "No"),
                  ("Watch Count", record.get("watch_count") or 0),
                  ("Owned", "Yes" if record.get("owned") else "No"),
                  ("Type", record.get("type") or "—"), ("Genre", record.get("genre") or "—"),
                  ("Tracked Watch Time", format_time(runtime * (record.get("watch_count") or 0) + partial)),
                  ("Release Year", record.get("release_year") or "—"),
                  ("Network / Service", record.get("network") or "—"),
                  ("Rating", record.get("rating") or "—"),
                  ("Price Paid", "—" if record.get("price_paid") is None else f"£{record['price_paid']:,.2f}")]
    else:
        title = record["name"]
        subtitle = record.get("type") or "Book"
        fields = [("Page Count", f"{record.get('page_count'):,}" if record.get("page_count") else "—"),
                  ("Reading Time", format_time(record.get("reading_time") or 0)),
                  ("Completed", "Yes" if record.get("completed") else "No"),
                  ("In Progress", "Yes" if record.get("in_progress") else "No"),
                  ("Read Count", record.get("read_count") or 0),
                  ("Owned", "Yes" if record.get("owned") else "No"),
                  ("Type", record.get("type") or "—"), ("Genre", record.get("genre") or "—"),
                  ("Author", record.get("author") or "—"),
                  ("Series", record.get("series") or "—"),
                  ("Release Year", record.get("release_year") or "—"),
                  ("Publisher", record.get("publisher") or "—"),
                  ("ISBN", record.get("isbn") or "—"),
                  ("Rating", record.get("rating") or "—"),
                  ("Price Paid", "—" if record.get("price_paid") is None else f"£{record['price_paid']:,.2f}")]

    # One artwork canvas spans the entire details page, not just the metadata column.
    # The navigation sidebar lives outside this parent and is unaffected.
    # Always use the cinematic game layout, even when no background artwork
    # has been assigned. Otherwise the right pane still uses the cinematic
    # renderer but loses its page canvas, leaving an empty-looking screen.
    full_art = kind == 'games' and PIL_AVAILABLE
    if full_art:
        page = tk.Canvas(parent, bg=BG, bd=0, highlightthickness=0)
        page.pack(fill='both', expand=True)
        page_state = {'photo': None, 'size': None, 'source': None, 'raster': None}
        art_file = _absolute_cover(_game_art_paths(item_id)[1])
        try:
            if art_file is not None:
                with Image.open(art_file) as image:
                    page_state['source'] = image.convert('RGB').copy()
        except (OSError, ValueError, TypeError):
            page_state['source'] = None
        def paint_page(event=None):
            if not page.winfo_exists(): return
            width, height = max(1,page.winfo_width()), max(1,page.winfo_height())
            if page_state['size'] == (width,height): return
            page_state['size'] = (width,height)
            if page_state['source'] is not None:
                backdrop = ImageOps.fit(page_state['source'], (width,height), method=Image.Resampling.LANCZOS)
                darkness = max(25,min(90,int(get_setting('game_background_darkness','48'))))
                tint = Image.new('RGB',(width,height),(14,17,22))
                backdrop = Image.blend(backdrop,tint,darkness/100)
            else:
                # Neutral dark fallback, shared by the page, toolbar and
                # independently scrolling details. No artwork is required.
                backdrop = Image.new('RGB', (width,height), (24,28,34))
            page_state['raster'] = backdrop
            page_state['photo'] = ImageTk.PhotoImage(backdrop)
            page.delete('page-art')
            page.create_image(0,0,anchor='nw',image=page_state['photo'],tags='page-art')
            page.tag_lower('page-art')
        page.bind('<Configure>',paint_page)
        # Existing Tk frames remain interactive; their dark surfaces provide readable overlays.
        page_container = page
    else:
        page = tk.Frame(parent,bg=BG)
        page.pack(fill='both',expand=True)
        page_container = page

    top = tk.Frame(page_container, bg=BG)
    if kind == 'games' and full_art:
        top.pack(fill="x", padx=(40, 34), pady=(12, 10))
    else:
        top.pack(fill="x", padx=40, pady=(28, 18))
    # Consistent, understated toolbar controls across accent themes.
    header_button_style = dict(fg=TEXT, activebackground=accent,
                               activeforeground='white', relief='flat', bd=0,
                               font=('Arial', 10), padx=14, pady=9,
                               cursor='hand2')
    tk.Button(top, text="← Back", command=on_back, bg=PANEL_ALT,
              **header_button_style).pack(side="left")
    if kind == 'games' and full_art:
        # The toolbar uses a crop of the fixed page image; buttons stay interactive.
        toolbar_art = {'image': None}
        toolbar_back = tk.Label(top, bd=0, highlightthickness=0)
        toolbar_back.place(x=0, y=0, relwidth=1, relheight=1)
        toolbar_back.lower()
        def paint_toolbar(event=None):
            if not top.winfo_exists(): return
            base = page_state.get('raster')
            if base is None: return
            w, h = max(1, top.winfo_width()), max(1, top.winfo_height())
            x = top.winfo_rootx() - page.winfo_rootx()
            y = top.winfo_rooty() - page.winfo_rooty()
            region = Image.new('RGB', (w, h), (22, 25, 31))
            bounds = (max(0,x), max(0,y), min(base.width,x+w), min(base.height,y+h))
            if bounds[2]>bounds[0] and bounds[3]>bounds[1]:
                region.paste(base.crop(bounds),(bounds[0]-x,bounds[1]-y))
            toolbar_art['image'] = ImageTk.PhotoImage(region)
            toolbar_back.configure(image=toolbar_art['image'])
            toolbar_back.lower()
        top.bind('<Configure>', paint_toolbar, add='+')
        page.bind('<Configure>', lambda e: top.after_idle(paint_toolbar)
                  if top.winfo_exists() else None, add='+')
    if kind == "games":
        def toggle_current():
            cursor.execute("UPDATE games SET in_progress = CASE WHEN in_progress = 1 "
                           "THEN 0 ELSE 1 END WHERE id = ?", (item_id,))
            connection.commit()
            on_back()

        def choose_executable():
            chosen = filedialog.askopenfilename(
                title="Select the game's executable",
                filetypes=[("Windows programs", "*.exe"), ("All files", "*.*")])
            if not chosen:
                return
            cursor.execute("UPDATE games SET executable = ? WHERE id = ?", (chosen, item_id))
            connection.commit()
            on_back()

        tk.Button(top, text="Toggle Playing", command=toggle_current,
                  bg=PANEL_ALT, **header_button_style).pack(side="right", padx=(6, 0))
        tk.Button(top, text="Set Game EXE", command=choose_executable,
                  bg=PANEL_ALT, **header_button_style).pack(side="right", padx=(6, 0))

    if kind in ("movies", "shows", "books"):
        from rich_details import open_rich_editor
        tk.Button(top, text="Extra Details", bg=PANEL_ALT, fg=TEXT,
                  relief="flat", padx=14, pady=8,
                  command=lambda: open_rich_editor(page, kind, item_id, accent,
                      lambda: show_detail(parent, kind, item_id, accent, on_back, on_edit))).pack(
                          side="right", padx=5)

    if on_edit:
        tk.Button(top, text="Edit", command=lambda: on_edit(item_id), bg=accent, fg="white",
                  activebackground=accent, activeforeground="white", relief="flat", bd=0,
                  font=('Arial', 10, 'bold'), padx=18, pady=9,
                  cursor="hand2").pack(side="right", padx=(6, 0))

    if kind == "books":
        from manual_timer import open_timer
        tk.Button(top, text="Reading Timer", bg=accent, fg="white",
                  relief="flat", command=lambda: open_timer(
                      parent, kind, item_id, title, accent)).pack(side="right", padx=5)

    if full_art:
        body = tk.Canvas(page_container, bg=BG, bd=0, highlightthickness=0)
        body.pack(fill='both', expand=True, padx=(40, 22), pady=(0,16))
        body_art = {'photo': None, 'size': None}
        def paint_body(event=None):
            if not body.winfo_exists(): return
            width,height = max(1,body.winfo_width()),max(1,body.winfo_height())
            if body_art['size'] == (width,height): return
            body_art['size']=(width,height)
            # This is a pixel-for-pixel crop of the ONE page background.
            # No independent resizing, tint or artwork placement.
            base = page_state.get('raster')
            if base is None: return
            x=body.winfo_rootx()-page.winfo_rootx()
            y=body.winfo_rooty()-page.winfo_rooty()
            tile=Image.new('RGB',(width,height),(14,17,22))
            bounds=(max(0,x),max(0,y),min(base.width,x+width),min(base.height,y+height))
            if bounds[2]>bounds[0] and bounds[3]>bounds[1]:
                tile.paste(base.crop(bounds),(bounds[0]-x,bounds[1]-y))
            body_art['photo']=ImageTk.PhotoImage(tile)
            body.delete('body-art')
            body.create_image(0,0,anchor='nw',image=body_art['photo'],tags='body-art')
            body.tag_lower('body-art')
        body.bind('<Configure>',paint_body)
    else:
        body = tk.Frame(page_container, bg=BG)
        body.pack(fill="both", expand=True, padx=40, pady=(0, 32))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

    left = tk.Frame(body, bg=PANEL, padx=12, pady=12, highlightthickness=1, highlightbackground=BORDER)
    if not full_art:
        left.grid(row=0, column=0, sticky="ns", padx=(0, 18))
    cover_holder = tk.Frame(left, width=252, height=352, bg=PANEL_ALT,
                            highlightthickness=1, highlightbackground=BORDER)
    cover_holder.pack(padx=0, pady=(0, 2))
    cover_holder.pack_propagate(False)
    # A quiet accent edge visually ties the cover to the rest of the detail UI.
    tk.Frame(left, bg=accent, height=3).pack(fill='x', pady=(2, 5))

    def render_cover():
        for child in cover_holder.winfo_children():
            child.destroy()
        cursor.execute(f"SELECT cover_path FROM {table} WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        path = _absolute_cover(row[0] if row else None)
        if path:
            try:
                if PIL_AVAILABLE:
                    image = Image.open(path).convert("RGB")
                    image = ImageOps.contain(image, (236, 336), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(image)
                else:
                    # Tk can display PNG/GIF without Pillow. Keep the app fully
                    # usable even on a plain Python installation.
                    photo = tk.PhotoImage(file=str(path))
                    scale = max(1, (photo.width() + 235) // 236, (photo.height() + 335) // 336)
                    if scale > 1:
                        photo = photo.subsample(scale, scale)
                label = tk.Label(cover_holder, image=photo, bg=PANEL_ALT)
                label.image = photo
                label.pack(expand=True)
                return
            except Exception:
                message = "COVER SAVED\nPREVIEW UNAVAILABLE" if not PIL_AVAILABLE else "COVER PREVIEW\nUNAVAILABLE"
                tk.Label(cover_holder, text=message, font=("Arial", 12, "bold"),
                         bg=PANEL_ALT, fg=MUTED, justify="center").pack(expand=True)
                return
        tk.Label(cover_holder, text="NO COVER\nART YET", font=("Arial", 15, "bold"),
                 bg=PANEL_ALT, fg=MUTED, justify="center").pack(expand=True)

    def choose_cover():
        from artwork_preferences import require_unlocked
        try:require_unlocked(kind,item_id,'cover_path')
        except ValueError as exc:
            messagebox.showwarning('Artwork',str(exc));return
        filename = filedialog.askopenfilename(
            parent=page.winfo_toplevel(), title="Choose Cover Art",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All files", "*.*")]
        )
        if not filename:
            return
        try:
            relative = _copy_cover(kind, item_id, title, filename)
            cursor.execute(f"UPDATE {table} SET cover_path = ? WHERE id = ?", (relative, item_id))
            connection.commit()
            render_cover()
        except Exception as exc:
            messagebox.showerror("Cover Art", f"The cover could not be saved.\n\n{exc}")

    def remove_cover():
        from artwork_preferences import require_unlocked
        try:require_unlocked(kind,item_id,'cover_path')
        except ValueError as exc:
            messagebox.showwarning('Artwork',str(exc));return
        cursor.execute(f"SELECT cover_path FROM {table} WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if not row or not row[0]:
            return
        if not messagebox.askyesno("Remove Cover", "Remove this cover art from the item?"):
            return
        old = _absolute_cover(row[0])
        cursor.execute(f"UPDATE {table} SET cover_path = NULL WHERE id = ?", (item_id,))
        connection.commit()
        if old:
            try:
                old.unlink()
            except OSError:
                pass
        render_cover()

    render_cover()
    from artwork_manager import open_manager
    tk.Button(top, text="Artwork Collection", command=lambda: open_manager(
        page, kind, item_id, title, accent,
        on_saved=lambda: show_detail(parent, kind, item_id, accent, on_back, on_edit)),
        bg=PANEL_ALT, **header_button_style).pack(side="right", padx=(6, 0))
    # Tk's activebackground is not a reliable hover treatment on Windows.
    # Explicit pointer events keep the header consistent across themes.
    for header_control in top.winfo_children():
        if not isinstance(header_control, tk.Button):
            continue
        normal_bg = header_control.cget('bg')
        hover_bg = PANEL_ALT if normal_bg == accent else accent
        header_control.bind(
            '<Enter>',
            lambda event, button=header_control, colour=hover_bg:
                button.configure(bg=colour, fg='white'),
            add='+')
        header_control.bind(
            '<Leave>',
            lambda event, button=header_control, colour=normal_bg:
                button.configure(bg=colour, fg='white' if colour == accent else TEXT),
            add='+')

    from metadata_finder import open_finder
    tk.Button(left, text="Find Art & Description Online",
              command=lambda: open_finder(page, kind, item_id, title, accent,
                  lambda: show_detail(parent, kind, item_id, accent, on_back, on_edit)),
              bg=accent, fg="white", relief="flat", padx=12, pady=10).pack(fill="x", pady=(4, 4))
    if kind != 'games':
        tk.Button(left, text="Choose / Change Cover", command=choose_cover, bg=accent, fg="white",
                  activebackground=accent, activeforeground="white", relief="flat", bd=0,
                  padx=14, pady=10, cursor="hand2").pack(fill="x", pady=(0, 4))
        if cover_path:
            tk.Button(left, text="Remove Cover", command=remove_cover, bg=PANEL_ALT, fg=TEXT,
                      activebackground=BORDER, activeforeground="white", relief="flat", bd=0,
                      padx=14, pady=10, cursor="hand2").pack(fill="x", pady=(0, 4))

    if kind == "games":
        def edit_game_metadata():
            from window_style import install as polish_dialog
            dialog = tk.Toplevel(page)
            dialog.title(f"Game Metadata - {title}")
            dialog.geometry("540x610")
            dialog.minsize(440, 520)
            dialog.configure(bg=PANEL)
            polish_dialog(dialog)
            dialog.transient(page.winfo_toplevel())
            tk.Label(dialog, text="GAME METADATA", bg=PANEL, fg=TEXT,
                     font=("Arial", 15, "bold")).pack(anchor="w", padx=20, pady=(16, 5))
            tk.Label(dialog, text="Saved locally. Leave unknown details blank; your personal tracking data is unchanged.",
                     bg=PANEL, fg=MUTED, wraplength=490, justify="left").pack(anchor="w", padx=20, pady=(0, 12))
            fields = (
                ("Release Date (YYYY-MM-DD)", "release_date"),
                ("Release Year", "release_year"),
                ("Genre", "genre"),
                ("Developer", "developer"),
                ("Publisher", "publisher"),
                ("Game Modes (e.g. Single-player)", "game_modes"),
                ("Age Rating (e.g. PEGI 18 or ESRB M)", "age_rating"),
            )
            body = tk.Frame(dialog, bg=PANEL)
            body.pack(fill="both", expand=True, padx=20)
            entries = {}
            for label, key in fields:
                tk.Label(body, text=label, bg=PANEL, fg=TEXT,
                         anchor="w").pack(fill="x", pady=(6, 2))
                entry = tk.Entry(body, bg=PANEL_ALT, fg=TEXT, insertbackground=TEXT,
                                 relief="flat", font=("Arial", 11))
                entry.insert(0, str(record.get(key) or ""))
                entry.pack(fill="x", ipady=5)
                entries[key] = entry
            original_values = {key: entry.get() for key, entry in entries.items()}
            close_prompt = {'window': None}
            def close_metadata(event=None):
                if all(entry.get() == original_values[key] for key, entry in entries.items()):
                    dialog.destroy()
                    return 'break'
                if close_prompt['window'] is not None:
                    close_prompt['window'].lift()
                    return 'break'
                confirmation = tk.Toplevel(dialog)
                close_prompt['window'] = confirmation
                confirmation.title('Unsaved Game Metadata')
                confirmation.geometry('420x200')
                confirmation.resizable(False, False)
                confirmation.configure(bg=PANEL)
                confirmation.transient(dialog)
                polish_dialog(confirmation)
                tk.Label(confirmation, text='Discard unsaved metadata?', bg=PANEL, fg=TEXT,
                         font=('Arial', 14, 'bold')).pack(anchor='w', padx=20, pady=(20, 10))
                tk.Label(confirmation, text='Your edits have not been saved. Keep editing or discard these changes.',
                         bg=PANEL, fg=MUTED, wraplength=380, justify='left').pack(anchor='w', padx=20)
                def keep_editing(event=None):
                    confirmation.destroy()
                    close_prompt['window'] = None
                    dialog.grab_set()
                    dialog.focus_set()
                    return 'break'
                def discard_changes():
                    confirmation.destroy()
                    dialog.destroy()
                actions = tk.Frame(confirmation, bg=PANEL)
                actions.pack(side='bottom', fill='x', padx=20, pady=20)
                keep_button = tk.Button(actions, text='Keep Editing', command=keep_editing,
                                        bg=accent, fg='white', relief='flat', padx=12, pady=8)
                keep_button.pack(side='right')
                tk.Button(actions, text='Discard Changes', command=discard_changes,
                          bg=PANEL_ALT, fg=TEXT, relief='flat', padx=12, pady=8).pack(side='right', padx=(0, 8))
                confirmation.protocol('WM_DELETE_WINDOW', keep_editing)
                confirmation.bind('<Escape>', keep_editing)
                confirmation.grab_set()
                keep_button.focus_set()
                return 'break'
            dialog.protocol('WM_DELETE_WINDOW', close_metadata)
            dialog.bind('<Escape>', close_metadata)
            tk.Label(dialog, text="UK ratings: enter PEGI 3, 7, 12, 16 or 18. Steam may supply US ESRB ratings instead.",
                     bg=PANEL, fg=MUTED, wraplength=490, justify='left').pack(anchor='w', padx=20, pady=(5, 0))
            error = tk.Label(dialog, text="", bg=PANEL, fg="#F19B9B")
            error.pack(pady=(4, 0))
            def save_metadata():
                values = {key: entry.get().strip() for key, entry in entries.items()}
                year = values['release_year']
                if year and (not year.isdigit() or not 1000 <= int(year) <= 9999):
                    error.configure(text="Release year must be four digits, or blank.")
                    return
                date = values['release_date']
                if date:
                    from datetime import date as date_type
                    try:
                        parsed = date_type.fromisoformat(date)
                        if len(date) != 10:
                            raise ValueError()
                    except ValueError:
                        error.configure(text="Release date must be YYYY-MM-DD, or blank.")
                        return
                    if year and int(year) != parsed.year:
                        error.configure(text="Release year and release date must agree.")
                        return
                    if not year:
                        values['release_year'] = str(parsed.year)
                values['release_year'] = int(values['release_year']) if values['release_year'] else None
                for key in values:
                    if key != 'release_year':
                        values[key] = values[key] or None
                keys = tuple(values)
                cursor.execute("UPDATE games SET " + ", ".join(f"{key}=?" for key in keys)
                               + " WHERE id=?", tuple(values[k] for k in keys) + (item_id,))
                connection.commit()
                dialog.destroy()
                show_detail(parent, kind, item_id, accent, on_back, on_edit)
            footer = tk.Frame(dialog, bg=PANEL)
            footer.pack(fill="x", padx=20, pady=(10, 18))
            tk.Button(footer, text="Cancel", command=close_metadata, bg=PANEL_ALT,
                      fg=TEXT, relief="flat", padx=18, pady=7).pack(side="right")
            tk.Button(footer, text="Save Metadata", command=save_metadata, bg=accent,
                      fg="white", relief="flat", padx=18, pady=7).pack(side="right", padx=(0, 8))
            dialog.grab_set()
        tk.Button(left, text="Edit Game Metadata", command=edit_game_metadata,
                  bg=PANEL_ALT, fg=TEXT, relief="flat", padx=14, pady=10,
                  cursor="hand2").pack(fill="x", pady=(0, 4))

    if kind == "games":
        def open_screenshot_manager():
            from game_gallery import GameGallery
            from window_style import install as polish_dialog
            win = tk.Toplevel(page)
            win.title(f"Screenshot Manager - {title}")
            win.geometry('840x490')
            win.configure(bg=PANEL)
            polish_dialog(win)
            tk.Label(win, text='SCREENSHOT MANAGER', bg=PANEL, fg=TEXT,
                     font=('Arial', 14, 'bold')).pack(anchor='w', padx=18, pady=(16, 8))
            tk.Label(win, text='Add, preview or remove screenshots. Changes appear when you close this window.',
                     bg=PANEL, fg=MUTED).pack(anchor='w', padx=18, pady=(0, 12))
            manager = GameGallery(win, item_id, accent, grid_view=True)
            manager.pack(fill='both', expand=True, padx=18, pady=8)
            def finish():
                win.destroy()
                if page.winfo_exists():
                    show_detail(parent, kind, item_id, accent, on_back, on_edit)
            tk.Button(win, text='Done', command=finish, bg=accent, fg='white',
                      relief='flat', padx=20, pady=8).pack(anchor='e', padx=18, pady=12)
            win.protocol('WM_DELETE_WINDOW', finish)
            win.transient(page.winfo_toplevel())
        tk.Button(left, text='Screenshot Manager', command=open_screenshot_manager,
                  bg=PANEL_ALT, fg=TEXT, relief='flat', padx=14, pady=10,
                  cursor='hand2').pack(fill='x', pady=(0, 4))

    if kind == "games":
        from manual_timer import clock
        root = parent.winfo_toplevel()
        timer = root.manual_timer
        tracker = getattr(root, 'game_tracker', None)
        timer_panel = tk.Frame(left, bg=PANEL_ALT, highlightthickness=1,
                               highlightbackground=BORDER, padx=10, pady=10)
        timer_panel.pack(fill='x', pady=(8, 0))
        tk.Label(timer_panel, text='PROGRESS TIMER', bg=PANEL_ALT, fg=TEXT,
                 font=('Arial', 11, 'bold')).pack(pady=(0, 10))
        timer_clock = tk.Label(timer_panel, text='00:00:00', bg=PANEL, fg=TEXT,
                               font=('Arial', 23), pady=8)
        timer_clock.pack(fill='x')
        controls = tk.Frame(timer_panel, bg=PANEL_ALT)
        controls.pack(fill='x', pady=(10, 0))
        def same():
            return timer.kind == 'games' and timer.item_id == item_id
        def start_pause():
            try:
                if same() and timer.since is not None:
                    timer.pause()
                elif same():
                    timer.resume()
                else:
                    if tracker and item_id in tracker.active:
                        raise ValueError('Automatic tracking is active. Stop the game first.')
                    timer.start('games', item_id, title)
            except ValueError as exc:
                messagebox.showwarning('Progress Timer', str(exc))
            update_timer()
        def add_time():
            if not same(): return
            try:
                from session_notes import ask_session_note
                note=ask_session_note(page,accent)
                if note is None:return
                seconds = timer.stop(tracker,note=note)
            except ValueError as exc:
                messagebox.showwarning('Progress Timer', str(exc))
                return
            messagebox.showinfo('Progress Timer', f'{clock(seconds)} added to playtime.')
            update_timer()
        def reset_time():
            if not same():
                update_timer()
                return
            # The themed messagebox does not accept tkinter's parent= keyword.
            # Confirmation must succeed before any unsaved session is discarded.
            if messagebox.askyesno('Reset Timer',
                    'Discard the unsaved timer session?'):
                timer.pause()
                timer.kind, timer.item_id, timer.title = None, None, ''
                timer.seconds, timer.since, timer.started_at = 0, None, None
            update_timer()
        # Equal-width controls, with only the primary action using the chosen
        # theme accent. No hard-coded blue and no tiny native-looking Reset.
        controls.columnconfigure(0, weight=1, uniform='timer_buttons')
        controls.columnconfigure(1, weight=1, uniform='timer_buttons')
        controls.columnconfigure(2, weight=1, uniform='timer_buttons')
        start_btn = tk.Button(controls, text='Start', bg=accent, fg='white',
                              activebackground=accent, activeforeground='white',
                              relief='flat', bd=0, padx=2, pady=7,
                              command=start_pause)
        start_btn.grid(row=0, column=0, sticky='ew', padx=(0, 4))
        add_btn = tk.Button(controls, text='Add', bg=PANEL, fg=TEXT,
                            activebackground=BORDER, activeforeground='white',
                            disabledforeground=MUTED, relief='flat', bd=0,
                            padx=2, pady=7, command=add_time)
        add_btn.grid(row=0, column=1, sticky='ew', padx=(2, 2))
        reset_btn = tk.Button(controls, text='Reset', bg=PANEL, fg=TEXT,
                              activebackground=BORDER, activeforeground='white',
                              relief='flat', bd=0, padx=2, pady=7,
                              command=reset_time)
        reset_btn.grid(row=0, column=2, sticky='ew', padx=(4, 0))
        def update_timer():
            if not timer_panel.winfo_exists(): return
            active = same()
            timer_clock.configure(text=clock(timer.elapsed() if active else 0))
            start_btn.configure(text=('Pause' if timer.since is not None else 'Resume')
                                if active else 'Start',
                                state='normal' if active or timer.kind is None else 'disabled')
            add_btn.configure(state='normal' if active else 'disabled')
        def tick():
            if not timer_panel.winfo_exists(): return
            update_timer()
            timer_panel.after(250, tick)
        tick()

    right_holder = tk.Frame(body, bg=BG, highlightthickness=0)
    if full_art:
        left_window = body.create_window(0,0,window=left,anchor='nw')
        right_window = body.create_window(0,0,window=right_holder,anchor='nw')
        def arrange_body(event=None):
            width,height=max(1,body.winfo_width()),max(1,body.winfo_height())
            left_width=max(290,left.winfo_reqwidth())
            body.coords(left_window,0,0)
            body.itemconfigure(left_window,width=left_width,height=height)
            body.coords(right_window,left_width+18,0)
            body.itemconfigure(right_window,width=max(100,width-left_width-18),height=height)
        body.bind('<Configure>',lambda event:(paint_body(event),arrange_body(event)),add='+')
        body.after_idle(arrange_body)
    else:
        right_holder.grid(row=0, column=1, sticky="nsew")
    if kind == 'games' and PIL_AVAILABLE:
        # Games do not use the old nested scroll panel at all.
        right = right_holder
        scroll = None
    else:
        scroll = tk.Canvas(right_holder, bg=PANEL, highlightthickness=0, bd=0)
        scroll.pack(side="left", fill="both", expand=True)
        scroll_bar = tk.Scrollbar(right_holder, orient="vertical", command=scroll.yview)
        scroll_bar.pack(side="right", fill="y")
        def update_standard_scrollbar(first, last):
            scroll_bar.set(first, last)
            if not scroll_bar.winfo_exists():
                return
            if float(first) <= 0.001 and float(last) >= 0.999:
                if scroll_bar.winfo_manager():
                    scroll_bar.pack_forget()
            elif not scroll_bar.winfo_manager():
                scroll_bar.pack(side="right", fill="y")
        scroll.configure(yscrollcommand=update_standard_scrollbar)
        right = tk.Frame(scroll, bg=PANEL, padx=8, pady=8)
        right_id = scroll.create_window((0, 0), window=right, anchor="nw")
        right.bind("<Configure>", lambda e: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda e: scroll.itemconfigure(right_id, width=e.width))
        wheel_tag = f"DetailWheel{id(scroll)}"
        def wheel(event):
            if getattr(event, "num", None) == 4:
                direction = -1
            elif getattr(event, "num", None) == 5:
                direction = 1
            else:
                delta = getattr(event, "delta", 0)
                if not delta:
                    return
                direction = -max(1, abs(delta) // 120) if delta > 0 else max(1, abs(delta) // 120)
            scroll.yview_scroll(direction, "units")
            if kind == 'games' and PIL_AVAILABLE and 'draw_cinematic' in locals():
                scroll.after_idle(lambda: draw_cinematic(force=True) if cinematic.winfo_exists() else None)
            return "break"
        scroll.bind_class(wheel_tag, "<MouseWheel>", wheel)
        scroll.bind_class(wheel_tag, "<Button-4>", wheel)
        scroll.bind_class(wheel_tag, "<Button-5>", wheel)
        def add_wheel_tags(widget):
            tags = widget.bindtags()
            if wheel_tag not in tags:
                widget.bindtags((tags[0], wheel_tag) + tags[1:])
            for child in widget.winfo_children():
                add_wheel_tags(child)
        right.after_idle(lambda: add_wheel_tags(right) if right.winfo_exists() else None)
        add_wheel_tags(scroll)

    if kind == 'games' and PIL_AVAILABLE:
        # The complete right-hand page is one artwork-backed canvas.  Unlike
        # separate Tk frames, its lower sections do not cover up the fan art.
        import textwrap
        import re
        logo_path, background_path = _game_art_paths(item_id)
        background_file = _absolute_cover(background_path)
        logo_file = _absolute_cover(logo_path)
        darkness = max(25, min(90, int(get_setting('game_background_darkness', '48'))))
        cinematic = tk.Canvas(right, bg=BG, bd=0, highlightthickness=0)
        cinematic.pack(side='left', fill='both', expand=True)
        def pin_background():
            if not cinematic.winfo_exists():
                return
            items = cinematic.find_withtag('fixed-background')
            if items:
                cinematic.coords(items[0], 0, cinematic.canvasy(0))
                cinematic.tag_lower(items[0])
        def scrollbar_move(*args):
            cinematic.yview(*args)
            pin_background()
        # Draw the track ourselves: the default Windows scrollbar ignores ttk colours.
        # A small canvas thumb is unobtrusive and has no OS-drawn white arrows.
        game_scrollbar = tk.Canvas(right, width=9, bg='#22272D',
                                   highlightthickness=0, bd=0, cursor='hand2')
        game_scrollbar.pack(side='right', fill='y', padx=(4, 0))
        bar_state = {'first': 0.0, 'last': 1.0, 'drag_start': None}
        def update_game_scrollbar_visibility():
            if not game_scrollbar.winfo_exists():
                return
            first, last = bar_state['first'], bar_state['last']
            needed = first > 0.001 or last < 0.999
            if needed and not game_scrollbar.winfo_manager():
                game_scrollbar.pack(side='right', fill='y', padx=(4, 0))
            elif not needed and game_scrollbar.winfo_manager():
                game_scrollbar.pack_forget()
        def paint_scrollbar():
            if not game_scrollbar.winfo_exists(): return
            h = max(1, game_scrollbar.winfo_height())
            game_scrollbar.delete('thumb')
            f, l = bar_state['first'], bar_state['last']
            if l-f >= 0.999: return
            top_y = int(f*h)
            bottom_y = max(top_y+26, int(l*h))
            game_scrollbar.create_rectangle(2, top_y, 7, min(h,bottom_y),
                                            fill=accent, outline='',
                                            tags='thumb')
        def scroll_changed(first, last):
            bar_state['first'], bar_state['last'] = float(first), float(last)
            update_game_scrollbar_visibility()
            paint_scrollbar()
            pin_background()
        def bar_press(event):
            h = max(1, game_scrollbar.winfo_height())
            f, l = bar_state['first'], bar_state['last']
            thumb_top, thumb_bottom = f*h, l*h
            if thumb_top <= event.y <= thumb_bottom:
                bar_state['drag_start'] = (event.y, f)
            else:
                cinematic.yview_moveto(max(0,min(1,event.y/h-(l-f)/2)))
                bar_state['drag_start'] = (event.y, cinematic.yview()[0])
            pin_background()
        def bar_drag(event):
            start_drag = bar_state['drag_start']
            if start_drag is None: return
            h = max(1,game_scrollbar.winfo_height())
            visible = bar_state['last']-bar_state['first']
            fraction = max(0,min(1-visible,start_drag[1]+(event.y-start_drag[0])/h))
            cinematic.yview_moveto(fraction)
            pin_background()
        game_scrollbar.bind('<Button-1>', bar_press)
        game_scrollbar.bind('<B1-Motion>', bar_drag)
        game_scrollbar.bind('<ButtonRelease-1>', lambda e: bar_state.update(drag_start=None))
        game_scrollbar.bind('<Configure>', lambda e: paint_scrollbar())
        cinematic.configure(yscrollcommand=scroll_changed)
        art_state = {'background': None, 'logo': None, 'width': 0}
        # Gallery images use natural aspect ratios, not two oversized fixed tiles.
        gallery_photos = []
        gallery_backdrop = {'photo': None, 'item': None}
        gallery_strip = tk.Canvas(cinematic, bg='#242A31', bd=0,
                                  highlightthickness=0, xscrollincrement=24)
        gallery_scroll = tk.Canvas(cinematic, height=12, bg='#22272D', bd=0,
                                   highlightthickness=0, cursor='hand2')
        gallery_bar = {'first': 0.0, 'last': 1.0, 'drag': None}
        def paint_gallery_bar():
            gallery_scroll.delete('thumb')
            w = max(1, gallery_scroll.winfo_width())
            first, last = gallery_bar['first'], gallery_bar['last']
            if last-first >= .999: return
            x0 = int(first*w)
            x1 = min(w, max(x0+28, int(last*w)))
            gallery_scroll.create_rectangle(x0, 3, x1, 9, fill=accent,
                                            outline='', tags='thumb')
        def gallery_xscroll(first, last):
            gallery_bar['first'], gallery_bar['last'] = float(first), float(last)
            # Keep the glass artwork anchored to the viewport while the
            # screenshot images move horizontally beneath the scrollbar.
            background_id = gallery_backdrop['item']
            if background_id is not None:
                gallery_strip.coords(background_id, gallery_strip.canvasx(0), 0)
            paint_gallery_bar()
        def gallery_press(event):
            w = max(1, gallery_scroll.winfo_width())
            first, last = gallery_bar['first'], gallery_bar['last']
            if first*w <= event.x <= last*w:
                gallery_bar['drag'] = (event.x, first)
            else:
                gallery_strip.xview_moveto(max(0, min(1, event.x/w-(last-first)/2)))
                gallery_bar['drag'] = (event.x, gallery_strip.xview()[0])
        def gallery_drag(event):
            if gallery_bar['drag'] is None: return
            x, start = gallery_bar['drag']
            visible = gallery_bar['last']-gallery_bar['first']
            fraction = max(0, min(1-visible, start+(event.x-x)/max(1,gallery_scroll.winfo_width())))
            gallery_strip.xview_moveto(fraction)
        gallery_scroll.bind('<Button-1>', gallery_press)
        gallery_scroll.bind('<B1-Motion>', gallery_drag)
        gallery_scroll.bind('<ButtonRelease-1>', lambda e: gallery_bar.update(drag=None))
        gallery_scroll.bind('<Configure>', lambda e: paint_gallery_bar())
        gallery_strip.configure(xscrollcommand=gallery_xscroll)
        gallery_window = cinematic.create_window(30, 0, anchor='nw',
                                                  window=gallery_strip)
        gallery_scroll_window = cinematic.create_window(30, 0, anchor='nw',
                                                         window=gallery_scroll)
        def horizontal_wheel(event):
            delta = getattr(event, 'delta', 0)
            steps = -3 if delta > 0 else 3
            if getattr(event, 'num', None) == 4: steps = -3
            if getattr(event, 'num', None) == 5: steps = 3
            gallery_strip.xview_scroll(steps, 'units')
            return 'break'
        gallery_strip.bind('<MouseWheel>', horizontal_wheel)
        gallery_strip.bind('<Button-4>', horizontal_wheel)
        gallery_strip.bind('<Button-5>', horizontal_wheel)
        def preview_screenshot(path):
            from window_style import install as polish_dialog
            win = tk.Toplevel(page)
            win.title(path.name)
            win.configure(bg='#101216')
            win.geometry('1000x650')
            polish_dialog(win)
            with Image.open(path) as im:
                picture = ImageOps.contain(im.convert('RGB'), (950, 580))
            photo = ImageTk.PhotoImage(picture)
            label = tk.Label(win, image=photo, bg='#101216')
            label.image = photo
            label.pack(fill='both', expand=True, padx=15, pady=15)
            tk.Button(win, text='Close', command=win.destroy, bg=PANEL_ALT,
                      fg=TEXT, relief='flat').pack(pady=(0, 10))

        def draw_cinematic(event=None, force=False):
            if not cinematic.winfo_exists():
                return
            width = max(460, cinematic.winfo_width())
            if art_state['width'] == width and event is not None and not force:
                return
            art_state['width'] = width
            cinematic.delete('paint')
            cinematic.delete('fixed-background')
            # Determine page height from wrapped text rather than truncating it.
            description = record.get('description') or 'No description saved yet.'
            chars_per_line = max(38, (width - 80) // 7)
            paragraphs = description.splitlines() or ['']
            lines = []
            for paragraph in paragraphs:
                lines.extend(textwrap.wrap(paragraph, width=chars_per_line,
                                           break_long_words=True) or [''])
            description_height = max(76, len(lines) * 19 + 36)
            cursor.execute('SELECT id, image_path FROM game_screenshots WHERE game_id=? ORDER BY id',
                           (item_id,))
            screenshot_items = cursor.fetchall()
            gallery_height = 84 if not screenshot_items else 255
            # Two separate panels: factual game metadata and personal activity.
            # On narrow windows they stack instead of squeezing together.
            split_panels = width >= 720
            facts_top = 194
            facts_step = 76
            activity_step = 68 if split_panels else 62
            def panel_rows(entries, cols):
                return (len(entries) + cols - 1) // cols
            if split_panels:
                info_bottom = max(345,
                                  facts_top + panel_rows(game_facts, 2) * facts_step + 20,
                                  facts_top + panel_rows(activity_fields, 2) * activity_step + 20)
            else:
                activity_y = facts_top + panel_rows(game_facts, 1) * facts_step + 14
                info_bottom = max(450, activity_y + 43
                                  + panel_rows(activity_fields, 1) * activity_step + 20)
            # Consistent 12px clear gap between the actual panel rectangles.
            # Their title/content offsets differ, so calculate from the edges.
            panel_gap = 12
            gallery_y = info_bottom + panel_gap + 12
            description_y = gallery_y + gallery_height + 4 + panel_gap
            sessions_y = description_y + description_height + 32 + panel_gap
            # Each session takes its own line; reserve enough space for all six.
            cursor.execute('SELECT COUNT(*) FROM (SELECT id FROM game_sessions '
                           'WHERE game_id=? ORDER BY id DESC LIMIT 6)', (item_id,))
            session_count = cursor.fetchone()[0]
            sessions_height = max(86, 48 + session_count * 26)
            height = max(sessions_y + sessions_height + 18, cinematic.winfo_height())
            cinematic.configure(scrollregion=(0, 0, width, height))
            # The single fixed page image is the source of truth.  This canvas
            # has a viewport-sized backing sample, never a document-sized image.
            viewport_height = max(1, cinematic.winfo_height())
            viewport = Image.new('RGB', (width, viewport_height), (14, 17, 22))
            base = page_state.get('raster')
            if base is not None:
                x = cinematic.winfo_rootx() - page.winfo_rootx()
                y = cinematic.winfo_rooty() - page.winfo_rooty()
                crop = (max(0, x), max(0, y),
                        min(base.width, x + width),
                        min(base.height, y + viewport_height))
                if crop[2] > crop[0] and crop[3] > crop[1]:
                    viewport.paste(base.crop(crop),
                                   (crop[0] - x, crop[1] - y))
            art_state['background'] = ImageTk.PhotoImage(viewport)
            cinematic.create_image(0, cinematic.canvasy(0), anchor='nw',
                                   image=art_state['background'],
                                   tags='fixed-background')
            if split_panels:
                half = width // 2
                for x0, x1 in ((18, half-5), (half+5, width-18)):
                    cinematic.create_rectangle(x0, 133, x1, info_bottom,
                                               fill='#242A31', stipple='gray50',
                                               outline='', tags='paint')
            else:
                cinematic.create_rectangle(18, 133, width-18, info_bottom,
                                           fill='#242A31', stipple='gray50',
                                           outline='', tags='paint')
            # Same glass overlay as the information, description and sessions.
            # Restore the original translucent gallery panel (matching Description).
            cinematic.create_rectangle(18, gallery_y-12, width-18,
                                       gallery_y+gallery_height-8,
                                       fill='#242A31', stipple='gray50',
                                       outline='', tags='paint')
            cinematic.create_rectangle(18, description_y-12, width-18,
                                       description_y+description_height+20,
                                       fill='#242A31', stipple='gray50',
                                       outline='', tags='paint')
            cinematic.create_rectangle(18, sessions_y-12, width-18, sessions_y+sessions_height,
                                       fill='#242A31', stipple='gray50',
                                       outline='', tags='paint')
            # Keep the logo within its own 118px-tall header area, above the
            # information panels. Preserve its native proportions and align it
            # consistently with the content margins at every window width.
            header_left = 34
            header_mid_y = 70
            if logo_file:
                try:
                    with Image.open(logo_file) as im:
                        logo = im.convert('RGBA')
                        logo.thumbnail((max(120, min(width - 80, 540)), 90),
                                       Image.Resampling.LANCZOS)
                    art_state['logo'] = ImageTk.PhotoImage(logo)
                    cinematic.create_image(header_left, header_mid_y,
                                           image=art_state['logo'], anchor='w', tags='paint')
                except (OSError, ValueError):
                    art_state['logo'] = None
            if art_state['logo'] is None:
                cinematic.create_text(header_left, header_mid_y, text=title,
                                      anchor='w', width=max(120, width-80),
                                      font=('Arial', 26, 'bold'), fill=TEXT, tags='paint')
            def draw_panel_heading(x0, x1, y, text):
                cinematic.create_rectangle(x0+17, y, x0+21, y+18,
                                           fill=accent, outline='', tags='paint')
                cinematic.create_text(x0+33, y, text=text, anchor='nw',
                                      fill='#FFFFFF', font=('Arial', 11, 'bold'), tags='paint')
                cinematic.create_line(x0+17, y+27, x1-17, y+27,
                                      fill='#515963', width=1, tags='paint')

            def draw_panel_fields(entries, x0, x1, top, cols, step):
                usable = max(80, x1-x0-34)
                column_width = usable // cols
                for index, (label, value) in enumerate(entries):
                    row, col = divmod(index, cols)
                    x = x0 + 17 + col * column_width
                    y = top + row * step
                    cinematic.create_text(x, y, text=label.upper(), anchor='nw',
                                          font=('Arial', 9, 'bold'), fill='#C7CAD2', tags='paint')
                    display_value = str(value)
                    if label.upper() == 'RECORDED PLAYTIME':
                        try:
                            hh, mm, ss = [int(part) for part in display_value.split(':')]
                            display_value = f'{hh}h {mm}m' + (f' {ss}s' if ss and hh == 0 else '')
                        except (ValueError, AttributeError):
                            pass
                    if label.upper() == 'AGE RATING':
                        rating = display_value.strip()
                        # Never guess a UK PEGI value from an American ESRB rating.
                        match = re.fullmatch(r'(?:PEGI\s*)?(3|7|12|16|18)', rating, re.I)
                        if match:
                            number = match.group(1)
                            # Compact PEGI-inspired badge: fits the metadata row
                            # and stays inside the translucent information panel.
                            # This is an in-app indicator, not an official logo asset.
                            rating_colours = {
                                '3': '#78B83D', '7': '#78B83D',
                                '12': '#E9A72C', '16': '#DF8530', '18': '#D83439',
                            }
                            bx, by = x, y + 19
                            # A little more room for the rating numeral and footer;
                            # official PEGI artwork remains a separate future upgrade.
                            badge_width, number_height, footer_height = 42, 30, 13
                            cinematic.create_rectangle(
                                bx, by, bx+badge_width, by+number_height,
                                fill=rating_colours[number], outline='#E6E6E6',
                                width=1, tags='paint')
                            cinematic.create_text(
                                bx+badge_width//2, by+number_height//2,
                                text=number, anchor='center', fill='#FFFFFF',
                                font=('Arial', 20, 'bold'), tags='paint')
                            cinematic.create_rectangle(
                                bx, by+number_height,
                                bx+badge_width, by+number_height+footer_height,
                                fill='#101010', outline='#101010', tags='paint')
                            cinematic.create_text(
                                bx+badge_width//2, by+number_height+footer_height//2,
                                text='PEGI', anchor='center', fill='#FFFFFF',
                                font=('Arial', 8, 'bold'), tags='paint')
                        else:
                            if rating.upper() in ('M', 'T', 'E', 'E10+', 'AO', 'RP'):
                                display_value = 'ESRB ' + rating.upper()
                            cinematic.create_text(x, y+19, text=display_value, anchor='nw',
                                width=max(55, column_width-12), font=('Arial', 12, 'bold'),
                                fill='#FFFFFF', tags='paint')
                    else:
                        cinematic.create_text(x, y+19, text=display_value, anchor='nw',
                                               width=max(55, column_width-12),
                                               font=('Arial', 12, 'bold'), fill='#FFFFFF', tags='paint')

            if split_panels:
                half = width // 2
                draw_panel_heading(18, half-5, 151, 'GAME INFORMATION')
                draw_panel_heading(half+5, width-18, 151, 'MY GAME ACTIVITY')
                draw_panel_fields(game_facts, 18, half-5, facts_top, 2, facts_step)
                draw_panel_fields(activity_fields, half+5, width-18, facts_top, 2, activity_step)
            else:
                draw_panel_heading(18, width-18, 151, 'GAME INFORMATION')
                draw_panel_fields(game_facts, 18, width-18, facts_top, 1, facts_step)
                draw_panel_heading(18, width-18, activity_y, 'MY GAME ACTIVITY')
                draw_panel_fields(activity_fields, 18, width-18,
                                  activity_y+43, 1, activity_step)
            # Consistent cinematic section accents and subtle separators.
            for section_top in (gallery_y+3, description_y, sessions_y):
                cinematic.create_rectangle(28, section_top, 32, section_top+17,
                                           fill=accent, outline='', tags='paint')
                cinematic.create_line(28, section_top+25, width-28, section_top+25,
                                      fill='#515963', width=1, tags='paint')
            cinematic.create_text(42, gallery_y+3, text='GAMEPLAY SCREENSHOTS',
                                  anchor='nw', fill='#FFFFFF',
                                  font=('Arial', 11, 'bold'), tags='paint')
            gallery_photos.clear()
            gallery_strip.delete('all')
            gallery_backdrop['item'] = None
            gallery_width = max(100, width - 60)
            gallery_backdrop['photo'] = None
            if not screenshot_items:
                cinematic.itemconfigure(gallery_window, state='hidden')
                cinematic.itemconfigure(gallery_scroll_window, state='hidden')
                cinematic.create_text(28, gallery_y+38,
                                      text='No screenshots yet. Use Screenshot Manager beside the cover.',
                                      anchor='nw', fill=MUTED,
                                      font=('Arial', 10), tags='paint')
            else:
                cinematic.itemconfigure(gallery_window, state='normal',
                                        width=gallery_width, height=175)
                cinematic.coords(gallery_window, 30, gallery_y+36)
                cinematic.itemconfigure(gallery_scroll_window, state='normal',
                                        width=gallery_width, height=12)
                cinematic.coords(gallery_scroll_window, 30, gallery_y+219)
                shot_x = 6
                for shot_id, relative in screenshot_items:
                    path = PROJECT_ROOT / relative
                    if not path.is_file():
                        continue
                    try:
                        with Image.open(path) as im:
                            picture = im.convert('RGB')
                            picture.thumbnail((360, 164), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(picture)
                        gallery_photos.append(photo)
                        image_id = gallery_strip.create_image(shot_x, 5, image=photo,
                                                               anchor='nw')
                        frame_id = gallery_strip.create_rectangle(
                            shot_x, 5, shot_x+picture.width, 5+picture.height,
                            outline='#515963', width=1)
                        gallery_strip.tag_bind(image_id, '<Button-1>',
                                               lambda e, p=path: preview_screenshot(p))
                        gallery_strip.tag_bind(frame_id, '<Button-1>',
                                               lambda e, p=path: preview_screenshot(p))
                        shot_x += picture.width + 12
                    except (OSError, ValueError):
                        continue
                # Precompose the translucent charcoal panel over the artwork.
                # Tk child canvases cannot themselves be transparent.
                strip_width = max(gallery_width, shot_x)
                top = int(gallery_y + 36 - cinematic.canvasy(0))
                sample = Image.new('RGB', (gallery_width, 175), '#242A31')
                if 0 <= top < viewport.height:
                    right = min(viewport.width, 30 + gallery_width)
                    bottom = min(viewport.height, top + 175)
                    if right > 30 and bottom > top:
                        sample.paste(viewport.crop((30, top, right, bottom)), (0, 0))
                glass = Image.blend(sample, Image.new('RGB', sample.size, '#242A31'), 0.65)
                # Only one viewport-sized backdrop is needed. Repositioning
                # this canvas item in gallery_xscroll makes it visually fixed.
                gallery_backdrop['photo'] = ImageTk.PhotoImage(glass)
                background_id = gallery_strip.create_image(
                    gallery_strip.canvasx(0), 0,
                    image=gallery_backdrop['photo'], anchor='nw')
                gallery_backdrop['item'] = background_id
                gallery_strip.tag_lower(background_id)
                gallery_strip.configure(scrollregion=(0, 0, strip_width, 175))
                gallery_strip.coords(background_id, gallery_strip.canvasx(0), 0)
                if shot_x <= gallery_width:
                    cinematic.itemconfigure(gallery_scroll_window, state='hidden')
            cinematic.create_text(42, description_y, text='DESCRIPTION', anchor='nw',
                                  fill='#FFFFFF', font=('Arial', 11, 'bold'), tags='paint')
            cinematic.create_text(28, description_y+35, text='\n'.join(lines),
                                  anchor='nw', width=width-60, fill=TEXT,
                                  font=('Arial', 10), tags='paint')
            cinematic.create_text(42, sessions_y, text='RECENT PLAY SESSIONS',
                                  anchor='nw', fill='#FFFFFF', font=('Arial', 11, 'bold'), tags='paint')
            cinematic.create_text(width-32, sessions_y+3, text='DURATION',
                                  anchor='ne', fill=MUTED, font=('Arial', 9, 'bold'), tags='paint')
            cursor.execute('SELECT started_at, duration_seconds FROM game_sessions '
                           'WHERE game_id=? ORDER BY id DESC LIMIT 6', (item_id,))
            sessions = cursor.fetchall()
            # Compact session count, without adding another divider or changing layout.
            cinematic.create_text(231, sessions_y+3,
                                  text=f'({len(sessions)} shown)',
                                  anchor='nw', fill=MUTED,
                                  font=('Arial', 9), tags='paint')
            if not sessions:
                cinematic.create_text(28, sessions_y+40,
                                      text='No completed automatic sessions yet.',
                                      anchor='nw', fill=MUTED, tags='paint')
            for index, (started_at, seconds) in enumerate(sessions):
                # Format dates for display only; preserve stored session timestamps.
                try:
                    from datetime import datetime
                    from datetime import timezone
                    parsed = datetime.fromisoformat(str(started_at).replace('Z', '+00:00'))
                    # Session timestamps are stored in UTC. Display them using the
                    # PC's configured local time zone (including DST adjustments).
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    local_time = parsed.astimezone()
                    # Windows may return verbose names such as 'GMT Summer Time'.
                    # Keep the PC-derived conversion; only abbreviate the label.
                    zone_name = local_time.strftime('%Z')
                    if zone_name in ('GMT Summer Time', 'British Summer Time'):
                        zone_label = 'BST'
                    elif zone_name in ('GMT Standard Time', 'Greenwich Mean Time'):
                        zone_label = 'GMT'
                    elif len(zone_name) <= 5:
                        zone_label = zone_name
                    else:
                        offset = local_time.strftime('%z')
                        zone_label = ('UTC' + offset[:3] + ':' + offset[3:]) if offset else ''
                    date_text = local_time.strftime('%d %b %Y  %H:%M')
                    if zone_label:
                        date_text += ' ' + zone_label
                except (TypeError, ValueError, OverflowError):
                    date_text = str(started_at or 'Unknown date')[:16].replace('T', ' ')
                elapsed = max(0, int(seconds or 0))
                duration = f'{elapsed//3600:02d}:{elapsed//60%60:02d}:{elapsed%60:02d}'
                row_y = sessions_y + 40 + index * 26
                cinematic.create_text(28, row_y, text=date_text,
                                      anchor='nw', fill=TEXT, font=('Arial', 10), tags='paint')
                cinematic.create_text(width-32, row_y, text=duration,
                                      anchor='ne', fill=TEXT, font=('Arial', 10), tags='paint')
            pin_background()
            cinematic.tag_raise(gallery_window)
            cinematic.tag_raise(gallery_scroll_window)
        def game_wheel(event):
            if getattr(event, 'num', None) == 4:
                steps = -1
            elif getattr(event, 'num', None) == 5:
                steps = 1
            else:
                delta = getattr(event, 'delta', 0)
                steps = -1 if delta > 0 else 1
            cinematic.yview_scroll(steps * 3, 'units')
            pin_background()
            return 'break'
        cinematic.bind('<MouseWheel>', game_wheel)
        cinematic.bind('<Button-4>', game_wheel)
        cinematic.bind('<Button-5>', game_wheel)
        cinematic.bind('<Configure>', lambda e: draw_cinematic(force=True))
        def initial_draw():
            draw_cinematic(force=True)
            cinematic.yview_moveto(0)
            pin_background()
        cinematic.after_idle(initial_draw)
        page.bind('<Configure>', lambda e: cinematic.after_idle(
            lambda: draw_cinematic(force=True) if cinematic.winfo_exists() else None), add='+')
    else:
        tk.Label(right, text=title, font=('Arial',23,'bold'),bg=PANEL,fg=TEXT,
                 wraplength=560,justify='left').pack(anchor='w')
        tk.Label(right,text=subtitle,font=('Arial',10),bg=PANEL,fg=accent).pack(anchor='w',pady=(3,13))
        info=tk.Frame(right,bg=PANEL_ALT,padx=10,pady=8)
        info.pack(fill='x')
        for index,(label,value) in enumerate(fields):
            row,column=divmod(index,2)
            cell=tk.Frame(info,bg=PANEL_ALT,padx=8,pady=5)
            cell.grid(row=row,column=column,sticky='ew')
            tk.Label(cell,text=label.upper(),bg=PANEL_ALT,fg=MUTED,
                     font=('Arial',8,'bold')).pack(anchor='w')
            tk.Label(cell,text=str(value),bg=PANEL_ALT,fg=TEXT,
                     font=('Arial',10,'bold')).pack(anchor='w',pady=(2,0))
        info.grid_columnconfigure(0,weight=1)
        info.grid_columnconfigure(1,weight=1)

    if kind == "games" and not PIL_AVAILABLE:
            from game_gallery import GameGallery
            gallery = GameGallery(right, item_id, accent)
            gallery.pack(fill="x", pady=(18, 0))
    if kind != "games" or not PIL_AVAILABLE:
        tk.Label(right, text="DESCRIPTION", bg=PANEL, fg=accent,
                 font=("Arial", 10, "bold")).pack(anchor="w", pady=(18, 6))
        tk.Label(right, text=record.get("description") or "No description saved yet.",
                 bg=PANEL, fg=TEXT, wraplength=1050, justify="left",
                 anchor="w").pack(anchor="w", fill="x")

    if kind != "games" and record.get("notes"):
        tk.Label(right, text="PERSONAL NOTES", bg=PANEL, fg=accent,
                 font=("Arial", 10, "bold")).pack(anchor="w", pady=(18, 6))
        tk.Label(right, text=record["notes"], bg=PANEL, fg=TEXT,
                 wraplength=520, justify="left").pack(anchor="w", fill="x")

    if kind == "games" and not PIL_AVAILABLE:
        tk.Label(right, text="RECENT PLAY SESSIONS", font=("Arial", 10, "bold"),
                 bg=PANEL, fg=accent).pack(anchor="w", pady=(18, 6))
        cursor.execute("SELECT started_at, duration_seconds FROM game_sessions "
                       "WHERE game_id = ? ORDER BY id DESC LIMIT 6", (item_id,))
        sessions = cursor.fetchall()
        if not sessions:
            tk.Label(right, text="No completed automatic sessions yet.",
                     bg=PANEL, fg=MUTED).pack(anchor="w")
        for started_at, seconds in sessions:
            try:
                from datetime import datetime, timezone
                dt = datetime.fromisoformat(str(started_at).replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt = dt.astimezone()
                zone = dt.strftime('%Z')
                if zone in ('GMT Summer Time', 'British Summer Time'):
                    zone = 'BST'
                elif zone in ('GMT Standard Time', 'Greenwich Mean Time'):
                    zone = 'GMT'
                elif len(zone) > 5:
                    offset = dt.strftime('%z')
                    zone = ('UTC' + offset[:3] + ':' + offset[3:]) if offset else ''
                date_text = dt.strftime('%d %b %Y  %H:%M') + (' ' + zone if zone else '')
            except (ValueError, TypeError, OverflowError):
                date_text = str(started_at or 'Unknown date')[:16].replace('T', ' ')
            duration = f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
            tk.Label(right, text=f"{date_text}     {duration}",
                     bg=PANEL, fg=TEXT, font=("Arial", 10)).pack(anchor="w", pady=2)
