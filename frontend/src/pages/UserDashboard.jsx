import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { getComplaints } from '../services/api';
import MapPage from './Map';

function UserDashboard() {
  const { user } = useAuth();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    getComplaints()
      .then(data => { if (active) setReports(data); })
      .catch(err => { if (active) setError(err?.response ? `Could not load your account summary (${err.response.status}).` : 'Could not reach the CityLens AI backend.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const open = reports.filter(report => report.status !== 'Resolved').length;
  const resolved = reports.filter(report => report.status === 'Resolved').length;

  return (
    <div className="citizen-home">
      <section className="welcome-banner">
        <div><div className="eyebrow">CITIZEN PORTAL</div><h1>Good to see you, {user?.account_id}.</h1><p>Report a problem or follow the progress of issues you have submitted.</p></div>
        <NavLink className="btn primary" to="/citizen/report"><span className="button-plus" aria-hidden="true">+</span> Report a problem</NavLink>
      </section>
      <div className="citizen-stat-grid">
        <div className="citizen-stat"><span className="citizen-stat-icon stat-icon-blue" aria-hidden="true">#</span><div><span className="citizen-stat-label">My complaints</span><strong>{loading ? '—' : reports.length}</strong></div></div>
        <div className="citizen-stat"><span className="citizen-stat-icon stat-icon-amber" aria-hidden="true"><span /></span><div><span className="citizen-stat-label">Awaiting resolution</span><strong>{loading ? '—' : open}</strong></div></div>
        <div className="citizen-stat"><span className="citizen-stat-icon stat-icon-green" aria-hidden="true">✓</span><div><span className="citizen-stat-label">Resolved</span><strong>{loading ? '—' : resolved}</strong></div></div>
      </div>
      {error && <div className="error" role="alert">{error}</div>}
      <div className="citizen-section-heading"><div><div className="eyebrow">CITYWIDE VIEW</div><h2>What is happening around Hyderabad?</h2></div><NavLink className="text-link" to="/citizen/map">Explore the map <span aria-hidden="true">→</span></NavLink></div>
      <MapPage embedded audience="citizen" />
      <div className="citizen-quick-links">
        <NavLink to="/citizen/complaints" className="quick-link-card"><span className="quick-link-icon" aria-hidden="true">01</span><span><strong>Track my complaints</strong><small>Check the latest authority status and timeline.</small></span><span className="quick-link-arrow" aria-hidden="true">→</span></NavLink>
        <NavLink to="/citizen/report" className="quick-link-card"><span className="quick-link-icon" aria-hidden="true">02</span><span><strong>Report a civic problem</strong><small>Share a photo and location with the city team.</small></span><span className="quick-link-arrow" aria-hidden="true">→</span></NavLink>
      </div>
    </div>
  );
}

export default UserDashboard;
