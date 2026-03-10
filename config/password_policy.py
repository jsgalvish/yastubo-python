import os

PASSWORD_POLICY: dict = {
    "min": int(os.getenv("PASSWORD_MIN", 8)),
    "max": int(os.getenv("PASSWORD_MAX", 128)),
    "require": {
        "uppercase":  os.getenv("PASSWORD_REQUIRE_UPPERCASE",  "true").lower() == "true",
        "lowercase":  os.getenv("PASSWORD_REQUIRE_LOWERCASE",  "true").lower() == "true",
        "numbers":    os.getenv("PASSWORD_REQUIRE_NUMBERS",    "true").lower() == "true",
        "symbols":    os.getenv("PASSWORD_REQUIRE_SYMBOLS",    "true").lower() == "true",
        "mixed_case": os.getenv("PASSWORD_REQUIRE_MIXED_CASE", "true").lower() == "true",
    },
    "history": {
        "enabled":        True,
        "remember_last":  5,
        "retention_days": 365,
    },
    "forbid_user_parts": ["first_name", "last_name", "display_name", "email_local"],
    "banned": ["password", "123456", "qwerty", "letmein", "admin"],
    "uncompromised": {
        "enabled":   os.getenv("PASSWORD_UNCOMPROMISED_ENABLED", "false").lower() == "true",
        "threshold": int(os.getenv("PASSWORD_UNCOMPROMISED_THRESHOLD", 1)),
    },
}
