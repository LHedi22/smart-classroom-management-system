#!/usr/bin/env python3
"""
Enroll demo students by uploading photos from enrollment_photos/ to the backend.

Runs on the HOST (not in Docker). Requires the backend to be running.

Usage:
    python enroll_demo_students.py

Environment variables (optional):
    API_BASE   http://localhost:8000
"""
import os
import sys
import requests
from pathlib import Path

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
    """Resolve institutional student_id (e.g. STU-DEMO-001) → DB UUID."""
    try:
        resp = requests.get(f"{API_BASE}/api/students", timeout=10)
        resp.raise_for_status()
        for s in resp.json():
            if s["student_id"] == student_id:
                return s["id"]
    except requests.RequestException as e:
        print(f"  ✗ Cannot reach backend: {e}", file=sys.stderr)
    return None


def enroll(uuid: str, photo_path: Path) -> bool:
    """POST photo bytes to /api/students/{uuid}/enroll-face. Returns True on success."""
    mime = "image/png" if photo_path.suffix.lower() == ".png" else "image/jpeg"
    with open(photo_path, "rb") as f:
        resp = requests.post(
            f"{API_BASE}/api/students/{uuid}/enroll-face",
            files=[("images", (photo_path.name, f, mime))],
            timeout=60,
        )
    if resp.status_code in (200, 201):
        return True
    print(f"  ✗ API error {resp.status_code}: {resp.text[:200]}")
    return False


def main() -> None:
    if not PHOTOS_DIR.exists():
        print(f"✗ Directory '{PHOTOS_DIR}/' not found.")
        print("  Create it and place one photo per student inside, then re-run.")
        sys.exit(1)

    print(f"Enrolling demo students from {PHOTOS_DIR}/\n")
    ok = skipped = 0

    for student_id, name in STUDENTS:
        # Accept .jpg, .jpeg, or .png
        photo_path: Path | None = None
        for ext in (".jpg", ".jpeg", ".png"):
            candidate = PHOTOS_DIR / f"{student_id}{ext}"
            if candidate.exists():
                photo_path = candidate
                break

        if photo_path is None:
            print(f"✗ Photo not found: {student_id} — skipping")
            skipped += 1
            continue

        db_uuid = get_student_uuid(student_id)
        if db_uuid is None:
            print(f"✗ Student {student_id} not in DB — run seed_laptop_test.py first")
            skipped += 1
            continue

        if enroll(db_uuid, photo_path):
            print(f"✓ Enrolled: {name} ({student_id})")
            ok += 1
        else:
            skipped += 1

    print(f"\nDone. {ok} enrolled, {skipped} skipped.")
    if skipped > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
