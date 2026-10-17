export const projectSections = ['dashboard', 'documents', 'chat', 'rag'] as const;
export type ProjectSection = typeof projectSections[number];
export function projectDestination(projectId: string, search: URLSearchParams): string {
  const requested = search.get('section');
  const section = projectSections.find(value => value === requested) || 'dashboard';
  const query = new URLSearchParams();
  // Preserve only the deep link belonging to the chosen workspace tool.
  const key = section === 'chat' ? 'conversation' : section === 'documents' ? 'file' : null;
  if (key && search.get(key)) query.set(key, search.get(key)!);
  return `/project/${encodeURIComponent(projectId)}/${section}${query.size ? `?${query}` : ''}`;
}
