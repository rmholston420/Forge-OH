'use client';
import { useState } from 'react';
import { useDeleteWorkspace } from './hooks';
import { useWorkspacesStore } from './store';

export function DeleteConfirmDialog() {
  const { confirmDeleteId, confirmDeleteName, closeConfirmDelete } = useWorkspacesStore();
  const deleteWs = useDeleteWorkspace();
  const [typed, setTyped] = useState('');

  if (!confirmDeleteId) return null;

  async function handleConfirm() {
    if (typed !== confirmDeleteName) return;
    await deleteWs.mutateAsync(confirmDeleteId!);
    closeConfirmDelete();
    setTyped('');
  }

  return (
    <div className="dialog-overlay" role="dialog" aria-modal="true"
         aria-label="Delete workspace">
      <div className="dialog">
        <h2>Delete workspace</h2>
        <p aria-live="polite">
          This will permanently delete <strong>{confirmDeleteName}</strong> and all
          associated data. This action cannot be undone.
        </p>
        <div className="form-field">
          <label htmlFor="confirm-name">
            Type <strong>{confirmDeleteName}</strong> to confirm
          </label>
          <input
            id="confirm-name"
            value={typed}
            onChange={e => setTyped(e.target.value)}
            autoComplete="off"
            aria-describedby="delete-warning"
          />
        </div>
        <p id="delete-warning" className="field-error" aria-live="assertive">
          {typed.length > 0 && typed !== confirmDeleteName
            ? 'Name does not match'
            : ''}
        </p>
        <div className="dialog-footer">
          <button className="btn btn-ghost" onClick={() => { closeConfirmDelete(); setTyped(''); }}>
            Cancel
          </button>
          <button
            className="btn btn-danger"
            onClick={handleConfirm}
            disabled={typed !== confirmDeleteName || deleteWs.isPending}
          >
            {deleteWs.isPending ? 'Deleting…' : 'Delete workspace'}
          </button>
        </div>
      </div>
    </div>
  );
}
