import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from "recharts";
import { getClusterHealth } from "../api/clusters";

function DonutChart({ title, value }) {
  const safeValue = Number.isFinite(value) ? value : 0;

  const data = [
    { name: "Used", value: safeValue },
    { name: "Free", value: Math.max(0, 100 - safeValue) },
  ];

  return (
    <div style={styles.chartCard}>
      <h3 style={styles.chartTitle}>{title}</h3>

      <div style={{ width: "180px", height: "180px" }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              innerRadius={60}
              outerRadius={80}
              paddingAngle={3}
              dataKey="value"
            >
              <Cell fill="#c1121f" />
              <Cell fill="#ececec" />
            </Pie>

            <text
              x="50%"
              y="50%"
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="22"
              fontWeight="700"
              fill="#111"
            >
              {safeValue.toFixed(1)}%
            </text>
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function formatClusterName(name) {
  return name
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatPeriod(iso) {
  if (!iso) return "—";
  return iso.split("T")[0];
}

export default function ClusterStatus() {
  const { clusterId } = useParams();
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadHealth() {
      setLoading(true);
      setError("");

      const { ok, data } = await getClusterHealth(clusterId);

      if (cancelled) return;

      if (ok) {
        setHealth(data);
      } else {
        setHealth(null);
        setError(data?.error || "Failed to load cluster health");
      }

      setLoading(false);
    }

    loadHealth();

    return () => {
      cancelled = true;
    };
  }, [clusterId]);

  const metrics = health?.metrics ?? {};

  return (
    <section style={styles.page}>
      <div style={styles.container}>
        <span style={styles.badge}>Live Status</span>

        <h1 style={styles.heading}>
          {health?.cluster
            ? formatClusterName(health.cluster)
            : formatClusterName(clusterId)}
        </h1>

        <p style={styles.subheading}>
          Slurm cluster utilization from{" "}
          <code>sreport cluster Utilization</code>.
        </p>

        {health?.period && (
          <p style={styles.period}>
            Period: {formatPeriod(health.period.start)} —{" "}
            {formatPeriod(health.period.end)}
          </p>
        )}

        {loading && (
          <p style={styles.message}>Loading cluster metrics…</p>
        )}

        {error && !loading && (
          <div style={styles.errorBanner}>{error}</div>
        )}

        {!loading && !error && health && (
          <div style={styles.dashboardLayout}>
            <div style={styles.infoPanel}>
              <InfoRow label="Status" value="Online" />
              <InfoRow
                label="Allocated"
                value={`${metrics.allocated?.toFixed(1) ?? "—"}%`}
              />
              <InfoRow
                label="Idle"
                value={`${metrics.idle?.toFixed(1) ?? "—"}%`}
              />
              <InfoRow
                label="Down"
                value={`${metrics.down?.toFixed(1) ?? "—"}%`}
              />
              <InfoRow
                label="Planned Down"
                value={`${metrics.planned_down?.toFixed(1) ?? "—"}%`}
              />
              <InfoRow
                label="Planned"
                value={`${metrics.planned?.toFixed(1) ?? "—"}%`}
              />
              <InfoRow
                label="Reported"
                value={`${metrics.reported?.toFixed(1) ?? "—"}%`}
              />
            </div>

            <div style={styles.chartGrid}>
              <DonutChart title="Allocated" value={metrics.allocated} />
              <DonutChart title="Idle" value={metrics.idle} />
              <DonutChart title="Down" value={metrics.down} />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function InfoRow({ label, value }) {
  return (
    <div style={styles.infoRow}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    background: "linear-gradient(to bottom,#fafafa,#f6f7fb)",
    padding: "40px 30px 90px",
  },
  container: {
    maxWidth: "1200px",
    margin: "0 auto",
  },
  badge: {
    background: "#ffe5e5",
    color: "#c1121f",
    padding: "10px 18px",
    borderRadius: "999px",
    fontWeight: "600",
    fontSize: "14px",
  },
  heading: {
    fontSize: "34px",
    fontWeight: "500",
    marginTop: "10px",
    marginBottom: "4px",
    lineHeight: "1.15",
    letterSpacing: "-0.5px",
    maxWidth: "800px",
  },
  subheading: {
    color: "#666",
    marginBottom: "10px",
    marginTop: "6px",
    fontSize: "18px",
  },
  period: {
    color: "#888",
    fontSize: "14px",
    marginBottom: "20px",
  },
  message: {
    color: "#666",
    fontSize: "16px",
    marginTop: "24px",
  },
  errorBanner: {
    marginTop: "24px",
    background: "#fff1f2",
    border: "1px solid #fecdd3",
    color: "#c1121f",
    borderRadius: "12px",
    padding: "16px 18px",
    fontSize: "15px",
    fontWeight: "500",
  },
  dashboardLayout: {
    display: "flex",
    gap: "40px",
    marginTop: "28px",
    flexWrap: "wrap",
  },
  infoPanel: {
    flex: 1,
    minWidth: "340px",
    background: "#fff",
    borderRadius: "28px",
    padding: "18px 32px 28px",
    boxShadow: "0 8px 24px rgba(0,0,0,0.04)",
  },
  infoRow: {
    display: "flex",
    justifyContent: "space-between",
    padding: "18px 0",
    borderBottom: "1px solid #f1f1f1",
    fontSize: "17px",
    color: "#444",
  },
  chartGrid: {
    display: "flex",
    gap: "24px",
    flexWrap: "wrap",
    justifyContent: "center",
  },
  chartCard: {
    background: "#fff",
    borderRadius: "26px",
    padding: "18px 22px",
    border: "1px solid #ececec",
    boxShadow: "0 8px 24px rgba(0,0,0,0.04)",
    width: "240px",
    height: "280px",
    flexShrink: 0,
  },
  chartTitle: {
    marginBottom: "20px",
    fontSize: "15px",
    fontWeight: "550",
  },
};
