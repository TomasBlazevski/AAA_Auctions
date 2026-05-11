# Contributing Guide

This repository uses a simple branch strategy to keep production stable.

## Branches

- `main`: production-ready code only.
- `dev`: integration branch for completed feature work.
- `feature/*`: short-lived branches for individual tasks.

## Standard workflow

1. Start from `dev`:
   - `git checkout dev`
   - `git pull`
2. Create a feature branch:
   - `git checkout -b feature/<short-name>`
3. Implement changes and commit with clear messages.
4. Push your branch:
   - `git push -u origin feature/<short-name>`
5. Open a Pull Request:
   - `feature/*` -> `dev`
6. After validation, merge `dev` into `main` via Pull Request when ready for release.

## Pull Request checklist

- Changes are focused and small.
- Scraper configs updated in `scrapers/config/*.json` when filters change.
- No secrets committed (`.env` is ignored).
- Basic local verification completed before PR.

## Commit message style

Use short, action-oriented messages:

- `add rb config loader`
- `update tm filters for 2027`
- `refactor scraper wrappers`

## Notes

- Avoid direct pushes to `main`.
- Prefer Pull Requests for all changes to keep history reviewable.
