import { useState } from "react";
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
    width: "155px",
    height: "155px",
  }}
>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              innerRadius={52}
outerRadius={68}
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

export default function ClusterDocs() {
  const { clusterId } =
    useParams();

  const [startDate,
    setStartDate] =
    useState("");

  const [endDate,
    setEndDate] =
    useState("");

  return (
    <section style={styles.page}>
      <div style={styles.container}>
        <span style={styles.badge}>
          Cluster Analytics
        </span>

        <h1 style={styles.heading}>
          {formatClusterName(
            clusterId
          )}
        </h1>

        <p style={styles.subheading}>
          Select a date range to
          view cluster statistics.
        </p>

        <div style={styles.filterCard}>
          <div
            style={styles.inputGroup}
          >
            <label>
              Start Date
            </label>

            <input
              type="date"
              value={startDate}
              onChange={(e) =>
                setStartDate(
                  e.target.value
                )
              }
              style={styles.input}
            />
          </div>

          <div
            style={styles.inputGroup}
          >
            <label>
              End Date
            </label>

            <input
              type="date"
              value={endDate}
              onChange={(e) =>
                setEndDate(
                  e.target.value
                )
              }
              style={styles.input}
            />
          </div>

          <button
            style={styles.button}
          >
            Generate Statistics
          </button>
        </div>

        <div style={styles.chartGrid}>
  <DonutChart
    title="Average CPU"
    value={67}
  />

  <DonutChart
    title="Average GPU"
    value={42}
  />

  <DonutChart
    title="Job Success"
    value={91}
  />
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
    border:
      "1px solid #ececec",
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
    border:
      "1px solid #ddd",
    borderRadius: "12px",
    padding: "12px",
  },

  button: {
    background: "#c1121f",
    color: "#fff",
    border: "none",
    borderRadius: "12px",
    padding: "14px 24px",
    cursor: "pointer",
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

  border:
    "1px solid #ececec",

  boxShadow:
    "0 6px 18px rgba(0,0,0,0.035)",

  width: "210px",

  height: "230px",

  flexShrink: 0,
},

chartTitle: {
  marginBottom: "14px",
  fontSize: "16px",
  fontWeight: "600",
},
};