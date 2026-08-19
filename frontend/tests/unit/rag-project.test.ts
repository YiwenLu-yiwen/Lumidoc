import { describe, expect, it } from 'vitest';

import { resolveRagProjectId } from '../../src/features/rag/ragProject';


describe('resolveRagProjectId', () => {
  it('prefers the project id from the route', () => {
    expect(resolveRagProjectId('route-project', 'current-project')).toBe(
      'route-project',
    );
  });

  it('uses the current project for the application RAG route', () => {
    expect(resolveRagProjectId(undefined, 'current-project')).toBe(
      'current-project',
    );
  });

  it('returns null when no project is available', () => {
    expect(resolveRagProjectId('', undefined)).toBeNull();
  });
});
