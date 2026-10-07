import React, { useEffect, useMemo, useState } from 'react';
import { getClusters, getComplaints, getSummary } from '../services/api';
import { getHotspotDistribution, getPriorityDistribution } from '../services/areaIntelligence';

const SEVERITY_ORDER = ['HIGH', 'MEDIUM', 'LOW'];
const STATUS_ORDER = ['Reported', 'Under Review', 'In Progress', 'Resolved', 'Assigned'];

function errorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (error?.response) return `Server error (${error.response.status})`;
  return 'Could not reach the CityLens AI backend. Is it running?';
}

function countBy(complaints, field) {
  return complaints.reduce((counts, complaint) => {
    const value = complaint[field] || 'Unknown';
    counts[value] = (counts[value] || 0) + 1;
    return counts;
  }, {});
}

function orderedItems(counts, preferredOrder = []) {
  const preferred = preferredOrder
    .filter(label => counts[label] != null)
    .map(label => ({ label, count: counts[label] }));
  const remaining = Object.entries(counts)
    .filter(([label]) => !preferredOrder.includes(label))
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
  return [...preferred, ...remaining];
}

function BarList({ title, items, colorClass }) {
  const max = Math.max(...items.map(item => item.count), 1);
  return (
    <div className="analytics-card">
      <h3>{title}</h3>
      {items.length === 0 ? <p className="placeholder">No data available.</p> : (
        <div className="analytics-bars">
          {items.map(item => (
            <div className="analytics-bar-row" key={item.label}>
              <div className="analytics-bar-head">
                <span>{item.label}</span><strong>{item.count}</strong>
              </div>
              <div className="analytics-bar-track">
                <div className={`analytics-bar-fill ${colorClass}`} style={{ width: `${(item.count / max) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Analytics() {
  const [summary, setSummary] = useState(null);
  const [complaints, setComplaints] = useState([]);
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.all([getSummary(), getComplaints(), getClusters()])
      .then(([summaryData, complaintData, clusterData]) => {
        if (!active) return;
        setSummary(summaryData);
        setComplaints(complaintData);
        setClusters(clusterData);
      })
      .catch(err => {
        if (active) setError(errorMessage(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const analytics = useMemo(() => {
    const statusCounts = countBy(complaints, 'status');
    STATUS_ORDER.forEach(status => { statusCounts[status] = statusCounts[status] || 0; });
    return {
      problemTypes: orderedItems(countBy(complaints, 'problem_type')),
      severity: orderedItems(countBy(complaints, 'severity'), SEVERITY_ORDER),
      status: orderedItems(statusCounts, STATUS_ORDER),
      areas: orderedItems(countBy(complaints, 'area')),
      priority: getPriorityDistribution(complaints),
      hotspots: getHotspotDistribution(clusters),
    };
  }, [complaints, clusters]);

  if (loading) return <p className="placeholder">Loading analytics…</p>;
  if (error) return <div className="error">Could not load analytics: {error}</div>;
  if (complaints.length === 0) {
    return <div className="panel"><p className="placeholder">No complaint data is available for analytics yet.</p></div>;
  }

  const total = summary?.total_complaints ?? complaints.length;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Analytics</h2>
          <div className="sub">Current complaint records, stored priority scores, and DBSCAN hotspot criticality.</div>
        </div>
      </div>

      <div className="analytics-total">
        <div className="stat"><div className="label">Total Complaints</div><div className="value">{total}</div></div>
      </div>

      <div className="analytics-grid">
        <BarList title="Complaints by Problem Type" items={analytics.problemTypes} colorClass="problem-fill" />
        <BarList title="Complaints by Severity" items={analytics.severity} colorClass="severity-fill" />
        <BarList title="Complaints by Status" items={analytics.status} colorClass="status-fill" />
        <BarList title="Complaints by Area" items={analytics.areas} colorClass="area-fill" />
        <BarList title="Stored Priority Scores" items={analytics.priority} colorClass="severity-fill" />
        <BarList title="DBSCAN Hotspots by Criticality" items={analytics.hotspots} colorClass="status-fill" />
      </div>
    </div>
  );
}

export default Analytics;
