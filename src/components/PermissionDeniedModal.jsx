export default function PermissionDeniedModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    /* ---------- backdrop — intentionally NOT clickable to close ---------- */
    <div style={styles.backdrop}>
      {/* ---------- modal box ---------- */}
      <div style={styles.modal}>
        <div style={styles.header}>
          <span style={styles.title}>Access Restricted</span>
        </div>

        <p style={styles.message}>
          You do not have permission to access this report.
        </p>

        <button style={styles.btn} onClick={onClose} autoFocus>
          OK
        </button>
      </div>
    </div>
  );
}

/* ---------- inline styles, matched to LoginModal's visual language ---------- */
const styles = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.35)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
    backdropFilter: "blur(6px)",
  },

  modal: {
    background: "#ffffff",
    border: "1px solid #ececec",
    borderRadius: "24px",
    padding: "36px",
    width: "100%",
    maxWidth: "400px",
    boxShadow: "0 20px 60px rgba(0,0,0,0.12)",
    color: "#111111",
    textAlign: "center",
  },

  header: {
    marginBottom: "10px",
  },

  title: {
    fontSize: "22px",
    fontWeight: "800",
    color: "#111111",
    letterSpacing: "-0.5px",
  },

  message: {
    color: "#444",
    fontSize: "15px",
    lineHeight: "1.6",
    margin: "16px 0 28px",
  },

  btn: {
    padding: "14px 32px",
    background: "#c1121f",
    color: "#ffffff",
    border: "none",
    borderRadius: "14px",
    fontSize: "16px",
    fontWeight: "700",
    cursor: "pointer",
    transition: "0.2s ease",
  },
};