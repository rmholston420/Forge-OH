'use client';
/**
 * Stage 1.6 (reconciliation-plan-v1) — Send Message While Running.
 *
 * Persistent composer on the run detail page. Sends a user message into a
 * live (or paused) conversation via POST /api/runs/{run_id}/message → BFF →
 * agent-server /api/conversations/{cid}/events.
 *
 * The composer is intentionally lightweight: single-line textarea, submit
 * on Ctrl/Cmd+Enter or button click. It disables itself for terminal-state
 * runs (completed / failed / stopped / rejected) and while the mutation is
 * in flight. Errors surface inline; success clears the field.
 */
import React, { useCallback, useState } from 'react';
import { useSendRunMessage } from '@/features/runs/hooks';

type Status = string | null | undefined;

// Runs in a terminal state can no longer accept new user messages: agent-
// server /events would either 400 or silently accept but never process.
const TERMINAL_STATUSES = new Set(['completed', 'failed', 'stopped', 'rejected', 'cancelled']);

function isTerminal(status: Status): boolean {
  return !!status && TERMINAL_STATUSES.has(status.toLowerCase());
}

export interface RunMessageComposerProps {
  runId: string;
  status?: Status;
}

export function RunMessageComposer({ runId, status }: RunMessageComposerProps) {
  const [value, setValue] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const mutation = useSendRunMessage();

  const terminal = isTerminal(status);
  const disabled = terminal || mutation.isPending;

  const submit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    setErrorMsg(null);
    mutation.mutate(
      { runId, message: trimmed },
      {
        onSuccess: () => setValue(''),
        onError: (err: unknown) => {
          setErrorMsg(err instanceof Error ? err.message : 'Failed to send message');
        },
      },
    );
  }, [value, disabled, mutation, runId]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        submit();
      }
    },
    [submit],
  );

  return (
    <div
      role="form"
      aria-label="Send message to running run"
      style={{
        display: 'flex',
        gap: 8,
        alignItems: 'flex-start',
        padding: '12px 16px',
        borderTop: '1px solid var(--color-border, #2a2a2a)',
        background: 'var(--color-surface, #111)',
        position: 'sticky',
        bottom: 0,
        zIndex: 5,
      }}
    >
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled}
        rows={2}
        maxLength={32_000}
        placeholder={
          terminal
            ? 'Run is in a terminal state — messages cannot be sent.'
            : 'Type a message to the running agent… (Ctrl/Cmd+Enter to send)'
        }
        aria-label="Message to running agent"
        style={{
          flex: 1,
          resize: 'vertical',
          minHeight: 40,
          fontFamily: 'inherit',
          fontSize: 14,
          padding: '8px 10px',
          borderRadius: 6,
          border: '1px solid var(--color-border, #333)',
          background: 'var(--color-bg, #0b0b0b)',
          color: 'var(--color-fg, #eaeaea)',
        }}
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || value.trim().length === 0}
        aria-label="Send message"
        style={{
          minWidth: 96,
          padding: '8px 12px',
          borderRadius: 6,
          border: '1px solid var(--color-accent, #4b8)',
          background: disabled ? 'var(--color-muted, #333)' : 'var(--color-accent, #4b8)',
          color: '#fff',
          cursor: disabled ? 'not-allowed' : 'pointer',
        }}
      >
        {mutation.isPending ? 'Sending…' : 'Send'}
      </button>
      {errorMsg && (
        <div role="alert" style={{ color: '#f88', fontSize: 12, alignSelf: 'center' }}>
          {errorMsg}
        </div>
      )}
    </div>
  );
}

export default RunMessageComposer;
