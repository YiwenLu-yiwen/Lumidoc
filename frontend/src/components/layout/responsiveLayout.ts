export const COMPACT_LAYOUT_MAX_WIDTH = 768;

export function shouldCollapseSidebar(viewportWidth: number): boolean {
  return viewportWidth <= COMPACT_LAYOUT_MAX_WIDTH;
}
