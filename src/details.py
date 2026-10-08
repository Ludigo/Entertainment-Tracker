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
    _game_art_setup()
    with connection:
        connection.execute('INSERT OR IGNORE INTO game_detail_art(game_id) VALUES(?)', (game_id,))
        connection.execute('UPDATE game_detail_art SET '+role+'=? WHERE game_id=?', (path, game_id))


def _choose_game_art(parent, game_id, role, refresh):
    from tkinter import ttk
    from artwork_manager import store
    dialog = tk.Toplevel(parent)
    dialog.title('Choose game logo' if role == 'logo_path' else 'Choose background fan art')
    dialog.configure(bg=BG)
    dialog.geometry('620x390')
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()
    tk.Label(dialog, text='Choose saved artwork or add an image', bg=BG, fg=TEXT,
             font=('Arial', 14, 'bold')).pack(anchor='w', padx=18, pady=(18, 8))
    rows = connection.execute('SELECT image_path,width,height FROM artwork_library '
                              'WHERE category=? AND item_id=? ORDER BY id DESC',
                              ('games', game_id)).fetchall()
    choices = [f'{w} × {h}   •   {Path(path).name}' for path,w,h in rows]
    selected = tk.StringVar(value=choices[0] if choices else '')
    box = ttk.Combobox(dialog, values=choices, textvariable=selected, state='readonly', width=64)
    box.pack(fill='x', padx=18, pady=12)
    status = tk.Label(dialog, text='Choose an existing image or import one from your PC.',
                      bg=BG, fg=MUTED, wraplength=570)
    status.pack(anchor='w', padx=18)
    def save(path):
        _set_game_art(game_id, role, path)
        dialog.destroy()
        refresh()
    def use_saved():
        if selected.get() in choices:
            save(rows[choices.index(selected.get())][0])
        else:
            status.configure(text='No image selected.')
    def import_file():
        filename = filedialog.askopenfilename(parent=dialog, filetypes=[('Images','*.png *.jpg *.jpeg *.webp'),('All files','*.*')])
        if not filename: return
        try:
            if not PIL_AVAILABLE: raise RuntimeError('Pillow is required for image imports')
            import io
            with Image.open(filename) as img:
                img.verify()
            with Image.open(filename) as img:
                w,h = img.size
                fmt = img.format
            if fmt not in ('JPEG','PNG','WEBP') or w*h > 60_000_000:
                raise ValueError('Please choose a JPEG, PNG or WebP image under 60 megapixels')
            ext = {'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[fmt]
            path = store('games', game_id, Path(filename).read_bytes(), w, h, ext, 'Local file', set_cover=False)
            save(path)
        except Exception as exc:
            messagebox.showerror('Artwork', str(exc))
    actions = tk.Frame(dialog, bg=BG)
    actions.pack(fill='x', padx=18, pady=22)
    for text, fn in [('Use selected',use_saved),('Add from PC',import_file),('Remove artwork',lambda:save(None))]:
        tk.Button(actions, text=text, command=fn, bg=PANEL_ALT, fg=TEXT,
                  relief='flat', padx=12, pady=9).pack(side='left', padx=(0,8))
    tk.Button(actions,text='Cancel',command=dialog.destroy,bg=PANEL_ALT,fg=TEXT,
              relief='flat',padx=12,pady=9).pack(side='right')

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
        fields = [("Platform", item[2]), ("Recorded Playtime", format_time(item[3])),
                  ("Currently Playing", "Yes" if record.get("in_progress") else "No"),
                  ("Price Paid", "Not recorded" if record.get("price_paid") is None
                   else f"£{record['price_paid']:,.2f}"),
                  ("Completed", "Yes" if record.get("completed") else "No"),
                  ("In Backlog", "Yes" if record.get("backlog") else "No"),
                  ("Started Playing", "Yes" if record.get("started") else "No")]
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
        top.pack(fill="x", padx=(40, 58), pady=(12, 10))
    else:
        top.pack(fill="x", padx=40, pady=(28, 18))
    tk.Button(top, text="← Back", command=on_back, bg=PANEL_ALT, fg=TEXT,
              activebackground=accent, activeforeground="white", relief="flat", bd=0,
              padx=12, pady=7, cursor="hand2").pack(side="left")
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
                  bg=PANEL_ALT, fg=TEXT, relief="flat", padx=12, pady=7).pack(side="right", padx=3)
        tk.Button(top, text="Set Game EXE", command=choose_executable,
                  bg=PANEL_ALT, fg=TEXT, relief="flat", padx=12, pady=7).pack(side="right", padx=3)

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
                  padx=18, pady=8, cursor="hand2").pack(side="right")

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
        bg=PANEL_ALT, fg=TEXT, relief="flat", padx=12, pady=7).pack(side="right", padx=3)
    from metadata_finder import open_finder
    tk.Button(left, text="Find Art & Description Online",
              command=lambda: open_finder(page, kind, item_id, title, accent,
                  lambda: show_detail(parent, kind, item_id, accent, on_back, on_edit)),
              bg=accent, fg="white", relief="flat", padx=12, pady=8).pack(fill="x", pady=(8, 3))
    tk.Button(left, text="Choose / Change Cover", command=choose_cover, bg=accent, fg="white",
              activebackground=accent, activeforeground="white", relief="flat", bd=0,
              padx=14, pady=8, cursor="hand2").pack(fill="x", pady=(3, 3))
    if cover_path:
        tk.Button(left, text="Remove Cover", command=remove_cover, bg=PANEL_ALT, fg=TEXT,
                  activebackground=BORDER, activeforeground="white", relief="flat", bd=0,
                  padx=14, pady=8, cursor="hand2").pack(fill="x")

    if kind == "games":
        from manual_timer import clock
        root = parent.winfo_toplevel()
        timer = root.manual_timer
        tracker = getattr(root, 'game_tracker', None)
        timer_panel = tk.Frame(left, bg='#111111', highlightthickness=1,
                               highlightbackground=BORDER, padx=10, pady=10)
        timer_panel.pack(fill='x', pady=(12, 0))
        tk.Label(timer_panel, text='Progress Timer', bg='#111111', fg=TEXT,
                 font=('Arial', 12, 'bold')).pack(pady=(0, 8))
        timer_clock = tk.Label(timer_panel, text='00:00:00', bg='#242424', fg=TEXT,
                               font=('Arial', 23), pady=8)
        timer_clock.pack(fill='x')
        controls = tk.Frame(timer_panel, bg='#111111')
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
                messagebox.showwarning('Progress Timer', str(exc), parent=root)
            update_timer()
        def add_time():
            if not same(): return
            try:
                seconds = timer.stop(tracker)
            except ValueError as exc:
                messagebox.showwarning('Progress Timer', str(exc), parent=root)
                return
            messagebox.showinfo('Progress Timer', f'{clock(seconds)} added to playtime.', parent=root)
            update_timer()
        def reset_time():
            if same() and messagebox.askyesno('Reset Timer',
                    'Discard the unsaved timer session?', parent=root):
                timer.pause()
                timer.kind, timer.item_id, timer.title = None, None, ''
                timer.seconds, timer.since, timer.started_at = 0, None, None
            update_timer()
        start_btn = tk.Button(controls, text='Start', bg=accent, fg='white',
                              relief='flat', padx=12, command=start_pause)
        start_btn.pack(side='left', padx=(0, 5))
        add_btn = tk.Button(controls, text='Add', bg='#287EB7', fg='white',
                            disabledforeground='#C9D6E6', activeforeground='white',
                            relief='flat', padx=12, command=add_time)
        add_btn.pack(side='left')
        tk.Button(controls, text='Reset', bg='#242424', fg=TEXT, relief='solid',
                  bd=1, padx=9, command=reset_time).pack(side='right')
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
        scroll.configure(yscrollcommand=scroll_bar.set)
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
        def paint_scrollbar():
            if not game_scrollbar.winfo_exists(): return
            h = max(1, game_scrollbar.winfo_height())
            game_scrollbar.delete('thumb')
            f, l = bar_state['first'], bar_state['last']
            if l-f >= 0.999: return
            top_y = int(f*h)
            bottom_y = max(top_y+26, int(l*h))
            game_scrollbar.create_rectangle(2, top_y, 7, min(h,bottom_y),
                                            fill='#808B9A', outline='',
                                            tags='thumb')
        def scroll_changed(first, last):
            bar_state['first'], bar_state['last'] = float(first), float(last)
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
        from game_gallery import GameGallery
        # Keep the screenshot manager for its database/import/remove actions,
        # but render the gallery directly on the cinematic canvas. Tk Frames
        # are opaque and were covering the fixed fan-art background.
        gallery = GameGallery(cinematic, item_id, accent)
        gallery.place_forget()
        gallery_photos = []
        def gallery_action(action):
            action()
            if cinematic.winfo_exists():
                draw_cinematic(force=True)
        gallery_add = tk.Button(cinematic, text='+ Add',
                                bg=PANEL_ALT, fg=TEXT, activeforeground=TEXT,
                                relief='flat', padx=9,
                                command=lambda: gallery_action(gallery.add))
        gallery_add_window = cinematic.create_window(0, 0, window=gallery_add,
                                                     anchor='ne')

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
            description_height = max(70, len(lines) * 19 + 30)
            cursor.execute('SELECT id, image_path FROM game_screenshots WHERE game_id=? ORDER BY id',
                           (item_id,))
            gallery.items = cursor.fetchall()
            gallery.offset = min(gallery.offset, max(0, len(gallery.items)-2))
            gallery_height = 84 if not gallery.items else 235
            gallery_y = 421
            description_y = gallery_y + gallery_height + 12
            sessions_y = description_y + description_height + 22
            height = max(sessions_y + 95, cinematic.winfo_height())
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
            cinematic.create_rectangle(18, 133, width-18, 405,
                                       fill='#242A31', stipple='gray50',
                                       outline='#62666D', tags='paint')
            # Same glass overlay as the information, description and sessions.
            cinematic.create_rectangle(18, gallery_y-10, width-18,
                                       gallery_y+gallery_height-8,
                                       fill='#242A31', stipple='gray50',
                                       outline='', tags='paint')
            cinematic.create_rectangle(18, description_y-12, width-18,
                                       description_y+description_height+20,
                                       fill='#242A31', stipple='gray50',
                                       outline='', tags='paint')
            cinematic.create_rectangle(18, sessions_y-12, width-18, sessions_y+75,
                                       fill='#242A31', stipple='gray50',
                                       outline='', tags='paint')
            if logo_file:
                try:
                    with Image.open(logo_file) as im:
                        logo = im.convert('RGBA')
                        logo.thumbnail((min(width-60, 570), 110), Image.Resampling.LANCZOS)
                    art_state['logo'] = ImageTk.PhotoImage(logo)
                    cinematic.create_image(26, 12, image=art_state['logo'], anchor='nw', tags='paint')
                except (OSError, ValueError):
                    art_state['logo'] = None
            if art_state['logo'] is None:
                cinematic.create_text(27, 37, text=title, anchor='nw', width=width-54,
                                      font=('Arial', 28, 'bold'), fill=TEXT, tags='paint')
            for index, (label, value) in enumerate(fields):
                row, col = divmod(index, 2)
                x = 37 if col == 0 else width // 2 + 12
                y = 155 + row * 60
                cinematic.create_text(x, y, text=label.upper(), anchor='nw',
                                      font=('Arial', 9, 'bold'), fill='#C7CAD2', tags='paint')
                display_value = str(value)
                if label.upper() == 'RECORDED PLAYTIME':
                    try:
                        hh, mm, ss = [int(part) for part in display_value.split(':')]
                        display_value = f'{hh}h {mm}m' + (f' {ss}s' if ss and hh == 0 else '')
                    except (ValueError, AttributeError):
                        pass
                cinematic.create_text(x, y+19, text=display_value, anchor='nw',
                                      width=width//2-55, font=('Arial', 12, 'bold'),
                                      fill='#FFFFFF', tags='paint')
            cinematic.create_text(28, gallery_y+3, text='GAMEPLAY SCREENSHOTS',
                                  anchor='nw', fill=accent,
                                  font=('Arial', 11, 'bold'), tags='paint')
            cinematic.coords(gallery_add_window, width-30, gallery_y+1)
            gallery_photos.clear()
            if not gallery.items:
                cinematic.create_text(28, gallery_y+38,
                                      text='No screenshots yet. Add gameplay images from your PC.',
                                      anchor='nw', fill=MUTED,
                                      font=('Arial', 10), tags='paint')
            else:
                visible = gallery.items[gallery.offset:gallery.offset+2]
                for i, (shot_id, relative) in enumerate(visible):
                    x = 30 + i*((width-65)//2)
                    path = PROJECT_ROOT / relative
                    if path.is_file():
                        try:
                            with Image.open(path) as im:
                                shot = ImageOps.contain(im.convert('RGB'),
                                            (min(280,(width-100)//2),145))
                            photo = ImageTk.PhotoImage(shot)
                            gallery_photos.append(photo)
                            image_item = cinematic.create_image(
                                x, gallery_y+35, anchor='nw', image=photo,
                                tags='paint')
                            cinematic.tag_bind(image_item, '<Button-1>',
                                               lambda e, p=path: gallery.preview(p))
                        except (OSError, ValueError):
                            pass
                    remove_button = tk.Button(cinematic, text='Remove',
                                              bg=PANEL_ALT, fg=TEXT, relief='flat',
                                              command=lambda sid=shot_id:
                                              gallery_action(lambda: gallery.remove(sid)))
                    cinematic.create_window(x, gallery_y+187, anchor='nw',
                                            window=remove_button, tags='paint')
                if gallery.offset:
                    prev = tk.Button(cinematic, text='‹', bg=PANEL_ALT,
                                     fg=TEXT, relief='flat',
                                     command=lambda: gallery_action(lambda: gallery.move(-1)))
                    cinematic.create_window(30, gallery_y+215, anchor='nw',
                                            window=prev, tags='paint')
                if gallery.offset+2 < len(gallery.items):
                    next_btn = tk.Button(cinematic, text='›', bg=PANEL_ALT,
                                         fg=TEXT, relief='flat',
                                         command=lambda: gallery_action(lambda: gallery.move(1)))
                    cinematic.create_window(width-45, gallery_y+215, anchor='nw',
                                            window=next_btn, tags='paint')
            cinematic.create_text(28, description_y, text='DESCRIPTION', anchor='nw',
                                  fill=accent, font=('Arial', 11, 'bold'), tags='paint')
            cinematic.create_text(28, description_y+29, text='\n'.join(lines),
                                  anchor='nw', width=width-60, fill=TEXT,
                                  font=('Arial', 10), tags='paint')
            cinematic.create_text(28, sessions_y, text='RECENT PLAY SESSIONS',
                                  anchor='nw', fill=accent, font=('Arial', 11, 'bold'), tags='paint')
            cursor.execute('SELECT started_at, duration_seconds FROM game_sessions '
                           'WHERE game_id=? ORDER BY id DESC LIMIT 6', (item_id,))
            sessions = cursor.fetchall()
            if not sessions:
                cinematic.create_text(28, sessions_y+35,
                                      text='No completed automatic sessions yet.',
                                      anchor='nw', fill=MUTED, tags='paint')
            for index, (started_at, seconds) in enumerate(sessions):
                date_text = started_at[:16].replace('T', ' ') + ' UTC'
                duration = f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}'
                cinematic.create_text(28, sessions_y+35+index*26,
                                      text=f'{date_text}     {duration}',
                                      anchor='nw', fill=TEXT, font=('Arial', 10), tags='paint')
            pin_background()
            cinematic.tag_raise(gallery_add_window)
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
            date_text = started_at[:16].replace("T", " ") + " UTC"
            duration = f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
            tk.Label(right, text=f"{date_text}     {duration}",
                     bg=PANEL, fg=TEXT, font=("Arial", 10)).pack(anchor="w", pady=2)
