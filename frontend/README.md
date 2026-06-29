# SolvAI Frontend

Interface React pour la plateforme de scoring crédit par IA.

## Installation

```bash
cd solvai_frontend
npm install
```

## Démarrage

```bash
# Development (avec proxy vers Flask sur :5000)
npm start

# Build production
npm run build
```

## Configuration

Copiez `.env.example` vers `.env` :

```bash
cp .env.example .env
```

Si votre backend Flask tourne sur un port différent, modifiez le champ `proxy` dans `package.json` ou définissez `REACT_APP_API_URL` dans `.env`.

## Structure

```
src/
├── components/
│   ├── common/       # Boutons, badges, jauges, cartes stat…
│   └── layout/       # Sidebar + Navbar
├── pages/            # Dashboard, Clients, Datasets, NewClient, History, Alerts, Settings
├── layouts/          # AppLayout (sidebar + navbar + outlet)
├── routes/           # AppRoutes + ProtectedRoute
├── services/         # Axios wrappers (auth, clients, datasets, predictions, dashboard)
├── context/          # AuthContext (JWT)
├── hooks/            # useDebounce
├── utils/            # formatters, constants
└── styles/           # variables CSS, global, animations
```

## Stack

- React 18 + React Router 6
- Axios (avec intercepteur JWT + refresh automatique)
- Recharts (graphiques dashboard)
- Framer Motion (animations)
- CSS Modules
- react-hot-toast (notifications)
- react-dropzone (upload datasets)
