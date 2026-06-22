import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import ProjectsPage from "./Projects";

const activeProject = { id: 1, name: "健身", status: "active", sort_order: 0 };
const nextActiveProject = { id: 2, name: "写作", status: "active", sort_order: 1 };
const archivedProject = { id: 3, name: "阅读", status: "archived", sort_order: 2 };

const activeTemplate = {
  id: 1,
  project_id: 1,
  name: "跑步 30 分钟",
  default_estimated_duration_minutes: 30,
  default_reward_amount: 2000,
  notes: "",
  is_active: true,
};

const archivedTemplate = {
  id: 2,
  project_id: 1,
  name: "拉伸 10 分钟",
  default_estimated_duration_minutes: 10,
  default_reward_amount: 600,
  notes: "",
  is_active: false,
};

const nextProjectTemplate = {
  id: 3,
  project_id: 2,
  name: "晨间随笔 15 分钟",
  default_estimated_duration_minutes: 15,
  default_reward_amount: 900,
  notes: "",
  is_active: true,
};

const archivedProjectTemplate = {
  id: 4,
  project_id: 3,
  name: "归档项目模板",
  default_estimated_duration_minutes: 25,
  default_reward_amount: 1000,
  notes: "",
  is_active: true,
};

const {
  fetchProjectsMock,
  fetchTaskTemplatesMock,
  createProjectMock,
  updateProjectMock,
  createTaskTemplateMock,
  updateTaskTemplateMock,
  createDailyTaskMock,
} = vi.hoisted(() => ({
  fetchProjectsMock: vi.fn(),
  fetchTaskTemplatesMock: vi.fn(),
  createProjectMock: vi.fn(),
  updateProjectMock: vi.fn(),
  createTaskTemplateMock: vi.fn(),
  updateTaskTemplateMock: vi.fn(),
  createDailyTaskMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  fetchProjects: fetchProjectsMock,
  fetchTaskTemplates: fetchTaskTemplatesMock,
  createProject: createProjectMock,
  updateProject: updateProjectMock,
  createTaskTemplate: createTaskTemplateMock,
  updateTaskTemplate: updateTaskTemplateMock,
  createDailyTask: createDailyTaskMock,
  getErrorMessage: (error, fallback) => error?.message || fallback,
}));

beforeEach(() => {
  vi.clearAllMocks();
  fetchProjectsMock.mockResolvedValue([activeProject]);
  fetchTaskTemplatesMock.mockResolvedValue([activeTemplate]);
  createProjectMock.mockResolvedValue({
    id: 2,
    name: "写作",
    status: "active",
    sort_order: 1,
  });
  updateProjectMock.mockResolvedValue({});
  createTaskTemplateMock.mockResolvedValue({
    id: 2,
    project_id: 1,
    name: "力量训练 20 分钟",
    default_estimated_duration_minutes: 20,
    default_reward_amount: 1200,
    notes: "",
    is_active: true,
  });
  updateTaskTemplateMock.mockResolvedValue({});
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

test("submits default duration and reward when template fields are blank", async () => {
  render(<ProjectsPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();

  fireEvent.change(screen.getByPlaceholderText("例如：力量训练 20 分钟"), {
    target: { value: "复盘 20 分钟" },
  });
  fireEvent.click(screen.getByRole("button", { name: "创建模板" }));

  await waitFor(() => {
    expect(createTaskTemplateMock).toHaveBeenCalledWith({
      project_id: 1,
      name: "复盘 20 分钟",
      default_estimated_duration_minutes: 20,
      default_reward_amount: 1200,
      notes: "",
      is_active: true,
    });
  });
});

test("archives and restores projects via updateProject", async () => {
  fetchProjectsMock.mockResolvedValue([activeProject, nextActiveProject, archivedProject]);
  window.confirm = vi.fn(() => true);

  render(<ProjectsPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "删除项目 健身" }));

  await waitFor(() => {
    expect(updateProjectMock).toHaveBeenCalledWith(1, { status: "archived" });
  });

  fireEvent.click(screen.getByRole("button", { name: "恢复项目 阅读" }));

  await waitFor(() => {
    expect(updateProjectMock).toHaveBeenCalledWith(3, { status: "active" });
  });
});

test("archives and restores templates via updateTaskTemplate", async () => {
  fetchTaskTemplatesMock.mockResolvedValue([activeTemplate, archivedTemplate]);
  window.confirm = vi.fn(() => true);

  render(<ProjectsPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();
  expect(screen.getByText("拉伸 10 分钟")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "删除模板 跑步 30 分钟" }));

  await waitFor(() => {
    expect(updateTaskTemplateMock).toHaveBeenCalledWith(1, { is_active: false });
  });

  fireEvent.click(screen.getByRole("button", { name: "恢复模板 拉伸 10 分钟" }));

  await waitFor(() => {
    expect(updateTaskTemplateMock).toHaveBeenCalledWith(2, { is_active: true });
  });
});

test("loads templates for the next active project after archiving the current project", async () => {
  window.confirm = vi.fn(() => true);
  let projectsResponse = [activeProject, nextActiveProject];
  fetchProjectsMock.mockImplementation(async () => projectsResponse);
  fetchTaskTemplatesMock.mockImplementation(async (projectId) => {
    if (projectId === 2) {
      return [nextProjectTemplate];
    }

    return [activeTemplate];
  });
  updateProjectMock.mockImplementation(async (projectId, payload) => {
    if (projectId === activeProject.id && payload.status === "archived") {
      projectsResponse = [
        { ...activeProject, status: "archived" },
        nextActiveProject,
      ];
    }
    return {};
  });

  render(<ProjectsPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "删除项目 健身" }));

  await waitFor(() => {
    expect(updateProjectMock).toHaveBeenCalledWith(1, { status: "archived" });
  });
  expect(await screen.findByText("晨间随笔 15 分钟")).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.queryByText("跑步 30 分钟")).not.toBeInTheDocument();
  });
});

test("does not allow selecting an archived project", async () => {
  fetchProjectsMock.mockResolvedValue([activeProject, archivedProject]);
  fetchTaskTemplatesMock.mockImplementation(async (projectId) => {
    if (projectId === archivedProject.id) {
      return [archivedProjectTemplate];
    }

    return [activeTemplate];
  });

  render(<ProjectsPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();

  expect(
    screen.queryByRole("button", { name: /^阅读.*已归档$/ })
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("阅读 已归档")).toBeInTheDocument();

  fireEvent.change(screen.getByPlaceholderText("例如：力量训练 20 分钟"), {
    target: { value: "继续训练" },
  });
  fireEvent.click(screen.getByRole("button", { name: "创建模板" }));

  await waitFor(() => {
    expect(createTaskTemplateMock).toHaveBeenCalledWith({
      project_id: 1,
      name: "继续训练",
      default_estimated_duration_minutes: 20,
      default_reward_amount: 1200,
      notes: "",
      is_active: true,
    });
  });
  expect(fetchTaskTemplatesMock).not.toHaveBeenCalledWith(archivedProject.id);
  expect(screen.queryByText("归档项目模板")).not.toBeInTheDocument();
});
