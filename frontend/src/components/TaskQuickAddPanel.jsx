function formatYuan(amount) {
  return `¥${(amount / 100).toFixed(2)}`;
}

export default function TaskQuickAddPanel({
  addingTemplateId,
  selectedDate,
  templates,
  onAddTemplate,
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>快速加任务</h2>
      </div>

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
