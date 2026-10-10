"""Bounded, cached CD image downloads. UI callbacks consume a queue only."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

_cache=OrderedDict()
_lock=threading.Lock()
_LIMIT=32*1024*1024


def fetch_image(url):
    with _lock:
        if url in _cache:
            value=_cache.pop(url);_cache[url]=value
            return value
    from artwork_manager import fetch
    value=fetch(url)
    if len(value[0])<=_LIMIT:
        with _lock:
            _cache[url]=value
            while sum(len(x[0]) for x in _cache.values())>_LIMIT:
                _cache.popitem(last=False)
    return value


def download_batch(options, cancel, emit):
    """At most four image requests in flight; never call Tk from a worker."""
    items=iter(options)
    pool=ThreadPoolExecutor(max_workers=4,thread_name_prefix='cd-art')
    pending={}
    def schedule():
        if cancel.is_set():return False
        try:label,url=next(items)
        except StopIteration:return False
        pending[pool.submit(fetch_image,url)]=(label,url)
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
