import { useState } from "react";

function formatYuan(amount) {
  return `¥${(amount / 100).toFixed(2)}`;
}

export default function ProjectTemplatePanel({
  projects,
  selectedProjectId,
  templates,
  submittingProject,
  submittingTemplate,
  addingTemplateId,
  onSelectProject,
  onCreateProject,
  onCreateTemplate,
  onAddToToday,
}) {
  const [projectName, setProjectName] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [durationValue, setDurationValue] = useState("");
  const [rewardValue, setRewardValue] = useState("");
  const [projectFormError, setProjectFormError] = useState(null);
  const [templateFormError, setTemplateFormError] = useState(null);

  const handleProjectSubmit = async () => {
    const trimmedName = projectName.trim();
    if (trimmedName === "") {
      setProjectFormError("项目名称不能为空。");
      return;
    }
    setProjectFormError(null);
    try {
      await onCreateProject(trimmedName);
      setProjectName("");
    } catch {}
  };

  const handleTemplateSubmit = async () => {
    const trimmedName = templateName.trim();
    const duration = Number(durationValue);
    const reward = Number(rewardValue);

    if (trimmedName === "") {
      setTemplateFormError("模板名称不能为空。");
      return;
    }
    if (!Number.isInteger(duration) || duration <= 0) {
      setTemplateFormError("默认时长需要填写正整数分钟。");
      return;
    }
    if (!Number.isInteger(reward) || reward < 0) {
      setTemplateFormError("默认奖励金额需要填写非负整数。");
      return;
    }

    setTemplateFormError(null);
    try {
      await onCreateTemplate({
        name: trimmedName,
        defaultEstimatedDurationMinutes: duration,
        defaultRewardAmount: reward,
      });
      setTemplateName("");
      setDurationValue("");
      setRewardValue("");
    } catch {}
  };

  return (
    <div className="board-grid">
      <section className="panel">
        <div className="panel-head">
          <h2>项目</h2>
        </div>
        <div className="form-stack">
          <label>
            <span>项目名称</span>
            <input
              type="text"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              placeholder="例如：写作"
              disabled={submittingProject}
            />
          </label>
          {projectFormError ? <div className="error-banner">{projectFormError}</div> : null}
          <button className="primary-button" onClick={() => void handleProjectSubmit()}>
            {submittingProject ? "创建中..." : "创建项目"}
          </button>
        </div>

        <div className="project-list">
          {projects.length === 0 ? (
            <p className="empty-copy">还没有项目。</p>
          ) : (
            projects.map((project) => (
              <button
                key={project.id}
                className={`project-chip${project.id === selectedProjectId ? " is-active" : ""}`}
                onClick={() => onSelectProject(project.id)}
              >
                <span>{project.name}</span>
                <span>{project.status === "active" ? "启用中" : project.status}</span>
              </button>
            ))
          )}
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>模板</h2>
        </div>
        <div className="form-stack">
          <label>
            <span>模板名称</span>
            <input
              type="text"
              value={templateName}
              onChange={(event) => setTemplateName(event.target.value)}
              placeholder="例如：力量训练 20 分钟"
              disabled={selectedProjectId === null || submittingTemplate}
            />
          </label>
          <div className="inline-grid">
            <label>
              <span>默认时长（分钟）</span>
              <input
                type="number"
                min="1"
                value={durationValue}
                onChange={(event) => setDurationValue(event.target.value)}
                placeholder="20"
                disabled={selectedProjectId === null || submittingTemplate}
              />
            </label>
            <label>
              <span>默认奖励金额（分）</span>
              <input
                type="number"
                min="0"
                value={rewardValue}
                onChange={(event) => setRewardValue(event.target.value)}
                placeholder="1200"
                disabled={selectedProjectId === null || submittingTemplate}
              />
            </label>
          </div>
          {templateFormError ? <div className="error-banner">{templateFormError}</div> : null}
          <button className="primary-button" onClick={() => void handleTemplateSubmit()}>
            {submittingTemplate ? "创建中..." : "创建模板"}
          </button>
        </div>

        <div className="template-list">
          {templates.length === 0 ? (
            <p className="empty-copy">当前项目还没有模板。</p>
          ) : (
            templates.map((template) => (
              <article key={template.id} className="template-card">
                <div className="task-row">
                  <div>
                    <div className="task-name">{template.name}</div>
                    <div className="task-meta">
                      <span>{template.default_estimated_duration_minutes} 分钟</span>
                      <span>{formatYuan(template.default_reward_amount)}</span>
                    </div>
                  </div>
                  <span className="status-pill">
                    {template.is_active ? "启用" : "停用"}
                  </span>
                </div>
                {template.notes ? <p className="template-notes">{template.notes}</p> : null}
                <button
                  className="ghost-button"
                  onClick={() => void onAddToToday(template)}
                  disabled={addingTemplateId === template.id}
                >
                  {addingTemplateId === template.id ? "加入中..." : "加入今日"}
                </button>
              </article>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
