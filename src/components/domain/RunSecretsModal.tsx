'use client';
import React, { useState } from 'react';
import { Modal } from '@/components/core/Modal';
import { Button } from '@/components/core/Button';
import { Banner } from '@/components/core/Banner';
import { useUpdateRunSecrets } from '@/features/run-detail/secrets-hooks';

interface Props {
  runId: string;
  open: boolean;
  onClose: () => void;
}

interface SecretRow {
  key: string;
  value: string;
}

/**
 * Per-run env-vars editor. Writes secrets to the run's agent-server
 * conversation (POST /api/runs/{run_id}/secrets). The agent-server
 * exposes no GET - secrets are write-only from the FE's perspective,
 * so we start with a single blank row.
 */
export function RunSecretsModal({ runId, open, onClose }: Props) {
  const [rows, setRows] = useState<SecretRow[]>([{ key: '', value: '' }]);
  const mut = useUpdateRunSecrets();

  const setKey = (i: number, key: string) =>
    setRows((r) => r.map((row, idx) => (idx === i ? { ...row, key } : row)));
  const setValue = (i: number, value: string) =>
    setRows((r) => r.map((row, idx) => (idx === i ? { ...row, value } : row)));
  const addRow = () => setRows((r) => [...r, { key: '', value: '' }]);
  const removeRow = (i: number) => setRows((r) => r.filter((_, idx) => idx !== i));

  const handleSave = () => {
    const secrets: Record<string, string> = {};
    for (const { key, value } of rows) {
      const k = key.trim();
      if (k) secrets[k] = value;
    }
    if (Object.keys(secrets).length === 0) return;
    mut.mutate(
      { runId, secrets },
      {
        onSuccess: () => {
          setRows([{ key: '', value: '' }]);
          onClose();
        },
      },
    );
  };

  return (
    <Modal open={open} onClose={onClose} title="Run environment variables" size="md">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Banner variant="info">
          Env vars are injected into this run only. They are write-only —
          the agent-server does not return existing values.
        </Banner>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {rows.map((row, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                aria-label={`Secret ${i + 1} key`}
                placeholder="KEY"
                value={row.key}
                onChange={(e) => setKey(i, e.target.value)}
                style={{ flex: '0 0 34%', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border-subtle,#334155)', background: 'var(--surface-2,#0b1220)', color: 'inherit', fontFamily: 'monospace' }}
              />
              <input
                aria-label={`Secret ${i + 1} value`}
                placeholder="value"
                value={row.value}
                onChange={(e) => setValue(i, e.target.value)}
                type="password"
                style={{ flex: 1, padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border-subtle,#334155)', background: 'var(--surface-2,#0b1220)', color: 'inherit', fontFamily: 'monospace' }}
              />
              <button
                type="button"
                aria-label={`Remove secret ${i + 1}`}
                onClick={() => removeRow(i)}
                disabled={rows.length === 1}
                style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border-subtle,#334155)', background: 'transparent', color: 'inherit', cursor: rows.length === 1 ? 'not-allowed' : 'pointer' }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        <Button variant="tertiary" onClick={addRow}>+ Add secret</Button>

        {mut.isError && (
          <Banner variant="error">
            {mut.error instanceof Error ? mut.error.message : 'Failed to save secrets.'}
          </Banner>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button variant="tertiary" onClick={onClose} disabled={mut.isPending}>Cancel</Button>
          <Button variant="primary" onClick={handleSave} disabled={mut.isPending}>
            {mut.isPending ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default RunSecretsModal;
