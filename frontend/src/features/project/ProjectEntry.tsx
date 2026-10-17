import { Navigate, useLocation } from 'react-router-dom';
import type { ProjectSection } from './projectNavigation';

// Legacy global tool URLs select a project before mounting any tool module.
export default function ProjectEntry({ section }: { section: ProjectSection }) {
  const { search } = useLocation();
  const parameters = new URLSearchParams(search);
  parameters.set('section', section);
  return <Navigate to={`/app/projects?${parameters}`} replace />;
}
