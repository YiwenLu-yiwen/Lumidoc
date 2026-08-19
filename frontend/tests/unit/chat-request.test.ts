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
