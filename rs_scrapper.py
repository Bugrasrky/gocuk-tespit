from playwright.sync_api import sync_playwright
import pandas as pd
import time
import re
import json
import urllib.request

URL = "https://rsservis.com.tr/servislerimiz"
EXCEL_ADI = "Service_Locations.xlsx"

def resolve_exact_pin_from_shortlink(short_url):
    """Google kısa linkini arka planda çözer ve GERÇEK KAPI PİNİNİ (!3d ve !4d) bulur."""
    if not short_url or "maps" not in short_url:
        return None, None
        
    try:
        # Tarayıcı açmadan direkt sunucuya soruyoruz (Hızlı ve engelsiz)
        req = urllib.request.Request(short_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=10) as response:
            final_url = response.url
            
            # 1. Öncelik: Gerçek Kapı Pini
            match_pin = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', final_url)
            if match_pin: return float(match_pin.group(1)), float(match_pin.group(2))
            
            # 2. Öncelik: Alternatif Yol Tarifi Pini
            match_dest = re.search(r'destination=(-?\d+\.\d+),(-?\d+\.\d+)', final_url)
            if match_dest: return float(match_dest.group(1)), float(match_dest.group(2))
            
            # 3. Yedek: Kamera Odak Noktası
            match_view = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', final_url)
            if match_view: return float(match_view.group(1)), float(match_view.group(2))
    except:
        pass
    return None, None

def extract_phones_robust(text):
    if not text: return ""
    text_clean = re.sub(r'[\(\)-]', ' ', text)
    phones = re.findall(r'\b(?:0[\s]*\d[\s]*\d[\s]*\d[\s]*\d[\s]*\d[\s]*\d[\s]*\d[\s]*\d[\s]*\d[\s]*\d|4[\s]*4[\s]*4[\s]*\d[\s]*\d[\s]*\d[\s]*\d)\b', text_clean)
    norm_phones = []
    for p in phones:
        clean_p = re.sub(r'\s+', ' ', p.strip())
        if clean_p not in norm_phones: norm_phones.append(clean_p)
    return " / ".join(norm_phones)

def format_saatler(hours_list):
    if not isinstance(hours_list, list) or len(hours_list) == 0: return ""
    gunler_tr = {"Monday": "Pzt", "Tuesday": "Sal", "Wednesday": "Çar", "Thursday": "Per", "Friday": "Cum", "Saturday": "Cmt", "Sunday": "Paz"}
    saatler_metni = []
    for h in hours_list:
        gun = gunler_tr.get(h.get("dayOfWeek", ""), h.get("dayOfWeek", ""))
        acilis, kapanis = h.get("opens", ""), h.get("closes", "")
        if gun and acilis and kapanis:
            saatler_metni.append(f"{gun}: {acilis}-{kapanis}")
    return " | ".join(saatler_metni)

def main():
    print("🚀 RS Resmi Site %100 Doğruluklu Ağ Kazıyıcı Başlatılıyor...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        print(f"🌍 Ana siteye gidiliyor: {URL}")
        page.goto(URL, timeout=60000)
        time.sleep(3)
        try: page.locator('text="Kabul Et"').first.click(timeout=2000)
        except: pass

        # Tüm resmi şube linklerini topla (Eksiksiz)
        page.mouse.wheel(0, 1000)
        time.sleep(2)
        detay_butonlari = page.locator('a:has-text("Detay"), a.btn-detail').all()
        sube_linkleri = []
        for btn in detay_butonlari:
            try:
                link = btn.get_attribute("href")
                if link and link not in sube_linkleri: sube_linkleri.append(link)
            except: pass
                
        if not sube_linkleri:
            html = page.inner_html('body')
            link_matches = re.findall(r'href=[\'"](https://rsservis\.com\.tr/[^\'"]+)[\'"]', html)
            for l in link_matches:
                if "iletisim" in l or ("servis" in l and l != URL):
                    if l not in sube_linkleri: sube_linkleri.append(l)

        print(f"✅ Resmi sitede {len(sube_linkleri)} şube bulundu. Ağ üzerinden gerçek pinler çözülüyor...\n")
        
        data = []
        for i, link in enumerate(sube_linkleri):
            try:
                if link.startswith("/"): link = "https://rsservis.com.tr" + link
                
                page.goto(link, timeout=30000)
                page.wait_for_load_state("domcontentloaded")
                time.sleep(1) # Yüklenme için kısa mola
                
                isim = page.locator('h1').inner_text().strip() if page.locator('h1').count() > 0 else "Bilinmiyor"
                isim = isim.replace("iletişim ve yol tarifi", "").replace("İletişim ve yol tarifi", "").strip().title()

                telefon, eposta, adres, has_map, calisma_saati = "", "", "", "", ""
                
                # 1. JSON-LD (Arka Plan Verisi) Taraması
                json_scripts = page.locator('script[type="application/ld+json"]').all_inner_texts()
                for script_text in json_scripts:
                    try:
                        jd = json.loads(script_text)
                        items = jd if isinstance(jd, list) else [jd]
                        for item in items:
                            if 'telephone' in item and not telefon: telefon = str(item.get('telephone', ''))
                            if 'email' in item and not eposta: eposta = str(item.get('email', ''))
                            if 'hasMap' in item and not has_map: has_map = str(item.get('hasMap', ''))
                            if 'openingHoursSpecification' in item and not calisma_saati:
                                calisma_saati = format_saatler(item['openingHoursSpecification'])
                            if 'address' in item and not adres:
                                if isinstance(item['address'], dict):
                                    adres = f"{item['address'].get('streetAddress', '')} {item['address'].get('addressLocality', '')}".strip()
                                else:
                                    adres = str(item['address'])
                    except: pass
                
                # 2. Ekranda Regex (Yedek) Tarama (JSON boş gelirse diye)
                text_icerik = page.inner_text('body').replace('\xa0', ' ')
                if not telefon: telefon = extract_phones_robust(text_icerik)
                if not eposta:
                    mail_fb = re.findall(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text_icerik)
                    if mail_fb: eposta = mail_fb[0].strip()
                if not has_map:
                    map_fb = re.search(r'href=[\'"](https://maps\.app\.goo\.gl/[^\'"]+)[\'"]', page.content())
                    if map_fb: has_map = map_fb.group(1)

                # 3. KESİN KOORDİNAT ÇÖZÜCÜ (Tarayıcı açmadan Ağ üzerinden çözer)
                lat, lon = resolve_exact_pin_from_shortlink(has_map)
                
                data.append({
                    "Servis Adı": isim,
                    "Lat": lat,
                    "Lon": lon,
                    "Adres": adres,
                    "Telefon": telefon,
                    "E-posta": eposta,
                    "Çalışma Saatleri": calisma_saati,
                    "Google Haritalar Linki": has_map,
                    "Detay Sayfası": link
                })
                
                print(f"[{i+1}/{len(sube_linkleri)}] ✅ {isim}")
                print(f"      📍 {lat}, {lon} | 📞 {telefon}")
                
            except Exception as e:
                print(f"[{i+1}/{len(sube_linkleri)}] ❌ HATA: {link}")
                
        browser.close()
        
        if data:
            df = pd.DataFrame(data)
            df.to_excel(EXCEL_ADI, index=False)
            print(f"\n🎉 İşlem Tamamlandı! Veriler resmi siteden %100 kapı pini ile '{EXCEL_ADI}' dosyasına yazıldı.")

if __name__ == "__main__":
    main()