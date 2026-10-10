"""Per-game session history, stats and monthly calendar."""
import calendar
import tkinter as tk
from datetime import datetime, timedelta, timezone
from database import cursor
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED, BORDER


def duration_text(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def show_session_history(parent, game_id, game_name, accent, on_back):
    for child in parent.winfo_children():
        child.destroy()
    page = tk.Frame(parent, bg=BG)
    page.pack(fill="both", expand=True)
    top = tk.Frame(page, bg=BG)
    top.pack(fill="x", padx=36, pady=(28, 10))
    if on_back:
        tk.Button(top, text="← Game Details", command=on_back, bg=PANEL_ALT,
                  fg=TEXT, activebackground=accent, activeforeground="white",
                  relief="flat", padx=13, pady=8).pack(side="left")
    tk.Label(top, text="ACTIVITY / SESSION HISTORY", bg=BG, fg=accent,
             font=("Arial", 9, "bold")).pack(side="right")
    tk.Label(page, text=game_name if game_id is not None else "History",
             bg=BG, fg=TEXT, font=("Arial", 27, "bold")).pack(anchor="w", padx=36)

    if game_id is None:
        cursor.execute("SELECT s.started_at, s.ended_at, s.duration_seconds, s.source, "
                       "g.name, s.note FROM game_sessions s JOIN games g ON g.id = s.game_id "
                       "ORDER BY s.started_at DESC, s.id DESC")
    else:
        cursor.execute("SELECT s.started_at, s.ended_at, s.duration_seconds, s.source, "
                       "g.name, s.note FROM game_sessions s JOIN games g ON g.id = s.game_id "
                       "WHERE s.game_id = ? ORDER BY s.started_at DESC, s.id DESC", (game_id,))
    sessions = cursor.fetchall()
    count = len(sessions)
    total = sum(max(0, int(r[2] or 0)) for r in sessions)
    longest = max((int(r[2] or 0) for r in sessions), default=0)
    average = round(total / count) if count else 0
    stats = tk.Frame(page, bg=BG)
    stats.pack(fill="x", padx=30, pady=(12, 12))
    for title, value in (("RECORDED SESSIONS", str(count)),
                         ("RECORDED TIME", duration_text(total)),
                         ("LONGEST SESSION", duration_text(longest)),
                         ("AVERAGE SESSION", duration_text(average))):
        card = tk.Frame(stats, bg=PANEL, padx=14, pady=14,
                        highlightthickness=1, highlightbackground=BORDER)
        card.pack(side="left", expand=True, fill="x", padx=5)
        tk.Label(card, text=title, bg=PANEL, fg=MUTED,
                 font=("Arial", 8, "bold")).pack(anchor="w")
        tk.Label(card, text=value, bg=PANEL, fg=TEXT,
                 font=("Arial", 16, "bold")).pack(anchor="w", pady=(4, 0))

    body = tk.Frame(page, bg=BG)
    body.pack(fill="both", expand=True, padx=35, pady=(0, 20))
    body.grid_columnconfigure(0, weight=1)
    body.grid_columnconfigure(1, weight=1)
    body.grid_rowconfigure(0, weight=1)
    cal_panel = tk.Frame(body, bg=PANEL, padx=17, pady=16,
                         highlightthickness=1, highlightbackground=BORDER)
    cal_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
    history_panel = tk.Frame(body, bg=PANEL, padx=17, pady=16,
                             highlightthickness=1, highlightbackground=BORDER)
    history_panel.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

    # Dates are displayed in the user's local timezone, including sessions
    # originally saved in UTC by the tracker.
    by_day = {}
    parsed = []
    for started, ended, seconds, source, session_game, note in sessions:
        try:
            dt = datetime.fromisoformat(started)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local = dt.astimezone()
        except (ValueError, TypeError):
            continue
        parsed.append((local, int(seconds or 0), source, session_game, note))
        # Split sessions across local midnight, using recorded elapsed seconds.
        end = local + timedelta(seconds=max(0, int(seconds or 0)))
        point = local
        while point.date() < end.date():
            midnight = datetime.combine(point.date() + timedelta(days=1),
                                        datetime.min.time(), tzinfo=point.tzinfo)
            by_day[point.date()] = by_day.get(point.date(), 0) + int((midnight-point).total_seconds())
            point = midnight
        by_day[point.date()] = by_day.get(point.date(), 0) + max(0, int((end-point).total_seconds()))

    month = [datetime.now().astimezone().year, datetime.now().astimezone().month]
    heading = tk.Frame(cal_panel, bg=PANEL)
    heading.pack(fill="x")
    grid_holder = tk.Frame(cal_panel, bg=PANEL)
    grid_holder.pack(fill="x", pady=(14, 8))
    selected_day = tk.StringVar(value="")
    detail_label = tk.Label(cal_panel, text="Select a highlighted day to see playtime.",
                            bg=PANEL, fg=MUTED, font=("Arial", 9), wraplength=330)
    detail_label.pack(anchor="w", pady=(8, 0))

    def change_month(offset):
        year, mon = month
        mon += offset
        if mon == 0:
            year, mon = year - 1, 12
        elif mon == 13:
            year, mon = year + 1, 1
        month[:] = [year, mon]
        render_month()

    tk.Button(heading, text="‹", command=lambda: change_month(-1), bg=PANEL_ALT,
              fg=TEXT, relief="flat", width=3).pack(side="left")
    month_label = tk.Label(heading, bg=PANEL, fg=TEXT, font=("Arial", 12, "bold"))
    month_label.pack(side="left", expand=True)
    tk.Button(heading, text="›", command=lambda: change_month(1), bg=PANEL_ALT,
              fg=TEXT, relief="flat", width=3).pack(side="right")

    def render_month():
        for child in grid_holder.winfo_children():
            child.destroy()
        year, mon = month
        month_label.configure(text=f"{calendar.month_name[mon]} {year}")
        for col, weekday in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            tk.Label(grid_holder, text=weekday, bg=PANEL, fg=MUTED,
                     font=("Arial", 8, "bold")).grid(row=0, column=col, sticky="ew", pady=4)
            grid_holder.grid_columnconfigure(col, weight=1)
        for row_num, week in enumerate(calendar.monthcalendar(year, mon), start=1):
            for col, day in enumerate(week):
                if not day:
                    continue
                date = datetime(year, mon, day).date()
                seconds = by_day.get(date, 0)
                button = tk.Button(grid_holder, text=str(day), relief="flat",
                                   bg=accent if seconds else PANEL_ALT,
                                   fg="white" if seconds else MUTED,
                                   activebackground=accent, activeforeground="white",
                                   cursor="hand2" if seconds else "arrow")
                button.grid(row=row_num, column=col, sticky="nsew", padx=2, pady=2, ipady=7)
                if seconds:
                    button.configure(command=lambda d=date, sec=seconds:
                                     detail_label.configure(text=f"{d:%A %d %B %Y}:  {duration_text(sec)}"))
        if not sessions:
            detail_label.configure(text="No recorded sessions yet. Finish a tracked game to see activity.")

    render_month()
    tk.Label(history_panel, text="ALL COMPLETED SESSIONS", bg=PANEL, fg=TEXT,
             font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 10))
    container = tk.Frame(history_panel, bg=PANEL)
    container.pack(fill="both", expand=True)
    scrollbar = tk.Scrollbar(container, bg=PANEL_ALT, troughcolor=PANEL, relief="flat")
    scrollbar.pack(side="right", fill="y")
    canvas = tk.Canvas(container, bg=PANEL, bd=0, highlightthickness=0,
                       yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.configure(command=canvas.yview)
    inner = tk.Frame(canvas, bg=PANEL)
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
    if not parsed:
        tk.Label(inner, text="No completed sessions recorded yet.",
                 bg=PANEL, fg=MUTED).pack(anchor="w", pady=10)
    for local, seconds, source, session_game, note in parsed:
        row = tk.Frame(inner, bg=PANEL_ALT, padx=12, pady=10)
        row.pack(fill="x", pady=3)
        info = tk.Frame(row, bg=PANEL_ALT)
        info.pack(side="left", fill="x", expand=True)
        if game_id is None:
            tk.Label(info, text=session_game, bg=PANEL_ALT, fg=TEXT,
                     font=("Arial", 10, "bold"), anchor="w").pack(anchor="w")
        tk.Label(info, text=local.strftime("%d %b %Y  •  %H:%M"), bg=PANEL_ALT,
                 fg=MUTED if game_id is None else TEXT,
                 font=("Arial", 9)).pack(anchor="w")
        if note:
            note_label=tk.Label(info,text=note,bg=PANEL_ALT,fg=MUTED,justify='left',anchor='w',wraplength=330)
            note_label.pack(fill='x',pady=(5,0))
            info.bind('<Configure>',lambda event,label=note_label:label.configure(wraplength=max(100,event.width)))
        tk.Label(row, text=duration_text(seconds), bg=PANEL_ALT,
                 fg=accent, font=("Arial", 10, "bold")).pack(side="right")


def show_all_session_history(parent, accent):
    """All-game calendar and session totals in the main content area."""
    show_session_history(parent, None, "All Games", accent, None)
