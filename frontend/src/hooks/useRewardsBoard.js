import { useCallback, useEffect, useState } from "react";
import {
  fetchRewardLedger,
  fetchRewardSummary,
  getErrorMessage,
  spendReward,
} from "../api/client";
import { parseYuanToFen } from "../utils/currency";

const EMPTY_SUMMARY = {
  current_balance: 0,
  today_earned: 0,
};

export default function useRewardsBoard() {
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [ledger, setLedger] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [amountValue, setAmountValue] = useState("");
  const [reasonValue, setReasonValue] = useState("");
  const [submitError, setSubmitError] = useState(null);

  const loadBoard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, ledgerData] = await Promise.all([
        fetchRewardSummary(),
        fetchRewardLedger(),
      ]);
      setSummary(summaryData);
      setLedger(ledgerData);
    } catch (loadError) {
      setError(getErrorMessage(loadError, "奖励页加载失败，请稍后重试。"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBoard();
  }, [loadBoard]);

  const submitSpend = useCallback(async () => {
    const amountInFen = parseYuanToFen(amountValue);
    if (amountInFen === null || amountInFen <= 0) {
      setSubmitError("扣减金额需要填写大于 0 的金额，最多保留两位小数。");
      return;
    }
    if (reasonValue.trim() === "") {
      setSubmitError("扣减原因不能为空。");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await spendReward(amountInFen, reasonValue.trim());
      setAmountValue("");
      setReasonValue("");
      await loadBoard();
    } catch (submitErrorValue) {
      setSubmitError(getErrorMessage(submitErrorValue, "奖励扣减失败，请稍后重试。"));
      throw submitErrorValue;
    } finally {
      setSubmitting(false);
    }
  }, [amountValue, loadBoard, reasonValue]);

  return {
    summary,
    ledger,
    loading,
    error,
    submitting,
    amountValue,
    reasonValue,
    submitError,
    setAmountValue,
    setReasonValue,
    submitSpend,
    reload: loadBoard,
  };
}
