const CRITICALITY_THRESHOLDS = {
  HIGH: 60,
  MEDIUM: 25,
};

/** Classify a count relative to the maximum count in the same dataset. */
export function classifyConcentration(count, maximum) {
  const complaintCount = Number.isFinite(Number(count)) ? Math.max(0, Number(count)) : 0;
  const maxCount = Number.isFinite(Number(maximum)) ? Math.max(0, Number(maximum)) : 0;

  if (maxCount === 0) {
    return { complaintCount, percentageOfMaximum: 0, level: null };
  }

  const exactPercentage = Math.min(100, (complaintCount / maxCount) * 100);
  const percentageOfMaximum = Math.round(exactPercentage * 10) / 10;
  let level = 'LOW';
  if (complaintCount >= maxCount) level = 'CRITICAL';
  else if (exactPercentage >= CRITICALITY_THRESHOLDS.HIGH) level = 'HIGH';
  else if (exactPercentage >= CRITICALITY_THRESHOLDS.MEDIUM) level = 'MEDIUM';

  return { complaintCount, percentageOfMaximum, level };
}
