"""
Backend Alert Service
=====================
Receives alert notifications from the combined detection script.

Endpoints:
  POST /api/alerts       — Receive a new alert (multipart form with snapshot)
  GET  /api/alerts       — List all alerts (JSON)
  GET  /api/alerts/<id>  — Get a single alert (JSON)
  GET  /api/snapshots/<filename>  — Serve a saved snapshot image
  GET  /                 — Web dashboard to view alerts

Run:
  python backend_service.py
"""

from flask import Flask, request, jsonify, send_from_directory, render_template_string
from datetime import datetime
import os
import uuid

# -----------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------
HOST = "0.0.0.0"
PORT = 5050
SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")
# -----------------------------------------------------------

app = Flask(__name__)

# In-memory alert store (replace with a DB for production)
alerts_store = []

# Ensure snapshot directory exists
os.makedirs(SNAPSHOT_DIR, exist_ok=True)


# ===========================================================
# DASHBOARD HTML TEMPLATE
# ===========================================================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛡️ Security Alert Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --bg-primary: #0a0e1a;
            --bg-secondary: #111827;
            --bg-card: #1a2035;
            --bg-glass: rgba(26, 32, 53, 0.7);
            --border: rgba(255, 255, 255, 0.06);
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-red: #ef4444;
            --accent-red-glow: rgba(239, 68, 68, 0.25);
            --accent-orange: #f59e0b;
            --accent-orange-glow: rgba(245, 158, 11, 0.25);
            --accent-blue: #3b82f6;
            --accent-green: #22c55e;
            --accent-purple: #a855f7;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Animated background grid */
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background:
                linear-gradient(rgba(59, 130, 246, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(59, 130, 246, 0.03) 1px, transparent 1px);
            background-size: 60px 60px;
            z-index: 0;
        }

        .app { position: relative; z-index: 1; }

        /* Header */
        .header {
            background: linear-gradient(135deg, rgba(17, 24, 39, 0.95), rgba(26, 32, 53, 0.9));
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border);
            padding: 1.5rem 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .header h1 {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #f1f5f9, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .header h1 .shield-icon {
            font-size: 1.8rem;
            -webkit-text-fill-color: initial;
        }

        .live-badge {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.4rem 1rem;
            background: rgba(34, 197, 94, 0.1);
            border: 1px solid rgba(34, 197, 94, 0.3);
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 500;
            color: var(--accent-green);
        }

        .live-dot {
            width: 8px; height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            animation: pulse 2s ease-in-out infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
            50% { opacity: 0.7; box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
        }

        /* Stats bar */
        .stats-bar {
            max-width: 1400px;
            margin: 1.5rem auto;
            padding: 0 2rem;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }

        .stat-card {
            background: var(--bg-glass);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.25rem 1.5rem;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }

        .stat-card:hover {
            transform: translateY(-2px);
            border-color: rgba(255, 255, 255, 0.12);
        }

        .stat-label {
            font-size: 0.75rem;
            font-weight: 500;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 700;
        }

        .stat-value.red { color: var(--accent-red); }
        .stat-value.orange { color: var(--accent-orange); }
        .stat-value.blue { color: var(--accent-blue); }
        .stat-value.green { color: var(--accent-green); }

        /* Main content */
        .main {
            max-width: 1400px;
            margin: 0 auto;
            padding: 1rem 2rem 3rem;
        }

        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.25rem;
        }

        .section-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-secondary);
        }

        .refresh-btn {
            padding: 0.5rem 1.2rem;
            background: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 10px;
            color: var(--accent-blue);
            font-family: inherit;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .refresh-btn:hover {
            background: rgba(59, 130, 246, 0.2);
            border-color: var(--accent-blue);
        }

        /* Alert cards */
        .alerts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 1.25rem;
        }

        .alert-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
            animation: slideIn 0.4s ease forwards;
        }

        @keyframes slideIn {
            from { opacity: 0; transform: translateY(16px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .alert-card:hover {
            transform: translateY(-4px);
            border-color: rgba(255, 255, 255, 0.1);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
        }

        .alert-card.weapon { border-left: 4px solid var(--accent-red); }
        .alert-card.unknown_person { border-left: 4px solid var(--accent-orange); }
        .alert-card.weapon_and_unknown_person { border-left: 4px solid var(--accent-purple); }

        .alert-snapshot {
            width: 100%;
            height: 240px;
            object-fit: cover;
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            transition: filter 0.3s ease;
        }

        .alert-snapshot:hover { filter: brightness(1.1); }

        .alert-body { padding: 1.25rem; }

        .alert-type-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.3rem 0.8rem;
            border-radius: 8px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.75rem;
        }

        .badge-weapon {
            background: var(--accent-red-glow);
            color: var(--accent-red);
        }

        .badge-unknown {
            background: var(--accent-orange-glow);
            color: var(--accent-orange);
        }

        .badge-both {
            background: rgba(168, 85, 247, 0.2);
            color: var(--accent-purple);
        }

        .alert-details {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .detail-row {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.85rem;
        }

        .detail-label {
            color: var(--text-muted);
            min-width: 80px;
        }

        .detail-value { color: var(--text-primary); font-weight: 500; }

        .alert-timestamp {
            margin-top: 0.75rem;
            padding-top: 0.75rem;
            border-top: 1px solid var(--border);
            font-size: 0.78rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }

        .empty-state {
            text-align: center;
            padding: 6rem 2rem;
            color: var(--text-muted);
        }

        .empty-icon { font-size: 4rem; margin-bottom: 1rem; opacity: 0.3; }
        .empty-text { font-size: 1.1rem; margin-bottom: 0.5rem; }
        .empty-sub { font-size: 0.85rem; }

        /* Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.85);
            z-index: 1000;
            backdrop-filter: blur(8px);
            cursor: pointer;
            justify-content: center;
            align-items: center;
        }

        .modal-overlay.active { display: flex; }

        .modal-overlay img {
            max-width: 90vw;
            max-height: 90vh;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        }

        @media (max-width: 500px) {
            .alerts-grid { grid-template-columns: 1fr; }
            .header-content { flex-direction: column; gap: 0.75rem; }
            .stats-bar { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="app">
        <header class="header">
            <div class="header-content">
                <h1><span class="shield-icon">🛡️</span> Security Alert Dashboard</h1>
                <div class="live-badge"><div class="live-dot"></div> LIVE MONITORING</div>
            </div>
        </header>

        <div class="stats-bar" id="statsBar"></div>

        <main class="main">
            <div class="section-header">
                <span class="section-title">Recent Alerts</span>
                <button class="refresh-btn" onclick="fetchAlerts()">↻ Refresh</button>
            </div>
            <div class="alerts-grid" id="alertsGrid"></div>
        </main>
    </div>

    <!-- Image modal -->
    <div class="modal-overlay" id="modal" onclick="this.classList.remove('active')">
        <img id="modalImg" src="" alt="Full snapshot">
    </div>

    <script>
        const BADGE_MAP = {
            'weapon': { label: '🔫 Weapon Detected', cls: 'badge-weapon' },
            'unknown_person': { label: '👤 Unknown Person', cls: 'badge-unknown' },
            'weapon_and_unknown_person': { label: '⚠️ Weapon + Unknown', cls: 'badge-both' }
        };

        function openModal(src) {
            document.getElementById('modalImg').src = src;
            document.getElementById('modal').classList.add('active');
        }

        function renderStats(alerts) {
            const total = alerts.length;
            const weapons = alerts.filter(a => a.alert_type.includes('weapon')).length;
            const unknowns = alerts.filter(a => a.alert_type.includes('unknown')).length;
            const latest = total > 0 ? new Date(alerts[0].timestamp).toLocaleTimeString() : '—';

            document.getElementById('statsBar').innerHTML = `
                <div class="stat-card">
                    <div class="stat-label">Total Alerts</div>
                    <div class="stat-value red">${total}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Weapon Alerts</div>
                    <div class="stat-value orange">${weapons}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Unknown Person</div>
                    <div class="stat-value blue">${unknowns}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Last Alert</div>
                    <div class="stat-value green">${latest}</div>
                </div>
            `;
        }

        function renderAlerts(alerts) {
            const grid = document.getElementById('alertsGrid');

            if (alerts.length === 0) {
                grid.innerHTML = `
                    <div class="empty-state" style="grid-column: 1 / -1;">
                        <div class="empty-icon">🔒</div>
                        <div class="empty-text">No alerts yet</div>
                        <div class="empty-sub">The system is monitoring. Alerts will appear here.</div>
                    </div>`;
                return;
            }

            grid.innerHTML = alerts.map((a, i) => {
                const badge = BADGE_MAP[a.alert_type] || { label: a.alert_type, cls: 'badge-weapon' };
                const ts = new Date(a.timestamp);
                const timeStr = ts.toLocaleString();
                const weapons = a.weapons ? a.weapons : '—';
                const faces = a.faces ? a.faces : '—';
                const snapshotUrl = a.snapshot_url || '';
                const cardClass = a.alert_type || '';

                return `
                <div class="alert-card ${cardClass}" style="animation-delay: ${i * 0.06}s">
                    ${snapshotUrl
                        ? `<img class="alert-snapshot" src="${snapshotUrl}" alt="Alert snapshot"
                               onclick="openModal('${snapshotUrl}')" loading="lazy">`
                        : ''}
                    <div class="alert-body">
                        <div class="alert-type-badge ${badge.cls}">${badge.label}</div>
                        <div class="alert-details">
                            <div class="detail-row">
                                <span class="detail-label">Weapons</span>
                                <span class="detail-value">${weapons}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Faces</span>
                                <span class="detail-value">${faces}</span>
                            </div>
                            <div class="detail-row">
                                <span class="detail-label">Alert ID</span>
                                <span class="detail-value" style="font-size:0.75rem; opacity:0.6;">${a.id}</span>
                            </div>
                        </div>
                        <div class="alert-timestamp">🕐 ${timeStr}</div>
                    </div>
                </div>`;
            }).join('');
        }

        async function fetchAlerts() {
            try {
                const res = await fetch('/api/alerts');
                const data = await res.json();
                const sorted = data.alerts.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                renderStats(sorted);
                renderAlerts(sorted);
            } catch (err) {
                console.error('Failed to fetch alerts:', err);
            }
        }

        // Initial load
        fetchAlerts();

        // Auto-refresh every 3 seconds
        setInterval(fetchAlerts, 3000);
    </script>
</body>
</html>
"""


# ===========================================================
# ROUTES
# ===========================================================

@app.route("/")
def dashboard():
    """Serve the web dashboard."""
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/alerts", methods=["POST"])
def receive_alert():
    """
    Receive an alert from the detection script.

    Expects multipart/form-data with:
      - timestamp   (str)  ISO-format timestamp
      - alert_type  (str)  'weapon' | 'unknown_person' | 'weapon_and_unknown_person'
      - weapons     (str)  comma-separated weapon labels
      - faces       (str)  comma-separated face names
      - snapshot    (file) JPEG image of the frame
    """
    timestamp = request.form.get("timestamp", datetime.now().isoformat())
    alert_type = request.form.get("alert_type", "unknown")
    weapons = request.form.get("weapons", "")
    faces = request.form.get("faces", "")

    # Save snapshot if provided
    snapshot_filename = None
    snapshot_url = None

    snapshot_file = request.files.get("snapshot")
    if snapshot_file:
        ext = os.path.splitext(snapshot_file.filename)[1] if snapshot_file.filename else ".jpg"
        snapshot_filename = f"{uuid.uuid4().hex}{ext}"
        snapshot_path = os.path.join(SNAPSHOT_DIR, snapshot_filename)
        snapshot_file.save(snapshot_path)
        snapshot_url = f"/api/snapshots/{snapshot_filename}"
        print(f"  📸 Snapshot saved: {snapshot_path}")

    alert = {
        "id": uuid.uuid4().hex[:12],
        "timestamp": timestamp,
        "alert_type": alert_type,
        "weapons": weapons,
        "faces": faces,
        "snapshot_filename": snapshot_filename,
        "snapshot_url": snapshot_url,
    }

    alerts_store.append(alert)

    print(f"🚨 Alert received: [{alert_type.upper()}] weapons={weapons} faces={faces} @ {timestamp}")

    return jsonify({"status": "ok", "alert": alert}), 201


@app.route("/api/alerts", methods=["GET"])
def list_alerts():
    """Return all alerts as JSON."""
    return jsonify({"alerts": alerts_store, "total": len(alerts_store)})


@app.route("/api/alerts/<alert_id>", methods=["GET"])
def get_alert(alert_id):
    """Return a single alert by ID."""
    for alert in alerts_store:
        if alert["id"] == alert_id:
            return jsonify(alert)
    return jsonify({"error": "Alert not found"}), 404


@app.route("/api/snapshots/<filename>")
def serve_snapshot(filename):
    """Serve a saved snapshot image."""
    return send_from_directory(SNAPSHOT_DIR, filename)


# ===========================================================
# MAIN
# ===========================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  🛡️  Security Alert Backend Service")
    print("=" * 55)
    print(f"  Dashboard : http://localhost:{PORT}/")
    print(f"  API       : http://localhost:{PORT}/api/alerts")
    print(f"  Snapshots : {SNAPSHOT_DIR}")
    print("=" * 55)
    print()
    app.run(host=HOST, port=PORT, debug=True)
