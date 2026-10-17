import { useEffect, useState } from 'react';

/** Elapsed waiting/thinking phase, frozen as soon as answer output starts. */
export function ThinkingElapsed({ startedAt, finishedAt, language }: {
  startedAt?: number; finishedAt?: number; language: string;
}) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (startedAt === undefined || finishedAt !== undefined) return;
    setNow(Date.now());
    const interval = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(interval);
  }, [startedAt, finishedAt]);
  if (startedAt === undefined) return null;
  const seconds = Math.max(0, Math.floor(((finishedAt ?? now) - startedAt) / 1000));
  return <span title={language === 'zh-CN' ? '从发出请求至开始回答的等待和思考用时' : 'Elapsed waiting and thinking time before the answer'} className="ml-2 text-xs tabular-nums" aria-label={language === 'zh-CN' ? '思考用时' : 'Thinking time'}>{seconds}s</span>;
}
