# Frontend

React application that visualizes the service dependency graph and displays AI analysis results.

## Running Locally

```bash
npm install
npm run dev
# → http://localhost:5173
```

The Vite dev server proxies `/api` and `/health` to `http://localhost:8000` — the backend must be running. No environment variables needed for local development.

## Building for Production

```bash
npm run build   # outputs to dist/
```

In Docker the build output is served by Nginx on port 80 (mapped to 3000 on the host). Vite is not used at runtime — it only runs during the build step.

## Component Overview

```
src/
├── App.tsx                  # Root — state, layout, data fetching, drag-to-resize panels
├── api/
│   └── client.ts            # Typed fetch wrappers for all backend endpoints
└── components/
    ├── DependencyGraph.tsx  # ReactFlow canvas — draggable nodes with persistent positions
    ├── ServiceList.tsx      # Searchable list of services; click to select
    ├── InsightsPanel.tsx    # AI findings — grouped by service when a node is selected
    └── RiskBadge.tsx        # Colour-coded risk level pill (low / medium / high / critical)
```

## Layout

Three draggable panels (default widths: 15% / 45% / 40%):

```
┌──────────────┬──────────────────────────┬──────────────────────────┐
│ Service List │     Dependency Graph      │       Insights           │
│   (15%)      │         (45%)            │        (40%)             │
└──────────────┴──────────────────────────┴──────────────────────────┘
```

Drag the dividers to resize. A transparent overlay div captures mouse events during drag to prevent ReactFlow from intercepting them.

## State Flow

```
App.tsx
 ├── graph (DependencyGraph)         ← set on "Load Sample Data"
 ├── selectedService (string|null)   ← set on node click in graph or row click in list
 ├── serviceDetail                   ← fetched from GET /api/insights/{service} on select
 └── job (AnalysisJob)               ← set on "Run AI Analysis", polled until completed

DependencyGraph   ← receives graph, selectedService; emits onSelectService
ServiceList       ← receives graph, selectedService; emits onSelectService
InsightsPanel     ← receives job result, selectedService, serviceDetail
```

When a service is selected, `InsightsPanel` shows that service's findings at the top with a highlight, then the remaining findings below — no duplication of the service name since the context card already shows it.
