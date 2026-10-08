"""Main entry point: apply queued restores before opening SQLite."""
from restore_manager import apply_pending_restore

try:
    restored_safety = apply_pending_restore()
    restore_startup_error = None
except Exception as exc:
    restored_safety = None
    restore_startup_error = f"{type(exc).__name__}: {exc}"

import tkinter as tk
import sqlite3

from database import setup_database, close_database, get_setting, set_setting, cursor, connection
from backup_manager import create_backup, automatic_backup_if_due
from offline_audit import audit_collection, format_audit
from restore_manager import validate_backup, schedule_restore
from games import open_games
from movies import open_movies
from shows import open_shows
from books import open_books
from details import show_detail
from tracker import GameTracker
from manual_timer import ManualTimer
from session_history import show_all_session_history
from modal import ModalFrame, app_messagebox as messagebox
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED, BORDER, DEFAULT_ACCENT, apply_theme, configure_ttk

setup_database()
try:
    automatic_backup_if_due(connection)
    backup_startup_error = None
except Exception as exc:
    backup_startup_error = str(exc)
accent = get_setting("accent_color", DEFAULT_ACCENT)

window = tk.Tk()
window.title("Entertainment Tracker")
window.geometry("1200x700")
window.minsize(900, 560)
window.configure(bg=BG)
configure_ttk(window, accent)
tracker = GameTracker(window)
window.game_tracker = tracker
window.manual_timer = ManualTimer(window)

# Responsive shell: fixed, dependable navigation rail + content that receives
# every extra pixel when the user resizes/maximises the application.
window.grid_rowconfigure(0, weight=1)
window.grid_columnconfigure(0, weight=0, minsize=240)
window.grid_columnconfigure(1, weight=1)

sidebar = tk.Frame(window, width=240, bg=PANEL)
sidebar.grid(row=0, column=0, sticky="nsew")
sidebar.grid_propagate(False)

content = tk.Frame(window, bg=BG)
content.grid(row=0, column=1, sticky="nsew")

nav_buttons = {}
current_page = "Dashboard"


def clear_content():
    content.grid_remove()
    for widget in content.winfo_children():
        widget.destroy()


def reveal_content():
    if content.winfo_exists():
        content.grid(row=0, column=1, sticky="nsew")


def refresh_nav():
    for name, button in nav_buttons.items():
        selected = name == current_page
        button.configure(
            bg=accent if selected else PANEL,
            fg="white" if selected else TEXT,
            activebackground=accent,
            activeforeground="white"
        )


def recolour_visible_accent(widget, old_colour, new_colour):
    """Update existing accent-coloured widgets without rebuilding the current page.

    Only options whose current value is the old accent are changed. This avoids
    clobbering deliberate backgrounds, text colours, or custom button colours.
    """
    if getattr(widget, "_et_fixed_preset", False):
        return
    for option in ("bg", "fg", "activebackground", "activeforeground",
                   "highlightbackground", "highlightcolor", "selectbackground"):
        try:
            if str(widget.cget(option)).casefold() == old_colour.casefold():
                widget.configure(**{option: new_colour})
        except (tk.TclError, AttributeError):
            pass
    for child in widget.winfo_children():
        recolour_visible_accent(child, old_colour, new_colour)


def finish_page():
    apply_theme(content, accent)
    refresh_nav()
    reveal_content()


def _session_clock(seconds):
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"




def section_heading(parent, eyebrow, title, subtitle):
    """Reusable heading treatment matching the four library toolbars."""
    head = tk.Frame(parent, bg=BG)
    accent_line = tk.Frame(head, bg=accent, width=4)
    accent_line.pack(side="left", fill="y", padx=(0, 16))
    copy = tk.Frame(head, bg=BG)
    copy.pack(side="left", fill="x", expand=True)
    tk.Label(copy, text=eyebrow.upper(), bg=BG, fg=accent,
             font=("Arial", 9, "bold")).pack(anchor="w", pady=(0, 5))
    tk.Label(copy, text=title, bg=BG, fg=TEXT,
             font=("Arial", 27, "bold")).pack(anchor="w")
    tk.Label(copy, text=subtitle, bg=BG, fg=MUTED,
             font=("Arial", 10)).pack(anchor="w", pady=(5, 0))
    return head


def polished_panel(parent, **kwargs):
    return tk.Frame(parent, bg=PANEL, highlightthickness=1,
                    highlightbackground=BORDER, **kwargs)

def show_dashboard():
    global current_page
    current_page = "Dashboard"
    clear_content()

    def hours_text(hours):
        total_seconds = max(0, round((hours or 0) * 3600))
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        return f"{h:,}h {m:02d}m"

    def compact_time(hours):
        hours = max(0, hours or 0)
        if hours >= 8760:
            return f"{hours / 8760:.2f} years"
        if hours >= 24:
            return f"{hours / 24:,.1f} days"
        return hours_text(hours)

    # Dashboard calculations deliberately mirror the meaning of the existing
    # fields rather than inventing data the library does not track yet.
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(playtime), 0) FROM games")
    game_count, game_hours = cursor.fetchone()

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(runtime * watch_count), 0) FROM movies")
    movie_count, movie_hours = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(
            runtime * watch_count +
            CASE WHEN episode_count > 0 THEN runtime * episode_reached / episode_count ELSE 0 END
        ), 0)
        FROM shows
    """)
    show_count, show_hours = cursor.fetchone()

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(reading_time), 0) FROM books")
    book_count, book_hours = cursor.fetchone()

    total_hours = game_hours + movie_hours + show_hours + book_hours

    page = tk.Frame(content, bg=BG)
    page.pack(fill="both", expand=True)
    page.grid_columnconfigure(0, weight=1)
    page.grid_rowconfigure(3, weight=1)

    header = section_heading(page, "YOUR OVERVIEW", "Dashboard",
                             "Your entertainment library at a glance")
    header.grid(row=0, column=0, sticky="ew", padx=36, pady=(28, 0))

    hero = polished_panel(page, padx=26, pady=19)
    hero.grid(row=1, column=0, sticky="ew", padx=40, pady=(24, 14))
    tk.Label(hero, text="YOUR TIME INVESTED", font=("Arial", 9, "bold"),
             bg=PANEL, fg=accent).pack(anchor="w")
    tk.Label(hero, text=hours_text(total_hours), font=("Arial", 30, "bold"),
             bg=PANEL, fg=TEXT).pack(anchor="w", pady=(4, 0))
    tk.Label(hero, text=f"{total_hours / 24:,.2f} days  •  {total_hours / 8760:.3f} years",
             font=("Arial", 10), bg=PANEL, fg=MUTED).pack(anchor="w", pady=(2, 0))

    cards = tk.Frame(page, bg=BG)
    cards.grid(row=2, column=0, sticky="ew", padx=40)
    for col in range(4):
        cards.grid_columnconfigure(col, weight=1, uniform="dashboard_cards")

    def category_card(parent, column, title, count, hours, command):
        card = polished_panel(parent, cursor="hand2")
        card.grid(row=0, column=column, sticky="nsew",
                  padx=(0 if column == 0 else 6, 0 if column == 3 else 6))
        inner = tk.Frame(card, bg=PANEL, cursor="hand2")
        inner.pack(fill="both", expand=True, padx=18, pady=16)
        title_label = tk.Label(inner, text=title, font=("Arial", 14, "bold"),
                               bg=PANEL, fg=TEXT, cursor="hand2")
        title_label.pack(anchor="w")
        time_label = tk.Label(inner, text=hours_text(hours), font=("Arial", 17, "bold"),
                              bg=PANEL, fg=accent, cursor="hand2")
        time_label.pack(anchor="w", pady=(10, 1))
        count_label = tk.Label(inner, text=f"{count:,} {'item' if count == 1 else 'items'}  •  {compact_time(hours)}",
                               font=("Arial", 9), bg=PANEL, fg=MUTED, cursor="hand2")
        count_label.pack(anchor="w")
        for widget in (card, inner, title_label, time_label, count_label):
            widget.bind("<Button-1>", lambda _e, c=command: c())
        return card

    category_card(cards, 0, "Games", game_count, game_hours, show_games)
    category_card(cards, 1, "Movies", movie_count, movie_hours, show_movies)
    category_card(cards, 2, "Shows", show_count, show_hours, show_shows)
    category_card(cards, 3, "Books", book_count, book_hours, show_books)

    lower = tk.Frame(page, bg=BG)
    lower.grid(row=3, column=0, sticky="nsew", padx=40, pady=(14, 32))
    lower.grid_columnconfigure(0, weight=3)
    lower.grid_columnconfigure(1, weight=2)
    lower.grid_rowconfigure(0, weight=1)

    current_panel = polished_panel(lower, padx=22, pady=18)
    current_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
    tk.Label(current_panel, text="In Progress", font=("Arial", 16, "bold"),
             bg=PANEL, fg=TEXT).pack(anchor="w")
    tk.Label(current_panel, text="Things you are currently playing, watching or reading",
             font=("Arial", 9), bg=PANEL, fg=MUTED).pack(anchor="w", pady=(2, 12))

    cursor.execute("""
        SELECT name, season, episode_reached, episode_count
        FROM shows WHERE in_progress = 1
        ORDER BY name COLLATE NOCASE, season LIMIT 4
    """)
    active_shows = cursor.fetchall()
    cursor.execute("""
        SELECT name, page_count, reading_time
        FROM books WHERE in_progress = 1
        ORDER BY name COLLATE NOCASE LIMIT 4
    """)
    active_books = cursor.fetchall()

    cursor.execute("SELECT name, platform FROM games WHERE in_progress = 1 "
                   "ORDER BY name COLLATE NOCASE LIMIT 4")
    active_games = cursor.fetchall()

    live_games = tracker.live_games()
    live_ids = {game[0] for game in live_games}
    active_count = len(active_games) + len(active_shows) + len(active_books) + len(live_games)
    if not active_count:
        tk.Label(current_panel, text="Nothing marked as in progress yet.",
                 font=("Arial", 11), bg=PANEL, fg=MUTED).pack(anchor="w", pady=10)
    else:
        live_labels = []
        for game_id, name, platform, elapsed in live_games:
            row = tk.Frame(current_panel, bg=PANEL_ALT, cursor="hand2")
            row.pack(fill="x", pady=3)
            tk.Label(row, text="● " + name, font=("Arial", 10, "bold"),
                     bg=PANEL_ALT, fg=accent).pack(side="left", padx=12, pady=9)
            timer_label = tk.Label(row, text="LIVE  " + _session_clock(elapsed),
                                   font=("Arial", 10, "bold"), bg=PANEL_ALT, fg=TEXT)
            timer_label.pack(side="right", padx=12)
            live_labels.append((game_id, timer_label))
            for widget in (row,) + tuple(row.winfo_children()):
                widget.bind("<Button-1>", lambda _e, gid=game_id: _show_media_detail(
                    "games", gid, show_games, show_games))
        def refresh_live():
            if not current_panel.winfo_exists():
                return
            for game_id, label in live_labels:
                if not label.winfo_exists():
                    continue
                seconds = tracker.elapsed(game_id)
                label.configure(text="LIVE  " + _session_clock(seconds) if seconds is not None
                                else "Session finished")
            current_panel.after(1000, refresh_live)
        refresh_live()
        for name, platform in active_games:
            row = tk.Frame(current_panel, bg=PANEL_ALT, cursor="hand2")
            row.pack(fill="x", pady=3)
            tk.Label(row, text=name, font=("Arial", 10, "bold"),
                     bg=PANEL_ALT, fg=TEXT).pack(side="left", padx=12, pady=9)
            tk.Label(row, text=f"Game  •  {platform}", font=("Arial", 9),
                     bg=PANEL_ALT, fg=MUTED).pack(side="right", padx=12)
            for widget in (row,) + tuple(row.winfo_children()):
                widget.bind("<Button-1>", lambda _e: show_games())
        for name, season, reached, episodes in active_shows:
            row = tk.Frame(current_panel, bg=PANEL_ALT, cursor="hand2")
            row.pack(fill="x", pady=3)
            tk.Label(row, text=name, font=("Arial", 10, "bold"), bg=PANEL_ALT,
                     fg=TEXT, cursor="hand2").pack(side="left", padx=12, pady=9)
            detail = f"Season {season}  •  Episode {reached}/{episodes}"
            tk.Label(row, text=detail, font=("Arial", 9), bg=PANEL_ALT,
                     fg=MUTED, cursor="hand2").pack(side="right", padx=12)
            for widget in (row,) + tuple(row.winfo_children()):
                widget.bind("<Button-1>", lambda _e: show_shows())
        for name, pages, reading_time in active_books:
            row = tk.Frame(current_panel, bg=PANEL_ALT, cursor="hand2")
            row.pack(fill="x", pady=3)
            tk.Label(row, text=name, font=("Arial", 10, "bold"), bg=PANEL_ALT,
                     fg=TEXT, cursor="hand2").pack(side="left", padx=12, pady=9)
            detail = f"Book  •  {pages:,} pages" if pages else f"Book  •  {hours_text(reading_time)} read"
            tk.Label(row, text=detail, font=("Arial", 9), bg=PANEL_ALT,
                     fg=MUTED, cursor="hand2").pack(side="right", padx=12)
            for widget in (row,) + tuple(row.winfo_children()):
                widget.bind("<Button-1>", lambda _e: show_books())

    stats_panel = polished_panel(lower, padx=22, pady=18)
    stats_panel.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
    tk.Label(stats_panel, text="Highlights", font=("Arial", 16, "bold"),
             bg=PANEL, fg=TEXT).pack(anchor="w")
    tk.Label(stats_panel, text="A few useful library standouts",
             font=("Arial", 9), bg=PANEL, fg=MUTED).pack(anchor="w", pady=(2, 12))

    cursor.execute("SELECT name, playtime FROM games ORDER BY playtime DESC LIMIT 1")
    top_game = cursor.fetchone()
    cursor.execute("SELECT name, runtime, watch_count FROM movies ORDER BY watch_count DESC, runtime * watch_count DESC LIMIT 1")
    top_movie = cursor.fetchone()
    cursor.execute("SELECT name, season, watch_count FROM shows ORDER BY watch_count DESC, runtime * watch_count DESC LIMIT 1")
    top_show = cursor.fetchone()
    cursor.execute("SELECT name, page_count FROM books ORDER BY page_count DESC LIMIT 1")
    longest_book = cursor.fetchone()

    highlights = []
    if top_game:
        highlights.append(("Most played game", top_game[0], hours_text(top_game[1])))
    if top_movie:
        highlights.append(("Most watched movie", top_movie[0], f"{top_movie[2]} watches"))
    if top_show:
        highlights.append(("Most watched season", f"{top_show[0]} — S{top_show[1]}", f"{top_show[2]} watches"))
    if longest_book and longest_book[1]:
        highlights.append(("Longest book", longest_book[0], f"{longest_book[1]:,} pages"))

    if not highlights:
        tk.Label(stats_panel, text="Add some library data and your highlights will appear here.",
                 font=("Arial", 10), bg=PANEL, fg=MUTED, wraplength=300,
                 justify="left").pack(anchor="w", pady=10)
    else:
        for label, value, detail in highlights[:4]:
            item = tk.Frame(stats_panel, bg=PANEL)
            item.pack(fill="x", pady=(2, 9))
            tk.Label(item, text=label.upper(), font=("Arial", 8, "bold"),
                     bg=PANEL, fg=MUTED).pack(anchor="w")
            tk.Label(item, text=value, font=("Arial", 10, "bold"),
                     bg=PANEL, fg=TEXT, wraplength=300, justify="left").pack(anchor="w")
            tk.Label(item, text=detail, font=("Arial", 9),
                     bg=PANEL, fg=accent).pack(anchor="w")

    finish_page()


def _show_media_detail(kind, item_id, back_command, edit_command):
    global current_page
    current_page = kind.title()
    clear_content()
    show_detail(content, kind, item_id, accent, back_command, edit_command)
    refresh_nav()
    reveal_content()


def show_games(initial_edit_id=None):
    global current_page
    current_page = "Games"
    clear_content()
    open_games(
        content,
        on_open_detail=lambda item_id: _show_media_detail("games", item_id, show_games, show_games),
        initial_edit_id=initial_edit_id
    )
    finish_page()


def show_history():
    global current_page
    current_page = "History"
    clear_content()
    show_all_session_history(content, accent)
    refresh_nav()
    reveal_content()


def show_movies(initial_edit_id=None):
    global current_page
    current_page = "Movies"
    clear_content()
    open_movies(
        content,
        on_open_detail=lambda item_id: _show_media_detail("movies", item_id, show_movies, show_movies),
        initial_edit_id=initial_edit_id
    )
    finish_page()


def show_shows(initial_edit_id=None):
    global current_page
    current_page = "Shows"
    clear_content()
    open_shows(
        content,
        on_open_detail=lambda item_id: _show_media_detail("shows", item_id, show_shows, show_shows),
        initial_edit_id=initial_edit_id
    )
    finish_page()


def show_books(initial_edit_id=None):
    global current_page
    current_page = "Books"
    clear_content()
    open_books(
        content,
        on_open_detail=lambda item_id: _show_media_detail("books", item_id, show_books, show_books),
        initial_edit_id=initial_edit_id
    )
    finish_page()


def open_custom_colour_picker(on_choose):
    """Themed in-app RGB/hex colour picker; no native white Windows dialog."""
    modal = ModalFrame(window)
    modal.geometry("520x500")
    modal.title("Choose Accent Colour")

    tk.Label(modal, text="Custom Accent Colour", font=("Arial", 20, "bold"),
             bg=PANEL, fg=TEXT).pack(anchor="w", pady=(8, 3))
    tk.Label(modal, text="Use the RGB sliders or type a hex colour.",
             font=("Arial", 10), bg=PANEL, fg=MUTED).pack(anchor="w", pady=(0, 16))

    preview = tk.Frame(modal, bg=accent, height=70, highlightthickness=1,
                       highlightbackground=BORDER)
    preview.pack(fill="x", pady=(0, 18))
    preview.pack_propagate(False)
    preview_text = tk.Label(preview, text=accent.upper(), bg=accent, fg="white",
                            font=("Arial", 14, "bold"))
    preview_text.pack(expand=True)

    try:
        start_r, start_g, start_b = tuple(int(accent.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    except (ValueError, TypeError):
        start_r, start_g, start_b = (178, 58, 72)

    values = {"R": tk.IntVar(value=start_r), "G": tk.IntVar(value=start_g), "B": tk.IntVar(value=start_b)}
    hex_var = tk.StringVar(value=accent.upper())
    syncing = {"active": False}

    controls = tk.Frame(modal, bg=PANEL)
    controls.pack(fill="x")

    def text_colour(r, g, b):
        # Readable preview text on both pale and dark custom colours.
        return "#17191d" if (0.299*r + 0.587*g + 0.114*b) > 165 else "white"

    def set_preview(colour, r, g, b):
        preview.configure(bg=colour)
        preview_text.configure(bg=colour, fg=text_colour(r, g, b), text=colour)

    def sliders_changed(_value=None):
        if syncing["active"]:
            return
        r, g, b = values["R"].get(), values["G"].get(), values["B"].get()
        colour = f"#{r:02X}{g:02X}{b:02X}"
        syncing["active"] = True
        hex_var.set(colour)
        syncing["active"] = False
        set_preview(colour, r, g, b)

    for label, variable in values.items():
        row = tk.Frame(controls, bg=PANEL)
        row.pack(fill="x", pady=4)
        tk.Label(row, text=label, width=2, anchor="w", bg=PANEL, fg=TEXT,
                 font=("Arial", 10, "bold")).pack(side="left")
        scale = tk.Scale(row, from_=0, to=255, orient="horizontal", variable=variable,
                         command=sliders_changed, showvalue=False, resolution=1,
                         bg=PANEL, fg=TEXT, troughcolor=PANEL_ALT,
                         activebackground=accent, highlightthickness=0, bd=0)
        scale.pack(side="left", fill="x", expand=True, padx=(8, 10))
        tk.Label(row, textvariable=variable, width=4, anchor="e", bg=PANEL,
                 fg=MUTED).pack(side="right")

    hex_row = tk.Frame(modal, bg=PANEL)
    hex_row.pack(fill="x", pady=(16, 0))
    tk.Label(hex_row, text="Hex", bg=PANEL, fg=TEXT,
             font=("Arial", 10, "bold")).pack(side="left")
    hex_entry = tk.Entry(hex_row, textvariable=hex_var, font=("Arial", 11), width=12,
                         bg=PANEL_ALT, fg=TEXT, insertbackground=TEXT,
                         selectbackground=accent, selectforeground="white",
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=accent)
    hex_entry.pack(side="left", padx=(12, 0), ipady=6)
    status = tk.Label(hex_row, text="", bg=PANEL, fg=MUTED, font=("Arial", 9))
    status.pack(side="left", padx=10)

    def hex_changed(*_args):
        if syncing["active"]:
            return
        value = hex_var.get().strip().upper()
        if not value.startswith("#"):
            value = "#" + value
        if len(value) != 7:
            status.configure(text="Enter 6 hex digits")
            return
        try:
            r, g, b = tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
        except ValueError:
            status.configure(text="Invalid hex colour")
            return
        status.configure(text="")
        syncing["active"] = True
        for variable, number in zip(values.values(), (r, g, b)):
            variable.set(number)
        hex_var.set(value)
        syncing["active"] = False
        set_preview(value, r, g, b)

    hex_var.trace_add("write", hex_changed)

    actions = tk.Frame(modal, bg=PANEL)
    actions.pack(side="bottom", fill="x", pady=(18, 2))

    def apply_custom():
        value = hex_var.get().strip().upper()
        if not value.startswith("#"):
            value = "#" + value
        try:
            if len(value) != 7:
                raise ValueError
            int(value[1:], 16)
        except ValueError:
            status.configure(text="Enter a valid #RRGGBB colour")
            return
        on_choose(value)
        modal.destroy()

    tk.Button(actions, text="Apply Colour", command=apply_custom,
              bg=accent, fg="white", activebackground=accent,
              activeforeground="white", relief="flat", bd=0,
              padx=18, pady=8, cursor="hand2").pack(side="right")
    tk.Button(actions, text="Cancel", command=modal.destroy,
              bg=PANEL_ALT, fg=TEXT, activebackground=BORDER,
              activeforeground="white", relief="flat", bd=0,
              padx=18, pady=8, cursor="hand2").pack(side="right", padx=(0, 8))

    # The picker has its own footer Cancel, so hide the generic top-right one.
    modal.cancel_button.place_forget()
    hex_entry.focus_set()


def show_settings():
    global current_page
    current_page = "Settings"
    clear_content()
    # Keep the page heading outside the scrollable region.
    fixed_header = tk.Frame(content, bg=BG)
    fixed_header.pack(fill="x")
    section_heading(fixed_header, "PERSONALISE YOUR TRACKER", "Settings",
                    "Appearance, imports and application preferences").pack(
                        fill="x", padx=24, pady=(12, 8))
    # Settings can grow beyond the window height; keep the whole page scrollable.
    scroll_host = tk.Frame(content, bg=BG)
    scroll_host.pack(fill="both", expand=True)
    canvas = tk.Canvas(scroll_host, bg=BG, highlightthickness=0, bd=0)
    # Draw the scrollbar ourselves: native Windows scrollbar colours ignore the app theme.
    rail = tk.Canvas(scroll_host, width=10, bg=BG, highlightthickness=0,
                     bd=0, cursor="hand2")
    canvas.pack(side="left", fill="both", expand=True)
    page = tk.Frame(canvas, bg=BG)
    page_window = canvas.create_window((0, 0), window=page, anchor="nw")
    dragging = {"y": None}

    def paint_scrollbar(first=None, last=None):
        if not rail.winfo_exists() or not canvas.winfo_exists():
            return
        first, last = canvas.yview()
        if page.winfo_reqheight() <= canvas.winfo_height() or (first <= 0.0001 and last >= 0.9999):
            if rail.winfo_manager():
                rail.pack_forget()
            return
        if not rail.winfo_manager():
            rail.pack(side="right", fill="y")
        rail.delete("all")
        height = max(1, rail.winfo_height())
        thumb_top = round(first * height)
        thumb_bottom = max(thumb_top + 24, round(last * height))
        thumb_bottom = min(height, thumb_bottom)
        rail.create_rectangle(3, 0, 7, height, fill=PANEL_ALT, outline="")
        rail.create_rectangle(1, thumb_top, 9, thumb_bottom,
                              fill=accent, outline="", tags="thumb")

    canvas.configure(yscrollcommand=paint_scrollbar, yscrollincrement=24)

    def update_scroll_region(event=None):
        canvas.configure(scrollregion=(0, 0, canvas.winfo_width(),
                         max(canvas.winfo_height(), page.winfo_reqheight())))
        if page.winfo_reqheight() <= canvas.winfo_height():
            canvas.yview_moveto(0)
        canvas.after_idle(paint_scrollbar)

    def fit_page_width(event):
        canvas.itemconfigure(page_window, width=event.width)
        canvas.after_idle(paint_scrollbar)

    page.bind("<Configure>", update_scroll_region)
    canvas.bind("<Configure>", fit_page_width)
    rail.bind("<Configure>", lambda event: paint_scrollbar())

    def rail_click(event):
        first, last = canvas.yview()
        span = last - first
        if span >= 1:
            return
        canvas.yview_moveto(max(0, min(1 - span,
                            event.y / max(1, rail.winfo_height()) - span / 2)))
        dragging["y"] = event.y

    def rail_drag(event):
        if dragging["y"] is None:
            return
        first, last = canvas.yview()
        canvas.yview_moveto(max(0, min(1 - (last - first),
                            first + (event.y - dragging["y"]) /
                            max(1, rail.winfo_height()))))
        dragging["y"] = event.y

    rail.bind("<Button-1>", rail_click)
    rail.bind("<B1-Motion>", rail_drag)
    rail.bind("<ButtonRelease-1>", lambda event: dragging.update(y=None))

    def wheel_settings(event):
        if not canvas.winfo_exists():
            return
        # Only scroll when the pointer is inside Settings, including child panels.
        try:
            hovered = window.winfo_containing(event.x_root, event.y_root)
            widget = hovered
            inside = False
            while widget is not None:
                if widget is scroll_host:
                    inside = True
                    break
                widget = widget.master
            if not inside:
                return
            if getattr(event, "num", None) == 4:
                amount = -1
            elif getattr(event, "num", None) == 5:
                amount = 1
            else:
                amount = -int(event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1 if event.delta < 0 else 0)
            if amount and page.winfo_reqheight() > canvas.winfo_height():
                canvas.yview_scroll(amount, "units")
        except tk.TclError:
            pass

    # One Settings-specific binding, rather than re-binding on every child hover.
    wheel_ids = [(seq, window.bind_all(seq, wheel_settings, add="+"))
                 for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>")]

    def cleanup_settings(event):
        if event.widget is scroll_host:
            for sequence, binding_id in wheel_ids:
                try:
                    window._root().tk.call("bind", "all", sequence,
                        "\n".join(line for line in str(window.tk.call("bind", "all", sequence)).split("\n")
                                  if binding_id not in line))
                    window.deletecommand(binding_id)
                except tk.TclError:
                    pass

    scroll_host.bind("<Destroy>", cleanup_settings)

    # Fill the available width with a modest, consistent gutter.
    settings_body = tk.Frame(page, bg=BG)
    settings_body.pack(fill="x", padx=18, pady=(6, 12))
    settings_panels = []
    wrapping_labels = []
    settings_layout = {"columns": 0, "width": 0}

    def arrange_settings(event=None):
        available = max(300, canvas.winfo_width() - 36)
        width = available
        # Maintain usable card widths, and scale to three/four columns on
        # ultrawide displays instead of wasting the additional space.
        columns = (6 if width >= 2100 else 5 if width >= 1740
                   else 4 if width >= 1360 else 3 if width >= 1000
                   else 2 if width >= 680 else 1)
        if (settings_layout["columns"], settings_layout["width"]) == (columns, width):
            update_scroll_region()
            return
        settings_layout.update(columns=columns, width=width)
        settings_body.configure(width=width)
        for col in range(6):
            settings_body.grid_columnconfigure(col, weight=1 if col < columns else 0,
                                               uniform="setting_cards" if col < columns else "")
        for label in wrapping_labels:
            label.configure(wraplength=max(240, int(width / columns) - 65))
        for index, widget in enumerate(settings_panels):
            widget.grid_forget()
            widget.grid(row=index // columns, column=index % columns,
                        sticky="nsew", padx=6, pady=6)
        settings_body.update_idletasks()
        page.update_idletasks()
        update_scroll_region()

    canvas.bind("<Configure>", lambda event: (fit_page_width(event), arrange_settings()))

    panel = polished_panel(settings_body, padx=18, pady=12)
    settings_panels.append(panel)
    tk.Label(panel, text="APPEARANCE", font=("Arial", 9, "bold"), bg=PANEL, fg=accent).pack(anchor="w", pady=(0, 4))
    tk.Label(panel, text="Accent Colour", font=("Arial", 14, "bold"),
             bg=PANEL, fg=TEXT).pack(anchor="w")
    tk.Label(panel, text="Choose a preset or pick any colour you fancy.",
             bg=PANEL, fg=MUTED).pack(anchor="w", pady=(3, 8))

    preview = tk.Label(panel, text=f"  {accent}  ", bg=accent, fg="white",
                       font=("Arial", 11, "bold"), padx=10, pady=6)
    preview.pack(anchor="w", pady=(0, 4))

    presets = [
        ("Red", "#B23A48"), ("Blue", "#4776B4"), ("Purple", "#7B5CB8"),
        ("Green", "#4C8B68"), ("Orange", "#B86F3C"), ("Cyan", "#3F8F99")
    ]
    buttons = tk.Frame(panel, bg=PANEL)
    buttons.pack(anchor="w")

    def choose(new_colour):
        global accent
        previous = accent
        accent = new_colour.upper()
        set_setting("accent_color", accent)
        configure_ttk(window, accent)
        recolour_visible_accent(window, previous, accent)
        preview.configure(bg=accent, text=f"  {accent}  ")
        # The scrollbar thumb is painted on a Canvas, not a Tk widget colour.
        # Repaint it immediately, including when the page cannot scroll.
        paint_scrollbar()
        canvas.after_idle(paint_scrollbar)
        refresh_nav()

    for index, (name, colour) in enumerate(presets):
        preset_button = tk.Button(buttons, text=name,
                  command=lambda c=colour: choose(c), bg=colour, fg="white",
                  activebackground=colour, activeforeground="white", relief="flat",
                  width=9, cursor="hand2")
        preset_button._et_fixed_preset = True
        preset_button.grid(row=index // 3, column=index % 3, padx=(0, 5), pady=3)

    tk.Button(panel, text="Choose Custom Colour...",
              command=lambda: open_custom_colour_picker(choose),
              bg=PANEL_ALT, fg=TEXT, activebackground=accent,
              activeforeground="white", relief="flat", padx=15, pady=8,
              cursor="hand2").pack(anchor="w", pady=(8, 0))
    fan_panel = polished_panel(settings_body, padx=18, pady=12)
    settings_panels.append(fan_panel)
    tk.Label(fan_panel, text='GAME DETAIL ARTWORK', font=('Arial', 9, 'bold'),
             bg=PANEL, fg=accent).pack(anchor='w', pady=(0, 4))
    tk.Label(fan_panel, text='Background darkness', font=('Arial', 14, 'bold'),
             bg=PANEL, fg=TEXT).pack(anchor='w')
    fan_description = tk.Label(fan_panel, text='Lower values show more fan art; higher values make the information panel darker.',
             bg=PANEL, fg=MUTED, wraplength=275, justify="left")
    fan_description.pack(anchor='w', pady=(4, 7))
    wrapping_labels.append(fan_description)
    darkness = tk.IntVar(value=int(get_setting('game_background_darkness', '48')))
    level = tk.Label(fan_panel, text=f'{darkness.get()}%', bg=PANEL, fg=TEXT)
    level.pack(anchor='e')
    def change_darkness(value):
        n = int(float(value))
        level.configure(text=f'{n}%')
        set_setting('game_background_darkness', n)
    tk.Scale(fan_panel, from_=25, to=90, orient='horizontal', variable=darkness,
             command=change_darkness, bg=PANEL, fg=TEXT, troughcolor=PANEL_ALT,
             highlightthickness=0, length=260).pack(anchor='w')

    import_panel = polished_panel(settings_body, padx=18, pady=12)
    settings_panels.append(import_panel)
    tk.Label(import_panel, text="COLLECTION TOOLS", font=("Arial", 9, "bold"), bg=PANEL, fg=accent).pack(anchor="w", pady=(0, 4))
    tk.Label(import_panel, text="Excel Collection Import",
             font=("Arial", 14, "bold"), bg=PANEL, fg=TEXT).pack(anchor="w")
    import_description = tk.Label(import_panel, text="Import Games, Books, Shows and Movies from Collection Master.xlsx. "
             "Preview new entries and duplicates before confirming.",
             bg=PANEL, fg=MUTED, wraplength=275, justify="left")
    import_description.pack(anchor="w", pady=(4, 7))
    wrapping_labels.append(import_description)
    from excel_import import open_import
    tk.Button(import_panel, text="Import Excel Workbook...",
              command=lambda: open_import(page, accent, show_dashboard),
              bg=accent, fg="white", relief="flat", padx=15, pady=6).pack(anchor="w")
    backup_panel = polished_panel(settings_body, padx=18, pady=12)
    settings_panels.append(backup_panel)
    tk.Label(backup_panel, text="COLLECTION BACKUPS", font=("Arial", 9, "bold"),
             bg=PANEL, fg=accent).pack(anchor="w", pady=(0, 4))
    tk.Label(backup_panel, text="Local backups", font=("Arial", 14, "bold"),
             bg=PANEL, fg=TEXT).pack(anchor="w")
    backup_description = tk.Label(backup_panel,
             text="Automatically backs up once a day on launch. Each ZIP contains "
                  "your database and locally stored artwork. The newest 10 backups "
                  "are kept in the backups folder.",
             bg=PANEL, fg=MUTED, wraplength=275, justify="left")
    backup_description.pack(anchor="w", pady=(4, 6))
    wrapping_labels.append(backup_description)
    backup_status = tk.Label(backup_panel,
                             text=("Startup backup failed: " + backup_startup_error)
                             if backup_startup_error else "Backups are stored locally.",
                             bg=PANEL, fg=MUTED, wraplength=275, justify="left")
    backup_status.pack(anchor="w", pady=(0, 6))
    wrapping_labels.append(backup_status)
    def backup_now():
        try:
            target = create_backup(connection)
            backup_status.configure(text=f"Backup created: {target.name}")
        except Exception as exc:
            backup_status.configure(text=f"Backup failed: {exc}")
    tk.Button(backup_panel, text="Create Backup Now",
              command=backup_now, bg=accent, fg="white",
              relief="flat", padx=15, pady=6).pack(anchor="w")
    def run_offline_audit():
        try:
            report = format_audit(audit_collection(connection))
            audit_window = tk.Toplevel(window)
            audit_window.title("Offline Collection Audit")
            audit_window.geometry("780x520")
            audit_window.configure(bg=BG)
            output = tk.Text(audit_window, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                             relief="flat", wrap="word", padx=16, pady=16)
            output.pack(fill="both", expand=True, padx=12, pady=12)
            output.insert("1.0", report)
            output.configure(state="disabled")
        except Exception as exc:
            backup_status.configure(text=f"Offline audit failed: {exc}")
    tk.Button(backup_panel, text="Check Offline Files", command=run_offline_audit,
              bg=PANEL_ALT, fg=TEXT, relief="flat", padx=12, pady=7).pack(anchor="w", pady=(8, 0))
    def choose_restore():
        from tkinter import filedialog, messagebox as native_messagebox
        selected = filedialog.askopenfilename(parent=window, title='Select collection backup',
                initialdir=str(__import__('pathlib').Path(__file__).resolve().parent.parent / 'backups'),
                filetypes=[('Backup ZIP files', '*.zip')])
        if not selected:
            return
        try:
            validate_backup(selected)
            if not native_messagebox.askyesno('Restore collection on next launch',
                    'The selected backup passed integrity checks.\n\n'
                    'On your NEXT launch, it will replace your current collection database '
                    'and local artwork. A safety copy of the current files will be created first.\n\n'
                    'Please stop any active timers and close the app normally before relaunching.\n\n'
                    'Schedule this restore?', parent=window):
                return
            schedule_restore(selected)
            backup_status.configure(text='Restore scheduled. Close the app normally, then reopen it.')
            native_messagebox.showinfo('Restore scheduled',
                'Close Entertainment Tracker normally and reopen it to restore.\n'
                'A pre-restore safety ZIP will be saved in backups.', parent=window)
        except Exception as exc:
            backup_status.configure(text=f'Restore failed: {exc}')
            native_messagebox.showerror('Restore not scheduled', str(exc), parent=window)
    tk.Button(backup_panel, text='Restore from Backup...', command=choose_restore,
              bg=PANEL_ALT, fg=TEXT, relief='flat', padx=12, pady=7).pack(anchor='w', pady=(8, 0))
    if restore_startup_error:
        backup_status.configure(text='Pending restore failed (original files retained): ' + restore_startup_error)
    elif restored_safety:
        backup_status.configure(text='Collection restored. Safety copy: ' + restored_safety.name)
    def preview_media_rename():
        from tkinter import messagebox as native_messagebox
        from media_naming import plan_renames, rename_existing
        try:
            planned, skipped = plan_renames(connection)
            preview = tk.Toplevel(window)
            preview.title('Preview Media Filenames')
            preview.geometry('830x540')
            preview.configure(bg=BG)
            output = tk.Text(preview, bg=PANEL, fg=TEXT, wrap='none', padx=12, pady=12)
            output.pack(fill='both', expand=True, padx=12, pady=10)
            lines = [f'{len(planned)} files ready to rename; {len(skipped)} skipped.',
                     'Only locally stored media inside assets/ will be renamed.',
                     'A full backup is created before any change.', '']
            lines += [f'{old.name}  →  {new.name}' for _, old, new in planned]
            if skipped:
                lines += ['', 'Skipped:'] + [f'{raw}: {reason}' for raw, reason in skipped]
            output.insert('1.0', '\n'.join(lines))
            output.configure(state='disabled')
            def perform():
                if not native_messagebox.askyesno('Rename existing media',
                        f'Rename {len(planned)} media files?\n\nA safety backup will be created first.', parent=preview):
                    return
                try:
                    count, ignored, safety = rename_existing(connection)
                    preview.destroy()
                    backup_status.configure(text=f'Renamed {count} files. Backup: {safety.name if safety else "not needed"}.')
                    native_messagebox.showinfo('Media filenames updated',
                        f'Renamed {count} files. Skipped {len(ignored)}.\n\nRestart the app to refresh cached artwork.',parent=window)
                except Exception as exc:
                    native_messagebox.showerror('Media rename failed',str(exc),parent=preview)
            tk.Button(preview, text='Rename Files (Create Backup First)', command=perform,
                      state='normal' if planned else 'disabled', bg=accent, fg='white',
                      relief='flat', padx=12, pady=7).pack(pady=(0,12))
        except Exception as exc:
            native_messagebox.showerror('Media rename preview failed',str(exc),parent=window)
    tk.Button(backup_panel, text='Preview / Rename Existing Media...', command=preview_media_rename,
              bg=PANEL_ALT, fg=TEXT, relief='flat', padx=12, pady=7).pack(anchor='w', pady=(8,0))
    def preview_unused_media():
        from tkinter import messagebox as native_messagebox
        from media_cleanup import scan_unused, quarantine_unused
        try:
            candidates = scan_unused(connection)
            dialog = tk.Toplevel(window)
            dialog.title('Unused Media Cleanup — Preview')
            dialog.geometry('850x560')
            dialog.configure(bg=BG)
            tk.Label(dialog, text=f'{len(candidates)} possible unused images • {sum(size for _,size in candidates)/1024/1024:.1f} MB',
                     bg=BG, fg=TEXT, font=('Arial', 13, 'bold')).pack(anchor='w', padx=16, pady=(14,4))
            tk.Label(dialog, text='Conservative scan: uncertain or referenced files are excluded. Select files to quarantine.\n'
                                  'Nothing is permanently deleted. A backup is created before moving files.',
                     bg=BG, fg=MUTED, justify='left').pack(anchor='w', padx=16, pady=(0,10))
            frame = tk.Frame(dialog, bg=BG)
            frame.pack(fill='both', expand=True, padx=16)
            scrollbar = tk.Scrollbar(frame)
            scrollbar.pack(side='right', fill='y')
            entries = tk.Listbox(frame, selectmode='extended', bg=PANEL, fg=TEXT,
                                 selectbackground=accent, selectforeground='white',
                                 activestyle='none', relief='flat', yscrollcommand=scrollbar.set)
            entries.pack(side='left', fill='both', expand=True)
            scrollbar.configure(command=entries.yview)
            for rel, size in candidates:
                entries.insert('end', f'{size/1024:.0f} KB   {rel}')
            if candidates:
                entries.selection_set(0,'end')
            def perform_cleanup():
                chosen = [candidates[i][0] for i in entries.curselection()]
                if not chosen:
                    native_messagebox.showinfo('No files selected','Select one or more files to quarantine.',parent=dialog)
                    return
                if not native_messagebox.askyesno('Move unused media to quarantine',
                        f'Move {len(chosen)} selected images out of assets?\n\n'
                        'A full backup is created first. Files will be kept in media_quarantine, not deleted.\n\n'
                        'Continue?',parent=dialog):
                    return
                try:
                    destination, safety, count = quarantine_unused(connection, chosen)
                    dialog.destroy()
                    backup_status.configure(text=f'Quarantined {count} images; backup: {safety.name}')
                    native_messagebox.showinfo('Media cleanup complete',
                        f'Moved {count} images to:\n{destination}\n\nSafety backup: {safety.name}\n\n'
                        'If any artwork is missing, close the app and move files back from quarantine.',parent=window)
                except Exception as exc:
                    native_messagebox.showerror('Media cleanup failed',str(exc),parent=dialog)
            tk.Button(dialog, text='Quarantine Selected (Backup First)',
                      command=perform_cleanup, state='normal' if candidates else 'disabled',
                      bg=accent, fg='white', relief='flat', padx=14, pady=8).pack(pady=12)
        except Exception as exc:
            native_messagebox.showerror('Media cleanup scan failed',str(exc),parent=window)
    tk.Button(backup_panel, text='Scan / Clean Unused Media...', command=preview_unused_media,
              bg=PANEL_ALT, fg=TEXT, relief='flat', padx=12, pady=7).pack(anchor='w', pady=(8,0))
    arrange_settings()
    refresh_nav()
    reveal_content()


def navigate(name, command):
    def wrapped():
        command()
    return wrapped


# A single-line title now fits comfortably in the wider navigation rail.
brand = tk.Frame(sidebar, bg=PANEL)
brand.pack(fill="x", padx=18, pady=(26, 30))
tk.Frame(brand, bg=accent, width=4).pack(side="left", fill="y", padx=(0, 12))
brand_copy = tk.Frame(brand, bg=PANEL)
brand_copy.pack(side="left")
tk.Label(brand_copy, text="ENTERTAINMENT", font=("Arial", 13, "bold"),
         bg=PANEL, fg=TEXT).pack(anchor="w")
tk.Label(brand_copy, text="TRACKER  /  YOUR LIBRARY", font=("Arial", 8, "bold"),
         bg=PANEL, fg=MUTED).pack(anchor="w", pady=(4, 0))
tk.Label(sidebar, text="YOUR COLLECTION", font=("Arial", 8, "bold"),
         bg=PANEL, fg=MUTED).pack(anchor="w", padx=23, pady=(0, 8))

for name, command in [
    ("Dashboard", show_dashboard), ("Games", show_games), ("Movies", show_movies),
    ("Shows", show_shows), ("Books", show_books), ("History", show_history),
    ("Settings", show_settings)
]:
    if name == "History":
        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(14, 13))
        tk.Label(sidebar, text="ACTIVITY & PREFERENCES", font=("Arial", 8, "bold"),
                 bg=PANEL, fg=MUTED).pack(anchor="w", padx=23, pady=(0, 8))
    button = tk.Button(sidebar, text=name, font=("Arial", 11), anchor="w",
                       padx=18, pady=11, relief="flat", bd=0, cursor="hand2",
                       command=navigate(name, command), bg=PANEL, fg=TEXT,
                       activebackground=accent, activeforeground="white")
    button.pack(fill="x", padx=10, pady=2)
    def nav_enter(event, nav_name=name, widget=button):
        if nav_name != current_page:
            widget.configure(bg=PANEL_ALT, fg="white")
    def nav_leave(event, nav_name=name, widget=button):
        widget.configure(bg=accent if nav_name == current_page else PANEL,
                         fg="white" if nav_name == current_page else TEXT)
    button.bind("<Enter>", nav_enter)
    button.bind("<Leave>", nav_leave)
    nav_buttons[name] = button


def close_app():
    if window.manual_timer.kind is not None:
        from tkinter import messagebox as native_messagebox
        if not native_messagebox.askyesno('Active timer', 'Stop and save the active manual timer before exiting?'):
            return
        try:
            window.manual_timer.stop(tracker)
        except ValueError as exc:
            native_messagebox.showwarning('Timer', str(exc))
            return
    tracker.stop()
    close_database()
    window.destroy()

window.protocol("WM_DELETE_WINDOW", close_app)

tk.Button(sidebar, text="Exit", font=("Arial", 10), command=close_app,
          bg=PANEL_ALT, fg=TEXT, activebackground=accent, activeforeground="white",
          relief="flat", bd=0, cursor="hand2", pady=9).pack(
              side="bottom", fill="x", padx=18, pady=20)

show_dashboard()
window.mainloop()
