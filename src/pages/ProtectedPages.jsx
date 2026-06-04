import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function ProtectedPage({ title, icon, description }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/");
  }

    return (
  <div style={styles.page}>
    <main style={styles.container}>
      <div style={styles.header}>
        <span style={styles.icon}>{icon}</span>

        <div>
          <h1 style={styles.title}>
            {title}
          </h1>

          <p style={styles.desc}>
            {description}
          </p>
        </div>
      </div>

      <div style={styles.infoCard}>
        <h3 style={styles.sectionTitle}>
          Access Information
        </h3>

        <p style={styles.infoText}>
          You are authenticated as{" "}
          <strong>{user}</strong>
        </p>

        <p style={styles.infoSubtext}>
          This protected module is
          currently under development.
          HPC resources and tools will
          be integrated here.
        </p>
      </div>

      <div style={styles.actionGrid}>
        <div style={styles.actionCard}>
          <h3>Module Status</h3>
          <p>
            Active and protected
            through authentication.
          </p>
        </div>

        <div style={styles.actionCard}>
          <h3>User Session</h3>
          <p>
            Session verified through
            Flask backend cookies.
          </p>
        </div>
      </div>

      <button
        style={styles.backBtn}
        onClick={() =>
          navigate("/dashboard")
        }
      >
        ← Back to Dashboard
      </button>
    </main>
  </div>
);
}

export function Jobs() {
  return <ProtectedPage title="Job Management" description="Submit and monitor HPC jobs on the cluster." />;
}

export function Docs() {
  return <ProtectedPage title="Documentation" description="Browse guides, tutorials, and API references." />;
}

export function Support() {
  return <ProtectedPage title="Support" description="Open tickets and track your support requests." />;
}

const styles = {
  page: {
  minHeight: "100vh",
  background: "#f8fafc",
},

container: {
  maxWidth: "1200px",
  margin: "0 auto",
  padding: "60px 24px",
},

header: {
  display: "flex",
  alignItems: "center",
  gap: "24px",
  marginBottom: "36px",
},

icon: {
  fontSize: "56px",
},

title: {
  fontSize: "42px",
  fontWeight: "800",
  color: "#111827",
  marginBottom: "10px",
},

desc: {
  fontSize: "18px",
  color: "#6b7280",
  lineHeight: 1.7,
},

infoCard: {
  background: "#ffffff",
  borderRadius: "24px",
  padding: "36px",
  boxShadow:
    "0 8px 30px rgba(0,0,0,0.06)",
  border: "1px solid #ececec",
  marginBottom: "30px",
},

sectionTitle: {
  fontSize: "22px",
  fontWeight: "700",
  marginBottom: "18px",
},

infoText: {
  fontSize: "17px",
  color: "#111827",
},

infoSubtext: {
  color: "#6b7280",
  lineHeight: "1.8",
},

actionGrid: {
  display: "grid",
  gridTemplateColumns:
    "repeat(auto-fit, minmax(280px,1fr))",
  gap: "24px",
  marginBottom: "40px",
},

actionCard: {
  background: "#ffffff",
  padding: "28px",
  borderRadius: "20px",
  border: "1px solid #ececec",
  boxShadow:
    "0 6px 20px rgba(0,0,0,0.05)",
},

backBtn: {
  background: "#c1121f",
  color: "#fff",
  border: "none",
  borderRadius: "14px",
  padding: "14px 28px",
  fontSize: "16px",
  fontWeight: "700",
  cursor: "pointer",
},
};
