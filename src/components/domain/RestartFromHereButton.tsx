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
  /**
   * The BFF-stamped commit sha for the anchor event, or null/undefined if
   * the event was authored before the sha-capture path shipped (Stage 6.4c
   * pre-ratify runs, or capture-failure downgrades).  Per ADR-026 §Frontend
   * contract, the button must not render when this is absent — clicking
   * would surface a 409 no_sha_anchor with no user recovery path.
   */
  commitShaAtTimeOfEvent?: string | null;
}

export function RestartFromHereButton({
  runId,
  eventId,
  eventLabel,
  commitShaAtTimeOfEvent,
}: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const { mutate, isPending, error, reset } = useRestartRun();

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

  // Feature-flag AND sha-gate.  Placed AFTER all hooks so hook-count stays
  // stable regardless of gate outcome (rules-of-hooks).  When the flag is
  // disabled OR the anchor has no captured sha, the whole surface — button
  // + modal — is hidden.  Per ADR-026 §Frontend contract, absent sha is
  // treated as "button hidden" rather than "button disabled" because there
  // is no user action that recovers from a missing capture.
  if (!isRunCompareEnabled()) {
    return null;
  }
  if (!commitShaAtTimeOfEvent) {
    return null;
  }

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

          {/* ADR-026 §Frontend contract — dialog copy is normative.  Do NOT
              paraphrase.  The three user-outcomes (files reset, prompt
              replayed, source preserved) must all be surfaced verbatim. */}
          <p
            style={{
              fontSize: 'var(--text-sm)',
              color: 'var(--color-text-muted)',
              margin: 0,
            }}
          >
            Start a new run at this point with files reset to that state.
            You'll re-send your original message; the assistant's prior
            replies won't carry over. Your current run is preserved.
          </p>

          {eventLabel ? (
            <p
              style={{
                fontSize: 'var(--text-xs)',
                color: 'var(--color-text-muted)',
                margin: 0,
              }}
            >
              Anchor:{' '}
              <code
                style={{
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--color-text)',
                }}
              >
                {eventLabel}
              </code>
            </p>
          ) : null}

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
