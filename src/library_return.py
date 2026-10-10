"""Session-only return context for details -> library navigation."""
import tkinter as tk
from cover_grid import PAGE_SIZE

_contexts={}


def install(owner,kind,on_open_detail,grid,table,search,view,switch_view,load,filters,
            extra_vars=None,restore=False):
    key=(str(owner.winfo_toplevel()),kind)
    state=_contexts.pop(key,None) if restore else None
    if not restore:_contexts.pop(key,None)
    variables={'status':filters['status'],'sort':filters['sort'],
               **{'extra:'+name:var for name,var in filters['extra'].items()},**(extra_vars or {})}
    def open_detail(item_id):
        _contexts[key]={'search':search.get(),'view':view.get(),'filters':{name:var.get() for name,var in variables.items()},
                        'page':grid.page,'grid_y':grid.canvas.yview()[0],'table_y':table.yview()[0],
                        'selected_id':item_id}
        if on_open_detail:on_open_detail(item_id)
    if state:
        search.delete(0,tk.END);search.insert(0,state['search'])
        for name,value in state['filters'].items():
            if name in variables:variables[name].set(value)
        switch_view(state['view']);load(search.get())
        grid.page=min(max(0,state['page']),max(0,(len(grid.rows)-1)//PAGE_SIZE))
        if state['view']=='Covers':grid.render()
        for row in table.get_children():
            values=table.item(row,'values')
            if values and str(values[0])==str(state['selected_id']):
                table.selection_set(row);table.focus(row);break
        # Let geometry/column reflow settle before restoring viewport fractions.
        jobs=[]
        def position():
            if not owner.winfo_exists():return
            grid.canvas.yview_moveto(state['grid_y']);table.yview_moveto(state['table_y'])
        jobs.append(owner.after_idle(position))
        jobs.append(owner.after(180,position))
        def cleanup(event):
            if event.widget is owner:
                for job in jobs:
                    try:owner.after_cancel(job)
                    except tk.TclError:pass
        owner.bind('<Destroy>',cleanup,add='+')
        def stop_restore(event=None):
            for job in jobs:
                try:owner.after_cancel(job)
                except tk.TclError:pass
        grid.cancel_return_restore=stop_restore
        # Do not pull the viewport back after the user starts interacting.
        def descendants(widget):
            yield widget
            for child in widget.winfo_children():yield from descendants(child)
        for widget in descendants(owner):
            for sequence in ('<Button-1>','<MouseWheel>','<Button-4>','<Button-5>','<KeyPress>'):
                widget.bind(sequence,stop_restore,add='+')
    return open_detail if on_open_detail else None
