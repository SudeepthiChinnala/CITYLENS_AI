import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { registerCitizen } from '../services/api';

function registrationError(error) {
  const status = error?.response?.status;
  if (status === 409) return 'An account with this email already exists. Sign in or use a different email address.';
  if (status === 422) return 'Please check your name, email, phone number, and password requirements.';
  if (!error?.response) return 'Could not reach the CityLens AI backend. Please try again.';
  return 'We could not create the account right now. Please try again shortly.';
}

function PortalRegister() {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setError('');
    if (password.length < 8) {
      setError('Choose a password with at least 8 characters.');
      return;
    }
    if (password !== confirmPassword) {
      setError('The password and confirmation do not match.');
      return;
    }
    setSubmitting(true);
    try {
      const result = await registerCitizen({
        full_name: fullName.trim(),
        email: email.trim(),
        phone: phone.trim() || null,
        password,
      });
      navigate('/citizen/login', {
        replace: true,
        state: { registrationNotice: `Registration successful. Your Citizen ID is ${result.citizen_id}. Sign in with your ID or email.` },
      });
    } catch (err) {
      setError(registrationError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="login-page citizen-login">
      <div className="login-side">
        <Link to="/" className="login-brand"><span className="brand-mark" aria-hidden="true"><span /><span /><span /></span><span>CITYLENS <strong>AI</strong></span></Link>
        <div className="login-side-copy">
          <div className="eyebrow">CITIZEN SERVICES</div>
          <h1>Your report can move a city forward.</h1>
          <p>Create an account to report an issue, follow its progress, and explore public civic insights.</p>
          <div className="login-promise"><span className="promise-dot" /> Private account <span className="promise-separator">·</span> Secure sign in</div>
        </div>
        <div className="login-side-foot">AI Urban Problem Intelligence Platform</div>
      </div>
      <section className="login-main">
        <div className="login-card">
          <Link to="/" className="back-link"><span aria-hidden="true">←</span> All portals</Link>
          <div className="login-card-heading"><div className="eyebrow">CITIZEN PORTAL</div><h2>Create your account</h2><p>Your password is verified and stored securely by the CityLens backend.</p></div>
          <form onSubmit={submit} className="login-form">
            <label htmlFor="register-name">Full Name</label>
            <input id="register-name" name="full_name" type="text" autoComplete="name" required maxLength={120} value={fullName} onChange={event => setFullName(event.target.value)} placeholder="Enter your full name" />
            <label htmlFor="register-email">Email</label>
            <input id="register-email" name="email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={event => setEmail(event.target.value)} placeholder="you@example.com" />
            <label htmlFor="register-phone">Phone Number <span className="placeholder">(optional)</span></label>
            <input id="register-phone" name="phone" type="tel" autoComplete="tel" maxLength={30} value={phone} onChange={event => setPhone(event.target.value)} placeholder="Include country code if needed" />
            <label htmlFor="register-password">Password</label>
            <input id="register-password" name="new_password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={password} onChange={event => setPassword(event.target.value)} placeholder="At least 8 characters" />
            <label htmlFor="register-confirm-password">Confirm Password</label>
            <input id="register-confirm-password" name="confirm_password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} placeholder="Enter your password again" />
            {error && <div className="login-error" role="alert">{error}</div>}
            <button className="login-submit" type="submit" disabled={submitting}>{submitting ? 'Creating account…' : 'Create Account'}<span aria-hidden="true">→</span></button>
          </form>
          <p className="register-prompt">Already have an account? <Link to="/citizen/login">Login</Link></p>
        </div>
      </section>
    </main>
  );
}

export default PortalRegister;
