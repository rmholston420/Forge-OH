/**
 * src/lib/schemas/skill.ts
 *
 * Skill row shape returned by GET /api/skills (Stage 6.6).
 * Mirrors bff/routers/skills.py::_skill_to_out.
 */
import { z } from 'zod';

export const SkillTypeSchema = z.enum(['repo', 'knowledge', 'agentskills']);
export type SkillType = z.infer<typeof SkillTypeSchema>;

export const SkillSchema = z.object({
  name: z.string(),
  type: SkillTypeSchema.catch('agentskills'),
  description: z.string().default(''),
  triggers: z.array(z.string()).default([]),
  source: z.string().default(''),
  contentPreview: z.string().default(''),
  contentTruncated: z.boolean().default(false),
  isAgentSkillsFormat: z.boolean().default(true),
  disableModelInvocation: z.boolean().default(false),
});
export type Skill = z.infer<typeof SkillSchema>;

export const SkillsSourceCountsSchema = z.record(z.string(), z.number());
export type SkillsSourceCounts = z.infer<typeof SkillsSourceCountsSchema>;

export const SkillsListResponseSchema = z.object({
  data: z.array(SkillSchema),
  sources: SkillsSourceCountsSchema.default({}),
});
export type SkillsListResponse = z.infer<typeof SkillsListResponseSchema>;

export const MarketplaceSkillSchema = z.object({
  name: z.string(),
  description: z.string().default(''),
  source: z.string().default(''),
  version: z.string().default(''),
  author: z.string().default(''),
});
export type MarketplaceSkill = z.infer<typeof MarketplaceSkillSchema>;
