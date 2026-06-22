function formatYuan(amount) {
  return `¥${(amount / 100).toFixed(2)}`;
}

export default function TaskSummaryCards({ summary, tasks }) {
  const completedCount = tasks.filter((task) => task.status === "completed").length;
  const totalMinutes = tasks.reduce(
    (sum, task) => sum + task.estimated_duration_minutes_snapshot,
    0
  );

  const cards = [
    {
      serial: "BALANCE",
      tone: "ledger",
      label: "当前奖励余额",
      value: formatYuan(summary.current_balance),
      hint: "可以用于手动扣减",
    },
    {
      serial: "EARNED",
      tone: "copper",
      label: "今日已赚",
      value: formatYuan(summary.today_earned),
      hint: "来自已完成任务",
    },
    {
      serial: "PROGRESS",
      tone: "plum",
      label: "今日进度",
      value: `${completedCount} / ${tasks.length}`,
      hint: tasks.length === 0 ? "今天还没有任务" : "按任务条目统计",
    },
    {
      serial: "MINUTES",
      tone: "ink",
      label: "预计总时长",
      value: `${totalMinutes} 分钟`,
      hint: "来自今日任务快照",
    },
  ];

  return (
    <section className="summary-grid">
      {cards.map((card) => (
        <article
          key={card.label}
          className={`summary-card summary-card--${card.tone}`}
        >
          <div className="summary-serial">{card.serial}</div>
          <div className="summary-label">{card.label}</div>
          <div className="summary-value">{card.value}</div>
          <div className="summary-hint">{card.hint}</div>
        </article>
      ))}
    </section>
  );
}
