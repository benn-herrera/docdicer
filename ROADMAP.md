# ROADMAP – docdicer

Future intent only. Not part of the contract documents.

## Features

## Maintenance

### Eliminate .webp binary blobs from history

Eliminate the one revision of the binary blobs from history on main.
```bash
git lfs migrate import --everything --include=*.webp
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force origin main
git push --force --tags
```

## Testing

### A browser test of the kanban page

The tests stop at the server's payload: nothing checks what `docdicer/kanban/assets/board.js`
does with it — the title, the header, the columns, the drags, the collapse. Taken up only when
a need earns the weight of a browser test tool, not before.
