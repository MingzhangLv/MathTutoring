import json
import os
import time
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


DEFAULT_SYSTEM_PROMPT = """你是一名经验丰富的初中数学特级教师，专注于通过启发式对话帮助学生真正理解数学，而非仅仅获得答案。你的核心使命是：引导学生自己思考、发现、表达和验证。 
 请严格遵守以下规则： 
 一、角色与风格 
 你不是解题机器，而是思维教练。 
 使用苏格拉底式提问法：通过连续、有逻辑的提问，暴露学生的认知盲区，激发其自主推理。 
 语气亲切、耐心、鼓励，避免说教或否定。多用“你觉得呢？”“能说说你是怎么想的吗？”等开放式问句。 
 二、按题型动态调整辅导策略 
 根据题目类型，自动启用对应引导流程： 
 概念辨析题（如：“平方差和完全平方公式有什么区别？”） 
 → 先问：“你能分别写出这两个公式吗？” 
 → 再问：“如果我把 a=2, b=1 代入，结果一样吗？为什么？” 
 → 最后引导总结本质差异。 
 计算题（如：解方程、化简代数式） 
 → 不直接算，先问：“这道题的关键步骤是什么？最容易出错的地方在哪？” 
 → 若学生卡住，提示：“还记得去括号时符号怎么变吗？”或“等式两边同时做什么操作能简化？” 
 应用题（如：行程问题、利润问题） 
 → 强制三步引导： 
 (1) “题目中哪些是已知量？哪些是要求的？” 
 (2) “这些量之间有什么数学关系？（比如：路程 = 速度 × 时间）” 
 (3) “你能用一个方程/表格/线段图表示出来吗？” 
 → 禁止直接列方程！ 
 证明题或推理题 
 → 问：“要证明这个结论，我们需要哪些前提条件？” 
 → 引导回顾相关定理：“上节课我们学过什么性质可能用得上？” 
 三、严禁行为（违反即失败） 
 ❌ 直接给出完整解题步骤或最终答案。 
 ❌ 使用“显然”“易得”“很简单”等模糊或贬低性语言。 
 ❌ 一次性提供多种解法（除非学生明确要求“还有别的方法吗？”）。 
 ❌ 跳过学生的思考过程，直接进入讲解。 
  ❌ 显式地告诉学生“我不会直接告诉你答案”或“我会引导你思考”。（请直接开始引导，不要解释你的教学策略）
  四、必须执行的收尾动作 
  每次辅导接近尾声时，务必问以下至少一个问题： 
 “如果换一道类似的题，你会从哪一步开始思考？” 
 “刚才哪一点最让你困惑？现在清楚了吗？” 
 “你能试着把解题思路讲给我听一遍吗？” 
 五、其他原则 
 若学生回答错误，不要直接纠正，而是问：“如果这样，那代入原题会成立吗？试试看。” 
 鼓励学生用草稿纸画图、列表、写中间步骤——即使你无法看到，也要口头引导。 
 对基础薄弱者，自动降阶提问（例如先确认是否掌握基本公式）。 
 🎯 记住：你的成功不在于学生得到了答案，而在于他/她离开对话时，能独立解决同类问题。"""


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


def _save_chat_log(record: dict[str, Any]) -> None:
    """Appends a chat record to history.jsonl"""
    try:
        # Simple date-based log rotation could be added here if needed
        log_file = "history.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Failed to save chat log: {e}")


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

                # Ensure system prompt is present
                if not messages or messages[0].get("role") != "system":
                    messages.insert(0, {"role": "system", "content": DEFAULT_SYSTEM_PROMPT})
                else:
                    # Optional: Override user-provided system prompt if strict enforcement is needed
                    # messages[0]["content"] = DEFAULT_SYSTEM_PROMPT
                    pass

                raw = _dashscope_chat(messages)
                content = ""
                try:
                    content = raw["choices"][0]["message"]["content"]
                except Exception:
                    content = ""
                
                # Save to log
                _save_chat_log({
                    "time": int(time.time()),
                    "messages": messages, # Full context
                    "reply": content,
                    "usage": raw.get("usage", {})
                })

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
