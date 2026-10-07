const severityWeight = { LOW: 1, MEDIUM: 2, HIGH: 3 };

export function buildMasterProblems(complaints = [], clusters = []) {
  const grouped = new Map();
  complaints.forEach((complaint) => {
    const key = complaint.cluster_id != null ? `cluster-${complaint.cluster_id}` : `area-${complaint.area || 'Unknown'}-${complaint.problem_type || 'Other'}`;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(complaint);
  });
  return [...grouped.entries()]
    .filter(([, rows]) => rows.length > 1)
    .map(([key, rows], index) => {
      const typeCounts = rows.reduce((acc, row) => {
        const type = row.problem_type || 'Other';
        acc[type] = (acc[type] || 0) + 1;
        return acc;
      }, {});
      const dominantIssue = Object.entries(typeCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'Urban issue';
      const highSeverity = rows.filter((row) => row.severity === 'HIGH').length;
      const priority = rows.map((row) => Number(row.priority_score)).filter(Number.isFinite);
      const area = rows.map((row) => row.area).filter(Boolean).sort()[0] || 'Unknown area';
      const cluster = rows[0].cluster_id != null ? clusters.find((item) => item.properties?.cluster_id === rows[0].cluster_id) : null;
      return {
        id: key.replace('cluster-', 'RI-').replace('area-', 'AREA-').toUpperCase(),
        title: `${dominantIssue} incident`,
        area,
        reports: rows.length,
        highSeverity,
        issueTypes: Object.keys(typeCounts).length,
        avgPriority: priority.length ? Math.round(priority.reduce((sum, value) => sum + value, 0) / priority.length) : null,
        status: rows.some((row) => row.status !== 'Resolved') ? 'Active' : 'Resolved',
        confidence: Math.min(99, 68 + rows.length * 4 + (cluster ? 8 : 0)),
        rows,
        rank: index + 1,
      };
    })
    .sort((a, b) => b.reports - a.reports || b.highSeverity - a.highSeverity);
}

export function buildObservedRiskAreas(complaints = [], clusters = []) {
  const now = Date.now();
  const recentCutoff = now - 7 * 24 * 60 * 60 * 1000;
  const priorCutoff = now - 21 * 24 * 60 * 60 * 1000;
  const byArea = new Map();
  complaints.forEach((complaint) => {
    const area = complaint.area || 'Unknown';
    if (!byArea.has(area)) byArea.set(area, []);
    byArea.get(area).push(complaint);
  });
  return [...byArea.entries()].map(([area, rows]) => {
    const recent = rows.filter((row) => new Date(row.timestamp).getTime() >= recentCutoff).length;
    const prior = rows.filter((row) => {
      const time = new Date(row.timestamp).getTime();
      return time >= priorCutoff && time < recentCutoff;
    }).length;
    const hotspots = new Set(rows.map((row) => row.cluster_id).filter((id) => id != null)).size;
    const high = rows.filter((row) => row.severity === 'HIGH').length;
    const unresolved = rows.filter((row) => row.status !== 'Resolved').length;
    const trend = recent - prior;
    const level = recent === 0 && unresolved === 0 ? 'STABLE' : (hotspots > 0 && (high > 0 || trend > 0) ? 'RISING-RISK' : 'OBSERVED');
    return { area, total: rows.length, recent, prior, trend, hotspots, high, unresolved, level };
  }).sort((a, b) => b.trend - a.trend || b.recent - a.recent || b.unresolved - a.unresolved);
}

export function getCityHealth(complaints = [], clusters = []) {
  if (!complaints.length) return { score: null, label: 'Awaiting data' };
  const unresolved = complaints.filter((row) => row.status !== 'Resolved').length;
  const high = complaints.filter((row) => row.severity === 'HIGH').length;
  const score = Math.max(0, Math.min(100, Math.round(100 - (unresolved / complaints.length) * 42 - (high / complaints.length) * 28 - Math.min(clusters.length * 2, 18))));
  return { score, label: score >= 75 ? 'Stable' : score >= 55 ? 'Watch' : 'Needs attention' };
}

export function severityValue(severity) { return severityWeight[severity] || 0; }
