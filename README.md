# Entertainment Tracker v1.0

This is the **beta development branch**. The latest Windows-tested and approved build is **Beta 1.76 — Album Grouping & IGDB**. The next candidate is **Beta 1.77**. Candidate source is published here after Windows testing and approval. The stable product version is **v1.0** (legacy `v19` tag).

A personal, non-commercial Windows desktop application built with Python.

Entertainment Tracker helps organise and track video games, movies, television shows, books and CDs/digital albums in one place.

## Features

- Game playtime tracking
- Movie and TV show collection management
- Book collection management
- CD and digital album ownership, multi-disc tracklists and listening activity
- Artwork and cover management
- Metadata lookup from external APIs
- SteamGridDB game covers, backgrounds, logos and icons
- IGDB game metadata, covers and screenshots
- Physical and digital ownership across all libraries
- Unified recorded game, album and book Activity History
- Personal entertainment statistics
- In-window Continue hub with quick episode, page and completion updates
- Backlog picks with section, platform, genre and recorded-runtime filters
- Monthly completion goals and dated recent additions
- Optional album edition grouping with individual album exceptions

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

## Album editions

**Settings → Album Editions → Group album editions** controls whether albums with matching titles and artists appear together. It is enabled by default. Turn it off to show each saved album separately. In Album Metadata, tick **Keep this album separate** for individual exceptions. Missing artists are not grouped. These preferences also apply to the edition selector and random picks; no saved albums, artwork or listening history are merged or deleted.

## Game providers

Open **Settings → Game Providers** to save your SteamGridDB API key and IGDB/Twitch Client ID and Client Secret locally. For IGDB, enable Twitch two-factor authentication, register a **Confidential** application, use `http://localhost` for its redirect URL and generate a Client Secret. The app obtains and renews its access token automatically. Settings includes a link to the [official setup instructions](https://api-docs.igdb.com/#account-creation).

Select IGDB in the existing Games metadata finder for descriptions, platform-specific releases, genres, developers, publishers, game modes, age ratings, covers, regional cover alternatives, backgrounds and screenshots where available. Review fields before applying them. Load artwork separately and assign Cover, Background, Logo or Extra in the existing controls. SteamGridDB remains available for additional artwork, including logos and icons.

IGDB access is free for non-commercial use under the Twitch Developer Service Agreement. See [IGDB documentation](https://api-docs.igdb.com/) and [SteamGridDB API documentation](https://www.steamgriddb.com/api/v2). Credentials and access tokens are not included in this distribution.

## Updating safely

Back up your existing installation before replacing application source files. Preserve your local `data/`, `assets/`, `backups/` and `media_quarantine/` folders. Launch the app normally after updating. Portable backups include local assets, but do not automatically copy artwork referenced by external paths or URLs.

## Privacy

The public repository and GitHub-generated source archives contain no personal databases, backups, downloaded artwork collections, saved API credentials or cache files. Supply any required TMDB token locally. Keep your private collection and recovery archives out of Git.

## Validation

The attached completed Phase 1 build was Windows-tested by the maintainer. Publication checks verify Python syntax and source-file identity; they do not repeat Windows GUI testing.


## Change history

See [CHANGELOG.md](CHANGELOG.md) for release notes and beta change history.

