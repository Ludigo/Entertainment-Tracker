"""Collection-only shortcuts, removed when that collection page is destroyed."""
import tkinter as tk


def install(page,entry,refresh):
    root=page.winfo_toplevel()
    def focus_search(event=None):
        if not page.winfo_exists() or root.grab_current() is not None:return
        entry.focus_set();entry.selection_range(0,tk.END)
        return 'break'
    def clear_search(event=None):
        if root.grab_current() is not None:return
        entry.delete(0,tk.END);refresh()
        return 'break'
    def clicked_elsewhere(event):
        if event.widget is entry or root.grab_current() is not None:return
        target=event.widget
        def release_search_focus():
            try:
                if not page.winfo_exists() or root.grab_current() is not None or root.focus_get() is not entry:return
                if not target.winfo_exists():return
                # Keep keyboard controls usable; blank areas return focus to the page.
                controls={'Entry','TEntry','Text','Spinbox','TSpinbox','TCombobox',
                          'Treeview','Listbox','Button','TButton','Checkbutton',
                          'TCheckbutton','Radiobutton','TRadiobutton','Scale','TScale'}
                (target if target.winfo_class() in controls else page).focus_set()
            except tk.TclError:pass
        root.after_idle(release_search_focus)
    binding=root.bind('<Control-f>',focus_search,add='+')
    click_binding=root.bind('<Button-1>',clicked_elsewhere,add='+')
    entry.bind('<Escape>',clear_search,add='+')
    def cleanup(event):
        if event.widget is page:
            for sequence,identifier in [('<Control-f>',binding),('<Button-1>',click_binding)]:
                try:root.unbind(sequence,identifier)
                except tk.TclError:pass
    page.bind('<Destroy>',cleanup,add='+')
