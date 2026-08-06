import { z } from 'zod';

/**
 * Stage 5.6a / ADR-024 — MemoryPort recent-writes wire shape.
 *
 * Mirrors the projected form of ``openhands_tools_ext.memory.ports.memory
 * .MemoryEventRecord`` on the BFF side (see bff/routers/memory.py :: _record_to_wire).
 */
export const MemoryWriteRecordSchema = z.object({
  id: z.string(),
  subject: z.string(),
  predicate: z.string(),
  object: z.string(),
  provenance: z.string(),
  confidence: z.number(),
  piiTier: z.string(),
  sourceCitation: z.string().nullable(),
  writtenAt: z.string(),
});
export type MemoryWriteRecord = z.infer<typeof MemoryWriteRecordSchema>;

export const RecentWritesResponseSchema = z.object({
  data: z.array(MemoryWriteRecordSchema),
});
export type RecentWritesResponse = z.infer<typeof RecentWritesResponseSchema>;
