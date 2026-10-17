import type { RagImportProgress } from "@/api/rag";

export function ImportProgress({
  progress,
  language,
}: {
  progress?: RagImportProgress | null;
  language: string;
}) {
  if (!progress) return null;
  const zh = language === "zh-CN";
  const done = progress.finished === progress.total;
  const estimate = progress.estimated_remaining_seconds;
  const duration = (seconds: number) =>
    seconds < 60
      ? `${seconds}${zh ? "秒" : "s"}`
      : `${Math.ceil(seconds / 60)}${zh ? "分钟" : "min"}`;
  const stages: Record<string, string> = zh
    ? {
        queued: "排队中",
        reading: "读取文档",
        waiting_extraction: "等待文档解析 / OCR",
        indexing: "构建索引",
      }
    : {
        queued: "Queued",
        reading: "Reading document",
        waiting_extraction: "Waiting for extraction / OCR",
        indexing: "Building index",
      };
  return (
    <section
      aria-label={zh ? "导入进度" : "Import progress"}
      className="mb-4 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-gray-800 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200"
    >
      <div className="mb-2 flex justify-between gap-2">
        <span>
          {done
            ? zh
              ? "本批处理结束"
              : "Batch finished"
            : zh
              ? "正在导入"
              : "Importing"}
          : {progress.finished}/{progress.total}
        </span>
        <span>{progress.percent}%</span>
      </div>
      <progress
        aria-label={zh ? "已处理文件" : "Files finished"}
        max={progress.total}
        value={progress.finished}
        className="h-2 w-full accent-blue-600"
      />
      <p className="mt-2">
        {zh
          ? `成功 ${progress.succeeded}，失败 ${progress.failed}`
          : `Succeeded ${progress.succeeded}, failed ${progress.failed}`}
      </p>
      {!done && (
        <>
          <p
            className="mt-1 truncate"
            title={progress.active_file || undefined}
          >
            {stages[progress.stage] || progress.stage}
            {progress.active_file ? ` · ${progress.active_file}` : ""}
          </p>
          <p className="mt-1">
            {estimate
              ? zh
                ? `预计剩余约 ${duration(estimate.low)}–${duration(estimate.high)}`
                : `Estimated remaining: ${duration(estimate.low)}–${duration(estimate.high)}`
              : progress.stage === "queued"
                ? zh
                  ? "等待处理资源，暂无法估算时间"
                  : "Waiting for processing capacity; estimate unavailable"
                : zh
                  ? "正在估算剩余时间…"
                  : "Estimating remaining time…"}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            {zh
              ? "进度按文件数计算；预计时间会随文件大小、OCR 和模型负载调整。"
              : "Progress is by file count. Estimates vary with file size, OCR and model load."}
          </p>
        </>
      )}
    </section>
  );
}
