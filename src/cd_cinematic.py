"""Saved album facts and listening activity using the shared cinematic surface."""
from movie_cinematic import render as render_panels
from utils import format_time
from database import connection


def album_sections(record):
    missing=lambda value:str(value) if value not in (None,'') else 'Not recorded'
    tracks=record.get('_tracks',[])
    total=sum(t['duration_seconds'] for t in tracks) if tracks and all(t['duration_seconds'] is not None for t in tracks) else None
    facts=[('Artist',missing(record.get('artist'))),('Release Year',missing(record.get('release_year'))),
           ('Genre',missing(record.get('genre'))),('Label',missing(record.get('label'))),
           ('Barcode',missing(record.get('barcode'))),('Discs',missing(record.get('disc_count'))),
           ('Tracks',str(len(tracks))),('Album Duration',format_time(total/3600) if total is not None else 'Unknown — complete track durations in Metadata'),
           ('Metadata Source',missing(record.get('provider_source')))]
    price=record.get('price_paid');hours=record.get('listening_time') or 0
    activity=[('Listening Time',format_time(hours)),('Full Album Plays',str(record.get('play_count') or 0)),
              ('Owned Physically','Yes' if record.get('owned_physical') else 'No'),
              ('Owned Digitally','Yes' if record.get('owned_digital') else 'No'),
              ('Price Paid','Not recorded' if price is None else f'£{price:,.2f}'),
              ('Cost per Listening Hour',f'£{price/hours:,.2f}' if price is not None and hours>0 else 'Not available')]
    return facts,activity


def extra_sections(record):
    tracks=record.get('_tracks',[]);lines=[];disc=None
    for track in tracks:
        if track['disc']!=disc:
            disc=track['disc'];lines.append(f'DISC {disc}')
        duration=format_time(track['duration_seconds']/3600) if track['duration_seconds'] is not None else 'Unknown duration'
        lines.append(f"{track['track']:02d}. {track['name']}  ·  {duration}")
    sessions=connection.execute('SELECT started_at,duration_seconds,source,note FROM cd_sessions WHERE cd_id=? ORDER BY id DESC LIMIT 6',(record['id'],)).fetchall()
    recent=[]
    from datetime import datetime
    for started,seconds,source,note in sessions:
        try:when=datetime.fromisoformat(started).astimezone().strftime('%d %b %Y %H:%M')
        except ValueError:when=str(started)
        recent.append(when+'  ·  '+format_time(seconds/3600)+'  ·  '+source+(('\n'+note) if note else ''))
    return [('TRACKLIST','\n'.join(lines) or 'No tracks saved. Add or import them in Metadata.'),
            ('RECENT LISTENING SESSIONS','\n\n'.join(recent) or 'No sessions recorded yet. Save a timer session or log a full album play.')]


def render(parent,record,accent,page=None,page_state=None):
    from cds import tracks_for
    record=dict(record,_tracks=tracks_for(record['id']))
    subtitle='ALBUM'+('  ·  '+record['artist'] if record.get('artist') else '')
    return render_panels(parent,record,accent,page,page_state,section_builder=album_sections,
                         media_label='ALBUM',subtitle=subtitle,activity_heading='MY LISTENING ACTIVITY',extra_sections=extra_sections(record))
