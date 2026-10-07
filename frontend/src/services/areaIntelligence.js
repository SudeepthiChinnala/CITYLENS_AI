import { classifyConcentration } from './criticality';

// The current area score uses 80/60/40 tiers. Apply those same explicit bands
// to stored complaint priority scores; do not recalculate an individual score.
export const PRIORITY_SCORE_THRESHOLD = 60;
const PRIORITY_BANDS = [
  { label: 'Critical (≥80)', minimum: 80 },
  { label: 'High (60–<80)', minimum: 60 },
  { label: 'Medium (40–<60)', minimum: 40 },
  { label: 'Low (<40)', minimum: -Infinity },
];
const SEVERITY_SCORE = { LOW: 1, MEDIUM: 2, HIGH: 3 };
const CRITICALITY_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const CRITICALITY_RANK = Object.fromEntries(CRITICALITY_ORDER.map((level, index) => [level, index]));

function usableScore(value) {
  return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
}

export function buildAreaIntelligence(areaStats, complaints) {
  const complaintsByArea = new Map();
  complaints.forEach(complaint => {
    const name = complaint.area || 'Unknown';
    if (!complaintsByArea.has(name)) complaintsByArea.set(name, []);
    complaintsByArea.get(name).push(complaint);
  });

  const statsByArea = new Map(areaStats.map(area => [area.area, area]));
  const areaNames = new Set([...statsByArea.keys(), ...complaintsByArea.keys()]);
  const maxCount = Math.max(...[...areaNames].map(name => complaintsByArea.get(name)?.length || 0), 0);

  return [...areaNames].map(name => {
    const rows = complaintsByArea.get(name) || [];
    const typeCounts = new Map();
    rows.forEach(row => {
      const type = row.problem_type || 'Unknown';
      typeCounts.set(type, (typeCounts.get(type) || 0) + 1);
    });
    const sortedTypes = [...typeCounts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    const tiedTypes = sortedTypes.length ? sortedTypes.filter(([, count]) => count === sortedTypes[0][1]).map(([type]) => type) : [];
    const severityScores = rows.map(row => SEVERITY_SCORE[row.severity]).filter(Number.isFinite);
    const priorityScores = rows.filter(row => usableScore(row.priority_score)).map(row => Number(row.priority_score));
    const clusterIds = new Set(rows.map(row => row.cluster_id).filter(id => id !== null && id !== undefined));
    const concentration = classifyConcentration(rows.length, maxCount);

    return {
      ...(statsByArea.get(name) || {}),
      area: name,
      total: rows.length,
      percentageOfMaximum: concentration.percentageOfMaximum,
      criticality: concentration.level || 'LOW',
      mainProblem: tiedTypes.length > 1 ? `${tiedTypes.join(' / ')} (tie)` : (tiedTypes[0] || '—'),
      averageSeverity: severityScores.length ? severityScores.reduce((sum, value) => sum + value, 0) / severityScores.length : null,
      highSeverityCount: rows.filter(row => row.severity === 'HIGH').length,
      highPriorityCount: priorityScores.filter(score => score >= PRIORITY_SCORE_THRESHOLD).length,
      averagePriority: priorityScores.length ? priorityScores.reduce((sum, value) => sum + value, 0) / priorityScores.length : null,
      highestPriority: priorityScores.length ? Math.max(...priorityScores) : null,
      openCount: rows.filter(row => row.status !== 'Resolved').length,
      resolvedCount: rows.filter(row => row.status === 'Resolved').length,
      hotspots: clusterIds.size,
    };
  }).sort((a, b) => (
    (Number(b.score) || 0) - (Number(a.score) || 0)
    || b.total - a.total
    || (CRITICALITY_RANK[a.criticality] ?? CRITICALITY_ORDER.length) - (CRITICALITY_RANK[b.criticality] ?? CRITICALITY_ORDER.length)
    || b.highSeverityCount - a.highSeverityCount
    || (b.averageSeverity || 0) - (a.averageSeverity || 0)
    || b.highPriorityCount - a.highPriorityCount
    || (b.averagePriority || 0) - (a.averagePriority || 0)
    || (b.highestPriority || 0) - (a.highestPriority || 0)
    || a.area.localeCompare(b.area)
  ));
}

export function getHotspotLevels(clusters) {
  const maxCount = Math.max(...clusters.map(cluster => Number(cluster?.properties?.count) || 0), 0);
  return clusters.map(cluster => {
    const properties = cluster?.properties || {};
    const concentration = classifyConcentration(properties.count, maxCount);
    return {
      clusterId: properties.cluster_id,
      count: concentration.complaintCount,
      percentageOfMaximum: concentration.percentageOfMaximum,
      level: concentration.level || 'LOW',
    };
  });
}

export function getHotspotDistribution(clusters) {
  const counts = Object.fromEntries(CRITICALITY_ORDER.map(level => [level, 0]));
  getHotspotLevels(clusters).forEach(hotspot => { counts[hotspot.level] += 1; });
  return CRITICALITY_ORDER.map(level => ({ label: level, count: counts[level] }));
}

export function getPriorityDistribution(complaints) {
  const counts = Object.fromEntries(PRIORITY_BANDS.map(band => [band.label, 0]));
  complaints.forEach(complaint => {
    if (!usableScore(complaint.priority_score)) return;
    const score = Number(complaint.priority_score);
    const band = PRIORITY_BANDS.find(item => score >= item.minimum);
    if (band) counts[band.label] += 1;
  });
  return PRIORITY_BANDS.map(({ label }) => ({ label, count: counts[label] }));
}
