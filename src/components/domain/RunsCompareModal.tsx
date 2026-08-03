'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Modal } from '@/components/core/Modal';
import { Button } from '@/components/core/Button';
import { Banner } from '@/components/core/Banner';
import type { RunSummary } from '@/lib/schemas/run';

interface Props {
  runs: RunSummary[];
  open: boolean;
  onClose: () => void;
}

/**
 * Two-run picker that navigates to /runs/compare?base=…&fork=…
 * The BFF /api/runs/compare endpoint accepts any two run IDs; the labels
 * "base"/"fork" are conventions, not enforced.
 */
export function RunsCompareModal({ runs, open, onClose }: Props) {
  const router = useRouter();
  const [baseId, setBaseId] = useState<string>('');
  const [forkId, setForkId] = useState<string>('');

  const canCompare = baseId && forkId && baseId !== forkId;

  const handleCompare = () => {
    if (!canCompare) return;
    router.push(`/runs/compare?base=${baseId}&fork=${forkId}`);
    onClose();
  };

  return (
    <Modal open={open} onClose={onClose} title="Compare runs" size="md">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Banner variant="info">
          Side-by-side diff of two runs&apos; workspace changes. Pick any two runs; results
          include per-file diffs and summary stats.
        </Banner>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Base run</span>
          <select
            value={baseId}
            onChange={(e) => setBaseId(e.target.value)}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              border: '1px solid var(--border-subtle,#334155)',
              background: 'var(--surface-2,#0b1220)',
              color: 'inherit',
            }}
          >
            <option value="">Select a run…</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title ?? r.id.slice(0, 8)} ({r.id.slice(0, 8)})
              </option>
            ))}
          </select>
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Fork run</span>
          <select
            value={forkId}
            onChange={(e) => setForkId(e.target.value)}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              border: '1px solid var(--border-subtle,#334155)',
              background: 'var(--surface-2,#0b1220)',
              color: 'inherit',
            }}
          >
            <option value="">Select a run…</option>
            {runs.filter((r) => r.id !== baseId).map((r) => (
              <option key={r.id} value={r.id}>
                {r.title ?? r.id.slice(0, 8)} ({r.id.slice(0, 8)})
              </option>
            ))}
          </select>
        </label>

        {baseId && forkId && baseId === forkId && (
          <Banner variant="error">Base and fork must be different runs.</Banner>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button variant="tertiary" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={handleCompare} disabled={!canCompare}>
            Compare
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default RunsCompareModal;
