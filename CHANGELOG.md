## Beta 1.77 — Collection management

Windows-tested and approved by the maintainer. Cumulative patch based on the approved 1.76 build.

- Bulk editing: review and apply ownership, Games backlog, tags, condition and estimated values to selected records atomically.
- Duplicate review: compare records side by side and retain different editions, with album separation persisted.
- Missing metadata: filter missing covers, descriptions, years, artists/authors or backgrounds, including missing local image files.
- Saved views: store filters, sorting and search text independently for each library.
- Filtered CSV export: export the current collection selection with recorded estimated values.
- Wishlist purchases: record price per item, shop, purchase date and physical/digital formats together.
- Collection values: show recorded paid and estimated totals, plus the difference for entries with both values.
- Custom shelves: create named shelves and assign or remove selected records without changing tags.
- Session corrections: edit game, book and album dates, durations and notes, adjust totals by the duration difference, and update linked track listens without changing play counts.
- Artwork review queue: retain the current record while assigning Cover, Background or Logo; reuse existing metadata and artwork finders.
- New management controls stay in the main window. Existing image pickers and metadata dialogs remain available.
- All 67 Python modules compile. Data and UI fixture checks cover atomic changes, stale records, purchases, filters, presets, shelves, CSV, session corrections, artwork queue navigation and existing Continue/IGDB behavior. The maintainer confirmed all features work on Windows.

## Beta 1.76 — Album grouping preferences

Windows-tested and approved by the maintainer.

- Settings → Album Editions adds Group album editions, enabled by default and saved immediately. Turning it off shows each saved album separately in the library, details edition selector and random picks.
- Album Add/Metadata has a Keep this album separate checkbox. Its saved flag isolates that album even when global grouping is enabled.
- Matching continues to use normalized title and artist; missing artists/titles are isolated rather than grouping uncertain matches. Tracklists are not used to force matches.
- Additive database migration defaults existing albums to normal grouping. Switching settings or flags never merges/deletes saved records, tracklists, artwork or listening history.
- Grouping/migration/editor persistence checks pass and all 64 modules compile. Includes IGDB and approved fixed cover boxes.

## Beta 1.75 — IGDB game metadata and artwork

Candidate for Windows testing.

- Replaces ScreenScraper in every Games Add, Edit and detail lookup flow with IGDB. Removes its Settings fields and network integration; existing local artwork remains usable.
- Game Providers Settings now accepts IGDB/Twitch Client ID and Client Secret, with a link to setup instructions. The app obtains an access token automatically, reuses it in memory, renews it before expiry and retries authentication once after HTTP 401.
- Search results distinguish platform editions. Metadata supports descriptions, platform-specific release dates, genres, developers, publishers, game modes and PEGI/ESRB ratings. Unknown values remain absent rather than replacing manual entries.
- Artwork options include the cover, available regional alternatives, artwork/backgrounds and screenshots. Existing role assignment and selective metadata review remain. SteamGridDB remains available for logos, icons and other artwork.
- Credentials are captured on the UI thread. Requests are paced below IGDB's four-per-second limit; public artwork downloads send no provider credentials. Errors remain inline in existing finders.
- Includes the Windows-approved 1.74 fixed 600:900 cropped cover boxes and earlier Continue & Explore work.
- All 64 modules compile. Offline integration tests cover provider replacement, platform matches, parsing, selective imports, token reuse/expiry/401 renewal, missing credentials, HTTP errors, credential-free artwork fetching and Continue regressions. Authenticated IGDB and Windows UI checks remain pending.

## Beta 1.74 — Fixed 600:900 cover boxes

Windows-tested and approved by the maintainer.

- Restores fixed-width library cover boxes and crop-to-fill artwork as requested. Artwork uses the 600:900 ratio, displayed at 240 × 360 pixels inside its thin frame.
- Removes variable-width cover cards and side padding. Source images remain unchanged.
- All 64 modules compile. Includes previous provider and session-text changes; Windows appearance confirmation remains pending.

## Beta 1.73 — Thin cover side borders

Candidate for Windows testing.

- Cover-grid side frames now follow the fitted image width, removing the wider side padding introduced by 1.72. The complete artwork remains visible, with its proportions preserved.
- Keeps the consistent tile height and thin existing borders. No-artwork placeholders retain their usual size.
- Image checks confirm all four artwork edges remain visible without added side padding, and all 64 modules compile. Includes all 1.71 and 1.72 work; Windows appearance confirmation remains pending.

## Beta 1.72 — Full artwork in library tiles

Candidate for Windows testing.

- Library cover tiles now fit the entire artwork inside the box, preserving proportions and centring it on the existing dark background. Applies to games, movies, shows, books and albums.
- Image dimensions account for the tile border so the outer cover edges remain visible. Portrait, landscape, square and tall artwork are supported; transparent images use the tile background and EXIF orientation is honoured.
- Includes all Beta 1.71 provider and session-text changes. No source artwork files are altered.
- Image-output checks pass for all five libraries and four cover proportions; all 64 modules compile. Windows appearance confirmation remains pending.

## Beta 1.71 — Game providers and session text

Candidate for Windows testing.

- Recent Play Sessions now puts the count below the heading, alongside the duration column heading, with additional room for the empty state and session rows.
- SteamGridDB and ScreenScraper appear in Games Add, Edit and detail metadata finders. Existing metadata review and artwork role selection remain available.
- SteamGridDB offers up to 20 static images per artwork type: grids, heroes, logos and icons. Preview downloads use the existing batches and gallery; no extra provider windows are added.
- ScreenScraper searches titles and loads selected game metadata, regional cover variants, logos and screenshots. English descriptions/genres and European names/dates/covers are preferred when available.
- Settings → Game Providers stores a SteamGridDB key, ScreenScraper developer credentials and optional user login locally. ScreenScraper requires credentials issued for this software; a normal user account alone is insufficient.
- Credentials are captured before background work. Saved artwork URLs omit credentials; ScreenScraper media requests attach them only to its HTTPS API host. ScreenScraper downloads are serialized to accommodate single-request accounts.
- Narrow logos and 64-pixel icons are supported. Images remain size-limited, format-checked and stored in their original bytes.
- Offline fixture tests cover provider routing, response parsing, missing credentials, HTTP failures, artwork downloading, selective metadata import and actual session drawing positions. Continue hub regression tests pass. Authenticated provider lookups and Windows visual checks remain pending.

## Beta 1.70 — Continue & Explore

Windows-tested and approved by the maintainer.

- New Continue area with Continue, Pick Something, Goals and Recent Additions tabs in the main window.
- Continue lists active games, movies, saved show seasons and books; details return to the same hub tab and selection.
- Inline quick actions log episodes, page progress, full watches and completions. Final episodes/pages complete their season/book without adding timer hours. Undo restores progress and goal counts, with a guard against later edits.
- Random backlog picks support section, platform, genre and available-time filters. Show seasons and album editions are grouped for fair picks; unknown lengths are handled explicitly. Wishlist and completed/played items are excluded.
- Monthly game, episode and book goals use dated progress events from this update onward; metadata-only runtime/count changes do not become viewing events. Goal targets and errors stay in-page.
- Recent additions show date added, purchase date and price across enabled sections. New records are dated; historical records remain date unknown.
- All hub tabs respect collection visibility. No new popup windows are used by these features.

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

