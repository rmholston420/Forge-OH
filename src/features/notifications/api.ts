import type { Notification } from '@/lib/schemas/notification';

const BASE = '/api/notifications';

export async function fetchNotifications(): Promise<Notification[]> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error('Failed to fetch notifications');
  return res.json();
}

export async function markRead(id: string): Promise<Notification> {
  const res = await fetch(`${BASE}/${id}/read`, { method: 'PATCH' });
  if (!res.ok) throw new Error('Failed to mark notification read');
  return res.json();
}

export async function markAllRead(): Promise<void> {
  const res = await fetch(`${BASE}/read-all`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to mark all read');
}

export async function dismissNotification(id: string): Promise<void> {
  const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to dismiss notification');
}
