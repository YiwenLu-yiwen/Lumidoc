/** Durable browser-side delivery. Blobs stay on this device until acknowledged. */
type Operation = {
  id: string;
  owner: string;
  project: string;
  kind: "upload" | "delete";
  file?: File;
  path?: string;
  attempts: number;
  nextAt: number;
  state: "pending" | "completed" | "failed";
  result?: unknown;
};
const active = new Map<string, Promise<unknown>>();
const gateway = import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:8888";
function owner() {
  try {
    return JSON.parse(localStorage.getItem("lumidoc_user") || "{}").id as
      | string
      | undefined;
  } catch {
    return undefined;
  }
}
function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("lumidoc-file-outbox", 1);
    request.onupgradeneeded = () =>
      request.result.createObjectStore("operations", { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
async function save(...batch: Operation[]) {
  const db = await database();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction("operations", "readwrite");
    for (const record of batch) tx.objectStore("operations").put(record);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () =>
      reject(tx.error || new Error("Local storage transaction aborted"));
  });
  db.close();
}
async function records(): Promise<Operation[]> {
  const db = await database();
  try {
    return await new Promise((resolve, reject) => {
      const request = db
        .transaction("operations")
        .objectStore("operations")
        .getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  } finally {
    db.close();
  }
}
async function deliver(
  record: Operation,
  progress?: (loaded: number, total: number) => void,
): Promise<unknown> {
  if (active.has(record.id)) return active.get(record.id)!;
  const work = (async () => {
    while (record.state === "pending" && owner() === record.owner) {
      await new Promise((resolve) =>
        setTimeout(resolve, Math.max(0, record.nextAt - Date.now())),
      );
      if (owner() !== record.owner)
        throw new Error("Operation paused until the original account signs in");
      const token = localStorage.getItem("lumidoc_token");
      if (!token) throw new Error("Sign in to resume pending operations");
      try {
        const url =
          record.kind === "upload"
            ? `${gateway}/api/file/upload/${record.project}`
            : `${gateway}/api/file/${record.project}/${encodeURIComponent(record.path!)}`;
        const response = await new Promise<Response>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open(record.kind === "upload" ? "POST" : "DELETE", url);
          xhr.timeout = 180000;
          xhr.setRequestHeader("Authorization", `Bearer ${token}`);
          xhr.setRequestHeader("X-Operation-Id", record.id);
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) progress?.(e.loaded, e.total);
          };
          xhr.onload = () =>
            resolve(new Response(xhr.response, { status: xhr.status }));
          xhr.onerror = () => reject(new Error("Connection interrupted"));
          xhr.ontimeout = () => reject(new Error("Delivery timed out"));
          if (record.kind === "upload") {
            const body = new FormData();
            body.append("file", record.file!);
            body.append("process", "true");
            xhr.send(body);
          } else xhr.send();
        });
        if (response.status === 401) throw new Error("AUTH_REQUIRED");
        if (response.status >= 500 || response.status === 429)
          throw new Error("Service recovering");
        const result =
          response.status === 404 && record.kind === "delete"
            ? { success: true }
            : await response.json();
        if (
          !response.ok &&
          !(response.status === 404 && record.kind === "delete")
        ) {
          record.state = "failed";
          record.result = result;
          await save(record);
          throw new Error("Operation rejected");
        }
        if (result.success === false)
          throw new Error("Operation not acknowledged");
        record.state = "completed";
        record.result = result;
        delete record.file;
        await save(record);
        window.dispatchEvent(
          new CustomEvent("file-operations-updated", {
            detail: { projectId: record.project },
          }),
        );
        return result;
      } catch (error) {
        if (error instanceof Error && error.message === "AUTH_REQUIRED")
          throw new Error("Sign in to resume pending operations");
        if (record.state === "failed") throw error;
        record.attempts += 1;
        if (record.attempts >= 5) {
          record.state = "failed";
          await save(record);
          throw new Error(
            "Automatic recovery limit reached. Your pending file is retained on this device.",
          );
        }
        record.nextAt = Date.now() + 30000;
        await save(record);
      }
    }
    if (record.state === "completed") return record.result;
    throw new Error("Operation paused");
  })();
  active.set(record.id, work);
  try {
    return await work;
  } finally {
    active.delete(record.id);
  }
}
export async function enqueueFileOperation<T>(
  project: string,
  value: { kind: "upload"; file: File } | { kind: "delete"; path: string },
  progress?: (loaded: number, total: number) => void,
): Promise<T> {
  const user = owner();
  if (!user) throw new Error("Sign in first");
  const record: Operation = {
    id: crypto.randomUUID(),
    owner: user,
    project,
    ...value,
    attempts: 0,
    nextAt: 0,
    state: "pending",
  };
  await save(record);
  return (await deliver(record, progress)) as T;
}
export function resumeFileOperations(userId: string) {
  let closed = false;
  const resume = async () => {
    for (const record of await records()) {
      if (closed) return;
      if (record.owner === userId && record.state === "pending")
        void deliver(record).catch(() => undefined);
    }
  };
  void resume().catch(() => undefined);
  return () => {
    closed = true;
  };
}

export async function pendingFileOperations(project: string) {
  return (await records()).filter(
    (record) =>
      record.owner === owner() &&
      record.project === project &&
      record.state !== "completed",
  );
}
export async function retryFileOperation(id: string) {
  const record = (await records()).find(
    (item) => item.id === id && item.owner === owner(),
  );
  if (!record || record.state !== "failed") return;
  const retry = {
    ...record,
    id: crypto.randomUUID(),
    attempts: 0,
    nextAt: 0,
    state: "pending" as const,
  };
  record.state = "completed";
  delete record.file;
  await save(record, retry);
  void deliver(retry).catch(() => undefined);
}

/** Commit the entire selection before starting delivery, so reload retains later files too. */
export async function enqueueFileUploads<T>(
  project: string,
  files: File[],
  progress?: (index: number, loaded: number, total: number) => void,
): Promise<T[]> {
  const user = owner();
  if (!user) throw new Error("Sign in first");
  const batch: Operation[] = files.map((file) => ({
    id: crypto.randomUUID(),
    owner: user,
    project,
    kind: "upload",
    file,
    attempts: 0,
    nextAt: 0,
    state: "pending",
  }));
  await save(...batch);
  const results: T[] = [];
  for (const [index, record] of batch.entries()) {
    results.push(
      (await deliver(record, (loaded, total) =>
        progress?.(index, loaded, total),
      )) as T,
    );
  }
  return results;
}
