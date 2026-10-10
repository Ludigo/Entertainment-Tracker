"""Manual stopwatch for games and books. Uses monotonic time while running."""
from window_style import install as polish_dialog

import time
from datetime import datetime, timezone
import tkinter as tk
from tkinter import messagebox
from database import connection
from theme import BG, PANEL, PANEL_ALT, TEXT, MUTED


def stamp():
    return datetime.now(timezone.utc).isoformat()


class ManualTimer:
    def __init__(self, root):
        self.root = root
        self.kind = None
        self.item_id = None
        self.title = ''
        self.seconds = 0.0
        self.since = None
        self.started_at = None

    def elapsed(self):
        return self.seconds + (time.monotonic() - self.since if self.since is not None else 0)

    def start(self, kind, item_id, title):
        if self.kind is not None and (self.kind, self.item_id) != (kind, item_id):
            raise ValueError(f'Finish the timer for {self.title} first.')
        if self.kind is None:
            self.kind, self.item_id, self.title = kind, item_id, title
            self.started_at = stamp()
            self.seconds = 0
        if self.since is None:
            self.since = time.monotonic()

    def pause(self):
        if self.since is not None:
            self.seconds = self.elapsed()
            self.since = None

    def resume(self):
        if self.kind is not None and self.since is None:
            self.since = time.monotonic()

    def stop(self, auto_tracker=None, note=''):
        if self.kind is None:
            return 0
        note=str(note or '').strip()
        if len(note)>2000:raise ValueError('Keep the session note to 2,000 characters or fewer.')
        self.pause()
        seconds = max(0, round(self.seconds))
        kind, item_id = self.kind, self.item_id
        if kind == 'games' and auto_tracker and item_id in auto_tracker.active:
            raise ValueError('Automatic game tracking is active. Stop the game first to avoid double-counting.')
        if seconds:
            with connection:
                if kind == 'games':
                    connection.execute('UPDATE games SET playtime = COALESCE(playtime,0) + ?, started = 1 WHERE id = ?', (seconds / 3600, item_id))
                    connection.execute('INSERT INTO game_sessions (game_id, started_at, ended_at, duration_seconds, source, note) VALUES (?, ?, ?, ?, ?, ?)',
                                       (item_id, self.started_at, stamp(), seconds, 'manual', note))
                elif kind == 'books':
                    connection.execute('UPDATE books SET reading_time = COALESCE(reading_time,0) + ? WHERE id = ?', (seconds / 3600, item_id))
        self.kind, self.item_id, self.title = None, None, ''
        self.seconds, self.since, self.started_at = 0, None, None
        return seconds


def clock(seconds):
    seconds = int(seconds)
    return f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'


def open_timer(parent, kind, item_id, title, accent, on_saved=None):
    root = parent.winfo_toplevel()
    timer = root.manual_timer
    tracker = getattr(root, 'game_tracker', None)
    dialog = tk.Toplevel(root)
    polish_dialog(dialog)
    dialog.title('Manual Session Timer')
    dialog.geometry('440x320')
    dialog.resizable(False, False)
    dialog.configure(bg=BG)
    dialog.transient(root)
    dialog.grab_set()
    tk.Label(dialog, text='MANUAL SESSION TIMER', bg=BG, fg=MUTED, font=('Arial', 10, 'bold')).pack(pady=(24, 6))
    tk.Label(dialog, text=title, bg=BG, fg=TEXT, font=('Arial', 15, 'bold'), wraplength=390).pack()
    display = tk.Label(dialog, text='00:00:00', bg=BG, fg=accent, font=('Arial', 35, 'bold'))
    display.pack(pady=(12, 4))
    status = tk.Label(dialog, bg=BG, fg=MUTED)
    status.pack()
    buttons = tk.Frame(dialog, bg=BG)
    buttons.pack(pady=18)

    def begin():
        try:
            if kind == 'games' and tracker and item_id in tracker.active:
                raise ValueError('This game is already being automatically tracked. Stop the game before starting a manual timer.')
            timer.start(kind, item_id, title)
        except ValueError as e:
            messagebox.showwarning('Timer', str(e), parent=dialog)
        refresh()

    def pause():
        timer.pause()
        refresh()

    def stop():
        try:
            note=''
            if kind=='games':
                from session_notes import ask_session_note
                note=ask_session_note(dialog,accent)
                if note is None:return
            seconds = timer.stop(tracker,note=note)
        except ValueError as e:
            messagebox.showwarning('Timer', str(e), parent=dialog)
            return
        messagebox.showinfo('Session saved', f'{clock(seconds)} added to your total.', parent=dialog)
        dialog.destroy()
        if on_saved: on_saved()

    start_btn = tk.Button(buttons, text='Start / Resume', command=begin, bg=accent, fg='white', relief='flat', padx=14, pady=10)
    start_btn.pack(side='left', padx=5)
    pause_btn = tk.Button(buttons, text='Pause', command=pause, bg=PANEL_ALT, fg=TEXT, relief='flat', padx=14, pady=10)
    pause_btn.pack(side='left', padx=5)
    stop_btn = tk.Button(buttons, text='Stop & Save', command=stop, bg=PANEL, fg=TEXT, relief='flat', padx=14, pady=10)
    stop_btn.pack(side='left', padx=5)
    tk.Label(dialog, text='Timer keeps running if you close this window.\nStop & Save adds the session to your total.',
             bg=BG, fg=MUTED, justify='center').pack()

    def refresh():
        if not dialog.winfo_exists(): return
        same = timer.kind == kind and timer.item_id == item_id
        display.configure(text=clock(timer.elapsed() if same else 0))
        state = 'Running' if same and timer.since is not None else 'Paused' if same else 'Ready'
        status.configure(text=state if same or timer.kind is None else f'Another timer is active: {timer.title}')
        start_btn.configure(state='normal' if timer.kind is None or same and timer.since is None else 'disabled')
        pause_btn.configure(state='normal' if same and timer.since is not None else 'disabled')
        stop_btn.configure(state='normal' if same else 'disabled')
        dialog.after(250, refresh)
    refresh()
