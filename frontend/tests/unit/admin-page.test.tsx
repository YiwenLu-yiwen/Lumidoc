// @vitest-environment jsdom
import {
  cleanup,
  render,
  screen,
  fireEvent,
  act,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import AdminPage from "../../src/features/admin/AdminPage";
import { apiClient } from "../../src/api/client";
const identity = vi.hoisted(() => ({
  user: { id: "1", role: "user" },
  language: "en-US",
}));
vi.mock("../../src/context/AuthContext", () => ({ useAuth: () => identity }));
vi.mock("../../src/context/LanguageContext", () => ({
  useLanguage: () => ({ currentLanguage: identity.language }),
}));
vi.mock("../../src/api/client", () => ({
  apiClient: { get: vi.fn(), patch: vi.fn(), post: vi.fn() },
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  identity.user.role = "user";
  identity.language = "en-US";
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
it("does not request privileged data for an ordinary user", () => {
  render(<AdminPage />);
  expect(screen.getByRole("alert").textContent).toContain(
    "Administrator access required",
  );
  expect(apiClient.get).not.toHaveBeenCalled();
});
it("shows service failure honestly and allows retry", async () => {
  identity.user.role = "admin";
  vi.mocked(apiClient.get)
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({
      data: {
        services: [],
        models: null,
        resources: { cpu_percent: 0, memory_percent: 0 },
        checked_at: "2026-10-18T00:00:00Z",
      },
    });
  render(<AdminPage />);
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
  await screen.findByText("Runtime information unavailable");
});

const snapshot = {
  services: [{ name: "chat", status: "unreachable", latency_ms: null }],
  models: [],
  resources: { scope: "container", cpu_percent: 1, memory_percent: 2 },
  checked_at: "2026-10-18T00:00:00Z",
  controls: { available: true, services: ["chat"], operations: {} },
};
it("polls real status every ten seconds and stops polling on unmount", async () => {
  vi.useFakeTimers();
  identity.user.role = "admin";
  vi.mocked(apiClient.get).mockResolvedValue({ data: snapshot });
  const view = render(<AdminPage />);
  await act(async () => {});
  expect(apiClient.get).toHaveBeenCalledTimes(1);
  await act(async () => vi.advanceTimersByTimeAsync(10000));
  expect(apiClient.get).toHaveBeenCalledTimes(2);
  view.unmount();
  await act(async () => vi.advanceTimersByTimeAsync(20000));
  expect(apiClient.get).toHaveBeenCalledTimes(2);
});
it("localizes health and submits a confirmed restart for the selected service", async () => {
  identity.user.role = "admin";
  identity.language = "zh-CN";
  vi.mocked(apiClient.get).mockResolvedValue({ data: snapshot });
  vi.mocked(apiClient.post).mockResolvedValue({ data: { accepted: true } });
  vi.stubGlobal(
    "confirm",
    vi.fn(() => true),
  );
  render(<AdminPage />);
  await screen.findByText("无法连接");
  fireEvent.click(screen.getByRole("button", { name: "重启 对话服务" }));
  await screen.findByText("重启请求已接受，状态将在自动检查后更新。");
  expect(apiClient.post).toHaveBeenCalledWith(
    expect.stringContaining("/monitoring/admin/services/chat/restart"),
  );
});
