/**
 * Stage 6.4 — Fork-from-here button.
 *
 * Renders inside the event-inspector aside on the run-detail page.  Only
 * visible for user-message events (spec D2).  On click, opens a lightweight
 * confirmation dialog; on confirm, calls the widened forkRun with
 * ``fromEventId`` and navigates to the new run.
 *
 * Design choices:
 *   - Purpose-built rather than reusing ForkRunModal.  ForkRunModal owns
 *     the whole-run + compare-after semantics, which don't apply cleanly
 *     to sub-event forks (there is no obvious diff target).  Keeping them
 *     separate keeps regressions isolated.
 *   - Uses useForkRun (widened in Stage 6.4) — the mutation invalidates
 *     the runs list and the new detail row for us.
 */

'use client';

import React, { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useForkRun } from '@/features/runs/hooks';
import { Modal } from '@/components/core/Modal';
import { Banner } from '@/components/core/Banner';

interface Props {
  /** The source run's id. */
  runId: string;
  /** The event to fork FROM (inclusive of that event on the new branch). */
  eventId: string;
  /**
   * A short label describing the event, used inside the confirm dialog so
   * the user is anchored to what they're about to fork from.  Optional.
   */
  eventLabel?: string;
}

export function ForkFromHereButton({ runId, eventId, eventLabel }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const { mutate, isPending, error, reset } = useForkRun();

  const handleClose = useCallback(() => {
    reset();
    setOpen(false);
  }, [reset]);

  const handleConfirm = useCallback(() => {
    mutate(
      { runId, fromEventId: eventId },
      {
        onSuccess: (data) => {
          setOpen(false);
          if (data?.forked_id) {
            router.push(`/runs/${data.forked_id}`);
          }
        },
      },
    );
  }, [mutate, router, runId, eventId]);

  return (
    <>
      <button
        type="button"
        data-testid="fork-from-here-button"
        onClick={() => setOpen(true)}
        style={{
          padding: 'var(--space-2) var(--space-3)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--color-border)',
          background: 'var(--color-surface)',
          color: 'var(--color-text)',
          fontSize: 'var(--text-sm)',
          cursor: 'pointer',
        }}
      >
        Fork from here
      </button>

      <Modal
        open={open}
        onClose={handleClose}
        title="Fork from this event"
      >
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-5)',
          }}
        >
          {error && <Banner variant="error">{error.message}</Banner>}

          <p
            style={{
              fontSize: 'var(--text-sm)',
              color: 'var(--color-text-muted)',
              margin: 0,
            }}
          >
            This creates a new run whose event history ends at the selected
            user message
            {eventLabel ? (
              <>
                {' '}(
                <code
                  style={{
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--color-text)',
                  }}
                >
                  {eventLabel}
                </code>
                )
              </>
            ) : null}
            . The source run is left untouched.
          </p>

          <p
            style={{
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-muted)',
              margin: 0,
            }}
          >
            Files on disk are not reverted in this stage.
          </p>

          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 'var(--space-3)',
              paddingTop: 'var(--space-2)',
            }}
          >
            <button
              type="button"
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
              type="button"
              data-testid="fork-from-here-confirm"
              onClick={handleConfirm}
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
              {isPending ? 'Forking…' : 'Fork from here'}
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
}
