import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * RequireAuth
 *
 * Wrap any <Route> element with this component to make it protected.
 * If the user is not logged in they are redirected to "/" automatically.
 *
 * Usage in your router:
 *   <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
 */
export default function RequireAuth({ children }) {
  const { user, loading } = useAuth();

  // While checking session with the backend, show a neutral loading screen
  if (loading) {
    return (
      <div style={styles.loading}>
        <span>Checking session…</span>
      </div>
    );
  }

  // Not authenticated → kick back to homepage
  if (!user) {
    return <Navigate to="/" replace />;
  }

  return children;
}

const styles = {
  loading: {
    minHeight: "100vh", display: "flex",
    alignItems: "center", justifyContent: "center",
    color: "#94a3b8", fontSize: "18px",
    background: "#0a0f1e",
  },
};
