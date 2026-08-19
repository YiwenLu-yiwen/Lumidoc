import { describe, expect, it } from 'vitest';

import { shouldCollapseSidebar } from '../../src/components/layout/responsiveLayout';


describe('shouldCollapseSidebar', () => {
  it('collapses the application sidebar on compact screens', () => {
    expect(shouldCollapseSidebar(390)).toBe(true);
    expect(shouldCollapseSidebar(768)).toBe(true);
  });

  it('keeps the application sidebar expanded on desktop screens', () => {
    expect(shouldCollapseSidebar(769)).toBe(false);
    expect(shouldCollapseSidebar(1440)).toBe(false);
  });
});
