'use client';
import React, { useState } from 'react';
import type { ToolEvent } from '@/lib/schemas/event';
import { formatDate } from '@/lib/utils/format';
import { RiskBadge } from '@/features/security/RiskBadge';
import styles from './EventCard.module.css';

const EVENT_ICONS: Record<string, string> = {
  think: '💧',
  plan: '📋',
  edit_file: '✏️',
  run_command: '▶',
  browser_action: '🌐',
  read_file: '📄',
  web_search: '🔍',
  message: '💬',
  error: '⚠️',
  finish: '✅',
  // Stage 4.4 — Serena LSP tool actions. Discriminator is `event.type`
  // (see ADR-018); no discriminated-union type change is needed.
  lsp_find_symbol: '🔎',
  lsp_find_referencing_symbols: '🔗',
  lsp_get_symbols_overview: '🗂️',
  lsp_replace_symbol_body: '✏️',
  lsp_insert_after_symbol: '➕',
  lsp_insert_before_symbol: '➕',
};

/** Stage 4.4 — render an "LSP" family badge for symbol-precise ops. */
const isLspEventType = (t: string | undefined): boolean =>
  typeof t === 'string' && t.startsWith('lsp_');

export interface EventCardProps {
  event: ToolEvent;
  selected?: boolean;
  highlight?: boolean;
  onSelect?: (id: string) => void;
}

export const EventCard: React.FC<EventCardProps> = ({ event, selected, highlight, onSelect }) => {
  const [expanded, setExpanded] = useState(false);
  const icon = EVENT_ICONS[event.type] ?? '○';

  return (
    <div
      className={[
        styles.card,
        selected ? styles['card--selected'] : '',
        highlight ? styles['card--highlight'] : '',
        event.type === 'error' ? styles['card--error'] : '',
      ].filter(Boolean).join(' ')}
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      onClick={() => onSelect?.(String(event.id))}
      onKeyDown={(e) => e.key === 'Enter' && onSelect?.(String(event.id))}
    >
      <div className={styles.header}>
        <span className={styles.icon} aria-hidden="true">{icon}</span>
        {isLspEventType(event.type) && (
          <span
            data-testid="event-lsp-badge"
            aria-label="language server protocol"
            title="Serena LSP"
            style={{
              fontSize: '0.7em',
              padding: '1px 6px',
              borderRadius: 4,
              border: '1px solid currentColor',
              opacity: 0.75,
              marginRight: 6,
              fontWeight: 600,
              letterSpacing: '0.04em',
            }}
          >
            LSP
          </span>
        )}
        <span className={styles.summary}>{String(event.summary ?? '')}</span>
        <RiskBadge risk={event.securityRisk} className={styles.riskBadge} />
        <span className={styles.meta}>{formatDate(event.timestamp)}</span>
        {Boolean(event.raw) && (
          <button
            className={styles.expandBtn}
            onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
            aria-expanded={expanded}
            aria-label={expanded ? 'Collapse raw output' : 'Expand raw output'}
          >
            {expanded ? '∧' : '∨'}
          </button>
        )}
      </div>
      {expanded && Boolean(event.raw) && (
        <pre className={styles.raw}>
          <code>{typeof event.raw === 'string' ? event.raw : JSON.stringify(event.raw ?? {}, null, 2)}</code>
        </pre>
      )}
    </div>
  );
};
