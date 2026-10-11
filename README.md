# Entertainment Tracker v1.0

This is the **beta development branch**. The latest Windows-tested and approved source is **Beta 1.69 — Show Summaries, Metadata & Logos**. The next candidate is **Beta 1.70**. Candidate source is published here after Windows testing and approval. The stable product version is **v1.0** (legacy `v19` tag).

A personal, non-commercial Windows desktop application built with Python.

Entertainment Tracker helps organise and track video games, movies, television shows, books and CDs/digital albums in one place.

## Features

- Game playtime tracking
- Movie and TV show collection management
- Book collection management
- CD and digital album ownership, multi-disc tracklists and listening activity
- Artwork and cover management
- Metadata lookup from external APIs
- Physical and digital ownership across all libraries
- Unified recorded game, album and book Activity History
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

## Updating safely

Back up your existing installation before replacing application source files. Preserve your local `data/`, `assets/`, `backups/` and `media_quarantine/` folders. Launch the app normally after updating. Portable backups include local assets, but do not automatically copy artwork referenced by external paths or URLs.

## Privacy

The public repository and GitHub-generated source archives contain no personal databases, backups, downloaded artwork collections, saved API credentials or cache files. Supply any required TMDB token locally. Keep your private collection and recovery archives out of Git.

## Validation

The attached completed Phase 1 build was Windows-tested by the maintainer. Publication checks verify Python syntax and source-file identity; they do not repeat Windows GUI testing.


## Change history

See [CHANGELOG.md](CHANGELOG.md) for release notes and beta change history.

