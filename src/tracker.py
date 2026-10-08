"""Opt-in Windows game session logger. Requires psutil for process detection."""
import time
from datetime import datetime, timezone
from pathlib import Path
from database import cursor, connection

try:
    import psutil
except ImportError:
    psutil = None

class GameTracker:
    def __init__(self, root):
        self.root = root
        self.active = {}
        self.enabled = psutil is not None
        if self.enabled:
            root.after(5000, self.poll)

    def poll(self):
        if not self.root.winfo_exists():
            return
        try:
            self.scan()
        except Exception:
            pass
        self.root.after(5000, self.poll)

    def scan(self):
        cursor.execute("SELECT id, executable FROM games WHERE executable IS NOT NULL "
                       "AND TRIM(executable) != ''")
        mapping = {}
        for game_id, executable in cursor.fetchall():
            mapping.setdefault(str(Path(executable).resolve()).casefold(), set()).add(game_id)
        running = set()
        for process in psutil.process_iter(["exe"]):
            try:
                exe = process.info.get("exe")
                if exe:
                    key = str(Path(exe).resolve()).casefold()
                    running.update(mapping.get(key, ()))
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                continue
        now = time.monotonic()
        for game_id in running - self.active.keys():
            self.active[game_id] = (now, datetime.now(timezone.utc).isoformat())
        for game_id in set(self.active) - running:
            self.finish(game_id)

    def elapsed(self, game_id):
        started = self.active.get(game_id)
        return max(0, int(time.monotonic() - started[0])) if started else None

    def live_games(self):
        if not self.active:
            return []
        ids = list(self.active)
        placeholders = ",".join("?" for _ in ids)
        cursor.execute(f"SELECT id, name, platform FROM games WHERE id IN ({placeholders})", ids)
        return [(game_id, name, platform, self.elapsed(game_id))
                for game_id, name, platform in cursor.fetchall()]

    def finish(self, game_id):
        started = self.active.pop(game_id, None)
        if not started:
            return
        elapsed = max(0, round(time.monotonic() - started[0]))
        if elapsed < 5:
            return
        cursor.execute("SELECT id FROM games WHERE id = ?", (game_id,))
        if cursor.fetchone() is None:
            return
        cursor.execute("INSERT INTO game_sessions "
                       "(game_id, started_at, ended_at, duration_seconds, source) "
                       "VALUES (?, ?, ?, ?, 'automatic')",
                       (game_id, started[1], datetime.now(timezone.utc).isoformat(), elapsed))
        cursor.execute("UPDATE games SET playtime = playtime + ? WHERE id = ?",
                       (elapsed / 3600, game_id))
        connection.commit()

    def stop(self):
        for game_id in list(self.active):
            self.finish(game_id)
