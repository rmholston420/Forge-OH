/**
 * Rigpa-LMS feature barrel.
 * Re-exports all public surface for Slice 5C.
 */
export { RigpaLmsRibbon } from './RigpaLmsRibbon';
export { useRigpaLmsContext } from './hooks';
export { rigpaLmsStore, useRigpaLmsStore } from './store';
export * from './api';
export type {
  RigpaAgentLaunchContext,
  RigpaTaskType,
  RigpaPermissions,
  RigpaPedagogicalContext,
  LmsArtifactType,
  LmsPackageRequest,
} from '@/lib/schemas/rigpa-lms';
