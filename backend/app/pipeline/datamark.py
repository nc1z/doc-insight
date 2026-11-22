MARKER = "^"


def datamark(text: str) -> str:
    words = text.split()
    if not words:
        return ""
    return MARKER.join(words)


def datamark_values(value: object) -> object:
    if isinstance(value, str):
        return datamark(value)
    if isinstance(value, list):
        return [datamark_values(item) for item in value]
    if isinstance(value, dict):
        return {str(key): datamark_values(item) for key, item in value.items()}
    return value
