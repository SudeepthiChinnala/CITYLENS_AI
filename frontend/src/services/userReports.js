const STORAGE_KEY = 'citylens.myReportIds';

export function getMyReportIds() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
    return Array.isArray(parsed) ? parsed.map(Number).filter(Number.isInteger) : [];
  } catch {
    return [];
  }
}

export function rememberMyReport(id) {
  if (!id) return;
  const ids = new Set(getMyReportIds());
  ids.add(Number(id));
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
}
