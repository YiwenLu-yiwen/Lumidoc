import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { FileText, Network, MessageSquare, ArrowRight } from "lucide-react";
import { projectApi } from "@/api/project";
import { fileApi } from "@/api/file";
import { ragApi, type RagFileStatusResponse } from "@/api/rag";
import { apiClient } from "@/api/client";
import type { ProjectResponse } from "@/types/api";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { ImportProgress } from "@/features/rag/ImportProgress";

type Conversation = { id: string; title: string; timestamp: string };
export default function ProjectOverview() {
  const { projectId } = useParams<{ projectId: string }>();
  const { currentLanguage } = useLanguage();
  const { user } = useAuth();
  const userId = user?.id;
  const zh = currentLanguage === "zh-CN";
  const [state, setState] = useState<{
    id?: string;
    project?: ProjectResponse;
    error?: boolean;
  }>({});
  const [files, setFiles] = useState<number | null>(null);
  const [rag, setRag] = useState<RagFileStatusResponse | null>(null);
  const [sessions, setSessions] = useState<Conversation[] | null>(null);
  const [retry, setRetry] = useState(0);
  const [partialError, setPartialError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    setState({});
    setFiles(null);
    setRag(null);
    setSessions(null);
    setPartialError(false);
    if (!projectId) return;
    const load = async () => {
      try {
        const project = await projectApi.getProject(projectId);
        if (cancelled) return;
        setState({ id: projectId, project });
        const results = await Promise.allSettled([
          fileApi.listFiles(projectId),
          ragApi.getRagFileStatus(projectId),
          apiClient.get<Conversation[]>(
            `${import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:8888"}/chat/api/chat/conversations/${projectId}`,
            { params: { user_id: userId } },
          ),
        ]);
        if (cancelled) return;
        const [documents, knowledge, conversations] = results;
        if (documents.status === "fulfilled") setFiles(documents.value.length);
        if (knowledge.status === "fulfilled" && knowledge.value.success)
          setRag(knowledge.value);
        const validConversations =
          conversations.status === "fulfilled" &&
          Array.isArray(conversations.value.data);
        if (validConversations) setSessions(conversations.value.data);
        setPartialError(
          !validConversations ||
            results.some((result) => result.status === "rejected") ||
            (knowledge.status === "fulfilled" && !knowledge.value.success),
        );
      } catch {
        if (!cancelled) setState({ id: projectId, error: true });
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId, retry, userId]);
  const base = `/project/${projectId}`;
  const statuses = Object.values(rag?.statuses || {});
  const indexed = rag
    ? statuses.filter((row) => row.status === "processed").length
    : null;
  const processing = statuses.filter((row) =>
    ["pending", "processing"].includes(row.status),
  ).length;
  const failed = statuses.filter((row) => row.status === "failed").length;
  const actions = [
    {
      path: "documents",
      icon: FileText,
      title: zh ? "文档库" : "Documents",
      count: files,
      description: zh
        ? "上传、预览 OCR 结果，下载处理后的文件。"
        : "Upload, preview OCR results and download processed files.",
      action: zh ? "上传文档" : "Upload documents",
    },
    {
      path: "rag",
      icon: Network,
      title: zh ? "知识库" : "Knowledge base",
      count: indexed,
      description: zh
        ? "批量导入文档，查看知识图谱，管理索引。"
        : "Import documents in batches, explore the graph and manage indexes.",
      action: zh ? "导入知识库" : "Import to knowledge base",
    },
    {
      path: "chat",
      icon: MessageSquare,
      title: zh ? "项目对话" : "Conversations",
      count: sessions?.length ?? null,
      description: zh
        ? "围绕项目资料提问，继续之前的完整会话。"
        : "Ask questions about your sources and continue saved conversations.",
      action: zh ? "开始对话" : "Start a conversation",
    },
  ];
  return (
    <div className="h-full overflow-y-auto p-5 md:p-8 text-foreground">
      {state.id !== projectId ? (
        <p role="status">{zh ? "正在加载项目…" : "Loading project…"}</p>
      ) : state.error ? (
        <div role="alert" className="rounded-xl border p-6">
          <h1 className="text-xl font-semibold">
            {zh ? "暂时无法打开项目" : "Unable to open project"}
          </h1>
          <p className="my-3">
            {zh
              ? "请检查连接或项目访问权限，然后重试。"
              : "Check your connection or project access, then retry."}
          </p>
          <button
            className="underline mr-6"
            onClick={() => setRetry((value) => value + 1)}
          >
            {zh ? "重试" : "Retry"}
          </button>
          <Link className="underline" to="/app/projects">
            {zh ? "返回项目列表" : "All projects"}
          </Link>
        </div>
      ) : (
        <div className="mx-auto max-w-6xl space-y-7">
          <header>
            <p className="text-sm text-muted-foreground">
              {zh ? "项目总览" : "Project overview"}
            </p>
            <h1 className="mt-2 text-3xl font-semibold break-words">
              {state.project?.name}
            </h1>
            <p className="mt-3 text-muted-foreground">
              {state.project?.description ||
                (zh
                  ? "集中管理资料、构建知识库，并与项目内容对话。"
                  : "Keep your sources, knowledge base and conversations together.")}
            </p>
          </header>
          {partialError && (
            <p role="alert" className="rounded-lg border p-3">
              {zh
                ? "部分统计暂不可用，仍可进入各功能查看。"
                : "Some statistics are unavailable. You can still open each workspace."}{" "}
              <button
                className="underline"
                onClick={() => setRetry((value) => value + 1)}
              >
                {zh ? "重试" : "Retry"}
              </button>
            </p>
          )}
          {files === 0 && (
            <section className="rounded-xl border border-blue-200 bg-blue-50 p-5 dark:bg-slate-900 dark:border-slate-700">
              <h2 className="font-semibold text-lg">
                {zh ? "从第一份文档开始" : "Start with your first document"}
              </h2>
              <p className="mt-2 text-muted-foreground">
                {zh
                  ? "1. 上传文档 → 2. 导入知识库 → 3. 开始提问。也可以直接进行普通对话。"
                  : "1. Upload documents → 2. Import to the knowledge base → 3. Ask questions. You can also start a regular chat right away."}
              </p>
            </section>
          )}
          <div className="grid gap-4 md:grid-cols-3">
            {actions.map(
              ({ path, icon: Icon, title, count, description, action }) => (
                <section
                  key={path}
                  className="rounded-xl border bg-card p-5 flex flex-col"
                >
                  <Icon className="h-6 w-6 text-blue-500" />
                  <h2 className="mt-4 font-semibold text-lg">{title}</h2>
                  <p className="my-3 text-3xl font-semibold">{count ?? "—"}</p>
                  <p className="text-sm text-muted-foreground flex-1">
                    {description}
                  </p>
                  <Link
                    to={`${base}/${path}`}
                    className="mt-6 inline-flex items-center gap-2 text-blue-600 dark:text-blue-400 font-medium"
                  >
                    {action}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </section>
              ),
            )}
          </div>
          <section className="rounded-xl border p-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-semibold">
                {zh ? "处理状态" : "Processing status"}
              </h2>
              <button
                className="text-sm underline"
                onClick={() => setRetry((value) => value + 1)}
              >
                {zh ? "刷新状态" : "Refresh status"}
              </button>
            </div>
            <p className="my-3 text-sm text-muted-foreground">
              {rag
                ? zh
                  ? `待处理 / 处理中 ${processing} · 导入失败 ${failed}`
                  : `Queued / processing ${processing} · Failed ${failed}`
                : zh
                  ? "等待知识库状态"
                  : "Knowledge base status unavailable"}
            </p>
            <ImportProgress
              progress={rag?.progress}
              language={currentLanguage}
            />
            <Link to={`${base}/rag`} className="text-sm underline">
              {zh ? "查看实时导入进度" : "View live import progress"}
            </Link>
          </section>
          <section className="rounded-xl border p-5">
            <h2 className="font-semibold mb-3">
              {zh ? "最近会话" : "Recent conversations"}
            </h2>
            {sessions === null ? (
              <p className="text-muted-foreground text-sm">
                {zh ? "会话暂不可用" : "Conversations unavailable"}
              </p>
            ) : sessions.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                {zh
                  ? "还没有会话。开始提问后，会话会保存在这个项目中。"
                  : "No conversations yet. Your chats will be saved in this project."}
              </p>
            ) : (
              <ul className="divide-y">
                {sessions.slice(0, 5).map((session) => (
                  <li key={session.id}>
                    <Link
                      className="block py-3 hover:underline break-words"
                      to={`${base}/chat?conversation=${encodeURIComponent(session.id)}`}
                    >
                      {session.title ||
                        (zh ? "未命名会话" : "Untitled conversation")}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
