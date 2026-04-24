let mainChart, networkChart, diskIoChart;

// Initialize Charts
function initCharts() {
    const ctxMain = document.getElementById('mainChart').getContext('2d');
    mainChart = new Chart(ctxMain, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'CPU (%)',
                    borderColor: '#6c5ce7',
                    backgroundColor: 'rgba(108, 92, 231, 0.1)',
                    data: [],
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'RAM (%)',
                    borderColor: '#0984e3',
                    backgroundColor: 'rgba(9, 132, 227, 0.1)',
                    data: [],
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                y: { beginAtZero: true, max: 100 }
            }
        }
    });

    const ctxNet = document.getElementById('networkChart').getContext('2d');
    networkChart = new Chart(ctxNet, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Sent (KB/s)',
                    borderColor: '#00b894',
                    data: [],
                    tension: 0.3
                },
                {
                    label: 'Recv (KB/s)',
                    borderColor: '#e17055',
                    data: [],
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true }
            }
        }
    });

    const ctxDisk = document.getElementById('diskIoChart').getContext('2d');
    diskIoChart = new Chart(ctxDisk, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Read (KB/s)',
                    borderColor: '#fdcb6e',
                    data: [],
                    tension: 0.3
                },
                {
                    label: 'Write (KB/s)',
                    borderColor: '#d63031',
                    data: [],
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}

// Fetch Functions
async function updateMetrics() {
    try {
        const res = await fetch('/api/metrics');
        const data = await res.json();
        
        // Update Cards
        document.getElementById('cpu-val').innerText = data.cpu + '%';
        document.getElementById('cpu-bar').style.width = data.cpu + '%';
        
        document.getElementById('ram-val').innerText = data.ram + '%';
        document.getElementById('ram-bar').style.width = data.ram + '%';
        
        document.getElementById('disk-val').innerText = data.disk + '%';
        document.getElementById('disk-bar').style.width = data.disk + '%';

        document.getElementById('swap-val').innerText = data.swap + '%';
        document.getElementById('swap-bar').style.width = data.swap + '%';
        
        document.getElementById('cpu-freq-val').innerText = data.cpu_freq.toFixed(0) + ' MHz';
        
        document.getElementById('process-count').innerText = data.process_count;
    } catch (e) {
        console.error("Metrics error", e);
    }
}

async function updateHistory() {
    try {
        const res = await fetch('/api/history');
        const data = await res.json();
        
        if (mainChart && networkChart) {
            const labels = data.labels.map(ts => new Date(ts * 1000).toLocaleTimeString());
            
            // Update Main Chart
            mainChart.data.labels = labels;
            mainChart.data.datasets[0].data = data.cpu;
            mainChart.data.datasets[1].data = data.ram;
            mainChart.update('none'); // 'none' for smooth animation
            
            // Update Network Chart (Convert Bytes to KB)
            networkChart.data.labels = labels;
            networkChart.data.datasets[0].data = data.net_sent.map(b => (b/1024).toFixed(1));
            networkChart.data.datasets[1].data = data.net_recv.map(b => (b/1024).toFixed(1));
            networkChart.update('none');

            // Update Disk I/O Chart
            diskIoChart.data.labels = labels;
            diskIoChart.data.datasets[0].data = data.disk_read.map(b => (b/1024).toFixed(1));
            diskIoChart.data.datasets[1].data = data.disk_write.map(b => (b/1024).toFixed(1));
            diskIoChart.update('none');
        }
    } catch (e) {
        console.error("History error", e);
    }
}

async function updateAnalysis() {
    try {
        const res = await fetch('/api/predict');
        const data = await res.json();
        
        if (data.status === 'success') {
            // Prediction
            document.getElementById('prediction-val').innerText = data.prediction.next_cpu.toFixed(1) + '%';
            document.getElementById('model-name').innerText = data.prediction.model_used;
            document.getElementById('prediction-status').innerText = "Updated just now";
            
            // Anomaly
            const anomalyBox = document.getElementById('anomaly-status');
            const anomalyDesc = document.getElementById('anomaly-desc');
            if (data.anomaly_detection.is_anomaly) {
                anomalyBox.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Anomaly Detected';
                anomalyBox.className = 'status-box danger';
                anomalyDesc.innerText = "Unusual resource usage pattern detected!";
            } else {
                anomalyBox.innerHTML = '<i class="fas fa-check-circle"></i> Normal';
                anomalyBox.className = 'status-box';
                anomalyDesc.innerText = "System behavior is within expected parameters.";
            }
            
            // Model Stats
            document.getElementById('lr-mse').innerText = data.analysis.linear_regression.mse.toFixed(2);
            document.getElementById('lr-r2').innerText = data.analysis.linear_regression.r2.toFixed(2);
            document.getElementById('rf-mse').innerText = data.analysis.random_forest.mse.toFixed(2);
            document.getElementById('rf-r2').innerText = data.analysis.random_forest.r2.toFixed(2);

            // Clustering
            document.getElementById('cluster-status').innerHTML = `<i class="fas fa-layer-group"></i> Cluster ${data.clustering.current_cluster}`;
            document.getElementById('cluster-desc').innerText = data.clustering.description;

            // Correlation Matrix
            const corrTable = document.getElementById('correlation-table');
            let corrHtml = '<thead><tr><th>Feature</th>';
            const keys = Object.keys(data.correlation);
            keys.forEach(k => corrHtml += `<th>${k}</th>`);
            corrHtml += '</tr></thead><tbody>';
            
            keys.forEach(rowKey => {
                corrHtml += `<tr><td><b>${rowKey}</b></td>`;
                keys.forEach(colKey => {
                    const val = data.correlation[rowKey][colKey];
                    // Colorize based on correlation
                    let color = 'inherit';
                    if (val > 0.7) color = '#00b894';
                    if (val < -0.7) color = '#d63031';
                    corrHtml += `<td style="color:${color}">${val}</td>`;
                });
                corrHtml += '</tr>';
            });
            corrHtml += '</tbody>';
            corrTable.innerHTML = corrHtml;
        }
    } catch (e) {
        console.error("Analysis error", e);
    }
}

function exportData() {
    window.location.href = "/api/history"; // Simple JSON export via API
}

async function updateProcesses() {
    try {
        const res = await fetch('/api/processes');
        const data = await res.json();
        
        const tbody = document.getElementById('process-list');
        tbody.innerHTML = '';
        
        data.forEach(proc => {
            const row = `<tr>
                <td>${proc.pid}</td>
                <td><b>${proc.name}</b></td>
                <td>${proc.cpu_percent.toFixed(1)}%</td>
                <td>${proc.memory_percent.toFixed(1)}%</td>
            </tr>`;
            tbody.innerHTML += row;
        });
    } catch (e) {
        console.error("Process error", e);
    }
}

async function loadSystemInfo() {
    try {
        const res = await fetch('/api/system_info');
        const data = await res.json();
        
        const container = document.getElementById('sys-info');
        const items = [
            ['OS', data.os + ' ' + data.os_release],
            ['Processor', data.processor],
            ['CPU Cores', data.cpu_count],
            ['Total RAM', data.ram_total],
            ['Boot Time', data.boot_time]
        ];
        
        container.innerHTML = items.map(([label, val]) => 
            `<div class="sys-item"><strong>${label}</strong>${val}</div>`
        ).join('');
    } catch (e) {
        console.error("Sys info error", e);
    }
}

// Update Clock
setInterval(() => {
    document.getElementById('current-time').innerText = new Date().toLocaleString();
}, 1000);

// Init
document.addEventListener('DOMContentLoaded', () => {
    // Determine which page we are on by checking for unique elements
    const isDashboard = document.getElementById('mainChart');
    const isAnalysis = document.getElementById('prediction-val');
    const isProcesses = document.getElementById('process-list');
    const isSystem = document.getElementById('sys-info');

    if (isDashboard) {
        initCharts();
        setInterval(updateMetrics, 2000);
        setInterval(updateHistory, 2000);
        // Initial calls
        updateMetrics();
        updateHistory();
    }

    if (isAnalysis) {
        updateAnalysis();
        setInterval(updateAnalysis, 10000);
    }

    if (isProcesses) {
        updateProcesses();
        setInterval(updateProcesses, 5000);
    }

    if (isSystem) {
        loadSystemInfo();
    }
});
