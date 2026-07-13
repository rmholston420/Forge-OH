import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notificationKeys } from '@/lib/query/query-keys';
import { fetchNotifications, markRead, markAllRead, dismissNotification } from './api';

export function useNotifications() {
  return useQuery({
    queryKey: notificationKeys.all,
    queryFn: fetchNotifications,
    refetchInterval: 10_000,
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: markRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationKeys.all }),
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: markAllRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationKeys.all }),
  });
}

export function useDismissNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: dismissNotification,
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationKeys.all }),
  });
}
