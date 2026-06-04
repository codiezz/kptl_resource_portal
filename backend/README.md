# HPC Portal — Full-Stack Login System

A beginner-friendly Flask + React login system with session-based authentication,
protected routes, and a login modal that intercepts unauthenticated access.

---

## Project Structure

```
hpc-portal/
│
├── backend/                    ← Python Flask server
│   ├── app.py                  ← All API endpoints (login, logout, auth-check)
│   └── requirements.txt        ← Python dependencies
│
└── frontend/                   ← React + Vite app
    ├── index.html              ← HTML entry point (Vite)
    ├── package.json            ← JS dependencies
    ├── vite.config.js          ← Vite config + API proxy
    └── src/
        ├── main.jsx            ← React root entry point
        ├── App.jsx             ← Router with public + protected routes
        ├── context/
        │   └── AuthContext.jsx ← Global auth state (user, login, logout)
        ├── components/
        │   ├── LoginModal.jsx  ← Login popup with form, loading, errors
        │   ├── ProtectedLink.jsx ← Nav link that shows modal if not logged in
        │   └── RequireAuth.jsx ← Route guard — redirects to / if not logged in
        └── pages/
            ├── Home.jsx              ← Public homepage with nav
            ├── Dashboard.jsx         ← Protected dashboard (stats + jobs table)
            └── ProtectedPages.jsx    ← Jobs, Docs, Support pages
```

---

## How Frontend and Backend Connect

```
React (port 5173)  ──fetch()──▶  Flask (port 5000)
        │                               │
        │  POST /api/login              │ checks USERS dict
        │  GET  /api/auth-check         │ reads Flask session cookie
        │  POST /api/logout             │ clears Flask session
        │                               │
        └───────────────────────────────┘
              cookies (session)
              sent with credentials:"include"
```

- The Vite dev server proxies `/api/*` calls to `http://localhost:5000`
- Flask sets a session cookie after login; every subsequent request includes it
- `credentials: "include"` in fetch ensures the cookie is sent cross-origin
- Flask-CORS is configured to allow `http://localhost:5173` with credentials

---

## Hardcoded Credentials

| Username   | Password   |
|------------|------------|
| admin      | admin123   |
| researcher | hpc2026    |
| student    | student123 |

Change these in `backend/app.py` → `USERS` dict.

---

## How to Run Locally (Step by Step)

### Prerequisites
- Python 3.9+ installed
- Node.js 18+ installed
- Two terminal windows

---

### Terminal 1 — Start the Flask Backend

```bash
# 1. Go into the backend folder
cd hpc-portal/backend

# 2. Create a virtual environment (only needed once)
python -m venv venv

# 3. Activate the virtual environment
#    On macOS/Linux:
source venv/bin/activate
#    On Windows:
venv\Scripts\activate

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Start the Flask server
python app.py
```

You should see:
```
 * Running on http://127.0.0.1:5000
```

---

### Terminal 2 — Start the React Frontend

```bash
# 1. Go into the frontend folder
cd hpc-portal/frontend

# 2. Install JS dependencies (only needed once)
npm install

# 3. Start the Vite dev server
npm run dev
```

You should see:
```
  VITE v5.x  ready in ...ms
  ➜  Local:   http://localhost:5173/
```

---

### Open the App

Go to **http://localhost:5173** in your browser.

---

## What Each File Does

### Backend

| File | Purpose |
|------|---------|
| `app.py` | Flask app with 3 API endpoints: `/api/login`, `/api/logout`, `/api/auth-check` |
| `requirements.txt` | Lists `flask` and `flask-cors` as dependencies |

### Frontend

| File | Purpose |
|------|---------|
| `App.jsx` | Defines all routes. Wraps protected routes in `<RequireAuth>` |
| `AuthContext.jsx` | Stores `user` state globally. Provides `login()` and `logout()` functions that call the Flask API |
| `LoginModal.jsx` | The popup form. Calls `login()` from context. Shows error if credentials are wrong |
| `ProtectedLink.jsx` | A nav link that checks auth. If logged in → navigate. If not → show LoginModal |
| `RequireAuth.jsx` | A route wrapper. If user visits `/dashboard` directly without login → redirects to `/` |
| `Home.jsx` | Public homepage with nav bar and section cards |
| `Dashboard.jsx` | Protected page showing stats and recent jobs |
| `ProtectedPages.jsx` | Jobs, Docs, Support pages (all protected) |

---

## Authentication Flow

```
User clicks "Jobs" nav link
        │
        ▼
ProtectedLink checks: is user logged in?
        │
   NO ──┼──▶  Show LoginModal
        │           │
        │     User submits form
        │           │
        │     POST /api/login → Flask
        │           │
        │     Flask checks USERS dict
        │           │
        │     ✓ Match → set session["user"] → return 200
        │     ✗ No match → return 401 + error message
        │           │
        │     ✓ React sets user state → redirect to /jobs
        │     ✗ React shows error in modal (stays on same page)
        │
  YES ──┼──▶  Navigate directly to /jobs
```

---

## Protected Route Guard (direct URL access)

If someone visits `http://localhost:5173/dashboard` directly:

1. `RequireAuth` checks `useAuth()` for a user
2. It also calls `GET /api/auth-check` on mount (in AuthContext)
3. If Flask session has no user → returns 401 → React sets `user = null`
4. `RequireAuth` sees `user = null` → redirects to `/`

---

## API Reference

### POST /api/login
```json
// Request body
{ "username": "admin", "password": "admin123" }

// Success (200)
{ "message": "Login successful", "username": "admin" }

// Failure (401)
{ "error": "Invalid username or password" }
```

### POST /api/logout
```json
// Success (200)
{ "message": "Logged out successfully" }
```

### GET /api/auth-check
```json
// Logged in (200)
{ "authenticated": true, "username": "admin" }

// Not logged in (401)
{ "authenticated": false }
```

---

## Integrating with Your Existing Frontend

If you already have a React + Vite project, copy these files in:

1. `src/context/AuthContext.jsx` → same path
2. `src/components/LoginModal.jsx` → same path
3. `src/components/ProtectedLink.jsx` → same path
4. `src/components/RequireAuth.jsx` → same path

Then in your existing `App.jsx`:
- Wrap everything in `<AuthProvider>`
- Replace nav links to protected sections with `<ProtectedLink>`
- Wrap protected `<Route>` elements with `<RequireAuth>`

---

## Customising

### Add more users
In `backend/app.py`, edit the `USERS` dict:
```python
USERS = {
    "admin":      "admin123",
    "researcher": "hpc2026",
    "student":    "student123",
    "yourname":   "yourpassword",   # ← add here
}
```

### Change session secret key
In `backend/app.py`:
```python
app.secret_key = "your-very-secret-key-here"
```

### Add a real database later
Replace the `USERS` dict check in the `login()` function with a database query.
Everything else stays the same.
