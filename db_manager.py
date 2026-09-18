import sqlite3
import datetime
import os
from paths import writable_path

# Veritabanı dosyasının adı
DB_NAME = writable_path("gocuk_gecmisi.db")
def init_db():
    """Uygulama açıldığında veritabanını ve tabloyu hazır hale getirir."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Raporlar tablosunu oluştur
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS raporlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            hasar_tipi TEXT,
            boyut_cm TEXT,
            derinlik_mm TEXT,
            tahmini_masraf TEXT,
            boya_durumu TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_report(hasar_tipi, boyut_cm, derinlik_mm, tahmini_masraf, boya_durumu):
    """Yapılan ölçümü veritabanına kaydeder."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # O anki tarih ve saati al
    tarih = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    
    cursor.execute('''
        INSERT INTO raporlar (tarih, hasar_tipi, boyut_cm, derinlik_mm, tahmini_masraf, boya_durumu)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (tarih, hasar_tipi, boyut_cm, derinlik_mm, tahmini_masraf, boya_durumu))
    
    conn.commit()
    conn.close()
    print(f"[VERİTABANI] Ölçüm başarıyla kaydedildi! ({tarih})")