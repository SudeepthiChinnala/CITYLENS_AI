import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { getSession, logoutPortal } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUserState] = useState(() => {
    try {
      const stored = localStorage.getItem('citylens_user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);

  const setAuthSession = (session) => {
    if (session) {
      const userPayload = { role: session.role, account_id: session.account_id };
      setUserState(userPayload);
      localStorage.setItem('citylens_user', JSON.stringify(userPayload));
      if (session.token) {
        localStorage.setItem('citylens_token', session.token);
      }
    } else {
      setUserState(null);
      localStorage.removeItem('citylens_user');
      localStorage.removeItem('citylens_token');
    }
  };

  useEffect(() => {
    let active = true;
    getSession()
      .then(session => {
        if (active) {
          setAuthSession(session);
        }
      })
      .catch(() => {
        if (active) {
          setAuthSession(null);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const signOut = async () => {
    try {
      await logoutPortal();
    } catch (e) {
      // Ignore network errors during signout
    } finally {
      setAuthSession(null);
    }
  };

  const value = useMemo(() => ({ user, setUser: setAuthSession, loading, signOut }), [user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}
