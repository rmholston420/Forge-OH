import { z } from 'zod';

export const MetricSchema = z.object({
  runId: z.string(),
  name: z.string(),
  value: z.number(),
  unit: z.string(),
  recordedAt: z.string(),
});
export type Metric = z.infer<typeof MetricSchema>;
export const RunMetricSchema = MetricSchema;
export type RunMetric = Metric;

export const MetricSeriesSchema = z.object({
  name: z.string(),
  points: z.array(MetricSchema).default([]),
});
export type MetricSeries = z.infer<typeof MetricSeriesSchema>;

export const RunMetricsSchema = z.object({
  tokenCount: z.number().default(0),
  toolCallCount: z.number().default(0),
  filesTouchedCount: z.number().default(0),
  costUsd: z.number().default(0),
  durationMs: z.number().default(0),
  series: z.array(MetricSeriesSchema).default([]),
});
export type RunMetrics = z.infer<typeof RunMetricsSchema>;
export const MetricsSummarySchema = RunMetricsSchema;
export type MetricsSummary = RunMetrics;
