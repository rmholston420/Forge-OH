'use client';
import React, { useState } from 'react';
import type { ToolEvent } from '@/lib/schemas/event';
import { formatDate } from '@/lib/utils/format';
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
};

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
      onClick={() => onSelect?.(event.id)}
      onKeyDown={(e) => e.key === 'Enter' && onSelect?.(event.id)}
    >
      <div className={styles.header}>
        <span className={styles.icon} aria-hidden="true">{icon}</span>
        <span className={styles.summary}>{event.summary}</span>
        <span className={styles.meta}>{formatDate(event.timestamp)}</span>
        {event.raw && (
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
      {expanded && event.raw && (
        <pre className={styles.raw}>
          <code>{JSON.stringify(event.raw, null, 2)}</code>
        </pre>
      )}
    </div>
  );
};
