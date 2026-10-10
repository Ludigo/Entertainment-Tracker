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
from form_safety import SafeFormModal, FormValidation, required, whole_number, duration


def open_shows(parent, on_open_detail=None, initial_edit_id=None, restore_library=False):

    shows_window = tk.Frame(parent)
    shows_window.pack(fill="both", expand=True)

    heading = tk.Label(
        shows_window,
        text="Shows Library",
        font=("Arial", 20)
    )
    heading.pack(pady=15)
    tk.Button(shows_window, text="Bulk Edit...",
              command=lambda: open_bulk_edit(shows_window, "shows",
                  on_done=lambda: load_shows(search_entry.get())),
              bg=PANEL_ALT, fg=TEXT, relief="flat", padx=12, pady=6).pack(anchor="e", padx=24)


    # -------------------------
    # SEARCH AREA
    # -------------------------

    search_frame = tk.Frame(shows_window, bg="#202329", highlightbackground="#363b44", highlightthickness=1)
    search_frame.pack(fill="x", padx=20, pady=5)

    tk.Label(
        search_frame,
        text="Search:",
        font=("Arial", 11)
    ).pack(side="left")

    search_entry = tk.Entry(
        search_frame,
        font=("Arial", 11),
        width=35
    )
    search_entry.pack(side="left", padx=10)


    # -------------------------
    # TABLE
    # -------------------------

    # Shared filters sit in the same position across all four libraries.
    filters = build_filters(shows_window, "shows", lambda: load_shows(search_entry.get()))

    table_frame = tk.Frame(shows_window)
    table_frame.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=10
    )

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", style="Dark.Vertical.TScrollbar")
    scrollbar.pack(side="right", fill="y")

    columns = (
        "ID",
        "Show",
        "Season",
        "Runtime",
        "Episodes",
        "Reached",
        "Completed",
        "In Progress",
        "Watch Count",
        "Owned",
        "Type",
        "Genre"
    )

    show_table = ttk.Treeview(
        table_frame,
        columns=columns,
        show="headings",
        yscrollcommand=scrollbar.set
    )

    scrollbar.config(command=show_table.yview)

    for column in columns:
        show_table.heading(column, text=column)

    show_table.column("ID", width=40, anchor="center")
    show_table.column("Show", width=220)
    show_table.column("Season", width=65, anchor="center")
    show_table.column("Runtime", width=100, anchor="center")
    show_table.column("Episodes", width=70, anchor="center")
    show_table.column("Reached", width=70, anchor="center")
    show_table.column("Completed", width=80, anchor="center")
    show_table.column("In Progress", width=80, anchor="center")
    show_table.column("Watch Count", width=80, anchor="center")
    show_table.column("Owned", width=60, anchor="center")
    show_table.column("Type", width=100)
    show_table.column("Genre", width=120)

    show_table.pack(fill="both", expand=True)



    # Cover grid / table switch. The grid shares the existing search field.
    def open_grid_detail(item_id):
        if on_open_detail:
            on_open_detail(item_id)

    grid_view = CoverGrid(shows_window, "shows", open_grid_detail)
    view_mode = tk.StringVar(value=get_setting("view_shows", "Covers"))
    def switch_view(mode):
        view_mode.set(mode)
        set_setting("view_shows", mode)
        update_toggle()
        if mode == "Covers":
            table_frame.pack_forget()
            grid_view.pack(fill="both", expand=True, padx=12, pady=8)
            load_shows(search_entry.get())
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
    # LOAD SHOWS
    # -------------------------

    def load_shows(search=""):

        for row in show_table.get_children():
            show_table.delete(row)

        condition, values, ordering = where_clause("shows", search, filters)
        cursor.execute("SELECT * FROM shows WHERE " + condition + " ORDER BY " + ordering, values)
        shows = cursor.fetchall()
        filtered_ids = [row[0] for row in shows]
        filters["count"].configure(text=f"Showing {len(shows)} items")

        for show in shows:

            show_table.insert(
                "",
                "end",
                values=(
                    show[0],
                    show[1],
                    show[2],
                    format_time(show[3]),
                    show[4],
                    show[5],
                    "Yes" if show[6] else "No",
                    "Yes" if show[7] else "No",
                    show[8],
                    "Yes" if show[9] else "No",
                    show[10] or "",
                    show[11] or ""
                )
            )


        if view_mode.get() == "Covers":
            grid_view.set_search(search, filtered_ids=filtered_ids)

    # -------------------------
    # SEARCH
    # -------------------------

    def search_shows():
        load_shows(search_entry.get())


    def show_all_shows():
        search_entry.delete(0, tk.END)
        load_shows()


    # -------------------------
    # SHOW FORM
    # Used for both Add + Edit
    # -------------------------

    def show_form(existing_show=None):

        editing = existing_show is not None

        form_window = SafeFormModal(shows_window)

        if editing:
            form_window.title("Edit Show")
        else:
            form_window.title("Add Show")

        form_window.geometry("450x650")
        form_window.resizable(False, False)

        tk.Label(
            form_window,
            text="Edit Show" if editing else "Add Show",
            font=("Arial", 18)
        ).pack(pady=15)


        # Show name
        tk.Label(
            form_window,
            text="Show Name:"
        ).pack()

        name_entry = tk.Entry(
            form_window,
            width=40
        )
        name_entry.pack(pady=4)


        # Season
        tk.Label(
            form_window,
            text="Season:"
        ).pack()

        season_entry = tk.Entry(
            form_window,
            width=40
        )
        season_entry.pack(pady=4)


        # Runtime
        tk.Label(
            form_window,
            text="Season Runtime (H:MM:SS):"
        ).pack()

        runtime_entry = tk.Entry(
            form_window,
            width=40
        )
        runtime_entry.pack(pady=4)


        # Episode count
        tk.Label(
            form_window,
            text="Episode Count:"
        ).pack()

        episode_count_entry = tk.Entry(
            form_window,
            width=40
        )
        episode_count_entry.pack(pady=4)


        # Episode reached
        tk.Label(
            form_window,
            text="Episode Reached:"
        ).pack()

        episode_reached_entry = tk.Entry(
            form_window,
            width=40
        )
        episode_reached_entry.pack(pady=4)


        # Watch count
        tk.Label(
            form_window,
            text="Watch Count:"
        ).pack()

        watch_count_entry = tk.Entry(
            form_window,
            width=40
        )
        watch_count_entry.pack(pady=4)


        # Type
        tk.Label(
            form_window,
            text="Type:"
        ).pack()

        type_entry = tk.Entry(
            form_window,
            width=40
        )
        type_entry.pack(pady=4)


        # Genre
        tk.Label(
            form_window,
            text="Genre:"
        ).pack()

        genre_entry = tk.Entry(
            form_window,
            width=40
        )
        genre_entry.pack(pady=4)


        # -------------------------
        # CHECKBOXES
        # -------------------------

        checkbox_frame = tk.Frame(form_window)
        checkbox_frame.pack(pady=10)

        completed_var = tk.IntVar()
        progress_var = tk.IntVar()
        owned_var = tk.IntVar()

        tk.Checkbutton(
            checkbox_frame,
            text="Completed",
            variable=completed_var
        ).grid(
            row=0,
            column=0,
            padx=10
        )

        tk.Checkbutton(
            checkbox_frame,
            text="In Progress",
            variable=progress_var
        ).grid(
            row=0,
            column=1,
            padx=10
        )

        tk.Checkbutton(
            checkbox_frame,
            text="Owned",
            variable=owned_var
        ).grid(
            row=0,
            column=2,
            padx=10
        )


        # -------------------------
        # LOAD EXISTING DATA
        # -------------------------

        if editing:

            name_entry.insert(0, existing_show[1])
            season_entry.insert(0, existing_show[2])

            runtime_entry.insert(
                0,
                format_time(existing_show[3])
            )

            episode_count_entry.insert(
                0,
                existing_show[4]
            )

            episode_reached_entry.insert(
                0,
                existing_show[5]
            )

            watch_count_entry.insert(
                0,
                existing_show[8]
            )

            type_entry.insert(
                0,
                existing_show[10] or ""
            )

            genre_entry.insert(
                0,
                existing_show[11] or ""
            )

            completed_var.set(existing_show[6])
            progress_var.set(existing_show[7])
            owned_var.set(existing_show[9])


        # -------------------------
        # SAVE
        # -------------------------

        def save_show():

            if not validation.validate():return

            name = name_entry.get().strip()
            type_text = type_entry.get().strip()
            genre = genre_entry.get().strip()

            if name == "":
                status_label.config(
                    text="Please enter a show name."
                )
                return

            try:
                season = int(season_entry.get())
                episode_count = int(
                    episode_count_entry.get()
                )
                episode_reached = int(
                    episode_reached_entry.get()
                )
                watch_count = int(
                    watch_count_entry.get()
                )

                if (
                    season < 0
                    or episode_count < 0
                    or episode_reached < 0
                    or watch_count < 0
                ):
                    raise ValueError

            except ValueError:
                status_label.config(
                    text="Season, episodes and watch count must be whole numbers."
                )
                return


            if episode_reached > episode_count:
                status_label.config(
                    text="Episode reached cannot exceed episode count."
                )
                return


            try:
                runtime = parse_time(
                    runtime_entry.get().strip()
                )

            except ValueError:
                status_label.config(
                    text="Runtime must use H:MM:SS."
                )
                return


            values = (
                name,
                season,
                runtime,
                episode_count,
                episode_reached,
                completed_var.get(),
                progress_var.get(),
                watch_count,
                owned_var.get(),
                type_text,
                genre
            )


            if editing:

                cursor.execute("""
                UPDATE shows
                SET
                    name = ?,
                    season = ?,
                    runtime = ?,
                    episode_count = ?,
                    episode_reached = ?,
                    completed = ?,
                    in_progress = ?,
                    watch_count = ?,
                    owned = ?,
                    type = ?,
                    genre = ?
                WHERE id = ?
                """, values + (
                    existing_show[0],
                ))

            else:

                cursor.execute("""
                INSERT INTO shows (
                    name,
                    season,
                    runtime,
                    episode_count,
                    episode_reached,
                    completed,
                    in_progress,
                    watch_count,
                    owned,
                    type,
                    genre
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
                """, values)


            connection.commit()
            load_shows()
            form_window.close_saved()


        tk.Button(
            form_window,
            text="Save Changes" if editing else "Save Show",
            width=15,
            command=save_show
        ).pack(pady=8)


        status_label = tk.Label(
            form_window,
            text=""
        )
        status_label.pack()

        form_window.watch([name_entry,season_entry,runtime_entry,episode_count_entry,
                           episode_reached_entry,watch_count_entry,type_entry,genre_entry],
                          [completed_var,progress_var,owned_var])
        def check_episode_progress():
            if int(episode_reached_entry.get())>int(episode_count_entry.get()):
                return episode_reached_entry,'Episode reached cannot exceed episode count.'
        validation=FormValidation(status_label,[(name_entry,required('a show name')),
                   (season_entry,whole_number('Season')),(runtime_entry,duration('Runtime')),
                   (episode_count_entry,whole_number('Episode count')),
                   (episode_reached_entry,whole_number('Episode reached')),
                   (watch_count_entry,whole_number('Watch count'))],check_episode_progress)

        name_entry.focus()


    # -------------------------
    # ADD
    # -------------------------

    def add_show():
        show_form()


    # -------------------------
    # EDIT
    # -------------------------

    def edit_show():
        selected = show_table.selection()
        if not selected:
            messagebox.showwarning('No Show Selected', 'Please select a show to edit.')
            return
        item_id = show_table.item(selected[0], 'values')[0]
        from rich_details import open_rich_editor
        open_rich_editor(shows_window, 'shows', item_id, get_setting('accent_color', '#B23A48'),
                         lambda: load_shows(search_entry.get()))


    # -------------------------
    # DELETE
    # -------------------------

    def delete_show():

        selected = show_table.selection()

        if not selected:
            messagebox.showwarning(
                "No Show Selected",
                "Please select a show to delete."
            )
            return

        values = show_table.item(
            selected[0],
            "values"
        )

        show_id = values[0]
        show_name = values[1]
        season = values[2]

        confirm = messagebox.askyesno(
            "Delete Show",
            f"Delete '{show_name}' Season {season}?"
        )

        if not confirm:
            return

        cursor.execute("""
        DELETE FROM shows
        WHERE id = ?
        """, (show_id,))

        connection.commit()
        load_shows()


    # -------------------------
    # BUTTONS
    # -------------------------

    tk.Button(
        search_frame,
        text="Search",
        command=search_shows
    ).pack(side="left", padx=5)

    tk.Button(
        search_frame,
        text="Show All",
        command=show_all_shows
    ).pack(side="left", padx=5)

    tk.Button(
        search_frame,
        text="Add Show",
        command=add_show
    ).pack(side="right", padx=5)

    tk.Button(
        search_frame,
        text="Edit Show",
        command=edit_show
    ).pack(side="right", padx=5)

    tk.Button(
        search_frame,
        text="Delete Show",
        command=delete_show
    ).pack(side="right", padx=5)


    # Double-click only a real table row to edit it.
    def on_table_double_click(event):
        if show_table.identify_region(event.x, event.y) != "cell":
            return
        row_id = show_table.identify_row(event.y)
        if not row_id:
            return
        show_table.selection_set(row_id)
        show_table.focus(row_id)
        if on_open_detail:
            on_open_detail(int(show_table.item(row_id, "values")[0]))
        else:
            edit_show()

    show_table.bind("<Double-1>", on_table_double_click)

    from search_shortcuts import install as install_search_shortcuts
    install_search_shortcuts(shows_window,search_entry,lambda:load_shows(search_entry.get()))

    search_entry.bind(
        "<Return>",
        lambda event: search_shows()
    )


    load_shows()
    switch_view(view_mode.get())

    from library_return import install as install_return_context
    on_open_detail=install_return_context(shows_window,'shows',on_open_detail,grid_view,show_table,
                                        search_entry,view_mode,switch_view,load_shows,filters,
                                        extra_vars=None,restore=restore_library)

    if initial_edit_id is not None:
        for row_id in show_table.get_children():
            values = show_table.item(row_id, "values")
            if values and str(values[0]) == str(initial_edit_id):
                show_table.selection_set(row_id)
                show_table.focus(row_id)
                show_table.see(row_id)
                show_table.after_idle(edit_show)
                break

    return shows_window
