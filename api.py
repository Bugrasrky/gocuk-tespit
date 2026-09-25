import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from card_detector import auto_detect_card, detect_card_single_click
from coin_detector import detect_coin_single_click
from depth_estimator import DamageEstimator

app = FastAPI(title="Gocuk Tespit Web API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The Excel matrix is loaded once. FastSAM is cached by card_detector.get_model().
estimator = DamageEstimator("hasar_derinlik_matrisi.xlsx")
BASE_DIR = Path(__file__).resolve().parent


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(BASE_DIR / "index.html")


def decode_image(file_bytes: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(file_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Gecerli bir goruntu dosyasi gonderilmedi.")
    return image


def box_to_list(box: Any) -> list[list[float]]:
    if box is None:
        return []
    return np.asarray(box, dtype=float).tolist()


def error_response(message: str) -> dict[str, str]:
    return {"ok": False, "error": message}


@app.post("/oto-kart-bul")
async def oto_kart_bul(
    file: UploadFile = File(...),
    referans_tipi: str = Form("CARD"),
):
    try:
        image = decode_image(await file.read())
        if referans_tipi.upper() == "COIN":
            return {
                "ok": True,
                "kart_ok": False,
                "referans_tipi": "COIN",
                "ppm": None,
                "kart_box": [],
                "image_size": {"width": image.shape[1], "height": image.shape[0]},
                "manual_required": True,
            }
        found, ppm, card_box = auto_detect_card(image)
        height, width = image.shape[:2]
        return {
            "ok": True,
            "referans_tipi": "CARD",
            "kart_ok": bool(found),
            "ppm": float(ppm) if ppm is not None else None,
            "kart_box": box_to_list(card_box),
            "image_size": {"width": width, "height": height},
        }
    except HTTPException:
        raise
    except Exception as exc:
        return error_response(f"Otomatik kart aramasi basarisiz: {exc}")


@app.post("/manuel-kart-bul")
async def manuel_kart_bul(
    file: UploadFile = File(...),
    x: float = Form(...),
    y: float = Form(...),
    referans_tipi: str = Form("CARD"),
):
    if not math.isfinite(x) or not math.isfinite(y):
        raise HTTPException(status_code=422, detail="Kart tiklama koordinatlari gecersiz.")

    try:
        image = decode_image(await file.read())
        height, width = image.shape[:2]
        if not (0 <= x < width and 0 <= y < height):
            raise HTTPException(status_code=422, detail="Kart koordinatlari goruntu disinda.")
        if referans_tipi.upper() == "COIN":
            found, ppm, card_box = detect_coin_single_click(image, (x, y))
        else:
            found, ppm, card_box = detect_card_single_click(image, (x, y))
        return {
            "ok": True,
            "referans_tipi": referans_tipi.upper(),
            "kart_ok": bool(found),
            "ppm": float(ppm) if ppm is not None else None,
            "kart_box": box_to_list(card_box),
        }
    except HTTPException:
        raise
    except Exception as exc:
        return error_response(f"Manuel kart aramasi basarisiz: {exc}")


@app.get("/senaryolar")
async def senaryolar():
    return {
        "ok": True,
        "senaryolar": [
            {"id": scenario_id, "name": name}
            for scenario_id, name in estimator.get_scenario_list()
        ],
    }


@app.post("/hasar-hesapla")
async def hasar_hesapla(
    noktalar: str = Form(...),
    ppm: float = Form(...),
    senaryo_id: str = Form("OTOPARK"),
    boya_hasarli: bool = Form(False),
):
    if not math.isfinite(ppm) or ppm <= 0:
        raise HTTPException(status_code=422, detail="Gecerli bir ppm degeri gerekli.")

    try:
        points = json.loads(noktalar)
        if not isinstance(points, list) or len(points) < 3:
            raise HTTPException(status_code=422, detail="Hesaplama icin en az 3 nokta gereklidir.")
        if any(
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in point)
            for point in points
        ):
            raise HTTPException(status_code=422, detail="Noktalar [x, y] formatinda olmalidir.")

        original_points = np.asarray(points, dtype=np.float32)
        rectangle = cv2.minAreaRect(original_points)
        dim1, dim2 = rectangle[1]
        if min(dim1, dim2) <= 0:
            raise HTTPException(status_code=422, detail="Gecerli bir hasar alani olusmadi.")

        length_cm = max(dim1, dim2) / ppm / 10.0
        width_cm = min(dim1, dim2) / ppm / 10.0
        hull = cv2.convexHull(original_points.astype(np.int32))
        area_cm2 = cv2.contourArea(hull) / ((ppm * 10.0) ** 2)
        if senaryo_id not in estimator.scenarios:
            raise HTTPException(status_code=422, detail="Gecerli bir hasar senaryosu secilmedi.")
        report = estimator.estimate(length_cm, width_cm, area_cm2, senaryo_id, boya_hasarli)
        return {
            "ok": True,
            "durum": "basarili",
            "hesaplama": {
                "boyutlar_cm": f"{length_cm:.1f} x {width_cm:.1f}",
                "uzunluk_cm": round(length_cm, 1),
                "genislik_cm": round(width_cm, 1),
                "alan_cm2": round(area_cm2, 1),
            },
            "rapor": report,
        }
    except HTTPException:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Nokta verisi okunamadi: {exc}") from exc
    except Exception as exc:
        return error_response(f"Hasar hesaplamasi basarisiz: {exc}")


if __name__ == "__main__":
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)