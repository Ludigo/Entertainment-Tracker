import tkinter as tk

from database import setup_database, close_database, get_setting, set_setting, cursor
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
    page = tk.Frame(content, bg=BG)
    page.pack(fill="both", expand=True)

    section_heading(page, "PERSONALISE YOUR TRACKER", "Settings",
                    "Appearance, imports and application preferences").pack(
                        fill="x", padx=36, pady=(28, 18))

    panel = polished_panel(page, padx=26, pady=20)
    panel.pack(fill="x", padx=36, pady=(0, 14))
    tk.Label(panel, text="APPEARANCE", font=("Arial", 9, "bold"), bg=PANEL, fg=accent).pack(anchor="w", pady=(0, 7))
    tk.Label(panel, text="Accent Colour", font=("Arial", 16, "bold"),
             bg=PANEL, fg=TEXT).pack(anchor="w")
    tk.Label(panel, text="Choose a preset or pick any colour you fancy.",
             bg=PANEL, fg=MUTED).pack(anchor="w", pady=(4, 18))

    preview = tk.Label(panel, text=f"  {accent}  ", bg=accent, fg="white",
                       font=("Arial", 11, "bold"), padx=10, pady=8)
    preview.pack(anchor="w", pady=(0, 15))

    presets = [
        ("Red", "#B23A48"), ("Blue", "#4776B4"), ("Purple", "#7B5CB8"),
        ("Green", "#4C8B68"), ("Orange", "#B86F3C"), ("Cyan", "#3F8F99")
    ]
    buttons = tk.Frame(panel, bg=PANEL)
    buttons.pack(anchor="w")

    def choose(new_colour):
        global accent
        accent = new_colour.upper()
        set_setting("accent_color", accent)
        configure_ttk(window, accent)
        preview.configure(bg=accent, text=f"  {accent}  ")
        refresh_nav()

    for name, colour in presets:
        tk.Button(buttons, text=name, command=lambda c=colour: choose(c),
                  bg=colour, fg="white", activebackground=colour,
                  activeforeground="white", relief="flat", width=9,
                  cursor="hand2").pack(side="left", padx=(0, 8), pady=5)

    tk.Button(panel, text="Choose Custom Colour...",
              command=lambda: open_custom_colour_picker(choose),
              bg=PANEL_ALT, fg=TEXT, activebackground=accent,
              activeforeground="white", relief="flat", padx=15, pady=8,
              cursor="hand2").pack(anchor="w", pady=(15, 0))
    fan_panel = polished_panel(page, padx=26, pady=16)
    fan_panel.pack(fill='x', padx=36, pady=(0, 14))
    tk.Label(fan_panel, text='GAME DETAIL ARTWORK', font=('Arial', 9, 'bold'),
             bg=PANEL, fg=accent).pack(anchor='w', pady=(0, 7))
    tk.Label(fan_panel, text='Background darkness', font=('Arial', 14, 'bold'),
             bg=PANEL, fg=TEXT).pack(anchor='w')
    tk.Label(fan_panel, text='Lower values show more fan art; higher values make the information panel darker.',
             bg=PANEL, fg=MUTED).pack(anchor='w', pady=(4, 7))
    darkness = tk.IntVar(value=int(get_setting('game_background_darkness', '48')))
    level = tk.Label(fan_panel, text=f'{darkness.get()}%', bg=PANEL, fg=TEXT)
    level.pack(anchor='e')
    def change_darkness(value):
        n = int(float(value))
        level.configure(text=f'{n}%')
        set_setting('game_background_darkness', n)
    tk.Scale(fan_panel, from_=25, to=90, orient='horizontal', variable=darkness,
             command=change_darkness, bg=PANEL, fg=TEXT, troughcolor=PANEL_ALT,
             highlightthickness=0, length=390).pack(anchor='w')

    import_panel = polished_panel(page, padx=26, pady=20)
    import_panel.pack(fill="x", padx=36, pady=(0, 20))
    tk.Label(import_panel, text="COLLECTION TOOLS", font=("Arial", 9, "bold"), bg=PANEL, fg=accent).pack(anchor="w", pady=(0, 7))
    tk.Label(import_panel, text="Excel Collection Import",
             font=("Arial", 16, "bold"), bg=PANEL, fg=TEXT).pack(anchor="w")
    tk.Label(import_panel, text="Import Games, Books, Shows and Movies from Collection Master.xlsx. "
             "Preview new entries and duplicates before confirming.",
             bg=PANEL, fg=MUTED, wraplength=680, justify="left").pack(
                 anchor="w", pady=(5, 12))
    from excel_import import open_import
    tk.Button(import_panel, text="Import Excel Workbook...",
              command=lambda: open_import(page, accent, show_dashboard),
              bg=accent, fg="white", relief="flat", padx=15, pady=9).pack(anchor="w")
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
