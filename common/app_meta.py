APP_VERSION = "1.1.0"


def format_window_title(title):
    base = (title or "").strip()
    suffix = f"v{APP_VERSION}"
    if not base:
        return suffix
    if suffix in base:
        return base
    return f"{base} · {suffix}"

