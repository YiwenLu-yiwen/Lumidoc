import {
  Activity,
  Cpu,
  RotateCw,
  Server,
  CircleCheck,
  CircleAlert,
} from "lucide-react";
import { adminLabel, serviceLabels, type ServiceStatus } from "./adminLabels";

export function ServiceStatusPanel({
  status,
  zh,
  busy,
  restarting,
  onRestart,
}: {
  status: ServiceStatus;
  zh: boolean;
  busy: boolean;
  restarting: string | null;
  onRestart: (name: string) => void;
}) {
  const healthy = status.services.filter(
    (service) => service.status === "healthy",
  ).length;
  const problems = status.services.filter(
    (service) =>
      status.controls?.recovery?.[service.name]?.phase === "needs_attention" ||
      (!status.controls?.recovery?.[service.name]?.phase &&
        service.status !== "healthy"),
  ).length;
  const metrics = [
    {
      label: zh ? "正常服务" : "Healthy services",
      value: `${healthy} / ${status.services.length}`,
      icon: Server,
    },
    {
      label: zh ? "需要关注" : "Needs attention",
      value: problems,
      icon: Activity,
    },
    {
      label: zh ? "已加载模型" : "Loaded models",
      value: status.models?.length ?? "—",
      icon: Cpu,
    },
  ];
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        {metrics.map(({ label, value, icon: Icon }) => (
          <div key={label} className="rounded-xl border bg-card p-5">
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              {label}
              <Icon className="h-4 w-4" />
            </div>
            <p className="mt-3 text-3xl font-semibold tabular-nums">{value}</p>
          </div>
        ))}
      </div>
      <section className="overflow-hidden rounded-xl border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b px-5 py-4">
          <h2 className="font-semibold">
            {zh ? "服务运行状态" : "Service health"}
          </h2>
          <p className="text-xs text-muted-foreground">
            {zh ? "检查时间" : "Checked"} ·{" "}
            {new Date(status.checked_at).toLocaleTimeString(
              zh ? "zh-CN" : "en-US",
            )}
          </p>
        </div>
        <div className="divide-y">
          {status.services.map((service) => {
            const recovery = status.controls?.recovery?.[service.name];
            const recovering = recovery?.phase === "recovering";
            const ok = service.status === "healthy";
            const op = status.controls?.operations[service.name];
            const pending =
              restarting === service.name || op?.status === "restarting";
            const cooling = Boolean(
              op && Date.now() - Date.parse(op.started_at) < 60000,
            );
            const allowed =
              status.controls?.available &&
              status.controls.services.includes(service.name);
            const Icon = ok ? CircleCheck : CircleAlert;
            return (
              <div
                key={service.name}
                className="flex flex-wrap items-center gap-3 px-5 py-4"
              >
                <div
                  className={`rounded-lg p-2 ${ok ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400" : "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-400"}`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1 basis-32">
                  <h3 className="text-sm font-medium">
                    {serviceLabels[service.name]?.[zh ? 0 : 1] || service.name}
                  </h3>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {service.name}
                  </p>
                </div>
                <div className="text-right">
                  <p
                    className={`text-xs font-medium ${ok ? "text-emerald-700 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400"}`}
                  >
                    {adminLabel(
                      recovery?.phase === "needs_attention"
                        ? "needs_attention"
                        : recovering
                          ? "recovering"
                          : service.status,
                      zh,
                    )}
                  </p>
                  <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                    {service.latency_ms !== null
                      ? `${service.latency_ms} ms`
                      : "—"}
                  </p>
                </div>
                <button
                  aria-label={`${zh ? "重启" : "Restart"} ${serviceLabels[service.name]?.[zh ? 0 : 1] || service.name}`}
                  disabled={!allowed || busy || pending || cooling}
                  title={
                    !allowed
                      ? zh
                        ? "控制服务不可用"
                        : "Container control unavailable"
                      : cooling
                        ? zh
                          ? "重启后需间隔 60 秒"
                          : "60-second restart cooldown"
                        : undefined
                  }
                  onClick={() => onRestart(service.name)}
                  className="ml-1 inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <RotateCw
                    className={`h-3.5 w-3.5 ${pending ? "animate-spin" : ""}`}
                  />
                  {pending
                    ? zh
                      ? "重启中"
                      : "Restarting"
                    : zh
                      ? "重启"
                      : "Restart"}
                </button>
                {recovering && (
                  <p className="w-full pl-11 text-xs text-blue-600 dark:text-blue-400">
                    {zh
                      ? `正在恢复服务，近期自动重启 ${recovery?.restart_count || 0} 次。`
                      : `Recovering service; ${recovery?.restart_count || 0} recent automatic restarts.`}
                  </p>
                )}
                {op && (
                  <p className="w-full pl-11 text-xs text-muted-foreground">
                    {zh ? "最近操作" : "Last action"}:{" "}
                    {adminLabel(op.status, zh)} ·{" "}
                    {new Date(
                      op.finished_at || op.started_at,
                    ).toLocaleTimeString(zh ? "zh-CN" : "en-US")}
                  </p>
                )}
              </div>
            );
          })}
        </div>
        <p className="border-t px-5 py-3 text-xs leading-relaxed text-muted-foreground">
          {status.controls?.available
            ? zh
              ? "重启会中断该服务正在处理的请求。重启命令完成后，以健康检查结果确认恢复。"
              : "Restarting interrupts active requests. Health checks confirm recovery after the restart command finishes."
            : zh
              ? "重启控制服务未连接，当前仅展示监控数据。"
              : "Restart control is disconnected. Monitoring remains available."}
        </p>
      </section>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border bg-card p-5">
          <h2 className="flex items-center gap-2 font-semibold">
            <Activity className="h-4 w-4 text-blue-500" />
            {zh ? "运行环境资源" : "Runtime resources"}
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {zh
              ? "监控进程可见的容器 / 虚拟机资源，不代表宿主机总量。"
              : "Container / VM resources visible to monitoring, not host totals."}
          </p>
          {[
            ["CPU", status.resources.cpu_percent],
            [zh ? "内存" : "Memory", status.resources.memory_percent],
          ].map(([label, value]) => (
            <div key={label} className="mt-5">
              <div className="mb-2 flex justify-between text-sm">
                <span>{label}</span>
                <span className="tabular-nums">{value}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-blue-500"
                  style={{
                    width: `${Math.max(0, Math.min(100, Number(value)))}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </section>
        <section className="rounded-xl border bg-card p-5">
          <h2 className="flex items-center gap-2 font-semibold">
            <Cpu className="h-4 w-4 text-blue-500" />
            {zh ? "Ollama 当前加载模型" : "Models currently loaded in Ollama"}
          </h2>
          {status.models === null ? (
            <p className="mt-5 text-sm text-muted-foreground">
              {zh ? "运行信息不可用" : "Runtime information unavailable"}
            </p>
          ) : !status.models.length ? (
            <p className="mt-5 text-sm text-muted-foreground">
              {zh ? "当前没有已加载模型" : "No models currently loaded"}
            </p>
          ) : (
            status.models.map((model) => (
              <div key={model.name} className="mt-4 rounded-lg bg-muted/50 p-3">
                <p className="break-all text-sm font-medium">{model.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {model.size_vram > 0
                    ? zh
                      ? "GPU 加速 / 部分卸载"
                      : "GPU / offload"
                    : "CPU"}{" "}
                  · {zh ? "显存" : "VRAM"}{" "}
                  {(model.size_vram / 1024 ** 3).toFixed(2)} GiB
                </p>
              </div>
            ))
          )}
        </section>
      </div>
    </div>
  );
}
