"""Константы хаба (ТЗ §2, §6, §10)."""

DISPATCH_NO_CANDIDATE_SEC = 3600
DEFAULT_SESSION_TTL_HOURS = 24
MIN_SESSION_TTL_HOURS = 1
MAX_SESSION_TTL_HOURS = 336  # 14 days
SESSION_TTL_SEC = DEFAULT_SESSION_TTL_HOURS * 3600
PASSWORD_RESET_TTL_SEC = 3600
MAX_UPLOAD_BYTES_CAP = 1073741824  # 1 GiB
MAX_SUMMARIZE_PAYLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a"}
COOKIE_NAME = "hub_session"
DEFAULT_TARIFF_NAME = "Default"
SUPPORTED_LOCALES = ("en", "ru", "es")
DEFAULT_LOCALE = "en"
INSTANCE_TABS = ("stats", "workers", "tariffs", "orgs", "settings", "baseSkills")
SECURITY_TABS = ("audit", "encryption")
DEFAULT_ROUTES = (
    "library/audio",
    "library/transcripts",
    "library/summaries",
    "skills",
    "org",
    "stats",
    "tasks",
    *(f"instance/{tab}" for tab in INSTANCE_TABS),
    "instance",
    *(f"security/{tab}" for tab in SECURITY_TABS),
)
DEFAULT_ROUTE = "library/audio"
LEGACY_DEFAULT_ROUTE = "library"
LEGACY_INSTANCE_ROUTE = "instance"
