# Entertainment Tracker

A personal, non-commercial Windows desktop application built with Python.

Entertainment Tracker helps organise and track video games, movies, television shows and books in one place.

## Features

- Game playtime tracking
- Movie and TV show collection management
- Book collection management
- Artwork and cover management
- Metadata lookup from external APIs
- Personal entertainment statistics

## TMDB Integration

Entertainment Tracker uses The Movie Database (TMDB) API to retrieve movie and television metadata, including descriptions, release dates, posters and background artwork.

This project is for personal, non-commercial use.

This product uses the TMDB API but is not endorsed or certified by TMDB.


## Getting started (Windows)

1. Install Python 3 with Tkinter support, and ensure `pythonw` is available on your PATH.
2. Download or clone this repository.
3. Open a terminal in the repository folder and run `python -m pip install -r requirements.txt`.
4. Double-click `Entertainment Tracker.bat` to start the app.

The app creates its local `data/entertainment.db` database automatically when launched. Local databases and downloaded artwork are intentionally not included in the public repository. Keep backups of your personal library before updating the application.

Optional process-based game tracking uses `psutil` (install with `python -m pip install psutil`).
