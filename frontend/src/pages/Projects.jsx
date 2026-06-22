import ProjectTemplatePanel from "../components/ProjectTemplatePanel";
import useProjectsBoard from "../hooks/useProjectsBoard";

export default function ProjectsPage() {
  const board = useProjectsBoard();

  return (
    <div className="page-stack">
      <header className="page-head">
        <div className="page-head-main">
          <div className="page-kicker">Projects</div>
          <h2>长期项目决定方向，模板决定今天怎么开工。</h2>
        </div>
        <aside className="page-stamp">
          <div className="page-stamp-label">本页用途</div>
          <div className="page-stamp-value">沉淀可复用的开工模板。</div>
        </aside>
      </header>
      {board.loading ? (
        <div className="loading-card">加载中...</div>
      ) : (
        <>
          {board.error ? <div className="error-banner">{board.error}</div> : null}
          {board.successMessage ? (
            <div className="success-banner">{board.successMessage}</div>
          ) : null}
          <ProjectTemplatePanel
            projects={board.projects}
            selectedProjectId={board.selectedProjectId}
            templates={board.templates}
            submittingProject={board.submittingProject}
            submittingTemplate={board.submittingTemplate}
            addingTemplateId={board.addingTemplateId}
            onSelectProject={board.selectProject}
            onCreateProject={board.submitProject}
            onCreateTemplate={board.submitTemplate}
            onAddToToday={board.addTemplateToToday}
          />
        </>
      )}
    </div>
  );
}
