import { useEffect, useState } from "react";
import {
  getStandaloneTaskActions,
  subscribeStandaloneTaskActions,
} from "../hooks/useTodayBoard";

function formatYuan(amount) {
  return `¥${(amount / 100).toFixed(2)}`;
}

function parsePositiveInteger(value) {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  if (!/^[1-9]\d*$/.test(trimmed)) return undefined;
  return Number(trimmed);
}

function parseRewardAmount(value) {
  const trimmed = value.trim();
  if (trimmed === "") return 0;
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return null;
  return Math.round(Number(trimmed) * 100);
}

export default function TaskQuickAddPanel({
  addingTemplateId,
  selectedDate,
  templates,
  onAddTemplate,
}) {
  const [standaloneActions, setStandaloneActions] = useState(getStandaloneTaskActions);
  const [name, setName] = useState("");
  const [estimatedDuration, setEstimatedDuration] = useState("");
  const [rewardAmount, setRewardAmount] = useState("");
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => subscribeStandaloneTaskActions(setStandaloneActions), []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setSubmitError("请输入任务名称。");
      return;
    }

    const parsedDuration = parsePositiveInteger(estimatedDuration);
    if (parsedDuration === undefined) {
      setSubmitError("预计时长需要填写正整数分钟。");
      return;
    }
    if (parsedDuration === null) {
      setSubmitError("请输入预计时长。");
      return;
    }

    const parsedReward = parseRewardAmount(rewardAmount);
    if (parsedReward === null) {
      setSubmitError("奖励金额最多保留两位小数。");
      return;
    }

    setSubmitError(null);

    try {
      await standaloneActions.addStandaloneTask({
        name: trimmedName,
        estimatedDurationMinutes: parsedDuration,
        rewardAmount: parsedReward,
      });
      setName("");
      setEstimatedDuration("");
      setRewardAmount("");
    } catch {}
  };

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>快速加任务</h2>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="confirm-sheet">
          <label>
            <span>任务名称</span>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={standaloneActions.addingStandaloneTask}
            />
          </label>
          <label>
            <span>预计时长（分钟）</span>
            <input
              type="number"
              min="1"
              value={estimatedDuration}
              onChange={(event) => setEstimatedDuration(event.target.value)}
              disabled={standaloneActions.addingStandaloneTask}
            />
          </label>
          <label>
            <span>奖励金额（元）</span>
            <input
              type="text"
              inputMode="decimal"
              placeholder="0.00"
              value={rewardAmount}
              onChange={(event) => setRewardAmount(event.target.value)}
              disabled={standaloneActions.addingStandaloneTask}
            />
          </label>
          <p className="helper-copy">留空按 ¥0.00 处理</p>
          <p className="helper-copy">会加入到 {selectedDate}</p>
          {submitError ? <div className="error-banner">{submitError}</div> : null}
          <div className="action-row">
            <button
              className="primary-button"
              type="submit"
              disabled={standaloneActions.addingStandaloneTask}
            >
              {standaloneActions.addingStandaloneTask ? "添加中..." : "直接添加任务"}
            </button>
          </div>
        </div>
      </form>

      {templates.length === 0 ? (
        <p className="empty-copy">当前没有可直接加入台账的启用模板。</p>
      ) : (
        <div className="quick-add-list">
          {templates.map((template) => {
            const isAdding = addingTemplateId === template.id;

            return (
              <article key={template.id} className="template-card">
                <div className="quick-add-header">
                  <div>
                    <div className="task-name">{template.name}</div>
                    <div className="quick-add-project">{template.project_name}</div>
                  </div>
                  <span className="status-pill">启用</span>
                </div>

                <div className="task-meta">
                  <span>{template.default_estimated_duration_minutes} 分钟</span>
                  <span>{formatYuan(template.default_reward_amount)}</span>
                </div>

                <div className="action-row">
                  <span className="helper-copy">会加入到 {selectedDate}</span>
                  <button
                    aria-label={`加入 ${selectedDate}：${template.name}`}
                    className="primary-button"
                    disabled={isAdding}
                    onClick={() => void onAddTemplate(template)}
                    type="button"
                  >
                    {isAdding ? "加入中..." : `加入 ${selectedDate}`}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
