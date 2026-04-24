# Intelligent System Resource Monitor (ISRM)
## Project Report

---

## 1. Project Overview

The **Intelligent System Resource Monitor (ISRM)** is a real-time web-based dashboard that monitors system performance metrics and applies machine learning algorithms to detect anomalies, predict future resource usage, and cluster system states. Built with Python (Flask) on the backend and vanilla JavaScript on the frontend, it stores all collected data in a MySQL database and presents it through an interactive, multi-page web interface.

---

## 2. Objectives

- Continuously collect system metrics (CPU, RAM, Disk, Network, Swap) in the background.
- Store historical data in a structured MySQL database for analysis.
- Apply machine learning models to detect anomalies, predict CPU usage, and classify system states.
- Provide a clean, real-time web dashboard accessible via a browser.
- Allow users to export collected data in CSV and JSON formats.

---

## 3. Technology Stack

| Layer | Technology |
|---|---|
| Backend Framework | Python 3, Flask |
| Database | MySQL (via `mysql-connector-python`) |
| ML / Data Analysis | scikit-learn, pandas, NumPy |
| System Metrics | psutil |
| Frontend | HTML5, CSS3, JavaScript (Chart.js) |
| Environment Config | python-dotenv |
| Performance | flask-compress (Gzip compression) |

---

## 4. Project Structure

```
ISRM/
├── .env                    # MySQL credentials (not committed to VCS)
├── .venv/                  # Python virtual environment
├── app.py                  # Main Flask application
├── model.py                # Machine learning models and analysis
├── mysql_database.py       # Database layer (MySQL)
├── requirements.txt        # Python dependencies
├── RUN_SERVER.bat          # Windows one-click server launcher
├── RUN_SERVER.ps1          # PowerShell server launcher
├── static/
│   ├── css/style.css       # Dashboard styling
│   └── js/main.js          # Frontend logic and Chart.js integration
└── templates/
    ├── base.html           # Shared layout template
    ├── index.html          # Dashboard (main page)
    ├── analysis.html       # ML & Algorithm Analysis page
    ├── processes.html      # Process monitoring page
    ├── system.html         # System information page
    └── data.html           # Data management & export page
```

---

## 5. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Browser (Client)                     │
│         Chart.js  │  Fetch API  │  HTML/CSS/JS           │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP (REST API)
┌──────────────────────────▼──────────────────────────────┐
│                   Flask Web Server                        │
│  Routes: /, /analysis, /processes, /system, /data        │
│  API:    /api/metrics, /api/history, /api/predict, ...   │
│                                                           │
│  Background Thread: collect_metrics() — every 2 seconds  │
└──────────┬──────────────────────────┬───────────────────┘
           │                          │
┌──────────▼──────────┐   ┌──────────▼──────────────────┐
│   psutil (OS Layer) │   │   model.py (ML Engine)       │
│  CPU, RAM, Disk,    │   │  Isolation Forest            │
│  Network, Swap,     │   │  K-Means Clustering          │
│  Processes          │   │  Linear Regression           │
└─────────────────────┘   │  Random Forest Regressor     │
                          └──────────┬───────────────────┘
                                     │
                          ┌──────────▼───────────────────┐
                          │   MySQL Database              │
                          │  Tables: hosts, metrics,      │
                          │  process_samples,             │
                          │  ml_predictions, alerts       │
                          └──────────────────────────────┘
```

---

## 6. Core Modules

### 6.1 `app.py` — Flask Application

The main entry point of the application. Responsibilities:

- **Initialization**: Loads environment variables, connects to MySQL, registers host metadata (OS, CPU count, RAM).
- **Background Collection Thread**: A daemon thread runs `collect_metrics()` every 2 seconds, gathering CPU, RAM, Disk, Swap, Network I/O, Disk I/O, CPU frequency, and process count via `psutil`. The top 5 CPU-consuming processes are also snapshotted.
- **REST API Endpoints**:

| Endpoint | Description |
|---|---|
| `GET /` | Dashboard page |
| `GET /analysis` | ML Analysis page |
| `GET /processes` | Process monitor page |
| `GET /system` | System info page |
| `GET /data` | Data management page |
| `GET /api/metrics` | Current live metrics (JSON) |
| `GET /api/history` | Last 50 metric records (JSON) |
| `GET /api/processes` | Top 5 processes by CPU (JSON) |
| `GET /api/system_info` | Static system information (JSON) |
| `GET /api/predict` | ML analysis and prediction (JSON) |
| `GET /api/all_metrics` | All stored metrics (JSON) |
| `GET /api/all_processes` | All stored process samples (JSON) |

- **Performance**: Gzip compression via `flask-compress` and browser cache headers (24 hours for CSS/JS, 7 days for images).

---

### 6.2 `mysql_database.py` — Database Layer

Manages all MySQL interactions using `mysql-connector-python`. Key components:

**Database Tables:**

| Table | Purpose |
|---|---|
| `hosts` | Stores host machine metadata (OS, CPU, RAM) |
| `metrics` | Time-series resource usage data |
| `process_samples` | Top-5 process snapshots per collection cycle |
| `ml_predictions` | Stores ML model outputs and predictions |
| `alerts` | Anomaly-triggered alerts with severity levels |

**Key Functions:**

- `init_db()` — Creates all tables and a legacy view (`v_metrics_legacy`) on startup.
- `upsert_host()` — Inserts or updates host metadata.
- `insert_metric_row()` — Stores a single metrics snapshot.
- `insert_process_samples()` — Bulk-inserts process snapshots.
- `insert_prediction()` — Persists ML model results.
- `insert_alert()` — Logs anomaly alerts.
- `get_recent_metrics(limit)` — Retrieves the last N records for charting.
- `get_all_metrics()` — Retrieves the full dataset for ML analysis.

---

### 6.3 `model.py` — Machine Learning Engine

Performs four types of analysis on the collected metrics:

#### 1. Anomaly Detection — Isolation Forest
- Algorithm: `sklearn.ensemble.IsolationForest` (contamination=0.1)
- Features used: CPU usage, RAM usage, Swap usage
- Output: Flags the current system state as normal or anomalous. Triggers a high-severity alert in the database if an anomaly is detected.

#### 2. System State Clustering — K-Means
- Algorithm: `sklearn.cluster.KMeans` (k=3)
- Features used: CPU, RAM, Disk, Swap
- Output: Classifies the current system state into one of 3 clusters (e.g., Idle, Normal, High Load).

#### 3. Correlation Analysis
- Computes a Pearson correlation matrix across all numeric metrics (CPU, RAM, Disk, Network, Swap, CPU Frequency).
- Returned as a dictionary for rendering in the frontend correlation table.

#### 4. CPU Usage Prediction — Regression Models
- Approach: Sliding window (size=5) to create feature vectors from historical CPU values.
- **Model 1**: `LinearRegression` — evaluated on MSE and R².
- **Model 2**: `RandomForestRegressor` (100 estimators) — evaluated on MSE and R².
- The model with the higher R² score is selected to predict the next CPU value.
- Results (predicted value, model name, metrics) are persisted to `ml_predictions`.

---

## 7. Frontend Pages

### 7.1 Dashboard (`/`)
- Displays 6 live metric cards: CPU %, RAM %, Disk %, Active Processes, Swap %, CPU Frequency.
- Three real-time Chart.js line charts:
  - **Resource Usage**: CPU and RAM over time.
  - **Network Traffic**: Bytes sent/received (KB/s).
  - **Disk I/O**: Read/write throughput (KB/s).
- Charts refresh every 2 seconds.

### 7.2 Algorithm Analysis (`/analysis`)
- **Next CPU Prediction**: Displays the predicted next CPU value and the winning model name.
- **Anomaly Detection**: Shows a green "Normal" or red "Anomaly Detected" status badge.
- **Model Performance Table**: Side-by-side MSE and R² comparison of Linear Regression vs. Random Forest.
- **K-Means Clustering**: Shows the current cluster ID.
- **Correlation Matrix**: Color-coded table (green for strong positive, red for strong negative correlation).
- Refreshes every 10 seconds.

### 7.3 Process Monitor (`/processes`)
- Live table of the top 5 CPU-consuming processes with PID, name, CPU %, and Memory %.
- Refreshes every 5 seconds.

### 7.4 System Information (`/system`)
- Static display of OS name, OS release, processor model, CPU core count, total RAM, and system boot time.

### 7.5 Data Management (`/data`)
- Paginated table of all stored metrics (50 rows per page).
- Paginated table of all stored process samples.
- Export buttons for Metrics (CSV/JSON), Processes (CSV/JSON), and a combined All Data (JSON) export.

---

## 8. Database Schema

```sql
-- Host machine registry
hosts (id, hostname, os_name, os_release, machine, processor,
       cpu_count, ram_total_bytes, created_at)

-- Time-series resource metrics
metrics (id, host_id, ts, cpu_usage, ram_usage, disk_usage,
         net_sent_bytes, net_recv_bytes, swap_usage,
         disk_read_bytes, disk_write_bytes, cpu_freq_mhz, process_count)

-- Process snapshots (top 5 per cycle)
process_samples (id, host_id, ts, pid, name, cpu_percent, memory_percent)

-- ML model outputs
ml_predictions (id, host_id, ts, model_name, target, predicted_value,
                is_anomaly, anomaly_score, cluster_id, metrics_json)

-- Anomaly alerts
alerts (id, host_id, ts, severity, alert_type, message, resolved)
```

---

## 9. Setup and Running

### Prerequisites
- Python 3.8+
- MySQL Server running on `localhost:3306`
- A database named `isrm` created in MySQL

### Installation

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
# Edit .env with your MySQL credentials:
#   MYSQL_HOST=localhost
#   MYSQL_PORT=3306
#   MYSQL_USER=root
#   MYSQL_PASSWORD=your_password
#   MYSQL_DATABASE=isrm

# 4. Start the server
python app.py
# OR double-click RUN_SERVER.bat
# OR run .\RUN_SERVER.ps1
```

### Access
Open a browser and navigate to: **http://localhost:5000**

---

## 10. Key Design Decisions

| Decision | Rationale |
|---|---|
| MySQL over SQLite | Supports concurrent writes from the background thread and the web server without locking issues. |
| Background daemon thread | Decouples metric collection from HTTP request handling, ensuring consistent 2-second sampling regardless of web traffic. |
| Lazy model import | `model.py` is only imported when `/api/predict` is first called, reducing application startup time. |
| Sliding window for prediction | Captures temporal patterns in CPU usage without requiring a full time-series model. |
| Best-model selection at runtime | Automatically picks Linear Regression or Random Forest based on R² score on the current dataset, adapting to data characteristics. |
| Gzip compression | Reduces payload size by 60–70%, improving page load times especially for chart data. |

---

## 11. Limitations and Future Improvements

| Limitation | Suggested Improvement |
|---|---|
| Single-host monitoring only | Add multi-host support with agent-based remote collection. |
| No user authentication | Add login/session management to protect the dashboard. |
| ML models retrained on every API call | Cache trained models and retrain on a schedule or when data grows significantly. |
| No alerting notifications | Integrate email or webhook notifications when anomalies are detected. |
| Fixed 3-cluster K-Means | Use the elbow method or silhouette score to determine the optimal number of clusters dynamically. |
| Data retention unbounded | Add a data retention policy (e.g., auto-delete records older than 30 days). |

---

## 12. Sample API Response

**`GET /api/predict`**
```json
{
  "status": "success",
  "anomaly_detection": {
    "is_anomaly": false,
    "total_anomalies": 3,
    "description": "System behavior is normal"
  },
  "clustering": {
    "current_cluster": 1,
    "description": "System State: Cluster 1"
  },
  "prediction": {
    "next_cpu": 14.7,
    "model_used": "Random Forest"
  },
  "analysis": {
    "linear_regression": { "mse": 12.34, "r2": 0.76 },
    "random_forest":     { "mse": 8.21,  "r2": 0.89 },
    "winner": "Random Forest"
  }
}
```

---

*Report generated for the Intelligent System Resource Monitor project — April 2026*
