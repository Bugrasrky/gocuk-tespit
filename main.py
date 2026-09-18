import torch
import cv2
import numpy as np
import sys
import tkinter as tk
from tkinter import filedialog, Label, Button, Checkbutton, BooleanVar, Frame, Toplevel
from history_viewer import show_history_window

from card_detector import detect_card_single_click, auto_detect_card
from coin_detector import detect_coin_single_click
from depth_estimator import DamageEstimator
from service_locator import show_nearest_services_window
from db_manager import init_db, save_report

# Program başlar başlamaz veritabanını kontrol et/oluştur
init_db()

estimator = DamageEstimator("hasar_derinlik_matrisi.xlsx")

# ---- TEK VE KALICI TKINTER KÖKÜ (Gizli Tutulur) ----
tk_root = tk.Tk()
tk_root.withdraw()


def select_image_file():
    path = filedialog.askopenfilename(
        parent=tk_root,
        title="Hasarlı Araç Fotoğrafını Seçin",
        filetypes=[("Görseller", "*.jpg *.jpeg *.png *.webp *.bmp")]
    )
    return path


def select_reference_object():
    win = Toplevel(tk_root)
    win.title("Referans Nesne")
    win.attributes("-topmost", True)
    win.geometry("380x180")
    win.resizable(False, False)

    selected = {"type": "CARD", "name": "Kredi Kartı"}

    def set_choice(t, n):
        selected["type"], selected["name"] = t, n
        win.destroy()

    Label(win, text="Referans Nesneyi Seçin:", font=("Arial", 11, "bold"), pady=12).pack()
    Button(win, text="💳 Kredi Kartı (Otomatik Sıfır Tık)", font=("Arial", 10, "bold"), width=38, pady=6, bg="#e2e8f0",
           command=lambda: set_choice("CARD", "Kredi Kartı")).pack(pady=4)
    Button(win, text="🪙 1 TL Madeni Para", font=("Arial", 10), width=38, pady=6, bg="#f1f5f9",
           command=lambda: set_choice("COIN", "1 TL")).pack(pady=4)

    win.wait_window()
    return selected["type"], selected["name"]


def prompt_damage_and_paint():
    win = Toplevel(tk_root)
    win.title("Hasar Parametreleri")
    win.attributes("-topmost", True)
    win.geometry("440x440")
    win.resizable(False, False)

    result = {"id": "OTOPARK", "paint_damaged": False}
    Label(win, text="Hasar ve Boya Durumu", font=("Arial", 12, "bold"), pady=8).pack()

    paint_frame = Frame(win, bg="#fee2e2", padx=10, pady=8, highlightbackground="#ef4444", highlightthickness=1)
    paint_frame.pack(fill="x", padx=15, pady=5)
    paint_var = BooleanVar(win, value=False)
    Checkbutton(paint_frame, text="⚠️ Boyada çatlak/derin çizik var (+Fırın Boya Masrafı)",
                variable=paint_var, font=("Arial", 9, "bold"), fg="#991b1b", bg="#fee2e2").pack(anchor="w")

    Label(win, text="Göçük Senaryosu:", font=("Arial", 10, "bold"), pady=8).pack()

    def set_res(sid):
        result["id"] = sid
        result["paint_damaged"] = paint_var.get()
        win.destroy()

    for sid, sname in estimator.get_scenario_list():
        Button(win, text=sname, font=("Arial", 9), width=42, pady=4,
               command=lambda s=sid: set_res(s)).pack(pady=2)

    win.wait_window()
    return result["id"], result["paint_damaged"]


# ---- Başlatma ----
IMAGE_PATH = select_image_file()
if not IMAGE_PATH:
    tk_root.destroy()
    sys.exit()

image = cv2.imread(IMAGE_PATH)
orig_h, orig_w = image.shape[:2]
REF_TYPE, REF_NAME = select_reference_object()

# Pencere Boyutları
WIN_W, WIN_H = 1000, int(1000 * (orig_h / orig_w))
if WIN_H > 750:
    WIN_H = 750
    WIN_W = int(750 * (orig_w / orig_h))

# Zoom & Pan Değişkenleri
zoom_level = 1.0
view_center = [orig_w / 2.0, orig_h / 2.0]
is_panning = False
pan_start = (0, 0)

state = "CALIBRATE"
input_points = []
ppm = None
detected_shape = None
result_shape_data = None
result_analysis = None

# Sıfır Tık Otomatik Arama
if REF_TYPE == "CARD":
    print("\n[AI] Kart taranıyor...")
    ok, auto_ppm, auto_box = auto_detect_card(image)
    if ok:
        ppm = auto_ppm
        detected_shape = ("CARD", auto_box)
        state = "CONFIRM_SHAPE"
        print("[BİLGİ] Kart bulundu! Lütfen ekrandan onaylayın.\n")


def get_viewport_rect():
    vw = orig_w / zoom_level
    vh = orig_h / zoom_level
    vx = np.clip(view_center[0] - vw / 2.0, 0, max(0, orig_w - vw))
    vy = np.clip(view_center[1] - vh / 2.0, 0, max(0, orig_h - vh))
    return int(vx), int(vy), int(vw), int(vh)


def screen_to_orig(sx, sy):
    vx, vy, vw, vh = get_viewport_rect()
    ox = vx + (sx / WIN_W) * vw
    oy = vy + (sy / WIN_H) * vh
    return float(ox), float(oy)


def orig_to_screen(ox, oy):
    vx, vy, vw, vh = get_viewport_rect()
    sx = int(((ox - vx) / vw) * WIN_W)
    sy = int(((oy - vy) / vh) * WIN_H)
    return sx, sy


def redraw():
    global canvas
    vx, vy, vw, vh = get_viewport_rect()

    crop = image[vy:vy + vh, vx:vx + vw]
    canvas = cv2.resize(crop, (WIN_W, WIN_H), interpolation=cv2.INTER_LINEAR)

    # 1. Referans Çerçevesi
    if detected_shape is not None:
        stype, sdata = detected_shape
        if stype == "CARD":
            pts_screen = np.array([orig_to_screen(p[0], p[1]) for p in sdata], dtype=np.int32)
            cv2.polylines(canvas, [pts_screen], True, (0, 255, 0), 2)
            cv2.putText(canvas, f"{REF_NAME} (Kilit)", (pts_screen[0][0], max(20, pts_screen[0][1] - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        elif stype == "COIN":
            cx, cy, r = sdata
            scx, scy = orig_to_screen(cx, cy)
            sr = int(r * (WIN_W / vw))
            cv2.circle(canvas, (scx, scy), sr, (0, 255, 0), 2)

    # 2. Göçük Noktaları
    screen_pts = [orig_to_screen(p[0], p[1]) for p in input_points]
    for idx, p in enumerate(screen_pts):
        cv2.circle(canvas, p, 4, (0, 0, 255), -1)
        cv2.putText(canvas, str(idx + 1), (p[0] + 5, p[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)

    if len(screen_pts) > 1 and state == "MEASURE":
        cv2.polylines(canvas, [np.array(screen_pts)], False, (0, 165, 255), 1)

    # 3. Sonuç Poligonu
    if result_shape_data is not None:
        box_orig, length_cm, width_cm, area_cm2, hull_orig = result_shape_data
        poly_s = np.array([orig_to_screen(p[0], p[1]) for p in hull_orig], dtype=np.int32)
        box_s = np.array([orig_to_screen(p[0], p[1]) for p in box_orig], dtype=np.int32)
        cv2.polylines(canvas, [poly_s], True, (0, 255, 255), 2)
        cv2.polylines(canvas, [box_s], True, (255, 100, 0), 2)

    # 4. Bilgi ve Rapor Kartı
    if result_analysis is not None:
        ra = result_analysis
        overlay = canvas.copy()
        card_h = 135 if ra["paint_damaged"] else 120
        cv2.rectangle(overlay, (10, WIN_H - card_h), (480, WIN_H - 10), (15, 23, 42), -1)
        cv2.addWeighted(overlay, 0.82, canvas, 0.18, 0, canvas)

        cv2.putText(canvas, f"Hasar: {ra['scenario_name']}", (20, WIN_H - card_h + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
        cv2.putText(canvas, f"Boyut: {result_shape_data[1]:.1f} x {result_shape_data[2]:.1f} cm | Alan: {result_shape_data[3]:.1f} cm2", (20, WIN_H - card_h + 42), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 1)
        cv2.putText(canvas, f"Derinlik: {ra['depth_min_mm']:.1f}-{ra['depth_max_mm']:.1f} mm ({ra['severity']})", (20, WIN_H - card_h + 62), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (134, 239, 172), 1)
        ptxt = f"Boya: HASARLI (+{ra['paint_cost_added']:,} TL)" if ra["paint_damaged"] else "Boya: Saglam (Boyasiz PDR)"
        cv2.putText(canvas, ptxt, (20, WIN_H - card_h + 82), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (100, 100, 255) if ra["paint_damaged"] else (200, 200, 200), 1)
        cv2.putText(canvas, f"Tahmini Masraf: {ra['cost_min']:,} - {ra['cost_max']:,} TL", (20, WIN_H - card_h + 107), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (56, 189, 248), 2)

    # Üst Bilgi Barı
    zoom_txt = f"Zoom: {zoom_level:.1f}x (Tekerlek: Zoom, Sag Tik: Surukle, 'z': Sifirla)"
    if state == "CALIBRATE":
        title = f"[MANUEL] {REF_NAME} uzerine tiklayin | {zoom_txt}"
    elif state == "CONFIRM_SHAPE":
        title = f"Kart/Para dogru mu? ONAY: ENTER | YANLISSA: Gercek objeye TEK TIKLA"
    elif state == "MEASURE":
        title = f"Gocuk cevresini secin ({len(input_points)}).[U]: Son Noktayi Geri Al. Bitir: ENTER | {zoom_txt}"
    else:
        title = f"Analiz Bitti | 's': RS Servisleri | Gecmis: 'h' | 'r': Sifirla | {zoom_txt}"

    cv2.putText(canvas, title, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)

    cv2.putText(canvas, title, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1)


def mouse_events(event, x, y, flags, param):
    global zoom_level, view_center, is_panning, pan_start, input_points, ppm, state, detected_shape

    if event == cv2.EVENT_MOUSEWHEEL:
        ox, oy = screen_to_orig(x, y)
        if flags > 0:
            zoom_level = min(zoom_level * 1.25, 8.0)
        else:
            zoom_level = max(zoom_level / 1.25, 1.0)

        view_center[0] = ox - (x / WIN_W - 0.5) * (orig_w / zoom_level)
        view_center[1] = oy - (y / WIN_H - 0.5) * (orig_h / zoom_level)
        redraw()

    elif event == cv2.EVENT_RBUTTONDOWN:
        is_panning = True
        pan_start = (x, y)

    elif event == cv2.EVENT_MOUSEMOVE and is_panning:
        dx = x - pan_start[0]
        dy = y - pan_start[1]
        pan_start = (x, y)
        vx, vy, vw, vh = get_viewport_rect()
        view_center[0] -= dx * (vw / WIN_W)
        view_center[1] -= dy * (vh / WIN_H)
        redraw()

    elif event == cv2.EVENT_RBUTTONUP:
        is_panning = False

    elif event == cv2.EVENT_LBUTTONDOWN:
        orig_pt = screen_to_orig(x, y)

        # Hem CALIBRATE hem de CONFIRM_SHAPE durumunda tıklamaya izin ver!
        if state in ["CALIBRATE", "CONFIRM_SHAPE"]:
            if REF_TYPE == "CARD":
                ok, calculated_ppm, box_pts = detect_card_single_click(image, orig_pt)
                if ok:
                    ppm = calculated_ppm
                    detected_shape = ("CARD", box_pts)
                    state = "CONFIRM_SHAPE" # Seçtikten sonra yine onay bekle
            else:
                ok, calculated_ppm, circle_data = detect_coin_single_click(image, orig_pt)
                if ok:
                    ppm = calculated_ppm
                    detected_shape = ("COIN", circle_data)
                    state = "CONFIRM_SHAPE" # Seçtikten sonra yine onay bekle
            redraw()

        elif state == "MEASURE":
            input_points.append(orig_pt)
            redraw()


def finish_measurement():
    global state, result_shape_data, result_analysis
    if len(input_points) < 3:
        return

    orig_pts = np.array(input_points, dtype=np.float32)
    rect = cv2.minAreaRect(orig_pts)
    box_orig = cv2.boxPoints(rect)
    dim1, dim2 = rect[1]
    length_cm = (max(dim1, dim2) / ppm) / 10.0
    width_cm = (min(dim1, dim2) / ppm) / 10.0

    hull_orig = cv2.convexHull(orig_pts.astype(np.int32))
    area_cm2 = cv2.contourArea(hull_orig) / ((ppm * 10.0) ** 2)

    result_shape_data = (box_orig, length_cm, width_cm, area_cm2, hull_orig.reshape(-1, 2))

    sid, paint_damaged = prompt_damage_and_paint()
    result_analysis = estimator.estimate(length_cm, width_cm, area_cm2, sid, paint_damaged)

    ra = result_analysis
    boyut_str = f"{length_cm:.1f}x{width_cm:.1f}"
    derinlik_str = f"{ra['depth_min_mm']:.1f}-{ra['depth_max_mm']:.1f}"
    fiyat_str = f"{ra['cost_min']} - {ra['cost_max']} TL"
    boya_str = "Hasarlı (+Fırın)" if ra["paint_damaged"] else "Sağlam (Boyasız)"
    
    save_report(ra['scenario_name'], boyut_str, derinlik_str, fiyat_str, boya_str)

    state = "DONE"
    redraw()
    
    # DİKKAT: Burada OpenCV'yi kapatmıyor ve haritaya yönlendirmiyoruz.
    # Kullanıcı ekranda oluşan raporu ve fiyatı okuyacak. 
    # Haritaya gitmek isterse klavyeden 's' (Servis) tuşuna basacak.

def reset():
    global input_points, ppm, state, result_shape_data, result_analysis, detected_shape, zoom_level, view_center
    input_points = []
    ppm = None
    result_shape_data = None
    result_analysis = None
    detected_shape = None
    zoom_level = 1.0
    view_center = [orig_w / 2.0, orig_h / 2.0]
    state = "CALIBRATE"
    redraw()


cv2.namedWindow("Olcum Ekrani")
cv2.setMouseCallback("Olcum Ekrani", mouse_events)
redraw()

while True:
    cv2.imshow("Olcum Ekrani", canvas)
    key = cv2.waitKey(1) & 0xFF

    if key in [ord('f'), 13, 32]: # 'f', Enter veya Boşluk
        if state == "CONFIRM_SHAPE":
            state = "MEASURE" # Şekli onayladık, artık göçük seçebiliriz
            redraw()
        elif state == "MEASURE":
            finish_measurement()
    elif key == ord('u') and len(input_points) > 0 and state == "MEASURE":
        input_points.pop()
        redraw()

    elif key in [ord('z'), ord('0')]:
        zoom_level = 1.0
        view_center = [orig_w / 2.0, orig_h / 2.0]
        redraw()
    elif key == ord('h'):
        show_history_window(parent=tk_root)
    elif key == ord('s') and state == "DONE":
        show_nearest_services_window(parent=tk_root)
    elif key == ord('r'):
        reset()
    elif key in [27, ord('q')]: # ESC veya Q
        break

cv2.destroyAllWindows()
tk_root.destroy()