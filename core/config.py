import json
import os

_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".seaice_platform", "config.json")


def load() -> dict:
    try:
        if os.path.exists(_CONFIG_FILE):
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save(data: dict):
    os.makedirs(os.path.dirname(_CONFIG_FILE), exist_ok=True)
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get(key: str, default=None):
    return load().get(key, default)


def set(key: str, value):
    data = load()
    data[key] = value
    save(data)
