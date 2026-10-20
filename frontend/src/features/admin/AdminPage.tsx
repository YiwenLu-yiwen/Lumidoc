import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { apiClient } from "@/api/client";

import { RefreshCw, ShieldCheck } from "lucide-react";
import { ServiceStatusPanel } from "./ServiceStatusPanel";
import { adminLabel, serviceLabels, type ServiceStatus } from "./adminLabels";

type Account = {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
};
type Task = {
  task_id?: string;
  file_id?: string;
  project_id?: string;
  task_name?: string;
  status: string;
  stage?: string;
  created_at?: string;
  duration_seconds?: number;
  processing_time_seconds?: number;
  failure_reason?: string;
  source: string;
};
const gateway = import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:8888";
export default function AdminPage() {
  const { user } = useAuth();
  const { currentLanguage } = useLanguage();
  const zh = currentLanguage === "zh-CN";
  const [events, setEvents] = useState<
    {
      id: number;
      timestamp: number;
      actor: string;
      action: string;
      target: string;
      outcome: string;
      operation_id: string;
    }[]
  >([]);
  const [before, setBefore] = useState<number | undefined>();
  const [tab, setTab] = useState("status");
  const [status, setStatus] = useState<ServiceStatus | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [restarting, setRestarting] = useState<string | null>(null);
  const requestId = useRef(0);
  const fetching = useRef(false);
  const request = useCallback(async () => {
    const id = ++requestId.current;
    fetching.current = true;
    if (user?.role !== "admin") {
      fetching.current = false;
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (tab === "status") {
        const response = await apiClient.get<ServiceStatus>(
          `${gateway}/monitoring/admin/status`,
        );
        if (id !== requestId.current) return;
        setStatus(response.data);
      } else if (tab === "events") {
        const response = await apiClient.get<{ events: typeof events }>(
          `${gateway}/monitoring/admin/events`,
          { params: { before } },
        );
        if (id !== requestId.current) return;
        setEvents(response.data.events);
      } else if (tab === "users") {
        const response = await apiClient.get<{
          users: Account[];
          total: number;
        }>("/api/auth/admin/users", { params: { offset, limit: 50 } });
        if (id !== requestId.current) return;
        setAccounts(response.data.users);
        setTotal(response.data.total);
      } else {
        const sources = [
          ["System", `${gateway}/monitoring/admin/tasks`],
          ["OCR", `${gateway}/fileproc/admin/tasks`],
          ["LightRAG", `${gateway}/api/lightrag/rag/admin/tasks`],
        ];
        const results = await Promise.allSettled(
          sources.map(async ([source, url]) => {
            const response = await apiClient.get<{ tasks: Task[] }>(url);
            return response.data.tasks.map((task) => ({ ...task, source }));
          }),
        );
        if (id !== requestId.current) return;
        setTasks(
          results.flatMap((result) =>
            result.status === "fulfilled" ? result.value : [],
          ),
        );
        if (results.some((result) => result.status === "rejected"))
          setError(
            zh
              ? "部分任务服务不可用；已显示可用结果。"
              : "Some task services are unavailable; available results are shown.",
          );
      }
    } catch {
      if (id !== requestId.current) return;
      setError(
        zh
          ? "加载失败，请检查服务连接和管理员权限。"
          : "Unable to load. Check service connectivity and administrator access.",
      );
    } finally {
      if (id === requestId.current) {
        setBusy(false);
        fetching.current = false;
      }
    }
  }, [user?.role, tab, offset, before, zh]);
  useEffect(() => {
    void request();
    const timer = window.setInterval(() => {
      if (!document.hidden && !fetching.current) void request();
    }, 10000);
    return () => {
      window.clearInterval(timer);
      requestId.current += 1;
    };
  }, [request]);
  async function restartService(name: string) {
    const label = serviceLabels[name]?.[zh ? 0 : 1] || name;
    if (
      !confirm(
        zh
          ? `重启「${label}」？该服务正在处理的请求会中断。`
          : `Restart ${label}? Active requests to this service will be interrupted.`,
      )
    )
      return;
    setRestarting(name);
    setError("");
    setNotice("");
    try {
      await apiClient.post(
        `${gateway}/monitoring/admin/services/${encodeURIComponent(name)}/restart`,
      );
      setNotice(
        zh
          ? "重启请求已接受，状态将在自动检查后更新。"
          : "Restart accepted. Automatic health checks will update the status.",
      );
      await request();
    } catch {
      setError(
        zh
          ? "重启未确认，请查看最新状态。服务可能处于 60 秒冷却期，或控制服务不可用。"
          : "Restart was not confirmed. Check current status; a 60-second cooldown or unavailable controller may prevent restarting.",
      );
    } finally {
      setRestarting(null);
    }
  }
  async function changeAccount(
    account: Account,
    field: "is_active" | "is_superuser",
  ) {
    if (
      !confirm(
        zh
          ? `确认修改用户 ${account.username} 的${field === "is_active" ? "启用状态" : "管理员权限"}？`
          : `Change ${field === "is_active" ? "active status" : "administrator privileges"} for ${account.username}?`,
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await apiClient.patch(`/api/auth/admin/users/${account.id}`, {
        is_active: account.is_active,
        is_superuser: account.is_superuser,
        [field]: !account[field],
      });
      await request();
    } catch {
      setError(
        zh
          ? "修改失败，用户状态未确认，请刷新。"
          : "Update failed. Refresh to confirm account status.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function retry(task: Task) {
    setBusy(true);
    setError("");
    try {
      await apiClient.post(
        `/api/lightrag/rag/admin/retry/${encodeURIComponent(task.project_id!)}/${encodeURIComponent(task.file_id!)}`,
      );
      await request();
    } catch {
      setError(
        zh
          ? "重试失败或任务状态已改变。"
          : "Retry failed or the task status has changed.",
      );
    } finally {
      setBusy(false);
    }
  }
  if (user?.role !== "admin")
    return (
      <div role="alert" className="p-8">
        {zh ? "此页面仅限管理员。" : "Administrator access required."}
      </div>
    );
  return (
    <div className="h-full overflow-y-auto bg-background p-5 text-foreground md:p-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="mb-2 flex items-center gap-2 text-sm text-muted-foreground">
              <ShieldCheck className="h-4 w-4 text-blue-500" />
              {zh ? "系统管理" : "System administration"}
            </p>
            <h1 className="text-3xl font-semibold">
              {zh ? "管理中心" : "Administration"}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {zh
                ? "服务健康、处理任务与账户权限，集中管理。"
                : "Service health, processing tasks and account access in one place."}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground">
              {zh ? "每 10 秒自动刷新" : "Auto-refresh every 10s"}
            </span>
            <button
              className="inline-flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm hover:bg-muted disabled:opacity-50"
              disabled={busy}
              onClick={() => void request()}
            >
              <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />
              {zh ? "刷新" : "Refresh"}
            </button>
          </div>
        </header>
        <nav
          className="flex gap-1 overflow-x-auto border-b"
          aria-label={zh ? "管理功能" : "Admin sections"}
        >
          {[
            ["status", zh ? "服务状态" : "Service status"],
            ["tasks", zh ? "任务中心" : "Tasks"],
            ["users", zh ? "用户管理" : "Users"],
            ["events", zh ? "操作记录" : "Activity log"],
          ].map(([key, label]) => (
            <button
              key={key}
              aria-pressed={tab === key}
              onClick={() => {
                setTab(key);
                setError("");
              }}
              className={`border-b-2 px-4 py-3 text-sm font-medium transition-colors ${tab === key ? "border-blue-500 text-blue-600 dark:text-blue-400" : "border-transparent text-muted-foreground hover:text-foreground"}`}
            >
              {label}
            </button>
          ))}
        </nav>
        {error && (
          <p
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:border-red-900 dark:text-red-300"
          >
            {error}
          </p>
        )}
        {notice && (
          <p
            role="status"
            className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-700 dark:bg-slate-900 dark:text-blue-300 dark:border-slate-700"
          >
            {notice}
          </p>
        )}
        {tab === "status" && !status && busy && (
          <div
            role="status"
            className="rounded-xl border bg-card p-8 text-muted-foreground"
          >
            {zh ? "正在检查服务…" : "Checking services…"}
          </div>
        )}
        {tab === "status" && status && (
          <ServiceStatusPanel
            status={status}
            zh={zh}
            busy={busy}
            restarting={restarting}
            onRestart={(name) => void restartService(name)}
          />
        )}
        {tab === "events" && (
          <section className="rounded-xl border bg-card overflow-hidden">
            <div className="p-4 text-sm text-muted-foreground">
              {zh
                ? "记录请求、中断、自动恢复与管理员操作；不记录密码、令牌或请求正文。"
                : "Requests, interruptions, recovery and administrator actions. Credentials and request bodies are excluded."}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    {(zh
                      ? ["时间", "操作人", "操作", "对象", "结果"]
                      : ["Time", "Actor", "Action", "Target", "Outcome"]
                    ).map((label) => (
                      <th className="px-4 py-3" key={label}>
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {events.map((event) => (
                    <tr key={event.id} className="border-t">
                      <td className="px-4 py-3 whitespace-nowrap">
                        {new Date(event.timestamp * 1000).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        {adminLabel(event.actor, zh)}
                      </td>
                      <td className="px-4 py-3">
                        {adminLabel(event.action, zh)}
                      </td>
                      <td className="px-4 py-3 max-w-xs break-all">
                        {event.target}
                      </td>
                      <td className="px-4 py-3">
                        {adminLabel(event.outcome, zh)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-between border-t p-4 text-sm">
              <button
                disabled={busy || !before}
                onClick={() => setBefore(undefined)}
              >
                {zh ? "最新记录" : "Latest"}
              </button>
              <button
                disabled={busy || events.length < 100}
                onClick={() => setBefore(events[events.length - 1]?.id)}
              >
                {zh ? "更早记录" : "Earlier"}
              </button>
            </div>
          </section>
        )}
        {tab === "tasks" && (
          <>
            <label className="block">
              {zh ? "筛选状态 / 类型" : "Filter status / type"}
              <input
                className="mt-2 block w-full rounded-lg border bg-card px-3 py-2 text-sm sm:max-w-sm"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
            </label>
            <p className="text-sm text-muted-foreground">
              {zh
                ? "展示任务元数据，不包含文档正文。每个来源最多展示 200 条；旧导入记录可能没有项目编号。"
                : "Task metadata only; document contents are excluded. Up to 200 records per source; older imports may have no project ID."}
            </p>
            <div className="overflow-x-auto rounded-xl border bg-card">
              <table className="w-full text-sm text-left">
                <thead className="bg-muted/50 text-xs text-muted-foreground">
                  <tr>
                    {(zh
                      ? [
                          "来源 / 任务",
                          "状态 / 阶段",
                          "时间",
                          "耗时",
                          "错误类别",
                          "操作",
                        ]
                      : [
                          "Source / task",
                          "Status / stage",
                          "Created",
                          "Duration",
                          "Failure category",
                          "Action",
                        ]
                    ).map((text) => (
                      <th className="border-b px-4 py-3" key={text}>
                        {text}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tasks
                    .filter((task) =>
                      `${task.source} ${adminLabel(task.source, zh)} ${adminLabel(task.status, zh)} ${adminLabel(task.stage, zh)} ${task.status} ${task.stage || ""} ${task.task_name || ""}`
                        .toLowerCase()
                        .includes(filter.toLowerCase()),
                    )
                    .map((task, index) => (
                      <tr
                        key={`${task.source}-${task.task_id || task.file_id}-${index}`}
                      >
                        <td className="border-b px-4 py-3">
                          {adminLabel(task.source, zh)}
                          <br />
                          {task.task_name ||
                            task.task_id?.slice(0, 12) ||
                            task.file_id?.slice(0, 12)}
                        </td>
                        <td className="border-b px-4 py-3">
                          {adminLabel(task.status, zh)}
                          <br />
                          {adminLabel(task.stage, zh)}
                        </td>
                        <td className="border-b px-4 py-3">
                          {task.created_at
                            ? new Date(
                                /[zZ]|[+-]\d{2}:\d{2}$/.test(task.created_at)
                                  ? task.created_at
                                  : `${task.created_at}Z`,
                              ).toLocaleString()
                            : "—"}
                        </td>
                        <td className="border-b px-4 py-3">
                          {task.duration_seconds ??
                            task.processing_time_seconds ??
                            "—"}{" "}
                          s
                        </td>
                        <td className="border-b px-4 py-3">
                          {adminLabel(task.failure_reason, zh)}
                        </td>
                        <td className="border-b px-4 py-3">
                          {task.source === "LightRAG" &&
                            task.status === "failed" &&
                            task.project_id && (
                              <button
                                className="underline"
                                disabled={busy}
                                onClick={() => void retry(task)}
                              >
                                {zh ? "重试" : "Retry"}
                              </button>
                            )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
              {!busy && tasks.length === 0 && (
                <p className="py-4">
                  {zh ? "暂无任务记录" : "No task records"}
                </p>
              )}
            </div>
          </>
        )}
        {tab === "users" && (
          <>
            <div className="overflow-x-auto rounded-xl border bg-card">
              <table className="w-full text-sm text-left">
                <thead className="bg-muted/50 text-xs text-muted-foreground">
                  <tr>
                    {(zh
                      ? ["用户", "邮箱", "状态", "角色", "操作"]
                      : ["User", "Email", "Status", "Role", "Actions"]
                    ).map((text) => (
                      <th className="border-b px-4 py-3" key={text}>
                        {text}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((account) => (
                    <tr key={account.id}>
                      <td className="border-b px-4 py-3">{account.username}</td>
                      <td className="border-b px-4 py-3">{account.email}</td>
                      <td className="border-b px-4 py-3">
                        {account.is_active
                          ? zh
                            ? "启用"
                            : "Active"
                          : zh
                            ? "停用"
                            : "Disabled"}
                      </td>
                      <td className="border-b px-4 py-3">
                        {account.is_superuser
                          ? zh
                            ? "管理员"
                            : "Admin"
                          : zh
                            ? "普通用户"
                            : "User"}
                      </td>
                      <td className="border-b px-4 py-3">
                        <button
                          disabled={busy || String(account.id) === user.id}
                          className="underline mr-3 disabled:opacity-40"
                          onClick={() =>
                            void changeAccount(account, "is_active")
                          }
                        >
                          {account.is_active
                            ? zh
                              ? "停用"
                              : "Disable"
                            : zh
                              ? "启用"
                              : "Enable"}
                        </button>
                        <button
                          disabled={busy || String(account.id) === user.id}
                          className="underline disabled:opacity-40"
                          onClick={() =>
                            void changeAccount(account, "is_superuser")
                          }
                        >
                          {account.is_superuser
                            ? zh
                              ? "撤销管理员"
                              : "Remove admin"
                            : zh
                              ? "设为管理员"
                              : "Make admin"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex gap-4">
              <button
                disabled={busy || offset === 0}
                onClick={() => setOffset(Math.max(0, offset - 50))}
              >
                {zh ? "上一页" : "Previous"}
              </button>
              <span>
                {total ? offset + 1 : 0}–{Math.min(offset + 50, total)} /{" "}
                {total}
              </span>
              <button
                disabled={busy || offset + 50 >= total}
                onClick={() => setOffset(offset + 50)}
              >
                {zh ? "下一页" : "Next"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
