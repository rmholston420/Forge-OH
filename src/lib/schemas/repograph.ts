/**
 * src/lib/schemas/repograph.ts
 *
 * Zod schemas + inferred TS types for the RepoGraph BFF endpoints
 * (Slice D.4). Kept in sync with:
 *   bff/routers/repograph.py::{IndexResponse, SymbolOut,
 *                              CallerOut, CalleeOut, CoChangedResponse}
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Symbol (used by search, callees, context_bundle)
// ---------------------------------------------------------------------------
export const RepoGraphSymbolSchema = z.object({
  rel_path: z.string(),
  name: z.string(),
  category: z.string(),
  start_line: z.number(),
  end_line: z.number(),
  parent: z.string().nullable().optional(),
  info: z.string(),
  pagerank: z.number(),
});
export type RepoGraphSymbol = z.infer<typeof RepoGraphSymbolSchema>;

// ---------------------------------------------------------------------------
// Callers
// ---------------------------------------------------------------------------
export const RepoGraphCallerSchema = z.object({
  caller_file: z.string(),
  callee_file: z.string(),
  callee: z.string(),
  callee_line: z.number().nullable().optional(),
  call_line: z.number().nullable().optional(),
});
export type RepoGraphCaller = z.infer<typeof RepoGraphCallerSchema>;

// ---------------------------------------------------------------------------
// Callees
// ---------------------------------------------------------------------------
export const RepoGraphCalleeSchema = z.object({
  callee_file: z.string(),
  callee: z.string(),
  category: z.string(),
  callee_line: z.number().nullable().optional(),
  call_line: z.number().nullable().optional(),
  pagerank: z.number(),
});
export type RepoGraphCallee = z.infer<typeof RepoGraphCalleeSchema>;

// ---------------------------------------------------------------------------
// Co-changed files
// ---------------------------------------------------------------------------
export const RepoGraphCoChangedFileSchema = z.object({
  rel_path: z.string(),
  commits: z.number(),
});
export const RepoGraphCoChangedResponseSchema = z.object({
  target: z.string(),
  window: z.number(),
  files: z.array(RepoGraphCoChangedFileSchema),
  available: z.boolean(),
  error: z.string().nullable(),
});
export type RepoGraphCoChangedFile = z.infer<typeof RepoGraphCoChangedFileSchema>;
export type RepoGraphCoChangedResponse = z.infer<
  typeof RepoGraphCoChangedResponseSchema
>;

// ---------------------------------------------------------------------------
// Index response
// ---------------------------------------------------------------------------
export const RepoGraphIndexResponseSchema = z.object({
  repo_key: z.string(),
  workspace_path: z.string(),
  stats: z.record(z.string(), z.number()),
});
export type RepoGraphIndexResponse = z.infer<
  typeof RepoGraphIndexResponseSchema
>;

// ---------------------------------------------------------------------------
// Health (D.1)
// ---------------------------------------------------------------------------
export const RepoGraphHealthSchema = z.object({
  enabled: z.boolean(),
  reachable: z.boolean(),
  neo4j_version: z.string().nullable(),
  neo4j_edition: z.string().nullable(),
  database: z.string().nullable(),
  error: z.string().nullable(),
});
export type RepoGraphHealth = z.infer<typeof RepoGraphHealthSchema>;

// ---------------------------------------------------------------------------
// Full graph (Stage 4.2 / 4.3)
// ---------------------------------------------------------------------------
export const RepoGraphNodeSchema = z.object({
  id: z.string(),
  kind: z.enum(['file', 'symbol']),
  label: z.string(),
  rel_path: z.string(),
  // symbol-only
  category: z.string().nullable().optional(),
  start_line: z.number().nullable().optional(),
  end_line: z.number().nullable().optional(),
  parent: z.string().nullable().optional(),
  pagerank: z.number().nullable().optional(),
  // file-only
  language: z.string().nullable().optional(),
});
export type RepoGraphNode = z.infer<typeof RepoGraphNodeSchema>;

export const RepoGraphEdgeSchema = z.object({
  source: z.string(),
  target: z.string(),
  type: z.enum(['CONTAINS', 'CALLS']),
  line: z.number().nullable().optional(),
});
export type RepoGraphEdge = z.infer<typeof RepoGraphEdgeSchema>;

export const RepoGraphStatsSchema = z.object({
  nodes: z.number(),
  symbols: z.number(),
  files: z.number(),
  edges: z.number(),
});

export const RepoGraphFullGraphSchema = z.object({
  repo_key: z.string(),
  nodes: z.array(RepoGraphNodeSchema),
  links: z.array(RepoGraphEdgeSchema),
  stats: RepoGraphStatsSchema,
});
export type RepoGraphFullGraph = z.infer<typeof RepoGraphFullGraphSchema>;
