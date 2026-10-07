import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { createComplaint } from '../services/api';

// Labels shown to the user -> exact problem_type strings the backend/dashboard use
const PROBLEM_TYPES = [
  { value: '', label: 'Auto Detect (AI)' },
  { value: 'Pothole', label: 'Pothole' },
  { value: 'Garbage', label: 'Waste / Garbage' },
  { value: 'Streetlight', label: 'Broken streetlight' },
  { value: 'Damaged Road', label: 'Damaged road' },
  { value: 'Drainage', label: 'Drainage problem' },
  { value: 'Other', label: 'Other / Unknown' },
];

const EMPTY = { description: '', manualType: '', latitude: '', longitude: '' };

function errorMessage(e) {
  const d = e?.response?.data?.detail;
  if (Array.isArray(d)) return d.map(x => `${(x.loc || []).slice(-1)[0]}: ${x.msg}`).join('; ');
  if (typeof d === 'string') return d;
  if (e?.response) return `Server error (${e.response.status})`;
  return 'Could not reach the CityLens AI backend. Is it running?';
}

function Report() {
  const [form, setForm] = useState(EMPTY);
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [errors, setErrors] = useState({});
  const [loc, setLoc] = useState({ state: 'idle', msg: '' });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [result, setResult] = useState(null);

  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const onImage = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    if (!f.type.startsWith('image/')) {
      setErrors({ ...errors, image: 'Please choose an image file (JPG, PNG, WEBPâ€¦).' });
      e.target.value = '';
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      setErrors({ ...errors, image: 'Image is larger than 10 MB.' });
      e.target.value = '';
      return;
    }
    setImage(f);
    setPreview(URL.createObjectURL(f));
    setErrors({ ...errors, image: undefined });
  };

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setLoc({ state: 'error', msg: 'Geolocation is not supported by this browser. Please enter coordinates manually.' });
      return;
    }
    setLoc({ state: 'loading', msg: 'Requesting locationâ€¦' });
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setForm(f => ({ ...f, latitude: pos.coords.latitude.toFixed(6), longitude: pos.coords.longitude.toFixed(6) }));
        setLoc({ state: 'ok', msg: `Location captured (Â±${Math.round(pos.coords.accuracy)} m)` });
      },
      (err) => {
        const msg = err.code === 1 ? 'Location permission denied.' : err.code === 3 ? 'Location request timed out.' : 'Location unavailable.';
        setLoc({ state: 'error', msg: `${msg} Please enter latitude and longitude manually.` });
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const validate = () => {
    const e = {};
    if (!image) e.image = 'A photo is required by the CityLens AI backend.';
    const lat = parseFloat(form.latitude), lon = parseFloat(form.longitude);
    if (form.latitude === '' || isNaN(lat) || lat < -90 || lat > 90) e.latitude = 'Enter a valid latitude (-90 to 90).';
    if (form.longitude === '' || isNaN(lon) || lon < -180 || lon > 180) e.longitude = 'Enter a valid longitude (-180 to 180).';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = async (ev) => {
    ev.preventDefault();
    setSubmitError('');
    if (!validate() || submitting) return;
    const fd = new FormData();
    fd.append('image', image);
    if (form.description.trim()) fd.append('description', form.description.trim());
    fd.append('latitude', form.latitude);
    fd.append('longitude', form.longitude);
    fd.append('auto_detect', form.manualType ? 'false' : 'true');
    if (form.manualType) fd.append('manual_type', form.manualType);
    setSubmitting(true);
    try {
      const created = await createComplaint(fd);
      setResult(created);
    } catch (e) {
      setSubmitError(errorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setForm(EMPTY); setImage(null); setPreview(null); setErrors({});
    setLoc({ state: 'idle', msg: '' }); setSubmitError(''); setResult(null);
  };

  if (result) {
    return (
      <div className="report-wrap"><div className="report-stagebar" aria-label="Citizen reporting flow"><span className="active"><b>01</b> REPORT</span><i>→</i><span><b>02</b> LOCATION</span><i>→</i><span><b>03</b> DESCRIBE</span><i>→</i><span><b>04</b> ANALYZE</span><i>→</i><span><b>05</b> SUBMIT</span></div>
        <div className="panel success-panel">
          <div className="success-icon">âœ“</div>
          <h2>Report Submitted Successfully</h2>
          <p className="placeholder">Your complaint has been received and added to CityLens AI.</p>
          <p className="complaint-id">Complaint ID: <strong>#{result.id}</strong></p>
          <p className="placeholder" style={{ fontSize: '0.85rem' }}>Keep this ID to track your complaint status.</p>
        </div>
        <div className="panel">
          <h3>AI Analysis</h3>
          <div className="ai-grid">
            <div><div className="label">Problem Type</div><div className="val">{result.problem_type}</div></div>
            <div><div className="label">Confidence</div><div className="val">{result.ai_detected === true && typeof result.confidence === 'number' && Number.isFinite(result.confidence) ? `${Math.round(result.confidence * 100)}%` : 'Manual / Not AI-classified'}</div></div>
            <div><div className="label">Severity</div><div className="val"><span className={`badge ${result.severity}`}>{result.severity}</span></div></div>
            <div><div className="label">AI Priority Score</div><div className="val">{result.priority_score != null ? result.priority_score.toFixed(1) : 'â€”'}</div></div>
            <div><div className="label">Area</div><div className="val">{result.area || 'Unknown'}</div></div>
            <div><div className="label">Status</div><div className="val"><span className="badge status">{result.status}</span></div></div>
          </div>
          {result.confidence < 0.6 && (
            <p className="hint" style={{ marginTop: '0.9rem' }}>
              Low AI image confidence â€” the problem type was taken from your description or manual selection.
            </p>
          )}
          <p className="hint" style={{ marginTop: '0.4rem' }}>AI Priority Score is a CityLens AI estimate, not an official government formula.</p>
        </div>
        <NavLink className="btn primary" to="/citizen/complaints">Track my complaint</NavLink>{' '}
        <button className="btn" onClick={reset}>Submit Another Report</button>
      </div>
    );
  }

  return (
    <div className="report-wrap"><div className="report-stagebar" aria-label="Citizen reporting flow"><span className="active"><b>01</b> REPORT</span><i>→</i><span><b>02</b> LOCATION</span><i>→</i><span><b>03</b> DESCRIBE</span><i>→</i><span><b>04</b> ANALYZE</span><i>→</i><span><b>05</b> SUBMIT</span></div>
      <div className="page-header">
        <div>
          <h2>Report an Urban Problem</h2>
          <div className="sub">Upload a photo and location â€” CityLens AI will analyze and prioritize it.</div>
        </div>
      </div>

      <form className="panel form" onSubmit={submit} noValidate>
        <div className="field">
          <label>Photo of the problem *</label>
          <input type="file" accept="image/*" onChange={onImage} />
          {errors.image && <div className="field-error">{errors.image}</div>}
          {preview && <img className="preview" src={preview} alt="Selected problem" />}
        </div>

        <div className="field">
          <label>Problem description (optional)</label>
          <textarea rows={4} placeholder="Describe the problem you found..." value={form.description} onChange={set('description')} />
        </div>

        <div className="field">
          <label>Problem type</label>
          <select value={form.manualType} onChange={set('manualType')}>
            {PROBLEM_TYPES.map(p => <option key={p.label} value={p.value}>{p.label}</option>)}
          </select>
          <div className="hint-sm">Leave on Auto Detect unless you are sure. Choose Other / Unknown if nothing fits.</div>
        </div>

        <div className="field">
          <label>Location *</label>
          <div className="loc-row">
            <div>
              <input type="number" step="any" placeholder="Latitude (e.g. 17.4375)" value={form.latitude} onChange={set('latitude')} />
              {errors.latitude && <div className="field-error">{errors.latitude}</div>}
            </div>
            <div>
              <input type="number" step="any" placeholder="Longitude (e.g. 78.4482)" value={form.longitude} onChange={set('longitude')} />
              {errors.longitude && <div className="field-error">{errors.longitude}</div>}
            </div>
            <button type="button" className="btn" onClick={useMyLocation} disabled={loc.state === 'loading'}>Use my location</button>
          </div>
          {loc.msg && <div className={loc.state === 'error' ? 'field-error' : loc.state === 'ok' ? 'field-ok' : 'hint-sm'}>{loc.msg}</div>}
        </div>

        {submitError && <div className="error">Submission failed: {submitError}</div>}

        <button type="submit" className="btn primary" disabled={submitting}>
          {submitting ? 'Analyzing & Submittingâ€¦' : 'Submit Report'}
        </button>
      </form>
    </div>
  );
}

export default Report;


