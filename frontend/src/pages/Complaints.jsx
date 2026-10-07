import React, { useEffect, useMemo, useState } from 'react';
import { addComplaintWorkUpdate, assignComplaintToWorker, getComplaintWorkUpdates, getComplaintWorkforceProgress, getComplaints, getImpactPriority, getResolutionConfirmation, getWorkers, updateComplaintStatus, verifyWorkerCompletion } from '../services/api';

const STATUS_OPTIONS = ['Reported', 'Under Review', 'In Progress', 'Resolved', 'Assigned'];

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

function errorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (error?.response) return `Server error (${error.response.status})`;
  return 'Could not reach the CityLens AI backend. Is it running?';
}

function WorkforceAssignmentPanel({ complaint, onStatusChange }) {
  const [workers, setWorkers] = useState([]);
  const [progress, setProgress] = useState(null);
  const [workerId, setWorkerId] = useState('');
  const [deadline, setDeadline] = useState('');
  const [assignmentNote, setAssignmentNote] = useState('');
  const [verificationNote, setVerificationNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = async () => {
    setError('');
    try {
      const [people, data] = await Promise.all([getWorkers(), getComplaintWorkforceProgress(complaint.id)]);
      setWorkers(people.filter(worker => worker.account_status === 'active'));
      setProgress(data);
    } catch (err) { setError(errorMessage(err)); }
    finally { setLoading(false); }
  };

  useEffect(() => { setLoading(true); load(); }, [complaint.id]);

  const assign = async event => {
    event.preventDefault();
    if (!workerId) return;
    setSaving(true); setError(''); setSuccess('');
    try {
      const assigned = await assignComplaintToWorker(complaint.id, {
        worker_id: workerId,
        deadline: deadline ? new Date(deadline).toISOString() : null,
        note: assignmentNote.trim() || null,
      });
      setSuccess(`Complaint assigned to ${assigned.worker_name}.`);
      setWorkerId(''); setDeadline(''); setAssignmentNote('');
      onStatusChange('Assigned');
      await load();
    } catch (err) { setError(errorMessage(err)); }
    finally { setSaving(false); }
  };

  const verify = async () => {
    setSaving(true); setError(''); setSuccess('');
    try {
      await verifyWorkerCompletion(complaint.id, verificationNote.trim() || null);
      setVerificationNote('');
      setSuccess('Worker completion verified. The complaint is now awaiting Citizen confirmation.');
      onStatusChange('Resolved');
      await load();
    } catch (err) { setError(errorMessage(err)); }
    finally { setSaving(false); }
  };

  const current = progress?.current_assignment;
  const timeline = (progress?.timeline || []).filter(item => item.event_type === 'assignment' || item.event_type === 'worker_update');
  return (
    <section className="workforce-assignment-panel" aria-label="Worker assignment and progress">
      <div className="workforce-section-heading"><div><span className="eyebrow">FIELD WORKFORCE</span><h4>Assignment &amp; work progress</h4></div>{current && <span className={`badge worker-status-${String(current.status).toLowerCase().replaceAll(' ', '-')}`}>{current.status}</span>}</div>
      {loading && <p className="placeholder">Loading assignment history…</p>}
      {current && <div className="workforce-current-assignment">
        <div><span>Current / latest worker</span><strong>{current.worker_name} · {current.department}</strong></div>
        <div><span>Worker ID · contact</span><strong>{current.worker_id} · {current.worker_phone || 'No phone on file'}</strong></div>
        <div><span>Assigned</span><strong>{formatDate(current.assigned_at)}</strong></div>
        <div><span>Deadline</span><strong>{formatDate(current.deadline)}{current.overdue ? ' · Overdue' : ''}</strong></div>
        <div><span>Progress</span><strong>{current.progress_percentage}% · {current.active ? 'Current assignment' : 'Historical assignment'}</strong></div>
        {current.assignment_note && <p className="workforce-assignment-note">Assignment note: {current.assignment_note}</p>}
      </div>}
      {!current && !loading && <p className="placeholder">No worker has been assigned to this complaint.</p>}
      {current?.status === 'Work Completed' && current.active && <div className="workforce-verify-box">
        <p>The worker submitted completion evidence. Verify the photo and work history above before marking this complaint Resolved.</p>
        <div className="field"><label htmlFor={`verification-note-${complaint.id}`}>Citizen-facing resolution note (optional)</label><input id={`verification-note-${complaint.id}`} value={verificationNote} maxLength={2000} onChange={event => setVerificationNote(event.target.value)} placeholder="Leave blank to use the worker's completion note" /></div>
        <button className="btn primary" type="button" disabled={saving} onClick={verify}>{saving ? 'Verifying…' : 'Verify completion & request Citizen confirmation'}</button>
      </div>}
      <details className="workforce-history-details" open={!!timeline.length}>
        <summary>Assignment and progress history ({timeline.length})</summary>
        {!timeline.length ? <p className="placeholder">No worker assignment history recorded.</p> : <ol className="worker-history-list">{timeline.map(item => <li key={item.event_id}><div className="worker-history-marker" /><div className="worker-history-content"><div className="worker-history-heading"><strong>{item.event_type === 'assignment' ? `Assigned to ${item.worker_name}` : item.status}</strong><time>{formatDate(item.created_at)}</time></div>{item.department && <div className="worker-history-progress">{item.department}{item.event_type === 'worker_update' ? ` · ${item.progress_percentage}% complete` : ''}</div>}{item.message && <p>{item.message}</p>}{item.photo_url && <a className="resolution-admin-photo" href={item.photo_url} target="_blank" rel="noreferrer">View work evidence photo</a>}{item.authenticity_status && <div className="authenticity-result"><strong>Photo Authenticity Check</strong><p>{item.authenticity_status}</p></div>}{item.file_hash && <details className="evidence-metadata"><summary>Worker photo hash and metadata</summary><code>SHA-256: {item.file_hash}</code><pre>{item.metadata_summary || 'No additional metadata summary.'}</pre></details>}</div></li>)}</ol>}
      </details>
      <form className="form workforce-assign-form" onSubmit={assign}>
        <h5>{current?.active ? 'Reassign complaint' : 'Assign complaint to a worker'}</h5>
        {!workers.length && <p className="placeholder">No active worker accounts are available. Create or reactivate a worker in Workforce management.</p>}
        <div className="workforce-assignment-form-grid">
          <div className="field"><label htmlFor={`assign-worker-${complaint.id}`}>Worker</label><select id={`assign-worker-${complaint.id}`} value={workerId} onChange={event => setWorkerId(event.target.value)} required><option value="">Select an active worker</option>{workers.map(worker => <option key={worker.worker_id} value={worker.worker_id}>{worker.full_name} · {worker.department}</option>)}</select></div>
          <div className="field"><label htmlFor={`assign-deadline-${complaint.id}`}>Deadline (optional)</label><input id={`assign-deadline-${complaint.id}`} type="datetime-local" value={deadline} onChange={event => setDeadline(event.target.value)} /></div>
        </div>
        <div className="field"><label htmlFor={`assign-note-${complaint.id}`}>Assignment note</label><textarea id={`assign-note-${complaint.id}`} rows={2} maxLength={1000} value={assignmentNote} onChange={event => setAssignmentNote(event.target.value)} placeholder="Provide scope or access details for the assigned worker…" /></div>
        {error && <div className="error" role="alert">{error}</div>}{success && <div className="field-ok" role="status">{success}</div>}
        <button className="btn" type="submit" disabled={!workerId || saving || !workers.length}>{saving ? 'Saving…' : current?.active ? 'Reassign to selected worker' : 'Assign worker'}</button>
      </form>
    </section>
  );
}

function Complaints() {
  const [complaints, setComplaints] = useState([]);
  const [problemFilter, setProblemFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [updatingId, setUpdatingId] = useState(null);
  const [selectedComplaint, setSelectedComplaint] = useState(null);
  const [workUpdates, setWorkUpdates] = useState([]);
  const [loadingWorkUpdates, setLoadingWorkUpdates] = useState(false);
  const [workStatus, setWorkStatus] = useState('');
  const [workMessage, setWorkMessage] = useState('');
  const [workPhoto, setWorkPhoto] = useState(null);
  const [workError, setWorkError] = useState('');
  const [workSuccess, setWorkSuccess] = useState('');
  const [impactPriority, setImpactPriority] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [impactError, setImpactError] = useState('');
  const [resolutionConfirmation, setResolutionConfirmation] = useState(null);
  const [resolutionConfirmationLoading, setResolutionConfirmationLoading] = useState(false);
  const [resolutionConfirmationError, setResolutionConfirmationError] = useState('');

  useEffect(() => {
    let active = true;
    getComplaints()
      .then(data => {
        if (active) setComplaints(data);
      })
      .catch(err => {
        if (active) setError(errorMessage(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selectedComplaint) {
      setImpactPriority(null);
      setImpactError('');
      return undefined;
    }
    let active = true;
    setImpactPriority(null);
    setImpactError('');
    setImpactLoading(true);
    getImpactPriority(selectedComplaint.id)
      .then(data => { if (active) setImpactPriority(data); })
      .catch(err => { if (active) setImpactError(errorMessage(err)); })
      .finally(() => { if (active) setImpactLoading(false); });
    return () => { active = false; };
  }, [selectedComplaint?.id]);

  useEffect(() => {
    if (!selectedComplaint) {
      setResolutionConfirmation(null);
      setResolutionConfirmationError('');
      return undefined;
    }
    let active = true;
    setResolutionConfirmation(null);
    setResolutionConfirmationError('');
    setResolutionConfirmationLoading(true);
    getResolutionConfirmation(selectedComplaint.id)
      .then(data => { if (active) setResolutionConfirmation(data); })
      .catch(err => { if (active) setResolutionConfirmationError(errorMessage(err)); })
      .finally(() => { if (active) setResolutionConfirmationLoading(false); });
    return () => { active = false; };
  }, [selectedComplaint?.id, selectedComplaint?.status]);

  const problemTypes = useMemo(() => (
    [...new Set(complaints.map(c => c.problem_type).filter(Boolean))].sort()
  ), [complaints]);

  const filteredComplaints = useMemo(() => complaints.filter(complaint => (
    (!problemFilter || complaint.problem_type === problemFilter) &&
    (!statusFilter || complaint.status === statusFilter)
  )), [complaints, problemFilter, statusFilter]);

  const changeStatus = async (complaintId, status) => {
    setUpdatingId(complaintId);
    setActionError('');
    try {
      const updated = await updateComplaintStatus(complaintId, status);
      setComplaints(current => current.map(complaint => (
        complaint.id === complaintId ? updated : complaint
      )));
      setSelectedComplaint(updated);
    } catch (err) {
      setActionError(`Could not update complaint #${complaintId}: ${errorMessage(err)}`);
    } finally {
      setUpdatingId(null);
    }
  };

  const openComplaint = async (complaint, requestedStatus = '') => {
    setSelectedComplaint(complaint);
    setWorkStatus(requestedStatus);
    setWorkMessage('');
    setWorkPhoto(null);
    const evidenceInput = document.getElementById('authority-evidence-photo');
    if (evidenceInput) evidenceInput.value = '';
    setWorkError('');
    setWorkSuccess('');
    setWorkUpdates([]);
    setLoadingWorkUpdates(true);
    try {
      setWorkUpdates(await getComplaintWorkUpdates(complaint.id));
    } catch (err) {
      setWorkError(`Could not load authority work updates: ${errorMessage(err)}`);
    } finally {
      setLoadingWorkUpdates(false);
    }
  };

  const handleStatusSelection = (complaint, nextStatus) => {
    if (nextStatus === 'In Progress' || nextStatus === 'Resolved') {
      openComplaint(complaint, nextStatus);
      return;
    }
    changeStatus(complaint.id, nextStatus);
  };

  const submitWorkUpdate = async event => {
    event.preventDefault();
    if (!selectedComplaint || !workStatus) return;
    if (workStatus === 'Resolved' && !workPhoto) {
      setWorkError('A completion photo is required before resolving this complaint.');
      return;
    }
    setUpdatingId(selectedComplaint.id);
    setWorkError('');
    setWorkSuccess('');
    const formData = new FormData();
    formData.append('status', workStatus);
    formData.append('message', workMessage.trim());
    if (workPhoto) formData.append('photo', workPhoto);
    try {
      const saved = await addComplaintWorkUpdate(selectedComplaint.id, formData);
      setWorkUpdates(current => [...current, saved]);
      setComplaints(current => current.map(complaint => (
        complaint.id === selectedComplaint.id ? { ...complaint, status: saved.status } : complaint
      )));
      setSelectedComplaint(current => current ? { ...current, status: saved.status } : current);
      setWorkStatus('');
      setWorkMessage('');
      setWorkPhoto(null);
      const input = document.getElementById('authority-evidence-photo');
      if (input) input.value = '';
      setWorkSuccess('Authority work update saved.');
    } catch (err) {
      setWorkError(`Could not save the authority work update: ${errorMessage(err)}`);
    } finally {
      setUpdatingId(null);
    }
  };

  if (loading) return <p className="placeholder">Loading complaints…</p>;
  if (error) return <div className="error">Could not load complaints: {error}</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>All Complaints</h2>
          <div className="sub">Review reported urban problems, open details, and update status.</div>
        </div>
      </div>

      <div className="panel">
        <div className="complaints-toolbar">
          <div className="filter-field">
            <label htmlFor="problem-filter">Problem type</label>
            <select id="problem-filter" value={problemFilter} onChange={e => setProblemFilter(e.target.value)}>
              <option value="">All problem types</option>
              {problemTypes.map(type => <option key={type} value={type}>{type}</option>)}
            </select>
          </div>
          <div className="filter-field">
            <label htmlFor="status-filter">Status</label>
            <select id="status-filter" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              {STATUS_OPTIONS.map(status => <option key={status} value={status}>{status === 'Assigned' ? 'Assigned (legacy)' : status}</option>)}
            </select>
          </div>
          <div className="complaints-count">Showing {filteredComplaints.length} of {complaints.length}</div>
        </div>
        {actionError && <div className="error">{actionError}</div>}
      </div>

      {selectedComplaint && (
        <div className="panel complaint-detail">
          <div className="detail-header">
            <h3>Complaint #{selectedComplaint.id}</h3>
            <button className="btn" type="button" onClick={() => { setSelectedComplaint(null); setWorkStatus(''); setWorkUpdates([]); }}>Close</button>
          </div>
          <div className="detail-grid">
            <div><span className="label">Problem type</span><strong>{selectedComplaint.problem_type || '—'}</strong></div>
            <div><span className="label">Citizen ID</span><strong>{selectedComplaint.citizen_id || 'Legacy / unlinked'}</strong></div>
            <div><span className="label">Complainant</span><strong>{selectedComplaint.citizen_name || 'Legacy / account not registered'}</strong></div>
            <div><span className="label">Email</span><strong>{selectedComplaint.citizen_email || '—'}</strong></div>
            <div><span className="label">Phone</span><strong>{selectedComplaint.citizen_phone || '—'}</strong></div>
            <div><span className="label">Area</span><strong>{selectedComplaint.area || 'Unknown'}</strong></div>
            <div><span className="label">Severity</span><strong>{selectedComplaint.severity || '—'}</strong></div>
            <div><span className="label">Existing CityLens priority</span><strong>{selectedComplaint.priority_score != null ? selectedComplaint.priority_score.toFixed(1) : '—'}</strong></div>
            <div><span className="label">Status</span><strong><span className="badge status">{selectedComplaint.status || '—'}</span></strong></div>
            <div><span className="label">AI confidence</span><strong>{selectedComplaint.ai_detected && Number.isFinite(selectedComplaint.confidence) ? `${Math.round(selectedComplaint.confidence * 100)}%` : '—'}</strong></div>
            <div><span className="label">Coordinates</span><strong>{selectedComplaint.latitude}, {selectedComplaint.longitude}</strong></div>
            <div><span className="label">Date/time</span><strong>{formatDate(selectedComplaint.timestamp)}</strong></div>
          </div>
          <p><span className="label">Description</span><br />{selectedComplaint.description || 'No description provided.'}</p>
          {selectedComplaint.image_url && <img className="complaint-image" src={selectedComplaint.image_url} alt={`Complaint ${selectedComplaint.id}`} />}
          <WorkforceAssignmentPanel complaint={selectedComplaint} onStatusChange={status => {
            setComplaints(current => current.map(item => item.id === selectedComplaint.id ? { ...item, status } : item));
            setSelectedComplaint(current => current ? { ...current, status } : current);
          }} />
          <section className={`resolution-confirmation-admin${resolutionConfirmation?.resolution_status === 'unresolved' ? ' is-unresolved' : ''}`} aria-label="Citizen Resolution Confirmation" aria-live="polite">
            <div className="resolution-confirmation-heading"><div><span className="eyebrow">RESOLUTION VERIFICATION</span><h4>Citizen Resolution Confirmation</h4></div>
              {resolutionConfirmation?.resolution_status === 'awaiting' && <span className="confirmation-state awaiting">Awaiting response</span>}
              {resolutionConfirmation?.resolution_status === 'confirmed' && <span className="confirmation-state confirmed">Confirmed fixed</span>}
              {resolutionConfirmation?.resolution_status === 'unresolved' && <span className="confirmation-state unresolved">Citizen says still unresolved</span>}
            </div>
            {resolutionConfirmationLoading && <p className="placeholder">Loading citizen confirmation…</p>}
            {resolutionConfirmationError && <div className="error" role="alert">Could not load citizen confirmation: {resolutionConfirmationError}</div>}
            {resolutionConfirmation && <>
              {!['awaiting', 'confirmed', 'unresolved'].includes(resolutionConfirmation.resolution_status) && <p className="resolution-confirmation-note">{resolutionConfirmation.resolution_status === 'evidence_unavailable' ? 'The latest completion evidence file is unavailable.' : resolutionConfirmation.resolution_status === 'not_pending' ? 'This complaint is not currently awaiting confirmation.' : 'No linked resolution-evidence cycle is available for this complaint.'}</p>}
              {resolutionConfirmation.resolution_status === 'awaiting' && <p className="resolution-confirmation-note">The complaint is resolved and awaiting the reporting citizen’s response.</p>}
              {resolutionConfirmation.resolution_status === 'confirmed' && <p className="resolution-confirmation-success">Citizen confirmed this resolution{resolutionConfirmation.responded_at ? ` on ${formatDate(resolutionConfirmation.responded_at)}` : ''}.</p>}
              {resolutionConfirmation.resolution_status === 'unresolved' && <p className="resolution-confirmation-warning">The citizen reported that the problem is still present. The complaint has been reopened as <strong>{resolutionConfirmation.complaint_status}</strong>; review the complaint and continue authority work.</p>}
              {resolutionConfirmation.completion_photo_url && <a className="resolution-admin-photo" href={resolutionConfirmation.completion_photo_url} target="_blank" rel="noreferrer">View current cycle completion evidence</a>}
              {resolutionConfirmation.citizen_photo_url && <a className="resolution-admin-photo" href={resolutionConfirmation.citizen_photo_url} target="_blank" rel="noreferrer">View citizen response photo</a>}
              {!!resolutionConfirmation.history?.length && <div className="resolution-confirmation-history"><strong>Immutable citizen response history</strong>
                {resolutionConfirmation.history.map(event => <p key={event.id}>
                  <span>{event.response === 'confirmed' ? 'Confirmed fixed' : 'Reported still unresolved'}{event.citizen_id ? ` · ${event.citizen_id}` : ''}</span>
                  <time dateTime={event.created_at}>{formatDate(event.created_at)}</time>
                </p>)}
              </div>}
            </>}
          </section>
          <section className="impact-priority-panel" aria-label="Explainable Impact-Based Priority" aria-live="polite">
            <div className="impact-priority-heading"><div><span className="eyebrow">ESTIMATED EXPOSURE</span><h4>Explainable Impact-Based Priority</h4></div>
              {impactPriority?.impact_priority_score != null && <strong className="impact-score">{impactPriority.impact_priority_score}<small>/100</small></strong>}
            </div>
            <p className="impact-caveat">Estimated exposure based on nearby public infrastructure; it is not a count of people affected. The existing CityLens priority score above is not modified.</p>
            {impactLoading && <p className="placeholder">Checking nearby OpenStreetMap features…</p>}
            {impactError && <div className="impact-fallback">Impact estimate unavailable: {impactError}. Existing CityLens priority remains in use.</div>}
            {impactPriority?.fallback_reason && <div className="impact-fallback">{impactPriority.fallback_reason} Existing CityLens priority: {impactPriority.legacy_priority_score != null ? Number(impactPriority.legacy_priority_score).toFixed(1) : '—'}.</div>}
            {impactPriority && <>
              <div className="impact-breakdown-grid">
                <div><span>Severity</span><strong>{impactPriority.severity} · {impactPriority.severity_score}/100</strong></div>
                <div><span>Exposure</span><strong>{impactPriority.exposure_score == null ? 'Unavailable' : `${impactPriority.exposure_score}/100`}</strong></div>
                <div><span>Recurrence</span><strong>{impactPriority.recurrence_count} incidents · {impactPriority.recurrence_score}/100 · {impactPriority.recurrence_window_days} days</strong></div>
                <div><span>Nearby schools</span><strong>{impactPriority.nearby_schools ?? '—'}</strong></div>
                <div><span>Nearby hospitals / clinics</span><strong>{impactPriority.nearby_hospitals ?? '—'} / {impactPriority.nearby_clinics ?? '—'}</strong></div>
                <div><span>Nearby public-transport stops</span><strong>{impactPriority.nearby_bus_stops ?? '—'}</strong></div>
                <div><span>Nearby major-road features</span><strong>{impactPriority.nearby_major_roads ?? '—'}{impactPriority.major_road_proximity == null ? '' : impactPriority.major_road_proximity ? ' · Yes' : ' · No'}</strong></div>
                <div><span>Exposure radius</span><strong>{impactPriority.osm_radius_m} m</strong></div>
              </div>
              <p className="impact-formula"><strong>Formula:</strong> {impactPriority.formula}</p>
              <p className="impact-formula"><strong>Component rules:</strong> {impactPriority.component_methodology}</p>
              <p className="impact-explanation">{impactPriority.explanation}</p>
              {impactPriority.impact_priority_score != null && <p className="impact-cache-note">OSM data {impactPriority.osm_cache_hit ? 'served from cache' : 'just retrieved'} · {impactPriority.attribution} · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">attribution</a></p>}
            </>}
          </section>
          <section className="authority-work-panel" aria-label="Authority Work Updates">
            <div className="authority-work-heading"><div><span className="eyebrow">AUTHORITY WORK UPDATES</span><h4>Authority Work Updates</h4></div></div>
            {loadingWorkUpdates && <p className="placeholder">Loading work updates…</p>}
            {workUpdates.length === 0 && !loadingWorkUpdates && <p className="placeholder">No authority work updates have been recorded yet.</p>}
            <div className="authority-update-list">
              {workUpdates.map(update => (
                <article className="authority-update-card" key={update.id}>
                  <div className="authority-update-heading"><h5>{update.status === 'Resolved' ? 'Resolution Evidence' : 'Work Progress Evidence'}</h5><span className="badge status">{update.status}</span></div>
                  <p className="authority-update-message">{update.message || 'No authority message was provided.'}</p>
                  <div className="authority-update-meta"><span>Updated by<strong>{update.updated_by}</strong></span><span>Updated at<strong>{formatDate(update.uploaded_at)}</strong></span></div>
                  {update.photo_url && <div className="authority-photo"><a href={update.photo_url} target="_blank" rel="noreferrer"><img src={update.photo_url} alt={`${update.status} evidence for complaint ${update.complaint_id}`} loading="lazy" /><span>View full image</span></a></div>}
                  <div className="authenticity-result"><strong>Photo Authenticity Check</strong><p>{update.authenticity_status}</p></div>
                  {update.file_hash && <details className="evidence-metadata"><summary>SHA-256 and image metadata</summary><code>SHA-256: {update.file_hash}</code><pre>{update.metadata_summary || 'No additional metadata summary.'}</pre></details>}
                </article>
              ))}
            </div>
            <form className="form evidence-form" onSubmit={submitWorkUpdate}>
              <h5>{workStatus === 'Resolved' ? 'Resolution Evidence' : 'Work Progress Evidence'}</h5>
              <div className="field">
                <label htmlFor="authority-work-status">Status update</label>
                <select id="authority-work-status" value={workStatus} onChange={event => {
                  setWorkStatus(event.target.value);
                  setWorkPhoto(null);
                  const input = document.getElementById('authority-evidence-photo');
                  if (input) input.value = '';
                  setWorkError('');
                }} required>
                  <option value="">Choose a work status</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Resolved">Resolved</option>
                </select>
              </div>
              {workStatus && <>
                <div className="field">
                  <label htmlFor="authority-work-message">{workStatus === 'Resolved' ? 'Completion Message' : 'Authority Update / Message'}</label>
                  <textarea id="authority-work-message" rows={3} maxLength={2000} value={workMessage} onChange={event => setWorkMessage(event.target.value)} placeholder={workStatus === 'Resolved' ? 'Describe the completed repair…' : 'Describe the work in progress…'} />
                </div>
                <div className="field">
                  <label htmlFor="authority-evidence-photo">{workStatus === 'Resolved' ? 'Completion Photo (required)' : 'Upload Progress Photo (optional)'}</label>
                  <input id="authority-evidence-photo" type="file" accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp" required={workStatus === 'Resolved'} onChange={event => {
                    const file = event.target.files?.[0] || null;
                    if (file && file.size > 10 * 1024 * 1024) {
                      setWorkPhoto(null);
                      setWorkError('Evidence photos must be 10 MB or smaller.');
                      event.target.value = '';
                    } else {
                      setWorkPhoto(file);
                      setWorkError('');
                    }
                  }} />
                  <div className="hint-sm">JPG, PNG, or WEBP; maximum 10 MB. The original image is preserved without re-encoding.</div>
                </div>
              </>}
              {workError && <div className="error" role="alert">{workError}</div>}
              {workSuccess && <div className="field-ok" role="status">{workSuccess}</div>}
              <button className="btn primary" type="submit" disabled={!workStatus || updatingId === selectedComplaint.id}>{updatingId === selectedComplaint.id ? 'Saving update…' : 'Save authority update'}</button>
            </form>
          </section>
        </div>
      )}

      {filteredComplaints.length === 0 ? (
        <div className="panel"><p className="placeholder">No complaints match the selected filters.</p></div>
      ) : (
        <div className="panel table-scroll">
          <table className="complaints-table">
            <thead><tr><th>ID</th><th>Citizen ID</th><th>Problem type</th><th>Description</th><th>Area</th><th>Severity</th><th>Priority</th><th>Status</th><th>Date/time</th></tr></thead>
            <tbody>
              {filteredComplaints.map(complaint => (
                <tr key={complaint.id}>
                  <td><button className="link-button" type="button" onClick={() => openComplaint(complaint)}>#{complaint.id}</button></td>
                  <td>{complaint.citizen_id || 'Legacy / unlinked'}</td>
                  <td>{complaint.problem_type || '—'}</td>
                  <td className="report-description">{complaint.description || '—'}</td>
                  <td>{complaint.area || 'Unknown'}</td>
                  <td><span className={`badge ${complaint.severity}`}>{complaint.severity || '—'}</span></td>
                  <td>{complaint.priority_score != null ? complaint.priority_score.toFixed(1) : '—'}</td>
                  <td>
                    <select
                      className="status-select"
                      value={complaint.status}
                      onChange={e => handleStatusSelection(complaint, e.target.value)}
                      disabled={updatingId === complaint.id}
                      aria-label={`Status for complaint ${complaint.id}`}
                    >
                      {STATUS_OPTIONS.map(status => <option key={status} value={status}>{status === 'Assigned' ? 'Assigned (legacy)' : status}</option>)}
                    </select>
                  </td>
                  <td>{formatDate(complaint.timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default Complaints;
