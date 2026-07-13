import { describe, it, expect } from 'vitest';
import { selectSelectedTab } from '@/lib/state/ui-store';

describe('ui-store selectors', () => {
  it('selectSelectedTab returns default when undefined', () => {
    const state = {} as any;
    expect(selectSelectedTab(state)).toBe('overview');
  });

  it('selectSelectedTab returns stored value when present', () => {
    const state = { selectedTab: 'events' } as any;
    expect(selectSelectedTab(state)).toBe('events');
  });
});
