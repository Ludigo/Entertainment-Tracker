"""Read-only release lookup; metadata never waits for optional artwork lookup."""
import copy
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

HEADERS = {'User-Agent': 'EntertainmentTracker/1.62 (https://github.com/Ludigo/Entertainment-Tracker)', 'Accept': 'application/json'}
_locks = {'musicbrainz.org': threading.Lock(), 'api.discogs.com': threading.Lock()}
_last = {host: 0.0 for host in _locks}
_cache = {}
_cache_lock = threading.Lock()


def _request(url, headers):
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise ValueError('Provider rate limit reached. Wait a moment and try again.') from None
        if exc.code in (401, 403) and url.startswith('https://api.discogs.com/'):
            raise ValueError('Discogs rejected the token. Check your personal access token in this window.') from None
        raise
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('Metadata response is too large.')
    return json.loads(raw)


def get_json(url, token=''):
    from urllib.parse import urlsplit
    host = urlsplit(url).hostname
    headers = dict(HEADERS)
    if host == 'api.discogs.com':
        if not token.strip():
            raise ValueError('Enter a Discogs personal access token to search Discogs.')
        headers['Authorization'] = 'Discogs token=' + token.strip()
    # Credential partitions are digests; credentials never enter URLs or status text.
    key = (url, hashlib.sha256(token.encode()).hexdigest() if host == 'api.discogs.com' else '')
    with _cache_lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < 900:
            return copy.deepcopy(cached[1])
    if host in _locks:
        with _locks[host]:
            delay = 1.1 - (time.monotonic() - _last[host])
            if delay > 0:
                time.sleep(delay)
            _last[host] = time.monotonic()
            result = _request(url, headers)
    else:
        result = _request(url, headers)
    with _cache_lock:
        if len(_cache) >= 80:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (time.monotonic(), copy.deepcopy(result))
    return result


def artist_name(item):
    return ''.join(str(c.get('name') or c.get('artist', {}).get('name', '')) + c.get('joinphrase', '')
                   for c in item.get('artist-credit', []) if isinstance(c, dict))


def search(query, provider='MusicBrainz', token=''):
    if not query.strip():
        raise ValueError('Enter an album, artist or barcode to search.')
    if provider == 'Discogs':
        params = {'type': 'release', 'per_page': 25}
        params['barcode' if query.strip().isdecimal() else 'q'] = query.strip()
        rows = get_json('https://api.discogs.com/database/search?' + urlencode(params), token).get('results', [])
        return [dict(x, source='Discogs', subtitle=' · '.join(str(x.get(k) or '?') for k in ('year','country')))
                for x in rows]
    if provider != 'MusicBrainz':
        raise ValueError('Unknown provider.')
    q = 'barcode:' + query.strip() if query.strip().isdecimal() else query.strip()
    rows = get_json('https://musicbrainz.org/ws/2/release/?' + urlencode({'query': q, 'fmt': 'json', 'limit': 25})).get('releases', [])
    return [dict(x, source='MusicBrainz', subtitle=' · '.join(filter(None, [artist_name(x),x.get('date'),x.get('country'),x.get('barcode')]))) for x in rows]


def release_id(item):
    source = item.get('source', 'MusicBrainz')
    ident = str(item.get('id', ''))
    if source == 'Discogs':
        if not ident.isdecimal() or int(ident) <= 0:
            raise ValueError('Invalid Discogs release identifier.')
    elif source == 'MusicBrainz':
        if not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', ident):
            raise ValueError('Invalid MusicBrainz release identifier.')
    else:
        raise ValueError('Unknown provider.')
    return source, ident


def _discogs_duration(value):
    bits = str(value or '').split(':')
    try:
        if len(bits) not in (2, 3) or any(not x.isdecimal() for x in bits):return None
        nums = list(map(int, bits))
        if nums[-1] >= 60 or len(nums) == 3 and nums[-2] >= 60:return None
        return nums[0] * 60 + nums[1] if len(nums) == 2 else nums[0] * 3600 + nums[1] * 60 + nums[2]
    except ValueError:return None


def load_discogs(item, token):
    _, ident = release_id(dict(item, source='Discogs'))
    data = get_json('https://api.discogs.com/releases/' + ident, token)
    artists = data.get('artists', [])
    artist = ''.join(str(a.get('name', '')) + (' ' + a['join'] + ' ' if a.get('join') else '') for a in artists).strip()
    genres = list(dict.fromkeys(data.get('genres', []) + data.get('styles', [])))
    barcode = next((x.get('value','') for x in data.get('identifiers',[]) if x.get('type') == 'Barcode'), '')
    declared = sum(int(x.get('qty',1)) for x in data.get('formats',[]) if str(x.get('qty','1')).isdecimal()) or 1
    tracks, used, warning = [], set(), ''
    def walk(items):
        nonlocal warning
        for item in items:
            if item.get('sub_tracks'):
                walk(item['sub_tracks']);continue
            if item.get('type_') in ('heading','index'):continue
            position = str(item.get('position',''))
            match = re.fullmatch(r'(\d+)[-.](\d+)', position)
            if match:disc, number = map(int, match.groups())
            elif position.isdecimal():disc, number = 1, int(position)
            else:
                disc, number = 1, len(tracks)+1
                warning = 'Some provider track positions need review; check the disc and track numbers.'
            while (disc,number) in used or number < 1 or disc < 1:
                disc,number=1,number+1
                warning = 'Some provider track positions need review; check the disc and track numbers.'
            used.add((disc,number))
            tracks.append({'disc':disc,'track':number,'name':item.get('title') or 'Untitled',
                           'duration_seconds':_discogs_duration(item.get('duration'))})
    walk(data.get('tracklist', []))
    fields = {'name':data.get('title',''), 'artist':artist, 'release_year':data.get('year') or None,
              'genre':', '.join(genres), 'label':', '.join(dict.fromkeys(x['name'] for x in data.get('labels',[]) if x.get('name'))),
              'barcode':barcode,'disc_count':max(declared,max((x['disc'] for x in tracks),default=1))}
    images=[]
    for index,image in enumerate(data.get('images',[]),1):
        url=image.get('uri') or ''
        if url.startswith('https://'):
            images.append(('Discogs '+str(image.get('type') or 'image')+' '+str(index),url))
    return {'fields':fields,'tracks':tracks,'artwork_options':images,'warning':warning,
            'source':'Discogs','id':ident,'url':'https://www.discogs.com/release/'+ident,
            'artwork_loaded':True}


def load_release(item, token='', *, include_artwork=False):
    source, ident = release_id(item)
    if source == 'Discogs':return load_discogs(item, token)
    data = get_json('https://musicbrainz.org/ws/2/release/' + ident + '?' +
                    urlencode({'fmt': 'json', 'inc': 'artist-credits+labels+recordings+genres'}))
    date = str(data.get('date', ''))[:4]
    fields = {'name': data.get('title', ''), 'artist': artist_name(data),
              'release_year': int(date) if date.isdecimal() else None,
              'barcode': data.get('barcode', ''),
              'label': ', '.join(dict.fromkeys(x['label']['name'] for x in data.get('label-info', []) if x.get('label', {}).get('name'))),
              'genre': ', '.join(x['name'] for x in data.get('genres', []) if x.get('name')),
              'disc_count': max(1, len(data.get('media', [])))}
    tracks = []
    for index, medium in enumerate(data.get('media', []), 1):
        for pos, track in enumerate(medium.get('tracks', []), 1):
            ms = track.get('length')
            tracks.append({'disc': medium.get('position') or index, 'track': track.get('position') or pos,
                           'name': track.get('title') or track.get('recording', {}).get('title') or 'Untitled',
                           'duration_seconds': round(ms / 1000) if isinstance(ms, (int, float)) and ms >= 0 else None})
    result = {'fields':fields,'tracks':tracks,'artwork_options':[],'warning':'', 'source':source,'id':ident,
              'url':'https://musicbrainz.org/release/'+ident,'artwork_loaded':False}
    if include_artwork:result=load_artwork(result,token)
    return result


def load_artwork(result, token=''):
    result = copy.deepcopy(result)
    if result.get('artwork_loaded'):return result
    source, ident = release_id(result)
    if source == 'Discogs':return load_discogs(result, token)
    options = []
    try:
        art = get_json('https://coverartarchive.org/release/' + ident)
        for index,image in enumerate(art.get('images', []),1):
            url = image.get('image')
            label = ', '.join(image.get('types', [])) or 'Release artwork'
            if isinstance(url, str) and url.startswith(('http://','https://')):
                options.append((label+' '+str(index),url.replace('http://','https://',1)))
        result['artwork_loaded']=True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:result['artwork_loaded']=True
        else:result['warning']='Artwork lookup failed; try Discogs or local images.'
    except Exception:
        result['warning']='Artwork lookup failed; try Discogs or local images.'
    result['artwork_options']=options
    return result
