import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = DATA_DIR / "entertainment.db"

connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()


def setup_database():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        platform TEXT NOT NULL,
        playtime REAL NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        runtime REAL NOT NULL,
        watch_count INTEGER NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        season INTEGER NOT NULL,
        runtime REAL NOT NULL,
        episode_count INTEGER NOT NULL,
        episode_reached INTEGER NOT NULL DEFAULT 0,
        completed INTEGER NOT NULL DEFAULT 0,
        in_progress INTEGER NOT NULL DEFAULT 0,
        watch_count INTEGER NOT NULL DEFAULT 0,
        owned INTEGER NOT NULL DEFAULT 0,
        type TEXT,
        genre TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        reading_time REAL NOT NULL,
        completed INTEGER NOT NULL DEFAULT 0,
        in_progress INTEGER NOT NULL DEFAULT 0,
        read_count INTEGER NOT NULL DEFAULT 0,
        owned INTEGER NOT NULL DEFAULT 0,
        type TEXT,
        genre TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)
    cursor.execute("PRAGMA table_info(books)")
    book_columns = [column[1] for column in cursor.fetchall()]
    if "page_count" not in book_columns:
        cursor.execute("ALTER TABLE books ADD COLUMN page_count INTEGER NOT NULL DEFAULT 0")

    # Cover art is stored as a relative file path rather than as image data.
    # These migrations preserve existing libraries in-place.
    for table in ("games", "movies", "shows", "books"):
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [column[1] for column in cursor.fetchall()]
        if "cover_path" not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN cover_path TEXT")

    for table in ('movies', 'shows'):
        cursor.execute(f"PRAGMA table_info({table})")
        if "background_path" not in {column[1] for column in cursor.fetchall()}:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN background_path TEXT")

    cursor.execute("PRAGMA table_info(games)")
    game_columns = {column[1] for column in cursor.fetchall()}
    if "in_progress" not in game_columns:
        cursor.execute("ALTER TABLE games ADD COLUMN in_progress INTEGER NOT NULL DEFAULT 0")
    if "executable" not in game_columns:
        cursor.execute("ALTER TABLE games ADD COLUMN executable TEXT")
    for column, declaration in (
        ("price_paid", "REAL"),
        ("completed", "INTEGER NOT NULL DEFAULT 0"),
        ("backlog", "INTEGER NOT NULL DEFAULT 0"),
        ("started", "INTEGER NOT NULL DEFAULT 0"),
        ("description", "TEXT"),
    ):
        if column not in game_columns:
            cursor.execute(f"ALTER TABLE games ADD COLUMN {column} {declaration}")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL,
            source TEXT NOT NULL,
            FOREIGN KEY(game_id) REFERENCES games(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            FOREIGN KEY(game_id) REFERENCES games(id)
        )
    """)
    cursor.execute("""CREATE TABLE IF NOT EXISTS artwork_library (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        image_path TEXT NOT NULL,
        width INTEGER NOT NULL,
        height INTEGER NOT NULL,
        source TEXT,
        UNIQUE(category, item_id, image_path)
    )""")
    # Workbook fields retained even when a category form does not edit them yet.
    extra_columns = {
        "games": {"achievements_unlocked": "INTEGER", "achievements_total": "INTEGER",
                  "cex_value": "REAL", "release_year": "INTEGER", "barcode": "TEXT"},
        "movies": {"completed": "INTEGER DEFAULT 0", "in_progress": "INTEGER DEFAULT 0",
                   "owned": "INTEGER DEFAULT 0", "type": "TEXT", "genre": "TEXT"},
        "books": {"price_paid": "REAL", "author": "TEXT", "series": "TEXT",
                  "release_year": "INTEGER"},
    }
    for table, columns in extra_columns.items():
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {r[1] for r in cursor.fetchall()}
        for column, declaration in columns.items():
            if column not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
    for table in ('books', 'movies', 'shows'):
        cursor.execute(f'PRAGMA table_info({table})')
        if 'description' not in {r[1] for r in cursor.fetchall()}:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN description TEXT')
    # Optional rich metadata, added without changing existing records.
    rich_fields = {
        "movies": {"release_year": "INTEGER", "director": "TEXT", "cast_members": "TEXT",
                   "rating": "TEXT", "price_paid": "REAL", "notes": "TEXT"},
        "shows": {"release_year": "INTEGER", "network": "TEXT", "rating": "TEXT",
                  "price_paid": "REAL", "notes": "TEXT"},
        "books": {"publisher": "TEXT", "isbn": "TEXT", "rating": "TEXT", "notes": "TEXT"},
    }
    for table, definitions in rich_fields.items():
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        for field, definition in definitions.items():
            if field not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {field} {definition}")
    session_columns = {row[1] for row in connection.execute('PRAGMA table_info(game_sessions)')}
    if 'note' not in session_columns:
        connection.execute("ALTER TABLE game_sessions ADD COLUMN note TEXT NOT NULL DEFAULT ''")
    # Non-destructive game metadata migration; all fields are optional.
    cursor.execute("PRAGMA table_info(games)")
    game_fields = {row[1] for row in cursor.fetchall()}
    for field in ("release_date", "genre", "developer", "publisher",
                  "game_modes", "age_rating"):
        if field not in game_fields:
            cursor.execute(f"ALTER TABLE games ADD COLUMN {field} TEXT")
    connection.commit()
    from artwork_preferences import install_artwork_guards
    install_artwork_guards()


def close_database():
    connection.close()


def get_setting(key, default=None):
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row[0] if row else default


def set_setting(key, value):
    cursor.execute("""
    INSERT INTO settings (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(value)))
    connection.commit()
