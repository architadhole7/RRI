import re
from typing import Any


class InputSanitizer:
    """Sanitizes raw inputs and checks for malicious strings or malformed fields."""

    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+previous\s+instructions",
        r"override\s+policy",
        r"approve\s+all",
        r"bypass\s+security",
        r"system\s*:",
        r"<script>",
        r"drop\s+table",
    ]

    def is_safe_string(self, text: str) -> bool:
        if not text:
            return True
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        return True

    def sanitize_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        sanitized = {}
        for k, v in data.items():
            if isinstance(v, str):
                if not self.is_safe_string(v):
                    raise ValueError(f"Malicious or suspicious string detected in field '{k}'")
                sanitized[k] = v.strip()
            else:
                sanitized[k] = v
        return sanitized
