'use client';
import { useEffect, useRef } from 'react';
import { useNotifications, useMarkAllRead } from '@/features/notifications/hooks';
import { useNotificationsStore } from '@/features/notifications/store';
import { NotificationItem } from './NotificationItem';
import type { NotificationFilter } from '@/features/notifications/store';

const FILTERS: { id: NotificationFilter; label: string }[] = [
  { id: 'all',       label: 'All' },
  { id: 'unread',    label: 'Unread' },
  { id: 'run_event', label: 'Run events' },
];

export function NotificationPanel() {
  const { data: all = [] } = useNotifications();
  const markAllRead = useMarkAllRead();
  const { panelOpen, setPanelOpen, filter, setFilter } = useNotificationsStore();
  const panelRef = useRef<HTMLDivElement>(null);

  // Keyboard trap: Escape closes
  useEffect(() => {
    if (!panelOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setPanelOpen(false);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [panelOpen, setPanelOpen]);

  // Focus panel on open
  useEffect(() => {
    if (panelOpen) panelRef.current?.focus();
  }, [panelOpen]);

  const filtered = all.filter((n) => {
    if (filter === 'unread')    return !n.read;
    if (filter === 'run_event') return n.type === 'run_event';
    return true;
  });

  const unreadCount = all.filter((n) => !n.read).length;

  if (!panelOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="notification-backdrop"
        aria-hidden
        onClick={() => setPanelOpen(false)}
      />

      <div
        id="notification-panel"
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Notifications"
        aria-live="polite"
        tabIndex={-1}
        className="notification-panel"
      >
        <div className="notification-panel-header">
          <h2>Notifications</h2>
          {unreadCount > 0 && (
            <button
              type="button"
              className="btn-link"
              onClick={() => markAllRead.mutate()}
              disabled={markAllRead.isPending}
            >
              Mark all read
            </button>
          )}
          <button
            type="button"
            className="btn-icon"
            aria-label="Close notifications"
            onClick={() => setPanelOpen(false)}
          >
            ×
          </button>
        </div>

        {/* Filter tabs */}
        <div className="notification-filters" role="tablist">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={filter === f.id}
              className={`notification-filter-tab ${filter === f.id ? 'active' : ''}`}
              onClick={() => setFilter(f.id)}
            >
              {f.label}
              {f.id === 'unread' && unreadCount > 0 && (
                <span className="unread-badge">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* List */}
        {filtered.length === 0 ? (
          <div className="notification-empty">
            <p>{filter === 'unread' ? 'All caught up!' : 'No notifications yet.'}</p>
          </div>
        ) : (
          <ul className="notification-list" role="list">
            {filtered.map((n) => <NotificationItem key={n.id} notification={n} />)}
          </ul>
        )}
      </div>
    </>
  );
}
