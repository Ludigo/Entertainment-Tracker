import tkinter as tk

from database import get_setting
from theme import PANEL, PANEL_ALT, TEXT, MUTED, BORDER, DEFAULT_ACCENT


class ModalFrame(tk.Frame):
    """A centred, themed, application-wide modal card."""
    def __init__(self, parent):
        self.host = parent.winfo_toplevel()
        self.accent = get_setting("accent_color", DEFAULT_ACCENT)
        self._closed = False

        # Application-wide dim layer. It sits above both the sidebar and page.
        self.overlay = tk.Frame(self.host, bg="#101216")
        self.overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.overlay.lift()

        super().__init__(
            self.overlay,
            bg=PANEL,
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=22,
            pady=16,
        )
        self._width = 450
        self._height = 500
        self.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
            width=self._width,
            height=self._height,
        )
        self.lift()

        # Visible Cancel control for every Add/Edit modal without each library
        # having to implement its own copy.
        self.cancel_button = tk.Button(
            self,
            text="Cancel",
            command=self.destroy,
            bg=PANEL_ALT,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
        )
        self.cancel_button.place(relx=1.0, x=-8, y=8, anchor="ne")

        try:
            self.grab_set()
        except tk.TclError:
            pass

        # Bind Escape on the ROOT window. Entry widgets receive keyboard focus,
        # so binding Escape only to this Frame does not reliably fire.
        self._escape_binding = self.host.bind(
            "<Escape>", self._escape_pressed, add="+"
        )

        # Forms create their widgets after ModalFrame.__init__ returns. Run the
        # styling pass a few times during that short construction period so all
        # labels, entries, checkboxes and buttons inherit the modal palette.
        self.after_idle(self._finish_setup)
        self.after(40, self._style_children)
        self.after(120, self._style_children)

    def _escape_pressed(self, _event=None):
        self.destroy()
        return "break"

    def _finish_setup(self):
        self._style_children()
        try:
            # Let the form's first Entry take focus if it already requested it.
            focused = self.focus_get()
            if focused is None or focused == self.host:
                self.focus_set()
        except tk.TclError:
            pass

    def _style_children(self, widget=None):
        if self._closed:
            return
        if widget is None:
            widget = self

        for child in widget.winfo_children():
            # Leave the universal Cancel button with its explicit styling.
            if child is self.cancel_button:
                continue
            try:
                if isinstance(child, (tk.Frame, tk.LabelFrame)):
                    child.configure(bg=PANEL)
                elif isinstance(child, tk.Label):
                    child.configure(bg=PANEL, fg=TEXT)
                elif isinstance(child, tk.Entry):
                    child.configure(
                        bg=PANEL_ALT,
                        fg=TEXT,
                        insertbackground=TEXT,
                        selectbackground=self.accent,
                        selectforeground="white",
                        relief="flat",
                        bd=0,
                        highlightthickness=1,
                        highlightbackground=BORDER,
                        highlightcolor=self.accent,
                    )
                elif isinstance(child, tk.Checkbutton):
                    child.configure(
                        bg=PANEL,
                        fg=TEXT,
                        selectcolor=PANEL_ALT,
                        activebackground=PANEL,
                        activeforeground=TEXT,
                        highlightthickness=0,
                    )
                elif isinstance(child, tk.Button):
                    child.configure(
                        bg=PANEL_ALT,
                        fg=TEXT,
                        activebackground=self.accent,
                        activeforeground="white",
                        relief="flat",
                        bd=0,
                        cursor="hand2",
                    )
            except tk.TclError:
                pass
            self._style_children(child)

    def title(self, _text):
        # Existing forms already draw their own visible heading.
        pass

    def geometry(self, geometry_text):
        try:
            size = geometry_text.split("+")[0]
            width, height = size.lower().split("x", 1)
            self._width = int(width)
            self._height = int(height)
            self.place_configure(width=self._width, height=self._height)
        except (ValueError, AttributeError):
            pass

    def resizable(self, *_args):
        pass

    def destroy(self):
        if self._closed:
            return
        self._closed = True

        try:
            if self._escape_binding:
                self.host.unbind("<Escape>", self._escape_binding)
        except tk.TclError:
            pass

        try:
            if self.grab_current() == self:
                self.grab_release()
        except tk.TclError:
            pass

        try:
            self.overlay.destroy()
        except tk.TclError:
            pass


class _AppMessagebox:
    def _root(self):
        return tk._default_root

    def _message(self, title, message, kind="info"):
        parent = self._root()
        if parent is None:
            return

        modal = ModalFrame(parent)
        modal.geometry("430x230")
        # Message cards already have an OK action, so the generic Cancel button
        # would be redundant here.
        modal.cancel_button.place_forget()

        tk.Label(
            modal,
            text=title,
            font=("Arial", 18, "bold"),
            bg=PANEL,
            fg=TEXT,
        ).pack(anchor="w", pady=(10, 12))

        tk.Label(
            modal,
            text=message,
            font=("Arial", 11),
            wraplength=360,
            justify="left",
            bg=PANEL,
            fg=MUTED,
        ).pack(anchor="w", fill="x")

        tk.Button(
            modal,
            text="OK",
            command=modal.destroy,
            bg=PANEL_ALT,
            fg=TEXT,
            activebackground=modal.accent,
            activeforeground="white",
            relief="flat",
            padx=22,
            pady=8,
            cursor="hand2",
        ).pack(side="bottom", anchor="e", pady=(18, 4))

    def showwarning(self, title, message):
        self._message(title, message, "warning")

    def showerror(self, title, message):
        self._message(title, message, "error")

    def showinfo(self, title, message):
        self._message(title, message, "info")

    def askyesno(self, title, message):
        parent = self._root()
        if parent is None:
            return False

        result = tk.BooleanVar(master=parent, value=False)
        finished = tk.BooleanVar(master=parent, value=False)
        modal = ModalFrame(parent)
        modal.geometry("460x250")
        modal.cancel_button.place_forget()

        tk.Label(
            modal,
            text=title,
            font=("Arial", 18, "bold"),
            bg=PANEL,
            fg=TEXT,
        ).pack(anchor="w", pady=(10, 12))

        tk.Label(
            modal,
            text=message,
            font=("Arial", 11),
            wraplength=390,
            justify="left",
            bg=PANEL,
            fg=MUTED,
        ).pack(anchor="w", fill="x")

        buttons = tk.Frame(modal, bg=PANEL)
        buttons.pack(side="bottom", fill="x", pady=(18, 4))

        def finish(value):
            result.set(value)
            finished.set(True)
            modal.destroy()

        tk.Button(
            buttons,
            text="Cancel",
            command=lambda: finish(False),
            bg=PANEL_ALT,
            fg=TEXT,
            activebackground=BORDER,
            activeforeground="white",
            relief="flat",
            padx=18,
            pady=8,
            cursor="hand2",
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            buttons,
            text="Delete",
            command=lambda: finish(True),
            bg="#8f3340",
            fg="white",
            activebackground="#a63b49",
            activeforeground="white",
            relief="flat",
            padx=18,
            pady=8,
            cursor="hand2",
        ).pack(side="right")

        # Override the generic Escape action so askyesno returns False cleanly.
        try:
            if modal._escape_binding:
                modal.host.unbind("<Escape>", modal._escape_binding)
        except tk.TclError:
            pass
        modal._escape_binding = modal.host.bind(
            "<Escape>", lambda event: (finish(False), "break")[1], add="+"
        )

        parent.wait_variable(finished)
        return result.get()


app_messagebox = _AppMessagebox()
