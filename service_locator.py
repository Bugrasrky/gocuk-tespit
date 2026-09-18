import json
import math
import os
import glob
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import Button, Frame, Label, Toplevel, Tk
import pandas as pd
from paths import resource_path

SCRIPT_DIR = os.path.dirname(resource_path("Service_Locations.xlsx"))
def find_excel_file():
    files = glob.glob(os.path.join(SCRIPT_DIR, "*.xlsx"))
    for f in files:
        if "service" in f.lower() or "sube" in f.lower() or "location" in f.lower():
            return f
    return os.path.join(SCRIPT_DIR, "Service_Locations.xlsx")

EXCEL_FILE = find_excel_file()

def clean_coordinate(val):
    if pd.isna(val) or str(val).strip() == '':
        return None
    s_val = str(val).replace(',', '.')
    if s_val.count('.') > 1:
        parts = s_val.split('.')
        s_val = parts[0] + '.' + ''.join(parts[1:])
    try:
        num = float(s_val)
        if num > 0:
            while num > 100:
                num /= 10
        return num
    except Exception:
        return None

def analyze_service_tags(name):
    """Şube ismindeki anahtar kelimelere göre hizmetleri sınıflandırır."""
    name_lower = name.lower()
    tags = []
    
    if "boyasız" in name_lower or "dolu" in name_lower:
        tags.append(("Boyasız Göçük Onarımı", "#10b981", "#ecfdf5")) # Yeşil
    if "mobil" in name_lower:
        tags.append(("Mobil Hizmet", "#3b82f6", "#eff6ff")) # Mavi
    if "mini" in name_lower:
        tags.append(("Mini Onarım", "#f59e0b", "#fffbeb")) # Turuncu
    if "radyatör" in name_lower:
        tags.append(("Radyatör", "#64748b", "#f8fafc")) # Gri
        
    # Eğer hiçbir özel tag yoksa standart servis sayalım
    if not tags:
        tags.append(("Genel Hasar Servisi", "#6366f1", "#eef2ff")) # İndigo
        
    return tags

def load_branches_from_excel():
    if not os.path.exists(EXCEL_FILE):
        return []

    try:
        df = pd.read_excel(EXCEL_FILE)
        cols = {str(c).strip().lower(): c for c in df.columns}
        
        lat_col_name = cols.get('lat', cols.get('enlem'))
        lon_col_name = cols.get('lon', cols.get('boylam'))
        
        if not lat_col_name or not lon_col_name:
            return []

        branches = []
        fail_count = 0
        for i, row in df.iterrows():
            name_col = cols.get('servis adı', cols.get('isim', 'Servis Adı'))
            name = str(row.get(name_col, '')).strip()
            if not name or name == 'nan':
                continue
                
            addr_col = cols.get('adres', 'Adres')
            address = str(row.get(addr_col, '')).strip()
            if address == 'nan': address = ''
            
            tel_col = cols.get('telefon', 'Telefon')
            phone = str(row.get(tel_col, '')).strip()
            if phone == 'nan': phone = ''
            
            email_col = cols.get('e-posta', cols.get('eposta', 'E-posta'))
            email = str(row.get(email_col, '')).strip()
            if email == 'nan': email = ''
            
            hours_col = cols.get('çalışma saatleri', 'Çalışma Saatleri')
            hours = str(row.get(hours_col, '')).strip()
            if hours == 'nan': hours = ''
            
            lat = clean_coordinate(row.get(lat_col_name))
            lon = clean_coordinate(row.get(lon_col_name))
            
            if lat is None or lon is None:
                fail_count += 1
                continue 
                
            branches.append({
                'name': name,
                'tags': analyze_service_tags(name), # ETİKETLER BURADA EKLENDİ
                'address': address,
                'phone': phone,
                'email': email,
                'hours': hours,
                'lat': lat,
                'lon': lon
            })
            
        print(f"[BİLGİ] Excel'den koordinatı olan {len(branches)} şube okundu. (Atlanan: {fail_count})")
        return branches
    except Exception as e:
        print(f"[HATA] Excel okuma hatası: {e}")
        return []

def get_user_location():
    try:
        url = "https://ipapi.co/json/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return float(data.get("latitude", 41.0082)), float(data.get("longitude", 28.9784)), data.get("city", "İstanbul")
    except Exception:
        return 41.0082, 28.9784, "İstanbul"

def haversine_distance(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return round(r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)

def show_nearest_services_window(parent=None):
    u_lat, u_lon, city = get_user_location()
    branches = load_branches_from_excel()
    
    if not branches:
        print("[HATA] Geçerli koordinata sahip şube bulunamadı.")
        return

    for b in branches:
        b["distance"] = haversine_distance(u_lat, u_lon, b["lat"], b["lon"])

    branches.sort(key=lambda x: x["distance"])
    nearest_branches = branches[:3]

    win = Toplevel(parent) if parent is not None else Tk()
    win.title("RS Servis - En Yakın Onarım Merkezleri")
    win.geometry("540x670") # Ek etiketler sığsın diye boyutu biraz daha uzattım
    win.attributes("-topmost", True)
    win.resizable(False, False)
    win.configure(bg="#f8fafc")

    header = Frame(win, bg="#0f172a", padx=16, pady=12)
    header.pack(fill="x")
    Label(header, text="📍 Size En Yakın Yetkili Servisler", font=("Arial", 12, "bold"), fg="#ffffff", bg="#0f172a").pack(anchor="w", pady=(4, 2))
    Label(header, text=f"Bölgeniz: {city} (GPS: {u_lat:.2f}, {u_lon:.2f})", font=("Arial", 8), fg="#94a3b8", bg="#0f172a").pack(anchor="w")

    for b in nearest_branches:
        card = Frame(win, bg="#ffffff", padx=14, pady=10, highlightbackground="#e2e8f0", highlightthickness=1)
        card.pack(fill="x", padx=14, pady=6)
        
        # Şube Başlığı ve Mesafe
        title_frame = Frame(card, bg="#ffffff")
        title_frame.pack(fill="x")
        Label(title_frame, text=b["name"], font=("Arial", 10, "bold"), fg="#0f172a", bg="#ffffff").pack(side="left")
        Label(title_frame, text=f"🚗 {b['distance']} km", font=("Arial", 10, "bold"), fg="#e11d48", bg="#ffffff").pack(side="right")
        
        # Hizmet Etiketleri (Sınıflandırma Badgeleri)
        tags_frame = Frame(card, bg="#ffffff")
        tags_frame.pack(fill="x", pady=(4, 6))
        for tag_text, fg_color, bg_color in b["tags"]:
            # Modern yuvarlatılmış hap (badge) görünümü
            tag_lbl = Label(tags_frame, text=f" {tag_text} ", font=("Arial", 7, "bold"), fg=fg_color, bg=bg_color, relief="solid", bd=1)
            tag_lbl.pack(side="left", padx=(0, 5))
        
        # Tam Adres
        if b["address"]:
            Label(card, text=b["address"], font=("Arial", 8), fg="#64748b", bg="#ffffff", wraplength=480, justify="left").pack(anchor="w", pady=(4, 2))
        
        # Yeni Veriler: Telefon, E-posta, Saatler
        details_frame = Frame(card, bg="#ffffff")
        details_frame.pack(fill="x", pady=2)
        
        if b["phone"]:
            Label(details_frame, text=f"📞 {b['phone']}", font=("Arial", 8), fg="#334155", bg="#ffffff").pack(anchor="w")
        if b["email"]:
            Label(details_frame, text=f"📧 {b['email']}", font=("Arial", 8), fg="#334155", bg="#ffffff").pack(anchor="w")
        if b["hours"]:
            display_hours = b["hours"][:60] + "..." if len(b["hours"]) > 60 else b["hours"]
            Label(details_frame, text=f"⏰ {display_hours}", font=("Arial", 8), fg="#334155", bg="#ffffff").pack(anchor="w")

        # Buton
        action_frame = Frame(card, bg="#ffffff")
        action_frame.pack(fill="x", pady=(6, 0))
        Button(action_frame, text="Yol Tarifi Al (Google Maps)", font=("Arial", 8, "bold"),
               bg="#e11d48", fg="#ffffff", cursor="hand2", padx=10, pady=3,
               command=lambda lat=b["lat"], lon=b["lon"]: webbrowser.open(f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}")).pack(side="right")
    
    win.wait_window()

if __name__ == "__main__":
    show_nearest_services_window()