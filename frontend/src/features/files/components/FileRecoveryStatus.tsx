import { useEffect, useState } from "react";
import { pendingFileOperations, retryFileOperation } from "@/api/fileOutbox";
import { useLanguage } from "@/context/LanguageContext";
export function FileRecoveryStatus({ projectId }: { projectId: string }) {
  const { currentLanguage } = useLanguage();
  const zh = currentLanguage === "zh-CN";
  const [rows, setRows] = useState<
    Awaited<ReturnType<typeof pendingFileOperations>>
  >([]);
  useEffect(() => {
    let cancelled = false;
    const refresh = () =>
      void pendingFileOperations(projectId)
        .then((result) => {
          if (!cancelled) setRows(result);
        })
        .catch(() => undefined);
    refresh();
    const timer = window.setInterval(refresh, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [projectId]);
  if (!rows.length) return null;
  return (
    <div
      className="mx-4 my-2 rounded-lg border bg-card p-3 text-sm"
      role="status"
    >
      {rows.map((row) => (
        <div key={row.id} className="flex flex-wrap justify-between gap-2 py-1">
          <span className="break-all">
            {row.file?.name || row.path} ·{" "}
            {row.state === "failed"
              ? zh
                ? "自动恢复次数已达上限"
                : "Automatic recovery limit reached"
              : row.attempts
                ? zh
                  ? "连接中断，正在自动恢复…"
                  : "Connection interrupted; recovering…"
                : zh
                  ? "操作进行中…"
                  : "Operation in progress…"}
          </span>
          {row.state === "failed" && (
            <button
              className="text-blue-600"
              onClick={() => void retryFileOperation(row.id)}
            >
              {zh ? "重新尝试" : "Retry"}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
