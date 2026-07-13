import { z } from 'zod';

export const PlanNodeStatusSchema = z.enum([
  'queued',
  'active',
  'done',
  'failed',
  'blocked',
  'awaiting_approval',
]);

export const PlanNodeSchema = z.object({
  id: z.string(),
  runId: z.string(),
  parentId: z.string().nullable(),
  title: z.string(),
  description: z.string().optional(),
  status: PlanNodeStatusSchema,
  order: z.number(),
  children: z.array(z.lazy((): z.ZodTypeAny => PlanNodeSchema)).optional(),
});

export type PlanNode = z.infer<typeof PlanNodeSchema>;
