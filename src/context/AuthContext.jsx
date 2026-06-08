import { createContext, useContext, useState, useEffect } from "react";
import * as authApi from "../api/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [role, setRole] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authApi
      .authCheck()
      .then(({ data }) => {
        if (data?.authenticated) {
          setUser(data.username);
          setRole(data.role);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function login(username, password) {
    const { ok, data } = await authApi.login(username, password);

    if (ok) {
      setUser(data.username);
      setRole(data.role);
      return { ok: true };
    }

    return { ok: false, error: data?.error || "Login failed" };
  }

  async function logout() {
    await authApi.logout();
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

export function useAuth() {
  return useContext(AuthContext);
}
