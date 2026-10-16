import { describe, expect, it } from 'vitest';

import { createChatRequestPayload } from '../../src/features/chat/chatRequest';


describe('createChatRequestPayload', () => {
  it('includes the selected model id in chat requests', () => {
    const payload = createChatRequestPayload({
      content: 'hello',
      projectId: 'project-1',
      userId: 'user-1',
      modelId: 'qwen3:8b',
    });

    expect(payload.model).toBe('qwen3:8b');
  });
});

it('keeps multiple turns in the selected conversation', () => {
  const first = createChatRequestPayload({ content: 'First', conversationId: 'conversation-a' });
  const second = createChatRequestPayload({ content: 'Followup', conversationId: 'conversation-a' });
  const other = createChatRequestPayload({ content: 'New chat', conversationId: 'conversation-b' });
  expect(first.session_id).toBe(second.session_id);
  expect(other.session_id).not.toBe(first.session_id);
});
