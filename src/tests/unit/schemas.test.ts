/**
 * Unit tests: Zod schema validation for core domain objects.
 * Verifies parse success for valid shapes and parse failure for invalid.
 */
import { describe, it, expect } from 'vitest';
import {
  RigpaAgentLaunchContextSchema,
  LmsPackageRequestSchema,
} from '@/lib/schemas/rigpa-lms';
import { SEED } from '../fixtures/seed';

const validLaunchContext = {
  userId: 'usr_001',
  courseId: SEED.lms.course1,
  moduleId: SEED.lms.module1,
  taskType: 'exercise-gen' as const,
  permissions: { canWriteRepo: true, canRunShell: true, canOpenPR: false },
  pedagogicalContext: {
    audience: 'beginner' as const,
    learningGoals: ['Understand closures'],
  },
};

describe('RigpaAgentLaunchContextSchema', () => {
  it('parses a valid launch context', () => {
    const result = RigpaAgentLaunchContextSchema.safeParse(validLaunchContext);
    expect(result.success).toBe(true);
  });

  it('rejects missing userId', () => {
    const { userId: _, ...noId } = validLaunchContext;
    const result = RigpaAgentLaunchContextSchema.safeParse(noId);
    expect(result.success).toBe(false);
  });

  it('rejects invalid taskType', () => {
    const result = RigpaAgentLaunchContextSchema.safeParse({
      ...validLaunchContext,
      taskType: 'invalid-type',
    });
    expect(result.success).toBe(false);
  });

  it('rejects invalid audience', () => {
    const result = RigpaAgentLaunchContextSchema.safeParse({
      ...validLaunchContext,
      pedagogicalContext: {
        ...validLaunchContext.pedagogicalContext,
        audience: 'expert',
      },
    });
    expect(result.success).toBe(false);
  });

  it('accepts optional fields absent', () => {
    const minimal = {
      userId: 'u1',
      courseId: 'c1',
      taskType: 'refactor' as const,
      permissions: { canWriteRepo: false, canRunShell: false, canOpenPR: false },
      pedagogicalContext: {
        audience: 'advanced' as const,
        learningGoals: ['improve performance'],
      },
    };
    const result = RigpaAgentLaunchContextSchema.safeParse(minimal);
    expect(result.success).toBe(true);
  });
});

describe('LmsPackageRequestSchema', () => {
  it('parses a valid package request', () => {
    const result = LmsPackageRequestSchema.safeParse({
      runId: SEED.runs.r1,
      artifactIds: [SEED.artifacts.art1],
      targetType: 'exercise',
      courseId: SEED.lms.course1,
    });
    expect(result.success).toBe(true);
  });

  it('rejects empty artifactIds', () => {
    const result = LmsPackageRequestSchema.safeParse({
      runId: SEED.runs.r1,
      artifactIds: [],
      targetType: 'exercise',
      courseId: SEED.lms.course1,
    });
    expect(result.success).toBe(false);
  });
});
