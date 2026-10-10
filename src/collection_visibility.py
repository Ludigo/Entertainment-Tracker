"""Display preferences only: collection rows and session data are never removed."""
from database import connection, get_setting

SECTIONS = {'games': 'Games', 'movies': 'Movies', 'shows': 'Shows',
            'books': 'Books', 'cds': 'CDs'}


def enabled(kind):
    if kind not in SECTIONS:
        raise ValueError('Unknown collection section')
    return get_setting('section_visible_' + kind, '1') != '0'


def visible_sections():
    return [kind for kind in SECTIONS if enabled(kind)]


def save_visibility(values):
    if set(values) != set(SECTIONS):
        raise ValueError('Choose visibility for every collection section')
    with connection:
        connection.executemany('INSERT INTO settings(key,value) VALUES(?,?) '
                               'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                               [('section_visible_'+kind, '1' if values[kind] else '0')
                                for kind in SECTIONS])
