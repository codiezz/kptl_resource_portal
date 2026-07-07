import { useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import PermissionDeniedModal from "../components/PermissionDeniedModal";
import { API_BASE } from "../api/client";
export default function ClusterDocs() {
  const { clusterId } = useParams();

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [loadingType, setLoadingType] = useState(null);
  const [error, setError] = useState("");
  const [showPermissionModal, setShowPermissionModal] = useState(false);

  // === Account/User tree state ===
  const [showAccountTree, setShowAccountTree] = useState(false);
  const [accountTree, setAccountTree] = useState([]); // [{ name, expanded, users: [] }]
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [downloadingKey, setDownloadingKey] = useState(null); // "account:acct1" or "user:acct1:user1"

  // === Single source of truth: is ANY report action in flight ===
  const isBusy = loadingType !== null || loadingAccounts || downloadingKey !== null;

  const handleGenerateReport = async (reportType) => {
    if (!startDate || !endDate) {
      setError("Please select both start and end dates.");
      return;
    }
    setError("");
    setLoadingType(reportType);
    try {
      const response = await axios.post(
        `${API_BASE}/api/clusters/${clusterId}/report/${reportType}`,
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
        if (err.response && err.response.status === 403) {
          setShowPermissionModal(true);
        } else {
            setError("Failed to generate report. Please try again."); //  error handling
    }
    } finally {
      setLoadingType(null);
    }
  };

  // === Fetch accounts + their users in ONE call, toggle tree open/closed ===
  const handleAccountReportClick = async () => {
    // If already loaded, just toggle visibility instead of refetching
    if (accountTree.length > 0) {
      setShowAccountTree((prev) => !prev);
      return;
    }

    setLoadingAccounts(true);
    try {
      const res = await axios.post(
        `${API_BASE}/api/clusters/${clusterId}/report/accounts`,
        { start: startDate, end: endDate },
        { withCredentials: true }
      );
      const accounts = res.data.accounts || []; // [{ name, users: [] }]
      setAccountTree(
        accounts.map((a) => ({
          name: a.name,
          users: a.users || [],
          expanded: false,
        }))
      );
      setShowAccountTree(true);
    } catch (err) {
        if (err.response && err.response.status === 403) {
          setShowPermissionModal(true);
      } else {
          console.error("Failed to fetch accounts", err);
          setError("Failed to load accounts.");
        }
    } finally {
      setLoadingAccounts(false);
    }
  };

  // === Toggle expand/collapse for one account (no fetch — users already in memory) ===
  const toggleAccountExpand = (accountName) => {
    setAccountTree((prev) =>
      prev.map((a) =>
        a.name === accountName ? { ...a, expanded: !a.expanded } : a
      )
    );
  };

  // === Download an account-level PDF ===
  const downloadAccountReport = async (accountName) => {
    if (isBusy) return;
    const key = `account:${accountName}`;
    setDownloadingKey(key);
    try {
      const res = await axios.post(
        `${API_BASE}/api/clusters/${clusterId}/report/account`,
        { start: startDate, end: endDate, account: accountName },
        { responseType: "blob", withCredentials: true }
      );
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute(
        "download",
        `account_report_${clusterId}_${accountName}_${startDate}_to_${endDate}.pdf`
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      if (err.response && err.response.status === 403) {
        setShowPermissionModal(true);
      } else {
        console.error("Failed to download account report", err);
      }
    } finally {
      setDownloadingKey(null);
    }
  };

  // === Download a user-level PDF ===
  const downloadUserReport = async (accountName, userLogin) => {
    if (isBusy) return;
    const key = `user:${accountName}:${userLogin}`;
    setDownloadingKey(key);
    try {
      const res = await axios.post(
        `${API_BASE}/api/clusters/${clusterId}/report/user`,
        { start: startDate, end: endDate, account: accountName, user: userLogin },
        { responseType: "blob", withCredentials: true }
      );
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute(
        "download",
        `user_report_${clusterId}_${accountName}_${userLogin}_${startDate}_to_${endDate}.pdf`
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      if (err.response && err.response.status === 403) {
        setShowPermissionModal(true);
    } else {
        console.error("Failed to download user report", err);
      }
    } finally {
      setDownloadingKey(null);
    }
  };

  return (
    <section style={styles.page}>
      <div style={styles.container}>
        <span style={styles.badge}>Cluster Analytics</span>

        <h1 style={styles.heading}>{formatClusterName(clusterId)}</h1>

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
              { type: "gpu", label: "GPU Report", enabled: true },
            ].map(({ type, label, enabled }) => {
              const isLoading = loadingType === type;
              const isDisabled = !enabled || isBusy;
              return (
                <button
                  key={type}
                  style={{
                    ...styles.button,
                    opacity: !enabled ? 0.4 : isDisabled ? 0.7 : 1,
                    cursor: isDisabled ? "not-allowed" : "pointer",
                  }}
                  onClick={() => enabled && !isBusy && handleGenerateReport(type)}
                  disabled={isDisabled}
                  title={!enabled ? "Not yet available" : undefined}
                >
                  {isLoading ? "Generating..." : label}
                </button>
              );
            })}

            {/* === ACCOUNT REPORT TREE (replaces old User Report + Account Report buttons) === */}
            <div style={{ position: "relative" }}>
              <button
                onClick={() => !isBusy && handleAccountReportClick()}
                disabled={isBusy}
                style={{
                  ...styles.button,
                  width: "100%",
                  opacity: isBusy ? 0.7 : 1,
                  cursor: isBusy ? "not-allowed" : "pointer",
                }}
              >
                {loadingAccounts ? "Loading..." : "Account Report"}
              </button>

              {showAccountTree && (
                <div
                  style={{
                    marginTop: "8px",
                    background: "#fff",
                    border: "1px solid #ddd",
                    borderRadius: "8px",
                    boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                    maxHeight: "320px",
                    overflowY: "auto",
                  }}
                >
                  {accountTree.length === 0 ? (
                    <div style={{ padding: "12px", fontSize: "14px", color: "#888" }}>
                      No accounts found
                    </div>
                  ) : (
                    accountTree.map((acct) => (
                      <div key={acct.name} style={{ borderBottom: "1px solid #f0f0f0" }}>
                        {/* Account row */}
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            padding: "10px 12px",
                            opacity: isBusy ? 0.5 : 1,
                          }}
                        >
                          <span
                            onClick={() => !isBusy && toggleAccountExpand(acct.name)}
                            style={{
                              cursor: isBusy ? "not-allowed" : "pointer",
                              width: "20px",
                              display: "inline-block",
                              fontSize: "12px",
                              color: "#666",
                              userSelect: "none",
                            }}
                          >
                            {acct.expanded ? "▼" : "▶"}
                          </span>

                          <span
                            onClick={() => !isBusy && downloadAccountReport(acct.name)}
                            style={{
                              flex: 1,
                              cursor: isBusy ? "not-allowed" : "pointer",
                              fontSize: "14px",
                              fontWeight: 500,
                              color: "#1a1a1a",
                            }}
                          >
                            {acct.name}
                          </span>

                          {downloadingKey === `account:${acct.name}` && (
                            <span style={{ fontSize: "12px", color: "#c1121f" }}>
                              Generating...
                            </span>
                          )}
                        </div>

                        {/* Nested users */}
                        {acct.expanded && (
                          <div style={{ paddingLeft: "28px", paddingBottom: "6px" }}>
                            {acct.users.length === 0 ? (
                              <div style={{ fontSize: "13px", color: "#888", padding: "6px 0" }}>
                                No users found
                              </div>
                            ) : (
                              acct.users.map((user) => (
                                <div
                                  key={user}
                                  onClick={() => !isBusy && downloadUserReport(acct.name, user)}
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "center",
                                    padding: "6px 8px",
                                    fontSize: "13px",
                                    color: "#444",
                                    cursor: isBusy ? "not-allowed" : "pointer",
                                    borderRadius: "6px",
                                    opacity: isBusy ? 0.5 : 1,
                                  }}
                                  onMouseEnter={(e) =>
                                    !isBusy && (e.currentTarget.style.background = "#f7f7f7")
                                  }
                                  onMouseLeave={(e) =>
                                    (e.currentTarget.style.background = "transparent")
                                  }
                                >
                                  <span>{user}</span>
                                  {downloadingKey === `user:${acct.name}:${user}` && (
                                    <span style={{ fontSize: "11px", color: "#c1121f" }}>
                                      Generating...
                                    </span>
                                  )}
                                </div>
                              ))
                            )}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      <PermissionDeniedModal
    isOpen={showPermissionModal}
    onClose={() => setShowPermissionModal(false)}
/>
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