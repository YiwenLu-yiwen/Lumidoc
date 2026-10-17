export interface ChatRequestPayloadInput {
  content: string;
  projectId?: string;
  userId?: string;
  modelId?: string;
  conversationId?: string;
  thinkingEnabled?: boolean;
}

export interface ChatRequestPayload {
  content: string;
  message: string;
  project_id: string;
  search_mode: 'hybrid';
  use_graph: true;
  user_id: string;
  model?: string;
  session_id: string;
  think: boolean;
}

export function createChatRequestPayload({
  content,
  projectId,
  userId,
  modelId,
  conversationId,
  thinkingEnabled = false,
}: ChatRequestPayloadInput): ChatRequestPayload {
  return {
    content,
    think: thinkingEnabled,
    session_id: conversationId || "legacy",
    message: content,
    project_id: projectId || 'default',
    search_mode: 'hybrid',
    use_graph: true,
    user_id: userId || 'unknown',
    ...(modelId ? { model: modelId } : {}),
  };
}
