from flask import Flask, render_template, jsonify
import psutil
import threading
import time
import os
from dotenv import load_dotenv
from pathlib import Path

# Try to import flask_compress, but make it optional
try:
    from flask_compress import Compress
    HAS_COMPRESS = True
except ImportError:
    HAS_COMPRESS = False

# Load environment variables from .env file FIRST
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

import mysql_database as database
# Import model lazily (only when needed) to speed up startup
# import model
import logging
import platform
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Enable compression for faster loading (if available)
if HAS_COMPRESS:
    Compress(app)

# Lazy import model only when needed
def get_model():
    global model
    if 'model' not in globals():
        import model as m
        model = m
    return model

# Add cache control headers for static files
@app.after_request
def add_cache_headers(response):
    if response.mimetype == 'application/javascript' or response.mimetype == 'text/css':
        response.cache_control.max_age = 86400  # Cache JS/CSS for 24 hours
    elif response.mimetype.startswith('image/'):
        response.cache_control.max_age = 604800  # Cache images for 7 days
    return response

# Initialize DB
database.init_db()

# Register host metadata
try:
    database.upsert_host(
        database.DEFAULT_HOSTNAME,
        os_name=platform.system(),
        os_release=platform.release(),
        machine=platform.machine(),
        processor=platform.processor(),
        cpu_count=psutil.cpu_count(logical=True),
        ram_total_bytes=psutil.virtual_memory().total,
    )
except Exception as e:
    logger.error(f"Failed to upsert host metadata: {e}")

# Global variables for background thread
collecting = True
last_net_io = psutil.net_io_counters()
last_disk_io = psutil.disk_io_counters()

def collect_metrics():
    global last_net_io, last_disk_io
    while collecting:
        try:
            # CPU & RAM
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:\\').percent
            swap = psutil.swap_memory().percent
            cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0

            process_count = len(psutil.pids())
            
            # Network I/O (Rate calculation)
            curr_net_io = psutil.net_io_counters()
            sent_bytes = curr_net_io.bytes_sent - last_net_io.bytes_sent
            recv_bytes = curr_net_io.bytes_recv - last_net_io.bytes_recv
            last_net_io = curr_net_io
            
            # Disk I/O (Rate calculation)
            curr_disk_io = psutil.disk_io_counters()
            read_bytes = curr_disk_io.read_bytes - last_disk_io.read_bytes
            write_bytes = curr_disk_io.write_bytes - last_disk_io.write_bytes
            last_disk_io = curr_disk_io
            
            # Insert into DB
            host_id = database.get_host_id(database.DEFAULT_HOSTNAME)
            if host_id is None:
                host_id = database.upsert_host(database.DEFAULT_HOSTNAME)
            ts = time.time()
            database.insert_metric_row(
                host_id,
                ts,
                cpu,
                ram,
                disk,
                sent_bytes,
                recv_bytes,
                swap,
                read_bytes,
                write_bytes,
                cpu_freq,
                process_count=process_count,
            )

            # Store a lightweight process snapshot (top 5 by CPU at that moment)
            try:
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                top_processes = sorted(processes, key=lambda p: p.get('cpu_percent', 0) or 0, reverse=True)[:5]
                database.insert_process_samples(host_id, ts, top_processes)
            except Exception as e:
                logger.error(f"Failed to store process samples: {e}")
            
            time.sleep(2) # Collect every 2 seconds
        except Exception as e:
            logger.error(f"Error in background collection: {e}")
            time.sleep(5) 

# Start background thread
t = threading.Thread(target=collect_metrics)
t.daemon = True
t.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analysis')
def analysis():
    return render_template('analysis.html')

@app.route('/processes')
def processes():
    return render_template('processes.html')

@app.route('/system')
def system():
    return render_template('system.html')

@app.route('/data')
def data():
    return render_template('data.html')

@app.route('/api/system_info')
def get_system_info():
    # Static system info
    try:
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        info = {
            'os': platform.system(),
            'os_release': platform.release(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'boot_time': boot_time,
            'cpu_count': psutil.cpu_count(logical=True),
            'ram_total': f"{round(psutil.virtual_memory().total / (1024**3), 2)} GB"
        }
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/metrics')
def get_metrics():
    try:
        # Get latest current readings
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:\\').percent
        swap = psutil.swap_memory().percent
        cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0
        process_count = len(psutil.pids())

        return jsonify({
            'cpu': cpu,
            'ram': ram,
            'disk': disk,
            'swap': swap,
            'cpu_freq': cpu_freq,
            'process_count': process_count
        })
    except Exception as e:
        logger.error(f"Error in /api/metrics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def get_history():
    try:
        data = database.get_recent_metrics(50)
        # Format for chart
        timestamps = [row[0] for row in data]
        cpu_data = [row[1] for row in data]
        ram_data = [row[2] for row in data]
        net_sent = [row[4] for row in data] # Bytes
        net_recv = [row[5] for row in data] # Bytes
        disk_read = [row[7] for row in data] # Bytes
        disk_write = [row[8] for row in data] # Bytes
        
        return jsonify({
            'labels': timestamps,
            'cpu': cpu_data,
            'ram': ram_data,
            'net_sent': net_sent,
            'net_recv': net_recv,
            'disk_read': disk_read,
            'disk_write': disk_write
        })
    except Exception as e:
        logger.error(f"Error in /api/history: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/processes')
def get_processes():
    try:
        # Get top 5 processes by CPU usage
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
            try:
                pinfo = proc.info
                # Get CPU percent with a small interval to get accurate reading
                pinfo['cpu_percent'] = proc.cpu_percent(interval=0.1)
                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Sort by CPU usage and get top 5
        top_processes = sorted(processes, key=lambda p: p.get('cpu_percent', 0) or 0, reverse=True)[:5]
        return jsonify(top_processes)
    except Exception as e:
        logger.error(f"Error in /api/processes: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/predict')
def predict():
    try:
        m = get_model()  # Load model only when needed
        result = m.analyze_and_predict()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in /api/predict: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/all_metrics')
def get_all_metrics():
    try:
        data = database.get_all_metrics()
        metrics_list = []
        for row in data:
            metrics_list.append({
                'timestamp': row[0],
                'cpu': row[1],
                'ram': row[2],
                'disk': row[3],
                'net_sent': row[4],
                'net_recv': row[5],
                'swap': row[6],
                'disk_read': row[7],
                'disk_write': row[8],
                'cpu_freq': row[9]
            })
        return jsonify(metrics_list)
    except Exception as e:
        logger.error(f"Error in /api/all_metrics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/all_processes')
def get_all_processes():
    try:
        # Get all unique process samples from database
        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ts, pid, name, cpu_percent, memory_percent 
            FROM process_samples 
            ORDER BY ts DESC 
            LIMIT 1000
        """)
        data = cursor.fetchall()
        conn.close()
        
        processes_list = []
        for row in data:
            processes_list.append({
                'timestamp': row[0],
                'pid': row[1],
                'name': row[2],
                'cpu': row[3],
                'memory': row[4]
            })
        return jsonify(processes_list)
    except Exception as e:
        logger.error(f"Error in /api/all_processes: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=False, port=port)
