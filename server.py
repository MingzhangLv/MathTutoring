import json
import os
import time
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def _json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")

def _load_application_config() -> dict[str, Any]:
    file_path = os.getenv("APPLICATION_CONFIG", "application.local.json").strip() or "application.local.json"
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_config_value(config: dict[str, Any], path: list[str], default: str = "") -> str:
    cur: Any = config
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    if cur is None:
        return default
    return str(cur)


def _read_json_body(handler: SimpleHTTPRequestHandler) -> Any:
    content_length = int(handler.headers.get("Content-Length") or "0")
    raw = handler.rfile.read(content_length) if content_length > 0 else b"{}"
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _dashscope_chat(messages: list[dict[str, str]]) -> dict[str, Any]:
    cfg = _load_application_config()

    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip() or _get_config_value(cfg, ["dashscope", "api_key"]).strip()
    if not api_key:
        raise RuntimeError("DashScope api_key is missing")

    model = (
        os.getenv("QWEN_MODEL", "").strip()
        or _get_config_value(cfg, ["dashscope", "model"], "qwen-turbo").strip()
        or "qwen-turbo"
    )
    base_url = (
        os.getenv("DASHSCOPE_BASE_URL", "").strip()
        or _get_config_value(cfg, ["dashscope", "base_url"], "https://dashscope.aliyuncs.com").strip()
        or "https://dashscope.aliyuncs.com"
    ).rstrip("/")
    url = f"{base_url}/compatible-mode/v1/chat/completions"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
    }

    req = urllib.request.Request(
        url=url,
        method="POST",
        data=_json_bytes(payload),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DashScope HTTPError {e.code}: {raw}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"DashScope URLError: {e}") from e


class AppHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def _send_json(self, status: int, data: Any) -> None:
        body = _json_bytes(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.startswith("/api/health"):
            self._send_json(200, {"ok": True, "time": int(time.time())})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path.startswith("/api/chat"):
            try:
                data = _read_json_body(self)
                incoming_messages = data.get("messages")
                prompt = data.get("prompt")
                if isinstance(incoming_messages, list):
                    messages = [
                        {"role": str(m.get("role", "")).strip(), "content": str(m.get("content", ""))}
                        for m in incoming_messages
                        if isinstance(m, dict)
                    ]
                else:
                    messages = []

                if prompt and not messages:
                    messages = [{"role": "user", "content": str(prompt)}]

                if not messages:
                    self._send_json(400, {"error": "messages or prompt is required"})
                    return

                raw = _dashscope_chat(messages)
                content = ""
                try:
                    content = raw["choices"][0]["message"]["content"]
                except Exception:
                    content = ""
                self._send_json(200, {"reply": content, "raw": raw})
            except RuntimeError as e:
                self._send_json(500, {"error": str(e)})
            except Exception as e:
                self._send_json(500, {"error": f"Internal error: {e}"})
            return

        self._send_json(404, {"error": "Not Found"})


def main() -> None:
    cfg = _load_application_config()
    port = int(os.getenv("PORT", "").strip() or _get_config_value(cfg, ["server", "port"], "5173") or "5173")
    server = ThreadingHTTPServer(("0.0.0.0", port), AppHandler)
    print(f"Serving on http://localhost:{port}/")
    print("POST /api/chat with {messages:[{role,content}]} or {prompt}")
    server.serve_forever()


if __name__ == "__main__":
    main()
