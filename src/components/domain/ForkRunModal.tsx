'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Modal } from '@/components/core/Modal';
import { Banner } from '@/components/core/Banner';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED !== 'false';

interface Props {
  runId: string;
  runTitle: string;
  open: boolean;
  onClose: () => void;
}

interface ForkResponse {
  ok: boolean;
  run_id: string;
  forked_id: string;
}

export function ForkRunModal({ runId, runTitle, open, onClose }: Props) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [compareAfter, setCompareAfter] = useState(true);

  const { mutate: forkRun, isPending, error, reset } = useMutation<ForkResponse, Error>({
    mutationFn: async () => {
      const res = await fetch(`/api/runs/${runId}/fork`, { method: 'POST' });
      if (!res.ok) throw new Error(`Fork failed: ${res.status}`);
      return res.json();
    },
    onSuccess: (data) => {
      // Invalidate runs list so the new fork appears
      queryClient.invalidateQueries({ queryKey: ['runs'] });
      onClose();
      if (compareAfter) {
        router.push(`/runs/compare?base=${data.run_id}&fork=${data.forked_id}`);
      } else {
        router.push(`/runs/${data.forked_id}`);
      }
    },
  });

  function handleClose() {
    reset();
    onClose();
  }

  if (!FEATURE_ENABLED) return null;

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Fork run"
      description={`Fork "${runTitle}" into a new independent run you can edit and re-run.`}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)' }}>

        {error && (
          <Banner variant="error">{error.message}</Banner>
        )}

        <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)', margin: 0 }}>
          A fork copies the run's workspace snapshot, agent preset, and context prompt.
          It starts in <strong>queued</strong> state — you can edit the prompt before starting.
        </p>

        <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={compareAfter}
            onChange={(e) => setCompareAfter(e.target.checked)}
            style={{ width: 16, height: 16, accentColor: 'var(--color-primary)' }}
          />
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text)' }}>
            Open diff comparison after fork
          </span>
        </label>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-3)', paddingTop: 'var(--space-2)' }}>
          <button
            onClick={handleClose}
            disabled={isPending}
            style={{
              padding: 'var(--space-2) var(--space-4)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              fontSize: 'var(--text-sm)',
              cursor: isPending ? 'not-allowed' : 'pointer',
              opacity: isPending ? 0.5 : 1,
            }}
          >
            Cancel
          </button>
          <button
            onClick={() => forkRun()}
            disabled={isPending}
            aria-busy={isPending}
            style={{
              padding: 'var(--space-2) var(--space-4)',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: 'var(--color-primary)',
              color: '#fff',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              cursor: isPending ? 'not-allowed' : 'pointer',
              opacity: isPending ? 0.7 : 1,
            }}
          >
            {isPending ? 'Forking…' : 'Fork run'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
