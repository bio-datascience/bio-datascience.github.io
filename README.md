# BioDS Munich website

Static website for the Biomedical Statistics and Data Science group. No build or dependencies are required.

Preview: `python3 -m http.server 8000`. Validate: `node --check app.js` and `python3 scripts/check_site.py` (or `npm run check`).

GitHub Pages serves the repository root from `master`. Existing proposal PDFs, images, legacy pages and license are retained.

## Previous site

The complete previous site and its Git history are preserved on branch `backup/before-biods-refresh-2026-11-16`, at commit `89a59568c6419071f4ea4be035ee5e3fb092997b`. Restore through a new commit based on that snapshot if needed; do not force-push shared history.

## Content provenance

The publication list reconciles all 134 entries in the user-supplied November 2026 Google Scholar export: 7 duplicate citations consolidated, 5 misattributed records omitted (including the explicitly excluded Temmel 2017 paper), and 2 existing verified records retained, yielding 124 displayed entries. One undated work is labeled accordingly. The reconciliation audit and bibliographic/figure provenance are retained under `docs/references/`. Upcoming Zurich and Paris appearances have no exact dates specified in the source handoff.

## Refresh publications on request

Run `python3 scripts/update_publications.py --check` to preview a Google Scholar refresh, then `python3 scripts/update_publications.py` to update local website data. Equivalent npm commands are `npm run publications:check` and `npm run publications:update`. No schedule runs automatically.

The updater needs only Python's standard library. It paginates the profile, preserves full author lists and verified paper links, retains existing records, and consolidates known duplicate citations. Exclusions and title aliases live in `docs/references/publication-settings.json`. Unexpectedly short, blocked or malformed responses stop the refresh before any files change. Scholar can restrict automated access; if blocked, keep the existing list and provide a new Scholar export for reconciliation.

After updating, run the site checks, review the changes, then commit and publish when requested. The updater never commits or publishes.
