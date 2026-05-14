from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://smartcam:smartcam@localhost:5432/smartclassroom"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # MQTT
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883

    # Moodle
    moodle_url: str = "http://localhost:8080"
    moodle_token: str = ""

    # Application
    secret_key: str = "changeme"
    room_id: str = "room1"
    mock_mode: bool = False
    face_recognition_enabled: bool = False
    laptop_mode: bool = False  # Webcam runs as standalone host script; ESP32 → laptop MQTT broker

    # Auth
    access_token_expire_minutes: int = 480  # 8 hours
    require_auth: bool = False  # set True in production to reject unauthenticated requests

    # Auto-control thresholds
    temp_ac_on_threshold: float = 28.0
    temp_ac_off_threshold: float = 22.0
    air_quality_alert_threshold: int = 500
    face_recognition_threshold: float = 0.40
    recognition_fps: int = 2

    # Ollama LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi3:mini"
    ai_summary_cache_ttl: int = 600

    # At-risk detection
    at_risk_threshold: float = 0.70

    # Attendance forecasting
    forecast_window: int = 8  # FORECAST_WINDOW — number of past sessions to include in trend

    # Attendance cycle (snapshot-per-cycle model)
    attendance_cycle_duration: int = 60  # seconds per scan→evaluate cycle


settings = Settings()
