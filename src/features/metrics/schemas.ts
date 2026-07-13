import { z } from 'zod';

export const PeriodSchema = z.enum(['7d', '30d', '90d', 'all']);
export type Period = z.infer<typeof PeriodSchema>;

export const RunMetricsSummarySchema = z.object({
  totalRuns:      z.number().int(),
  totalCostUsd:   z.number(),
  totalTokens:    z.number().int(),
  avgDurationMs:  z.number(),
  successRate:    z.number().min(0).max(1),
  failureRate:    z.number().min(0).max(1),
  p50DurationMs:  z.number(),
  p95DurationMs:  z.number(),
  // deltas vs prior period (null when period=all)
  deltaRuns:      z.number().nullable(),
  deltaCostUsd:   z.number().nullable(),
});
export type RunMetricsSummary = z.infer<typeof RunMetricsSummarySchema>;

export const DailyMetricsPointSchema = z.object({
  date:        z.string(),  // YYYY-MM-DD
  runs:        z.number().int(),
  costUsd:     z.number(),
  tokens:      z.number().int(),
  successRate: z.number(),
});
export type DailyMetricsPoint = z.infer<typeof DailyMetricsPointSchema>;

export const ModelBreakdownSchema = z.object({
  model:         z.string(),
  runs:          z.number().int(),
  costUsd:       z.number(),
  tokens:        z.number().int(),
  avgDurationMs: z.number(),
});
export type ModelBreakdown = z.infer<typeof ModelBreakdownSchema>;

export const WorkspaceBreakdownSchema = z.object({
  workspaceId: z.string(),
  name:        z.string(),
  runs:        z.number().int(),
  costUsd:     z.number(),
});
export type WorkspaceBreakdown = z.infer<typeof WorkspaceBreakdownSchema>;
