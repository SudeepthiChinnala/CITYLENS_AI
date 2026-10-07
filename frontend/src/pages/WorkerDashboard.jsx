import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getWorkerDashboard } from '../services/api';

const SUMMARY_CARDS = [
  ['total_assigned', 'Total Assigned', ''],
  ['pending', 'Pending', ''],
  ['accepted', 'Accepted', ''],
  ['work_started', 'Work Started', ''],
  ['in_progress', 'In Progress', 'medium'],
  ['completed', 'Completed', 'low'],
  ['overdue', 'Overdue', 'high'],
];

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

function errorMessage(error) {
  const detail = error?.response?.data?.detail;
  return typeof detail === 'string' ? detail : error?.response ? `Server error (${error.response.status})` : 'Could not reach the CityLens AI backend.';
}

function WorkerDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setError('');
    try { setData(await getWorkerDashboard()); }
    catch (err) { setError(errorMessage(err)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <p className="placeholder">Loading your work queue…</p>;
  if (error) return <div className="error" role="alert">Could not load your work queue: {error}</div>;
  const summary = data?.summary || {};
  const assignments = data?.assignments || [];

  return (
    <div className="worker-dashboard">
      <div className="page-header">
        <div><div className="eyebrow">FIELD OPERATIONS</div><h1>My work queue</h1><div className="sub">{data?.worker?.full_name || 'Worker'} · {data?.worker?.department || 'Assigned city work'}</div></div>
        <button className="btn" type="button" onClick={() => { setLoading(true); load(); }}>Refresh work</button>
      </div>
      <div className="worker-summary-grid">
        {SUMMARY_CARDS.map(([key, label, tone]) => <div className={`stat ${tone}`} key={key}><div className="label">{label}</div><div className="value">{summary[key] ?? 0}</div></div>)}
      </div>
      <section className="panel">
        <div className="workforce-section-heading"><div><span className="eyebrow">ASSIGNED CASES</span><h2>Complaints assigned to you</h2></div><span className="workforce-count">{assignments.length} records</span></div>
        {!assignments.length ? <div className="empty-state"><h2>No assignments yet</h2><p>When an Admin assigns a complaint to you, it will appear here.</p></div> : (
          <div className="table-scroll">
            <table className="workforce-table">
              <thead><tr><th>Complaint</th><th>Area</th><th>Priority</th><th>Work status</th><th>Progress</th><th>Deadline</th><th>Last update</th><th /></tr></thead>
              <tbody>{assignments.map(item => (
                <tr key={item.assignment_id}>
                  <td><strong>#{item.complaint_id}</strong><span className="table-subline">{item.problem_type || 'Civic issue'}</span></td>
                  <td>{item.area || 'Unknown'}</td>
                  <td>{item.priority_score == null ? '—' : Number(item.priority_score).toFixed(1)}</td>
                  <td><span className={`badge worker-status-${String(item.status).toLowerCase().replaceAll(' ', '-')}`}>{item.status}</span>{item.overdue && <span className="worker-overdue-tag">Overdue</span>}</td>
                  <td><div className="work-progress-cell"><span>{item.progress_percentage}%</span><div className="work-progress-track"><span style={{ width: `${item.progress_percentage}%` }} /></div></div></td>
                  <td>{formatDate(item.deadline)}</td>
                  <td>{formatDate(item.last_updated)}</td>
                  <td><Link className="btn" to={`/worker/complaints/${item.complaint_id}`}>Open case</Link></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default WorkerDashboard;
