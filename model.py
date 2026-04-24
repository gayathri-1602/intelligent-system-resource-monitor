import pandas as pd
import numpy as np
import json
import time
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.cluster import KMeans
from sklearn.metrics import mean_squared_error, r2_score
import mysql_database as database

def analyze_and_predict():
    data = database.get_all_metrics()
    if len(data) < 20:
        return {
            'status': 'error',
            'message': 'Not enough data (need at least 20 points)'
        }

    # Update columns to match new schema
    df = pd.DataFrame(data, columns=['timestamp', 'cpu', 'ram', 'disk', 'net_sent', 'net_recv', 'swap', 'disk_read', 'disk_write', 'cpu_freq'])
    
    # --- 1. Anomaly Detection (Algorithm Analysis) ---
    # Using Isolation Forest to detect anomalies in CPU and RAM usage
    iso_forest = IsolationForest(contamination=0.1, random_state=42)
    df['anomaly'] = iso_forest.fit_predict(df[['cpu', 'ram', 'swap']])
    # -1 is anomaly, 1 is normal
    anomalies = df[df['anomaly'] == -1]
    latest_is_anomaly = df.iloc[-1]['anomaly'] == -1
    
    # --- 2. Clustering (Algorithm Analysis) ---
    # Cluster system states into 3 categories (e.g., Idle, Normal, High Load)
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    features_for_clustering = df[['cpu', 'ram', 'disk', 'swap']].fillna(0)
    df['cluster'] = kmeans.fit_predict(features_for_clustering)
    current_cluster = int(df.iloc[-1]['cluster'])
    
    # --- 3. Correlation Analysis ---
    correlation = df[['cpu', 'ram', 'disk', 'net_sent', 'net_recv', 'swap', 'cpu_freq']].corr().fillna(0).round(2).to_dict()

    # --- 4. Predictive Modeling (CPU) ---
    window_size = 5
    X = []
    y = []
    values = df['cpu'].values
    for i in range(len(values) - window_size):
        X.append(values[i:i+window_size])
        y.append(values[i+window_size])
    
    X = np.array(X)
    y = np.array(y)
    
    # Split for evaluation
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    # Model 1: Linear Regression
    lr_model = LinearRegression()
    lr_model.fit(X_train, y_train)
    lr_preds = lr_model.predict(X_test)
    lr_mse = mean_squared_error(y_test, lr_preds)
    lr_r2 = r2_score(y_test, lr_preds)
    
    # Model 2: Random Forest (for comparison)
    rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
    rf_model.fit(X_train, y_train)
    rf_preds = rf_model.predict(X_test)
    rf_mse = mean_squared_error(y_test, rf_preds)
    rf_r2 = r2_score(y_test, rf_preds)
    
    # Select best model for future prediction (simplistic selection)
    best_model = lr_model if lr_r2 > rf_r2 else rf_model
    best_model_name = "Linear Regression" if lr_r2 > rf_r2 else "Random Forest"
    
    # Predict next step
    last_window = values[-window_size:].reshape(1, -1)
    next_cpu = best_model.predict(last_window)[0]

    # Persist prediction + anomaly/cluster info
    try:
        host_id = database.get_host_id(database.DEFAULT_HOSTNAME)
        if host_id is None:
            host_id = database.upsert_host(database.DEFAULT_HOSTNAME)

        ts = time.time()
        payload = {
            'anomaly': {
                'is_anomaly': bool(latest_is_anomaly),
                'total_anomalies': int(len(anomalies)),
            },
            'cluster': {'current_cluster': current_cluster},
            'analysis': {
                'linear_regression': {'mse': float(lr_mse), 'r2': float(lr_r2)},
                'random_forest': {'mse': float(rf_mse), 'r2': float(rf_r2)},
                'winner': best_model_name,
            },
        }

        database.insert_prediction(
            host_id=host_id,
            ts=ts,
            model_name=best_model_name,
            target='cpu',
            predicted_value=float(next_cpu),
            is_anomaly=bool(latest_is_anomaly),
            cluster_id=current_cluster,
            metrics_json=json.dumps(payload),
        )

        if latest_is_anomaly:
            database.insert_alert(
                host_id=host_id,
                ts=ts,
                severity='high',
                alert_type='anomaly',
                message='Unusual Resource Usage Detected',
                resolved=0,
            )
    except Exception:
        # Keep API working even if DB write fails
        pass
    
    return {
        'status': 'success',
        'anomaly_detection': {
            'is_anomaly': bool(latest_is_anomaly),
            'total_anomalies': int(len(anomalies)),
            'description': 'Unusual Resource Usage Detected' if latest_is_anomaly else 'System behavior is normal'
        },
        'clustering': {
            'current_cluster': current_cluster,
            'description': f"System State: Cluster {current_cluster}"
        },
        'correlation': correlation,
        'prediction': {
            'next_cpu': float(next_cpu),
            'model_used': best_model_name
        },
        'analysis': {
            'linear_regression': {'mse': float(lr_mse), 'r2': float(lr_r2)},
            'random_forest': {'mse': float(rf_mse), 'r2': float(rf_r2)},
            'winner': best_model_name
        }
    }
