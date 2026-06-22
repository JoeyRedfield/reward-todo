import { useState } from "react";

function formatYuan(amount) {
  return `¥${(amount / 100).toFixed(2)}`;
}

function confirmBeforeArchive(message) {
  if (typeof window?.confirm !== "function") {
    return false;
  }

  try {
    return window.confirm(message) !== false;
  } catch {
    return false;
  }
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
  onArchiveProject,
  onRestoreProject,
  onArchiveTemplate,
  onRestoreTemplate,
  onAddToToday,
}) {
  const [projectName, setProjectName] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [durationValue, setDurationValue] = useState("");
  const [rewardValue, setRewardValue] = useState("");
  const [projectFormError, setProjectFormError] = useState(null);
  const [templateFormError, setTemplateFormError] = useState(null);
  const activeProjects = projects.filter((project) => project.status === "active");
  const archivedProjects = projects.filter((project) => project.status !== "active");
  const activeTemplates = templates.filter((template) => template.is_active);
  const archivedTemplates = templates.filter((template) => !template.is_active);

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
    const trimmedDuration = durationValue.trim();
    const trimmedReward = rewardValue.trim();
    const duration = trimmedDuration === "" ? null : Number(trimmedDuration);
    const reward = trimmedReward === "" ? null : Number(trimmedReward);

    if (trimmedName === "") {
      setTemplateFormError("模板名称不能为空。");
      return;
    }
    if (
      trimmedDuration !== "" &&
      (!Number.isInteger(duration) || duration <= 0)
    ) {
      setTemplateFormError("默认时长需要填写正整数分钟。");
      return;
    }
    if (trimmedReward !== "" && (!Number.isInteger(reward) || reward < 0)) {
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

  const handleArchiveProject = async (project) => {
    if (!confirmBeforeArchive(`确认删除项目「${project.name}」吗？`)) {
      return;
    }
    await onArchiveProject(project.id);
  };

  const handleArchiveTemplate = async (template) => {
    if (!confirmBeforeArchive(`确认删除模板「${template.name}」吗？`)) {
      return;
    }
    await onArchiveTemplate(template.id);
  };

  const renderProjectList = (items, emptyText, renderAction, isSelectable) => {
    if (items.length === 0) {
      return <p className="empty-copy">{emptyText}</p>;
    }

    return items.map((project) => (
      <article key={project.id} className="template-card">
        <div className="task-row">
          {isSelectable ? (
            <button
              className={`project-chip${project.id === selectedProjectId ? " is-active" : ""}`}
              onClick={() => onSelectProject(project.id)}
            >
              <span>{project.name}</span>
              <span>{project.status === "active" ? "启用中" : "已归档"}</span>
            </button>
          ) : (
            <div className="project-chip" aria-label={`${project.name} 已归档`}>
              <span>{project.name}</span>
              <span>已归档</span>
            </div>
          )}
          {renderAction(project)}
        </div>
      </article>
    ));
  };

  const renderTemplateList = (items, emptyText, renderAction) => {
    if (items.length === 0) {
      return <p className="empty-copy">{emptyText}</p>;
    }

    return items.map((template) => (
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
        <div className="task-row">
          {template.is_active ? (
            <button
              className="ghost-button"
              onClick={() => void onAddToToday(template)}
              disabled={addingTemplateId === template.id}
            >
              {addingTemplateId === template.id ? "加入中..." : "加入今日"}
            </button>
          ) : (
            <span />
          )}
          {renderAction(template)}
        </div>
      </article>
    ));
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
          <h3>启用中</h3>
          {renderProjectList(activeProjects, "还没有启用中的项目。", (project) => (
            <button
              className="ghost-button"
              aria-label={`删除项目 ${project.name}`}
              onClick={() => void handleArchiveProject(project)}
            >
              删除
            </button>
          ), true)}
          <h3>已归档</h3>
          {renderProjectList(archivedProjects, "还没有归档项目。", (project) => (
            <button
              className="ghost-button"
              aria-label={`恢复项目 ${project.name}`}
              onClick={() => void onRestoreProject(project.id)}
            >
              恢复
            </button>
          ), false)}
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
          <p className="empty-copy">留空时使用默认：20 分钟 / 1200 分</p>
          {templateFormError ? <div className="error-banner">{templateFormError}</div> : null}
          <button className="primary-button" onClick={() => void handleTemplateSubmit()}>
            {submittingTemplate ? "创建中..." : "创建模板"}
          </button>
        </div>

        <div className="template-list">
          <h3>启用中</h3>
          {renderTemplateList(activeTemplates, "当前项目还没有启用中的模板。", (template) => (
            <button
              className="ghost-button"
              aria-label={`删除模板 ${template.name}`}
              onClick={() => void handleArchiveTemplate(template)}
            >
              删除
            </button>
          ))}
          <h3>已归档</h3>
          {renderTemplateList(archivedTemplates, "当前项目还没有归档模板。", (template) => (
            <button
              className="ghost-button"
              aria-label={`恢复模板 ${template.name}`}
              onClick={() => void onRestoreTemplate(template.id)}
            >
              恢复
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
