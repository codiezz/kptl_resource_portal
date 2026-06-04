import { useParams } from "react-router-dom";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from "recharts";

function DonutChart({
  title,
  value,
}) {
  const data = [
    {
      name: "Used",
      value,
    },
    {
      name: "Free",
      value: 100 - value,
    },
  ];

  return (
    <div style={styles.chartCard}>
      <h3 style={styles.chartTitle}>
        {title}
      </h3>

      <div
        style={{
          width: "180px",
          height: "180px",
        }}
      >
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
              {value}%
            </text>
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function ClusterStatus() {
  const { clusterId } =
    useParams();

  const mockStats = {
    cpu: "68%",
    gpu: "41%",
    ram: "124 GB / 192 GB",
    temperature: "54°C",
    nodes: "18 / 24 Active",
    jobs: "142 Running",
    queue: "31 Pending",
    status: "Online",
  };

  return (
    <section style={styles.page}>
      <div style={styles.container}>
        <span style={styles.badge}>
          Live Status
        </span>

        <h1 style={styles.heading}>
          {formatClusterName(
            clusterId
          )}
        </h1>

        <p style={styles.subheading}>
          Real-time cluster health
          and system monitoring.
        </p>

        <div style={styles.dashboardLayout}>

  {/* LEFT */}
  <div style={styles.infoPanel}>

    <div style={styles.infoRow}>
      <span>Status</span>
      <strong>Online</strong>
    </div>

    <div style={styles.infoRow}>
      <span>CPU Usage</span>
      <strong>68%</strong>
    </div>

    <div style={styles.infoRow}>
      <span>GPU Usage</span>
      <strong>41%</strong>
    </div>

    <div style={styles.infoRow}>
      <span>RAM Usage</span>
      <strong>124 GB / 192 GB</strong>
    </div>

    <div style={styles.infoRow}>
      <span>Temperature</span>
      <strong>54°C</strong>
    </div>

    <div style={styles.infoRow}>
      <span>Active Nodes</span>
      <strong>18 / 24</strong>
    </div>

    <div style={styles.infoRow}>
      <span>Running Jobs</span>
      <strong>142 Running</strong>
    </div>

    <div style={styles.infoRow}>
      <span>Queue</span>
      <strong>31 Pending</strong>
    </div>

  </div>

  {/* RIGHT */}
  <div style={styles.chartGrid}>
    <DonutChart
      title="CPU"
      value={68}
    />

    <DonutChart
      title="GPU"
      value={41}
    />

    <DonutChart
      title="RAM"
      value={74}
    />
  </div>

</div>
        
      </div>
    </section>
  );
}



function formatClusterName(
  name
) {
  return name
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) =>
      c.toUpperCase()
    );
}

const styles = {
  page: {
  minHeight: "100vh",
  background:
    "linear-gradient(to bottom,#fafafa,#f6f7fb)",
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

  grid: {
    display: "grid",
    gridTemplateColumns:
      "repeat(auto-fit, minmax(260px,1fr))",
    gap: "24px",
  },

  card: {
    background: "#ffffff",
    borderRadius: "24px",
    padding: "30px",
    border:
      "1px solid #ececec",
    boxShadow:
      "0 8px 24px rgba(0,0,0,0.04)",
  },

  cardTitle: {
    color: "#777",
    fontSize: "14px",
  },

  cardValue: {
    marginTop: "12px",
    fontSize: "34px",
    color: "#111",
  },
  chartGrid: {
  display: "flex",

  gap: "22px",

  alignItems: "flex-start",

  justifyContent:
    "flex-start",

  flexWrap: "nowrap",

  width: "fit-content",
},

chartCard: {
  background: "#fff",

  borderRadius: "26px",

  padding: "18px 22px",

  border:
    "1px solid #ececec",

  boxShadow:
    "0 8px 24px rgba(0,0,0,0.04)",

  width: "240px",

  height: "280px",

  flexShrink: 0,
},

chartTitle: {
  marginBottom: "20px",
  fontSize: "15px",
  fontWeight: "550",
},
dashboardLayout: {
  display: "flex",
  gap: "40px",
  marginTop: "28px",
},

infoPanel: {
  flex: 1,
  minWidth: "340px",
  background: "#fff",
  borderRadius: "28px",
  padding: "18px 32px 28px",
  boxShadow:
      "0 8px 24px rgba(0,0,0,0.04)",
},

infoRow: {
  display: "flex",
  justifyContent:
    "space-between",

  padding: "18px 0",

  borderBottom:
    "1px solid #f1f1f1",

  fontSize: "17px",

  color: "#444",
},

chartGrid: {
  display: "flex",
  gap: "24px",
  flexWrap: "wrap",
  justifyContent:
    "center",
},
};