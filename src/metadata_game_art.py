"""Preserve the original Games Edit artwork and Steam workflows in Metadata."""
import tkinter as tk
from types import SimpleNamespace
from database import get_setting
from theme import PANEL, PANEL_ALT, TEXT


class GameArtworkStage:
    def __init__(self, parent, window, game_id, record, widgets, accent, status):
        from add_game_metadata import METADATA_FIELDS, load_game_artwork
        from artwork_preferences import is_locked
        modal = window
        messagebox = SimpleNamespace(showerror=lambda title,message:status.configure(text=title+': '+str(message)),
                                     showinfo=lambda title,message:status.configure(text=title+': '+str(message)))
        title_entry, platform_entry, description_entry = widgets['name'], widgets['platform'], widgets['description']
        cover, roles, available, expected_art = load_game_artwork(game_id)
        pending = {'metadata': {key: record.get(key) for key in METADATA_FIELDS}, 'cover': cover,
                   'roles': roles, 'available': available, 'extras': []}
        protect_cover = tk.BooleanVar(master=window, value=is_locked('games',game_id,'cover_path'))
        protect_roles = {key:tk.BooleanVar(master=window,value=is_locked('games',game_id,key))
                         for key in ('background_path','logo_path')}
        tk.Button(parent,text='Find on Steam…',command=lambda:find_on_steam(),bg=PANEL_ALT,fg=TEXT,
                  relief='flat',padx=12,pady=6).pack(anchor='w',pady=(12,8))
        cover_row=tk.Frame(parent,bg=PANEL)
        cover_row.pack(fill='x',padx=15,pady=(3,6))
        staged_info=tk.StringVar(value='Manual entry · No cover selected')
        summary=tk.Label(cover_row,bg=PANEL,fg=TEXT,textvariable=staged_info,wraplength=330,justify='left')
        summary.pack(side='left',fill='x',expand=True)
        summary.bind('<Configure>',lambda event:summary.configure(wraplength=max(100,event.width)),add='+')
        cover_button=tk.Menubutton(cover_row,text='Artwork ▾',bg=PANEL_ALT,fg=TEXT,relief='flat',padx=10,pady=6)
        cover_button.pack(side='right')
        cover_menu=tk.Menu(cover_button,tearoff=False,bg=PANEL_ALT,fg=TEXT)
        cover_button.configure(menu=cover_menu)
        def update_staged_info():
            statuses=[]
            for name,image,var,key in (
                ('Cover',pending['cover'],protect_cover,'cover_path'),
                ('Background',pending['roles']['background_path'],protect_roles['background_path'],'background_path'),
                ('Logo',pending['roles']['logo_path'],protect_roles['logo_path'],'logo_path')):
                protected=var.get() or (game_id is not None and is_locked('games',game_id,key))
                statuses.append(name+': '+('protected' if image and protected else 'selected' if image else 'none'))
            count=sum(bool(widgets[key].get().strip()) for key in METADATA_FIELDS)
            staged_info.set(f"{count} metadata fields · {len(pending['extras'])} extra images\n"+' · '.join(statuses))
        def choose_role(role):
            from add_game_metadata import choose_local_cover,preview_cover
            label='Background' if role=='background_path' else 'Logo'
            try:
                image=choose_local_cover(modal,label)
                if image:
                    pending['roles'][role]=image;update_staged_info();preview_cover(modal,image,label)
            except Exception as exc:messagebox.showerror('Game '+label,str(exc))
        def preview_role(role):
            from add_game_metadata import preview_cover
            label='Background' if role=='background_path' else 'Logo'
            if pending['roles'][role]:preview_cover(modal,pending['roles'][role],label)
            else:messagebox.showinfo('Game '+label,'Choose an image first.')
        def clear_role(role):
            pending['roles'][role]=None;update_staged_info()
        def staged_artwork():
            from add_game_metadata import choose_artwork
            def chosen(cover,extras,roles):
                pending['cover']=cover;pending['extras']=extras;pending['roles']=roles
                if not cover:protect_cover.set(False)
                update_staged_info()
            choose_artwork(modal,accent,pending['available'],pending['cover'],
                           pending['extras'],chosen,roles=pending['roles'])
        def local_cover():
            from add_game_metadata import choose_local_cover,preview_cover
            try:
                cover=choose_local_cover(modal)
                if cover:
                    pending['cover']=cover;update_staged_info();preview_cover(modal,cover)
            except Exception as exc:messagebox.showerror('Game Cover',str(exc))
        def review_cover():
            from add_game_metadata import preview_cover
            if pending['cover']:preview_cover(modal,pending['cover'])
            else:messagebox.showinfo('Game Cover','Choose a cover from Steam or your PC first.')
        def clear_cover():
            pending['cover']=None;protect_cover.set(False);update_staged_info()
        def manual_metadata():
            from add_game_metadata import edit_staged_metadata
            def applied(values):
                pending['metadata'].update(values)
                for key in METADATA_FIELDS:
                    widgets[key].delete(0,tk.END);widgets[key].insert(0,'' if values.get(key) is None else str(values[key]))
                update_staged_info()
            edit_staged_metadata(modal,accent,{key:widgets[key].get() for key in METADATA_FIELDS},applied)
        cover_menu.add_command(label='Review / edit metadata…',command=manual_metadata)
        cover_menu.add_command(label='Choose from PC…',command=local_cover)
        cover_menu.add_command(label='Preview selected cover',command=review_cover)
        cover_menu.add_command(label='Clear selected cover',command=clear_cover)
        cover_menu.add_checkbutton(label='Protect selected cover after saving',variable=protect_cover,command=update_staged_info,
                                   state='disabled' if game_id is not None and protect_cover.get() else 'normal')
        cover_menu.add_command(label='Review staged artwork / remove extras…',command=staged_artwork)
        for role,label in [('background_path','Background'),('logo_path','Logo')]:
            submenu=tk.Menu(cover_menu,tearoff=False,bg=PANEL_ALT,fg=TEXT)
            submenu.add_command(label='Choose from PC…',command=lambda role=role:choose_role(role))
            submenu.add_command(label='Preview selected image',command=lambda role=role:preview_role(role))
            submenu.add_command(label='Clear selected image',command=lambda role=role:clear_role(role))
            submenu.add_checkbutton(label='Protect after saving',variable=protect_roles[role],command=update_staged_info,
                                    state='disabled' if game_id is not None and protect_roles[role].get() else 'normal')
            cover_menu.add_cascade(label=label,menu=submenu)
        def import_current():
            return dict({key:widgets[key].get().strip() for key in METADATA_FIELDS},name=title_entry.get(),platform=platform_entry.get(),
                        description=description_entry.get('1.0','end-1c'),_cover=pending['cover'],
                        _extras=pending['extras'],_lock_cover=protect_cover.get(),_roles=pending['roles'],_available=pending['available'],_editing=game_id is not None)
        def apply_import(updates,cover,extras=(),lock_cover=None,roles=None,available=()):
            from add_game_metadata import METADATA_FIELDS
            for key,widget in [('name',title_entry),('platform',platform_entry)]:
                if key in updates:widget.delete(0,tk.END);widget.insert(0,str(updates[key]))
            if 'description' in updates:
                description_entry.delete('1.0',tk.END);description_entry.insert('1.0',updates['description'])
            pending['metadata'].update({key:value for key,value in updates.items() if key in METADATA_FIELDS})
            for key in METADATA_FIELDS:
                if key in updates:
                    widgets[key].delete(0,tk.END);widgets[key].insert(0,'' if updates[key] is None else str(updates[key]))
            if cover:pending['cover']=cover
            pending['extras']=list(extras)
            if lock_cover is not None:protect_cover.set(bool(lock_cover))
            if roles is not None:pending['roles']={key:roles.get(key) for key in ('background_path','logo_path')}
            from add_game_metadata import image_digest
            pending['available']=list({image_digest(image):image for image in pending['available']+list(available)}.values())
            update_staged_info()
        def find_on_steam():
            from add_game_metadata import open_search
            open_search(modal,accent,import_current,apply_import)

        update_staged_info()

        for key in METADATA_FIELDS:
            widgets[key].bind('<KeyRelease>',lambda event:update_staged_info(),add='+')
        self.pending = pending
        self.expected_art = expected_art
        self.protect_cover = protect_cover
        self.protect_roles = protect_roles
        self.import_current = import_current
        self.apply_import = apply_import

    def state(self):
        return {'cover': self.pending['cover'], 'roles': self.pending['roles'],
                'extras': self.pending['extras'], 'expected': self.expected_art,
                'locks': {'cover_path': self.protect_cover.get(),
                          **{key:var.get() for key,var in self.protect_roles.items()}}}

    def signature(self):
        from add_game_metadata import staged_signature
        return (staged_signature({},self.pending['cover'],self.pending['extras'],
                                 self.protect_cover.get(),self.pending['roles']),
                tuple((key,var.get()) for key,var in self.protect_roles.items()))
