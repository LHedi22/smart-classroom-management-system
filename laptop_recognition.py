#!/usr/bin/env python3
"""
laptop_recognition.py — Host-side face recognition for Laptop Mode.

Runs on the host (not in Docker). Grabs the laptop webcam, detects faces
using DeepFace/FaceNet, matches them against enrolled student encodings
fetched from the backend API, and POSTs attendance events (present/absent)
to /api/webcam/attendance.

Usage:
    pip install -r laptop_recognition_requirements.txt
    python laptop_recognition.py

Environment variables (all optional — defaults shown):
    API_BASE        http://localhost:8000   Backend base URL
    ROOM_ID         room1                   Must match ROOM_ID in .env
    FPS             2                       Frames to process per second
    ABSENT_TIMEOUT  5                       Seconds without detection → mark absent
"""

import os
import time
import base64
import logging
import requests
import numpy as np
import cv2
from deepface import DeepFace

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

API_BASE       = os.getenv("API_BASE", "http://localhost:8000")
ROOM_ID        = os.getenv("ROOM_ID", "room1")
FPS            = float(os.getenv("FPS", "2"))
ABSENT_TIMEOUT = float(os.getenv("ABSENT_TIMEOUT", "5"))


# ── Encoding helpers ───────────────────────────────────────────────────────────

def fetch_encodings() -> list[dict]:
    """
    Fetch all enrolled student encodings from the backend.
    Returns a list of dicts: [{student_id, name, encoding: np.ndarray}, ...]
    Exits if the backend is unreachable or returns no enrollments.
    """
    url = f"{API_BASE}/api/webcam/encodings"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error("Cannot reach backend at %s: %s", url, e)
        raise SystemExit(1)

    raw = resp.json()
    if not raw:
        log.error("No enrolled students found. Enroll students first, then restart.")
        raise SystemExit(1)

    result = []
    for item in raw:
        encoding_bytes = base64.b64decode(item["encoding_b64"])
        encoding_array = np.frombuffer(encoding_bytes, dtype=np.float32).copy()
        if encoding_array.shape[0] != 128 or np.linalg.norm(encoding_array) < 1e-6:
            continue  # skip zero-vector stub placeholders
        result.append({
            "student_id": item["student_id"],
            "name":       item["name"],
            "encoding":   encoding_array,
        })

    log.info("Loaded %d enrolled student(s).", len(result))
    return result


# ── Face matching ──────────────────────────────────────────────────────────────

def match_faces(
    frame: np.ndarray,
    enrolled: list[dict],
    threshold: float = 0.6,
) -> list[dict]:
    """
    Detect all faces in `frame` and match each one against `enrolled`.

    Parameters
    ----------
    frame    : BGR image from OpenCV (numpy uint8 array, shape H×W×3)
    enrolled : list returned by fetch_encodings() —
               each item has keys: student_id (str), name (str), encoding (np.ndarray 128-d)
    threshold: cosine distance below which a match is accepted (lower = stricter)

    Returns
    -------
    List of match dicts for each face that was successfully identified:
        [{"student_id": "<uuid>", "name": "Full Name", "confidence": 0.87}, ...]
    Returns an empty list if no faces are detected or no match clears the threshold.
    """
    from scipy.spatial.distance import cosine as cosine_dist

    try:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_results = DeepFace.represent(
            img_path=rgb,
            model_name="Facenet",
            enforce_detection=False,
            detector_backend="opencv",
        )
    except Exception:
        return []

    matches: list[dict] = []
    used_students: set[str] = set()  # prevent one student matching two faces

    for face_data in face_results:
        embedding = np.array(face_data["embedding"], dtype=np.float32)

        best_id: str | None = None
        best_name: str | None = None
        best_dist = 1.0

        for item in enrolled:
            if item["student_id"] in used_students:
                continue
            dist = float(cosine_dist(embedding, item["encoding"]))
            if dist < best_dist:
                best_dist = dist
                best_id = item["student_id"]
                best_name = item["name"]

        if best_id is not None and best_dist < threshold:
            used_students.add(best_id)
            matches.append({
                "student_id": best_id,
                "name":       best_name,
                "confidence": round(1.0 - best_dist, 4),
            })

    return matches


# ── Attendance posting ─────────────────────────────────────────────────────────

def post_attendance(student_id: str, status: str, confidence: float) -> str:
    """
    POST to /api/webcam/attendance.
    Returns "recorded", "cooldown", "no_session", "skipped", or "error".
    """
    url = f"{API_BASE}/api/webcam/attendance"
    payload = {"student_id": student_id, "status": status, "confidence": confidence}
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return "recorded" if data.get("recorded") else "skipped"
        if resp.status_code == 409:
            return "cooldown"
        if resp.status_code == 404:
            return "no_session"
        log.warning("Unexpected status %d from attendance API", resp.status_code)
        return "error"
    except requests.RequestException as e:
        log.error("Failed to post attendance: %s", e)
        return "error"


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    enrolled    = fetch_encodings()
    frame_delay = 1.0 / FPS

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        log.error("Cannot open webcam (VideoCapture(0)). Is the camera in use?")
        raise SystemExit(1)

    log.info("Webcam opened. Processing at %.1f fps. Press Ctrl+C to stop.", FPS)

    # last_seen[student_id]        = monotonic timestamp of last in-frame detection
    # last_posted_status[student_id] = last status string posted to backend
    #
    # Pre-seed every enrolled student as "just timed out" so any student the camera
    # doesn't detect in the first pass is immediately marked absent. Without this,
    # students already marked present by a prior system (e.g., the backend stub loop)
    # would never appear in last_seen and would stay present indefinitely.
    last_seen: dict[str, float] = {
        item["student_id"]: time.monotonic() - ABSENT_TIMEOUT
        for item in enrolled
    }
    last_posted_status: dict[str, str] = {}

    try:
        while True:
            loop_start = time.monotonic()

            ret, frame = cap.read()
            if not ret:
                log.warning("Failed to read frame — skipping.")
                time.sleep(frame_delay)
                continue

            matches = match_faces(frame, enrolled)
            now = time.monotonic()

            # ── Mark detected students as present ──────────────────────────────
            seen_ids: set[str] = set()
            for match in matches:
                sid  = match["student_id"]
                name = match["name"]
                conf = match["confidence"]
                seen_ids.add(sid)
                last_seen[sid] = now

                if last_posted_status.get(sid) != "present":
                    result = post_attendance(sid, "present", conf)
                    if result in ("recorded", "cooldown"):
                        last_posted_status[sid] = "present"
                        if result == "recorded":
                            log.info("PRESENT  %s (conf=%.2f)", name, conf)
                    elif result == "no_session":
                        log.warning("No active session — start a session on the dashboard first.")

            # ── Mark vanished students as absent after timeout ─────────────────
            for sid, ts in list(last_seen.items()):
                if sid not in seen_ids and (now - ts) >= ABSENT_TIMEOUT:
                    if last_posted_status.get(sid) != "absent":
                        name = next((e["name"] for e in enrolled if e["student_id"] == sid), sid)
                        result = post_attendance(sid, "absent", 0.0)
                        if result in ("recorded", "cooldown", "skipped"):
                            last_posted_status[sid] = "absent"
                            if result == "recorded":
                                log.info("ABSENT   %s (timeout=%.0fs)", name, ABSENT_TIMEOUT)

            # ── Pace to target FPS ─────────────────────────────────────────────
            elapsed = time.monotonic() - loop_start
            sleep_for = frame_delay - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    except KeyboardInterrupt:
        log.info("Stopped by user.")
    finally:
        cap.release()
        log.info("Webcam released.")


if __name__ == "__main__":
    main()
