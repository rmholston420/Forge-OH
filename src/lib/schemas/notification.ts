import { z } from 'zod';

export const NotificationTypeSchema = z.enum([
  'info', 'success', 'warning', 'error', 'run_event',
]);

export const NotificationSchema = z.object({
  id:        z.string().uuid(),
  type:      NotificationTypeSchema,
  title:     z.string(),
  body:      z.string(),
  runId:     z.string().uuid().optional(),
  read:      z.boolean().default(false),
  createdAt: z.string().datetime(),
});

export type Notification = z.infer<typeof NotificationSchema>;
export type NotificationType = z.infer<typeof NotificationTypeSchema>;
