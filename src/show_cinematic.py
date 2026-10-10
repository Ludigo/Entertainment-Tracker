"""Cinematic Shows facts, original watch totals and current-season progress."""
from movie_cinematic import render as render_panels
from utils import format_time


def show_sections(record):
    missing = lambda value: str(value) if value not in (None, '') else 'Not recorded'
    runtime = record.get('runtime') or 0
    episodes = record.get('episode_count') or 0
    reached = record.get('episode_reached') or 0
    watches = record.get('watch_count') or 0
    # Preserve the established calculation: whole seasons + partial season.
    partial = runtime * reached / episodes if episodes else 0
    facts = [('Season', missing(record.get('season'))),
             ('Release Year', missing(record.get('release_year'))),
             ('Network / Service', missing(record.get('network'))),
             ('Type', missing(record.get('type'))), ('Genre', missing(record.get('genre'))),
             ('Season Runtime', format_time(runtime) if runtime else 'Not recorded'),
             ('Rating', missing(record.get('rating')))]
    price = record.get('price_paid')
    activity = [('Episodes', str(episodes)), ('Episode Reached', str(reached)),
                ('Watch Count', str(watches)), ('Tracked Watch Time', format_time(runtime * watches + partial)),
                ('Price Paid', 'Not recorded' if price is None else f'£{price:,.2f}'),
                ('Completed', 'Yes' if record.get('completed') else 'No'),
                ('In Progress', 'Yes' if record.get('in_progress') else 'No'),
                ('Owned', 'Yes' if record.get('owned') else 'No')]
    members=record.get('_series_records') or []
    if members:
        from show_series import totals
        summary=totals(members)
        facts.append(('Saved Seasons',str(summary['seasons'])))
        activity.extend([('Season Entries Completed',f"{sum(bool(r.get('completed')) for r in members)} / {len(members)}"),
                         ('Total Watch Time (All Seasons)',format_time(summary['watched']))])
    return facts, activity


def episode_progress(record):
    if record.get('completed'):
        return 'Current season: Completed · 100%', 1.0
    total = record.get('episode_count')
    reached = record.get('episode_reached') or 0
    if total in (None, 0):
        return 'Episode progress — no episode total recorded.', None
    if not isinstance(total, int) or not isinstance(reached, int) or total < 0 or not 0 <= reached <= total:
        return 'Episode progress unavailable — check episode counts in Metadata.', None
    fraction = reached / total
    return f'Current season: {reached} / {total} episodes · {fraction:.1%}', fraction


def render(parent, record, accent, page=None, page_state=None):
    subtitle = 'SHOW'
    if record.get('season') is not None:
        subtitle += f"  ·  Season {record['season']}"
    if record.get('release_year'):
        subtitle += f"  ·  {record['release_year']}"
    return render_panels(parent, record, accent, page, page_state,
                         section_builder=show_sections, media_label='SHOW',
                         subtitle=subtitle, progress=episode_progress(record))

