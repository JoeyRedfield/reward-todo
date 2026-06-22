import { useCallback, useEffect, useState } from "react";
import {
  createDailyTask,
  createProject,
  createTaskTemplate,
  fetchProjects,
  fetchTaskTemplates,
  getErrorMessage,
  updateProject,
  updateTaskTemplate,
} from "../api/client";
import { formatLocalDate } from "../utils/date";

const DEFAULT_TEMPLATE_DURATION_MINUTES = 20;
const DEFAULT_TEMPLATE_REWARD_AMOUNT = 1200;

function getActiveProjects(projects) {
  return projects.filter((project) => project.status === "active");
}

function pickSelectedProjectId(projects, preferredProjectId = null) {
  const activeProjects = getActiveProjects(projects);
  if (activeProjects.length === 0) {
    return null;
  }

  if (
    preferredProjectId !== null &&
    activeProjects.some((project) => project.id === preferredProjectId)
  ) {
    return preferredProjectId;
  }

  return activeProjects[0].id;
}

export default function useProjectsBoard() {
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submittingProject, setSubmittingProject] = useState(false);
  const [submittingTemplate, setSubmittingTemplate] = useState(false);
  const [addingTemplateId, setAddingTemplateId] = useState(null);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const loadBoard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const projectsData = await fetchProjects();
      setProjects(projectsData);
      const initialProjectId = pickSelectedProjectId(projectsData);
      setSelectedProjectId(initialProjectId);
      if (initialProjectId === null) {
        setTemplates([]);
      } else {
        setTemplates(await fetchTaskTemplates(initialProjectId));
      }
    } catch (loadError) {
      setError(getErrorMessage(loadError, "项目页加载失败，请稍后重试。"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBoard();
  }, [loadBoard]);

  const selectProject = useCallback(async (projectId) => {
    setError(null);
    setSuccessMessage(null);
    const project = projects.find((item) => item.id === projectId);
    if (!project || project.status !== "active") {
      setError("只能选择启用中的项目。");
      return;
    }
    try {
      const templatesData = await fetchTaskTemplates(projectId);
      setSelectedProjectId(projectId);
      setTemplates(templatesData);
    } catch (loadError) {
      setError(getErrorMessage(loadError, "模板加载失败，请稍后重试。"));
    }
  }, [projects]);

  const submitProject = useCallback(async (name) => {
    setSubmittingProject(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const project = await createProject(name);
      const projectsData = await fetchProjects();
      setProjects(projectsData);
      setSelectedProjectId(project.id);
      setTemplates(await fetchTaskTemplates(project.id));
      setSuccessMessage("项目已创建。");
    } catch (submitError) {
      setError(getErrorMessage(submitError, "创建项目失败，请稍后重试。"));
      throw submitError;
    } finally {
      setSubmittingProject(false);
    }
  }, []);

  const submitTemplate = useCallback(async (payload) => {
    if (selectedProjectId === null) {
      setError("请先创建并选择项目。");
      return;
    }
    setSubmittingTemplate(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const durationMinutes =
        payload.defaultEstimatedDurationMinutes ?? DEFAULT_TEMPLATE_DURATION_MINUTES;
      const rewardAmount =
        payload.defaultRewardAmount ?? DEFAULT_TEMPLATE_REWARD_AMOUNT;

      await createTaskTemplate({
        project_id: selectedProjectId,
        name: payload.name,
        default_estimated_duration_minutes: durationMinutes,
        default_reward_amount: rewardAmount,
        notes: "",
        is_active: true,
      });
      setTemplates(await fetchTaskTemplates(selectedProjectId));
      setSuccessMessage("模板已创建。");
    } catch (submitError) {
      setError(getErrorMessage(submitError, "创建模板失败，请稍后重试。"));
      throw submitError;
    } finally {
      setSubmittingTemplate(false);
    }
  }, [selectedProjectId]);

  const addTemplateToToday = useCallback(async (template) => {
    setAddingTemplateId(template.id);
    setError(null);
    setSuccessMessage(null);
    try {
      await createDailyTask({
        date: formatLocalDate(),
        task_template_id: template.id,
        estimated_duration_minutes: template.default_estimated_duration_minutes,
        reward_amount: template.default_reward_amount,
      });
      setSuccessMessage("已加入今日任务。");
    } catch (submitError) {
      setError(getErrorMessage(submitError, "加入今日失败，请稍后重试。"));
      throw submitError;
    } finally {
      setAddingTemplateId(null);
    }
  }, []);

  const archiveProject = useCallback(async (projectId) => {
    setError(null);
    setSuccessMessage(null);
    try {
      await updateProject(projectId, { status: "archived" });
      const projectsData = await fetchProjects();
      const nextProjectId = pickSelectedProjectId(projectsData, selectedProjectId);
      setProjects(projectsData);
      setSelectedProjectId(nextProjectId);
      if (nextProjectId === null) {
        setTemplates([]);
      } else {
        setTemplates(await fetchTaskTemplates(nextProjectId));
      }
      setSuccessMessage("项目已删除。");
    } catch (submitError) {
      setError(getErrorMessage(submitError, "删除项目失败，请稍后重试。"));
      throw submitError;
    }
  }, [selectedProjectId]);

  const restoreProject = useCallback(async (projectId) => {
    setError(null);
    setSuccessMessage(null);
    try {
      await updateProject(projectId, { status: "active" });
      const projectsData = await fetchProjects();
      const nextProjectId = pickSelectedProjectId(projectsData, selectedProjectId);
      setProjects(projectsData);
      if (nextProjectId === null) {
        setSelectedProjectId(null);
        setTemplates([]);
      } else if (nextProjectId !== selectedProjectId) {
        setSelectedProjectId(nextProjectId);
        setTemplates(await fetchTaskTemplates(nextProjectId));
      }
      setSuccessMessage("项目已恢复。");
    } catch (submitError) {
      setError(getErrorMessage(submitError, "恢复项目失败，请稍后重试。"));
      throw submitError;
    }
  }, [selectedProjectId]);

  const archiveTemplate = useCallback(async (templateId) => {
    if (selectedProjectId === null) {
      return;
    }

    setError(null);
    setSuccessMessage(null);
    try {
      await updateTaskTemplate(templateId, { is_active: false });
      setTemplates(await fetchTaskTemplates(selectedProjectId));
      setSuccessMessage("模板已删除。");
    } catch (submitError) {
      setError(getErrorMessage(submitError, "删除模板失败，请稍后重试。"));
      throw submitError;
    }
  }, [selectedProjectId]);

  const restoreTemplate = useCallback(async (templateId) => {
    if (selectedProjectId === null) {
      return;
    }

    setError(null);
    setSuccessMessage(null);
    try {
      await updateTaskTemplate(templateId, { is_active: true });
      setTemplates(await fetchTaskTemplates(selectedProjectId));
      setSuccessMessage("模板已恢复。");
    } catch (submitError) {
      setError(getErrorMessage(submitError, "恢复模板失败，请稍后重试。"));
      throw submitError;
    }
  }, [selectedProjectId]);

  return {
    projects,
    selectedProjectId,
    templates,
    loading,
    error,
    successMessage,
    submittingProject,
    submittingTemplate,
    addingTemplateId,
    selectProject,
    submitProject,
    submitTemplate,
    archiveProject,
    restoreProject,
    archiveTemplate,
    restoreTemplate,
    addTemplateToToday,
    reload: loadBoard,
  };
}
