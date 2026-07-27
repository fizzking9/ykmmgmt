# YKMMgmt

Internal business tool for financial and operational data management — unify business data, automate imports, and surface KPIs through an interactive dashboard.

## Prerequisites

- **Python 3.12+** (conda environment `ykmmgmt` recommended)
- **Node.js 20+**
- **npm 10+**

## Quick Start

### 1. Backend

```bash
cd ykmmgmt/backend

# Activate conda env (if using conda)
conda activate ykmmgmt

# Install dependencies
pip install -r requirements.txt

# Start dev server
uvicorn main:app --reload --port 8000
```

Backend runs at **http://localhost:8000** with auto-generated docs at `/docs`.

### 2. Frontend

```bash
cd ykmmgmt/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend runs at **http://localhost:5173** and proxies `/api/*` to the backend.

### 3. Verify

```bash
curl http://localhost:8000/api/health   # → {"status":"ok"}
curl http://localhost:5173/api/health    # → {"status":"ok"} (via proxy)
```

Open **http://localhost:5173** in a browser — you should see the backend health status.

## Project Structure

```
ykmmgmt/
├── backend/          # FastAPI application
│   ├── main.py       # App entry point
│   ├── requirements.txt
│   └── ruff.toml
├── frontend/         # React + Vite + TypeScript
│   ├── src/
│   │   ├── App.tsx   # Health check page
│   │   ├── main.tsx  # React entry point
│   │   └── lib/      # Utility functions
│   ├── vite.config.ts
│   └── package.json
├── specs/            # Project specifications & roadmap
└── .gitignore
```
# Management App for YKM

## Input from stakeholders

- The management team wants a light-weight system to use in their daily work, making it easier to decision making based on data.
- This application is for Chinese users.
