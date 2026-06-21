import RewardLedgerPanel from "../components/RewardLedgerPanel";
import useRewardsBoard from "../hooks/useRewardsBoard";

export default function RewardsPage() {
  const board = useRewardsBoard();

  return (
    <div className="page-stack">
      <header className="page-head">
        <div>
          <div className="page-kicker">Rewards</div>
          <h2>把奖励额度当作账本，明确地赚、明确地花。</h2>
        </div>
      </header>
      {board.loading ? (
        <div className="loading-card">加载中...</div>
      ) : (
        <>
          {board.error ? <div className="error-banner">{board.error}</div> : null}
          <RewardLedgerPanel
            summary={board.summary}
            ledger={board.ledger}
            submitting={board.submitting}
            amountValue={board.amountValue}
            reasonValue={board.reasonValue}
            submitError={board.submitError}
            onAmountChange={board.setAmountValue}
            onReasonChange={board.setReasonValue}
            onSubmitSpend={board.submitSpend}
          />
        </>
      )}
    </div>
  );
}
