export function formatYuanFromFen(amount) {
  return `¥${(amount / 100).toFixed(2)}`;
}

export function parseYuanToFen(value) {
  const trimmed = value.trim();
  if (trimmed === "") {
    return undefined;
  }
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) {
    return null;
  }

  const normalized = Number(trimmed);
  if (!Number.isFinite(normalized)) {
    return null;
  }

  return Math.round(normalized * 100);
}
