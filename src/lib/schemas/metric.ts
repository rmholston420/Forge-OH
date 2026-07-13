import { z } from 'zod';

export const MetricPointSchema = z.object({
  ts: z.string(),         // ISO timestamp
  value: z.number(),
});

export const MetricSeriesSchema = z.object({
  name: z.string(),
  unit: z.string().default(''),
  points: z.array(MetricPointSchema),
});

export const RunMetricsSchema = z.object({
  runId: z.string(),
  tokenCount: z.number().int().default(0),
  toolCallCount: z.number().int().default(0),
  filesTouchedCount: z.number().int().default(0),
  costUsd: z.number().default(0),
  durationMs: z.number().nullable().default(null),
  series: z.array(MetricSeriesSchema).default([]),
});

export type MetricPoint = z.infer<typeof MetricPointSchema>;
export type MetricSeries = z.infer<typeof MetricSeriesSchema>;
export type RunMetrics = z.infer<typeof RunMetricsSchema>;
