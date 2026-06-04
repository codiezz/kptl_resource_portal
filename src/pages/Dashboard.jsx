
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

export default function Dashboard() {
  const { user, role } = useAuth();
  const navigate = useNavigate();

  return role === "admin" ? (
    <AdminDashboard
      user={user}
      navigate={navigate}
    />
  ) : (
    <UserDashboard
      user={user}
      navigate={navigate}
    />
  );
}

/* ================= USER DASHBOARD ================= */

function UserDashboard({
  user,
  navigate,
}) {
  return (
    <div style={styles.page}>
      <main style={styles.main}>
        {/* Back Button */}
        <div style={styles.topBar}>
          <button
            style={styles.homeBtn}
            onClick={() =>
              navigate("/")
            }
          >
            ← Back to Home
          </button>
        </div>

        <h1 style={styles.heading}>
          Dashboard
        </h1>

        {/* Welcome */}
        <div style={styles.welcomeSection}>
          <h1 style={styles.welcomeTitle}>
            Welcome back, {user}
          </h1>

          <p style={styles.welcomeText}>
            Manage your HPC resources,
            monitor recent activity,
            and access cluster services.
          </p>
        </div>

        {/* Top Grid */}
        <div style={styles.grid}>
          {/* Recent Jobs */}
          <div style={styles.card}>
            <h2 style={styles.cardTitle}>
              Recent Jobs
            </h2>

            <div style={styles.jobItem}>
              <span>job_1042</span>
              <span style={styles.running}>
                Running
              </span>
            </div>

            <div style={styles.jobItem}>
              <span>job_1038</span>
              <span style={styles.completed}>
                Completed
              </span>
            </div>

            <div style={styles.jobItem}>
              <span>job_1031</span>
              <span style={styles.queued}>
                Queued
              </span>
            </div>
          </div>

          {/* Quick Actions */}
          <div style={styles.card}>
            <h2 style={styles.cardTitle}>
              Quick Actions
            </h2>

            <button
              style={styles.actionBtn}
              onClick={() =>
                navigate("/jobs")
              }
            >
              View Clusters
            </button>

            <button
              style={styles.actionBtn}
              onClick={() =>
                navigate(
                  "/cluster-status"
                )
              }
            >
              Live Status
            </button>

            <button
              style={styles.actionBtn}
              onClick={() =>
                navigate(
                  "/cluster-docs"
                )
              }
            >
              Download Docs
            </button>
          </div>
        </div>

        {/* Cluster Health */}
        <div style={styles.healthCard}>
          <h2 style={styles.cardTitle}>
            Cluster Health
          </h2>

          <div style={styles.clusterItem}>
            <div>
              <h4 style={styles.clusterName}>
                Bhoomi Cluster
              </h4>

              <p style={styles.clusterDesc}>
                CPU Cluster
              </p>
            </div>

            <span style={styles.online}>
              ● Online
            </span>
          </div>

          <div style={styles.clusterItem}>
            <div>
              <h4 style={styles.clusterName}>
                Athena Cluster
              </h4>

              <p style={styles.clusterDesc}>
                CPU + GPU Cluster
              </p>
            </div>

            <span style={styles.busy}>
              ● Busy
            </span>
          </div>

          <div style={styles.clusterItem}>
            <div>
              <h4 style={styles.clusterName}>
                High-End Server
              </h4>

              <p style={styles.clusterDesc}>
                GPU Compute Server
              </p>
            </div>

            <span style={styles.online}>
              ● Healthy
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}

/* ================= ADMIN DASHBOARD ================= */

function AdminDashboard({
  user,
  navigate,
}) {
  return (
    <div style={styles.page}>
      <main style={styles.main}>
        <div style={styles.topBar}>
          <button
            style={styles.homeBtn}
            onClick={() =>
              navigate("/")
            }
          >
            ← Back to Home
          </button>
        </div>

        <h1 style={styles.heading}>
          Admin Dashboard
        </h1>

        <div style={styles.welcomeSection}>
          <h1 style={styles.welcomeTitle}>
            Welcome back, {user}
          </h1>

          <p style={styles.welcomeText}>
            Monitor cluster health,
            manage users,
            and oversee HPC operations.
          </p>
        </div>

        <div style={styles.grid}>
          {/* Cluster Overview */}
          <div style={styles.card}>
            <h2 style={styles.cardTitle}>
              Cluster Overview
            </h2>

            <div style={styles.jobItem}>
              <span>
                Active Nodes
              </span>
              <span>28</span>
            </div>

            <div style={styles.jobItem}>
              <span>
                Running Jobs
              </span>
              <span>143</span>
            </div>

            <div style={styles.jobItem}>
              <span>
                Queue Length
              </span>
              <span>34</span>
            </div>
          </div>

          {/* Admin Actions */}
          <div style={styles.card}>
            <h2 style={styles.cardTitle}>
              Admin Actions
            </h2>

            <button
              style={styles.actionBtn}
            >
              Manage Users
            </button>

            <button
              style={styles.actionBtn}
            >
              Cluster Monitoring
            </button>

            <button
              style={styles.actionBtn}
            >
              Analytics
            </button>

            <button
              style={styles.actionBtn}
            >
              Resource Allocation
            </button>
          </div>
        </div>

        {/* System Health */}
        <div style={styles.healthCard}>
          <h2 style={styles.cardTitle}>
            System Health
          </h2>

          <div style={styles.clusterItem}>
            <span>
              Bhoomi Cluster
            </span>

            <span
              style={styles.online}
            >
              ● Online
            </span>
          </div>

          <div style={styles.clusterItem}>
            <span>
              GPU Cluster
            </span>

            <span
              style={styles.busy}
            >
              ● Busy
            </span>
          </div>

          <div style={styles.clusterItem}>
            <span>
              High-End Server
            </span>

            <span
              style={styles.online}
            >
              ● Healthy
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}

/* ================= STYLES ================= */

const styles = {
  page: {
    minHeight: "100vh",
    background: "#fafafa",
    color: "#111",
    fontFamily:
      "system-ui, sans-serif",
  },

  main: {
    maxWidth: "1200px",
    margin: "0 auto",
    padding:
      "26px 30px 60px",
  },

  topBar: {
    display: "flex",
    justifyContent:
      "flex-start",
    marginBottom: "18px",
  },

  homeBtn: {
    background: "#ffffff",
    border:
      "1px solid #ececec",
    padding: "10px 18px",
    borderRadius: "12px",
    cursor: "pointer",
    fontWeight: "600",
    fontSize: "14px",
    color: "#333",
    boxShadow:
      "0 4px 12px rgba(0,0,0,0.04)",
  },

  heading: {
    fontSize: "44px",
    fontWeight: "700",
    marginBottom: "8px",
  },

  welcomeSection: {
    marginBottom: "28px",
  },

  welcomeTitle: {
    fontSize: "34px",
    fontWeight: "600",
    marginBottom: "8px",
  },

  welcomeText: {
    color: "#666",
    fontSize: "16px",
    lineHeight: "1.7",
  },

  grid: {
    display: "grid",
    gridTemplateColumns:
      "repeat(auto-fit, minmax(340px, 1fr))",
    gap: "26px",
    marginBottom: "28px",
  },

  card: {
    background: "#ffffff",
    border:
      "1px solid #ececec",
    borderRadius: "22px",
    padding: "28px",
    boxShadow:
      "0 8px 24px rgba(0,0,0,0.04)",
  },

  cardTitle: {
    fontSize: "22px",
    fontWeight: "600",
    marginBottom: "22px",
  },

  jobItem: {
    display: "flex",
    justifyContent:
      "space-between",
    padding: "14px 0",
    borderBottom:
      "1px solid #f2f2f2",
  },

  running: {
    color: "#2563eb",
    fontWeight: "600",
  },

  completed: {
    color: "#16a34a",
    fontWeight: "600",
  },

  queued: {
    color: "#ca8a04",
    fontWeight: "600",
  },

  actionBtn: {
    width: "100%",
    padding: "14px",
    marginBottom: "12px",
    border:
      "1px solid #ececec",
    background: "#fafafa",
    borderRadius: "14px",
    cursor: "pointer",
    fontWeight: "500",
    fontSize: "15px",
  },

  healthCard: {
    background: "#ffffff",
    border:
      "1px solid #ececec",
    borderRadius: "22px",
    padding: "28px",
    boxShadow:
      "0 8px 24px rgba(0,0,0,0.04)",
  },

  clusterItem: {
    display: "flex",
    justifyContent:
      "space-between",
    alignItems: "center",
    padding: "18px 0",
    borderBottom:
      "1px solid #f2f2f2",
  },

  clusterName: {
    margin: 0,
    fontSize: "17px",
    fontWeight: "600",
  },

  clusterDesc: {
    marginTop: "4px",
    fontSize: "14px",
    color: "#666",
  },

  online: {
    color: "#16a34a",
    fontWeight: "600",
  },

  busy: {
    color: "#ca8a04",
    fontWeight: "600",
  },
};

