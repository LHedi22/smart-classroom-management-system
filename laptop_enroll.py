#!/usr/bin/env python3
"""
laptop_enroll.py — Host-side enrollment for Laptop Mode.

Computes real FaceNet embeddings locally (where DeepFace is installed) and
pushes them to the backend via POST /api/webcam/enroll — bypassing the Docker
stub that would otherwise store zero-vector placeholders.

Run this INSTEAD of enroll_demo_students.py when using laptop mode.

Usage:
    python laptop_enroll.py

Environment variables (optional):
    API_BASE   http://localhost:8000
"""
import os
import sys
import base64
import logging
import requests
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

API_BASE   = os.getenv("API_BASE", "http://localhost:8000")
PHOTOS_DIR = Path("enrollment_photos")

STUDENTS = [
    ("STU-DEMO-001", "Mohamed Hedi Ben Jemaa"),
    ("STU-DEMO-002", "Ahmed Amine Jallouli"),
    ("STU-DEMO-003", "Abdelhamid Ouertani"),
    ("STU-DEMO-004", "Ali Saadaoui"),
    ("STU-DEMO-005", "Iyed Dai"),
    ("STU-DEMO-006", "Donia Driss"),
    ("STU-DEMO-007", "Lamia Bouaziz"),
]


def get_student_uuid(student_id: str) -> str | None:
    """Resolve institutional student_id → DB UUID."""
    try:
        resp = requests.get(f"{API_BASE}/api/students", timeout=10)
        resp.raise_for_status()
        for s in resp.json():
            if s["student_id"] == student_id:
                return s["id"]
    except requests.RequestException as e:
        log.error("Cannot reach backend: %s", e)
    return None


def compute_embedding(photo_path: Path) -> np.ndarray | None:
    """Run DeepFace FaceNet on a photo and return a 128-d float32 vector."""
    from deepface import DeepFace
    try:
        result = DeepFace.represent(
            img_path=str(photo_path),
            model_name="Facenet",
            enforce_detection=False,
            detector_backend="opencv",
        )
        if not result:
            return None
        arr = np.array(result[0]["embedding"], dtype=np.float32)
        if arr.shape[0] != 128 or np.linalg.norm(arr) < 1e-6:
            return None
        return arr
    except Exception as e:
        log.error("DeepFace error on %s: %s", photo_path.name, e)
        return None


def push_encoding(db_uuid: str, encoding: np.ndarray) -> bool:
    """POST the pre-computed embedding to /api/webcam/enroll."""
    encoding_b64 = base64.b64encode(encoding.tobytes()).decode()
    try:
        resp = requests.post(
            f"{API_BASE}/api/webcam/enroll",
            json={"student_id": db_uuid, "encoding_b64": encoding_b64},
            timeout=15,
        )
        return resp.status_code == 200
    except requests.RequestException as e:
        log.error("Failed to push encoding: %s", e)
        return False


def main() -> None:
    if not PHOTOS_DIR.exists():
        print(f"✗ Directory '{PHOTOS_DIR}/' not found.")
        print("  Create it and place one photo per student (STU-DEMO-001.jpg, etc.), then re-run.")
        sys.exit(1)

    print(f"Laptop enrollment — computing FaceNet embeddings from {PHOTOS_DIR}/\n")
    ok = skipped = 0

    for student_id, name in STUDENTS:
        photo_path: Path | None = None
        for ext in (".jpg", ".jpeg", ".png"):
            candidate = PHOTOS_DIR / f"{student_id}{ext}"
            if candidate.exists():
                photo_path = candidate
                break

        if photo_path is None:
            print(f"  SKIP Photo not found: {student_id}")
            skipped += 1
            continue

        db_uuid = get_student_uuid(student_id)
        if db_uuid is None:
            print(f"  SKIP Student {student_id} not in DB — run seed_laptop_test.py first")
            skipped += 1
            continue

        print(f"  Computing embedding for {name} ...", end=" ", flush=True)
        embedding = compute_embedding(photo_path)
        if embedding is None:
            print("FAIL  No usable face detected in photo")
            skipped += 1
            continue

        if push_encoding(db_uuid, embedding):
            print(f"OK  (norm={np.linalg.norm(embedding):.2f})")
            ok += 1
        else:
            print("FAIL  Store failed")
            skipped += 1

    print(f"\nDone. {ok}/{len(STUDENTS)} enrolled, {skipped} skipped.")
    if ok > 0:
        print("\nNow run: python laptop_recognition.py")
    if skipped > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
