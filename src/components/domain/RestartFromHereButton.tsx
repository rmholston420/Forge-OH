/**
 * Stage 6.4c — Restart-from-here button (ADR-026).
 *
 * Renders inside the event-inspector aside next to ``ForkFromHereButton``.
 * Only visible for user-message events (spec parity with fork-from-here —
 * an assistant event has no captured commit sha to reset to).
 *
 * Difference from ForkFromHereButton:
 *   - Fork branches the CONVERSATION only.  Restart branches the whole
 *     run (fresh conversation + worktree provisioned at the anchor's
 *     captured sha + anchor's user text replayed as the first message).
 *   - Because restart resets the working tree, the confirm-dialog body
 *     surfaces "resets files on disk" explicitly.  This is the ADR-026
 *     §Storage promise.
 *
 * Design choices:
 *   - Purpose-built rather than sharing a base component with
 *     ForkFromHereButton.  The click paths are similar but the copy
 *     and the mutation are different enough that a shared base would
 *     become a leaky abstraction the first time either surface added
 *     a knob (e.g. a "reset files: yes/no" checkbox).
 *   - Uses useRestartRun (new in 6.4c) — the mutation invalidates the
 *     source run row and the new detail row for us.
 *   - Feature-flag gate matches ForkFromHereButton exactly so the whole
 *     revert/restart surface toggles as one under
 *     NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED.  Default-on unless the
 *     env var is explicitly set to the string 'false'.  Evaluated
 *     per-render so tests can flip it without reloading the module.
 */

'use client';

import React, { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useRestartRun } from '@/features/runs/hooks';
import { Modal } from '@/components/core/Modal';
import { Banner } from '@/components/core/Banner';

function isRunCompareEnabled(): boolean {
  return process.env.NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED !== 'false';
}

interface Props {
  /** The source run's id. */
  runId: string;
  /** The user MessageEvent to restart FROM (must carry a captured sha). */
  eventId: string;
  /**
   * A short label describing the event, used inside the confirm dialog so
   * the user is anchored to what they're about to restart from.  Optional.
   */
  eventLabel?: string;
}

export function RestartFromHereButton({ runId, eventId, eventLabel }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const { mutate, isPending, error, reset } = useRestartRun();

  // Feature-flag gate.  Evaluated AFTER all hooks (rules-of-hooks).  When
  // the flag is disabled the whole surface — button + modal — is hidden.
  if (!isRunCompareEnabled()) {
    return null;
  }

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
          if (data?.restarted_run_id) {
            router.push(`/runs/${data.restarted_run_id}`);
          }
        },
      },
    );
  }, [mutate, router, runId, eventId]);

  return (
    <>
      <button
        type="button"
        data-testid="restart-from-here-button"
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
        Restart from here
      </button>

      <Modal
        open={open}
        onClose={handleClose}
        title="Restart from this event"
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
            This creates a new run whose working tree is reset to the commit
            captured at the selected user message
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
            . The message text is replayed as the first prompt on the new
            run. The source run is left untouched.
          </p>

          <p
            style={{
              fontSize: 'var(--text-xs)',
              color: 'var(--color-text-muted)',
              margin: 0,
            }}
          >
            Unlike fork, this resets files on disk to the anchor commit.
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
              data-testid="restart-from-here-confirm"
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
              {isPending ? 'Restarting…' : 'Restart from here'}
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
}
