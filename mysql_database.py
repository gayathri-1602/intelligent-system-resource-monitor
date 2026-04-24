import os
import time
import mysql.connector
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

DEFAULT_HOSTNAME = "local"


def _db_config():
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "isrm"),
        "autocommit": True,
    }


def get_connection():
    return mysql.connector.connect(**_db_config())


def init_db():
    conn = get_connection()
    try:
        c = conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS hosts (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                hostname VARCHAR(255) NOT NULL,
                os_name VARCHAR(64),
                os_release VARCHAR(64),
                machine VARCHAR(64),
                processor VARCHAR(255),
                cpu_count INT,
                ram_total_bytes BIGINT,
                created_at DOUBLE NOT NULL,
                UNIQUE KEY uq_hosts_hostname (hostname)
            ) ENGINE=InnoDB
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                host_id BIGINT NOT NULL,
                ts DOUBLE NOT NULL,
                cpu_usage DOUBLE NOT NULL,
                ram_usage DOUBLE NOT NULL,
                disk_usage DOUBLE NOT NULL,
                net_sent_bytes DOUBLE NOT NULL,
                net_recv_bytes DOUBLE NOT NULL,
                swap_usage DOUBLE NOT NULL,
                disk_read_bytes DOUBLE NOT NULL,
                disk_write_bytes DOUBLE NOT NULL,
                cpu_freq_mhz DOUBLE NOT NULL,
                process_count INT,
                CONSTRAINT fk_metrics_host FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE CASCADE,
                INDEX idx_metrics_host_ts (host_id, ts)
            ) ENGINE=InnoDB
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS process_samples (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                host_id BIGINT NOT NULL,
                ts DOUBLE NOT NULL,
                pid INT,
                name VARCHAR(255),
                cpu_percent DOUBLE,
                memory_percent DOUBLE,
                CONSTRAINT fk_proc_host FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE CASCADE,
                INDEX idx_proc_host_ts (host_id, ts)
            ) ENGINE=InnoDB
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS ml_predictions (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                host_id BIGINT NOT NULL,
                ts DOUBLE NOT NULL,
                model_name VARCHAR(128) NOT NULL,
                target VARCHAR(64) NOT NULL,
                predicted_value DOUBLE,
                is_anomaly TINYINT,
                anomaly_score DOUBLE,
                cluster_id INT,
                metrics_json JSON,
                CONSTRAINT fk_pred_host FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE CASCADE,
                INDEX idx_pred_host_ts (host_id, ts)
            ) ENGINE=InnoDB
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                host_id BIGINT NOT NULL,
                ts DOUBLE NOT NULL,
                severity VARCHAR(16) NOT NULL,
                alert_type VARCHAR(64) NOT NULL,
                message TEXT NOT NULL,
                resolved TINYINT NOT NULL DEFAULT 0,
                CONSTRAINT fk_alert_host FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE CASCADE,
                INDEX idx_alerts_host_ts (host_id, ts)
            ) ENGINE=InnoDB
            """
        )

        c.execute("DROP VIEW IF EXISTS v_metrics_legacy")
        c.execute(
            """
            CREATE VIEW v_metrics_legacy AS
            SELECT
                m.ts AS timestamp,
                m.cpu_usage AS cpu_usage,
                m.ram_usage AS ram_usage,
                m.disk_usage AS disk_usage,
                m.net_sent_bytes AS net_sent,
                m.net_recv_bytes AS net_recv,
                m.swap_usage AS swap_usage,
                m.disk_read_bytes AS disk_read,
                m.disk_write_bytes AS disk_write,
                m.cpu_freq_mhz AS cpu_freq
            FROM metrics m
            ORDER BY m.ts ASC
            """
        )
    finally:
        conn.close()


def upsert_host(
    hostname,
    os_name=None,
    os_release=None,
    machine=None,
    processor=None,
    cpu_count=None,
    ram_total_bytes=None,
):
    conn = get_connection()
    try:
        c = conn.cursor()
        now = time.time()
        c.execute(
            """
            INSERT INTO hosts (hostname, os_name, os_release, machine, processor, cpu_count, ram_total_bytes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                os_name=VALUES(os_name),
                os_release=VALUES(os_release),
                machine=VALUES(machine),
                processor=VALUES(processor),
                cpu_count=VALUES(cpu_count),
                ram_total_bytes=VALUES(ram_total_bytes)
            """,
            (hostname, os_name, os_release, machine, processor, cpu_count, ram_total_bytes, now),
        )
        c.execute("SELECT id FROM hosts WHERE hostname=%s", (hostname,))
        row = c.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_host_id(hostname=DEFAULT_HOSTNAME):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT id FROM hosts WHERE hostname=%s", (hostname,))
        row = c.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def insert_metric_row(
    host_id,
    ts,
    cpu,
    ram,
    disk,
    net_sent,
    net_recv,
    swap,
    disk_read,
    disk_write,
    cpu_freq,
    process_count=None,
):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO metrics (
                host_id, ts, cpu_usage, ram_usage, disk_usage,
                net_sent_bytes, net_recv_bytes, swap_usage,
                disk_read_bytes, disk_write_bytes, cpu_freq_mhz, process_count
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                host_id,
                ts,
                cpu,
                ram,
                disk,
                net_sent,
                net_recv,
                swap,
                disk_read,
                disk_write,
                cpu_freq,
                process_count,
            ),
        )
    finally:
        conn.close()


def insert_process_samples(host_id, ts, processes):
    if not processes:
        return
    conn = get_connection()
    try:
        c = conn.cursor()
        rows = [
            (host_id, ts, p.get("pid"), p.get("name"), p.get("cpu_percent"), p.get("memory_percent"))
            for p in processes
        ]
        c.executemany(
            """
            INSERT INTO process_samples (host_id, ts, pid, name, cpu_percent, memory_percent)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            rows,
        )
    finally:
        conn.close()


def insert_prediction(
    host_id,
    ts,
    model_name,
    target,
    predicted_value=None,
    is_anomaly=None,
    anomaly_score=None,
    cluster_id=None,
    metrics_json=None,
):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO ml_predictions (
                host_id, ts, model_name, target, predicted_value,
                is_anomaly, anomaly_score, cluster_id, metrics_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CAST(%s AS JSON))
            """,
            (
                host_id,
                ts,
                model_name,
                target,
                predicted_value,
                int(is_anomaly) if is_anomaly is not None else None,
                anomaly_score,
                cluster_id,
                metrics_json,
            ),
        )
    finally:
        conn.close()


def insert_alert(host_id, ts, severity, alert_type, message, resolved=0):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO alerts (host_id, ts, severity, alert_type, message, resolved)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (host_id, ts, severity, alert_type, message, int(resolved)),
        )
    finally:
        conn.close()


def insert_metrics(cpu, ram, disk, net_sent, net_recv, swap, disk_read, disk_write, cpu_freq):
    host_id = get_host_id(DEFAULT_HOSTNAME)
    if host_id is None:
        host_id = upsert_host(DEFAULT_HOSTNAME)
    ts = time.time()
    insert_metric_row(host_id, ts, cpu, ram, disk, net_sent, net_recv, swap, disk_read, disk_write, cpu_freq)


def get_recent_metrics(limit=100):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT timestamp, cpu_usage, ram_usage, disk_usage, net_sent, net_recv, swap_usage, disk_read, disk_write, cpu_freq
            FROM v_metrics_legacy
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (limit,),
        )
        data = c.fetchall()
        return data[::-1]
    finally:
        conn.close()


def get_all_metrics():
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT timestamp, cpu_usage, ram_usage, disk_usage, net_sent, net_recv, swap_usage, disk_read, disk_write, cpu_freq
            FROM v_metrics_legacy
            ORDER BY timestamp ASC
            """
        )
        return c.fetchall()
    finally:
        conn.close()
