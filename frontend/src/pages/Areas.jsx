import React, { useEffect, useMemo, useState } from 'react';
import { getAreas, getComplaints } from '../services/api';
import { buildAreaIntelligence } from '../services/areaIntelligence';

const SCORE_COLOR = {
  CRITICAL: 'var(--high)',
  HIGH: 'var(--high)',
  MEDIUM: 'var(--medium)',
  LOW: 'var(--low)',
};

function errorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (error?.response) return `Server error (${error.response.status})`;
  return 'Could not reach the CityLens AI backend. Is it running?';
}

function Areas() {
  const [areas, setAreas] = useState([]);
  const [complaints, setComplaints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.all([getAreas(), getComplaints()])
      .then(([areaData, complaintData]) => {
        if (!active) return;
        setAreas(areaData);
        setComplaints(complaintData);
      })
      .catch(err => {
        if (active) setError(errorMessage(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const recentByArea = useMemo(() => {
    const cutoff = Date.now() - (7 * 24 * 60 * 60 * 1000);
    return complaints.reduce((counts, complaint) => {
      const timestamp = new Date(complaint.timestamp).getTime();
      if (complaint.area && Number.isFinite(timestamp) && timestamp >= cutoff) {
        counts[complaint.area] = (counts[complaint.area] || 0) + 1;
      }
      return counts;
    }, {});
  }, [complaints]);

  const rankedAreas = useMemo(() => buildAreaIntelligence(areas, complaints), [areas, complaints]);

  if (loading) return <p className="placeholder">Loading area rankings…</p>;
  if (error) return <div className="error">Could not load area rankings: {error}</div>;
  if (rankedAreas.length === 0) {
    return <div className="panel"><p className="placeholder">No area ranking data is available yet.</p></div>;
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Area Intelligence &amp; Ranking</h2>
          <div className="sub">Areas requiring the most attention, ranked by the existing CityLens AI area score.</div>
        </div>
      </div>

      <div className="panel">
        <p className="hint area-ranking-note">
          Priority score and tier reuse the existing backend area ranking (complaint volume, high severity, DBSCAN hotspots, and recent activity). Complaint-count criticality uses the same dynamic thresholds as the map. Severity is LOW=1, MEDIUM=2, HIGH=3; high priority means a stored complaint score ≥60 (existing score tier). Recent counts use the last 7 days.
        </p>
        <div className="table-scroll">
          <table className="areas-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Area</th>
                <th>Priority score</th>
                <th>Priority tier</th>
                <th>Count criticality</th>
                <th>Complaints (% max)</th>
                <th>Main problem</th>
                <th>Avg severity / 3</th>
                <th>High severity</th>
                <th>High priority (≥60)</th>
                <th>Avg priority</th>
                <th>Top priority</th>
                <th>Open</th>
                <th>Resolved</th>
                <th>DBSCAN hotspots</th>
                <th>Recent (7d)</th>
              </tr>
            </thead>
            <tbody>
              {rankedAreas.map((area, index) => (
                <tr key={area.area} className={index === 0 ? 'top-area' : ''}>
                  <td>{index + 1}</td>
                  <td><strong>{area.area}</strong></td>
                  <td>
                    <div className="scorebar area-scorebar">
                      <strong>{Number(area.score || 0).toFixed(1)}</strong>
                      <div className="track"><div className="fill" style={{ width: `${Number(area.score) || 0}%`, background: SCORE_COLOR[area.status] || 'var(--brand)' }} /></div>
                    </div>
                  </td>
                  <td><span className={`badge ${area.status}`}>{area.status}</span></td>
                  <td><span className={`badge ${area.criticality}`}>{area.criticality}</span></td>
                  <td>{area.total} ({area.percentageOfMaximum}%)</td>
                  <td>{area.mainProblem}</td>
                  <td>{area.averageSeverity != null ? area.averageSeverity.toFixed(1) : '—'}</td>
                  <td>{area.highSeverityCount}</td>
                  <td>{area.highPriorityCount}</td>
                  <td>{area.averagePriority != null ? area.averagePriority.toFixed(1) : '—'}</td>
                  <td>{area.highestPriority != null ? area.highestPriority.toFixed(1) : '—'}</td>
                  <td>{area.openCount}</td>
                  <td>{area.resolvedCount}</td>
                  <td>{area.hotspots}</td>
                  <td>{recentByArea[area.area] || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default Areas;
