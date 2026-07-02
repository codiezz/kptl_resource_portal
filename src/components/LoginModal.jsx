import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

export default function LoginModal({ onClose, redirectTo }) {
  const { login }           = useAuth();
  const navigate            = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]   = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const result = await login(email, password);

    setLoading(false);

    if (result.ok) {
      onClose();                                    // close modal
      navigate(redirectTo || "/dashboard");         // go to dashboard
    } else {
      setError(result.error);                       // show error in-place
    }
  }

  return (
    /* ---------- backdrop ---------- */
    <div style={styles.backdrop} onClick={onClose}>
      {/* ---------- modal box — stop click from closing ---------- */}
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>

        {/* header */}
        <div style={styles.header}>
          <span style={styles.title}>
  HPC Portal Login
</span>
          <button style={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
        </div>

        <p style={styles.subtitle}>Sign in to access this section</p>

        {/* error banner */}
        {error && (
          <div style={styles.errorBanner}>
            ⚠️ {error}
          </div>
        )}

        {/* form */}
        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>Email</label>
          <input
            style={styles.input}
            type="email"
            autoFocus
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="abc@iiserpune.ac.in"
            disabled={loading}
            required
          />

          <label style={styles.label}>Password</label>
          <input
            style={styles.input}
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            disabled={loading}
            required
          />

          <button style={loading ? styles.btnDisabled : styles.btn} type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>

      </div>
    </div>
  );
}

/* ---------- inline styles (no extra CSS file needed) ---------- */
const styles = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.35)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
    backdropFilter: "blur(6px)",
  },

  modal: {
    background: "#ffffff",
    border: "1px solid #ececec",
    borderRadius: "24px",
    padding: "36px",
    width: "100%",
    maxWidth: "440px",
    boxShadow: "0 20px 60px rgba(0,0,0,0.12)",
    color: "#111111",
  },

  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "10px",
  },

  title: {
    fontSize: "24px",
    fontWeight: "800",
    color: "#111111",
    letterSpacing: "-0.5px",
  },

  closeBtn: {
    background: "#f5f5f5",
    border: "none",
    width: "38px",
    height: "38px",
    borderRadius: "50%",
    color: "#555",
    fontSize: "18px",
    cursor: "pointer",
    transition: "0.2s ease",
  },

  subtitle: {
    color: "#666",
    fontSize: "15px",
    marginBottom: "24px",
    marginTop: 0,
    lineHeight: "1.6",
  },

  errorBanner: {
    background: "#fff1f2",
    border: "1px solid #fecdd3",
    color: "#c1121f",
    borderRadius: "12px",
    padding: "14px",
    marginBottom: "18px",
    fontSize: "14px",
    fontWeight: "500",
  },

  form: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },

  label: {
    fontSize: "14px",
    fontWeight: "600",
    color: "#222",
    marginBottom: "2px",
  },

  input: {
    background: "#fafafa",
    border: "1px solid #e5e5e5",
    borderRadius: "14px",
    padding: "14px 16px",
    color: "#111111",
    fontSize: "15px",
    outline: "none",
    transition: "0.2s ease",
  },

  btn: {
    marginTop: "12px",
    padding: "15px",
    background: "#c1121f",
    color: "#ffffff",
    border: "none",
    borderRadius: "14px",
    fontSize: "16px",
    fontWeight: "700",
    cursor: "pointer",
    transition: "0.2s ease",
  },

  btnDisabled: {
    marginTop: "12px",
    padding: "15px",
    background: "#d1d5db",
    color: "#6b7280",
    border: "none",
    borderRadius: "14px",
    fontSize: "16px",
    fontWeight: "700",
    cursor: "not-allowed",
  },

  hint: {
    marginTop: "20px",
    fontSize: "12px",
    color: "#888",
    textAlign: "center",
    lineHeight: "1.6",
    borderTop: "1px solid #efefef",
    paddingTop: "16px",
  },
};