import socket
from flask import Flask, jsonify, request, render_template_string
from service_locator import find_nearest_branches

app = Flask(__name__)

# Telefon ekranı için sade, kurumsal RS Servis & Carshine Mobil Web Arayüzü
MOBILE_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RS Servis & Carshine Mobil</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 16px; background: #0f172a; color: #f8fafc; }
        .header { text-align: center; margin-bottom: 20px; }
        .header h1 { font-size: 20px; margin: 0; color: #e11d48; }
        .header p { font-size: 13px; color: #94a3b8; margin-top: 4px; }
        .card { background: #1e293b; border-radius: 12px; padding: 16px; margin-bottom: 12px; border: 1px solid #334155; }
        .card-title { font-weight: bold; font-size: 16px; display: flex; justify-content: space-between; align-items: center; }
        .distance { color: #e11d48; font-weight: bold; font-size: 15px; }
        .badge { display: inline-block; background: #0284c7; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin: 6px 0; }
        .address { font-size: 13px; color: #cbd5e1; line-height: 1.4; }
        .btn-nav { display: block; width: 100%; box-sizing: border-box; text-align: center; background: #e11d48; color: white; text-decoration: none; padding: 12px; border-radius: 8px; font-weight: bold; margin-top: 10px; }
        .status { text-align: center; font-size: 14px; padding: 20px; color: #38bdf8; }
    </style>
</head>
<body>
    <div class="header">
        <h1>RS SERVİS & CARSHINE</h1>
        <p>Mobil Onarım ve Servis Ağı</p>
    </div>

    <div id="status" class="status">📡 Telefonunuzun GPS konumu alınıyor...</div>
    <div id="results"></div>

    <script>
        function fetchNearest(lat, lon) {
            document.getElementById('status').innerText = '🔍 En yakın şubeler hesaplanıyor...';
            fetch(`/api/nearest?lat=${lat}&lon=${lon}`)
                .then(r => r.json())
                .then(data => {
                    document.getElementById('status').style.display = 'none';
                    let html = '';
                    data.forEach(b => {
                        html += `
                            <div class="card">
                                <div class="card-title">
                                    <span>${b.name}</span>
                                    <span class="distance">🚗 ${b.distance} km</span>
                                </div>
                                <div class="badge">${b.badge}</div>
                                <div class="address">${b.address}</div>
                                <a href="${b.nav_url}" class="btn-nav" target="_blank">Google Maps ile Git</a>
                            </div>
                        `;
                    });
                    document.getElementById('results').innerHTML = html;
                })
                .catch(err => {
                    document.getElementById('status').innerText = 'Hata oluştu: ' + err;
                });
        }

        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                pos => fetchNearest(pos.coords.latitude, pos.coords.longitude),
                err => {
                    document.getElementById('status').innerText = 'GPS izni verilmedi. Varsayılan konum gösteriliyor.';
                    fetchNearest(41.0082, 28.9784);
                }
            );
        } else {
            fetchNearest(41.0082, 28.9784);
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(MOBILE_HTML)

@app.route("/api/nearest")
def api_nearest():
    lat = float(request.args.get("lat", 41.0082))
    lon = float(request.args.get("lon", 28.9784))
    branches = find_nearest_branches(lat, lon, count=5)
    return jsonify(branches)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    ip = get_local_ip()
    print("\n" + "="*60)
    print("🚀 RS SERVİS & CARSHINE MOBİL SERVİSİ BAŞLATILDI")
    print(f"📱 Telefonunuzdan (aynı Wi-Fi): http://{ip}:5000 adresine girin")
    print("="*60 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)