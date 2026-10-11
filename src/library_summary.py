"""Read-only summaries of every record behind the currently visible listings."""
from database import connection
from collection_tools import expand_ids
from utils import format_time

def summary_text(kind,ids):
    ids=list(dict.fromkeys(int(i) for i in ids));records=[]
    for ident in expand_ids(kind,ids):
        cur=connection.execute('SELECT * FROM '+kind+' WHERE id=?',(ident,));row=cur.fetchone()
        if row:records.append(dict(zip([c[0] for c in cur.description],row)))
    from collection_manager_data import values_summary
    value_summary=values_summary(kind,[r['id'] for r in records])
    def total(field):return sum(r.get(field) or 0 for r in records)
    if kind=='games':return f'{len(records)} games • {total("completed")} completed • {format_time(total("playtime"))} played\n'+value_summary
    if kind=='books':return f'{len(records)} books • {total("completed")} completed • {total("read_count")} full reads • {format_time(total("reading_time"))} read\n'+value_summary
    watched=sum((r.get('runtime') or 0)*(r.get('watch_count') or 0) for r in records)
    if kind=='movies':return f'{len(records)} movies • {total("watch_count")} watches • {format_time(watched)} watched\n'+value_summary
    if kind=='shows':
        from show_series import totals
        watched=totals(records)['watched']
        return f'{len(ids)} shows • {len(records)} saved season entries • {total("watch_count")} season watches • {format_time(watched)} watched\n'+value_summary
    raise ValueError('Unknown collection')

def create_footer(parent):
    import tkinter as tk
    from theme import BG,MUTED
    label=tk.Label(parent,bg=BG,fg=MUTED,anchor='w',justify='left',font=('Arial',9))
    label.pack(side='bottom',fill='x',padx=20,pady=8)
    label.bind('<Configure>',lambda event:label.configure(wraplength=max(200,event.width)))
    return label
