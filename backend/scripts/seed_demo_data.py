import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import get_session_factory, init_db
from app.services.task_reward_service import TaskRewardService


def main() -> None:
    init_db()
    session = get_session_factory()()
    try:
        service = TaskRewardService(session)
        if service.list_projects():
            print("seed skipped: demo data already exists")
            return

        fitness = service.create_project(name="健身", sort_order=0)
        learning = service.create_project(name="学习", sort_order=1)

        run_template = service.create_task_template(
            project_id=fitness.id,
            name="跑步 30 分钟",
            default_estimated_duration_minutes=30,
            default_reward_amount=2000,
            notes="晨跑，保持心肺",
        )
        stretch_template = service.create_task_template(
            project_id=fitness.id,
            name="拉伸 15 分钟",
            default_estimated_duration_minutes=15,
            default_reward_amount=800,
            notes="收操与放松",
        )
        reading_template = service.create_task_template(
            project_id=learning.id,
            name="读书 45 分钟",
            default_estimated_duration_minutes=45,
            default_reward_amount=1500,
            notes="输出一段笔记",
        )

        today = datetime.date.today()
        run_task = service.create_daily_task(
            task_template_id=run_template.id,
            date=today,
            estimated_duration_minutes=30,
            reward_amount=2000,
        )
        service.create_daily_task(
            task_template_id=stretch_template.id,
            date=today,
            estimated_duration_minutes=20,
            reward_amount=1000,
        )
        service.create_daily_task(
            task_template_id=reading_template.id,
            date=today,
            estimated_duration_minutes=45,
            reward_amount=1500,
        )
        service.complete_daily_task(run_task.id, actual_duration_minutes=28)
        service.spend_reward(amount=500, reason="咖啡奖励")

        print(f"seeded demo data for {today.isoformat()}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
