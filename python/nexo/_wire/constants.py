"""Version-frozen NEXO/1 tags, dictionaries and parser limits."""
KEYS = ("type", "task", "status", "data", "id", "name", "files", "changed",
        "content", "message", "role", "agent", "timestamp", "error", "result",
        "tool", "args", "output", "mime", "sha256", "size", "ref", "version",
        "metadata", "input", "model", "tokens", "cost")
VALUES = ("result", "ok", "error", "request", "pending", "running", "done",
          "failed", "system", "user", "assistant", "tool", "text", "image",
          "file", "success", "warning")
KEY_IDS = {name: i for i, name in enumerate(KEYS)}
VALUE_IDS = {name: i for i, name in enumerate(VALUES)}
MAX_FRAME = 8 * 1024 * 1024
MAX_ITEMS = 100_000
MAX_DEPTH = 64
MIN_I64, MAX_I64 = -(2**63), 2**63 - 1


