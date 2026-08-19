export interface ChatRequestPayloadInput {
  content: string;
  projectId?: string;
  userId?: string;
  modelId?: string;
}

export interface ChatRequestPayload {
  content: string;
  message: string;
  project_id: string;
  search_mode: 'hybrid';
  use_graph: true;
  user_id: string;
  model?: string;
}

export function createChatRequestPayload({
  content,
  projectId,
  userId,
  modelId,
}: ChatRequestPayloadInput): ChatRequestPayload {
  return {
    content,
    message: content,
    project_id: projectId || 'default',
    search_mode: 'hybrid',
    use_graph: true,
    user_id: userId || 'unknown',
    ...(modelId ? { model: modelId } : {}),
  };
}
