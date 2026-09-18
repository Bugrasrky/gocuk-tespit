import torch
import cv2
import numpy as np
import os
from ultralytics import FastSAM
from paths import resource_path

CARD_LONG_MM = 85.60
CARD_SHORT_MM = 53.98
CARD_RATIO = CARD_LONG_MM / CARD_SHORT_MM
MIN_DIM_THRESHOLD = 40  # İki fonksiyonda da tutarlılık sağlandı

_fastsam_model = None

def get_model():
    global _fastsam_model
    if _fastsam_model is None:
        model_path = resource_path("FastSAM-s.pt")
        if not os.path.exists(model_path):
            print("\n[UYARI] FastSAM-s.pt dosyası diskte bulunamadı, indiriliyor...")
        print("\n[AI] FastSAM modeli yükleniyor...")
        _fastsam_model = FastSAM(model_path)
    return _fastsam_model

def auto_detect_card(image):
    try:
        model = get_model()
        h, w = image.shape[:2]
        img_area = h * w

        results = model(image, device="cpu", retina_masks=True, imgsz=640, conf=0.25, iou=0.7, verbose=False)
        if not results or results[0].masks is None:
            return False, None, None

        masks_data = results[0].masks.data.cpu().numpy()
        candidates = []

        for i in range(len(masks_data)):
            raw_m = (masks_data[i] > 0).astype(np.uint8)
            if raw_m.shape != (h, w):
                raw_m = cv2.resize(raw_m, (w, h), interpolation=cv2.INTER_NEAREST)

            contours, _ = cv2.findContours(raw_m * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue

            cnt = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(cnt)
            
            if area < (img_area * 0.015) or area > (img_area * 0.15):
                continue

            rect = cv2.minAreaRect(cnt)
            dim_max, dim_min = max(rect[1]), min(rect[1])
            
            if dim_min < MIN_DIM_THRESHOLD:
                continue
            
            if (area / (dim_max * dim_min)) < 0.85:
                continue

            score = abs((dim_max / dim_min) - CARD_RATIO)
            if score < 0.25:
                candidates.append((score, rect))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            best_rect = candidates[0][1]
            dim_max, dim_min = max(best_rect[1]), min(best_rect[1])
            ppm = ((dim_max / CARD_LONG_MM) + (dim_min / CARD_SHORT_MM)) / 2.0
            print(f"[OTOMATİK KİLİTLENDİ] Kart yakalandı! PPM: {ppm:.3f}")
            return True, ppm, cv2.boxPoints(best_rect)

        return False, None, None

    except Exception as e:
        print(f"[HATA] auto_detect_card başarısız: {e}")
        return False, None, None

def detect_card_single_click(image, click_pt):
    try:
        model = get_model()
        cx, cy = int(click_pt[0]), int(click_pt[1])
        
        print(f"[AI] {cx},{cy} koordinatına nokta atışı (Point Prompt) yapılıyor...")
        # SADECE TIKLANAN NOKTAYA BAKAR - 10X DAHA HIZLI
        results = model(image, device="cpu", points=[[cx, cy]], labels=[1], retina_masks=True, imgsz=640, verbose=False)
        
        if not results or results[0].masks is None:
            print("[UYARI] Tıklanan noktada nesne bulunamadı.")
            return False, None, None

        raw_m = results[0].masks.data[0].cpu().numpy()
        raw_m = (raw_m > 0).astype(np.uint8)
        
        h, w = image.shape[:2]
        if raw_m.shape != (h, w):
            raw_m = cv2.resize(raw_m, (w, h), interpolation=cv2.INTER_NEAREST)

        contours, _ = cv2.findContours(raw_m * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            cnt = max(contours, key=cv2.contourArea)
            if cv2.contourArea(cnt) > 2000:
                rect = cv2.minAreaRect(cnt)
                dim_max, dim_min = max(rect[1]), min(rect[1])
                
                if dim_min > MIN_DIM_THRESHOLD:
                    score = abs((dim_max / dim_min) - CARD_RATIO)
                    if score < 0.35:
                        ppm = ((dim_max / CARD_LONG_MM) + (dim_min / CARD_SHORT_MM)) / 2.0
                        return True, ppm, cv2.boxPoints(rect)
                    else:
                        print(f"[UYARI] Bulunan nesne kart oranlarına uymuyor. Oran: {dim_max/dim_min:.2f}")

        return False, None, None

    except Exception as e:
        print(f"[HATA] detect_card_single_click başarısız: {e}")
        return False, None, None