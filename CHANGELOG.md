# Changelog

## Beta 1.64 — Unified Add & Collection Sections

Windows-tested and approved by the maintainer, including artwork assignment and Settings layout corrections.

- Games, Movies, Shows and Books use the Album-style Add layout with embedded provider search, checked-field review and staged artwork.
- All five Add editors share the artwork panel, with thumbnails and visible Set Cover, Set Background and Toggle Extra controls. Games adds Logo options under More.
- Drafts, search results and Show season choices remain available across tabs; clear draft/save feedback and discard safeguards are retained.
- Consistent duplicate warnings for Games, Books and Albums allow another copy or edition.
- Settings can hide collection sections from navigation, dashboard and unified History while preserving saved collection and session data.
- Settings backup/recovery and maintenance actions use grouped, equal-width buttons with consistent spacing.
- Beta 1.63 Enter/keypad Enter handling and album previews retained.

## Beta 1.63 — Ownership, Activity & Streamlined Albums

Windows-tested and approved by the maintainer, including the corrected full patch.

- Physical and digital ownership across Games, Movies, Shows and Books; existing Owned records retain unspecified format.
- Unified Activity History for recorded game, CD and book sessions. Existing reading totals do not invent past sessions.
- Cached, parallel artwork downloads across sections, separate from metadata lookup.
- Album search, metadata, tracks and artwork stay inside the editor, with clear draft and saved confirmations.
- Visible album artwork thumbnails with Cover, Background and Extra labels; double-click opens a larger preview.
- Enter and keypad Enter run searches in libraries, metadata finders, album finder, artwork search and bulk editing, with priority bindings.
- Imports and artwork remain staged until Save; cancellation and artwork protection safeguards retained.

## v1.0 — Data Safety & Reliability Update

This release publishes the completed Phase 1 version, Windows-tested by the maintainer.

- Portable ZIP backups include the SQLite database and locally stored artwork. Manual backups and automatic backups (at most once per UTC day) are available; the newest 10 standard backups are retained.
- Backup restore validates ZIP paths, ZIP integrity and SQLite integrity, queues restoration for the next launch, and creates a pre-restore safety archive.
- A read-only offline audit reports saved descriptions, missing media, remote-only images and files outside the application folder.
- Existing local media can be previewed and renamed to descriptive, Windows-safe filenames. Renaming creates a safety backup, updates database references in a transaction and reverses file moves on failure.
- Conservative unused-media scanning protects referenced and uncertain files. Selected unused images move to `media_quarantine/` after a safety backup; they are never permanently deleted. To recover quarantined files, close the app and move them back to their original locations.


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
