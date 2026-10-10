"""Optional themed note prompt used by the existing manual timer."""
import tkinter as tk
from window_style import install as polish_dialog
from theme import PANEL, PANEL_ALT, TEXT, MUTED


def ask_session_note(parent, accent, initial=''):
    dialog = tk.Toplevel(parent)
    polish_dialog(dialog)
    dialog.title('Save Manual Session')
    dialog.configure(bg=PANEL)
    dialog.geometry('480x260')
    dialog.transient(parent.winfo_toplevel())
    previous_grab = dialog.grab_current()
    result = {'note': None}
    tk.Label(dialog, text='Session note (optional)', bg=PANEL, fg=TEXT,
             font=('Arial', 14, 'bold')).pack(anchor='w', padx=18, pady=(18, 6))
    tk.Label(dialog, text='Leave blank to save without a note. Cancel keeps your timer.',
             bg=PANEL, fg=MUTED, wraplength=440).pack(anchor='w', padx=18)
    field = tk.Text(dialog, height=4, bg=PANEL_ALT, fg=TEXT, insertbackground=TEXT,
                    relief='flat', wrap='word')
    field.pack(fill='both', expand=True, padx=18, pady=10)
    field.insert('1.0', initial)
    def finish(save=False):
        if save:
            note = field.get('1.0', 'end-1c').strip()
            if len(note) > 2000:
                from tkinter import messagebox
                messagebox.showwarning('Session Note', 'Keep the note to 2,000 characters or fewer.', parent=dialog)
                return
            result['note'] = note
        dialog.destroy()
        if previous_grab is not None:
            try:
                if previous_grab.winfo_exists():previous_grab.grab_set()
            except tk.TclError:pass
    buttons = tk.Frame(dialog, bg=PANEL)
    buttons.pack(fill='x', padx=18, pady=(0, 14))
    tk.Button(buttons, text='Save Session', command=lambda:finish(True), bg=accent,
              fg='white', relief='flat', padx=12, pady=8).pack(side='right')
    tk.Button(buttons, text='Cancel', command=finish, bg=PANEL_ALT, fg=TEXT,
              relief='flat', padx=12, pady=8).pack(side='right', padx=8)
    dialog.protocol('WM_DELETE_WINDOW', finish)
    dialog.bind('<Escape>', lambda event:finish())
    dialog.grab_set();field.focus_set()
    dialog.wait_window()
    return result['note']
