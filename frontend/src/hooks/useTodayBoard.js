import { useCallback, useEffect, useState } from "react";
import {
  completeDailyTask,
  fetchDailyTasks,
  fetchRewardSummary,
  getErrorMessage,
  reopenDailyTask,
} from "../api/client";
import { formatLocalDate } from "../utils/date";

const EMPTY_SUMMARY = {
  current_balance: 0,
  today_earned: 0,
};

export default function useTodayBoard() {
  const [tasks, setTasks] = useState([]);
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pendingTaskId, setPendingTaskId] = useState(null);

  const loadBoard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const date = formatLocalDate();
      const [tasksData, summaryData] = await Promise.all([
        fetchDailyTasks(date),
        fetchRewardSummary(),
      ]);
      setTasks(tasksData);
      setSummary(summaryData);
    } catch (loadError) {
      setError(getErrorMessage(loadError, "今日任务加载失败，请稍后重试。"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBoard();
  }, [loadBoard]);

  const finishTask = useCallback(async (taskId, actualDurationMinutes) => {
    setPendingTaskId(taskId);
    setError(null);
    try {
      await completeDailyTask(taskId, actualDurationMinutes);
      await loadBoard();
    } catch (finishError) {
      setError(getErrorMessage(finishError, "任务完成失败，请稍后再试。"));
      throw finishError;
    } finally {
      setPendingTaskId(null);
    }
  }, [loadBoard]);

  const reopenTask = useCallback(async (taskId) => {
    setPendingTaskId(taskId);
    setError(null);
    try {
      await reopenDailyTask(taskId);
      await loadBoard();
    } catch (reopenError) {
      setError(getErrorMessage(reopenError, "撤销失败，请稍后再试。"));
      throw reopenError;
    } finally {
      setPendingTaskId(null);
    }
  }, [loadBoard]);

  return {
    tasks,
    summary,
    loading,
    error,
    pendingTaskId,
    finishTask,
    reopenTask,
    reload: loadBoard,
  };
}
