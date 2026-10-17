// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import ProjectOverview from "../../src/features/project/ProjectOverview";
import { projectApi } from "../../src/api/project";
vi.mock("../../src/api/project", () => ({
  projectApi: { getProject: vi.fn() },
}));
vi.mock("../../src/api/file", () => ({
  fileApi: { listFiles: vi.fn().mockResolvedValue([]) },
}));
vi.mock("../../src/api/rag", () => ({
  ragApi: {
    getRagFileStatus: vi
      .fn()
      .mockResolvedValue({ success: true, statuses: {} }),
  },
}));
vi.mock("../../src/api/client", () => ({
  apiClient: { get: vi.fn().mockResolvedValue({ data: [] }) },
}));
vi.mock("../../src/context/LanguageContext", () => ({
  useLanguage: () => ({ currentLanguage: "en-US" }),
}));
vi.mock("../../src/context/AuthContext", () => ({
  useAuth: () => ({ user: { id: "test-user" } }),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
const mount = () =>
  render(
    <MemoryRouter initialEntries={["/project/one"]}>
      <Routes>
        <Route path="/project/:projectId" element={<ProjectOverview />} />
      </Routes>
    </MemoryRouter>,
  );
it("offers a usable empty project with correctly scoped actions", async () => {
  vi.mocked(projectApi.getProject).mockResolvedValue({
    id: "one",
    name: "New project",
  } as Awaited<ReturnType<typeof projectApi.getProject>>);
  mount();
  await screen.findByText("Start with your first document");
  expect(
    screen.getByRole("link", { name: "Upload documents" }).getAttribute("href"),
  ).toBe("/project/one/documents");
  expect(
    screen
      .getByRole("link", { name: "Start a conversation" })
      .getAttribute("href"),
  ).toBe("/project/one/chat");
});
it("keeps a visible error and supports retry instead of redirecting", async () => {
  vi.mocked(projectApi.getProject)
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({ id: "one", name: "Recovered" } as Awaited<
      ReturnType<typeof projectApi.getProject>
    >);
  mount();
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await screen.findByText("Recovered");
});
it("does not mistake failed statistics for an empty project", async () => {
  const { fileApi } = await import("../../src/api/file");
  vi.mocked(fileApi.listFiles).mockRejectedValueOnce(new Error("offline"));
  vi.mocked(projectApi.getProject).mockResolvedValue({
    id: "one",
    name: "Existing",
  } as Awaited<ReturnType<typeof projectApi.getProject>>);
  mount();
  await screen.findByRole("alert");
  expect(screen.queryByText("Start with your first document")).toBeNull();
  expect(
    screen.getByRole("link", { name: "Import to knowledge base" }),
  ).toBeTruthy();
});
it("handles a non-array conversation response without crashing the whole route", async () => {
  const { apiClient } = await import("../../src/api/client");
  vi.mocked(apiClient.get).mockResolvedValueOnce({
    data: { error: true, htmlResponse: true },
  });
  vi.mocked(projectApi.getProject).mockResolvedValue({
    id: "one",
    name: "Available project",
  } as Awaited<ReturnType<typeof projectApi.getProject>>);
  mount();
  await screen.findByRole("alert");
  expect(screen.getByText("Available project")).toBeTruthy();
  expect(screen.getByText("Conversations unavailable")).toBeTruthy();
});
