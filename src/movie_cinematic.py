"""Offline cinematic movie information and independently protected background art."""
import tkinter as tk
from tkinter import font as tkfont
from database import connection
from artwork_preferences import require_unlocked
from theme import TEXT, MUTED
from utils import format_time

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None


def background_path(item_id, kind='movies'):
    if kind not in ('movies','shows','books'):raise ValueError('Invalid background category')
    row = connection.execute(f'SELECT background_path FROM {kind} WHERE id=?', (item_id,)).fetchone()
    return row[0] if row else None


def set_background(item_id, path, kind='movies'):
    if kind not in ('movies','shows','books'):raise ValueError('Invalid background category')
    require_unlocked(kind, item_id, 'background_path')
    if path and not connection.execute(
            'SELECT 1 FROM artwork_library WHERE category=? AND item_id=? AND image_path=?',
            (kind, item_id, path)).fetchone():
        raise ValueError('Choose a saved image from this item’s artwork collection.')
    with connection:
        changed = connection.execute(f'UPDATE {kind} SET background_path=? WHERE id=?', (path, item_id))
        if changed.rowcount != 1:
            raise ValueError('This item is no longer in the collection.')


def movie_sections(record):
    """Display saved values without inventing metadata or changing watch totals."""
    missing = lambda value: str(value) if value not in (None, '') else 'Not recorded'
    facts = [('Release Year', missing(record.get('release_year'))),
             ('Runtime', format_time(record['runtime']) if record.get('runtime') else 'Not recorded'),
             ('Type', missing(record.get('type'))), ('Genre', missing(record.get('genre'))),
             ('Director', missing(record.get('director'))), ('Cast', missing(record.get('cast_members'))),
             ('Rating', missing(record.get('rating')))]
    price = record.get('price_paid')
    activity = [('Watch Count', str(record.get('watch_count') or 0)),
                ('Tracked Watch Time', format_time((record.get('runtime') or 0) * (record.get('watch_count') or 0))),
                ('Price Paid', 'Not recorded' if price is None else f'£{price:,.2f}'),
                ('Completed', 'Yes' if record.get('completed') else 'No'),
                ('In Progress', 'Yes' if record.get('in_progress') else 'No'),
                ('Owned', 'Yes' if record.get('owned') else 'No')]
    return facts, activity


def wrap_text(value, font, width):
    """Pixel based wrapping also breaks unusually long words without losing text."""
    lines = []
    for paragraph in str(value).split('\n'):
        line = ''
        for word in paragraph.split():
            candidate = (line + ' ' + word).lstrip()
            if font.measure(candidate) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
                line = ''
            for char in word:
                if line and font.measure(line + char) > width:
                    lines.append(line)
                    line = ''
                line += char
        lines.append(line)
    return '\n'.join(lines)


def render(parent, record, accent, page=None, page_state=None, *,
           section_builder=movie_sections, media_label='MOVIE', subtitle=None, progress=None):
    canvas = tk.Canvas(parent, bg='#181c22', bd=0, highlightthickness=0, yscrollincrement=24)
    canvas.pack(side='left', fill='both', expand=True)
    bar = tk.Scrollbar(parent, orient='vertical')
    fonts = {name: tkfont.Font(root=canvas, family='Arial', size=size, weight=weight)
             for name, size, weight in [('title', 25, 'bold'), ('heading', 12, 'bold'),
                                       ('label', 8, 'bold'), ('value', 11, 'normal')]}
    state = {'photo': None, 'job': None, 'painting': False}

    def request_paint(event=None):
        if state['job'] is None and canvas.winfo_exists():
            state['job'] = canvas.after_idle(paint)

    def scroll(*args):
        canvas.yview(*args)
        request_paint()

    def scroll_position(first, last):
        bar.set(first, last)
        needed = float(first) > .001 or float(last) < .999
        if needed and not bar.winfo_manager():
            bar.pack(side='right', fill='y')
        elif not needed and bar.winfo_manager():
            bar.pack_forget()

    bar.configure(command=scroll)
    canvas.configure(yscrollcommand=scroll_position)

    def paint():
        state['job'] = None
        if not canvas.winfo_exists():
            return
        state['painting'] = True
        fraction = canvas.yview()[0]
        width, height = max(1, canvas.winfo_width()), max(1, canvas.winfo_height())
        canvas.delete('paint')
        panels = []
        margin = 24 if width >= 400 else 12
        usable = max(30, width - margin * 2)

        def text(x, y, value, style='value', colour=TEXT, text_width=None):
            font = fonts[style]
            value = wrap_text(value, font, max(15, text_width or usable))
            canvas.create_text(x, y, text=value, font=font, fill=colour, anchor='nw', tags='paint')
            return len(value.split('\n')) * font.metrics('linespace')

        y = 22
        y += text(margin, y, record['name'], 'title') + 8
        year = record.get('release_year')
        y += text(margin, y, subtitle if subtitle is not None else media_label + (f'  ·  {year}' if year else ''), 'label', accent) + 22
        facts, activity = section_builder(record)
        for heading, fields in [(media_label + ' INFORMATION', facts), ('MY ' + media_label + ' ACTIVITY', activity)]:
            start = y
            inset = margin + 18
            y += 18
            y += text(inset, y, heading, 'heading', accent, usable - 36) + 22
            columns = 2 if usable >= 430 else 1
            cell_width = max(15, (usable - 36 - (18 if columns == 2 else 0)) // columns)
            for index in range(0, len(fields), columns):
                row_height = 0
                for column, (label, value) in enumerate(fields[index:index + columns]):
                    x = inset + column * (cell_width + 18)
                    label_height = text(x, y, label.upper(), 'label', MUTED, cell_width)
                    value_height = text(x, y + label_height + 5, value, text_width=cell_width)
                    row_height = max(row_height, label_height + 5 + value_height)
                y += row_height + 18
            if fields is activity and progress is not None:
                label, progress_fraction = progress
                y += text(inset, y, label, 'value', TEXT, usable - 36) + 10
                if progress_fraction is not None:
                    end = width - margin - 18
                    canvas.create_rectangle(inset, y, end, y + 8, fill='#343b47', outline='', tags='paint')
                    if progress_fraction > 0:
                        canvas.create_rectangle(inset, y, inset + (end - inset) * progress_fraction, y + 8,
                                                fill=accent, outline='', tags='paint')
                    y += 18
                y += 8
            panels.append((margin, start, width - margin, y))
            y += 18
        for heading, content in [('DESCRIPTION', record.get('description') or 'No description saved yet.'),
                                 ('PERSONAL NOTES', record.get('notes'))]:
            if not content:
                continue
            start = y
            y += 18
            y += text(margin + 18, y, heading, 'heading', accent, usable - 36) + 14
            y += text(margin + 18, y, content, text_width=usable - 36) + 20
            panels.append((margin, start, width - margin, y))
            y += 18
        canvas.configure(scrollregion=(0, 0, width, max(height, y + 10)))
        canvas.yview_moveto(fraction)
        offset = canvas.canvasy(0)
        if Image is not None:
            tile = Image.new('RGB', (width, height), (24, 28, 34))
            base = (page_state or {}).get('raster')
            if base is not None and page is not None:
                x = canvas.winfo_rootx() - page.winfo_rootx()
                top = canvas.winfo_rooty() - page.winfo_rooty()
                tile = base.crop((x, top, x + width, top + height))
            # Panel surfaces are blended with the same fixed artwork as Games.
            from PIL import ImageDraw
            overlay = Image.new('RGBA', tile.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            for x1, y1, x2, y2 in panels:
                draw.rounded_rectangle((x1, y1 - offset, x2, y2 - offset), radius=12,
                                       fill=(13, 16, 22, 210), outline=(88, 96, 109, 110))
            tile = Image.alpha_composite(tile.convert('RGBA'), overlay)
            state['photo'] = ImageTk.PhotoImage(tile)
            canvas.delete('surface')
            canvas.create_image(0, offset, image=state['photo'], anchor='nw', tags='surface')
            canvas.tag_lower('surface')
        else:
            for x1, y1, x2, y2 in panels:
                item = canvas.create_rectangle(x1, y1, x2, y2, fill='#12161c', outline='#343b47', tags='paint')
                canvas.tag_lower(item)
        state['painting'] = False

    def wheel(event):
        number = getattr(event, 'num', None)
        delta = getattr(event, 'delta', 0)
        if number not in (4, 5) and not delta:
            return
        scroll('scroll', -3 if number == 4 or delta > 0 else 3, 'units')
        return 'break'

    canvas.bind('<Configure>', request_paint)
    for event in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
        canvas.bind(event, wheel)
    if page is not None:
        page.bind('<Configure>', request_paint, add='+')
    def destroyed(event):
        if event.widget is canvas and state['job'] is not None:
            canvas.after_cancel(state['job'])
            state['job'] = None
    canvas.bind('<Destroy>', destroyed, add='+')
    request_paint()
    return canvas

