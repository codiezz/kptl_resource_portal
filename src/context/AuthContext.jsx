import { createContext, useContext, useState, useEffect } from "react";

const AuthContext = createContext(null);

// Base URL of the Flask backend
const API = "http://localhost:5000";

export function AuthProvider({ children }) {
  const [user, setUser] =
  useState(null);

const [role, setRole] =
  useState(null);

const [loading, setLoading] =
  useState(true);   // true while checking session

  // On app start, ask the backend if the user is already logged in
  useEffect(() => {
    fetch(`${API}/api/auth-check`, { credentials: "include" })
      .then((res) => res.json())
      .then((data) => {
  if (data.authenticated) {
    setUser(data.username);
    setRole(data.role);
  }
})
      .catch(() => {}) // network error — just treat as logged out
      .finally(() => setLoading(false));
  }, []);

  // ------------------------------------------------------------------
  // login(username, password) → { ok: true } or { ok: false, error }
  // ------------------------------------------------------------------
  async function login(username, password) {
   const res = await fetch(`${API}/api/login`, {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username, password }),
}); 
    const data = await res.json();
    if (res.ok) {
  setUser(data.username);
  setRole(data.role);

  return { ok: true };
}
    return { ok: false, error: data.error || "Login failed" };
  }

  // ------------------------------------------------------------------
  // logout()
  // ------------------------------------------------------------------
  async function logout() {
    await fetch(`${API}/api/logout`, {
      method:      "POST",
      credentials: "include",
    });
    setUser(null);
setRole(null);
  }

  return (
   <AuthContext.Provider
  value={{
    user,
    role,
    loading,
    login,
    logout,
  }}
>
      {children}
    </AuthContext.Provider>
  );
}

// Convenience hook
export function useAuth() {
  return useContext(AuthContext);
}
