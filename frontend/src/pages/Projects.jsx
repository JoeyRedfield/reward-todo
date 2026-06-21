import ProjectTemplatePanel from "../components/ProjectTemplatePanel";
import useProjectsBoard from "../hooks/useProjectsBoard";

export default function ProjectsPage() {
  const board = useProjectsBoard();

  return (
    <div className="page-stack">
      <header className="page-head">
        <div>
          <div className="page-kicker">Projects</div>
          <h2>长期项目决定方向，模板决定今天怎么开工。</h2>
        </div>
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
