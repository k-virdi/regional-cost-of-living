<!-- README.md -->
<div align="center">

# Regional Cost of Living
### Data Platform & Policy Simulator

**An end-to-end data engineering and game-theoretic analysis platform that ingests 50 years of Canadian and U.S. economic indicators, stores them in a normalized PostgreSQL warehouse, and simulates the cost-of-living impact of policy interventions.**

[![CI](https://github.com/k-virdi/regional-cost-of-living/actions/workflows/ci.yml/badge.svg)](https://github.com/k-virdi/regional-cost-of-living/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.37+-FF4B4B.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**🔗 [Live Dashboard](https://regional-cost-of-living.streamlit.app)** · **📊 [Architecture](docs/ARCHITECTURE.md)** · **📈 [Key Findings](#-key-findings)**

</div>

---

## 📸 Dashboard Preview

![Dashboard Overview](docs/images/dashboard-overview.png)

---

## 🎯 The Problem

Housing affordability is the defining economic issue of our time. Between 1980 and 2024, median household income in Canada and the U.S. grew by roughly 180%, but average rents grew by over 400%. Policymakers, economists, and citizens all need a tool that answers a simple question:

> **"If we change policy X, how does the cost of living actually change — and who wins, who loses?"**

This project builds that tool from the ground up: official data ingestion → normalized warehouse → interactive visualization → game-theoretic policy simulation.

---

## ✨ What It Does

| Layer | What It Does | Key Technology |
|---|---|---|
| **1. Data Ingestion** | Extracts 50 years of economic indicators from Statistics Canada, US Census Bureau, BLS, and CMHC | Python, `requests`, Pydantic |
| **2. Warehouse** | Stores data in a star schema with versioned migrations and dbt transformation marts | PostgreSQL 16, SQLAlchemy, Alembic, dbt |
| **3. Dashboard** | 5 interactive views: national overview, regional comparison, affordability, inflation adjuster, policy simulator | Streamlit, Plotly |
| **4. Game Theory** | Solves Nash equilibria for landlord–consumer interaction under government policy; ranks scenarios by composite welfare | Nashpy, PyGambit, SciPy |

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Language** | Python 3.11+ |
| **Data Extraction** | `requests`, `pandas`, `tenacity` (retry), `Pydantic` (validation) |
| **Database** | PostgreSQL 16, SQLAlchemy 2.0, Alembic, dbt-postgres |
| **Visualization** | Streamlit, Plotly, Matplotlib |
| **Game Theory** | Nashpy (Nash equilibrium), PyGambit (logit QRE), NumPy, SciPy |
| **Infrastructure** | Docker, Docker Compose, GitHub Actions |
| **Storage** | Parquet (staging), PostgreSQL (warehouse) |
| **Testing** | pytest, pytest-mock, responses |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Free API keys: [BLS](https://data.bls.gov/registrationEngine/) and [US Census](https://api.census.gov/data/key_signup.html)

### Setup (5 minutes)

```bash
# 1. Clone the repository
git clone https://github.com/k-virdi/regional-cost-of-living.git
cd regional-cost-of-living

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env: add your BLS_API_KEY and CENSUS_API_KEY

# 5. Start PostgreSQL
docker compose up -d postgres

# 6. Run the ETL pipeline (extracts 50 years of data)
python scripts/run_pipeline.py

# 7. Apply database migrations
alembic upgrade head

# 8. Load data into the warehouse
python scripts/run_warehouse.py

# 9. Build analytical marts
cd dbt && dbt run && dbt test && cd ..

# 10. Launch the dashboard
streamlit run dashboard/app.py
