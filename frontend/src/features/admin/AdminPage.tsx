import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { apiClient } from "@/api/client";

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
type Status = {
  services: { name: string; status: string; latency_ms: number | null }[];
  models: { name: string; size: number; size_vram: number }[] | null;
  resources: { scope: string; cpu_percent: number; memory_percent: number };
  checked_at: string;
};
const gateway = import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:8888";
export default function AdminPage() {
  const { user } = useAuth();
  const { currentLanguage } = useLanguage();
  const zh = currentLanguage === "zh-CN";
  const [tab, setTab] = useState("status");
  const [status, setStatus] = useState<Status | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const request = useCallback(async () => {
    if (user?.role !== "admin") return;
    setBusy(true);
    setError("");
    try {
      if (tab === "status") {
        const response = await apiClient.get<Status>(
          `${gateway}/monitoring/admin/status`,
        );
        setStatus(response.data);
      } else if (tab === "users") {
        const response = await apiClient.get<{
          users: Account[];
          total: number;
        }>("/api/auth/admin/users", { params: { offset, limit: 50 } });
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
      setError(
        zh
          ? "加载失败，请检查服务连接和管理员权限。"
          : "Unable to load. Check service connectivity and administrator access.",
      );
    } finally {
      setBusy(false);
    }
  }, [user?.role, tab, offset, zh]);
  useEffect(() => {
    void request();
  }, [request]);
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
    <div className="h-full overflow-y-auto p-5 md:p-8">
      <div className="mx-auto max-w-6xl space-y-5">
        <header className="flex justify-between items-center">
          <h1 className="text-2xl font-semibold">
            {zh ? "管理中心" : "Administration"}
          </h1>
          <button
            className="border rounded px-3 py-2"
            disabled={busy}
            onClick={() => void request()}
          >
            {busy ? (zh ? "加载中…" : "Loading…") : zh ? "刷新" : "Refresh"}
          </button>
        </header>
        <nav
          className="flex gap-2"
          aria-label={zh ? "管理功能" : "Admin sections"}
        >
          {[
            ["status", zh ? "服务状态" : "Service status"],
            ["tasks", zh ? "任务中心" : "Tasks"],
            ["users", zh ? "用户管理" : "Users"],
          ].map(([key, label]) => (
            <button
              key={key}
              aria-pressed={tab === key}
              onClick={() => {
                setTab(key);
                setError("");
              }}
              className={`rounded px-4 py-2 border ${tab === key ? "bg-blue-600 text-white" : ""}`}
            >
              {label}
            </button>
          ))}
        </nav>
        {error && (
          <p role="alert" className="border border-red-300 rounded p-3">
            {error}
          </p>
        )}
        {tab === "status" && status && (
          <>
            <p className="text-sm text-muted-foreground">
              {zh ? "检查时间" : "Checked"}:{" "}
              {new Date(status.checked_at).toLocaleString()}
            </p>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {status.services.map((service) => (
                <div className="border rounded-lg p-4" key={service.name}>
                  <h2 className="font-semibold">{service.name}</h2>
                  <p>
                    {service.status}{" "}
                    {service.latency_ms !== null
                      ? `· ${service.latency_ms} ms`
                      : ""}
                  </p>
                </div>
              ))}
            </div>
            <section className="border rounded-lg p-4">
              <h2 className="font-semibold">
                {zh
                  ? "监控容器资源（非宿主机总量）"
                  : "Monitoring container resources (not host totals)"}
              </h2>
              <p>
                CPU {status.resources.cpu_percent}% · {zh ? "内存" : "Memory"}{" "}
                {status.resources.memory_percent}%
              </p>
            </section>
            <section className="border rounded-lg p-4">
              <h2 className="font-semibold mb-2">
                {zh
                  ? "Ollama 当前加载模型"
                  : "Models currently loaded in Ollama"}
              </h2>
              {status.models === null ? (
                <p>
                  {zh ? "运行信息不可用" : "Runtime information unavailable"}
                </p>
              ) : status.models.length === 0 ? (
                <p>
                  {zh ? "当前没有已加载模型" : "No models currently loaded"}
                </p>
              ) : (
                status.models.map((model) => (
                  <p className="break-all" key={model.name}>
                    {model.name} ·{" "}
                    {model.size_vram > 0 ? "GPU / offload" : "CPU"} · VRAM{" "}
                    {(model.size_vram / 1024 ** 3).toFixed(2)} GiB
                  </p>
                ))
              )}
            </section>
          </>
        )}
        {tab === "tasks" && (
          <>
            <label className="block">
              {zh ? "筛选状态 / 类型" : "Filter status / type"}
              <input
                className="block border rounded px-3 py-2 mt-1 bg-background"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
            </label>
            <p className="text-sm text-muted-foreground">
              {zh
                ? "展示任务元数据，不包含文档正文。每个来源最多展示 200 条；旧导入记录可能没有项目编号。"
                : "Task metadata only; document contents are excluded. Up to 200 records per source; older imports may have no project ID."}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead>
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
                      <th className="p-2 border-b" key={text}>
                        {text}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tasks
                    .filter((task) =>
                      `${task.source} ${task.status} ${task.stage || ""} ${task.task_name || ""}`
                        .toLowerCase()
                        .includes(filter.toLowerCase()),
                    )
                    .map((task, index) => (
                      <tr
                        key={`${task.source}-${task.task_id || task.file_id}-${index}`}
                      >
                        <td className="p-2 border-b">
                          {task.source}
                          <br />
                          {task.task_name ||
                            task.task_id?.slice(0, 12) ||
                            task.file_id?.slice(0, 12)}
                        </td>
                        <td className="p-2 border-b">
                          {task.status}
                          <br />
                          {task.stage}
                        </td>
                        <td className="p-2 border-b">
                          {task.created_at
                            ? new Date(
                                /[zZ]|[+-]\d{2}:\d{2}$/.test(task.created_at)
                                  ? task.created_at
                                  : `${task.created_at}Z`,
                              ).toLocaleString()
                            : "—"}
                        </td>
                        <td className="p-2 border-b">
                          {task.duration_seconds ??
                            task.processing_time_seconds ??
                            "—"}{" "}
                          s
                        </td>
                        <td className="p-2 border-b">
                          {task.failure_reason || "—"}
                        </td>
                        <td className="p-2 border-b">
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
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead>
                  <tr>
                    {(zh
                      ? ["用户", "邮箱", "状态", "角色", "操作"]
                      : ["User", "Email", "Status", "Role", "Actions"]
                    ).map((text) => (
                      <th className="p-2 border-b" key={text}>
                        {text}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((account) => (
                    <tr key={account.id}>
                      <td className="p-2 border-b">{account.username}</td>
                      <td className="p-2 border-b">{account.email}</td>
                      <td className="p-2 border-b">
                        {account.is_active
                          ? zh
                            ? "启用"
                            : "Active"
                          : zh
                            ? "停用"
                            : "Disabled"}
                      </td>
                      <td className="p-2 border-b">
                        {account.is_superuser ? "Admin" : "User"}
                      </td>
                      <td className="p-2 border-b">
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
                {offset + 1}–{Math.min(offset + 50, total)} / {total}
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
