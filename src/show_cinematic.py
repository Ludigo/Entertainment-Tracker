"""Cinematic Shows facts, original watch totals and current-season progress."""
from ownership import describe as describe_ownership
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
                ('Ownership', describe_ownership(record))]
    members=record.get('_series_records') or []
    if members:
        from show_series import totals
        summary=totals(members)
        facts.append(('Saved Seasons',str(summary['seasons'])))
        activity.extend([('Season Entries Completed',f"{sum(bool(r.get('completed')) for r in members)} / {len(members)}"),
                         ('Total Watch Time (All Seasons)',format_time(summary['watched']))])
    return facts, activity


def summary_sections(record):
    """Aggregate saved season entries without modifying their tracking records."""
    from show_series import totals
    members=record['_series_records']
    summary=totals(members)
    def combined(key):
        values=list(dict.fromkeys(str(r[key]) for r in members if r.get(key) not in (None,'')))
        return ' · '.join(values) or 'Not recorded'
    years=sorted({r['release_year'] for r in members if r.get('release_year')})
    years_text=(str(years[0]) if len(years)==1 else f'{years[0]}–{years[-1]}') if years else 'Not recorded'
    facts=[('Saved Seasons',str(summary['seasons'])),('Release Years',years_text),
           ('Total Episodes',str(summary['episodes'])),('Total Runtime (All Episodes)',format_time(summary['runtime'])),
           ('Network / Service',combined('network')),('Type',combined('type')),
           ('Genre',combined('genre')),('Rating',combined('rating'))]
    prices=[r['price_paid'] for r in members if r.get('price_paid') is not None]
    completed=sum(bool(r.get('completed')) for r in members)
    watched_episodes=sum((r.get('episode_count') or 0) if r.get('completed') else
                         min(r.get('episode_count') or 0,max(0,r.get('episode_reached') or 0)) for r in members)
    activity=[('Season Entries Completed',f'{completed} / {len(members)}'),
              ('Episodes Watched (Current Progress)',f"{watched_episodes} / {summary['episodes']}"),
              ('Total Tracked Watch Time',format_time(summary['watched'])),
              ('Total Price Paid',f'£{sum(prices):,.2f}' + (' (partly recorded)' if len(prices)<len(members) else '') if prices else 'Not recorded'),
              ('Completed','Yes' if summary['completed'] else 'No'),
              ('In Progress','Yes' if summary['in_progress'] else 'No'),
              ('Owned Season Entries',f"{sum(bool(r.get('owned')) for r in members)} / {len(members)}")]
    return facts,activity


def summary_progress(record):
    members=record['_series_records']
    total=sum(r.get('episode_count') or 0 for r in members)
    reached=sum((r.get('episode_count') or 0) if r.get('completed') else
                min(r.get('episode_count') or 0,max(0,r.get('episode_reached') or 0)) for r in members)
    if not total:return 'Show progress — no episode totals recorded.',None
    fraction=reached/total
    return f'Show progress: {reached} / {total} episodes · {fraction:.1%}',fraction


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
    if record.get('_show_summary'):
        from show_series import season_labels
        members=record['_series_records']
        display=dict(record)
        # All descriptions and notes remain readable without presenting one season as the whole show.
        for key in ('description','notes'):
            entries=[(label,r.get(key)) for label,r in zip(season_labels(members),members) if r.get(key)]
            unique=list(dict.fromkeys(value for _,value in entries))
            display[key]=unique[0] if len(unique)==1 else '\n\n'.join(f'{label}\n{value}' for label,value in entries)
        season_lines='\n'.join(f"{label} · {r.get('episode_count') or 0} episodes · {format_time(r.get('runtime') or 0)} · " +
                               ('Completed' if r.get('completed') else 'Watching' if r.get('in_progress') else 'Not started')
                               for label,r in zip(season_labels(members),members))
        return render_panels(parent,display,accent,page,page_state,
                             section_builder=summary_sections,media_label='SHOW',
                             subtitle='SHOW · ALL SAVED SEASONS',progress=summary_progress(record),
                             extra_sections=[('SEASONS · OPEN USING THE SELECTOR ABOVE',season_lines)])
    subtitle = 'SHOW'
    if record.get('season') is not None:
        subtitle += f"  ·  Season {record['season']}"
    if record.get('release_year'):
        subtitle += f"  ·  {record['release_year']}"
    return render_panels(parent, record, accent, page, page_state,
                         section_builder=show_sections, media_label='SHOW',
                         subtitle=subtitle, progress=episode_progress(record))

