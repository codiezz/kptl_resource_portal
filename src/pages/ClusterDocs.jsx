import { useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";

export default function ClusterDocs() {
  const { clusterId } = useParams();

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [loadingType, setLoadingType] = useState(null);
  const [error, setError] = useState("");

  const handleGenerateReport = async (reportType) => {
  if (!startDate || !endDate) {
    setError("Please select both start and end dates.");
    return;
  }
  setError("");
  setLoadingType(reportType);
  try {
    const response = await axios.post(
      `http://localhost:5000/api/clusters/${clusterId}/report/${reportType}`,
      { start: startDate, end: endDate },
      { withCredentials: true, responseType: "blob" }
    );
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute(
      "download",
      `${reportType}_report_${clusterId}_${startDate}_to_${endDate}.pdf`
    );
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    setError("Failed to generate report. Please try again.");
  } finally {
    setLoadingType(null);
  }
};

  return (
    <section style={styles.page}>
      <div style={styles.container}>
        <span style={styles.badge}>Cluster Analytics</span>

        <h1 style={styles.heading}>
          {formatClusterName(clusterId)}
        </h1>

        <p style={styles.subheading}>
          Select a date range to view cluster statistics.
        </p>

        <div style={styles.filterCard}>
          <div style={styles.inputGroup}>
            <label>Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              style={styles.input}
            />
          </div>

          <div style={styles.inputGroup}>
            <label>End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              style={styles.input}
            />
          </div>

          {error && (
            <p style={{ color: "#c1121f", fontSize: "13px", width: "100%" }}>
              {error}
            </p>
          )}

          <div style={styles.buttonGrid}>
  {[
    { type: "cluster", label: "Cluster Report", enabled: true },
    { type: "gpu",     label: "GPU Report",     enabled: true },
    { type: "account", label: "Account Report", enabled: false },
    { type: "user",    label: "User Report",    enabled: false },
  ].map(({ type, label, enabled }) => {
    const isLoading = loadingType === type;
    const isDisabled = !enabled || loadingType !== null;
    return (
      <button
        key={type}
        style={{
          ...styles.button,
          opacity: !enabled ? 0.4 : isDisabled ? 0.7 : 1,
          cursor: isDisabled ? "not-allowed" : "pointer",
        }}
        onClick={() => enabled && handleGenerateReport(type)}
        disabled={isDisabled}
        title={!enabled ? "Not yet available" : undefined}
      >
        {isLoading ? "Generating..." : label}
      </button>
    );
  })}
</div>

        </div>

        
      </div>
    </section>
  );
}

function formatClusterName(name) {
  return name
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const styles = {
  page: {
    minHeight: "100vh",
    background: "linear-gradient(to bottom,#fafafa,#f6f7fb)",
    padding: "40px 30px 90px",
  },

  container: {
    maxWidth: "900px",
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
    marginBottom: "50px",
  },

  filterCard: {
    background: "#fff",
    borderRadius: "24px",
    padding: "30px",
    border: "1px solid #ececec",
    display: "flex",
    gap: "20px",
    flexWrap: "wrap",
    alignItems: "end",
  },

  inputGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },

  input: {
    border: "1px solid #ddd",
    borderRadius: "12px",
    padding: "12px",
  },

  button: {
    background: "#c1121f",
    color: "#fff",
    border: "none",
    borderRadius: "12px",
    padding: "14px 24px",
  },

  stats: {
    marginTop: "40px",
    background: "#fff",
    padding: "30px",
    borderRadius: "24px",
    lineHeight: "2",
  },

  chartGrid: {
    display: "flex",
    gap: "28px",
    flexWrap: "wrap",
    marginTop: "50px",
  },

  chartCard: {
    background: "#fff",
    borderRadius: "24px",
    padding: "14px 18px",
    border: "1px solid #ececec",
    boxShadow: "0 6px 18px rgba(0,0,0,0.035)",
    width: "210px",
    height: "230px",
    flexShrink: 0,
  },

  chartTitle: {
    marginBottom: "14px",
    fontSize: "16px",
    fontWeight: "600",
  },
  buttonGrid: {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: "12px",
  width: "100%",
},
};