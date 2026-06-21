import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import ProjectsPage from "./Projects";

const {
  fetchProjectsMock,
  fetchTaskTemplatesMock,
  createProjectMock,
  createTaskTemplateMock,
  createDailyTaskMock,
} = vi.hoisted(() => ({
  fetchProjectsMock: vi.fn(),
  fetchTaskTemplatesMock: vi.fn(),
  createProjectMock: vi.fn(),
  createTaskTemplateMock: vi.fn(),
  createDailyTaskMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  fetchProjects: fetchProjectsMock,
  fetchTaskTemplates: fetchTaskTemplatesMock,
  createProject: createProjectMock,
  createTaskTemplate: createTaskTemplateMock,
  createDailyTask: createDailyTaskMock,
  getErrorMessage: (error, fallback) => error?.message || fallback,
}));

beforeEach(() => {
  vi.clearAllMocks();
  fetchProjectsMock.mockResolvedValue([
    { id: 1, name: "健身", status: "active", sort_order: 0 },
  ]);
  fetchTaskTemplatesMock.mockResolvedValue([
    {
      id: 1,
      project_id: 1,
      name: "跑步 30 分钟",
      default_estimated_duration_minutes: 30,
      default_reward_amount: 2000,
      notes: "",
      is_active: true,
    },
  ]);
  createProjectMock.mockResolvedValue({
    id: 2,
    name: "写作",
    status: "active",
    sort_order: 1,
  });
  createTaskTemplateMock.mockResolvedValue({
    id: 2,
    project_id: 1,
    name: "力量训练 20 分钟",
    default_estimated_duration_minutes: 20,
    default_reward_amount: 1200,
    notes: "",
    is_active: true,
  });
  createDailyTaskMock.mockResolvedValue({ id: 10 });
});

test("renders template list", async () => {
  render(<ProjectsPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();
});

test("creates a project", async () => {
  render(<ProjectsPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText("例如：写作"), {
    target: { value: "写作" },
  });
  fireEvent.click(screen.getByRole("button", { name: "创建项目" }));

  await waitFor(() => {
    expect(createProjectMock).toHaveBeenCalledWith("写作");
  });
});
