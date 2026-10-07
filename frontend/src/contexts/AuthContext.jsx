import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { getSession, logoutPortal } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getSession()
      .then(session => { if (active) setUser(session); })
      .catch(() => { if (active) setUser(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const signOut = async () => {
    try {
      await logoutPortal();
    } finally {
      setUser(null);
    }
  };

  const value = useMemo(() => ({ user, setUser, loading, signOut }), [user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}
