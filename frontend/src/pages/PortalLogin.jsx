import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { loginAdmin, loginCitizen, loginWorker } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

function PortalLogin({ role }) {
  const isAdmin = role === 'admin';
  const isWorker = role === 'worker';
  const title = isAdmin ? 'Administrator sign in' : isWorker ? 'Worker sign in' : 'Welcome back';
  const home = isAdmin ? '/admin' : isWorker ? '/worker' : '/citizen';
  const location = useLocation();
  const navigate = useNavigate();
  const { user, setUser, loading } = useAuth();
  const [accountId, setAccountId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user?.role === role) navigate(home, { replace: true });
  }, [home, loading, navigate, role, user]);

  const submit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const session = isAdmin
        ? await loginAdmin(accountId.trim(), password)
        : isWorker ? await loginWorker(accountId.trim(), password) : await loginCitizen(accountId.trim(), password);
      setUser(session);
      const requested = location.state?.from?.pathname;
      const safeNext = typeof requested === 'string' && (requested === home || requested.startsWith(`${home}/`)) && !requested.endsWith('/login')
        ? requested
        : home;
      navigate(safeNext, { replace: true });
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const isWrongPortal = typeof detail === 'string' && detail.toLowerCase().includes('different portal');
      setError({
        title: isWrongPortal ? 'Wrong portal' : 'Unable to sign in',
        message: isWrongPortal
          ? 'These credentials are associated with another CityLens portal. Please use the appropriate portal to sign in.'
          : 'The credentials or portal role are incorrect. Please check your details and try again.',
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <main className="login-loading" aria-live="polite">Checking your secure session…</main>;

  return (
    <main className={`login-page ${isAdmin ? 'admin-login' : isWorker ? 'worker-login' : 'citizen-login'}`}>
      <div className="login-side">
        <Link to="/" className="login-brand"><span className="brand-mark"><span /><span /><span /></span><span>CITYLENS <strong>AI</strong></span></Link>
        <div className="login-side-copy">
          <div className="eyebrow">{isAdmin ? 'CITY OPERATIONS' : isWorker ? 'FIELD OPERATIONS' : 'CITIZEN SERVICES'}</div>
          <h1>{isAdmin ? 'A clearer view of city priorities.' : isWorker ? 'Keep assigned city work moving.' : 'Your report can move a city forward.'}</h1>
          <p>{isAdmin ? 'A focused workspace for complaints, response progress and urban risk intelligence.' : isWorker ? 'Sign in to accept assigned complaints, record progress and submit completion evidence.' : 'Sign in to report an issue, follow its progress and see public civic insights.'}</p>
          <div className="login-promise"><span className="promise-dot" /> Role-based access <span className="promise-separator">·</span> Private session</div>
        </div>
        <div className="login-side-foot">AI Urban Problem Intelligence Platform</div>
      </div>
      <section className="login-main">
        <div className="login-card">
          <Link to="/" className="back-link"><span aria-hidden="true">←</span> All portals</Link>
          <div className="login-card-heading"><div className="eyebrow">{isAdmin ? 'ADMIN PORTAL' : isWorker ? 'WORKER PORTAL' : 'CITIZEN PORTAL'}</div><h2>{title}</h2><p>Enter the credentials provided for your {isAdmin ? 'administrator' : isWorker ? 'worker' : 'citizen'} account.</p></div>
          {!isAdmin && !isWorker && location.state?.registrationNotice && <div className="login-success" role="status">{location.state.registrationNotice}</div>}
          <form onSubmit={submit} className="login-form">
            <label htmlFor="portal-account">{isAdmin ? 'Admin ID' : isWorker ? 'Worker ID' : 'Citizen ID or Email'}</label>
            <input id="portal-account" name="account_id" value={accountId} onChange={e => { setAccountId(e.target.value); if (error) setError(null); }} autoComplete="username" required maxLength={254} placeholder={isAdmin ? 'Enter your Admin ID' : isWorker ? 'Enter your Worker ID' : 'Enter your Citizen ID or email'} />
            <div className="password-label"><label htmlFor="portal-password">Password</label></div>
            <input id="portal-password" name="password" type="password" value={password} onChange={e => { setPassword(e.target.value); if (error) setError(null); }} autoComplete="current-password" required maxLength={1024} placeholder="Enter your password" />
            {error && <div className="login-error" role="alert"><strong>{error.title}</strong><span>{error.message}</span></div>}
            <button className="login-submit" type="submit" disabled={submitting}>{submitting ? 'Verifying…' : isAdmin ? 'Sign in to Admin Portal' : isWorker ? 'Sign in to Worker Portal' : 'Login to Citizen Portal'}<span aria-hidden="true">→</span></button>
          </form>
          {!isAdmin && !isWorker && <p className="register-prompt">Don’t have an account? <Link to="/citizen/register">Create Citizen Account</Link></p>}
          <div className="login-footnote">Your credentials are verified by the CityLens backend. They are not stored in this page.</div>
        </div>
      </section>
    </main>
  );
}

export default PortalLogin;
