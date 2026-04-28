"""
Face recognition service.

face_recognition (dlib-based) is an optional heavy dependency — on dev machines
without dlib compiled it will be unavailable. The service degrades gracefully:
recognize_faces() returns [] and count_heads() returns 0.
"""
import logging

import numpy as np
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.db_models import FaceEncoding

logger = logging.getLogger(__name__)

# Optional imports — not available on Windows dev machines without dlib
try:
    import face_recognition as fr  # type: ignore[import]
    _FR_AVAILABLE = True
except ImportError:
    fr = None  # type: ignore[assignment]
    _FR_AVAILABLE = False
    logger.warning("face_recognition library not available — recognition disabled")

try:
    import cv2  # type: ignore[import]
    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore[assignment]
    _CV2_AVAILABLE = False
    logger.warning("OpenCV not available — HOG detector disabled")


class FaceRecognitionService:
    def __init__(self) -> None:
        # {student_id: 128-d float64 numpy array}
        self.known_encodings: dict[str, np.ndarray] = {}
        self._hog: object | None = None

        if _CV2_AVAILABLE:
            self._hog = cv2.HOGDescriptor()
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    # ── Encoding management ───────────────────────────────────────────────

    async def reload_encodings(self) -> None:
        """Re-read all face encodings from PostgreSQL into memory."""
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(select(FaceEncoding))).scalars().all()

        encodings: dict[str, np.ndarray] = {}
        for row in rows:
            vec = np.frombuffer(row.encoding, dtype=np.float64)
            encodings[row.student_id] = vec

        self.known_encodings = encodings
        logger.info("Loaded %d face encodings", len(encodings))

    # ── Face recognition ─────────────────────────────────────────────────

    def recognize_faces(self, frame: np.ndarray) -> list[dict]:
        """
        Recognize faces in a BGR OpenCV frame.

        Returns a list of dicts:
          {"student_id": str|"UNKNOWN", "confidence": float,
           "location": [top, right, bottom, left]}
        """
        if not _FR_AVAILABLE or not _CV2_AVAILABLE:
            return []

        # Resize to 50% for speed
        small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        locations = fr.face_locations(rgb)
        if not locations:
            return []

        encodings = fr.face_encodings(rgb, locations)
        results = []

        for enc, loc in zip(encodings, locations):
            student_id = "UNKNOWN"
            confidence = 0.0

            if self.known_encodings:
                ids = list(self.known_encodings.keys())
                known_vecs = list(self.known_encodings.values())
                distances = fr.face_distance(known_vecs, enc)
                best_idx = int(np.argmin(distances))
                best_dist = float(distances[best_idx])

                if best_dist < settings.face_recognition_threshold:
                    student_id = ids[best_idx]
                    # Convert distance to a 0–1 confidence score
                    confidence = round(1.0 - best_dist, 4)

            # Scale locations back to original frame size
            top, right, bottom, left = loc
            results.append({
                "student_id": student_id,
                "confidence": confidence,
                "location": [top * 2, right * 2, bottom * 2, left * 2],
            })

        return results

    # ── Occupancy fallback ────────────────────────────────────────────────

    def count_heads(self, frame: np.ndarray) -> int:
        """
        Use OpenCV HOG person detector as a fallback occupancy counter.
        Returns integer count of detected people in the frame.
        """
        if not _CV2_AVAILABLE or self._hog is None:
            return 0

        # HOG works best on smaller frames
        small = cv2.resize(frame, (640, 480)) if frame.shape[1] > 640 else frame
        rects, _ = self._hog.detectMultiScale(
            small,
            winStride=(8, 8),
            padding=(4, 4),
            scale=1.05,
        )
        return len(rects)


# Module-level singleton — loaded once, shared across the app
face_recognition_service = FaceRecognitionService()
