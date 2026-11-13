# ROADMAP – docdicer

Future intent only. Not part of the contract documents.

## Features

### Double-clicking a category separator collapses the category

If we are not going to let `kanban` grow into a markdown renderer we need to accommodate some
of the issues like big design doc cards. Making the categories double-click to collapse makes
navigating the SPEC delta, ARCHITECTURE delta, CODE delta sections easier

## Maintenance

### Break up README.md

Keep it short and sweet. Break out the rest into `docs/`.

### Eliminate .webp binary blobs from history

Move the images to `docs/` and eliminate the one revision of the binary blobs from history on main.
```bash
git lfs migrate import --everything --include=*.webp`
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force origin main
git push --force --tags
```
## Testing

### A browser test of the kanban page

The tests stop at the server's payload: nothing checks what `docdicer/kanban/assets/board.js`
does with it — the title, the header, the columns, the drags. Taken up only when a need earns
the weight of a browser test tool, not before.
