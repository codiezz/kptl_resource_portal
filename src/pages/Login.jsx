import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import image from "../components/image/images.png";

const ALLOWED_EMAIL_DOMAIN = "@iiser.ac.in";
const MIN_PASSWORD_LENGTH = 6;

export default function Login() {
  const { user, loading: authLoading, login, register } = useAuth();
  const navigate = useNavigate();

  const [isRegistering, setIsRegistering] = useState(false);

  // --- Login form state ---
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [submitting, setSubmitting] = useState(false);

  // --- Registration form state ---
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirmPassword, setRegConfirmPassword] = useState("");
  const [regError, setRegError] = useState("");
  const [regSubmitting, setRegSubmitting] = useState(false);

  // Already logged in → bounce straight to home, don't show login again
  if (!authLoading && user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    const result = await login(email, password);

    setSubmitting(false);

    if (result.ok) {
      navigate("/");
    } else {
      setError(result.error);
    }
  }

  async function handleRegisterSubmit(e) {
    e.preventDefault();
    setRegError("");

    // --- Frontend validation (backend is still the source of truth) ---
    const normalizedEmail = regEmail.trim().toLowerCase();

    if (!normalizedEmail.endsWith(ALLOWED_EMAIL_DOMAIN)) {
      setRegError(`Email must end with ${ALLOWED_EMAIL_DOMAIN}`);
      return;
    }

    if (regPassword.length < MIN_PASSWORD_LENGTH) {
      setRegError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters`);
      return;
    }

    if (regPassword !== regConfirmPassword) {
      setRegError("Passwords do not match");
      return;
    }

    setRegSubmitting(true);

    const result = await register(normalizedEmail, regPassword);

    setRegSubmitting(false);

    if (result.ok) {
      // Backend already created the session — go straight to dashboard
      navigate("/");
    } else {
      setRegError(result.error);
    }
  }

  function switchToRegister() {
    setError("");
    setIsRegistering(true);
  }

  function switchToLogin() {
    setRegError("");
    setIsRegistering(false);
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        {/* Branding */}
        <div style={styles.brandRow}>
          <img src={image} alt="IISER Pune" style={styles.logo} />
          <div style={styles.brandText}>
            <div style={styles.instName}>IISER PUNE</div>
            <div style={styles.instSub}>
              Indian Institute of Science Education and Research Pune
            </div>
          </div>
        </div>

        <div style={styles.divider} />

        <h1 style={styles.title}>High Performance Computing Portal</h1>

        {!isRegistering ? (
          <>
            <p style={styles.subtitle}>Sign in to access the portal</p>

            {error && <div style={styles.errorBanner}>⚠️ {error}</div>}

            <form onSubmit={handleSubmit} style={styles.form}>
              <label style={styles.label}>Email</label>
              <input
                style={styles.input}
                type="email"
                autoFocus
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="abc@iiser.ac.in"
                disabled={submitting}
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
                disabled={submitting}
                required
              />

              <button
                style={submitting ? styles.btnDisabled : styles.btn}
                type="submit"
                disabled={submitting}
              >
                {submitting ? "Signing in…" : "Sign In"}
              </button>
            </form>

            <p style={styles.hint}>
              Sign in using your registered IISER email account.
            </p>

            <p style={styles.switchText}>
              Don't have an account?{" "}
              <span style={styles.switchLink} onClick={switchToRegister}>
                Create Account
              </span>
            </p>
          </>
        ) : (
          <>
            <p style={styles.subtitle}>Create your IISER HPC Portal account</p>

            {regError && <div style={styles.errorBanner}>⚠️ {regError}</div>}

            <form onSubmit={handleRegisterSubmit} style={styles.form}>
              <label style={styles.label}>IISER Email</label>
              <input
                style={styles.input}
                type="email"
                autoFocus
                autoComplete="email"
                value={regEmail}
                onChange={(e) => setRegEmail(e.target.value)}
                placeholder="abc@iiser.ac.in"
                disabled={regSubmitting}
                required
              />

              <label style={styles.label}>Password</label>
              <input
                style={styles.input}
                type="password"
                autoComplete="new-password"
                value={regPassword}
                onChange={(e) => setRegPassword(e.target.value)}
                placeholder="••••••••"
                disabled={regSubmitting}
                required
              />

              <label style={styles.label}>Confirm Password</label>
              <input
                style={styles.input}
                type="password"
                autoComplete="new-password"
                value={regConfirmPassword}
                onChange={(e) => setRegConfirmPassword(e.target.value)}
                placeholder="••••••••"
                disabled={regSubmitting}
                required
              />

              <button
                style={regSubmitting ? styles.btnDisabled : styles.btn}
                type="submit"
                disabled={regSubmitting}
              >
                {regSubmitting ? "Creating Account…" : "Create Account"}
              </button>
            </form>

            <p style={styles.switchText}>
              Already have an account?{" "}
              <span style={styles.switchLink} onClick={switchToLogin}>
                Sign In
              </span>
            </p>
          </>
        )}
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    width: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background:
      "linear-gradient(135deg, #f7f9fc 0%, #eef2f8 60%, #e8edf5 100%)",
    padding: "24px",
  },

  card: {
    background: "#ffffff",
    border: "1px solid #ececec",
    borderRadius: "24px",
    padding: "44px",
    width: "100%",
    maxWidth: "460px",
    boxShadow: "0 24px 70px rgba(0,0,0,0.10)",
    color: "#111111",
  },

  brandRow: {
    display: "flex",
    alignItems: "center",
    gap: "14px",
    marginBottom: "18px",
  },

  logo: {
    height: "56px",
    width: "auto",
    objectFit: "contain",
    flexShrink: 0,
  },

  brandText: {
    display: "flex",
    flexDirection: "column",
    lineHeight: 1.2,
  },

  instName: {
    fontSize: "16px",
    fontWeight: "750",
    color: "#000000",
    letterSpacing: "0.3px",
  },

  instSub: {
    fontSize: "11.5px",
    color: "#667085",
    marginTop: "2px",
  },

  divider: {
    height: "3px",
    width: "64px",
    background: "#c1121f",
    borderRadius: "2px",
    marginBottom: "22px",
  },

  title: {
    fontSize: "21px",
    fontWeight: "750",
    color: "#111111",
    margin: "0 0 4px 0",
    letterSpacing: "-0.3px",
  },

  subtitle: {
    color: "#667085",
    fontSize: "14.5px",
    marginBottom: "24px",
    marginTop: 0,
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

  switchText: {
    marginTop: "18px",
    fontSize: "13.5px",
    color: "#667085",
    textAlign: "center",
  },

  switchLink: {
    color: "#c1121f",
    fontWeight: "700",
    cursor: "pointer",
    textDecoration: "underline",
  },
};