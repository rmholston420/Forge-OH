import { z } from 'zod';

export const PlanStepStatusSchema = z.enum(['pending', 'running', 'completed', 'failed', 'skipped']);

export const PlanStepSchema: z.ZodType<any> = z
  .object({
    id: z.string().min(1),
    planId: z.string().min(1).optional(),
    title: z.string().min(1).optional(),
    label: z.string().min(1).optional(),
    status: PlanStepStatusSchema,
    order: z.number(),
    children: z.lazy(() => PlanStepSchema.array()).optional(),
  })
  .superRefine((value, ctx) => {
    if (!value.title && !value.label) {
      ctx.addIssue({ code: 'custom', message: 'Plan step requires title or label' });
    }
  })
  .transform((value) => ({
    ...value,
    title: value.title ?? value.label ?? '',
    label: value.label ?? value.title ?? '',
  }));

export const PlanStatusSchema = z.enum(['pending', 'in_progress', 'completed', 'failed', 'skipped']);

export const PlanSchema = z.object({
  id: z.string().min(1),
  runId: z.string().min(1),
  steps: PlanStepSchema.array(),
  status: PlanStatusSchema,
});

export type PlanStep = z.infer<typeof PlanStepSchema>;
export type Plan = z.infer<typeof PlanSchema>;

export type PlanNode = PlanStep;
