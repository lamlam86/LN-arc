# Reports

Markdown recon reports and the publisher that exposes them in the web UI.

## Files

- `*.md` — reports. Use language suffixes to publish two versions of the same
  report: `recon-task-1.vi.md` and `recon-task-1.en.md` (grouped into one entry).
  A file without a suffix is treated as English.
- `sync_web.py` also picks up
  `dist/artex-windows-amd64/data/tasks/<id>/recon-report.md` and
  `data/tasks/<id>/recon-report.md` when `reports/` has no entry for that task.
- `sync_web.py` — regenerates `web/src/lib/reports-data.ts`.

## Publish to the UI

```bash
python reports/sync_web.py
```

Or keep it in sync automatically while tasks run:

```bash
python reports/watch.py
```

`watch.py` polls the report sources every 5 seconds and republishes whenever a
task writes a new `recon-report.md`. `npm run dev` also syncs once on startup
(`predev`), and `npm run sync:reports` runs a one-off sync.

Then open **Tasks → Reports** in the web UI. The report content is bundled into
the frontend module, so it stays behind the app's authentication proxy and works
in the static export as well. Reports with both suffixes show a **VI / EN**
toggle and a download button per language.

After changing reports:

- dev (`next dev`): hot-reloads automatically.
- static build: run `npm run build:static` (and rebuild the backend if the UI is
  embedded) to pick up the new module.

## Notes

- The report content is embedded in the JS bundle. Keep individual reports
  reasonably small; archive old ones if the bundle grows too large.
- Do not put secrets or personal data in reports. Redact values before saving.
