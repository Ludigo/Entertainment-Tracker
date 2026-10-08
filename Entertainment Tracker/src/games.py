from library_filters import build_filters, where_clause
from bulk_edit import open_bulk_edit
from cover_grid import CoverGrid
from database import get_setting, set_setting
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED, BORDER
import tkinter as tk
from tkinter import ttk
from modal import ModalFrame, app_messagebox as messagebox
from database import connection, cursor
from utils import format_time, parse_time


def open_games(parent, on_open_detail=None, initial_edit_id=None):

    games_window = tk.Frame(parent)
    games_window.pack(fill="both", expand=True)


    heading = tk.Label(
        games_window,
        text="Games Library",
        font=("Arial", 20)
    )
    heading.pack(pady=15)
    tk.Button(games_window, text="Bulk Edit...",
              command=lambda: open_bulk_edit(games_window, "games",
                  on_done=lambda: load_games(search_entry.get())),
              bg=PANEL_ALT, fg=TEXT, relief="flat", padx=12, pady=6).pack(anchor="e", padx=24)


    # -------------------------
    # SEARCH AREA
    # -------------------------

    search_frame = tk.Frame(games_window, bg="#202329", highlightbackground="#363b44", highlightthickness=1)
    search_frame.pack(
        fill="x",
        padx=20,
        pady=5
    )


    search_label = tk.Label(
        search_frame,
        text="Search:",
        font=("Arial", 11)
    )
    search_label.configure(bg="#202329", fg="#a9adb5")
    search_label.pack(side="left")


    search_entry = tk.Entry(
        search_frame,
        font=("Arial", 11),
        width=35
    )
    search_entry.configure(bg="#292d34", fg="#f2f2f2", insertbackground="#f2f2f2", relief="flat", highlightthickness=0)
    search_entry.pack(
        side="left",
        padx=10
    )


    # Platform choices come from the database, not a hard-coded list.
    platform_var = tk.StringVar(value="All Platforms")
    tk.Label(search_frame, text="Platform:", font=("Arial", 10)).pack(side="left", padx=(6, 4))
    platform_combo = ttk.Combobox(search_frame, textvariable=platform_var,
                                  state="readonly", width=17,
                                  style="Filter.TCombobox")
    platform_combo.pack(side="left", padx=(0, 5))

    def refresh_platforms():
        cursor.execute("SELECT DISTINCT platform FROM games "
                       "WHERE platform IS NOT NULL AND TRIM(platform) != '' "
                       "ORDER BY platform COLLATE NOCASE")
        choices = ["All Platforms"] + [row[0] for row in cursor.fetchall()]
        platform_combo.configure(values=choices)
        saved = get_setting("games_platform_filter", "All Platforms")
        if saved in choices:
            platform_var.set(saved)
        elif platform_var.get() not in choices:
            platform_var.set("All Platforms")
            set_setting("games_platform_filter", "All Platforms")

    refresh_platforms()

    sort_options = ("Name: A–Z", "Name: Z–A", "Most Played",
                    "Least Played", "Recently Added", "Oldest Added", "Platform")
    sort_var = tk.StringVar(value=get_setting("games_sort", "Name: A–Z"))
    if sort_var.get() not in sort_options:
        sort_var.set("Name: A–Z")
    tk.Label(search_frame, text="Sort:", font=("Arial", 10)).pack(side="left", padx=(6, 4))
    sort_combo = ttk.Combobox(search_frame, textvariable=sort_var, values=sort_options,
                              state="readonly", width=16, style="Filter.TCombobox")
    sort_combo.pack(side="left", padx=(0, 5))

    status_options = ("All Statuses", "Backlog", "Completed", "Started",
                      "Not Started", "Not Completed")
    status_var = tk.StringVar(value=get_setting("games_status_filter", "All Statuses"))
    if status_var.get() not in status_options:
        status_var.set("All Statuses")
    tk.Label(search_frame, text="Status:", font=("Arial", 10)).pack(side="left", padx=(5, 3))
    status_combo = ttk.Combobox(search_frame, textvariable=status_var,
                                values=status_options, state="readonly",
                                width=15, style="Filter.TCombobox")
    status_combo.pack(side="left", padx=(0, 5))

    # -------------------------
    # TABLE AREA
    # -------------------------

    # Legacy game controls remain internally available for compatibility,
    # but the shared toolbar is the single visible filter interface.
    for control in (platform_combo, sort_combo, status_combo):
        control.pack_forget()
    for control in search_frame.winfo_children():
        if isinstance(control, tk.Label) and control.cget("text") in ("Platform:", "Sort:", "Status:"):
            control.pack_forget()

    # Shared filters sit in the same position across all four libraries.
    filters = build_filters(games_window, "games", lambda: load_games(search_entry.get()))

    table_frame = tk.Frame(games_window)
    table_frame.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=10
    )


    scrollbar = ttk.Scrollbar(
        table_frame,
        orient="vertical",
        style="Dark.Vertical.TScrollbar"
    )

    scrollbar.pack(
        side="right",
        fill="y"
    )


    game_table = ttk.Treeview(
        table_frame,
        columns=(
            "ID",
            "Game",
            "Platform",
            "Playtime", "Price", "Completed", "Backlog", "Started"
        ),
        show="headings",
        yscrollcommand=scrollbar.set
    )


    scrollbar.config(
        command=game_table.yview
    )


    game_table.heading(
        "ID",
        text="ID"
    )

    game_table.heading(
        "Game",
        text="Game"
    )

    game_table.heading(
        "Platform",
        text="Platform"
    )

    game_table.heading(
        "Playtime",
        text="Playtime"
    )


    game_table.column(
        "ID",
        width=50,
        anchor="center"
    )

    game_table.column(
        "Game",
        width=350
    )

    game_table.column(
        "Platform",
        width=180
    )

    game_table.column(
        "Playtime",
        width=150,
        anchor="center"
    )


    for column, width in (("Price", 95), ("Completed", 90),
                          ("Backlog", 80), ("Started", 85)):
        game_table.heading(column, text=column if column != "Price" else "Paid")
        game_table.column(column, width=width, minwidth=65, anchor="center")

    game_table.pack(
        fill="both",
        expand=True
    )



    # Cover grid / table switch. The grid shares the existing search field.
    def open_grid_detail(item_id):
        if on_open_detail:
            on_open_detail(item_id)

    grid_view = CoverGrid(games_window, "games", open_grid_detail)
    view_mode = tk.StringVar(value=get_setting("view_games", "Covers"))
    def switch_view(mode):
        view_mode.set(mode)
        set_setting("view_games", mode)
        update_toggle()
        if mode == "Covers":
            table_frame.pack_forget()
            grid_view.pack(fill="both", expand=True, padx=12, pady=8)
            load_games(search_entry.get())
        else:
            grid_view.pack_forget()
            table_frame.pack(fill="both", expand=True, padx=20, pady=10)
    view_controls = tk.Frame(search_frame, bg=PANEL_ALT)
    view_controls.pack(side="right", padx=(8, 0))
    list_button = tk.Button(view_controls, text="☷  List", width=9,
                            relief="flat", bd=0, cursor="hand2",
                            command=lambda: switch_view("List"))
    list_button.pack(side="left", padx=2, pady=2)
    cover_button = tk.Button(view_controls, text="▦  Covers", width=11,
                             relief="flat", bd=0, cursor="hand2",
                             command=lambda: switch_view("Covers"))
    cover_button.pack(side="left", padx=2, pady=2)

    def update_toggle():
        accent = get_setting("accent_color", "#B23A48")
        for button, mode in ((list_button, "List"), (cover_button, "Covers")):
            active = view_mode.get() == mode
            button.configure(bg=accent if active else PANEL_ALT,
                             fg="white" if active else MUTED,
                             activebackground=accent if active else BORDER,
                             activeforeground="white",
                             font=("Arial", 10, "bold" if active else "normal"))
    update_toggle()

    # -------------------------
    # LOAD GAMES
    # -------------------------

    def load_games(search=""):

        # Clear table
        for row in game_table.get_children():
            game_table.delete(row)


        selected_platform = platform_var.get()
        order_by = {
            "Name: A–Z": "name COLLATE NOCASE ASC, id ASC",
            "Name: Z–A": "name COLLATE NOCASE DESC, id DESC",
            "Most Played": "playtime DESC, name COLLATE NOCASE",
            "Least Played": "playtime ASC, name COLLATE NOCASE",
            "Recently Added": "id DESC",
            "Oldest Added": "id ASC",
            "Platform": "platform COLLATE NOCASE, name COLLATE NOCASE",
        }
        sql = "SELECT * FROM games WHERE name LIKE ?"
        params = ["%" + search + "%"]
        if selected_platform != "All Platforms":
            sql += " AND platform = ?"
            params.append(selected_platform)
        status_conditions = {
            "Backlog": "backlog = 1",
            "Completed": "completed = 1",
            "Started": "started = 1",
            "Not Started": "started = 0",
            "Not Completed": "completed = 0",
        }
        if status_var.get() in status_conditions:
            sql += " AND " + status_conditions[status_var.get()]
        sql += " ORDER BY " + order_by.get(sort_var.get(), order_by["Name: A–Z"])
        condition, values, ordering = where_clause("games", search, filters)
        cursor.execute("SELECT * FROM games WHERE " + condition + " ORDER BY " + ordering, values)
        games = cursor.fetchall()
        filtered_ids = [row[0] for row in games]
        filters['count'].configure(text=f"Showing {len(games)} items")
        cursor.execute("PRAGMA table_info(games)")
        field_names = [col[1] for col in cursor.fetchall()]

        for raw in games:
            game = dict(zip(field_names, raw))

            game_table.insert(
                "",
                "end",
                values=(
                    game["id"],
                    game["name"],
                    game["platform"],
                    format_time(game["playtime"] or 0),
                    "—" if game.get("price_paid") is None else f"£{game['price_paid']:,.2f}",
                    "Yes" if game.get("completed") else "No",
                    "Yes" if game.get("backlog") else "No",
                    "Yes" if game.get("started") else "No"
                )
            )


        if view_mode.get() == "Covers":
            grid_view.set_search(search, platform_var.get(), sort_var.get(), status_var.get(), filtered_ids=filtered_ids)

    # -------------------------
    # SEARCH GAMES
    # -------------------------

    def search_games():

        search_text = search_entry.get()

        load_games(search_text)


    def show_all_games():

        search_entry.delete(
            0,
            tk.END
        )

        refresh_platforms()
        load_games()


    # -------------------------
    # ADD / EDIT GAME DETAILS
    # -------------------------
    def game_form(game_id=None):
        record = {}
        if game_id is not None:
            cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
            row = cursor.fetchone()
            if not row:
                messagebox.showerror("Not Found", "Game could not be found.")
                return
            cursor.execute("PRAGMA table_info(games)")
            record = dict(zip((col[1] for col in cursor.fetchall()), row))

        modal = ModalFrame(games_window)
        modal.title("Edit Game" if game_id is not None else "Add Game")
        modal.geometry("540x740")
        modal.resizable(False, False)
        tk.Label(modal, text="Edit Game" if game_id is not None else "Add Game",
                 font=("Arial", 18, "bold")).pack(pady=(8, 12))

        def field(label, value="", width=40):
            tk.Label(modal, text=label).pack(anchor="w", padx=15)
            entry = tk.Entry(modal, width=width)
            entry.pack(fill="x", padx=15, pady=(2, 9))
            if value is not None:
                entry.insert(0, str(value))
            return entry

        title_entry = field("Title", record.get("name", ""))
        platform_entry = field("Platform", record.get("platform", ""))
        price_entry = field("Price Paid (£) — leave blank if unknown",
                            "" if record.get("price_paid") is None else f"{record['price_paid']:.2f}")
        playtime_entry = field("Playtime (H:MM:SS)",
                               format_time(record.get("playtime") or 0))
        tk.Label(modal, text="Game Description").pack(anchor="w", padx=15)
        description_entry = tk.Text(modal, height=5, wrap="word", font=("Arial", 10))
        description_entry.pack(fill="x", padx=15, pady=(3, 9))
        description_entry.insert("1.0", record.get("description") or "")
        checks = tk.Frame(modal)
        checks.pack(fill="x", padx=15, pady=8)
        completed_var = tk.BooleanVar(value=bool(record.get("completed", 0)))
        backlog_var = tk.BooleanVar(value=bool(record.get("backlog", 0)))
        started_var = tk.BooleanVar(value=bool(record.get("started", 0)))
        for label, variable in (
            ("Completed", completed_var),
            ("In Backlog", backlog_var),
            ("Started Playing", started_var),
        ):
            tk.Checkbutton(checks, text=label, variable=variable,
                           anchor="w").pack(anchor="w", pady=3)

        error = tk.Label(modal, text="", fg="#F19B9B", wraplength=400)
        error.pack(pady=3)

        def save():
            title = title_entry.get().strip()
            platform = platform_entry.get().strip()
            if not title or not platform:
                error.configure(text="Title and platform are required.")
                return
            try:
                hours = parse_time(playtime_entry.get().strip())
                if hours < 0:
                    raise ValueError()
            except (ValueError, TypeError):
                error.configure(text="Playtime must be a non-negative H:MM:SS value.")
                return
            price_text = price_entry.get().strip().replace("£", "")
            try:
                price = float(price_text) if price_text else None
                if price is not None and (not 0 <= price < float("inf")):
                    raise ValueError()
            except ValueError:
                error.configure(text="Price must be a non-negative number, or blank.")
                return
            values = (title, platform, hours, price, int(completed_var.get()),
                      int(backlog_var.get()), int(started_var.get()),
                      description_entry.get("1.0", "end-1c").strip())
            if game_id is None:
                cursor.execute(
                    "INSERT INTO games (name, platform, playtime, price_paid, completed, "
                    "backlog, started, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", values)
            else:
                cursor.execute(
                    "UPDATE games SET name=?, platform=?, playtime=?, price_paid=?, "
                    "completed=?, backlog=?, started=?, description=? WHERE id=?",
                    values + (game_id,))
            connection.commit()
            modal.destroy()
            refresh_platforms()
            load_games(search_entry.get().strip())

        tk.Button(modal, text="Save Game", command=save,
                  bg=get_setting("accent_color", "#B23A48"), fg="white",
                  relief="flat", padx=18, pady=8).pack(pady=10)
        title_entry.focus_set()

    def add_game_window():
        game_form()

    def edit_game_window():
        selected = game_table.selection()
        if not selected:
            messagebox.showwarning("Select Game", "Select a game in List view first.")
            return
        game_form(int(game_table.item(selected[0], "values")[0]))

    # -------------------------
    # DELETE GAME
    # -------------------------

    def delete_game():

        selected = game_table.selection()


        if not selected:

            messagebox.showwarning(
                "No Game Selected",
                "Please select a game to delete."
            )

            return


        values = game_table.item(
            selected[0],
            "values"
        )

        game_id = values[0]
        game_name = values[1]


        confirm = messagebox.askyesno(
            "Delete Game",
            f"Are you sure you want to delete '{game_name}'?"
        )


        if not confirm:
            return


        cursor.execute("""
        DELETE FROM games
        WHERE id = ?
        """, (
            game_id,
        ))


        connection.commit()

        refresh_platforms()
        load_games()


        messagebox.showinfo(
            "Game Deleted",
            f"'{game_name}' has been deleted."
        )


    # -------------------------
    # GAME BUTTONS
    # -------------------------

    search_button = tk.Button(
        search_frame,
        text="Search",
        command=search_games
    )
    search_button.pack(
        side="left",
        padx=5
    )


    show_all_button = tk.Button(
        search_frame,
        text="Show All",
        command=show_all_games
    )
    show_all_button.pack(
        side="left",
        padx=5
    )


    add_button = tk.Button(
        search_frame,
        text="Add Game",
        command=add_game_window
    )
    add_button.pack(
        side="right",
        padx=5
    )


    edit_button = tk.Button(
        search_frame,
        text="Edit Game",
        command=edit_game_window
    )
    edit_button.pack(
        side="right",
        padx=5
    )


    delete_button = tk.Button(
        search_frame,
        text="Delete Game",
        command=delete_game
    )
    delete_button.pack(
        side="right",
        padx=5
    )


    def status_changed(event=None):
        set_setting("games_status_filter", status_var.get())
        load_games(search_entry.get().strip())

    status_combo.bind("<<ComboboxSelected>>", status_changed)

    def sort_changed(event=None):
        set_setting("games_sort", sort_var.get())
        load_games(search_entry.get().strip())

    sort_combo.bind("<<ComboboxSelected>>", sort_changed)

    def toggle_playing():
        selected = game_table.selection()
        if not selected:
            messagebox.showwarning("Select Game", "Select a game in List view first.")
            return
        game_id = int(game_table.item(selected[0], "values")[0])
        cursor.execute("UPDATE games SET in_progress = CASE WHEN in_progress = 1 "
                       "THEN 0 ELSE 1 END WHERE id = ?", (game_id,))
        connection.commit()
        load_games(search_entry.get().strip())

    playing_button = tk.Button(search_frame, text="Toggle Playing",
                               command=toggle_playing)
    playing_button.pack(side="left", padx=3)

    def platform_changed(event=None):
        set_setting("games_platform_filter", platform_var.get())
        load_games(search_entry.get().strip())

    platform_combo.bind("<<ComboboxSelected>>", platform_changed)

    def clear_filters():
        platform_var.set("All Platforms")
        set_setting("games_platform_filter", "All Platforms")
        status_var.set("All Statuses")
        set_setting("games_status_filter", "All Statuses")
        search_entry.delete(0, tk.END)
        load_games()

    clear_button = tk.Button(search_frame, text="Clear Filters", command=clear_filters)
    # Shared filter panel owns the only visible Clear Filters button.
    # Legacy clear handler retained for compatibility.

    # Double-click only a real table row to edit it.
    def on_table_double_click(event):
        if game_table.identify_region(event.x, event.y) != "cell":
            return
        row_id = game_table.identify_row(event.y)
        if not row_id:
            return
        game_table.selection_set(row_id)
        game_table.focus(row_id)
        if on_open_detail:
            on_open_detail(int(game_table.item(row_id, "values")[0]))
        else:
            edit_game_window()

    game_table.bind("<Double-1>", on_table_double_click)


    # Enter to search
    search_entry.bind(
        "<Return>",
        lambda event: search_games()
    )


    # Load games when window opens
    load_games()
    switch_view(view_mode.get())

    if initial_edit_id is not None:
        for row_id in game_table.get_children():
            values = game_table.item(row_id, "values")
            if values and str(values[0]) == str(initial_edit_id):
                game_table.selection_set(row_id)
                game_table.focus(row_id)
                game_table.see(row_id)
                game_table.after_idle(edit_game_window)
                break

    return games_window
