"""Statistics for visible collections, calculated from saved records."""
from database import connection
from collection_visibility import visible_sections,SECTIONS

def statistics():
    result=[]
    for kind in visible_sections():
        cur=connection.execute('SELECT * FROM '+kind);names=[c[0] for c in cur.description];rows=[dict(zip(names,r)) for r in cur]
        def activity(r):
            if kind=='games':return r.get('playtime') or 0
            if kind=='books':return r.get('reading_time') or 0
            if kind=='cds':return r.get('listening_time') or 0
            hours=(r.get('runtime') or 0)*(r.get('watch_count') or 0)
            if kind=='shows' and r.get('episode_count'):hours+=(r.get('runtime') or 0)*(r.get('episode_reached') or 0)/r['episode_count']
            return hours
        hours=sum(activity(r) for r in rows);spend=sum(r.get('price_paid') or 0 for r in rows)
        result.append({'kind':kind,'records':len(rows),'physical':sum(bool(r.get('owned_physical')) for r in rows),'digital':sum(bool(r.get('owned_digital')) for r in rows),'wishlist':sum(bool(r.get('wishlist')) for r in rows),'spend':spend,'hours':hours,'cost_per_hour':spend/hours if hours>0 else None})
    return result

def open_statistics(parent,accent):
    import tkinter as tk
    from tkinter import ttk
    from theme import BG,TEXT,MUTED
    from utils import format_time
    page=tk.Frame(parent,bg=BG);page.pack(fill='both',expand=True)
    tk.Label(page,text='Collection Statistics',font=('Arial',20,'bold'),bg=BG,fg=TEXT).pack(anchor='w',padx=20,pady=20)
    tk.Label(page,text='Visible sections only. Physical and digital counts can overlap. Spend uses recorded prices; activity uses recorded time.',bg=BG,fg=MUTED,wraplength=800,justify='left').pack(anchor='w',padx=20,pady=(0,14))
    columns=('Section','Records','Physical','Digital','Wishlist','Spend','Activity','Cost / hour')
    table=ttk.Treeview(page,columns=columns,show='headings')
    for c in columns:table.heading(c,text=c);table.column(c,width=100,anchor='center')
    table.pack(fill='both',expand=True,padx=20,pady=10)
    rows=statistics()
    def insert(label,r):table.insert('','end',values=(label,r['records'],r['physical'],r['digital'],r['wishlist'],f"£{r['spend']:.2f}",format_time(r['hours']),f"£{r['cost_per_hour']:.2f}" if r['cost_per_hour'] is not None else '—'))
    for r in rows:insert(SECTIONS[r['kind']],r)
    total={k:sum(r[k] for r in rows) for k in ('records','physical','digital','wishlist','spend','hours')};total['cost_per_hour']=total['spend']/total['hours'] if total['hours']>0 else None
    insert('Total',total)
    return page
