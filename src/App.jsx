import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";

import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";

import {
  Jobs,
  Docs,
  Support,
} from "./pages/ProtectedPages";

import RequireAuth from "./components/RequireAuth";
import { AuthProvider } from "./context/AuthContext";


import ClusterStatus from "./pages/ClusterStatus";
import PublicLayout from "./layouts/PublicLayout";
import PortalLayout from "./layouts/PortalLayout";
import Login from "./pages/Login";
import ClusterDocs from "./pages/ClusterDocs";
import {
  DEFAULT_CLUSTER_ID,
  clusterDocsPath,
  clusterStatusPath,
} from "./config/clusters";


function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>

          {/* ---------------- PUBLIC LAYOUT (no navbar/footer) ---------------- */}
          <Route element={<PublicLayout />}>
            <Route path="/login" element={<Login />} />
          </Route>

          {/* ---------------- PORTAL LAYOUT (navbar + footer) ---------------- */}
          <Route element={<PortalLayout />}>

            {/* Home */}
            <Route
              path="/"
              element={
                <RequireAuth>
                  <Home />
                </RequireAuth>
              }
            />

            {/* Dashboard */}
            <Route
              path="/dashboard"
              element={
                <RequireAuth>
                  <Dashboard />
                </RequireAuth>
              }
            />

            {/* Protected Pages */}
            <Route
              path="/jobs"
              element={
                <RequireAuth>
                  <Jobs />
                </RequireAuth>
              }
            />

            <Route
              path="/docs"
              element={
                <RequireAuth>
                  <Docs />
                </RequireAuth>
              }
            />

            <Route
              path="/support"
              element={
                <RequireAuth>
                  <Support />
                </RequireAuth>
              }
            />

            {/* Legacy redirects */}
            <Route
              path="/cluster-status"
              element={
                <Navigate
                  to={clusterStatusPath(DEFAULT_CLUSTER_ID)}
                  replace
                />
              }
            />

            <Route
              path="/cluster-docs"
              element={
                <Navigate
                  to={clusterDocsPath(DEFAULT_CLUSTER_ID)}
                  replace
                />
              }
            />

            {/* Cluster Status */}
            <Route
              path="/cluster/:clusterId/status"
              element={
                <RequireAuth>
                  <ClusterStatus />
                </RequireAuth>
              }
            />

            {/* Cluster Docs */}
            <Route
              path="/cluster/:clusterId/reports"
              element={
                <RequireAuth>
                  <ClusterDocs />
                </RequireAuth>
              }
            />

          </Route>

        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;