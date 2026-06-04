import { useNavigate } from "react-router-dom";
import image from "./image/images-removebg-preview.png";

export default function Footer() {
  const navigate = useNavigate();

  return (
    <footer style={styles.footer}>

      {/* ── Main content ── */}
      <div style={styles.topBand}>
        <div style={styles.topInner}>

          {/* Brand */}
          <div style={styles.brand}>
            <img src={image} alt="IISER Pune Logo" style={styles.logo} />
            <div>
              <p style={styles.hindi}>
                भारतीय विज्ञान शिक्षा एवं अनुसंधान संस्थान पुणे
              </p>
              <p style={styles.instituteName}>
                INDIAN INSTITUTE OF SCIENCE EDUCATION AND RESEARCH PUNE
              </p>
              <p style={styles.portalName}>High Performance Computing Portal</p>
            </div>
          </div>

          {/* Nav */}
          <div style={styles.navGroup}>
            <p style={styles.colHeading}>Navigation</p>
            {[
              { label: "Jobs", path: "/jobs" },
              { label: "Documentation", path: "/docs" },
              { label: "Support", path: "/support" },
              { label: "Dashboard", path: "/dashboard" },
            ].map(({ label, path }) => (
              <button
                key={label}
                style={styles.navLink}
                onClick={() => navigate(path)}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Contact */}
          <div style={styles.contactGroup}>
            <p style={styles.colHeading}>Contact</p>
            <p style={styles.contactName}>HPC Support Team</p>
            <p style={styles.contactSub}>IISER Pune</p>
            <a href="mailto:hpc-support@iiserpune.ac.in" style={styles.emailLink}>
              hpc-support@iiserpune.ac.in
            </a>
          </div>

        </div>
      </div>

      {/* ── Bottom bar ── */}
      <div style={styles.bottomBar}>
        <span style={styles.bottomLeft}>© 2026 IISER Pune High Performance Computing Portal</span>
        <span style={styles.bottomRight}>All rights reserved</span>
      </div>

    </footer>
  );
}

const styles = {
  footer: {
    marginTop: "0",
    fontFamily: "'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
  },

  topBand: {
    background: "linear-gradient(to bottom, #ececec, #f4f4f4 18px)",
    width: "100%",
  },

  topInner: {
    maxWidth: "1300px",
    margin: "0 auto",
    padding: "44px 56px 48px",
    display: "flex",
    alignItems: "flex-start",
  },

  brand: {
    display: "flex",
    alignItems: "flex-start",
    gap: "18px",
    flex: "2.5 1 0",
    paddingRight: "64px",
    borderRight: "1px solid #ddd",
  },

  logo: {
    height: "72px",
    width: "auto",
    objectFit: "contain",
    flexShrink: 0,
  },

  hindi: {
    fontSize: "12px",
    fontWeight: "500",
    color: "#c0392b",
    lineHeight: 1.6,
    margin: "0 0 4px 0",
  },

  instituteName: {
    fontSize: "14px",
    fontWeight: "700",
    color: "#1a1a1a",
    lineHeight: 1.4,
    margin: "0 0 8px 0",
    maxWidth: "280px",
    letterSpacing: "0.01em",
  },

  portalName: {
    fontSize: "12px",
    color: "#888",
    margin: 0,
    letterSpacing: "0.04em",
    textTransform: "uppercase",
  },

  navGroup: {
    flex: "1 1 0",
    paddingLeft: "64px",
    paddingRight: "64px",
    borderRight: "1px solid #ddd",
    display: "flex",
    flexDirection: "column",
  },

  colHeading: {
    fontSize: "11px",
    fontWeight: "700",
    color: "#c0392b",
    letterSpacing: "0.12em",
    textTransform: "uppercase",
    margin: "0 0 18px 0",
  },

  navLink: {
    background: "none",
    border: "none",
    cursor: "pointer",
    fontSize: "14px",
    color: "#333",
    fontWeight: "400",
    padding: "0 0 11px 0",
    textAlign: "left",
    fontFamily: "inherit",
    letterSpacing: "0.01em",
  },

  contactGroup: {
    flex: "1 1 0",
    paddingLeft: "64px",
    display: "flex",
    flexDirection: "column",
  },

  contactName: {
    fontSize: "14px",
    fontWeight: "600",
    color: "#1a1a1a",
    margin: "0 0 3px 0",
  },

  contactSub: {
    fontSize: "13px",
    color: "#888",
    margin: "0 0 14px 0",
  },

  emailLink: {
    fontSize: "13px",
    color: "#c0392b",
    textDecoration: "none",
    borderBottom: "1px solid #e8a89f",
    paddingBottom: "2px",
    width: "fit-content",
  },

  bottomBar: {
    background: "#c0392b",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "14px 56px",
    boxSizing: "border-box",
  },

  bottomLeft: {
    fontSize: "12px",
    color: "#ffffff",
    letterSpacing: "0.01em",
  },

  bottomRight: {
    fontSize: "12px",
    color: "rgba(255,255,255,0.65)",
    letterSpacing: "0.03em",
  },
};
