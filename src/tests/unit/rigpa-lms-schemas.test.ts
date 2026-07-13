/**
 * rigpa-lms-schemas.test.ts
 *
 * The existing rigpa-lms-store.test.ts tests the Zustand store only.
 * This file covers the Zod schemas in src/lib/schemas/rigpa-lms.ts which
 * are the validation boundary for everything the LMS plugin sends to the BFF.
 */
import { describe, it, expect } from 'vitest';
import {
  RigpaAgentLaunchContextSchema,
  RigpaPedagogicalContextSchema,
  RigpaPermissionsSchema,
  RigpaTaskTypeSchema,
  LmsArtifactTypeSchema,
  LmsPackageRequestSchema,
} from '@/lib/schemas/rigpa-lms';

const VALID_PERMISSIONS = {
  canWriteRepo: true,
  canRunShell: false,
  canOpenPR: true,
};

const VALID_PEDAGOGICAL = {
  audience: 'intermediate' as const,
  learningGoals: ['Understand closures'],
};

const VALID_LAUNCH = {
  userId: 'u1',
  courseId: 'c1',
  taskType: 'authoring' as const,
  permissions: VALID_PERMISSIONS,
  pedagogicalContext: VALID_PEDAGOGICAL,
};

describe('RigpaPermissionsSchema', () => {
  it('parses valid permissions', () => {
    expect(() => RigpaPermissionsSchema.parse(VALID_PERMISSIONS)).not.toThrow();
  });

  it('requires all three boolean fields', () => {
    expect(() => RigpaPermissionsSchema.parse({ canWriteRepo: true })).toThrow();
  });
});

describe('RigpaPedagogicalContextSchema', () => {
  it('accepts all three audience levels', () => {
    for (const audience of ['beginner', 'intermediate', 'advanced'] as const) {
      expect(() =>
        RigpaPedagogicalContextSchema.parse({ audience, learningGoals: ['goal'] })
      ).not.toThrow();
    }
  });

  it('rejects empty learningGoals array (min 1)', () => {
    expect(() =>
      RigpaPedagogicalContextSchema.parse({ audience: 'beginner', learningGoals: [] })
    ).toThrow();
  });

  it('styleGuide is optional', () => {
    const result = RigpaPedagogicalContextSchema.parse(VALID_PEDAGOGICAL);
    expect(result.styleGuide).toBeUndefined();
  });
});

describe('RigpaTaskTypeSchema', () => {
  const valid = ['authoring', 'exercise-gen', 'code-review', 'assessment', 'refactor'];
  it.each(valid)('accepts %s', (t) => {
    expect(() => RigpaTaskTypeSchema.parse(t)).not.toThrow();
  });

  it('rejects unknown task type', () => {
    expect(() => RigpaTaskTypeSchema.parse('unknown')).toThrow();
  });
});

describe('RigpaAgentLaunchContextSchema', () => {
  it('parses minimal valid context', () => {
    const result = RigpaAgentLaunchContextSchema.parse(VALID_LAUNCH);
    expect(result.userId).toBe('u1');
    expect(result.moduleId).toBeUndefined();
    expect(result.lessonId).toBeUndefined();
    expect(result.repoUrl).toBeUndefined();
  });

  it('accepts optional moduleId, lessonId, repoUrl, workspacePath', () => {
    const result = RigpaAgentLaunchContextSchema.parse({
      ...VALID_LAUNCH,
      moduleId: 'm1',
      lessonId: 'l1',
      repoUrl: 'https://github.com/org/repo',
      workspacePath: '/workspace',
    });
    expect(result.moduleId).toBe('m1');
    expect(result.repoUrl).toBe('https://github.com/org/repo');
  });

  it('rejects invalid repoUrl', () => {
    expect(() =>
      RigpaAgentLaunchContextSchema.parse({ ...VALID_LAUNCH, repoUrl: 'not-a-url' })
    ).toThrow();
  });

  it('requires userId, courseId, taskType, permissions, pedagogicalContext', () => {
    expect(() => RigpaAgentLaunchContextSchema.parse({})).toThrow();
  });
});

describe('LmsArtifactTypeSchema', () => {
  const valid = ['exercise', 'feedback-record', 'lesson-content', 'starter-kit', 'hint-sequence', 'quiz'];
  it.each(valid)('accepts %s', (t) => {
    expect(() => LmsArtifactTypeSchema.parse(t)).not.toThrow();
  });
});

describe('LmsPackageRequestSchema', () => {
  it('parses a valid request', () => {
    const result = LmsPackageRequestSchema.parse({
      runId: 'run-1',
      artifactIds: ['a1', 'a2'],
      targetType: 'exercise',
      courseId: 'c1',
    });
    expect(result.artifactIds).toHaveLength(2);
  });

  it('rejects empty artifactIds (min 1)', () => {
    expect(() =>
      LmsPackageRequestSchema.parse({
        runId: 'run-1',
        artifactIds: [],
        targetType: 'exercise',
        courseId: 'c1',
      })
    ).toThrow();
  });

  it('moduleId and lessonId are optional', () => {
    const result = LmsPackageRequestSchema.parse({
      runId: 'r',
      artifactIds: ['a'],
      targetType: 'quiz',
      courseId: 'c',
    });
    expect(result.moduleId).toBeUndefined();
  });
});
