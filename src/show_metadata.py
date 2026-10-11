"""Fetch metadata for saved seasons of one explicitly selected provider show."""
FIELDS=[('description','Description'),('release_year','Release year'),('network','Network'),
        ('genre','Genre'),('episode_count','Episodes'),('runtime','Season runtime'),('cover_path','Cover art')]


def load(item,records,token=''):
    from metadata_finder import get_json,plain
    from utils import format_time
    output=[];cache={}
    provider=item['source']
    if provider not in ('TMDB','TVmaze'):raise ValueError('Choose TVmaze or TMDB for season metadata.')
    maze_seasons=None
    if provider=='TVmaze':
        ident=str(item.get('tvmaze_id',''))
        if not ident.isdecimal():raise ValueError('Invalid TVmaze show match.')
        maze_seasons={s['number']:s for s in get_json(f'https://api.tvmaze.com/shows/{ident}/seasons')}
    for record in records:
        number=record['season']
        if number not in cache:
            try:
                if provider=='TMDB':
                    from add_media_metadata import load_tmdb
                    data=load_tmdb('shows',item,token,number,download_artwork=False)
                    values=dict(data['fields']);values.pop('name',None);values.pop('season',None)
                    values['artwork_options']=data.get('image_options',[])
                    cover=next((url for label,url in data.get('image_options',[]) if 'poster' in label.lower()),None)
                    if cover:values['cover']=cover
                    warning=data.get('warning','')
                else:
                    season=maze_seasons.get(number)
                    if season is None:raise ValueError('This saved season is not listed by TVmaze.')
                    episodes=get_json(f'https://api.tvmaze.com/seasons/{season["id"]}/episodes')
                    values={key:item.get(key) for key in ('description','release_year','network','genre')}
                    if season.get('summary'):values['description']=plain(season['summary'])
                    if season.get('premiereDate'):values['release_year']=season['premiereDate'][:4]
                    values['network']=((season.get('network') or season.get('webChannel') or {}).get('name')) or values.get('network')
                    cover=(season.get('image') or {}).get('original') or item.get('cover')
                    if cover:values['cover']=cover
                    # Unnumbered specials are not counted as regular episodes.
                    regular=[e for e in episodes if e.get('number') is not None]
                    values['episode_count']=len(regular)
                    runtimes=[e.get('runtime') for e in regular]
                    warning=''
                    if runtimes and all(type(r) in (int,float) and r>0 for r in runtimes):
                        values['runtime']=format_time(sum(runtimes)/60)
                    else:warning='Runtime unavailable: missing episode runtimes; existing runtime will be kept.'
                    values['artwork_options']=[('Season cover',cover)] if cover else []
                values.update(source=provider,title=item['title'])
                cache[number]=(values,warning)
            except Exception as exc:cache[number]=(None,str(exc))
        values,warning=cache[number]
        output.append({'id':record['id'],'season':number,'values':values,'warning':warning})
    return output
