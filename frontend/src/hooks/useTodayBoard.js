import { useCallback, useEffect, useRef, useState } from "react";
import {
  completeDailyTask,
  createDailyTask,
  deleteDailyTask,
  fetchDailyTaskCalendar,
  fetchDailyTasks,
  fetchProjects,
  fetchRewardSummary,
  fetchTaskTemplates,
  getErrorMessage,
  reopenDailyTask,
} from "../api/client";
import { getMonthBounds } from "../utils/calendar";
import { formatLocalDate } from "../utils/date";

const EMPTY_SUMMARY = {
  current_balance: 0,
  today_earned: 0,
};

function buildQuickAddTemplates(projects, templates) {
  const activeProjects = projects.filter((project) => project.status === "active");
  const activeProjectIds = new Set(activeProjects.map((project) => project.id));
  const projectNameById = Object.fromEntries(activeProjects.map((project) => [project.id, project.name]));

  return templates
    .filter((template) => template.is_active && activeProjectIds.has(template.project_id))
    .map((template) => ({
      ...template,
      project_name: projectNameById[template.project_id] || "未命名项目",
    }));
}

export default function useTodayBoard() {
  const today = formatLocalDate();
  const [selectedDate, setSelectedDate] = useState(today);
  const [visibleMonth, setVisibleMonth] = useState(today);
  const [tasks, setTasks] = useState([]);
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [calendarSummary, setCalendarSummary] = useState([]);
  const [quickAddTemplates, setQuickAddTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pendingTaskId, setPendingTaskId] = useState(null);
  const [pendingTaskAction, setPendingTaskAction] = useState(null);
  const [addingTemplateId, setAddingTemplateId] = useState(null);
  const [addingStandaloneTask, setAddingStandaloneTask] = useState(false);
  const requestIdRef = useRef(0);
  const selectedDateRef = useRef(today);
  const visibleMonthRef = useRef(today);

  selectedDateRef.current = selectedDate;
  visibleMonthRef.current = visibleMonth;

  const loadBoard = useCallback(async (targetDate, monthDate) => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setError(null);

    try {
      const { start, end } = getMonthBounds(monthDate);
      const [tasksData, summaryData, calendarData, projectsData, templatesData] = await Promise.all([
        fetchDailyTasks(targetDate),
        fetchRewardSummary(targetDate),
        fetchDailyTaskCalendar(start, end),
        fetchProjects(),
        fetchTaskTemplates(),
      ]);

      if (requestId !== requestIdRef.current) {
        return;
      }

      setTasks(tasksData);
      setSummary(summaryData);
      setCalendarSummary(calendarData);
      setQuickAddTemplates(buildQuickAddTemplates(projectsData, templatesData));
    } catch (loadError) {
      if (requestId !== requestIdRef.current) {
        return;
      }
      setTasks([]);
      setSummary(EMPTY_SUMMARY);
      setCalendarSummary([]);
      setError(getErrorMessage(loadError, "台账加载失败，请稍后重试。"));
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadBoard(selectedDate, visibleMonth);
  }, [loadBoard, selectedDate, visibleMonth]);

  const finishTask = useCallback(async (taskId, actualDurationMinutes) => {
    setPendingTaskId(taskId);
    setPendingTaskAction("complete");
    setError(null);
    try {
      await completeDailyTask(taskId, actualDurationMinutes);
      await loadBoard(selectedDateRef.current, visibleMonthRef.current);
    } catch (finishError) {
      setError(getErrorMessage(finishError, "任务完成失败，请稍后再试。"));
      throw finishError;
    } finally {
      setPendingTaskId(null);
      setPendingTaskAction(null);
    }
  }, [loadBoard]);

  const reopenTask = useCallback(async (taskId) => {
    setPendingTaskId(taskId);
    setPendingTaskAction("reopen");
    setError(null);
    try {
      await reopenDailyTask(taskId);
      await loadBoard(selectedDateRef.current, visibleMonthRef.current);
    } catch (reopenError) {
      setError(getErrorMessage(reopenError, "撤销失败，请稍后再试。"));
      throw reopenError;
    } finally {
      setPendingTaskId(null);
      setPendingTaskAction(null);
    }
  }, [loadBoard]);

  const addTemplateToSelectedDate = useCallback(async (template) => {
    setAddingTemplateId(template.id);
    setError(null);
    try {
      await createDailyTask({
        date: selectedDateRef.current,
        task_template_id: template.id,
        estimated_duration_minutes: template.default_estimated_duration_minutes,
        reward_amount: template.default_reward_amount,
      });
      await loadBoard(selectedDateRef.current, visibleMonthRef.current);
    } catch (submitError) {
      setError(getErrorMessage(submitError, "加入当前日期失败，请稍后重试。"));
      throw submitError;
    } finally {
      setAddingTemplateId(null);
    }
  }, [loadBoard]);

  const addStandaloneTask = useCallback(async ({ name, estimatedDurationMinutes, rewardAmount }) => {
    setAddingStandaloneTask(true);
    setError(null);
    try {
      await createDailyTask({
        date: selectedDateRef.current,
        name,
        estimated_duration_minutes: estimatedDurationMinutes,
        reward_amount: rewardAmount,
      });
      await loadBoard(selectedDateRef.current, visibleMonthRef.current);
    } catch (submitError) {
      setError(getErrorMessage(submitError, "直接添加任务失败，请稍后重试。"));
      throw submitError;
    } finally {
      setAddingStandaloneTask(false);
    }
  }, [loadBoard]);

  const deleteStandaloneTask = useCallback(async (taskId) => {
    setPendingTaskId(taskId);
    setPendingTaskAction("delete");
    setError(null);
    try {
      await deleteDailyTask(taskId);
      await loadBoard(selectedDateRef.current, visibleMonthRef.current);
    } catch (deleteError) {
      setError(getErrorMessage(deleteError, "删除任务失败，请稍后重试。"));
      throw deleteError;
    } finally {
      setPendingTaskId(null);
      setPendingTaskAction(null);
    }
  }, [loadBoard]);

  const selectDate = useCallback((date) => {
    setSelectedDate(date);
    setVisibleMonth(date);
  }, []);

  const jumpToToday = useCallback(() => {
    setSelectedDate(today);
    setVisibleMonth(today);
  }, [today]);

  return {
    addingStandaloneTask,
    addingTemplateId,
    addTemplateToSelectedDate,
    addStandaloneTask,
    calendarSummary,
    deleteStandaloneTask,
    error,
    finishTask,
    jumpToToday,
    loading,
    pendingTaskId,
    pendingTaskAction,
    quickAddTemplates,
    reopenTask,
    selectedDate,
    selectDate,
    setVisibleMonth,
    summary,
    tasks,
    today,
    visibleMonth,
  };
}
