/**
 * src/features/skills/api.ts
 *
 * BFF calls for the Skills feature (Stage 6.6).
 * Backed by the in-process SDK loader in bff/routers/skills.py.
 */
import { bffGet } from '@/lib/api/client';
import { unwrap } from '@/lib/api/response';
import { ENDPOINTS } from '@/lib/api/endpoints';
import {
  SkillSchema,
  SkillsSourceCountsSchema,
  type Skill,
  type SkillsSourceCounts,
} from '@/lib/schemas/skill';
import { z } from 'zod';

const SkillsListResponseSchema = z.object({
  data: z.array(SkillSchema).default([]),
  sources: SkillsSourceCountsSchema.default({}),
});

export interface SkillsListResult {
  data: Skill[];
  sources: SkillsSourceCounts;
}

export async function fetchSkills(params?: {
  includeUser?: boolean;
  includeProject?: boolean;
}): Promise<SkillsListResult> {
  const res = await bffGet<unknown>(ENDPOINTS.SKILLS.list(params));
  const parsed = SkillsListResponseSchema.parse(unwrap(res));
  return { data: parsed.data, sources: parsed.sources };
}
