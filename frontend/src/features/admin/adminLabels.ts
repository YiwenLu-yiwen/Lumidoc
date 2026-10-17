export const serviceLabels: Record<string, [string, string]> = {
  auth: ["账户认证", "Authentication"],
  project: ["项目管理", "Projects"],
  file: ["文件存储", "Files"],
  fileproc: ["文档处理 / OCR", "Document processing / OCR"],
  rag: ["知识库 / LightRAG", "Knowledge base / LightRAG"],
  chat: ["对话服务", "Conversations"],
  llm: ["模型服务", "Language models"],
  graph: ["知识图谱", "Knowledge graph"],
  question: ["问题服务", "Questions"],
  monitoring: ["监控服务", "Monitoring"],
};
const labels: Record<string, string> = {
  healthy: "运行正常",
  unhealthy: "健康检查异常",
  unreachable: "无法连接",
  not_configured: "未配置",
  processed: "已处理",
  reading: "读取文档",
  interrupted: "已中断",
  pending: "等待中",
  queued: "排队中",
  running: "运行中",
  processing: "处理中",
  completed: "已完成",
  success: "已完成",
  succeeded: "重启命令完成",
  failed: "失败",
  cancelled: "已取消",
  canceled: "已取消",
  restarting: "正在重启",
  waiting_extraction: "等待文本提取",
  waiting_for_file: "等待文档处理",
  extracting: "提取中",
  indexing: "建立索引",
  importing: "导入中",
  saving: "保存中",
  done: "已完成",
  timeout: "超时",
  connection: "连接异常",
  processing_failed: "处理失败",
  System: "系统",
};
export function adminLabel(value: string | undefined, zh: boolean) {
  return value ? (zh ? labels[value] || value : value.replace(/_/g, " ")) : "—";
}
export type ServiceStatus = {
  services: { name: string; status: string; latency_ms: number | null }[];
  models: { name: string; size: number; size_vram: number }[] | null;
  resources: { scope: string; cpu_percent: number; memory_percent: number };
  checked_at: string;
  controls?: {
    available: boolean;
    services: string[];
    operations: Record<
      string,
      { status: string; started_at: string; finished_at?: string }
    >;
  };
};
