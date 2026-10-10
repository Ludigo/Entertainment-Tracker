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


def open_books(parent, on_open_detail=None, initial_edit_id=None, restore_library=False):

    books_window = tk.Frame(parent)
    books_window.pack(fill="both", expand=True)

    heading = tk.Label(
        books_window,
        text="Books Library",
        font=("Arial", 20)
    )
    heading.pack(pady=15)
    tk.Button(books_window, text="Bulk Edit...",
              command=lambda: open_bulk_edit(books_window, "books",
                  on_done=lambda: load_books(search_entry.get())),
              bg=PANEL_ALT, fg=TEXT, relief="flat", padx=12, pady=6).pack(anchor="e", padx=24)


    # -------------------------
    # SEARCH AREA
    # -------------------------

    search_frame = tk.Frame(books_window, bg="#202329", highlightbackground="#363b44", highlightthickness=1)
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
    filters = build_filters(books_window, "books", lambda: load_books(search_entry.get()))

    table_frame = tk.Frame(books_window)
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
        "Book",
        "Page Count",
        "Reading Time",
        "Completed",
        "In Progress",
        "Read Count",
        "Owned",
        "Type",
        "Genre"
    )

    book_table = ttk.Treeview(
        table_frame,
        columns=columns,
        show="headings",
        yscrollcommand=scrollbar.set
    )

    scrollbar.config(command=book_table.yview)

    for column in columns:
        book_table.heading(column, text=column)

    book_table.column("ID", width=40, anchor="center")
    book_table.column("Book", width=250)
    book_table.column("Page Count", width=80, anchor="center")
    book_table.column("Reading Time", width=110, anchor="center")
    book_table.column("Completed", width=80, anchor="center")
    book_table.column("In Progress", width=80, anchor="center")
    book_table.column("Read Count", width=80, anchor="center")
    book_table.column("Owned", width=60, anchor="center")
    book_table.column("Type", width=100)
    book_table.column("Genre", width=120)

    book_table.pack(fill="both", expand=True)



    # Cover grid / table switch. The grid shares the existing search field.
    def open_grid_detail(item_id):
        if on_open_detail:
            on_open_detail(item_id)

    grid_view = CoverGrid(books_window, "books", open_grid_detail)
    view_mode = tk.StringVar(value=get_setting("view_books", "Covers"))
    def switch_view(mode):
        view_mode.set(mode)
        set_setting("view_books", mode)
        update_toggle()
        if mode == "Covers":
            table_frame.pack_forget()
            grid_view.pack(fill="both", expand=True, padx=12, pady=8)
            load_books(search_entry.get())
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
    # LOAD BOOKS
    # -------------------------

    def load_books(search=""):

        for row in book_table.get_children():
            book_table.delete(row)

        condition, values, ordering = where_clause("books", search, filters)
        cursor.execute("SELECT * FROM books WHERE " + condition + " ORDER BY " + ordering, values)
        books = cursor.fetchall()
        filtered_ids = [row[0] for row in books]
        filters["count"].configure(text=f"Showing {len(books)} items")

        for book in books:

            book_table.insert(
                "",
                "end",
                values=(
                    book[0],
                    book[1],
                    book[9],
                    format_time(book[2]),
                    "Yes" if book[3] else "No",
                    "Yes" if book[4] else "No",
                    book[5],
                    "Yes" if book[6] else "No",
                    book[7] or "",
                    book[8] or ""
                )
            )


        if view_mode.get() == "Covers":
            grid_view.set_search(search, filtered_ids=filtered_ids)

    # -------------------------
    # SEARCH
    # -------------------------

    def search_books():
        load_books(search_entry.get())


    def show_all_books():
        search_entry.delete(0, tk.END)
        load_books()


    # -------------------------
    # BOOK FORM
    # -------------------------

    def book_form(existing_book=None):

        editing = existing_book is not None

        form_window = SafeFormModal(books_window)

        form_window.title(
            "Edit Book" if editing else "Add Book"
        )

        form_window.geometry("450x550")
        form_window.resizable(False, False)

        tk.Label(
            form_window,
            text="Edit Book" if editing else "Add Book",
            font=("Arial", 18)
        ).pack(pady=15)


        # Book name
        tk.Label(
            form_window,
            text="Book Name:"
        ).pack()

        name_entry = tk.Entry(
            form_window,
            width=40
        )
        name_entry.pack(pady=5)


        # Page count
        tk.Label(
            form_window,
            text="Page Count:"
        ).pack()

        page_count_entry = tk.Entry(
            form_window,
            width=40
        )
        page_count_entry.pack(pady=5)


        # Reading time
        tk.Label(
            form_window,
            text="Reading Time (H:MM:SS):"
        ).pack()

        reading_time_entry = tk.Entry(
            form_window,
            width=40
        )
        reading_time_entry.pack(pady=5)


        # Read count
        tk.Label(
            form_window,
            text="Read Count:"
        ).pack()

        read_count_entry = tk.Entry(
            form_window,
            width=40
        )
        read_count_entry.pack(pady=5)


        # Type
        tk.Label(
            form_window,
            text="Type:"
        ).pack()

        type_entry = tk.Entry(
            form_window,
            width=40
        )
        type_entry.pack(pady=5)


        # Genre
        tk.Label(
            form_window,
            text="Genre:"
        ).pack()

        genre_entry = tk.Entry(
            form_window,
            width=40
        )
        genre_entry.pack(pady=5)


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
        # LOAD EXISTING BOOK
        # -------------------------

        if editing:

            name_entry.insert(
                0,
                existing_book[1]
            )

            page_count_entry.insert(
                0,
                existing_book[9]
            )

            reading_time_entry.insert(
                0,
                format_time(existing_book[2])
            )

            read_count_entry.insert(
                0,
                existing_book[5]
            )

            type_entry.insert(
                0,
                existing_book[7] or ""
            )

            genre_entry.insert(
                0,
                existing_book[8] or ""
            )

            completed_var.set(
                existing_book[3]
            )

            progress_var.set(
                existing_book[4]
            )

            owned_var.set(
                existing_book[6]
            )


        # -------------------------
        # SAVE BOOK
        # -------------------------

        def save_book():

            if not validation.validate():return

            name = name_entry.get().strip()

            type_text = (
                type_entry
                .get()
                .strip()
            )

            genre = (
                genre_entry
                .get()
                .strip()
            )


            # Book name
            if name == "":

                status_label.config(
                    text="Please enter a book name."
                )

                return


            # Page count
            try:

                page_count = int(
                    page_count_entry
                    .get()
                    .strip()
                )

                if page_count < 0:
                    raise ValueError

            except ValueError:

                status_label.config(
                    text="Page count must be a whole number."
                )

                return


            # Reading time
            try:

                reading_time = parse_time(
                    reading_time_entry
                    .get()
                    .strip()
                )

            except ValueError:

                status_label.config(
                    text="Reading time must use H:MM:SS."
                )

                return


            # Read count
            try:

                read_count = int(
                    read_count_entry
                    .get()
                    .strip()
                )

                if read_count < 0:
                    raise ValueError

            except ValueError:

                status_label.config(
                    text="Read count must be a whole number."
                )

                return


            values = (
                name,
                reading_time,
                completed_var.get(),
                progress_var.get(),
                read_count,
                owned_var.get(),
                type_text,
                genre,
                page_count
            )


            # -------------------------
            # UPDATE EXISTING BOOK
            # -------------------------

            if editing:

                cursor.execute("""
                UPDATE books
                SET
                    name = ?,
                    reading_time = ?,
                    completed = ?,
                    in_progress = ?,
                    read_count = ?,
                    owned = ?,
                    type = ?,
                    genre = ?,
                    page_count = ?
                WHERE id = ?
                """, values + (
                    existing_book[0],
                ))


            # -------------------------
            # ADD NEW BOOK
            # -------------------------

            else:

                cursor.execute("""
                INSERT INTO books (
                    name,
                    reading_time,
                    completed,
                    in_progress,
                    read_count,
                    owned,
                    type,
                    genre,
                    page_count
                )
                VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                """, values)


            connection.commit()

            load_books()

            form_window.close_saved()


        tk.Button(
            form_window,
            text="Save Changes" if editing else "Save Book",
            width=15,
            command=save_book
        ).pack(pady=8)


        status_label = tk.Label(
            form_window,
            text=""
        )
        status_label.pack()


        form_window.watch([name_entry,page_count_entry,reading_time_entry,read_count_entry,type_entry,genre_entry],
                          [completed_var,progress_var,owned_var])
        validation=FormValidation(status_label,[(name_entry,required('a book name')),
                   (page_count_entry,whole_number('Page count')),(reading_time_entry,duration('Reading time')),
                   (read_count_entry,whole_number('Read count'))])

        name_entry.focus()


    # -------------------------
    # ADD BOOK
    # -------------------------

    def add_book():
        book_form()


    # -------------------------
    # EDIT BOOK
    # -------------------------

    def edit_book():
        selected = book_table.selection()
        if not selected:
            messagebox.showwarning('No Book Selected', 'Please select a book to edit.')
            return
        item_id = book_table.item(selected[0], 'values')[0]
        from rich_details import open_rich_editor
        open_rich_editor(books_window, 'books', item_id, get_setting('accent_color', '#B23A48'),
                         lambda: load_books(search_entry.get()))


    # -------------------------
    # DELETE BOOK
    # -------------------------

    def delete_book():

        selected = book_table.selection()

        if not selected:

            messagebox.showwarning(
                "No Book Selected",
                "Please select a book to delete."
            )

            return


        values = book_table.item(
            selected[0],
            "values"
        )

        book_id = values[0]
        book_name = values[1]


        confirm = messagebox.askyesno(
            "Delete Book",
            f"Delete '{book_name}'?"
        )


        if not confirm:
            return


        cursor.execute("""
        DELETE FROM books
        WHERE id = ?
        """, (
            book_id,
        ))


        connection.commit()

        load_books()


        messagebox.showinfo(
            "Book Deleted",
            f"'{book_name}' has been deleted."
        )


    # -------------------------
    # BUTTONS
    # -------------------------

    tk.Button(
        search_frame,
        text="Search",
        command=search_books
    ).pack(
        side="left",
        padx=5
    )


    tk.Button(
        search_frame,
        text="Show All",
        command=show_all_books
    ).pack(
        side="left",
        padx=5
    )


    tk.Button(
        search_frame,
        text="Add Book",
        command=add_book
    ).pack(
        side="right",
        padx=5
    )


    tk.Button(
        search_frame,
        text="Edit Book",
        command=edit_book
    ).pack(
        side="right",
        padx=5
    )


    tk.Button(
        search_frame,
        text="Delete Book",
        command=delete_book
    ).pack(
        side="right",
        padx=5
    )


    # Double-click only a real table row to edit it.
    def on_table_double_click(event):
        if book_table.identify_region(event.x, event.y) != "cell":
            return
        row_id = book_table.identify_row(event.y)
        if not row_id:
            return
        book_table.selection_set(row_id)
        book_table.focus(row_id)
        if on_open_detail:
            on_open_detail(int(book_table.item(row_id, "values")[0]))
        else:
            edit_book()

    book_table.bind("<Double-1>", on_table_double_click)


    from search_shortcuts import install as install_search_shortcuts
    install_search_shortcuts(books_window,search_entry,lambda:load_books(search_entry.get()))

    # Enter to search
    search_entry.bind(
        "<Return>",
        lambda event: search_books()
    )


    # Load books
    load_books()
    switch_view(view_mode.get())

    from library_return import install as install_return_context
    on_open_detail=install_return_context(books_window,'books',on_open_detail,grid_view,book_table,
                                        search_entry,view_mode,switch_view,load_books,filters,
                                        extra_vars=None,restore=restore_library)

    if initial_edit_id is not None:
        for row_id in book_table.get_children():
            values = book_table.item(row_id, "values")
            if values and str(values[0]) == str(initial_edit_id):
                book_table.selection_set(row_id)
                book_table.focus(row_id)
                book_table.see(row_id)
                book_table.after_idle(edit_book)
                break

    return books_window
