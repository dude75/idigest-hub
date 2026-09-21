"""Константы хаба (ТЗ §2, §6, §10)."""

DISPATCH_NO_CANDIDATE_SEC = 3600
DEFAULT_SESSION_TTL_HOURS = 24
MIN_SESSION_TTL_HOURS = 1
MAX_SESSION_TTL_HOURS = 336  # 14 days
SESSION_TTL_SEC = DEFAULT_SESSION_TTL_HOURS * 3600
PASSWORD_RESET_TTL_SEC = 3600
PASSWORD_RESET_COOLDOWN_SEC = 900  # min interval between reset emails to the same user
PUBLIC_LINK_UNLOCK_TTL_SEC = 1800
PUBLIC_LINK_PIN_MIN_LEN = 4
PUBLIC_LINK_PIN_MAX_LEN = 6
PUBLIC_LINK_UNLOCK_COOKIE = "hub_plu"
MFA_CHALLENGE_TTL_SEC = 300
MFA_RECOVERY_CODE_COUNT = 8
MFA_TOTP_ISSUER = "iDigest Hub"
MAX_UPLOAD_BYTES_CAP = 1073741824  # 1 GiB
MAX_SUMMARIZE_PAYLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a"}
# Video uploads: extract audio to MP3 on ingest (v1 hint list + v2 extra containers).
ALLOWED_VIDEO_SUFFIXES = {
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".3gp",
    ".wmv",
    ".asf",
    ".mpeg",
    ".mpg",
    ".flv",
    ".ogv",
}
ALLOWED_UPLOAD_SUFFIXES = ALLOWED_AUDIO_SUFFIXES | ALLOWED_VIDEO_SUFFIXES
DEFAULT_VIDEO_EXTRACT_FFMPEG_TIMEOUT_SEC = 3600
COOKIE_NAME = "hub_session"
CSRF_COOKIE_NAME = "hub_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
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
