# Entertainment Tracker v1.0

This is the **beta development branch**. The latest Windows-tested and approved source is **Beta 1.62 — Polished CDs & Discogs**. The next candidate is **Beta 1.63**; subsequent builds continue Beta 1.64, Beta 1.65, and so on. Candidate source is published here after Windows testing and approval. The stable product version is **v1.0** (legacy `v19` tag).

A personal, non-commercial Windows desktop application built with Python.

Entertainment Tracker helps organise and track video games, movies, television shows, books and CDs/digital albums in one place.

## Features

- Game playtime tracking
- Movie and TV show collection management
- Book collection management
- CD and digital album ownership, multi-disc tracklists and listening activity
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

## Beta 1.60 — Artwork and Show Seasons

Windows-tested and approved by the maintainer.

- Expanded editing-finder artwork choices for movies, shows and books, with incremental gallery loading.
- Multiple saved seasons appear under one show listing, with season selection and individual season actions.
- Saved season records and tracking values remain intact.

## Beta 1.61 — CDs & Albums

Windows-tested and approved by the maintainer.

- CD/digital album library with independent physical and digital ownership, multi-disc tracks, metadata and local artwork.
- Listening time, full-album play counts and recorded listening sessions.
- Additive database setup and CD coverage in portable backups, artwork protection and offline safety tools.

## Beta 1.62 — Polished CDs & Discogs

Windows-tested and approved by the maintainer.

- In-app cinematic album details with independent cover/background artwork, Album Information and My Listening Activity.
- Embedded listening timer, complete listening history and full-album play actions.
- Matching Add/Metadata forms with structured track editing, field review and staged artwork saved atomically with album metadata.
- Library Back restores search, ownership filter, sorting, selection, view, pagination and scroll.
- MusicBrainz metadata loads independently of optional Cover Art Archive lookup. CD artwork uses bounded parallel downloads and in-memory caching.
- Discogs release/barcode lookup, edition metadata, tracklists and returned artwork choices. Enter your personal access token in the album finder; Save Token Locally retains it only in your local settings. Generate a token at https://www.discogs.com/settings/developers . MusicBrainz remains available without a token.
- Existing movie/show/book metadata and artwork workflows retained.

Timer sessions add elapsed listening time; Log Full Album Play adds one play and the complete tracklist duration. Choose the appropriate method for each listen to avoid counting the same time twice. Unknown track durations stay unknown.
