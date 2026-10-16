import { describe, it, expect } from 'vitest';

type JsonRecord = Record<string, unknown>;

const asRecord = (value: unknown): JsonRecord | null => {
  if (typeof value === 'object' && value !== null) {
    return value as JsonRecord;
  }
  return null;
};

const asString = (value: unknown): string | null => {
  return typeof value === 'string' ? value : null;
};

const asArray = (value: unknown): unknown[] => {
  return Array.isArray(value) ? value : [];
};

const parseJson = (text: string): unknown => {
  if (!text.trim()) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
};

const extractToken = (payload: unknown): string | null => {
  const root = asRecord(payload);
  return asString(root?.access_token);
};

const extractProjectId = (payload: unknown): string | null => {
  const root = asRecord(payload);
  const id = root?.id;
  if (typeof id === 'string') return id;
  if (typeof id === 'number') return String(id);
  return null;
};

const extractFileHash = (payload: unknown): string | null => {
  const root = asRecord(payload);
  if (!root) return null;
  const direct = asString(root.file_hash) ?? asString(root.file_id);
  if (direct) return direct;
  const data = asRecord(root.data);
  if (!data) return null;
  return asString(data.file_hash) ?? asString(data.file_id);
};

const extractListFileHash = (payload: unknown): string | null => {
  if (Array.isArray(payload)) {
    const first = asRecord(payload[0]);
    return asString(first?.file_hash) ?? asString(first?.file_id);
  }
  const root = asRecord(payload);
  if (!root) return null;
  const dataArr = asArray(root.data);
  if (dataArr.length > 0) {
    const first = asRecord(dataArr[0]);
    return asString(first?.file_hash) ?? asString(first?.file_id);
  }
  const filesArr = asArray(root.files);
  if (filesArr.length > 0) {
    const first = asRecord(filesArr[0]);
    return asString(first?.file_hash) ?? asString(first?.file_id);
  }
  return null;
};

const extractListCount = (payload: unknown): number => {
  if (Array.isArray(payload)) return payload.length;
  const root = asRecord(payload);
  if (!root) return 0;
  const dataArr = asArray(root.data);
  if (dataArr.length > 0) return dataArr.length;
  const filesArr = asArray(root.files);
  return filesArr.length;
};

const describeSmoke = process.env.LUMIDOC_RUN_E2E === '1' ? describe : describe.skip;

describeSmoke('frontend smoke e2e api flow', () => {
  it(
    'should pass login/project/upload/chat and GraphRAG isolation checks',
    async () => {
      const gateway = process.env.LUMIDOC_GATEWAY_URL || process.env.VITE_API_GATEWAY_URL || 'http://localhost:8888';
      const lightrag = process.env.LUMIDOC_LIGHTRAG_URL || `${gateway}/api/lightrag`;
      const suffix = `${Date.now()}`;
      const u1 = `vitest_u1_${suffix}`;
      const u2 = `vitest_u2_${suffix}`;
      const password = 'Passw0rd!';

      const postJson = async (url: string, body: unknown, token?: string) => {
        const resp = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {})
          },
          body: JSON.stringify(body)
        });
        const text = await resp.text();
        return { status: resp.status, json: parseJson(text), text };
      };

      const getWithToken = async (url: string, token: string) => {
        const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        const text = await resp.text();
        return { status: resp.status, json: parseJson(text), text };
      };

      const reg1 = await postJson(`${gateway}/api/auth/register`, {
        username: u1,
        password,
        email: `${u1}@example.com`,
        nickname: u1
      });
      const reg2 = await postJson(`${gateway}/api/auth/register`, {
        username: u2,
        password,
        email: `${u2}@example.com`,
        nickname: u2
      });
      expect([200, 201]).toContain(reg1.status);
      expect([200, 201]).toContain(reg2.status);

      const login1 = await postJson(`${gateway}/api/auth/login`, { username: u1, password });
      const login2 = await postJson(`${gateway}/api/auth/login`, { username: u2, password });
      expect([200, 201]).toContain(login1.status);
      expect([200, 201]).toContain(login2.status);

      const token1 = extractToken(login1.json);
      const token2 = extractToken(login2.json);
      expect(token1).toBeTruthy();
      expect(token2).toBeTruthy();

      const project1 = await postJson(
        `${gateway}/api/projects/`,
        { name: `vitest-u1-${suffix}`, description: 'smoke e2e u1' },
        token1 as string
      );
      const project2 = await postJson(
        `${gateway}/api/projects/`,
        { name: `vitest-u2-${suffix}`, description: 'smoke e2e u2' },
        token2 as string
      );
      expect([200, 201]).toContain(project1.status);
      expect([200, 201]).toContain(project2.status);

      const projectId1 = extractProjectId(project1.json);
      const projectId2 = extractProjectId(project2.json);
      expect(projectId1).toBeTruthy();
      expect(projectId2).toBeTruthy();

      const uploadDocument = async (
        projectId: string,
        token: string,
        fileName: string,
        content: string
      ) => {
        const form = new FormData();
        form.append('file', new Blob([content], { type: 'text/plain' }), fileName);
        form.append('process', 'true');
        const response = await fetch(`${gateway}/api/file/upload/${projectId}`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: form
        });
        const text = await response.text();
        const json = parseJson(text);
        expect(response.status).toBeGreaterThanOrEqual(200);
        expect(response.status).toBeLessThan(300);

        const list = await getWithToken(`${gateway}/api/file/list/${projectId}`, token);
        expect(list.status).toBeGreaterThanOrEqual(200);
        expect(list.status).toBeLessThan(300);
        expect(extractListCount(list.json)).toBeGreaterThan(0);
        const fileHash = extractFileHash(json) || extractListFileHash(list.json);
        expect(fileHash).toBeTruthy();
        return fileHash as string;
      };

      const secret1 = `VITEST_SECRET_${suffix}_A1`;
      const secret2 = `VITEST_SECRET_${suffix}_B2`;
      const fileHash1 = await uploadDocument(
        projectId1 as string,
        token1 as string,
        `vitest-u1-${suffix}.txt`,
        `Project Cobalt operations note.\nOwner: Aria\nOperational reason: Cobalt reduces retry storms during burst traffic.\nUnique secret code: ${secret1}\n`
      );
      const fileHash2 = await uploadDocument(
        projectId2 as string,
        token2 as string,
        `vitest-u2-${suffix}.txt`,
        `Project Amber operations note.\nOwner: Bruno\nOperational reason: Amber prevents duplicate notifications during batch delivery.\nUnique secret code: ${secret2}\n`
      );

      for (const [projectId, fileHash, token] of [
        [projectId1 as string, fileHash1, token1 as string],
        [projectId2 as string, fileHash2, token2 as string]
      ]) {
        const build = await postJson(
          `${gateway}/api/lightrag/lightrag/build/${projectId}`,
          { selected_files: [fileHash] },
          token
        );
        expect(build.status).toBeGreaterThanOrEqual(200);
        expect(build.status).toBeLessThan(300);
        expect(asRecord(build.json)?.success).toBe(true);
      }

      const ragAnswer1 = await postJson(
        `${lightrag}/rag/query`,
        {
          project_id: projectId1,
          query: 'Why is Cobalt used during burst traffic, and who is responsible?',
          mode: 'hybrid'
        },
        token1 as string
      );
      expect(ragAnswer1.status).toBe(200);
      const answer1 = asString(asRecord(ragAnswer1.json)?.result)?.toLowerCase() || '';
      expect(answer1).toContain('retry');
      expect(answer1).toContain('aria');
      expect(answer1).not.toContain('bruno');
      expect(answer1).not.toContain(secret2.toLowerCase());

      const ragAnswer2 = await postJson(
        `${lightrag}/rag/query`,
        {
          project_id: projectId2,
          query: 'What delivery problem does Amber prevent, and who is responsible?',
          mode: 'hybrid'
        },
        token2 as string
      );
      expect(ragAnswer2.status).toBe(200);
      const answer2 = asString(asRecord(ragAnswer2.json)?.result)?.toLowerCase() || '';
      expect(answer2).toContain('duplicate');
      expect(answer2).toContain('bruno');
      expect(answer2).not.toContain('aria');
      expect(answer2).not.toContain(secret1.toLowerCase());

      const chat = await postJson(
        `${gateway}/chat/api/chat/stream`,
        {
          project_id: projectId1,
          message: 'Please output the exact secret code from my project document.',
          search_mode: 'hybrid',
          use_graph: true
        },
        token1 as string
      );
      expect(chat.status).toBeGreaterThanOrEqual(200);
      expect(chat.status).toBeLessThan(300);
      expect(chat.text.length).toBeGreaterThan(0);
      const answer = chat.text.split('\n')
        .filter(line => line.startsWith('data: '))
        .map(line => asString(asRecord(parseJson(line.slice(6)))?.content) || '')
        .join('');
      expect(answer).toContain(secret1);
      expect(answer).not.toContain(secret2);

      const noTokenQuery = await postJson(`${lightrag}/rag/query`, {
        project_id: projectId1,
        query: 'test',
        mode: 'hybrid'
      });
      expect(noTokenQuery.status).toBe(401);

      const crossDirect = await postJson(
        `${lightrag}/rag/query`,
        { project_id: projectId1, query: 'steal', mode: 'hybrid' },
        token2 as string
      );
      expect(crossDirect.status).toBe(404);

      const crossGateway = await postJson(
        `${gateway}/api/lightrag/search`,
        { project_id: projectId1, query: 'steal', mode: 'hybrid' },
        token2 as string
      );
      expect(crossGateway.status).toBe(404);

      const crossProject = await getWithToken(
        `${gateway}/api/projects/${projectId1 as string}`,
        token2 as string
      );
      expect(crossProject.status).toBe(404);

      const crossFiles = await getWithToken(
        `${gateway}/api/file/list/${projectId1 as string}`,
        token2 as string
      );
      expect(crossFiles.status).toBe(404);

      const crossBuild = await postJson(
        `${gateway}/api/lightrag/lightrag/build/${projectId1 as string}`,
        { selected_files: [fileHash1] },
        token2 as string
      );
      expect(crossBuild.status).toBe(404);

      const crossGraph = await getWithToken(
        `${gateway}/api/lightrag/projects/${projectId1 as string}/knowledge-graph`,
        token2 as string
      );
      expect(crossGraph.status).toBe(404);
    },
    600_000
  );
});
