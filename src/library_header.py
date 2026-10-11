"""Consistent library chrome using each library's existing action callbacks."""
import tkinter as tk
from tkinter import ttk
from database import get_setting
from theme import PANEL_ALT,TEXT,MUTED,BORDER

def polish(parent,search,tools,kind,view_mode):
    accent=get_setting('accent_color','#B23A48')
    secondary=[];primary=None;view=None
    for child in parent.winfo_children():
        if isinstance(child,tk.Button) and str(child.cget('text')).startswith('Bulk Edit'):
            secondary.append(('Bulk Edit…',child.invoke));child.pack_forget()
    for child in search.winfo_children():
        if isinstance(child,tk.Button):
            label=str(child.cget('text'))
            if label.startswith(('Delete ','Edit ')) or label=='Toggle Playing':
                secondary.append((label,child.invoke));child.pack_forget()
            elif label.startswith('Add '):primary=child
            elif label in ('Search','Show All'):
                child.configure(font=('Arial',10),padx=12,pady=6)
        elif isinstance(child,tk.Entry) and not isinstance(child,ttk.Combobox):
            child.configure(width=35,font=('Arial',11))
            child.pack_configure(padx=10,pady=4)
        elif isinstance(child,tk.Frame):
            if any(isinstance(w,tk.Button) and ('List' in str(w.cget('text')) or 'Covers' in str(w.cget('text'))) for w in child.winfo_children()):view=child
    for child in tools.winfo_children():
        if isinstance(child,tk.Button):
            label=str(child.cget('text'))
            if label.startswith('Export'):secondary.append(('Export Filtered CSV…',child.invoke));child.pack_forget()
            else:child.configure(font=('Arial',10),padx=12,pady=6)
        elif isinstance(child,tk.Label):
            child.configure(wraplength=420)
            var=str(child.cget('textvariable'))
            if var:parent.setvar(var,'Select a list row or right-click a cover for quick actions.')
    if view:
        def paint_view(*args):
            colour=get_setting('accent_color','#B23A48')
            for button in view.winfo_children():
                if not isinstance(button,tk.Button):continue
                active=view_mode.get() in str(button.cget('text'))
                button._et_active_library_view=active
                button._et_hover_installed=True
                button.configure(bg=colour if active else PANEL_ALT,fg='white' if active else MUTED,font=('Arial',10,'bold' if active else 'normal'))
        view_mode.trace_add('write',paint_view)
        parent.after_idle(paint_view)
        paint_view()
    if primary:
        primary.configure(font=('Arial',10,'bold'),padx=14,pady=6,bg=accent,fg='white')
        primary._et_primary_action=True
    actions=tk.Menubutton(search,text='Actions ▾',font=('Arial',10),bg=PANEL_ALT,fg=TEXT,activebackground=accent,activeforeground='white',relief='flat',bd=0,padx=12,pady=6,cursor='hand2')
    menu=tk.Menu(actions,tearoff=False,bg=PANEL_ALT,fg=TEXT,activebackground=accent,activeforeground='white');actions.configure(menu=menu)
    for label,callback in secondary:menu.add_command(label=label,command=callback)
    if primary:primary.pack_forget()
    if view:view.pack_forget()
    if view:view.pack(side='right',padx=(8,4),pady=2)
    if primary:primary.pack(side='right',padx=4,pady=2)
    actions.pack(side='right',padx=4,pady=2)
    parent._library_actions=menu
    return actions
