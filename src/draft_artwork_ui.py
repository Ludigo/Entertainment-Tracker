"""The album editor's artwork layout, shared by every collection Add window."""
import tkinter as tk
from tkinter import ttk
from theme import PANEL, PANEL_ALT, TEXT, MUTED


def build_artwork_tab(window, parent, label, roles, local, preview_selected,
                      preview_role, clear, assign, locks=None, lock_changed=None):
    summary=tk.StringVar(master=window,value='')
    tk.Label(parent,textvariable=summary,bg=PANEL,fg=TEXT,justify='left',wraplength=600).pack(anchor='w',padx=16,pady=16)
    controls=tk.Frame(parent,bg=PANEL);controls.pack(fill='x',padx=16)
    for index,(text,command) in enumerate([('Local Cover',lambda:local('cover')),
            ('Local Background',lambda:local('background')),('Preview Selected',preview_selected)]):
        tk.Button(controls,text=text,command=command,bg=PANEL_ALT,fg=TEXT,relief='flat',padx=6,pady=6).grid(row=0,column=index,sticky='ew',padx=3,pady=3)
        controls.columnconfigure(index,weight=1)
    actions=tk.Menubutton(controls,text='More ▾',bg=PANEL_ALT,fg=TEXT,relief='flat',padx=6,pady=6)
    actions.grid(row=0,column=3,sticky='ew',padx=3,pady=3);controls.columnconfigure(3,weight=1)
    menu=tk.Menu(actions,tearoff=False);actions.configure(menu=menu)
    for role in roles:
        if role not in ('cover','background'):menu.add_command(label='Local '+role.title(),command=lambda r=role:local(r))
        menu.add_command(label='Preview '+role.title(),command=lambda r=role:preview_role(r))
        menu.add_command(label='Clear '+role.title(),command=lambda r=role:clear(r))
        if role not in ('cover','background'):menu.add_command(label='Set '+role.title(),command=lambda r=role:assign(r))
    if locks:
        menu.add_separator()
        for role in roles:
            menu.add_checkbutton(label='Protect '+role.title(),variable=locks[role+'_path'],command=lock_changed)
    tk.Label(parent,text='Select an image below. Choose its role, then Save '+label+' to keep it.',bg=PANEL,fg=MUTED,wraplength=500).pack(anchor='w',padx=16,pady=6)
    body=tk.Frame(parent,bg=PANEL)
    # Reserve the role controls before allocating space to the expanding gallery.
    # This is the same packing order as the working Album editor.
    role_row=tk.Frame(parent,bg=PANEL);role_row.pack(side='bottom',fill='x',padx=16,pady=6)
    for column,(text,role) in enumerate([('Set Cover','cover'),('Set Background','background'),('Toggle Extra','extra')]):
        role_row.columnconfigure(column,weight=1)
        tk.Button(role_row,text=text,command=lambda r=role:assign(r),bg=PANEL_ALT,fg=TEXT,pady=6).grid(row=0,column=column,sticky='ew',padx=3)
    body.pack(fill='both',expand=True,padx=16,pady=8)
    style=ttk.Style(window);style.configure('CDArtwork.Treeview',rowheight=112)
    table=ttk.Treeview(body,columns=('Image','Size'),show='tree headings',height=2,selectmode='browse',style='CDArtwork.Treeview')
    table.heading('#0',text='Preview');table.column('#0',width=140,minwidth=140,stretch=False)
    for key in ('Image','Size'):table.heading(key,text=key)
    table.column('Image',width=240);table.column('Size',width=100)
    scrollbar=ttk.Scrollbar(body,command=table.yview);scrollbar.pack(side='right',fill='y')
    table.configure(yscrollcommand=scrollbar.set);table.pack(fill='both',expand=True)
    table.bind('<Double-1>',lambda event:preview_selected() if table.identify_region(event.x,event.y) in ('tree','cell') else None)
    return table, summary
