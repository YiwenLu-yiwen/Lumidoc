export function resolveRagProjectId(
  routeProjectId?: string,
  currentProjectId?: string,
): string | null {
  return routeProjectId?.trim() || currentProjectId?.trim() || null;
}
