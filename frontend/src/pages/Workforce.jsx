import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { createWorker, getWorkerProfile, getWorkers, getWorkforceSummary, updateWorkerAccountStatus } from '../services/api';

const METRICS = [
  ['total_workers', 'Total Workers', ''],
  ['active_workers', 'Active Workers', 'low'],
  ['total_assigned', 'Total Assigned', ''],
  ['active', 'Active Work', 'medium'],
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

function Workforce() {
  const { workerId } = useParams();
  const [summary, setSummary] = useState(null);
  const [workers, setWorkers] = useState([]);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
  const [success, setSuccess] = useState('');
  const [saving, setSaving] = useState(false);
  const [workerForm, setWorkerForm] = useState({ worker_id: '', full_name: '', phone: '', department: '', password: '' });

  const load = async () => {
    setError('');
    try {
      const [metrics, people] = await Promise.all([getWorkforceSummary(), getWorkers()]);
      setSummary(metrics);
      setWorkers(people);
      if (workerId) setProfile(await getWorkerProfile(workerId));
      else setProfile(null);
    } catch (err) { setError(errorMessage(err)); }
    finally { setLoading(false); }
  };

  useEffect(() => { setLoading(true); setProfile(null); load(); }, [workerId]);

  const create = async event => {
    event.preventDefault();
    setSaving(true);
    setFormError('');
    setSuccess('');
    try {
      const created = await createWorker(workerForm);
      setWorkers(current => [...current, created].sort((a, b) => a.full_name.localeCompare(b.full_name)));
      setWorkerForm({ worker_id: '', full_name: '', phone: '', department: '', password: '' });
      setSuccess(`Worker account ${created.worker_id} was created.`);
      const metrics = await getWorkforceSummary();
      setSummary(metrics);
    } catch (err) { setFormError(errorMessage(err)); }
    finally { setSaving(false); }
  };

  const toggleStatus = async () => {
    if (!profile) return;
    setSaving(true);
    setError('');
    try {
      await updateWorkerAccountStatus(profile.worker_id, profile.account_status === 'active' ? 'suspended' : 'active');
      await load();
    } catch (err) { setError(errorMessage(err)); }
    finally { setSaving(false); }
  };

  if (loading) return <p className="placeholder">Loading workforce…</p>;
  if (workerId && error && !profile) return <div className="error" role="alert">Could not load this worker profile: {error}</div>;
  if (error && !workers.length && !profile) return <div className="error" role="alert">Could not load workforce: {error}</div>;

  return (
    <div className="workforce-page">
      <div className="page-header"><div><div className="eyebrow">FIELD OPERATIONS</div><h1>{profile ? 'Worker profile' : 'Workforce'}</h1><div className="sub">Manage field-worker accounts, assignments, workload and completion history.</div></div><button className="btn" type="button" onClick={() => { setLoading(true); load(); }}>Refresh</button></div>
      {error && <div className="error" role="alert">{error}</div>}
      <div className="workforce-metrics-grid">{METRICS.map(([key, label, tone]) => <div className={`stat ${tone}`} key={key}><div className="label">{label}</div><div className="value">{summary?.[key] ?? 0}</div></div>)}</div>

      {profile ? <>
        <div className="workforce-profile-header panel">
          <div><Link to="/admin/workforce" className="back-link">← All workers</Link><h2>{profile.full_name}</h2><p>{profile.department} · Worker ID <strong>{profile.worker_id}</strong></p><p>{profile.phone || 'No phone on file'} · Created {formatDate(profile.created_at)}</p></div>
          <div className="workforce-profile-actions"><span className={`badge ${profile.account_status === 'active' ? 'LOW' : 'HIGH'}`}>{profile.account_status}</span><button className="btn" type="button" onClick={toggleStatus} disabled={saving}>{profile.account_status === 'active' ? 'Suspend account' : 'Reactivate account'}</button></div>
        </div>
        <div className="worker-profile-stats">
          {[[profile.total_assigned, 'Currently assigned'], [profile.active, 'Active work'], [profile.pending, 'Pending'], [profile.accepted, 'Accepted'], [profile.work_started, 'Work started'], [profile.in_progress, 'In progress'], [profile.completed, 'Completed'], [profile.overdue, 'Overdue']].map(([value, label]) => <div className="worker-profile-stat" key={label}><strong>{value}</strong><span>{label}</span></div>)}
        </div>
        <section className="panel"><div className="workforce-section-heading"><div><span className="eyebrow">ASSIGNMENT HISTORY</span><h2>Complaints assigned to {profile.full_name}</h2></div><span className="workforce-count">{profile.assignments?.length || 0} records</span></div>
          {!profile.assignments?.length ? <p className="placeholder">No complaint assignments recorded.</p> : <div className="table-scroll"><table className="workforce-table"><thead><tr><th>Complaint</th><th>Area</th><th>Assigned</th><th>Deadline</th><th>Work status</th><th>Progress</th><th>Priority</th><th>Assignment</th></tr></thead><tbody>{profile.assignments.map(item => <tr key={item.assignment_id}><td><strong>#{item.complaint_id}</strong><span className="table-subline">{item.problem_type || 'Civic issue'}</span></td><td>{item.area || 'Unknown'}</td><td>{formatDate(item.assigned_at)}</td><td>{formatDate(item.deadline)}</td><td><span className={`badge worker-status-${String(item.status).toLowerCase().replaceAll(' ', '-')}`}>{item.status}</span></td><td>{item.progress_percentage}%</td><td>{item.priority_score == null ? '—' : Number(item.priority_score).toFixed(1)}</td><td>{item.active ? 'Current' : 'History'}</td></tr>)}</tbody></table></div>}
        </section>
      </> : <div className="workforce-admin-grid">
        <section className="panel workforce-create-panel"><div className="workforce-section-heading"><div><span className="eyebrow">ACCOUNT MANAGEMENT</span><h2>Create worker account</h2></div></div><p className="hint">Worker accounts are created by Admin only. The password is stored as a one-way verifier and is never returned by the API.</p>
          {success && <div className="field-ok" role="status">{success}</div>}{formError && <div className="error" role="alert">{formError}</div>}
          <form className="form" onSubmit={create}>
            <div className="field"><label htmlFor="worker-id">Worker ID</label><input id="worker-id" minLength={3} maxLength={32} value={workerForm.worker_id} onChange={e => setWorkerForm(current => ({ ...current, worker_id: e.target.value }))} autoComplete="off" required /></div>
            <div className="field"><label htmlFor="worker-name">Full name</label><input id="worker-name" maxLength={120} value={workerForm.full_name} onChange={e => setWorkerForm(current => ({ ...current, full_name: e.target.value }))} autoComplete="off" required /></div>
            <div className="field"><label htmlFor="worker-phone">Phone (optional)</label><input id="worker-phone" maxLength={30} value={workerForm.phone} onChange={e => setWorkerForm(current => ({ ...current, phone: e.target.value }))} autoComplete="off" /></div>
            <div className="field"><label htmlFor="worker-department">Department / specialization</label><input id="worker-department" maxLength={120} value={workerForm.department} onChange={e => setWorkerForm(current => ({ ...current, department: e.target.value }))} autoComplete="organization-title" required /></div>
            <div className="field"><label htmlFor="worker-password">Initial password</label><input id="worker-password" type="password" minLength={8} maxLength={128} value={workerForm.password} onChange={e => setWorkerForm(current => ({ ...current, password: e.target.value }))} autoComplete="new-password" required /><div className="hint-sm">At least 8 characters. Provide it to the worker through your normal secure channel.</div></div>
            <button className="btn primary" type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create worker account'}</button>
          </form>
        </section>
        <section className="panel workforce-list-panel"><div className="workforce-section-heading"><div><span className="eyebrow">WORKER DIRECTORY</span><h2>Worker profiles</h2></div><span className="workforce-count">{workers.length} accounts</span></div>
          {!workers.length ? <p className="placeholder">No worker accounts yet. Create the first field account.</p> : <div className="workforce-worker-list">{workers.map(worker => <Link className="workforce-worker-card" to={`/admin/workforce/${encodeURIComponent(worker.worker_id)}`} key={worker.worker_id}><div className="workforce-worker-avatar">{worker.full_name.slice(0, 1).toUpperCase()}</div><div className="workforce-worker-copy"><strong>{worker.full_name}</strong><span>{worker.worker_id} · {worker.department}</span><small>{worker.total_assigned} assigned · {worker.completed} completed · {worker.overdue} overdue</small></div><span className={`badge ${worker.account_status === 'active' ? 'LOW' : 'HIGH'}`}>{worker.account_status}</span></Link>)}</div>}
        </section>
      </div>}
    </div>
  );
}

export default Workforce;
