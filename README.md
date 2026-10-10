# Entertainment Tracker v1.0

This is the **beta development branch**. The latest Windows-tested and approved source is **Beta 1.59 — Metadata-first Movies and Shows**. The next candidate is **Beta 1.60**; subsequent builds continue Beta 1.61, Beta 1.62, and so on. Candidate source is published here after Windows testing and approval. The stable product version is **v1.0** (legacy `v19` tag).

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

## v1.0 — Data Safety & Reliability Update

This release publishes the completed Phase 1 version, Windows-tested by the maintainer.

- Portable ZIP backups include the SQLite database and locally stored artwork. Manual backups and automatic backups (at most once per UTC day) are available; the newest 10 standard backups are retained.
- Backup restore validates ZIP paths, ZIP integrity and SQLite integrity, queues restoration for the next launch, and creates a pre-restore safety archive.
- A read-only offline audit reports saved descriptions, missing media, remote-only images and files outside the application folder.
- Existing local media can be previewed and renamed to descriptive, Windows-safe filenames. Renaming creates a safety backup, updates database references in a transaction and reverses file moves on failure.
- Conservative unused-media scanning protects referenced and uncertain files. Selected unused images move to `media_quarantine/` after a safety backup; they are never permanently deleted. To recover quarantined files, close the app and move them back to their original locations.

### Updating safely

Back up your existing installation before replacing application source files. Preserve your local `data/`, `assets/`, `backups/` and `media_quarantine/` folders. Launch the app normally after updating. Portable backups include local assets, but do not automatically copy artwork referenced by external paths or URLs.

### Privacy

The public repository and GitHub-generated source archives contain no personal databases, backups, downloaded artwork collections, saved API credentials or cache files. Supply any required TMDB token locally. Keep your private collection and recovery archives out of Git.

### Validation

The attached completed Phase 1 build was Windows-tested by the maintainer. Publication checks verify Python syntax and source-file identity; they do not repeat Windows GUI testing.

## Beta 1.57 — Cinematic Shows

Windows-tested and approved by the maintainer.

- Cinematic Shows details with local background artwork and independent cover presentation.
- Show Information and My Show Activity panels retain saved metadata and existing watch-time calculations.
- Show backgrounds can be selected, cleared and protected through Artwork Collection, with offline audit, relink and portable backup support.
- Episode progress displays saved current-season counts, with guidance for missing or invalid totals.
- Existing metadata editors and embedded Books timer retained.

## Beta 1.58 — Cinematic Books

Windows-tested and approved by the maintainer.

- Cinematic Books details with Book Information and My Book Activity panels, descriptions and personal notes.
- Independent locally saved and protected book backgrounds, with relink, audit, cleanup and portable backup support.
- Optional Page reached field in Metadata and a page-progress bar. Existing unknown progress stays unrecorded.
- Completed Books and Shows display 100% progress while retaining saved page and episode counts.
- Existing embedded reading timer retained.

## Beta 1.59 — Metadata-first Movies and Shows

Windows-tested and approved by the maintainer.

- Full Add Movie/Show metadata forms with TMDB search and selected-field review protecting entered values.
- Staged local/provider cover and background choices, previews and extra artwork; Save commits metadata and artwork together and Cancel discards the draft.
- Show season selection with supplied episode counts and runtime only when every episode runtime is available.
- Duplicate title/year/season warnings allow an explicitly chosen additional copy.
- Search results, selected result and season remain available during artwork review in the Add session.
