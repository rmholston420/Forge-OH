/**
 * Rigpa-LMS Integration — Zod schema for RigpaAgentLaunchContext.
 * Feature-flagged: NEXT_PUBLIC_FEATURE_RIGPA_LMS_ENABLED
 * The plugin shell sends this to the Forge BFF; the BFF transforms it
 * into an OpenHands task context and policy envelope.
 */
import { z } from 'zod';

export const RigpaPermissionsSchema = z.object({
  canWriteRepo: z.boolean(),
  canRunShell: z.boolean(),
  canOpenPR: z.boolean(),
});

export const RigpaPedagogicalContextSchema = z.object({
  audience: z.enum(['beginner', 'intermediate', 'advanced']),
  learningGoals: z.array(z.string()).min(1),
  styleGuide: z.string().optional(),
});

export const RigpaTaskTypeSchema = z.enum([
  'authoring',
  'exercise-gen',
  'code-review',
  'assessment',
  'refactor',
]);

export const RigpaAgentLaunchContextSchema = z.object({
  userId: z.string(),
  courseId: z.string(),
  moduleId: z.string().optional(),
  lessonId: z.string().optional(),
  repoUrl: z.string().url().optional(),
  workspacePath: z.string().optional(),
  taskType: RigpaTaskTypeSchema,
  permissions: RigpaPermissionsSchema,
  pedagogicalContext: RigpaPedagogicalContextSchema,
});

export type RigpaAgentLaunchContext = z.infer<typeof RigpaAgentLaunchContextSchema>;
export type RigpaTaskType = z.infer<typeof RigpaTaskTypeSchema>;
export type RigpaPermissions = z.infer<typeof RigpaPermissionsSchema>;
export type RigpaPedagogicalContext = z.infer<typeof RigpaPedagogicalContextSchema>;

/**
 * Artifact-to-LMS packaging types.
 * Maps a Forge-OH artifact action to the LMS object it produces.
 */
export const LmsArtifactTypeSchema = z.enum([
  'exercise',
  'feedback-record',
  'lesson-content',
  'starter-kit',
  'hint-sequence',
  'quiz',
]);

export const LmsPackageRequestSchema = z.object({
  runId: z.string(),
  artifactIds: z.array(z.string()).min(1),
  targetType: LmsArtifactTypeSchema,
  courseId: z.string(),
  moduleId: z.string().optional(),
  lessonId: z.string().optional(),
});

export const LmsPackageResultSchema = z.object([
  z.object({
    artifactId: z.string(),
    lmsObjectId: z.string(),
    targetType: LmsArtifactTypeSchema,
    status: z.enum(['packaged', 'failed']),
    error: z.string().optional(),
  }),
]).or(z.array(z.object({
  artifactId: z.string(),
  lmsObjectId: z.string(),
  targetType: LmsArtifactTypeSchema,
  status: z.enum(['packaged', 'failed']),
  error: z.string().optional(),
})));

export type LmsArtifactType = z.infer<typeof LmsArtifactTypeSchema>;
export type LmsPackageRequest = z.infer<typeof LmsPackageRequestSchema>;
