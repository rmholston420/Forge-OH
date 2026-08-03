'use client';
import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useLiveBash } from '@/features/terminal/hooks';
import styles from './LiveBashPanel.module.css';

export interface LiveBashPanelProps {
  runId: string;
  /** Optional cwd hint sent with the start request. */
  cwd?: string | null;
}

/**
 * Slice C.1 — live bash panel. Type a command, hit Enter, watch stdout/stderr
 * stream in from the BFF's SSE relay. One command at a time.
 */
export const LiveBashPanel: React.FC<LiveBashPanelProps> = ({ runId, cwd }) => {
  const { status, events, exitCode, error, run, reset } = useLiveBash(runId);
  const [input, setInput] = useState('');
  const outputRef = useRef<HTMLPreElement>(null);

  const busy = status === 'starting' || status === 'running';

  // Assemble a plain-text transcript from the ordered events.
  const transcript = useMemo(() => {
    const parts: string[] = [];
    for (const evt of events) {
      if (evt.kind === 'BashCommand' && evt.command) {
        parts.push(`$ ${evt.command}`);
      } else if (evt.kind === 'BashOutput') {
        if (evt.stdout) parts.push(evt.stdout.replace(/\n$/, ''));
        if (evt.stderr) parts.push(evt.stderr.replace(/\n$/, ''));
      }
    }
    return parts.filter(Boolean).join('\n');
  }, [events]);

  // Auto-scroll on new output.
  useEffect(() => {
    const el = outputRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [transcript, status]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cmd = input.trim();
    if (!cmd || busy) return;
    setInput('');
    void run(cmd, cwd ?? null);
  };

  return (
    <div className={styles.panel} data-testid="live-bash-panel">
      <div className={styles.header}>
        <span className={styles.title}>Live shell</span>
        <span className={styles.status} data-status={status}>
          {status === 'idle' && 'ready'}
          {status === 'starting' && 'starting…'}
          {status === 'running' && 'running…'}
          {status === 'done' && `done (exit ${exitCode ?? '?'})`}
          {status === 'error' && 'error'}
        </span>
        {(status === 'done' || status === 'error') && (
          <button
            type="button"
            className={styles.clearBtn}
            onClick={reset}
            aria-label="Clear live shell output"
          >
            clear
          </button>
        )}
      </div>

      <pre
        ref={outputRef}
        className={styles.output}
        data-testid="live-bash-output"
        aria-live="polite"
      >
        {transcript || (
          <span className={styles.empty}>
            Type a command below to run it in the agent&apos;s runtime.
          </span>
        )}
      </pre>

      {error && (
        <div className={styles.error} role="alert">
          {error}
        </div>
      )}

      <form className={styles.form} onSubmit={onSubmit}>
        <span className={styles.prompt} aria-hidden="true">
          $
        </span>
        <input
          className={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={busy ? 'command running…' : 'e.g. ls -la'}
          disabled={busy}
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          data-testid="live-bash-input"
          aria-label="Bash command"
        />
        <button
          type="submit"
          className={styles.runBtn}
          disabled={busy || !input.trim()}
          data-testid="live-bash-run"
        >
          run
        </button>
      </form>
    </div>
  );
};

export default LiveBashPanel;
