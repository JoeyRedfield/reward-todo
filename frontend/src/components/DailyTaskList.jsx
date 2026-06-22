import { useMemo, useState } from "react";

function formatYuan(amount) {
  return `¥${(amount / 100).toFixed(2)}`;
}

function parsePositiveInteger(value) {
  const trimmed = value.trim();
  if (trimmed === "") return undefined;
  if (!/^[1-9]\d*$/.test(trimmed)) return null;
  return Number(trimmed);
}

export default function DailyTaskList({
  tasks,
  pendingTaskId,
  onFinishTask,
  onReopenTask,
}) {
  const [expandedTaskId, setExpandedTaskId] = useState(null);
  const [actualDurationValue, setActualDurationValue] = useState("");
  const [submitError, setSubmitError] = useState(null);

  const expandedTask = useMemo(
    () => tasks.find((task) => task.id === expandedTaskId) || null,
    [expandedTaskId, tasks]
  );

  const resetConfirmation = () => {
    setExpandedTaskId(null);
    setActualDurationValue("");
    setSubmitError(null);
  };

  const handleConfirm = async () => {
    if (!expandedTask) return;
    const parsed = parsePositiveInteger(actualDurationValue);
    if (actualDurationValue.trim() !== "" && parsed === null) {
      setSubmitError("实际时长需要填写正整数分钟。");
      return;
    }

    try {
      await onFinishTask(expandedTask.id, parsed === null ? undefined : parsed);
      resetConfirmation();
    } catch {
      setSubmitError("提交失败，请稍后重试。");
    }
  };

  if (tasks.length === 0) {
    return (
      <section className="panel">
        <div className="panel-head">
          <h2>今日任务</h2>
        </div>
        <p className="empty-copy">今天还没有安排任务。</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>今日任务</h2>
      </div>
      <div className="task-list">
        {tasks.map((task) => {
          const isCompleted = task.status === "completed";
          const isExpanded = expandedTaskId === task.id;
          const isSubmitting = pendingTaskId === task.id;

          return (
            <article
              key={task.id}
              className={`task-item${isCompleted ? " is-complete" : ""}`}
            >
              <div className="task-row">
                <div>
                  <div className="task-name">{task.name_snapshot}</div>
                  <div className="task-meta">
                    <span>{task.estimated_duration_minutes_snapshot} 分钟</span>
                    <span>{formatYuan(task.reward_amount_snapshot)}</span>
                  </div>
                </div>
                {isCompleted ? (
                  <div className="task-status-actions">
                    <span className="status-pill">已完成</span>
                    <button
                      className="ghost-button"
                      onClick={() => {
                        void onReopenTask(task.id).catch(() => {});
                      }}
                      disabled={pendingTaskId !== null}
                    >
                      {isSubmitting ? "撤销中..." : "撤销完成"}
                    </button>
                  </div>
                ) : (
                  <button
                    className="primary-button"
                    onClick={() => {
                      setExpandedTaskId(task.id);
                      setActualDurationValue("");
                      setSubmitError(null);
                    }}
                    disabled={pendingTaskId !== null}
                  >
                    完成
                  </button>
                )}
              </div>

              {task.actual_duration_minutes !== null ? (
                <div className="task-footnote">
                  实际时长 {task.actual_duration_minutes} 分钟
                </div>
              ) : null}

              {isExpanded ? (
                <div className="confirm-sheet">
                  <label>
                    <span>实际时长</span>
                    <input
                      type="number"
                      min="1"
                      value={actualDurationValue}
                      onChange={(event) => setActualDurationValue(event.target.value)}
                      placeholder="选填，单位分钟"
                      disabled={isSubmitting}
                    />
                  </label>
                  <p className="helper-copy">
                    不填写会直接按完成处理，只记录状态和奖励。
                  </p>
                  {submitError ? <div className="error-banner">{submitError}</div> : null}
                  <div className="action-row">
                    <button className="ghost-button" onClick={resetConfirmation}>
                      取消
                    </button>
                    <button
                      className="primary-button"
                      onClick={() => void handleConfirm()}
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? "提交中..." : "确认完成"}
                    </button>
                  </div>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
