import React, { useRef } from 'react';
import type { Workspace } from '@/features/workspaces/schemas';
import { WorkspaceHealthBadge } from './workspace-health-badge';

interface WorkspaceDetailsDrawerProps {
  workspace: Workspace | undefined;
  open: boolean;
  onClose: () => void;
  onReset: (id: string) => void;
  onConfirmReset: boolean;
  onCancelReset: () => void;
  onDoReset: () => void;
}

export function WorkspaceDetailsDrawer({
  workspace,
  open,
  onClose,
  onReset,
  onConfirmReset,
  onCancelReset,
  onDoReset,
}: WorkspaceDetailsDrawerProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  if (!open || !workspace) return null;

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    // File upload handling — wire to BFF /workspaces/{id}/files
    const files = Array.from(e.dataTransfer.files);
    // eslint-disable-next-line no-console
    console.log('[WorkspaceDetailsDrawer] drop', files);
  };

  return (
    <>
      <div
        className="drawer-backdrop"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className="drawer drawer--right"
        role="complementary"
        aria-label={`Details for workspace ${workspace.name}`}
      >
        <header className="drawer__header">
          <h2 className="drawer__title">{workspace.name}</h2>
          <button
            ref={closeRef}
            className="btn btn-ghost btn-icon"
            onClick={onClose}
            aria-label="Close workspace details"
          >
            ✕
          </button>
        </header>

        <div className="drawer__body">
          <section className="drawer__section">
            <h3 className="drawer__section-title">Health</h3>
            <WorkspaceHealthBadge health={workspace.health ?? 'healthy'} size="md" />
          </section>

          <section className="drawer__section">
            <h3 className="drawer__section-title">Configuration</h3>
            <dl className="detail-list">
              <dt>Type</dt>
              <dd>{workspace.type}</dd>
              <dt>Isolation Mode</dt>
              <dd>{workspace.isolationMode}</dd>
              {workspace.agentServerUrl && (
                <>
                  <dt>Agent Server URL</dt>
                  <dd className="detail-list__monospace">{workspace.agentServerUrl}</dd>
                </>
              )}
              <dt>Runs</dt>
              <dd>{workspace.runCount}</dd>
            </dl>
          </section>

          <section className="drawer__section">
            <h3 className="drawer__section-title">File Upload / Download</h3>
            <div
              className="file-drop-zone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              aria-label="Drag and drop files to upload, or click to browse"
              tabIndex={0}
              role="button"
            >
              <span>Drag files here or click to upload</span>
            </div>
          </section>

          <section className="drawer__section drawer__section--danger">
            <h3 className="drawer__section-title">Danger Zone</h3>
            {onConfirmReset ? (
              <div className="confirm-dialog">
                <p>Reset will stop all active runs and clear workspace state. Continue?</p>
                <div className="confirm-dialog__actions">
                  <button className="btn btn-destructive" onClick={onDoReset}>
                    Yes, reset
                  </button>
                  <button className="btn btn-secondary" onClick={onCancelReset}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                className="btn btn-destructive"
                onClick={() => onReset(workspace.id)}
              >
                Reset Workspace
              </button>
            )}
          </section>
        </div>
      </aside>
    </>
  );
}
