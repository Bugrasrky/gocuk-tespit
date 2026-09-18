import cv2
import numpy as np

COIN_DIAM_MM = 26.15

def detect_coin_single_click(image, click_pt):
    h, w = image.shape[:2]
    cx, cy = int(click_pt[0]), int(click_pt[1])

    # KURAL 1: Arama alanını (ROI) çok daha dar tutuyoruz ki etraftaki gölgeleri görmesin
    roi_r = int(min(h, w) * 0.12)
    roi_r = max(60, min(roi_r, 150))
    x1, y1 = max(0, cx - roi_r), max(0, cy - roi_r)
    x2, y2 = min(w, cx + roi_r), min(h, cy + roi_r)
    roi = image[y1:y2, x1:x2]
    roi_pt = (cx - x1, cy - y1)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.medianBlur(gray, 7)
    edges = cv2.Canny(blurred, 40, 150)

    # KURAL 2: maxRadius değerini çok küçülttük! Artık kaporta kavislerini çember sanamaz.
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1.0, minDist=10,
        param1=130, param2=15, minRadius=15, maxRadius=int(roi_r * 0.75)
    )

    best_circle = None

    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        candidates = []
        
        for (xc, yc, r) in circles:
            # KURAL 3: Tıkladığın yer çemberin merkezine milimetrik yakın olmalı (Tolerans %35)
            dist = np.hypot(xc - roi_pt[0], yc - roi_pt[1])
            if dist > r * 0.35:
                continue
            
            # Kenar Kapsama (Edge Coverage) Skoru
            mask = np.zeros_like(edges)
            cv2.circle(mask, (xc, yc), r, 255, thickness=2)
            overlap = cv2.bitwise_and(edges, mask)
            score = cv2.countNonZero(overlap)
            circumference = 2 * np.pi * r
            coverage = score / circumference
            
            # Çemberin en az %20'si gerçek bir kenarla eşleşiyorsa adaydır
            if coverage > 0.20:
                # KURAL 4: Sadece büyüklüğe değil, kapsama oranına (kaliteye) göre puanla
                final_score = coverage * (r ** 0.5) 
                candidates.append((final_score, r, xc, yc))
                
        if candidates:
            # Puanı en yüksek olanı (En mantıklı oturanı) al
            candidates.sort(key=lambda c: -c[0]) 
            _, best_r, best_xc, best_yc = candidates[0]
            best_circle = (best_xc, best_yc, best_r)

    if best_circle is not None:
        final_cx, final_cy, final_r = best_circle
        ppm = (final_r * 2.0) / COIN_DIAM_MM
        return True, ppm, (int(final_cx + x1), int(final_cy + y1), int(final_r))

    return False, None, None