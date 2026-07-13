/**
 * src/tests/unit/rigpa-lms-store.test.ts
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useRigpaLmsStore } from '@/features/rigpa-lms/store';
import type { RigpaAgentLaunchContext } from '@/lib/schemas/rigpa-lms';

const mockCtx: RigpaAgentLaunchContext = {
  courseId: 'course-1',
  learnerId: 'learner-42',
  activityId: 'activity-7',
  returnUrl: 'https://lms.example.com/return',
  locale: 'en-US',
  metadata: {},
};

beforeEach(() => {
  useRigpaLmsStore.setState({ context: null, ribbonVisible: false, pluginMode: false });
});

describe('useRigpaLmsStore', () => {
  it('initial state: context null, ribbonVisible false, pluginMode false', () => {
    const s = useRigpaLmsStore.getState();
    expect(s.context).toBeNull();
    expect(s.ribbonVisible).toBe(false);
    expect(s.pluginMode).toBe(false);
  });

  it('setContext stores context and sets ribbonVisible=true', () => {
    useRigpaLmsStore.getState().setContext(mockCtx);
    const s = useRigpaLmsStore.getState();
    expect(s.context).toEqual(mockCtx);
    expect(s.ribbonVisible).toBe(true);
  });

  it('clearContext nulls context and sets ribbonVisible=false', () => {
    useRigpaLmsStore.getState().setContext(mockCtx);
    useRigpaLmsStore.getState().clearContext();
    const s = useRigpaLmsStore.getState();
    expect(s.context).toBeNull();
    expect(s.ribbonVisible).toBe(false);
  });

  it('setRibbonVisible updates ribbonVisible independently', () => {
    useRigpaLmsStore.getState().setRibbonVisible(true);
    expect(useRigpaLmsStore.getState().ribbonVisible).toBe(true);
    useRigpaLmsStore.getState().setRibbonVisible(false);
    expect(useRigpaLmsStore.getState().ribbonVisible).toBe(false);
  });

  it('setPluginMode updates pluginMode', () => {
    useRigpaLmsStore.getState().setPluginMode(true);
    expect(useRigpaLmsStore.getState().pluginMode).toBe(true);
  });
});
