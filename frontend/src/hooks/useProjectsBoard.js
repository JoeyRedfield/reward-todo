import { useCallback, useEffect, useState } from "react";
import {
  createDailyTask,
  createProject,
  createTaskTemplate,
  fetchProjects,
  fetchTaskTemplates,
  getErrorMessage,
} from "../api/client";
import { formatLocalDate } from "../utils/date";

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
      const initialProjectId = projectsData[0]?.id ?? null;
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
    try {
      const templatesData = await fetchTaskTemplates(projectId);
      setSelectedProjectId(projectId);
      setTemplates(templatesData);
    } catch (loadError) {
      setError(getErrorMessage(loadError, "模板加载失败，请稍后重试。"));
    }
  }, []);

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
      await createTaskTemplate({
        project_id: selectedProjectId,
        name: payload.name,
        default_estimated_duration_minutes: payload.defaultEstimatedDurationMinutes,
        default_reward_amount: payload.defaultRewardAmount,
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
    addTemplateToToday,
    reload: loadBoard,
  };
}
