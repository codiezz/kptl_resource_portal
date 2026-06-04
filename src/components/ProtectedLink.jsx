import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import LoginModal from "./LoginModal";

/**
 * ProtectedLink
 *
 * Use this instead of <Link> for nav items that require authentication.
 * - If the user IS logged in  → navigate directly to `to`
 * - If the user is NOT logged in → show the login modal,
 *   which redirects to `to` after a successful login
 *
 * Props:
 *   to        – destination route (e.g. "/jobs")
 *   children  – link label / content
 *   style     – optional inline styles
 *   className – optional className
 */
export default function ProtectedLink({ to, children, style, className }) {
  const { user }          = useAuth();
  const navigate          = useNavigate();
  const [showModal, setShowModal] = useState(false);

  function handleClick(e) {
    e.preventDefault();
    if (user) {
      navigate(to);         // already authenticated → go straight there
    } else {
      setShowModal(true);   // not authenticated → show login modal
    }
  }

  return (
    <>
      <a href={to} onClick={handleClick} style={style} className={className}>
        {children}
      </a>

      {showModal && (
        <LoginModal
          redirectTo={to}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  );
}
