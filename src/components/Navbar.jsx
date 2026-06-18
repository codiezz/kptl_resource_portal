
import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import ProtectedLink from "./ProtectedLink";
import image from "./image/images.png";
import { clusterStatusPath } from "../config/clusters";

export default function Navbar() {
  const { user, role, logout } =
    useAuth();

  const navigate = useNavigate();

  const [profileOpen, setProfileOpen] =
    useState(false);

  const profileRef = useRef(null);

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  /* Close dropdown if clicked outside */
  useEffect(() => {
    function handleClickOutside(
      event
    ) {
      if (
        profileRef.current &&
        !profileRef.current.contains(
          event.target
        )
      ) {
        setProfileOpen(false);
      }
    }

    document.addEventListener(
      "mousedown",
      handleClickOutside
    );

    return () => {
      document.removeEventListener(
        "mousedown",
        handleClickOutside
      );
    };
  }, []);

  return (
    <>
      <nav style={styles.navbar}>
        {/* LEFT */}
        <div style={styles.left}>
          <div
            style={styles.logoContainer}
            onClick={() =>
              navigate("/")
            }
          >
            <img
              src={image}
              alt="IISER Pune"
              style={styles.logoImage}
            />

            <div style={styles.logoText}>
              {/* Hindi */}
              <div
                style={styles.hindiText}
              >
                <span
                  style={
                    styles.boldBlue
                  }
                >
                  भारतीय विज्ञान शिक्षा
                  एवं अनुसंधान संस्थान
                </span>

                <span
                  style={
                    styles.lightBlue
                  }
                >
                  {" "}पुणे
                </span>
              </div>

              {/* English */}
              <div
                style={
                  styles.instituteLine
                }
              >
                <span
                  style={
                    styles.boldBlue
                  }
                >
                  INDIAN INSTITUTE
                  OF SCIENCE
                  EDUCATION AND
                  RESEARCH
                </span>

                <span
                  style={
                    styles.lightBlue
                  }
                >
                  {" "}PUNE
                </span>
              </div>

              {/* Portal */}
              <div
                style={
                  styles.portalName
                }
              >
                High Performance
                Computing Portal
              </div>
            </div>
          </div>
        </div>

        {/* CENTER LINKS */}
        <div style={styles.links}>
          {/* LOGGED OUT */}
          {!user && (
            <>
              <ProtectedLink
                to="/jobs"
                style={styles.link}
              >
                Jobs
              </ProtectedLink>

              <ProtectedLink
                to="/docs"
                style={styles.link}
              >
                Docs
              </ProtectedLink>

              <ProtectedLink
                to="/support"
                style={styles.link}
              >
                Support
              </ProtectedLink>
            </>
          )}

          {/* USER NAVBAR */}
          {user &&
            role === "user" && (
              <>
                <ProtectedLink
                  to="/jobs"
                  style={
                    styles.link
                  }
                >
                  Clusters
                </ProtectedLink>

                <ProtectedLink
                  to="/support"
                  style={
                    styles.link
                  }
                >
                  Support
                </ProtectedLink>
              </>
            )}

          {/* ADMIN NAVBAR */}
          {user &&
            role === "admin" && (
              <>
                <ProtectedLink
                  to="/jobs"
                  style={
                    styles.link
                  }
                >
                  Clusters
                </ProtectedLink>

                <ProtectedLink
                  to={clusterStatusPath()}
                  style={
                    styles.link
                  }
                >
                  Monitoring
                </ProtectedLink>

                <ProtectedLink
                  to="/support"
                  style={
                    styles.link
                  }
                >
                  Admin Support
                </ProtectedLink>
              </>
            )}
        </div>

        {/* RIGHT */}
        <div style={styles.authSection}>
          {user ? (
            <div
              style={
                styles.profileWrapper
              }
              ref={profileRef}
            >
              {/* Profile Circle */}
              <div
                style={
                  styles.profileIcon
                }
                onClick={() =>
                  setProfileOpen(
                    !profileOpen
                  )
                }
              >
                {user
                  ?.charAt(0)
                  .toUpperCase()}
              </div>

              {/* DROPDOWN */}
              {profileOpen && (
                <div
                  style={
                    styles.dropdown
                  }
                >
                  <button
                    style={
                      styles.dropdownItem
                    }
                    onClick={() => {
                      navigate(
                        "/dashboard"
                      );

                      setProfileOpen(
                        false
                      );
                    }}
                  >
                    Dashboard
                  </button>

                  <button
                    style={
                      styles.logoutDropdown
                    }
                    onClick={
                      handleLogout
                    }
                  >
                    Logout
                  </button>
                </div>
              )}
            </div>
           ) : (
            <button
              style={styles.loginBtn}
              onClick={() => navigate("/login")}
            >
              Login
            </button>
          )}
        </div>
      </nav>

      
    </>
  );
}

const styles = {
  navbar: {
    minHeight: "88px",
    background: "#ffffff",
    borderBottom:
      "1px solid #ececec",

    boxShadow:
      "0 1px 10px rgba(0,0,0,0.035)",

    display: "flex",

    justifyContent:
      "space-between",

    alignItems: "center",

    padding:
      "12px clamp(16px, 4vw, 60px)",

    position: "sticky",
    top: 0,
    zIndex: 100,

    flexWrap: "wrap",
    gap: "12px",
  },

  left: {
    display: "flex",
    alignItems: "center",
    minWidth: 0,
  },

  logoContainer: {
    display: "flex",
    alignItems: "center",
    gap: "16px",
    cursor: "pointer",
    minWidth: 0,
  },

  logoImage: {
    height: "78px",
    width: "auto",
    objectFit: "contain",
    flexShrink: 0,
  },

  logoText: {
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    lineHeight: 1.15,
  },

  hindiText: {
    fontSize:
      "clamp(11px, 0.95vw, 16px)",
    marginBottom: "2px",
  },

  instituteLine: {
    fontSize:
      "clamp(14px, 1.15vw, 22px)",
    lineHeight: 1.15,
  },

  boldBlue: {
    color: "#0056b3",
    fontWeight: "650",
  },

  lightBlue: {
    color: "#0056b3",
    fontWeight: "400",
  },

  portalName: {
    fontSize:
      "clamp(11px, 0.95vw, 15px)",
    color: "#444",
    marginTop: "4px",
    fontWeight: "450",
  },

  links: {
    display: "flex",
    gap:
      "clamp(12px, 2vw, 34px)",
    alignItems: "center",
    flexWrap: "wrap",
    justifyContent: "center",
  },

  link: {
    textDecoration: "none",
    color: "#333",
    fontWeight: "500",
    fontSize:
      "clamp(14px, 1.2vw, 16px)",
    whiteSpace: "nowrap",
  },

  authSection: {
    display: "flex",
    alignItems: "center",
  },

  loginBtn: {
    background: "#c1121f",
    color: "#fff",
    border: "none",
    padding:
      "clamp(10px,1vw,12px) clamp(18px,2vw,26px)",
    borderRadius: "14px",
    cursor: "pointer",
    fontWeight: "700",
    fontSize: "14px",
  },

  profileWrapper: {
    position: "relative",
  },

  profileIcon: {
    width: "46px",
    height: "46px",
    borderRadius: "50%",
    background:
      "linear-gradient(135deg,#c1121f,#9f1020)",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: "700",
    fontSize: "16px",
    cursor: "pointer",
    userSelect: "none",
    boxShadow:
      "0 6px 18px rgba(193,18,31,0.22)",
  },

  dropdown: {
    position: "absolute",
    top: "58px",
    right: 0,
    background: "#fff",
    border:
      "1px solid #ececec",
    borderRadius: "16px",
    minWidth: "180px",
    padding: "8px",
    boxShadow:
      "0 14px 34px rgba(0,0,0,0.10)",
    zIndex: 200,
  },

  dropdownItem: {
    width: "100%",
    background:
      "transparent",
    border: "none",
    padding: "13px 14px",
    borderRadius: "10px",
    textAlign: "left",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "500",
    color: "#333",
  },

  logoutDropdown: {
    width: "100%",
    background:
      "transparent",
    border: "none",
    padding: "13px 14px",
    borderRadius: "10px",
    textAlign: "left",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "500",
    color: "#c1121f",
  },
};

