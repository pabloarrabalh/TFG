# LigaMaster — React Frontend

Full-stack LaLiga fantasy football app. This document describes how to run the project locally.

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Django 5.1.4 + SQLite |
| Frontend | React 18 + Vite 5 |
| CSS | Tailwind CSS 3 + custom dark theme |
| Routing | React Router v6 |
| HTTP | Axios (session cookies + CSRF) |
| Charts | Recharts |

---

## Project structure

```
TFG/
├── config/            Django project settings
├── main/              Main Django app
│   ├── api_views.py   JSON API endpoints for React
│   ├── views.py       Template-based views (legacy)
│   ├── models.py      Database models
│   └── urls.py
├── frontend-web/      React SPA
│   ├── src/
│   │   ├── pages/     One file per page
│   │   ├── components/
│   │   │   ├── layout/  Header, Sidebar, Layout
│   │   │   └── ui/      GlassPanel, LoadingSpinner, TeamShield
│   │   ├── context/   AuthContext (session auth)
│   │   ├── services/  apiClient.js (Axios instance)
│   │   └── styles/    globals.css (Tailwind + custom classes)
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
├── data/              Per-season CSV match data
├── static/            Django static files (escudos, logos)
└── db.sqlite3
```

---

## Running the backend (Django)

```bash
# 1. Activate the virtual environment
.venv311\Scripts\activate        # Windows
# or
source .venv311/bin/activate     # macOS/Linux

# 2. Install dependencies (first time only)
pip install -r requirements.txt

# 3. Apply migrations
python manage.py migrate

# 4. Start the development server
python manage.py runserver
# → Django is now running at http://localhost:8000
```

---

## Running the frontend (React + Vite)

```bash
# From the frontend-web/ directory:
cd frontend-web

# 1. Install Node dependencies (first time only)
npm install

# 2. Start the Vite dev server
npm run dev
# → React app is now at http://localhost:5173
```

> Vite proxies all `/api/*`, `/static/*`, `/media/*` requests to Django automatically.  
> No environment variables needed for local development.

---

## Building for production

```bash
cd frontend-web
npm run build
# Output: frontend-web/dist/
```

To serve from Django, copy `dist/` to a static location and add a catch-all URL in `config/urls.py`.

---

## Pages

| Route | Page | Auth required |
|---|---|---|
| `/login` | Login / Register | No |
| `/terms` | Terms & Conditions | No |
| `/menu` | Dashboard | No |
| `/clasificacion` | League table | No |
| `/equipos` | All teams | No |
| `/equipo/:nombre` | Team detail | No |
| `/jugador` | Player search | No |
| `/jugador/:id` | Player detail with XAI | No |
| `/mi-plantilla` | Fantasy team builder | **Yes** |
| `/perfil` | User profile | **Yes** |
| `/amigos` | Friends | **Yes** |
| `/favoritos/select` | Select favourite teams | **Yes** |

---

## API endpoints (Django → `/api/`)

| Method | URL | Description |
|---|---|---|
| GET | `/api/me/` | Auth status + set CSRF cookie |
| POST | `/api/auth/login/` | Login |
| POST | `/api/auth/logout/` | Logout |
| POST | `/api/auth/register/` | Register |
| GET | `/api/menu/` | Dashboard data |
| GET | `/api/clasificacion/` | League table + jornada results |
| GET | `/api/equipos/` | All teams list |
| GET | `/api/equipo/<nombre>/` | Team detail |
| GET | `/api/jugador/<id>/` | Player stats |
| GET | `/api/mi-plantilla/jugadores/` | Player search for team builder |
| GET | `/api/perfil/` | User profile |
| POST | `/api/perfil/update/` | Update profile info |
| POST | `/api/perfil/foto/` | Upload / choose avatar |
| POST | `/api/perfil/status/` | Update status |
| GET | `/api/favoritos/` | List favourite teams |
| POST | `/api/favoritos/toggle-v2/` | Toggle favourite |
| DELETE | `/api/favoritos/<id>/` | Delete favourite |
| GET | `/api/amigos/` | Friends list + pending requests |
| POST | `/api/amigos/solicitud/` | Send friend request |
| POST | `/api/amigos/aceptar/<id>/` | Accept request |
| POST | `/api/amigos/rechazar/<id>/` | Reject request |
| POST | `/api/amigos/eliminar/<id>/` | Remove friend |

---

## Authentication

The app uses **Django session authentication**. The flow is:

1. On app load, `GET /api/me/` is called — this sets the CSRF cookie and returns user info if logged in.
2. All mutating requests (`POST`, `DELETE`) include the `X-CSRFToken` header (read from the cookie by the Axios interceptor in `src/services/apiClient.js`).
3. Credentials are sent with every request via `withCredentials: true`.

---

## Colours (Tailwind custom theme)

| Token | Value |
|---|---|
| `primary` | `#39ff14` (neon green) |
| `primary-dark` | `#2ccb10` |
| `background-dark` | `#050505` |
| `surface-dark` | `#121212` |
| `surface-dark-lighter` | `#1e1e1e` |
| `border-dark` | `#262626` |
