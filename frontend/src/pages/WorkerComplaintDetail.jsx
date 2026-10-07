import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { addWorkerProgressUpdate, getComplaintWorkforceProgress } from '../services/api';

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

function errorMessage(error) {
  const detail = error?.response?.data?.detail;
  return typeof detail === 'string' ? detail : error?.response ? `Server error (${error.response.status})` : 'Could not reach the CityLens AI backend.';
}

function nextStatuses(status) {
  if (status === 'Assigned') return ['Accepted'];
  if (status === 'Accepted') return ['Work Started'];
  if (status === 'Work Started') return ['In Progress'];
  if (status === 'In Progress') return ['In Progress', 'Work Completed'];
  return [];
}

function WorkerComplaintDetail() {
  const { complaintId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
  const [status, setStatus] = useState('');
  const [progress, setProgress] = useState(0);
  const [comment, setComment] = useState('');
  const [photo, setPhoto] = useState(null);

  const load = async () => {
    setError('');
    try { setData(await getComplaintWorkforceProgress(complaintId)); }
    catch (err) { setError(errorMessage(err)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [complaintId]);
  const assignment = data?.current_assignment;
  const statuses = useMemo(() => nextStatuses(assignment?.status), [assignment?.status]);

  const changeStage = next => {
    setStatus(next);
    setProgress(next === 'Work Completed' ? 100 : assignment?.progress_percentage || 0);
    setPhoto(null);
    setFormError('');
    const input = document.getElementById('worker-progress-photo');
    if (input) input.value = '';
  };

  const submit = async event => {
    event.preventDefault();
    if (!assignment || !status) return;
    if (status === 'Work Completed' && !photo) {
      setFormError('A completion photo is required before submitting work for Admin verification.');
      return;
    }
    const formData = new FormData();
    formData.append('new_status', status);
    formData.append('progress_percentage', String(status === 'Work Completed' ? 100 : progress));
    formData.append('comment', comment.trim());
    if (photo) formData.append('photo', photo);
    setSaving(true);
    setFormError('');
    try {
      await addWorkerProgressUpdate(assignment.assignment_id, formData);
      setStatus('');
      setComment('');
      setPhoto(null);
      await load();
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p className="placeholder">Loading complaint details…</p>;
  if (error) return <div className="error" role="alert">Could not load this assigned complaint: {error}</div>;
  if (!assignment) return <div className="panel"><p className="placeholder">No assignment details are available for this complaint.</p><Link className="btn" to="/worker">Back to work queue</Link></div>;

  const canUpdate = assignment.active && statuses.length > 0;
  const history = data?.work_updates || [];
  return (
    <div className="worker-case-page">
      <div className="page-header">
        <div><Link className="back-link" to="/worker">← My work queue</Link><div className="eyebrow">COMPLAINT #{data.complaint_id}</div><h1>{assignment.problem_type || 'Civic complaint'}</h1><div className="sub">{assignment.area || 'Unknown area'} · Citizen report status: {assignment.complaint_status}</div></div>
        <span className={`badge worker-status-${String(assignment.status).toLowerCase().replaceAll(' ', '-')}`}>{assignment.status}</span>
      </div>

      <section className="panel worker-case-summary">
        <div className="detail-grid">
          <div><span className="label">Assigned</span><strong>{formatDate(assignment.assigned_at)}</strong></div>
          <div><span className="label">Deadline</span><strong>{formatDate(assignment.deadline)}{assignment.overdue ? ' · Overdue' : ''}</strong></div>
          <div><span className="label">Severity</span><strong>{assignment.severity || '—'}</strong></div>
          <div><span className="label">Priority</span><strong>{assignment.priority_score == null ? '—' : Number(assignment.priority_score).toFixed(1)}</strong></div>
          <div><span className="label">Location</span><strong>{assignment.latitude}, {assignment.longitude}</strong></div>
          <div><span className="label">Progress</span><strong>{assignment.progress_percentage}%</strong></div>
        </div>
        <p className="worker-case-description">{assignment.description || 'No description provided.'}</p>
        {assignment.image_url && <img className="complaint-image worker-original-image" src={assignment.image_url} alt={`Original citizen report for complaint ${data.complaint_id}`} />}
        <div className="work-progress-track work-progress-large"><span style={{ width: `${assignment.progress_percentage}%` }} /></div>
        <div className="work-progress-caption">{assignment.progress_percentage}% complete</div>
      </section>

      {canUpdate && <form className="panel form worker-update-form" onSubmit={submit}>
        <div className="workforce-section-heading"><div><span className="eyebrow">FIELD UPDATE</span><h2>Record work progress</h2></div></div>
        <div className="field"><label htmlFor="worker-work-status">Next work stage</label>
          <select id="worker-work-status" value={status} onChange={event => changeStage(event.target.value)} required>
            <option value="">Select next stage</option>
            {statuses.map(next => <option value={next} key={next}>{next}</option>)}
          </select>
        </div>
        {status && <>
          <div className="field"><label htmlFor="worker-progress">Progress percentage</label>
            <input id="worker-progress" type="number" min={assignment.progress_percentage} max={status === 'Work Completed' ? 100 : 99} value={status === 'Work Completed' ? 100 : progress} disabled={status === 'Work Completed' || status === 'Accepted'} onChange={event => setProgress(Number(event.target.value))} required />
            {status === 'Work Completed' && <div className="hint-sm">Completion is submitted at 100% and requires a photo.</div>}
          </div>
          <div className="field"><label htmlFor="worker-update-comment">Work note</label><textarea id="worker-update-comment" rows={3} maxLength={2000} value={comment} onChange={event => setComment(event.target.value)} placeholder="Describe the work carried out or the next action…" /></div>
          <div className="field"><label htmlFor="worker-progress-photo">Evidence photo {status === 'Work Completed' ? '(required)' : '(optional)'}</label>
            <input id="worker-progress-photo" type="file" accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp" required={status === 'Work Completed'} onChange={event => {
              const selected = event.target.files?.[0] || null;
              if (selected && selected.size > 10 * 1024 * 1024) { setPhoto(null); setFormError('Evidence photos must be 10 MB or smaller.'); event.target.value = ''; }
              else { setPhoto(selected); setFormError(''); }
            }} />
            <div className="hint-sm">JPG, PNG, or WEBP; up to 10 MB. Completion photos are sent to Admin for verification.</div>
          </div>
        </>}
        {formError && <div className="error" role="alert">{formError}</div>}
        <button className="btn primary" type="submit" disabled={!status || saving}>{saving ? 'Saving update…' : 'Submit work update'}</button>
      </form>}
      {!canUpdate && <div className="panel worker-verification-note"><strong>{assignment.status === 'Work Completed' ? 'Submitted for Admin verification' : 'This assignment is no longer active.'}</strong><p>{assignment.status === 'Work Completed' ? 'The authority will review your completion evidence before the complaint is marked resolved.' : 'You can still review the recorded work history below.'}</p></div>}

      <section className="panel worker-history-panel">
        <div className="workforce-section-heading"><div><span className="eyebrow">RECORDED HISTORY</span><h2>Progress updates</h2></div><button className="btn" type="button" onClick={() => { setLoading(true); load(); }}>Refresh</button></div>
        {!history.length ? <p className="placeholder">No work-progress updates have been recorded yet.</p> : <ol className="worker-history-list">
          {history.map(item => <li key={item.id}>
            <div className="worker-history-marker" />
            <div className="worker-history-content"><div className="worker-history-heading"><strong>{item.status}</strong><time>{formatDate(item.created_at)}</time></div><div className="worker-history-progress">{item.progress_percentage}% complete</div>{item.comment && <p>{item.comment}</p>}{item.photo_url && <a className="citizen-evidence-link" href={item.photo_url} target="_blank" rel="noreferrer"><img src={item.photo_url} alt={`Work evidence for complaint ${data.complaint_id}`} loading="lazy" /><span>View evidence photo</span></a>}</div>
          </li>)}
        </ol>}
      </section>
    </div>
  );
}

export default WorkerComplaintDetail;
