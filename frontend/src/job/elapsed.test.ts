import { describe, expect, it } from 'vitest';

import { formatElapsed } from '@/job/elapsed';

describe('elapsed time', () => {
  it('formats minutes and seconds, adding hours only when needed', () => {
    expect(formatElapsed(0)).toBe('0:00');
    expect(formatElapsed(7_400)).toBe('0:07');
    expect(formatElapsed(222_000)).toBe('3:42');
    expect(formatElapsed(3_729_000)).toBe('1:02:09');
    expect(formatElapsed(-5)).toBe('0:00');
  });
});
