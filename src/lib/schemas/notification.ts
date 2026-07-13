import { z } from 'zod';

export const NotificationLevelSchema = z.enum(['info', 'success', 'warning', 'error']);

export const NotificationSchema = z.object({
  id: z.string(),
  type: z.union([NotificationLevelSchema, z.literal('run_event')]).default('info'),
  level: NotificationLevelSchema.default('info'),
  title: z.string(),
  body: z.string(),
  message: z.string().default(''),
  read: z.boolean().default(false),
  createdAt: z.string(),
  runId: z.string().optional(),
});

export type Notification = z.infer<typeof NotificationSchema>;
