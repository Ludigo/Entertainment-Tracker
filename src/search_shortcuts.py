"""Collection-only shortcuts, removed when that collection page is destroyed."""
import tkinter as tk


def bind_enter(entry,search):
    """Give each search box first chance to handle Enter without global hooks."""
    def submit(event=None):
        if event is not None:
            keysym=getattr(event,'keysym','')
            char=getattr(event,'char','')
            if keysym not in ('Return','KP_Enter','Enter') and char not in ('\r','\n'):
                return None
        search()
        return 'break'
    for sequence in ('<Return>','<KP_Enter>'):
        entry.bind(sequence,submit)
    # A dedicated first bindtag also survives later widget bindings, including
    # generic KeyPress handlers installed during library return restoration.
    tag='ETSearch:'+str(entry)
    tags=entry.bindtags()
    entry.bind_class(tag,'<KeyPress>',submit)
    entry.bindtags((tag,)+tuple(value for value in tags if value!=tag))
    def cleanup(event):
        if event.widget is entry:
            entry.unbind_class(tag,'<KeyPress>')
    entry.bind('<Destroy>',cleanup,add='+')


def install(page,entry,refresh):
    bind_enter(entry,refresh)
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

