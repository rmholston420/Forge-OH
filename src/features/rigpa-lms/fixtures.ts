/**
 * MSW fixture data for Rigpa-LMS API routes.
 * Mirrors expected live payload shapes exactly.
 */
import type { RigpaAgentLaunchContext } from '@/lib/schemas/rigpa-lms';

export const mockRigpaContext: RigpaAgentLaunchContext = {
  userId: 'usr_demo001',
  courseId: 'RIGPA-CS101',
  moduleId: 'M3-Functions',
  lessonId: 'L2-Closures',
  repoUrl: 'https://github.com/rigpa-lms/cs101-exercises',
  workspacePath: '/workspace/cs101',
  taskType: 'exercise-gen',
  permissions: {
    canWriteRepo: true,
    canRunShell: true,
    canOpenPR: false,
  },
  pedagogicalContext: {
    audience: 'beginner',
    learningGoals: [
      'Understand closure scope in JavaScript',
      'Write functions that return functions',
      'Debug common closure pitfalls',
    ],
    styleGuide: 'Use ES6 syntax. Prefer arrow functions. Add JSDoc comments.',
  },
};

export const mockContextInjectionResponse = {
  sessionId: 'sess_rigpa_demo001',
  injected: true,
};

export const mockPackageResponse = [
  { artifactId: 'art_001', lmsObjectId: 'lms_obj_closures_ex1', targetType: 'exercise' as const, status: 'packaged' as const },
  { artifactId: 'art_002', lmsObjectId: 'lms_obj_closures_ex2', targetType: 'exercise' as const, status: 'packaged' as const },
];
