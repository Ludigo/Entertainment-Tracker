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


def open_movies(parent, on_open_detail=None, initial_edit_id=None):

    movies_window = tk.Frame(parent)
    movies_window.pack(fill="both", expand=True)


    # -------------------------
    # HEADING
    # -------------------------

    heading = tk.Label(
        movies_window,
        text="Movie Library",
        font=("Arial", 20)
    )
    heading.pack(pady=15)
    tk.Button(movies_window, text="Bulk Edit...",
              command=lambda: open_bulk_edit(movies_window, "movies",
                  on_done=lambda: load_movies(search_entry.get())),
              bg=PANEL_ALT, fg=TEXT, relief="flat", padx=12, pady=6).pack(anchor="e", padx=24)


    # -------------------------
    # SEARCH AREA
    # -------------------------

    search_frame = tk.Frame(movies_window, bg="#202329", highlightbackground="#363b44", highlightthickness=1)
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


    # -------------------------
    # TABLE AREA
    # -------------------------

    # Shared filters sit in the same position across all four libraries.
    filters = build_filters(movies_window, "movies", lambda: load_movies(search_entry.get()))

    table_frame = tk.Frame(movies_window)
    table_frame.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=10
    )

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", style="Dark.Vertical.TScrollbar")
    scrollbar.pack(
        side="right",
        fill="y"
    )

    movie_table = ttk.Treeview(
        table_frame,
        columns=(
            "ID",
            "Movie",
            "Runtime",
            "Watch Count"
        ),
        show="headings",
        yscrollcommand=scrollbar.set
    )

    scrollbar.config(
        command=movie_table.yview
    )

    movie_table.heading(
        "ID",
        text="ID"
    )

    movie_table.heading(
        "Movie",
        text="Movie"
    )

    movie_table.heading(
        "Runtime",
        text="Runtime"
    )

    movie_table.heading(
        "Watch Count",
        text="Watch Count"
    )

    movie_table.column(
        "ID",
        width=50,
        anchor="center"
    )

    movie_table.column(
        "Movie",
        width=400
    )

    movie_table.column(
        "Runtime",
        width=150,
        anchor="center"
    )

    movie_table.column(
        "Watch Count",
        width=120,
        anchor="center"
    )

    movie_table.pack(
        fill="both",
        expand=True
    )



    # Cover grid / table switch. The grid shares the existing search field.
    def open_grid_detail(item_id):
        if on_open_detail:
            on_open_detail(item_id)

    grid_view = CoverGrid(movies_window, "movies", open_grid_detail)
    view_mode = tk.StringVar(value=get_setting("view_movies", "Covers"))
    def switch_view(mode):
        view_mode.set(mode)
        set_setting("view_movies", mode)
        update_toggle()
        if mode == "Covers":
            table_frame.pack_forget()
            grid_view.pack(fill="both", expand=True, padx=12, pady=8)
            load_movies(search_entry.get())
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
    # LOAD MOVIES
    # -------------------------

    def load_movies(search=""):

        # Clear current table
        for row in movie_table.get_children():
            movie_table.delete(row)

        # Get movies from database
        condition, values, ordering = where_clause("movies", search, filters)
        condition, values, ordering = where_clause("movies", search, filters)
        cursor.execute("SELECT * FROM movies WHERE " + condition + " ORDER BY " + ordering, values)
        movies = cursor.fetchall()
        filtered_ids = [row[0] for row in movies]
        filters["count"].configure(text=f"Showing {len(movies)} items")
        filtered_ids = [row[0] for row in movies]
        filters["count"].configure(text=f"Showing {len(movies)} items")

        # Add movies to table
        for movie in movies:

            movie_table.insert(
                "",
                "end",
                values=(
                    movie[0],
                    movie[1],
                    format_time(movie[2]),
                    movie[3]
                )
            )


        if view_mode.get() == "Covers":
            grid_view.set_search(search, filtered_ids=filtered_ids)

    # -------------------------
    # SEARCH MOVIES
    # -------------------------

    def search_movies():

        search_text = search_entry.get()

        load_movies(search_text)


    def show_all_movies():

        search_entry.delete(
            0,
            tk.END
        )

        load_movies()


    # -------------------------
    # ADD MOVIE
    # -------------------------

    def add_movie_window():

        add_window = ModalFrame(
            movies_window
        )

        add_window.title("Add Movie")
        add_window.geometry("400x350")
        add_window.resizable(
            False,
            False
        )


        heading = tk.Label(
            add_window,
            text="Add Movie",
            font=("Arial", 18)
        )
        heading.pack(pady=15)


        # Movie name
        tk.Label(
            add_window,
            text="Movie Name:"
        ).pack()

        name_entry = tk.Entry(
            add_window,
            width=40
        )
        name_entry.pack(pady=5)


        # Runtime
        tk.Label(
            add_window,
            text="Runtime (H:MM:SS):"
        ).pack()

        runtime_entry = tk.Entry(
            add_window,
            width=40
        )
        runtime_entry.pack(pady=5)


        # Watch count
        tk.Label(
            add_window,
            text="Watch Count:"
        ).pack()

        watch_count_entry = tk.Entry(
            add_window,
            width=40
        )
        watch_count_entry.pack(pady=5)


        # -------------------------
        # SAVE MOVIE
        # -------------------------

        def save_movie():

            name = name_entry.get().strip()

            runtime_text = (
                runtime_entry
                .get()
                .strip()
            )

            watch_count_text = (
                watch_count_entry
                .get()
                .strip()
            )


            # Check movie name
            if name == "":

                status_label.config(
                    text="Please enter a movie name."
                )

                return


            # Check runtime
            try:

                runtime = parse_time(
                    runtime_text
                )

            except ValueError:

                status_label.config(
                    text="Runtime must use H:MM:SS."
                )

                return


            # Check watch count
            try:

                watch_count = int(
                    watch_count_text
                )

                if watch_count < 0:

                    status_label.config(
                        text="Watch count cannot be negative."
                    )

                    return

            except ValueError:

                status_label.config(
                    text="Watch count must be a whole number."
                )

                return


            # Add movie to database
            cursor.execute("""
            INSERT INTO movies (
                name,
                runtime,
                watch_count
            )
            VALUES (?, ?, ?)
            """, (
                name,
                runtime,
                watch_count
            ))

            connection.commit()

            # Refresh table
            load_movies()

            # Close Add Movie
            add_window.destroy()


        save_button = tk.Button(
            add_window,
            text="Save Movie",
            width=15,
            command=save_movie
        )
        save_button.pack(pady=10)


        status_label = tk.Label(
            add_window,
            text=""
        )
        status_label.pack()


        name_entry.focus()


    # -------------------------
    # EDIT MOVIE
    # -------------------------

    def edit_movie_window():

        selected = movie_table.selection()


        if not selected:

            messagebox.showwarning(
                "No Movie Selected",
                "Please select a movie to edit."
            )

            return


        values = movie_table.item(
            selected[0],
            "values"
        )

        movie_id = values[0]


        # Get full movie from database
        cursor.execute("""
        SELECT * FROM movies
        WHERE id = ?
        """, (
            movie_id,
        ))

        movie = cursor.fetchone()


        if not movie:

            messagebox.showerror(
                "Error",
                "Movie could not be found in the database."
            )

            return


        edit_window = ModalFrame(
            movies_window
        )

        edit_window.title("Edit Movie")
        edit_window.geometry("400x350")
        edit_window.resizable(
            False,
            False
        )


        heading = tk.Label(
            edit_window,
            text="Edit Movie",
            font=("Arial", 18)
        )
        heading.pack(pady=15)


        # Movie name
        tk.Label(
            edit_window,
            text="Movie Name:"
        ).pack()

        name_entry = tk.Entry(
            edit_window,
            width=40
        )
        name_entry.pack(pady=5)

        name_entry.insert(
            0,
            movie[1]
        )


        # Runtime
        tk.Label(
            edit_window,
            text="Runtime (H:MM:SS):"
        ).pack()

        runtime_entry = tk.Entry(
            edit_window,
            width=40
        )
        runtime_entry.pack(pady=5)

        runtime_entry.insert(
            0,
            format_time(movie[2])
        )


        # Watch count
        tk.Label(
            edit_window,
            text="Watch Count:"
        ).pack()

        watch_count_entry = tk.Entry(
            edit_window,
            width=40
        )
        watch_count_entry.pack(pady=5)

        watch_count_entry.insert(
            0,
            str(movie[3])
        )


        # -------------------------
        # SAVE CHANGES
        # -------------------------

        def save_changes():

            name = (
                name_entry
                .get()
                .strip()
            )

            runtime_text = (
                runtime_entry
                .get()
                .strip()
            )

            watch_count_text = (
                watch_count_entry
                .get()
                .strip()
            )


            if name == "":

                status_label.config(
                    text="Please enter a movie name."
                )

                return


            # Runtime
            try:

                runtime = parse_time(
                    runtime_text
                )

            except ValueError:

                status_label.config(
                    text="Runtime must use H:MM:SS."
                )

                return


            # Watch count
            try:

                watch_count = int(
                    watch_count_text
                )

                if watch_count < 0:

                    status_label.config(
                        text="Watch count cannot be negative."
                    )

                    return

            except ValueError:

                status_label.config(
                    text="Watch count must be a whole number."
                )

                return


            # Update database
            cursor.execute("""
            UPDATE movies
            SET
                name = ?,
                runtime = ?,
                watch_count = ?
            WHERE id = ?
            """, (
                name,
                runtime,
                watch_count,
                movie_id
            ))

            connection.commit()

            load_movies()

            edit_window.destroy()


        save_button = tk.Button(
            edit_window,
            text="Save Changes",
            width=15,
            command=save_changes
        )
        save_button.pack(pady=10)


        status_label = tk.Label(
            edit_window,
            text=""
        )
        status_label.pack()


        name_entry.focus()


    # -------------------------
    # DELETE MOVIE
    # -------------------------

    def delete_movie():

        selected = movie_table.selection()


        if not selected:

            messagebox.showwarning(
                "No Movie Selected",
                "Please select a movie to delete."
            )

            return


        values = movie_table.item(
            selected[0],
            "values"
        )

        movie_id = values[0]
        movie_name = values[1]


        confirm = messagebox.askyesno(
            "Delete Movie",
            f"Are you sure you want to delete '{movie_name}'?"
        )


        if not confirm:
            return


        cursor.execute("""
        DELETE FROM movies
        WHERE id = ?
        """, (
            movie_id,
        ))

        connection.commit()

        load_movies()


        messagebox.showinfo(
            "Movie Deleted",
            f"'{movie_name}' has been deleted."
        )


    # -------------------------
    # MOVIE BUTTONS
    # -------------------------

    search_button = tk.Button(
        search_frame,
        text="Search",
        command=search_movies
    )
    search_button.pack(
        side="left",
        padx=5
    )


    show_all_button = tk.Button(
        search_frame,
        text="Show All",
        command=show_all_movies
    )
    show_all_button.pack(
        side="left",
        padx=5
    )


    add_button = tk.Button(
        search_frame,
        text="Add Movie",
        command=add_movie_window
    )
    add_button.pack(
        side="right",
        padx=5
    )


    edit_button = tk.Button(
        search_frame,
        text="Edit Movie",
        command=edit_movie_window
    )
    edit_button.pack(
        side="right",
        padx=5
    )


    delete_button = tk.Button(
        search_frame,
        text="Delete Movie",
        command=delete_movie
    )
    delete_button.pack(
        side="right",
        padx=5
    )


    # Double-click only a real table row to edit it.
    def on_table_double_click(event):
        if movie_table.identify_region(event.x, event.y) != "cell":
            return
        row_id = movie_table.identify_row(event.y)
        if not row_id:
            return
        movie_table.selection_set(row_id)
        movie_table.focus(row_id)
        if on_open_detail:
            on_open_detail(int(movie_table.item(row_id, "values")[0]))
        else:
            edit_movie_window()

    movie_table.bind("<Double-1>", on_table_double_click)


    # Enter to search
    search_entry.bind(
        "<Return>",
        lambda event: search_movies()
    )


    # Load movies when window opens
    load_movies()
    switch_view(view_mode.get())

    if initial_edit_id is not None:
        for row_id in movie_table.get_children():
            values = movie_table.item(row_id, "values")
            if values and str(values[0]) == str(initial_edit_id):
                movie_table.selection_set(row_id)
                movie_table.focus(row_id)
                movie_table.see(row_id)
                movie_table.after_idle(edit_movie_window)
                break

    return movies_window
