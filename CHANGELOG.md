## Beta 1.69 — Metadata scrolling and logos

Windows-tested and approved by the maintainer.

- Metadata editors scroll in fixed steps, with the form handler preceding field handlers.
- Movies, shows, books and albums support logos through Artwork Collection: set, clear, lock and relink. Details use the logo header with a title fallback.
- Show summary logo changes apply to every saved season; individual season changes remain independent.
- Includes all Beta 1.68 show summary, shared artwork and Get All Metadata work.

## Beta 1.68 — Show summary details

Windows-tested and approved by the maintainer.

- Get All Metadata on Show summary looks up every saved season from one selected TVmaze/TMDB show match, with per-season field previews and optional artwork import. Existing values are unchecked by default. Missing runtimes and failed seasons are reported without guessing values; personal viewing records stay unchanged.

- Cover/background choices made from Show summary apply to all saved seasons. Individual season choices remain independent. Summary artwork changes respect locks on every season.

- One shared artwork collection across saved seasons, including existing covers/backgrounds. Files are reused; individual season cover/background selections remain available. Shared removal honours locks across all seasons.

- Grouped shows open a summary of all saved seasons, with total episodes, runtime, watch time, price and episode progress.
- The selector includes Show summary and individual seasons. Each season keeps its own metadata and tracking.
- Editing from the summary offers a season chooser. Delete This Season is available only within a season.
- Season descriptions, notes and a season breakdown appear in the summary.

# Changelog

## Beta 1.67 — Games Details Style

Windows-tested and approved by the maintainer, including the final independent-panel and fixed-background scrolling correction.

- Replaces the earlier scroll redraw fix: Games and media panels are independent rounded images at the same document coordinates as text; the plain background is pinned synchronously and never scrolls with content.

- Scroll correction: Games redraws its rounded panel surface as content moves; cinematic media details refresh fixed artwork on scrollbar-originated scrolling as well as mouse-wheel scrolling.

- Games retains its existing panel layout, screenshots, description and recent sessions.
- Smooth dark rounded panels and subtle borders replace dotted overlays.
- Accent headings and lighter value typography match the other cinematic sections.


## Beta 1.66 — Consistent Library Headers

Windows-tested and approved by the maintainer, including the final independent-panel and fixed-background scrolling correction.

- CD-style bottom summaries added to Games, Movies, Shows and Books, showing filtered counts and saved activity totals in List and Covers views.

- Games correction: header styling skips ttk dropdowns so hidden legacy filters are not packed back into the search row.

- All five libraries use the CD-style header with consistent search/action button spacing.
- Edit, Delete, Bulk Edit, Export and Games Toggle Playing are accessible through Actions where applicable.
- Add and the selected List/Covers view retain accent styling through theme application.
- Shorter quick-action helper text; existing callbacks and right-click actions retained.


## Beta 1.65 — Collection Tools & Album Editions

Windows-tested and approved by the maintainer, including the corrected layout.

- Layout correction: advanced filter rows align consistently, expanded filters stay above the count footer, and CDs uses the Games-style centred heading/search/actions/view controls with ownership and sort in the shared filter panel.

- Album listings group independent artist/title editions, with an edition selector.
- Expanded metadata, ownership, wishlist, tags, seller and condition filters.
- Statistics shows recorded spend, ownership, activity and cost/hour for visible sections.
- Wishlist, custom tags, purchase date, seller/shop and condition across all sections.
- Book ISBN lookup through Open Library/Google Books and CD barcode lookup through MusicBrainz/Discogs; manual barcode entry elsewhere.
- Track listens save listening time and a snapshot/session without incrementing full-album plays.
- Quick actions update a selected record’s ownership, wishlist and applicable completion/watch status.
- Filtered CSV export includes actual records behind visible edition/season groups and useful metadata.
- Additive migration preserves existing collections, activity and preferences.
- Approved 1.64 Add artwork controls, previews, Enter handling and Settings layout retained.

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

