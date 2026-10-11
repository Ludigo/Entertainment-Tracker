"""Bounded, cached CD image downloads. UI callbacks consume a queue only."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

_cache=OrderedDict()
_lock=threading.Lock()
_LIMIT=32*1024*1024


def fetch_image(url,game_auth=None):
    with _lock:
        if url in _cache:
            value=_cache.pop(url);_cache[url]=value
            return value
    from artwork_manager import fetch
    value=fetch(url,game_auth=game_auth)
    if len(value[0])<=_LIMIT:
        with _lock:
            _cache[url]=value
            while sum(len(x[0]) for x in _cache.values())>_LIMIT:
                _cache.popitem(last=False)
    return value


def download_batch(options, cancel, emit,game_auth=None):
    """At most four image requests in flight; never call Tk from a worker."""
    items=iter(options)
    pool=ThreadPoolExecutor(max_workers=4,thread_name_prefix='cd-art')
    pending={}
    def schedule():
        if cancel.is_set():return False
        try:label,url=next(items)
        except StopIteration:return False
        pending[pool.submit(fetch_image,url,game_auth)]=(label,url)
        return True
    try:
        for _ in range(4):schedule()
        while pending and not cancel.is_set():
            future=next(as_completed(pending))
            label,url=pending.pop(future)
            try:
                value=future.result()
                if not cancel.is_set():emit('image',(*value,label,url))
            except Exception:
                if not cancel.is_set():emit('failure',label)
            schedule()
    finally:
        for future in pending:future.cancel()
        pool.shutdown(wait=False,cancel_futures=True)
        if not cancel.is_set():emit('done',None)


def collect_images(options, cancel=None,game_auth=None):
    """Download a batch on a worker and return successes plus a failure count."""
    cancel=cancel or threading.Event();images=[];failures=[]
    def emit(kind,value):
        if kind=='image':images.append(value)
        elif kind=='failure':failures.append(value)
    download_batch(list(dict((url,(label,url)) for label,url in options).values()),cancel,emit,game_auth=game_auth)
    return images,len(failures)
