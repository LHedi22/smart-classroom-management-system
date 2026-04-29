"""
Face recognition service.

When FACE_RECOGNITION_ENABLED=true (Raspberry Pi only), loads DeepFace and
performs real Facenet-based recognition.

When FACE_RECOGNITION_ENABLED=false (default, Docker/dev), all methods are
stubs: enrollment stores a zeroed 128-d placeholder vector, and the recognition
loop emits synthetic attendance events on a timer (see recognition_loop.py).
"""
import logging
import os

import numpy as np
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.db_models import FaceEncoding

logger = logging.getLogger(__name__)

_FR_ENABLED = os.getenv("FACE_RECOGNITION_ENABLED", "false").lower() == "true"

if _FR_ENABLED:
    try:
        from deepface import DeepFace  # type: ignore[import]
        import cv2  # type: ignore[import]
        _FR_AVAILABLE = True
    except ImportError:
        DeepFace = None  # type: ignore[assignment]
        cv2 = None  # type: ignore[assignment]
        _FR_AVAILABLE = False
        logger.warning(
            "FACE_RECOGNITION_ENABLED=true but deepface/cv2 not installed — stub mode active"
        )
else:
    DeepFace = None  # type: ignore[assignment]
    cv2 = None  # type: ignore[assignment]
    _FR_AVAILABLE = False
    logger.info("[FACE_STUB] Recognition stub active — set FACE_RECOGNITION_ENABLED=true on RPi")


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    return float(1.0 - np.dot(a, b) / (norm_a * norm_b))


class FaceRecognitionService:
    def __init__(self) -> None:
        # {student_id: 128-d float32 numpy array}
        self.known_encodings: dict[str, np.ndarray] = {}
        self._hog: object | None = None

        if _FR_AVAILABLE and cv2 is not None:
            self._hog = cv2.HOGDescriptor()
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    # ── Encoding management ───────────────────────────────────────────────

    async def reload_encodings(self) -> None:
        """Re-read all face encodings from PostgreSQL into memory. No-op in stub mode."""
        if not _FR_AVAILABLE:
            return

        async with AsyncSessionLocal() as session:
            rows = (await session.execute(select(FaceEncoding))).scalars().all()

        encodings: dict[str, np.ndarray] = {}
        for row in rows:
            vec = np.frombuffer(row.encoding, dtype=np.float32)
            encodings[row.student_id] = vec

        self.known_encodings = encodings
        logger.info("Loaded %d face encodings", len(encodings))

    # ── Enrollment ────────────────────────────────────────────────────────

    async def enroll_student_face(self, student_id: str, images_bytes: list[bytes]) -> dict:
        """
        Compute a mean Facenet encoding from raw image bytes.

        Stub mode: returns a zeroed 128-d placeholder so the DB row is created
        and the student can participate in mock attendance events.

        Returns:
            {"encoding": np.ndarray | None, "frames_used": int, "mode": "real"|"stub"}
        """
        if not _FR_AVAILABLE:
            return {
                "encoding": np.zeros(128, dtype=np.float32),
                "frames_used": 0,
                "mode": "stub",
            }

        encodings: list[np.ndarray] = []
        for raw in images_bytes:
            arr = np.frombuffer(raw, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)  # type: ignore[union-attr]
            if frame is None:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # type: ignore[union-attr]
            try:
                face_results = DeepFace.represent(  # type: ignore[union-attr]
                    img_path=rgb,
                    model_name="Facenet",
                    enforce_detection=True,
                    detector_backend="opencv",
                )
                if face_results:
                    enc = np.array(face_results[0]["embedding"], dtype=np.float32)
                    encodings.append(enc)
            except Exception as exc:
                logger.warning("No face detected in image — skipping: %s", exc)

        if not encodings:
            return {"encoding": None, "frames_used": 0, "mode": "real"}

        mean_encoding = np.mean(encodings, axis=0).astype(np.float32)
        return {"encoding": mean_encoding, "frames_used": len(encodings), "mode": "real"}

    # ── Face recognition ─────────────────────────────────────────────────

    def recognize_faces(self, frame: np.ndarray) -> list[dict]:
        """
        Recognize faces in a BGR OpenCV frame.

        Returns a list of dicts:
          {"student_id": str|"UNKNOWN", "confidence": float,
           "location": [top, right, bottom, left]}
        Returns [] in stub mode.
        """
        if not _FR_AVAILABLE:
            return []

        small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)  # type: ignore[union-attr]
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)  # type: ignore[union-attr]

        try:
            face_results = DeepFace.represent(  # type: ignore[union-attr]
                img_path=rgb,
                model_name="Facenet",
                enforce_detection=True,
                detector_backend="opencv",
            )
        except Exception:
            return []

        from app.config import settings

        results = []
        for face_data in face_results:
            embedding = np.array(face_data["embedding"], dtype=np.float32)
            fa = face_data.get("facial_area", {})

            student_id = "UNKNOWN"
            confidence = 0.0

            if self.known_encodings:
                ids = list(self.known_encodings.keys())
                distances = [_cosine_distance(embedding, enc) for enc in self.known_encodings.values()]
                best_idx = int(np.argmin(distances))
                best_dist = distances[best_idx]

                if best_dist < settings.face_recognition_threshold:
                    student_id = ids[best_idx]
                    confidence = round(1.0 - best_dist, 4)

            x = fa.get("x", 0) * 2
            y = fa.get("y", 0) * 2
            w = fa.get("w", 0) * 2
            h = fa.get("h", 0) * 2
            results.append({
                "student_id": student_id,
                "confidence": confidence,
                "location": [y, x + w, y + h, x],
            })

        return results

    # ── Occupancy fallback ────────────────────────────────────────────────

    def count_heads(self, frame: np.ndarray) -> int:
        """
        Use OpenCV HOG person detector as a fallback occupancy counter.
        Returns 0 in stub mode.
        """
        if not _FR_AVAILABLE or self._hog is None:
            return 0

        small = cv2.resize(frame, (640, 480)) if frame.shape[1] > 640 else frame  # type: ignore[union-attr]
        rects, _ = self._hog.detectMultiScale(  # type: ignore[union-attr]
            small,
            winStride=(8, 8),
            padding=(4, 4),
            scale=1.05,
        )
        return len(rects)


# Module-level singleton — loaded once, shared across the app
face_recognition_service = FaceRecognitionService()
