import { formatYuanFromFen } from "../utils/currency";

function formatYuan(amount) {
  return formatYuanFromFen(Math.abs(amount));
}

export default function RewardLedgerPanel({
  summary,
  ledger,
  submitting,
  amountValue,
  reasonValue,
  submitError,
  onAmountChange,
  onReasonChange,
  onSubmitSpend,
}) {
  return (
    <div className="board-grid">
      <section className="panel">
        <div className="panel-head">
          <h2>奖励概况</h2>
        </div>
        <div className="summary-grid">
          <article className="summary-card">
            <div className="summary-label">当前余额</div>
            <div className="summary-value">{formatYuan(summary.current_balance)}</div>
            <div className="summary-hint">可用于手动扣减</div>
          </article>
          <article className="summary-card">
            <div className="summary-label">今日已赚</div>
            <div className="summary-value">{formatYuan(summary.today_earned)}</div>
            <div className="summary-hint">来自今日完成任务</div>
          </article>
        </div>
        <div className="form-stack reward-form">
          <label>
            <span>扣减金额（元）</span>
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={amountValue}
              onChange={(event) => onAmountChange(event.target.value)}
              placeholder="例如：5.00"
              disabled={submitting}
            />
          </label>
          <label>
            <span>扣减原因</span>
            <input
              type="text"
              value={reasonValue}
              onChange={(event) => onReasonChange(event.target.value)}
              placeholder="例如：咖啡"
              disabled={submitting}
            />
          </label>
          {submitError ? <div className="error-banner">{submitError}</div> : null}
          <button className="primary-button" onClick={() => void onSubmitSpend()}>
            {submitting ? "提交中..." : "确认扣减"}
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>奖励流水</h2>
        </div>
        {ledger.length === 0 ? (
          <p className="empty-copy">还没有奖励流水。</p>
        ) : (
          <div className="ledger-list">
            {ledger.map((entry) => (
              <article key={entry.id} className="ledger-item">
                <div>
                  <div className="task-name">{entry.reason}</div>
                  <div className="task-meta">
                    <span>{entry.entry_type}</span>
                    <span>{new Date(entry.created_at).toLocaleString()}</span>
                  </div>
                </div>
                <div
                  className={`ledger-amount${
                    entry.amount >= 0 ? " is-positive" : " is-negative"
                  }`}
                >
                  {entry.amount >= 0 ? "+" : "-"}
                  {formatYuan(entry.amount)}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
