import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { getComplaintWorkUpdates, getComplaintWorkforceProgress, getComplaints, getResolutionConfirmation, submitResolutionConfirmation, uploadCitizenResolutionEvidence } from '../services/api';

const FLOW = ['Reported', 'Under Review', 'In Progress', 'Resolved'];

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

function StatusTimeline({ status }) {
  const activeIndex = status === 'Assigned' ? 1 : Math.max(0, FLOW.indexOf(status));
  return (
    <div className="complaint-timeline" aria-label={`Complaint progress: ${status}`}>
      {FLOW.map((step, index) => {
        const state = index < activeIndex ? 'complete' : index === activeIndex ? 'current' : 'upcoming';
        return <div className={`timeline-step ${state}`} key={step}><span className="timeline-marker">{state === 'complete' ? '✓' : index + 1}</span><span className="timeline-label">{step}</span></div>;
      })}
      {status === 'Assigned' && <p className="legacy-status-note">The backend reports the legacy status <strong>Assigned</strong>; it is shown at the review stage in this progress guide.</p>}
    </div>
  );
}

function AuthorityWorkHistory({ updates }) {
  return (
    <section className="citizen-authority-updates" aria-label="Authority Work Updates">
      <h3>Authority Work Updates</h3>
      {!updates.length && <p className="placeholder">No authority work updates have been recorded yet.</p>}
      {updates.map(update => (
        <article className="citizen-authority-update" key={update.id}>
          <div className="citizen-authority-heading"><strong>{update.status}</strong><span>{formatDate(update.uploaded_at)}</span></div>
          <p>{update.message || 'No authority message was provided.'}</p>
          <div className="citizen-authority-meta">Updated by <strong>{update.updated_by}</strong></div>
          {update.photo_url && <a className="citizen-evidence-link" href={update.photo_url} target="_blank" rel="noreferrer"><img src={update.photo_url} alt={`${update.status} evidence for complaint ${update.complaint_id}`} loading="lazy" /><span>View {update.status === 'Resolved' ? 'Completion' : 'Progress'} Photo</span></a>}
          <div className="authenticity-result"><strong>Photo Authenticity Check</strong><p>{update.authenticity_status}</p></div>
          {update.file_hash && <details className="evidence-metadata"><summary>Photo hash and metadata summary</summary><code>SHA-256: {update.file_hash}</code><pre>{update.metadata_summary || 'No additional metadata summary.'}</pre></details>}
        </article>
      ))}
    </section>
  );
}

function WorkforceProgressHistory({ progress }) {
  if (!progress?.assignment_history?.length) return null;
  const current = progress.current_assignment;
  const timeline = progress.timeline || [];
  return (
    <section className="citizen-workforce-history" aria-label="Worker assignment and progress history">
      <div className="workforce-section-heading"><div><span className="eyebrow">FIELD WORK PROGRESS</span><h3>Worker assignment &amp; updates</h3></div></div>
      {current && <div className="citizen-current-assignment">
        <div><span>Assigned worker</span><strong>{current.worker_name} · {current.department}</strong></div>
        <div><span>Current work stage</span><strong>{current.status} · {current.progress_percentage}%</strong></div>
        <div><span>Assigned</span><strong>{formatDate(current.assigned_at)}</strong></div>
        {current.deadline && <div><span>Target date</span><strong>{formatDate(current.deadline)}</strong></div>}
      </div>}
      <ol className="citizen-workforce-timeline">
        {timeline.map(event => {
          const title = event.event_type === 'complaint_submitted' ? 'Complaint submitted'
            : event.event_type === 'assignment' ? `Assigned to ${event.worker_name || 'field worker'}`
              : event.event_type === 'authority_update' ? `Authority update · ${event.status}`
                : event.event_type === 'citizen_confirmation' ? (event.status === 'confirmed' ? 'Citizen confirmed resolution' : 'Citizen reported issue unresolved')
                  : `${event.status}${event.progress_percentage != null ? ` · ${event.progress_percentage}%` : ''}`;
          return <li key={event.event_id}>
            <div className="citizen-workforce-dot" />
            <div><div className="citizen-workforce-event-heading"><strong>{title}</strong><time>{formatDate(event.created_at)}</time></div>
              {event.department && <div className="citizen-workforce-department">{event.department}</div>}
              {event.message && <p>{event.message}</p>}
              {event.photo_url && <a className="citizen-evidence-link" href={event.photo_url} target="_blank" rel="noreferrer"><img src={event.photo_url} alt={`Evidence for complaint ${progress.complaint_id}`} loading="lazy" /><span>View evidence photo</span></a>}
            </div>
          </li>;
        })}
      </ol>
    </section>
  );
}

function ResolutionConfirmationCard({ report, confirmation, onRespond, busy, error, onUploadEvidence, evidenceUploading, evidenceUploadError }) {
  const resolutionStatus = confirmation?.resolution_status;
  const [selectedEvidencePhoto, setSelectedEvidencePhoto] = useState(null);
  const canUploadEvidence = resolutionStatus === 'awaiting' && confirmation?.can_respond && !confirmation?.citizen_photo_url;
  const handleEvidenceUpload = async event => {
    event.preventDefault();
    if (!selectedEvidencePhoto) return;
    const uploaded = await onUploadEvidence(report.id, selectedEvidencePhoto);
    if (uploaded) setSelectedEvidencePhoto(null);
  };
  const shouldShow = report.status === 'Resolved' || resolutionStatus === 'unresolved' || (confirmation?.history?.length ?? 0) > 0;
  if (!shouldShow) return null;

  return (
    <section className={`resolution-confirmation-card${resolutionStatus === 'unresolved' ? ' is-unresolved' : ''}`} aria-label="Citizen resolution confirmation">
      <div className="resolution-confirmation-heading">
        <div><span className="eyebrow">RESOLUTION CHECK</span><h3>Is this problem fixed?</h3></div>
        {resolutionStatus === 'awaiting' && <span className="confirmation-state awaiting">Awaiting your response</span>}
        {resolutionStatus === 'confirmed' && <span className="confirmation-state confirmed">Confirmed fixed</span>}
        {resolutionStatus === 'unresolved' && <span className="confirmation-state unresolved">Reopened for review</span>}
      </div>
      {confirmation?.resolved_at && <p className="resolution-confirmation-meta">Marked resolved {formatDate(confirmation.resolved_at)}</p>}
      {confirmation?.resolution_message && <p className="resolution-authority-message">{confirmation.resolution_message}</p>}
      {confirmation?.completion_photo_url && <a className="citizen-evidence-link resolution-completion-photo" href={confirmation.completion_photo_url} target="_blank" rel="noreferrer">
        <img src={confirmation.completion_photo_url} alt={`Completion evidence for complaint ${report.id}`} loading="lazy" />
        <span>View completion photo</span>
      </a>}
      {confirmation?.citizen_photo_url && <a className="citizen-evidence-link resolution-completion-photo" href={confirmation.citizen_photo_url} target="_blank" rel="noreferrer">
        <img src={confirmation.citizen_photo_url} alt={`Your response photo for complaint ${report.id}`} loading="lazy" />
        <span>View your uploaded photo</span>
      </a>}
      {canUploadEvidence && <form className="resolution-evidence-upload" onSubmit={handleEvidenceUpload}>
        <label htmlFor={`citizen-resolution-photo-${report.id}`}>Upload a photo to support your response (optional)</label>
        <div className="resolution-confirmation-actions">
          <input id={`citizen-resolution-photo-${report.id}`} type="file" accept="image/jpeg,image/png,image/webp" onChange={event => setSelectedEvidencePhoto(event.target.files?.[0] || null)} />
          <button className="btn" type="submit" disabled={!selectedEvidencePhoto || evidenceUploading}>{evidenceUploading ? 'Uploading…' : 'Upload Photo'}</button>
        </div>
        <p className="resolution-confirmation-note">Optional. Your photo is linked to this resolution cycle and visible to the authority.</p>
        {evidenceUploadError && <div className="error" role="alert">{evidenceUploadError}</div>}
      </form>}
      {!confirmation && report.status === 'Resolved' && <p className="resolution-confirmation-note">Could not load the resolution confirmation details. Refresh to try again.</p>}
      {resolutionStatus === 'awaiting' && confirmation?.can_respond && <>
        <p className="resolution-confirmation-note">The authority has marked this problem as resolved. The photo is evidence of the work performed, not proof that the issue is fixed.</p>
        <div className="resolution-confirmation-actions">
          <button className="btn primary" type="button" disabled={busy} onClick={() => onRespond(report.id, 'confirmed')}>{busy ? 'Submitting…' : 'Yes, it is fixed'}</button>
          <button className="btn" type="button" disabled={busy} onClick={() => onRespond(report.id, 'unresolved')}>{busy ? 'Submitting…' : 'No, the problem is still there'}</button>
        </div>
      </>}
      {resolutionStatus === 'confirmed' && <p className="resolution-confirmation-success" role="status">Thank you. Your confirmation has been recorded. {confirmation.responded_at ? `(${formatDate(confirmation.responded_at)})` : ''}</p>}
      {resolutionStatus === 'unresolved' && <p className="resolution-confirmation-warning" role="status">We've reopened your complaint and sent it back for review. {confirmation.responded_at ? `Reported ${formatDate(confirmation.responded_at)}.` : ''}</p>}
      {resolutionStatus === 'evidence_unavailable' && <p className="resolution-confirmation-note">The completion evidence is unavailable, so a response cannot be recorded yet. Please contact the authority.</p>}
      {resolutionStatus === 'not_available' && report.status === 'Resolved' && <p className="resolution-confirmation-note">This older resolved record has no linked completion-evidence cycle to confirm.</p>}
      {error && <div className="error" role="alert">{error}</div>}
      {!!confirmation?.history?.length && <div className="resolution-confirmation-history" aria-label="Resolution confirmation history">
        <strong>Confirmation history</strong>
        {confirmation.history.map(event => <p key={event.id}>
          {event.response === 'confirmed' ? 'You confirmed this resolution.' : 'You reported that the problem is still present; it was sent back for review.'}
          <time dateTime={event.created_at}>{formatDate(event.created_at)}</time>
        </p>)}
      </div>}
    </section>
  );
}

function MyReports() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [workUpdates, setWorkUpdates] = useState({});
  const [workforceProgress, setWorkforceProgress] = useState({});
  const [resolutionConfirmations, setResolutionConfirmations] = useState({});
  const [confirmationActionId, setConfirmationActionId] = useState(null);
  const [confirmationErrors, setConfirmationErrors] = useState({});
  const [evidenceUploadId, setEvidenceUploadId] = useState(null);
  const [evidenceUploadErrors, setEvidenceUploadErrors] = useState({});
  const [workUpdatesError, setWorkUpdatesError] = useState('');

  const refreshReports = async () => {
    setRefreshing(true);
    setError('');
    try {
      const data = await getComplaints();
      const results = await Promise.all(data.map(async report => {
        const [updates, confirmation, workforce] = await Promise.all([
          getComplaintWorkUpdates(report.id).catch(() => null),
          getResolutionConfirmation(report.id).catch(() => null),
          getComplaintWorkforceProgress(report.id).catch(() => null),
        ]);
        return [report.id, updates, confirmation, workforce];
      }));
      setReports(data);
      setWorkUpdates(Object.fromEntries(results.map(([id, updates]) => [id, updates || []])));
      setResolutionConfirmations(Object.fromEntries(results.map(([id, , confirmation]) => [id, confirmation])));
      setWorkforceProgress(Object.fromEntries(results.map(([id, , , workforce]) => [id, workforce])));
      setWorkUpdatesError(results.some(([, updates, confirmation, workforce]) => updates === null || confirmation === null || workforce === null) ? 'Some authority updates, worker progress, or resolution details could not be loaded. Refresh to try again.' : '');
    }
    catch (err) { setError(err?.response ? `Server error (${err.response.status})` : 'Could not reach the CityLens AI backend.'); }
    finally { setRefreshing(false); }
  };

  const respondToResolution = async (complaintId, response) => {
    setConfirmationActionId(complaintId);
    setConfirmationErrors(current => ({ ...current, [complaintId]: '' }));
    try {
      const result = await submitResolutionConfirmation(complaintId, response);
      setResolutionConfirmations(current => ({ ...current, [complaintId]: result }));
      setReports(current => current.map(report => report.id === complaintId ? { ...report, status: result.complaint_status } : report));
      const latestProgress = await getComplaintWorkforceProgress(complaintId).catch(() => null);
      if (latestProgress) setWorkforceProgress(current => ({ ...current, [complaintId]: latestProgress }));
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setConfirmationErrors(current => ({ ...current, [complaintId]: typeof detail === 'string' ? detail : `Could not save your response${err?.response ? ` (HTTP ${err.response.status})` : ''}.` }));
    } finally {
      setConfirmationActionId(null);
    }
  };

  const uploadResolutionEvidence = async (complaintId, photo) => {
    setEvidenceUploadId(complaintId);
    setEvidenceUploadErrors(current => ({ ...current, [complaintId]: '' }));
    try {
      const result = await uploadCitizenResolutionEvidence(complaintId, photo);
      setResolutionConfirmations(current => ({ ...current, [complaintId]: result }));
      return true;
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setEvidenceUploadErrors(current => ({ ...current, [complaintId]: typeof detail === 'string' ? detail : `Could not upload your photo${err?.response ? ` (HTTP ${err.response.status})` : ''}.` }));
      return false;
    } finally {
      setEvidenceUploadId(null);
    }
  };

  useEffect(() => {
    let active = true;
    getComplaints()
      .then(async data => {
      const results = await Promise.all(data.map(async report => {
          const [updates, confirmation, workforce] = await Promise.all([
            getComplaintWorkUpdates(report.id).catch(() => null),
            getResolutionConfirmation(report.id).catch(() => null),
            getComplaintWorkforceProgress(report.id).catch(() => null),
          ]);
          return [report.id, updates, confirmation, workforce];
        }));
        if (active) {
          setReports(data);
          setWorkUpdates(Object.fromEntries(results.map(([id, updates]) => [id, updates || []])));
          setResolutionConfirmations(Object.fromEntries(results.map(([id, , confirmation]) => [id, confirmation])));
          setWorkforceProgress(Object.fromEntries(results.map(([id, , , workforce]) => [id, workforce])));
          setWorkUpdatesError(results.some(([, updates, confirmation, workforce]) => updates === null || confirmation === null || workforce === null) ? 'Some authority updates, worker progress, or resolution details could not be loaded. Refresh to try again.' : '');
        }
      })
      .catch(err => { if (active) setError(err?.response ? `Server error (${err.response.status})` : 'Could not reach the CityLens AI backend.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  if (loading) return <p className="placeholder">Loading your complaints…</p>;
  if (error) return <div className="error" role="alert">Could not load your complaints: {error}</div>;

  return (
    <div className="my-complaints-page">
      <div className="page-header"><div><div className="eyebrow">CITIZEN SERVICES</div><h1>My complaints</h1><div className="sub">See what happened to your report. Statuses are read from the live CityLens backend.</div></div><div className="my-complaint-actions"><span className="my-report-count">{reports.length} {reports.length === 1 ? 'complaint' : 'complaints'}</span><button className="btn" type="button" onClick={refreshReports} disabled={refreshing}>{refreshing ? 'Refreshing…' : 'Refresh status'}</button></div></div>
      {workUpdatesError && <div className="error" role="status">{workUpdatesError}</div>}
      {reports.length === 0 ? (
        <div className="empty-state panel"><span className="empty-state-mark" aria-hidden="true">01</span><h2>No complaints yet</h2><p>When you submit a civic report from this account, its status and timeline will appear here.</p><NavLink className="btn primary" to="/citizen/report">Report a problem</NavLink></div>
      ) : (
        <div className="my-complaint-list">
          {reports.map(report => (
            <article className="my-complaint-card panel" key={report.id}>
              <div className="my-complaint-heading"><div><span className="complaint-reference">COMPLAINT #{report.id}</span><h2>{report.problem_type || 'Urban problem'}</h2></div><span className={`badge status-badge status-${String(report.status || '').toLowerCase().replaceAll(' ', '-')}`}>{report.status || '—'}</span></div>
              <p className="my-complaint-description">{report.description || 'No description was provided.'}</p>
              <div className="my-complaint-meta"><span><small>Area</small><strong>{report.area || 'Unknown'}</strong></span><span><small>Submitted</small><strong>{formatDate(report.timestamp)}</strong></span><span><small>Severity</small><strong><span className={`badge ${report.severity || ''}`}>{report.severity || '—'}</span></strong></span><span><small>Priority score</small><strong>{report.priority_score != null ? Number(report.priority_score).toFixed(1) : '—'}</strong></span></div>
              <div className="timeline-title">WHAT HAPPENED TO MY COMPLAINT?</div>
              <StatusTimeline status={report.status} />
              <WorkforceProgressHistory progress={workforceProgress[report.id]} />
              <ResolutionConfirmationCard
                report={report}
                confirmation={resolutionConfirmations[report.id]}
                onRespond={respondToResolution}
                busy={confirmationActionId === report.id}
                error={confirmationErrors[report.id]}
                onUploadEvidence={uploadResolutionEvidence}
                evidenceUploading={evidenceUploadId === report.id}
                evidenceUploadError={evidenceUploadErrors[report.id]}
              />
              <AuthorityWorkHistory updates={workUpdates[report.id] || []} />
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

export default MyReports;
