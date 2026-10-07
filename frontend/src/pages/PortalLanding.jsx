import React from 'react';
import { Link } from 'react-router-dom';

function BrandMark() {
  return <div className="brand-mark" aria-hidden="true"><span /><span /><span /></div>;
}

function PortalLanding() {
  return (
    <main className="landing-page">
      <header className="landing-header">
        <Link to="/" className="landing-brand" aria-label="CityLens AI home">
          <BrandMark />
          <span>CITYLENS <strong>AI</strong></span>
        </Link>
        <span className="landing-header-note">Civic intelligence for better cities</span>
      </header>

      <section className="landing-hero">
        <div className="landing-copy">
          <div className="eyebrow"><span className="eyebrow-line" /> AI URBAN PROBLEM INTELLIGENCE PLATFORM</div>
          <h1>See the city.<br /><span>Move it forward.</span></h1>
          <p>One connected view of civic problems—from the first citizen report to city-wide response and resolution.</p>
        </div>
        <div className="landing-orbit" aria-hidden="true"><div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" /><div className="orbit-core"><BrandMark /></div><span className="orbit-node node-one" /><span className="orbit-node node-two" /><span className="orbit-node node-three" /></div>
      </section>

      <section className="portal-choice" aria-labelledby="portal-heading">
        <div className="section-heading">
          <div><div className="eyebrow">CHOOSE YOUR WORKSPACE</div><h2 id="portal-heading">How would you like to use CityLens?</h2></div>
          <span className="section-note">Secure, role-specific access</span>
        </div>
        <div className="portal-cards">
          <Link to="/citizen/login" className="portal-card citizen-card">
            <div className="portal-card-top"><span className="portal-icon citizen-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z"/><path d="M4.5 21a7.5 7.5 0 0 1 15 0"/><path d="M19 8v6m-3-3h6"/></svg></span><span className="portal-arrow" aria-hidden="true">↗</span></div>
            <div className="portal-card-kicker">FOR RESIDENTS</div>
            <h3>Citizen Portal</h3>
            <p>Report civic problems, follow progress and explore public issue hotspots in your city.</p>
            <span className="portal-card-cta">Sign in as a citizen <span aria-hidden="true">→</span></span>
          </Link>
          <Link to="/admin/login" className="portal-card admin-card">
            <div className="portal-card-top"><span className="portal-icon admin-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 19V9m5 10V5m5 14v-7m5 7V3"/><path d="M2 21h20"/></svg></span><span className="portal-arrow" aria-hidden="true">↗</span></div>
            <div className="portal-card-kicker">FOR CITY TEAMS</div>
            <h3>Admin Portal</h3>
            <p>Monitor complaints, severity, priority, response stages, hotspots and area intelligence.</p>
            <span className="portal-card-cta">Sign in as an administrator <span aria-hidden="true">→</span></span>
          </Link>
          <Link to="/worker/login" className="portal-card worker-card">
            <div className="portal-card-top"><span className="portal-icon worker-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z"/><path d="M4 21a8 8 0 0 1 16 0"/><path d="M18 5h3v5h-3z"/></svg></span><span className="portal-arrow" aria-hidden="true">↗</span></div>
            <div className="portal-card-kicker">FOR FIELD TEAMS</div>
            <h3>Worker Portal</h3>
            <p>Accept assigned complaints, record work progress and submit completion evidence for review.</p>
            <span className="portal-card-cta">Sign in as a worker <span aria-hidden="true">→</span></span>
          </Link>
        </div>
      </section>
      <footer className="landing-footer"><span>CityLens AI</span><span>From Citizen Reports to City-Wide Action.</span></footer>
    </main>
  );
}

export default PortalLanding;
