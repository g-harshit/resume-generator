"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, ApiError, getToken, setToken, type User } from "@/lib/api";

type AuthState = {
  user: User | null;
  /** True until we know whether the stored token is valid. */
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  /** With the ID token from Google's button. */
  loginWithGoogle: (credential: string) => Promise<void>;
  logout: () => void;
  /** Sign in with a token the API already issued (after a password reset). */
  adopt: (token: string, user: User) => void;
};

const AuthContext = createContext<AuthState | null>(null);

// How long to keep retrying /auth/me when the API is unreachable or erroring
// before giving up (the token is kept either way).
const RETRY_FOR_MS = 60_000;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Read in an effect, not during render: the pages are prerendered without
    // localStorage, and the first client render has to match that HTML.
    let cancelled = false;
    const started = Date.now();

    async function load(delay: number) {
      if (!getToken()) {
        if (!cancelled) setLoading(false);
        return;
      }
      try {
        const me = await api.me();
        if (!cancelled) setUser(me);
      } catch (err) {
        // Only a 401 means "this token is no good". A network error or a 5xx means
        // the API is down or restarting — signing people out for that would be wrong.
        if (err instanceof ApiError && err.status === 401) {
          setToken(null);
        } else if (!cancelled && Date.now() - started < RETRY_FOR_MS) {
          setTimeout(() => load(Math.min(delay * 2, 8000)), delay);
          return;
        }
      }
      if (!cancelled) setLoading(false);
    }

    load(1000);
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    setToken(res.token);
    setUser(res.user);
  }, []);

  const register = useCallback(async (email: string, password: string, name: string) => {
    const res = await api.register(email, password, name);
    setToken(res.token);
    setUser(res.user);
  }, []);

  const loginWithGoogle = useCallback(async (credential: string) => {
    const res = await api.googleSignIn(credential);
    setToken(res.token);
    setUser(res.user);
  }, []);

  const adopt = useCallback((token: string, next: User) => {
    setToken(token);
    setUser(next);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, loginWithGoogle, logout, adopt }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
