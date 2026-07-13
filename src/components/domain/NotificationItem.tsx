'use client';
import Link from 'next/link';
import { useMarkRead, useDismissNotification } from '@/features/notifications/hooks';
import type { Notification } from '@/lib/schemas/notification';

const TYPE_ICONS: Record<string, string> = {
  info:      'ℹ️',
  success:   '✅',
  warning:   '⚠️',
  error:     '❌',
  run_event: '⚡',
};

const TYPE_LABELS: Record<string, string> = {
  info:      'Info',
  success:   'Success',
  warning:   'Warning',
  error:     'Error',
  run_event: 'Run event',
};

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

interface Props { notification: Notification; }

export function NotificationItem({ notification: n }: Props) {
  const markRead    = useMarkRead();
  const dismiss     = useDismissNotification();

  return (
    <li
      className={`notification-item ${n.read ? 'notification-item--read' : ''}`}
      aria-label={`${TYPE_LABELS[n.type]} notification: ${n.title}`}
    >
      <span className="notification-icon" aria-hidden>{TYPE_ICONS[n.type]}</span>
      <div className="notification-body">
        <div className="notification-header">
          <strong className="notification-title">{n.title}</strong>
          <time className="notification-time" dateTime={n.createdAt}>
            {relativeTime(n.createdAt)}
          </time>
        </div>
        <p className="notification-text">{n.body}</p>
        {n.runId && (
          <Link href={`/runs/${n.runId}`} className="notification-run-link">
            View run →
          </Link>
        )}
      </div>
      <div className="notification-actions">
        {!n.read && (
          <button
            type="button"
            className="btn-icon"
            aria-label="Mark as read"
            onClick={() => markRead.mutate(n.id)}
          >
            ✓
          </button>
        )}
        <button
          type="button"
          className="btn-icon"
          aria-label="Dismiss notification"
          onClick={() => dismiss.mutate(n.id)}
        >
          ×
        </button>
      </div>
    </li>
  );
}
