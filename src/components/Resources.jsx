import { useState } from "react";

function DropdownCard({ title, items }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div style={styles.card}>
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={styles.cardHeader}
      >
        <h3 style={styles.cardTitle}>
          {title}
        </h3>

        <span
          style={{
            ...styles.arrow,
            transform: isOpen
              ? "rotate(180deg)"
              : "rotate(0deg)",
          }}
        >
          ▼
        </span>
      </div>

      <div
        style={{
          maxHeight: isOpen ? "2000px" : "0",
          overflow: "hidden",
          transition: "max-height 0.35s ease",
        }}
      >
        <ul style={styles.list}>
          {items.map((item, index) => (
            <ListItem
              key={index}
              label={item.label}
              host={item.host}
            />
          ))}
        </ul>
      </div>
    </div>
  );
}

function ListItem({ label, host }) {
  const [hovered, setHovered] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleLogin = () => {
    if (host) {
      window.location.assign(`ssh://${host}`);
    }
  };

  const clusterId = label
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[():]/g, "");

  return (
    <li
      onMouseEnter={() => {
        setHovered(true);
        setExpanded(true);
      }}
      onMouseLeave={() => {
        setHovered(false);
        setExpanded(false);
      }}
      onClick={() => setExpanded(!expanded)}
      style={{
        ...styles.listItem,
        backgroundColor: hovered ? "#fff5f5" : "#ffffff",
        border: hovered ? "1px solid #c1121f" : "1px solid #efefef",
        boxShadow: hovered
          ? "0 4px 12px rgba(193,18,31,0.08)"
          : "none",
      }}
    >
      {/* Title */}
      <div style={styles.resourceTitle}>{label}</div>

      {/* Hover Actions */}
      <div
        style={{
          ...styles.actionPanel,
          maxHeight: expanded ? "120px" : "0",
          opacity: expanded ? 1 : 0,
          overflow: "hidden",
        }}
      >
        <button
          style={styles.actionBtn}
          onClick={(e) => {
            e.stopPropagation();
            window.location.href = `/cluster/${clusterId}/status`;
          }}
        >
          Live Status
        </button>

        <button
          style={styles.actionBtn}
          onClick={(e) => {
            e.stopPropagation();
            window.location.href = `/cluster/${clusterId}/docs`;
          }}
        >
          Docs
        </button>

        <button
          style={{ ...styles.actionBtn, ...styles.loginBtn }}
          onClick={(e) => {
            e.stopPropagation();
            handleLogin();
          }}
        >
          Login
        </button>
      </div>
    </li>
  );
}

function Resources() {
  const clusterItems = [
    { label: "CMS Cluster (Dr. Seema & Dr. Sourabh) : CPU", host: "localhost" },
    { label: "Fermi Cluster (Dr. Prasenjith) : CPU", host: "192.168.1.170" },
    { label: "Athena Cluster (Dr. Mukul) : CPU", host: "192.168.1.211" },
    { label: "Charu Cluster (Dr. Arnab) : CPU", host: "192.168.1.202" },
    { label: "Megha Cluster (Dr. Neena) : CPU", host: "192.168.1.213" },
    { label: "Taurus Cluster (Dr. Arun) : CPU", host: "192.168.1.225" },
    { label: "Lammer Cluster (Dr. Sreejith) : CPU", host: "192.168.1.212" },
    { label: "Maths Cluster (Dr. Vivek) : CPU + GPU", host: "192.168.1.136" },
    { label: "Bhoomi Cluster (Dr. Arjun) : CPU", host: "192.168.1.139" },
    { label: "Violin Cluster (Dr. Srabanti) : CPU", host: "" },
    { label: "Veena Cluster (Dr. Srabanti) : CPU", host: "192.168.1.167" },
    { label: "Onsagar Cluster (Dr. Arnab) : CPU", host: "localhost" },
    { label: "Fortytwo Cluster (Data Science Department) : CPU + GPU", host: "192.168.1.152" },
    { label: "Niraj Cluster (Dr. Saikrishnan) : CPU + GPU", host: "192.168.1.250" },
    { label: "Ada Cluster (Dr. Madhu, Dr. Suhita and Dr. Collins) : CPU", host: "localhost" },
    { label: "PARAM Brahma Cluster : CPU + GPU", host: "localhost" },
  ];

  const serverItems = [
    { label: "Dr. Apratim High End Server 1 : CPU + GPU", host: "192.168.1.146" },
    { label: "Dr. Apratim High End Server 2 : CPU + GPU", host: "192.168.1.175" },
    { label: "Dr. Apratim High End Server 3 : CPU + GPU", host: "192.168.1.176" },
    { label: "Dr. Joy High End Server 1 : CPU", host: "192.168.1.237" },
    { label: "Dr. Joy High End Server 2 : CPU", host: "192.168.1.233" },
    { label: "Dr. Arnab High End Server : GPU", host: "192.168.1.192" },
    { label: "Dr. Arka High End Server 1 : CPU", host: "192.168.1.199" },
    { label: "Dr. Arka High End Server 2 : CPU", host: "192.168.1.142" },
    { label: "Dr. Bijay High End Server : CPU", host: "localhost" },
  ];

  return (
    <section style={styles.section}>
      <div style={styles.container}>
        <span style={styles.badge}>
          HPC Infrastructure
        </span>

        <h2 style={styles.heading}>
          Available Resources
        </h2>

        <p style={styles.subheading}>
          Browse compute clusters and high-end servers available
          for research and workloads.
        </p>

        <div style={styles.grid}>
          <DropdownCard title="Clusters" items={clusterItems} />
          <DropdownCard title="High End Servers" items={serverItems} />
        </div>
      </div>
    </section>
  );
}

const styles = {
  resourceTitle: {
    fontSize: "15px",
    fontWeight: "500",
    color: "#333",
  },

  actionPanel: {
    transition: "max-height 0.3s ease, opacity 0.3s ease",
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
    marginTop: "14px",
  },

  actionBtn: {
    border: "1px solid rgba(193,18,31,0.18)",
    background: "rgba(193,18,31,0.06)",
    padding: "11px 16px",
    borderRadius: "7px",
    cursor: "pointer",
    fontWeight: "600",
    color: "#9f1020",
    fontSize: "14px",
    transition: "all 0.22s ease",
    backdropFilter: "blur(10px)",
  },

  loginBtn: {
    background: "linear-gradient(135deg,#c1121f,#9f1020)",
    color: "#ffffff",
    border: "none",
    boxShadow: "0 6px 16px rgba(193,18,31,0.22)",
  },

  section: {
    background: "#fafafa",
    padding: "60px 30px",
  },

  container: {
    maxWidth: "1150px",
    margin: "0 auto",
    textAlign: "center",
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
    fontSize: "48px",
    fontWeight: "800",
    color: "#111111",
    marginTop: "24px",
    marginBottom: "18px",
  },

  subheading: {
    fontSize: "18px",
    color: "#666",
    maxWidth: "700px",
    margin: "0 auto 60px",
    lineHeight: "1.8",
  },

  grid: {
    display: "flex",
    flexDirection: "row",
    gap: "28px",
    alignItems: "flex-start",
  },

  card: {
    flex: "1 1 0",
    minWidth: "0",
    background: "#ffffff",
    border: "1px solid #efefef",
    borderRadius: "24px",
    padding: "28px",
    boxShadow: "0 10px 30px rgba(0,0,0,0.04)",
    textAlign: "left",
    boxSizing: "border-box",
  },

  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    cursor: "pointer",
  },

  cardTitle: {
    fontSize: "22px",
    fontWeight: "700",
    color: "#111111",
    margin: 0,
  },

  arrow: {
    fontSize: "18px",
    color: "#c1121f",
    transition: "transform 0.3s ease",
    display: "inline-block",
  },

  list: {
    listStyle: "none",
    padding: 0,
    marginTop: "22px",
  },

  listItem: {
    padding: "14px 18px",
    border: "1px solid #efefef",
    borderRadius: "14px",
    marginBottom: "12px",
    cursor: "pointer",
    color: "#444",
    fontSize: "15px",
    transition: "all 0.25s ease",
    background: "#fff",
    boxSizing: "border-box",
  },
};

export default Resources;