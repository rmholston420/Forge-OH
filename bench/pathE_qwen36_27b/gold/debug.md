1. **Root cause:** `bff/routers/runs.py` and `bff/routers/workspaces.py` still contain the module-level import `from bff.middleware.rbac import require_role` plus `_: None = Depends(require_role(...))` route parameters that use it (7 handlers in runs.py: create/pause/resume/stop/approve/reject/fork; 4 in workspaces.py: create/update/delete/reset), so when `bff/main.py` imports both routers at startup the import fails against the deleted `bff/middleware/rbac.py`.

2. **Fix:**

```bash
sed -i '/^from bff\.middleware\.rbac import require_role$/d; /Depends(require_role(/d' bff/routers/runs.py bff/routers/workspaces.py
sed -i 's/^from fastapi import APIRouter, Depends, Query$/from fastapi import APIRouter, Query/' bff/routers/runs.py
sed -i 's/^from fastapi import APIRouter, Depends, HTTPException$/from fastapi import APIRouter, HTTPException/' bff/routers/workspaces.py
```

Line 1 deletes the dead import and every `_: None = Depends(require_role("write"))`/`require_role('delete')` parameter line (each is a standalone line ending in a comma, so the remaining signatures stay syntactically valid). Lines 2–3 drop the now-unused `Depends` from each file's fastapi import.

3. **Verify:**

```bash
python -c "from bff.main import app_with_sio; print('BOOT OK')"
```
