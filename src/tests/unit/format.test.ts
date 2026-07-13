import { describe, it, expect } from 'vitest';
import { formatDuration, formatCost } from '@/lib/utils/format';

describe('formatDuration', () => {
  it('formats null as dash', () => expect(formatDuration(null)).toBe('—'));
  it('formats seconds', () => expect(formatDuration(45000)).toBe('45s'));
  it('formats minutes', () => expect(formatDuration(125000)).toBe('2m 5s'));
  it('formats hours', () => expect(formatDuration(3720000)).toBe('1h 2m'));
});

describe('formatCost', () => {
  it('formats null as dash', () => expect(formatCost(null)).toBe('—'));
  it('formats sub-cent', () => expect(formatCost(0.005)).toBe('<$0.01'));
  it('formats normal cost', () => expect(formatCost(0.042)).toBe('$0.042'));
});
