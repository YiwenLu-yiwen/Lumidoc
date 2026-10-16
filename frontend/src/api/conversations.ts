export async function deleteConversation(projectId: string, conversationId: string): Promise<void> {
  const gateway = import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
  const response = await fetch(`${gateway}/chat/api/chat/conversations/${encodeURIComponent(projectId)}/${encodeURIComponent(conversationId)}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${localStorage.getItem('lumidoc_token')}` },
  });
  if (!response.ok) throw new Error('会话删除失败，请稍后重试');
  window.dispatchEvent(new CustomEvent('conversation-deleted', { detail: { projectId, conversationId } }));
  window.dispatchEvent(new Event('chat-updated'));
}
