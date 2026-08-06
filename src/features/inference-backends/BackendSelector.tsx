/**
 * src/features/inference-backends/BackendSelector.tsx
 *
 * Radio-group selector for inference backends. Renders the live health
 * inventory returned by GET /api/inference-backends in registry order
 * (ollama, vllm-coder, vllm-planner, vllm-legacy, llamacpp, sglang).
 *
 * Backends whose `roleHint` conflicts with the caller's `role` (e.g. the
 * caller is a "coder" preset and the backend is vllm-planner) render as
 * disabled with an incompatibility hint.
 *
 * See docs/reconciliation-plan-stage-2.md § 2.2.4.
 */
'use client';
import React from 'react';
import { useInferenceBackends } from './hooks';
import { HealthBadge } from './HealthBadge';
import type { BackendId, InferenceBackend, RoleHint } from './schemas';
import styles from './BackendSelector.module.css';

export interface BackendSelectorProps {
  /** Currently selected backend id, or null for "no explicit pin". */
  value: BackendId | null;
  onChange: (id: BackendId | null) => void;
  /** Preset role hint. When set, incompatible role-specific backends
   *  render as disabled. `null` accepts any backend. */
  role?: RoleHint | null;
  /** Field label rendered inside the fieldset legend. */
  label?: string;
  /** Optional htmlFor-style id prefix so multiple selectors coexist. */
  idPrefix?: string;
  /** When true, disables the whole group (e.g. during form submit). */
  disabled?: boolean;
}

const NONE_VALUE = '__none__';

function isIncompatible(backend: InferenceBackend, role?: RoleHint | null): boolean {
  if (!role) return false;
  const hint = backend.roleHint;
  // hint 'any' or 'probe' never blocks. Role-specific hints must match.
  if (hint === 'coder' && role !== 'coder') return true;
  if (hint === 'planner' && role !== 'planner') return true;
  return false;
}

export function BackendSelector({
  value,
  onChange,
  role = null,
  label = 'Inference backend',
  idPrefix = 'backend',
  disabled = false,
}: BackendSelectorProps) {
  const { data: backends, isLoading, isError } = useInferenceBackends();
  const groupName = React.useId();

  if (isLoading) {
    return (
      <div className={styles.selector} aria-label="Inference backend loading">
        <div className={styles.legend}>{label}</div>
        <div className={styles.loading}>Loading backends…</div>
      </div>
    );
  }
  if (isError || !backends) {
    return (
      <div className={styles.selector} aria-label="Inference backend error">
        <div className={styles.legend}>{label}</div>
        <div className={styles.error}>Could not load backends — using preset default.</div>
      </div>
    );
  }

  const selected = value ?? NONE_VALUE;

  const handleChange = (id: string) => {
    if (id === NONE_VALUE) onChange(null);
    else onChange(id as BackendId);
  };

  return (
    <fieldset
      className={styles.selector}
      aria-label="Inference backend"
      disabled={disabled}
    >
      <legend className={styles.legend}>{label}</legend>

      {/* "None" option — falls back to preset backendId, then default route. */}
      <label className={styles.option}>
        <input
          type="radio"
          name={groupName}
          value={NONE_VALUE}
          checked={selected === NONE_VALUE}
          onChange={() => handleChange(NONE_VALUE)}
          className={styles.radio}
        />
        <span className={styles.optionBody}>
          <span className={styles.optionName}>Use preset default</span>
          <span className={styles.optionMeta}>
            Falls back to the preset's <code>backendId</code>, then role-based routing.
          </span>
        </span>
      </label>

      {backends.map((b) => {
        const incompatible = isIncompatible(b, role);
        const isDisabled = incompatible;
        const id = `${idPrefix}-${b.id}`;
        return (
          <label
            key={b.id}
            htmlFor={id}
            className={`${styles.option} ${isDisabled ? styles.optionDisabled : ''}`}
            title={incompatible ? `Incompatible with role=${role}` : b.baseUrl}
          >
            <input
              id={id}
              type="radio"
              name={groupName}
              value={b.id}
              checked={selected === b.id}
              onChange={() => handleChange(b.id)}
              disabled={isDisabled}
              className={styles.radio}
              aria-label={`Backend ${b.displayName} — ${b.health.state}`}
            />
            <span className={styles.optionBody}>
              <span className={styles.optionHeader}>
                <span className={styles.optionName}>{b.displayName}</span>
                <HealthBadge state={b.health.state} latencyMs={b.health.latencyMs} />
              </span>
              <span className={styles.optionMeta}>
                <code>{b.id}</code>
                {b.roleHint !== 'any' && b.roleHint !== 'probe' && (
                  <> · role: {b.roleHint}</>
                )}
                {b.health.error && (
                  <span className={styles.optionError} title={b.health.error}>
                    {' · '}{b.health.error}
                  </span>
                )}
              </span>
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}
