"""Offline book facts, saved reading activity and explicit page progress."""
from movie_cinematic import render as render_panels
from utils import format_time


def book_sections(record):
    missing = lambda value: str(value) if value not in (None, '') else 'Not recorded'
    facts = [('Author', missing(record.get('author'))),
             ('Series', missing(record.get('series'))),
             ('Release Year', missing(record.get('release_year'))),
             ('Publisher', missing(record.get('publisher'))),
             ('ISBN', missing(record.get('isbn'))),
             ('Type', missing(record.get('type'))),
             ('Genre', missing(record.get('genre'))),
             ('Page Count', missing(record.get('page_count'))),
             ('Rating', missing(record.get('rating')))]
    price = record.get('price_paid')
    activity = [('Reading Time', format_time(record.get('reading_time') or 0)),
                ('Read Count', str(record.get('read_count') or 0)),
                ('Page Reached', missing(record.get('page_reached'))),
                ('Price Paid', 'Not recorded' if price is None else f'£{price:,.2f}'),
                ('Completed', 'Yes' if record.get('completed') else 'No'),
                ('In Progress', 'Yes' if record.get('in_progress') else 'No'),
                ('Owned', 'Yes' if record.get('owned') else 'No')]
    return facts, activity


def page_progress(record):
    if record.get('completed'):
        return 'Current read: Completed · 100%', 1.0
    total, reached = record.get('page_count'), record.get('page_reached')
    if total in (None, 0):
        return 'Page progress — no page total recorded.', None
    if reached is None:
        return 'Page progress — enter Page reached in Metadata.', None
    if (type(total) is not int or type(reached) is not int
            or total < 0 or not 0 <= reached <= total):
        return 'Page progress unavailable — check page counts in Metadata.', None
    fraction = reached / total
    return f'Current read: {reached:,} / {total:,} pages · {fraction:.1%}', fraction


def render(parent, record, accent, page=None, page_state=None):
    subtitle = 'BOOK'
    if record.get('release_year'):
        subtitle += f"  ·  {record['release_year']}"
    return render_panels(parent, record, accent, page, page_state,
                         section_builder=book_sections, media_label='BOOK',
                         subtitle=subtitle, progress=page_progress(record))
