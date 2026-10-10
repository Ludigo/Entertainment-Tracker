"""Expand only artwork published by the selected metadata provider."""
import re


def enrich_with_artwork(kind,item,token='',season=None):
    from metadata_finder import enrich,get_json
    if item.get('source')=='TMDB' and kind in ('movies','shows'):
        from add_media_metadata import load_tmdb
        data=load_tmdb(kind,item,token,season,download_artwork=False)
        item.update({key:value for key,value in data['fields'].items() if key!='name'})
        item['artwork_options']=[('TMDB '+label,url) for label,url in data.get('image_options',[])]
        return item
    item=enrich(kind,item,token)
    choices=list(item.get('artwork_options') or [])
    if item.get('source')=='Google Books':
        if re.fullmatch(r'[A-Za-z0-9_-]+',str(item.get('google_id') or '')):
            try:
                data=get_json('https://www.googleapis.com/books/v1/volumes/'+item['google_id'])
                item['image_links']={**(item.get('image_links') or {}),**((data.get('volumeInfo') or {}).get('imageLinks') or {})}
            except Exception as e:item['artwork_warning']='Additional Google Books images could not be loaded: '+str(e)
        choices.extend(('Google Books '+key,url.replace('http:','https:')) for key,url in (item.get('image_links') or {}).items() if isinstance(url,str))
    if item.get('source')=='Open Library':
        ids=[]
        match=re.search(r'/b/id/(\d+)',item.get('cover') or '')
        if match:ids.append(int(match[1]))
        detail=item.get('detail') or ''
        if detail.startswith('https://openlibrary.org/'):
            try:
                data=get_json(detail+'.json');ids.extend(x for x in data.get('covers',[]) if type(x) is int and x>0)
            except Exception as e:item['artwork_warning']='Additional Open Library covers could not be loaded: '+str(e)
        for ident in dict.fromkeys(ids):
            for size,label in [('L','large'),('M','medium'),('S','small')]:
                choices.append((f'Open Library cover {ident} ({label})',f'https://covers.openlibrary.org/b/id/{ident}-{size}.jpg?default=false'))
    item['artwork_options']=choices
    return item
