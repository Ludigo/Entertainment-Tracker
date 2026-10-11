"""SteamGridDB artwork and IGDB game metadata; no embedded credentials."""
import json
import re
import threading
import time
from datetime import datetime, timezone
import urllib.parse
import urllib.request
import urllib.error


SETTINGS=[('steamgriddb_key','SteamGridDB API key',True),
          ('igdb_client_id','IGDB / Twitch Client ID',False),
          ('igdb_client_secret','IGDB / Twitch Client Secret',True)]
_IGDB_LOCK=threading.RLock()
_TOKEN={}
_LAST_REQUEST=0.0
_SECRET_KEYS={'devid','devpassword','ssid','sspassword','apikey','api_key','token','password','client_secret','access_token'}


def credentials():
    """Call on the UI thread, then pass this snapshot to network workers."""
    from database import get_setting
    return {key:get_setting(key,'') or '' for key,_,_ in SETTINGS}


def clean_url(url):
    parts=urllib.parse.urlsplit(str(url or ''))
    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password:return ''
    query=[(key,value) for key,value in urllib.parse.parse_qsl(parts.query,keep_blank_values=True)
           if key.casefold() not in _SECRET_KEYS]
    return urllib.parse.urlunsplit((parts.scheme,parts.netloc,parts.path,urllib.parse.urlencode(query),''))


def open_request(url,provider,headers=None,data=None):
    request=urllib.request.Request(url,headers=headers or {'User-Agent':'EntertainmentTracker/1.75','Accept':'application/json'},data=data)
    try:return urllib.request.urlopen(request,timeout=20)
    except urllib.error.HTTPError as exc:
        if exc.code in (401,403):message='Access rejected. Check your Game Providers credentials and provider account permissions.'
        elif exc.code==429:message='Rate limit reached. Please try again later.'
        elif exc.code==404:message='No matching game or artwork was found.'
        else:message=f'Provider request failed (HTTP {exc.code}). Try again later.'
        error=RuntimeError(provider+': '+message);error.http_code=exc.code
        raise error from None
    except (urllib.error.URLError,TimeoutError):raise RuntimeError(provider+': could not connect. Check your connection and try again.') from None


def decode_response(response,provider):
    with response:
        raw=response.read(8*1024*1024+1)
    if len(raw)>8*1024*1024:raise RuntimeError(provider+': response was too large.')
    try:return json.loads(raw)
    except (ValueError,UnicodeError):raise RuntimeError(provider+': no usable response. Check service availability.') from None


def request_json(provider,path,auth=None,params=None):
    auth=auth or {}
    if provider!='SteamGridDB':raise ValueError('Unsupported game provider.')
    key=auth.get('steamgriddb_key','').strip()
    if not key:raise ValueError('Add your SteamGridDB API key in Settings → Game Providers.')
    url='https://www.steamgriddb.com/api/v2/'+path
    if params:url+='?'+urllib.parse.urlencode(params)
    data=decode_response(open_request(url,provider,{'User-Agent':'EntertainmentTracker/1.75','Accept':'application/json','Authorization':'Bearer '+key}),provider)
    if not isinstance(data,dict):raise RuntimeError(provider+': unexpected response.')
    if data.get('success') is False:raise RuntimeError('SteamGridDB: request rejected. Check your API key and try again.')
    return data


def igdb_token(auth,force=False):
    client=(auth or {}).get('igdb_client_id','').strip();secret=(auth or {}).get('igdb_client_secret','').strip()
    if not client or not secret:raise ValueError('Add your IGDB / Twitch Client ID and Client Secret in Settings → Game Providers.')
    with _IGDB_LOCK:
        if not force and _TOKEN.get('credentials')==(client,secret) and _TOKEN.get('expires',0)>time.monotonic():return _TOKEN['value']
        body=urllib.parse.urlencode({'client_id':client,'client_secret':secret,'grant_type':'client_credentials'}).encode()
        result=decode_response(open_request('https://id.twitch.tv/oauth2/token','IGDB',{'Content-Type':'application/x-www-form-urlencoded'},body),'IGDB')
        if not isinstance(result,dict) or not result.get('access_token'):raise RuntimeError('IGDB: could not obtain an access token. Check your Twitch application credentials.')
        try:lifetime=max(0,float(result.get('expires_in',0))-60)
        except (ValueError,TypeError):lifetime=0
        _TOKEN.update(credentials=(client,secret),value=result['access_token'],expires=time.monotonic()+lifetime)
        return _TOKEN['value']


def igdb_json(query,auth):
    global _LAST_REQUEST
    with _IGDB_LOCK:
        for attempt in range(2):
            token=igdb_token(auth,force=bool(attempt))
            delay=.26-(time.monotonic()-_LAST_REQUEST)
            if delay>0:time.sleep(delay)
            _LAST_REQUEST=time.monotonic()
            try:
                data=decode_response(open_request('https://api.igdb.com/v4/games','IGDB',
                    {'Client-ID':auth['igdb_client_id'].strip(),'Authorization':'Bearer '+token,'Accept':'application/json','Content-Type':'text/plain'},query.encode('utf-8')),'IGDB')
            except RuntimeError as exc:
                if getattr(exc,'http_code',None)==401 and attempt==0:continue
                raise
            if not isinstance(data,list):raise RuntimeError('IGDB: unexpected metadata response.')
            return data


def image_url(item):
    ident=(item or {}).get('image_id') if isinstance(item,dict) else None
    return 'https://images.igdb.com/igdb/image/upload/t_original/'+ident+'.jpg' if isinstance(ident,str) and re.fullmatch(r'[A-Za-z0-9_-]+',ident) else ''


def parse_igdb(game,platform_id=None):
    from metadata_finder import plain
    platforms=[p for p in (game.get('platforms') or []) if isinstance(p,dict)]
    selected=next((p for p in platforms if p.get('id')==platform_id),None)
    if selected is None and len(platforms)==1:selected=platforms[0]
    out={'source':'IGDB','title':game.get('name') or 'Untitled game','detail':str(game.get('id') or ''),
         'igdb_url':clean_url(game.get('url')),'_platform_id':selected.get('id') if selected else None,
         'subtitle':selected.get('name','') if selected else ', '.join(p.get('name','') for p in platforms),
         'description':plain(game.get('summary') or game.get('storyline') or '')}
    if selected:out['platform']=selected.get('abbreviation') or selected.get('name','')
    for key,source in [('genre','genres'),('game_modes','game_modes')]:
        out[key]=', '.join(dict.fromkeys(p['name'] for p in (game.get(source) or []) if isinstance(p,dict) and p.get('name')))
    for field in ('developer','publisher'):
        out[field]=', '.join(dict.fromkeys(p['company']['name'] for p in (game.get('involved_companies') or []) if isinstance(p,dict) and p.get(field) and isinstance(p.get('company'),dict) and p['company'].get('name')))
    dates=[r for r in (game.get('release_dates') or []) if isinstance(r,dict) and r.get('date') and (not selected or (r.get('platform') or {}).get('id')==selected['id'])]
    dates.sort(key=lambda r:0 if r.get('region')==1 else 1 if r.get('region')==8 else 2)
    stamp=dates[0]['date'] if dates else (game.get('first_release_date') if not selected else None)
    if stamp:
        try:
            date=datetime.fromtimestamp(float(stamp),timezone.utc);out.update(release_date=date.strftime('%Y-%m-%d'),release_year=date.year)
        except (ValueError,TypeError,OverflowError,OSError):pass
    ratings=[]
    for rating in (game.get('age_ratings') or []):
        if not isinstance(rating,dict):continue
        org=rating.get('organization') or {};cat=rating.get('rating_category') or {}
        if isinstance(org,dict) and isinstance(cat,dict) and org.get('name') in ('PEGI','ESRB') and cat.get('rating'):
            ratings.append((org['name'],str(cat['rating'])))
    ratings.sort(key=lambda r:0 if r[0]=='PEGI' else 1)
    if ratings:out['age_rating']=' '.join(ratings[0])
    options=[];cover=image_url(game.get('cover'))
    if cover:options.append(('IGDB Cover',cover));out['cover']=cover
    for loc in (game.get('game_localizations') or []):
        if isinstance(loc,dict):
            url=image_url(loc.get('cover'))
            if url:options.append(('IGDB Regional cover · '+str(loc.get('name') or 'Alternative'),url))
    for field,label in [('artworks','Artwork / background'),('screenshots','Screenshot')]:
        for picture in (game.get(field) or []):
            url=image_url(picture)
            if url:options.append(('IGDB '+label,url))
    out['artwork_options']=list(dict((url,(label,url)) for label,url in options).values())
    return out


IGDB_FIELDS='name,url,summary,storyline,first_release_date,platforms.name,platforms.abbreviation,genres.name,game_modes.name,involved_companies.company.name,involved_companies.developer,involved_companies.publisher,release_dates.date,release_dates.region,release_dates.platform.id,age_ratings.organization.name,age_ratings.rating_category.rating,cover.image_id,game_localizations.name,game_localizations.cover.image_id,artworks.image_id,screenshots.image_id'


def search(title,provider,auth=None):
    if provider=='SteamGridDB':
        data=request_json(provider,'search/autocomplete/'+urllib.parse.quote(title,safe=''),auth)
        return [dict(source=provider,title=x['name'],subtitle='Artwork',detail=str(x['id'])) for x in data.get('data',[]) if isinstance(x,dict) and x.get('name') and x.get('id')]
    if provider!='IGDB':raise ValueError('Unsupported game provider.')
    games=igdb_json('search '+json.dumps(title)+'; fields name,url,platforms.name,platforms.abbreviation; limit 30;',auth)
    results=[]
    for game in games:
        if not isinstance(game,dict) or not game.get('id'):continue
        platforms=[p for p in (game.get('platforms') or []) if isinstance(p,dict)]
        for platform in platforms or [None]:results.append(parse_igdb(game,platform.get('id') if platform else None))
    return results


def enrich(item,auth=None):
    provider=item['source'];ident=str(item.get('detail') or '')
    if not ident.isdecimal():raise ValueError('Select a valid provider game first.')
    if provider=='IGDB':
        games=igdb_json('fields '+IGDB_FIELDS+'; where id = '+ident+'; limit 1;',auth)
        if not games or not isinstance(games[0],dict):raise RuntimeError('IGDB: no details available for this game.')
        return parse_igdb(games[0],item.get('_platform_id'))
    out=dict(item);options=[];warnings=[]
    for path,label in [('grids','Grid / cover'),('heroes','Hero / background'),('logos','Logo'),('icons','Icon')]:
        try:
            data=request_json(provider,f'{path}/game/{ident}',auth,{'limit':20,'page':0,'types':'static'})
            for image in data.get('data',[]):
                url=clean_url(image.get('url'))
                if url:options.append((f"SteamGridDB {label} · {image.get('width','?')}×{image.get('height','?')}",url))
        except Exception as exc:warnings.append(label+': '+str(exc))
    out['artwork_options']=options
    out['cover']=next((url for label,url in options if 'Grid / cover' in label),'')
    out['artwork_warning']=' '.join(warnings)
    if not options and warnings:raise RuntimeError('SteamGridDB artwork unavailable. '+out['artwork_warning'])
    return out


def settings_panel(parent,accent):
    import tkinter as tk
    from database import connection
    from theme import PANEL,PANEL_ALT,TEXT,MUTED
    tk.Label(parent,text='Game Providers',font=('Arial',14,'bold'),bg=PANEL,fg=TEXT).pack(anchor='w')
    tk.Label(parent,text='SteamGridDB supplies artwork. IGDB supplies metadata and covers. Create a Twitch application with 2FA enabled, then enter its Client ID and Client Secret. Values are saved on this PC; access tokens renew automatically.',bg=PANEL,fg=MUTED,wraplength=340,justify='left').pack(anchor='w',pady=8)
    def setup():
        import webbrowser
        webbrowser.open('https://api-docs.igdb.com/#account-creation')
    tk.Button(parent,text='IGDB Setup Instructions',command=setup,bg=PANEL_ALT,fg=TEXT,relief='flat',pady=6).pack(anchor='w')
    existing=credentials();variables={}
    for key,label,secret in SETTINGS:
        tk.Label(parent,text=label,bg=PANEL,fg=TEXT).pack(anchor='w',pady=(7,2))
        var=tk.StringVar(value=existing[key]);variables[key]=var
        tk.Entry(parent,textvariable=var,show='•' if secret else '',bg=PANEL_ALT,fg=TEXT,insertbackground=TEXT,relief='flat').pack(fill='x',ipady=5)
    status=tk.StringVar()
    def save():
        with connection:
            for key,var in variables.items():
                value=var.get() if 'password' in key else var.get().strip()
                connection.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))
        status.set('Provider settings saved locally. Reopen a finder to use changed credentials.')
    tk.Button(parent,text='Save Provider Settings',command=save,bg=accent,fg='white',relief='flat',pady=8).pack(anchor='w',pady=10)
    tk.Label(parent,textvariable=status,bg=PANEL,fg=MUTED,wraplength=340).pack(anchor='w')
