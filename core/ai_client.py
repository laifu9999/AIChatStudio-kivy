"""可插拔 AI provider 客户端 + 自动获取模型列表。

支持 OpenAI 兼容协议（覆盖 DeepSeek / 通义 / 文心 / 本地 Ollama / OpenRouter / 智谱 等），
以及 Anthropic(Claude) 原生协议。新增厂商只需在 PROVIDER_PRESETS 加一项。

并发策略（按 provider 维度）：
- 智谱免费模型：自动 1 并发、单任务串行轮流请求（免费额度限制），跨会话也排队。
- 其他 provider：可多会话/多并发同时进行（默认并发上限见 GLOBAL_LIMIT，可配）。
"""
import http.client
import json
import threading
import urllib.request
import urllib.error
import urllib.parse
from core.config import DEFAULT_SETTINGS

# 智谱免费/Flash 模型关键字（命中即强制串行单并发）
ZHIPU_FREE_MODELS = ("glm-4-flash", "glm-4v-flash", "glm-4-air", "glm-4-airx",
                     "glm-4.7-flash", "glm-4.7-flashx", "free")

# 新增的两个 GLM Flash 模型（适配单并发、不限流、不出错）
GLM_FLASH_MODELS = ["glm-4.7-flash", "glm-4.7-flashx"]


# 厂商预设：base_url 为兼容 OpenAI /v1 协议的地址；anthropic 走原生协议
# free_tier=True 表示该 provider 的默认模型走免费额度 → 强制 1 并发串行。
PROVIDER_PRESETS = {
    "OpenAI":        {"base_url": "https://api.openai.com/v1", "protocol": "openai"},
    "DeepSeek":      {"base_url": "https://api.deepseek.com/v1", "protocol": "openai"},
    "通义千问(Qwen)": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "protocol": "openai"},
    "文心一言(ERNIE)": {"base_url": "https://qianfan.baidubce.com/v2", "protocol": "openai"},
    "OpenRouter":    {"base_url": "https://openrouter.ai/api/v1", "protocol": "openai"},
    "Ollama(本地)":   {"base_url": "http://localhost:11434/v1", "protocol": "openai"},
    "Claude(Anthropic)": {"base_url": "https://api.anthropic.com/v1", "protocol": "anthropic"},
    "智谱GLM(免费)":  {"base_url": "https://open.bigmodel.cn/api/paas/v4", "protocol": "openai",
                      "free_tier": True, "default_model": "glm-4-flash"},
    "智谱GLM(Flash)": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "protocol": "openai",
                      "free_tier": True, "default_model": "glm-4.7-flash",
                      "fixed_models": GLM_FLASH_MODELS,
                      "verify_model": True},
    "智谱GLM(付费)":  {"base_url": "https://open.bigmodel.cn/api/paas/v4", "protocol": "openai",
                      "default_model": "glm-4-plus"},
    "自定义OpenAI兼容": {"base_url": "", "protocol": "openai"},
}


def fixed_models_for(provider_name):
    """返回某 provider 的「固定模型列表」（若有预设），用于不让下拉被接口返回的无关模型污染。"""
    preset = PROVIDER_PRESETS.get(provider_name, {})
    return list(preset.get("fixed_models", []) or [])

# 其他 provider 的全局并发上限（免费模型不被包含）。智谱免费始终 1。
GLOBAL_LIMIT = 6


def list_providers():
    return list(PROVIDER_PRESETS.keys())


def fetch_models(provider_name, api_key, base_url=None):
    """拉取某 provider 的模型列表。返回模型 id 列表（str）。失败抛异常。"""
    preset = PROVIDER_PRESETS.get(provider_name, {})
    protocol = preset.get("protocol", "openai")
    url = (base_url or preset.get("base_url") or "").rstrip("/")
    if not url:
        raise ValueError("未配置 Base URL")
    if protocol == "openai":
        return _fetch_openai_models(url, api_key)
    elif protocol == "anthropic":
        return _fetch_anthropic_models(url, api_key)
    raise ValueError("未知协议")


def _fetch_openai_models(base_url, api_key):
    url = f"{base_url}/models"
    req = urllib.request.Request(url)
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    models = [m["id"] for m in data.get("data", [])]
    return sorted(models)


def _fetch_anthropic_models(base_url, api_key):
    # Anthropic 没有公开 list models 接口，返回常见模型作为回退
    fallback = [
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229",
        "claude-3-haiku-20240307",
    ]
    if not api_key:
        return fallback
    try:
        url = f"{base_url}/models"
        req = urllib.request.Request(url)
        req.add_header("x-api-key", api_key)
        req.add_header("anthropic-version", "2023-06-01")
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return sorted([m["id"] for m in data.get("data", [])])
    except Exception:
        return fallback


class ChatClient:
    """统一聊天客户端，支持流式逐字输出（on_token 回调）。

    并发说明：
    - 若该客户端属于「智谱免费」或当前模型是免费模型，则走 _serial_lock（全局唯一），
      任意时刻只有 1 个请求进行，多个会话/多次调用自动排队轮流（单并发、每次只处理
      一次请求、多请求轮流来、不重叠、不出错）。
    - 否则走全局并发信号量 GLOBAL_LIMIT，可多会话同时进行。

    模型校验：
    - 若 preset 标记 verify_model=True（如智谱 Flash 系列），每次请求会校验接口实际
      返回的 model 字段是否与所请求的模型一致，防止「选了 A 模型却连到 B 模型」。
    """
    # 智谱免费全局串行锁（所有智谱免费客户端共用，跨会话排队）
    _serial_lock = threading.Lock()
    # 其他 provider 的全局并发信号量
    _conc_sem = threading.Semaphore(GLOBAL_LIMIT)
    # 请求序号（用于日志/轮换追踪）
    _req_counter = 0

    def __init__(self, provider_name, api_key, model, base_url=None, system_prompt=None):
        self.provider_name = provider_name
        preset = PROVIDER_PRESETS.get(provider_name, {})
        self.protocol = preset.get("protocol", "openai")
        self.base_url = (base_url or preset.get("base_url") or "").rstrip("/")
        self.api_key = api_key
        self.model = model or ""
        self.system_prompt = system_prompt or ""
        # 是否免费额度（强制 1 并发串行）
        self.is_free = bool(preset.get("free_tier")) or any(
            fm in self.model.lower() for fm in ZHIPU_FREE_MODELS
        )
        # 是否需要校验返回模型与请求模型一致
        self.verify_model = bool(preset.get("verify_model")) and self.is_free

    def chat(self, messages, on_token=None, on_reasoning=None):
        """messages: [{"role": "user"/"assistant"/"system", "content": "..."}]
        on_token: 可选回调，每收到一个增量片段时调用 on_token(delta_text)。
        on_reasoning: 可选回调，收到思考过程(reasoning_content)增量时调用。
        返回完整助手文本。自动按并发策略排队（单并发时串行轮流，每次只一个请求）。"""
        ChatClient._req_counter += 1
        if self.is_free:
            # 单并发：全局唯一锁，保证任意时刻只有一个请求在处理；
            # 多个请求自动排队轮流，不重叠、不报错。
            with ChatClient._serial_lock:
                return self._do_chat(messages, on_token, on_reasoning)
        else:
            with ChatClient._conc_sem:
                return self._do_chat(messages, on_token, on_reasoning)

    def _do_chat(self, messages, on_token=None, on_reasoning=None):
        if self.protocol == "anthropic":
            return self._chat_anthropic(messages, on_token)
        return self._chat_openai(messages, on_token, on_reasoning)

    def _inject_system(self, messages):
        """把系统提示词作为首条 system 消息注入（若已存在 system 则合并）。"""
        if not self.system_prompt:
            return messages
        msgs = list(messages)
        if msgs and msgs[0].get("role") == "system":
            msgs[0] = {"role": "system", "content": self.system_prompt + "\n\n" + msgs[0]["content"]}
        else:
            msgs.insert(0, {"role": "system", "content": self.system_prompt})
        return msgs

    def _chat_openai(self, messages, on_token=None, on_reasoning=None):
        url = f"{self.base_url}/chat/completions"
        # 注入系统提示词 + 规范化消息
        messages = self._inject_system(messages)
        messages = self._normalize_messages(messages)
        # 优先流式；若调用方未提供 on_token 则退化为非流式
        stream = on_token is not None
        # 记录本次请求使用的模型，便于校验（防止选 A 连到 B）
        req_model = self.model
        payload = {"model": req_model, "messages": messages, "stream": stream}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")
        try:
            req.timeout = 120
            # 用低层连接以支持流式逐行读取
            parsed = urllib.parse.urlparse(url)
            conn = http.client.HTTPSConnection(parsed.netloc, timeout=120) if parsed.scheme == "https" \
                else http.client.HTTPConnection(parsed.netloc, timeout=120)
            path = parsed.path + ("?" + parsed.query if parsed.query else "")
            conn.request("POST", path, body=data, headers=dict(req.headers))
            resp = conn.getresponse()
            if resp.status != 200:
                detail = resp.read().decode("utf-8", "ignore")[:500]
                raise RuntimeError(f"HTTP {resp.status} {resp.reason}: {detail}")
            if not stream:
                obj = json.loads(resp.read().decode("utf-8"))
                self._verify_returned_model(obj.get("model"), req_model)
                msg = obj["choices"][0]["message"]
                conn.close()
                return msg.get("content", "")
            # 流式逐字解析 SSE
            buf = ""
            full = ""
            resp_model = None
            while True:
                line = resp.readline()
                if not line:
                    break
                line = line.decode("utf-8", "ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except Exception:
                    continue
                if resp_model is None:
                    resp_model = chunk.get("model")
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                # 思考过程（DeepSeek-R1 / 通义 thinking 等推理模型）
                reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                if reasoning:
                    full_reasoning = getattr(self, "_acc_reasoning", "")
                    full_reasoning += reasoning
                    self._acc_reasoning = full_reasoning
                    if on_reasoning:
                        on_reasoning(reasoning)
                if content:
                    full += content
                    if on_token:
                        on_token(content)
            conn.close()
            # 流式结束时再校验一次模型（用首个 chunk 里的 model）
            self._verify_returned_model(resp_model, req_model)
            return full
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "ignore")
            except Exception:
                pass
            raise RuntimeError(f"HTTP {e.code} {e.reason}: {detail[:500]}")

    def _verify_returned_model(self, returned_model, req_model):
        """校验接口实际返回的模型是否与请求的模型一致。

        防止「选了 GLM-4.7-Flash 却连到了别的模型」之类问题。
        仅在 verify_model=True（智谱 Flash 系列）时生效。
        """
        if not getattr(self, "verify_model", False):
            return
        if not req_model:
            return
        rm = (returned_model or "").strip().lower()
        qm = req_model.strip().lower()
        if rm and rm != qm:
            raise RuntimeError(
                f"模型校验失败：请求模型为「{req_model}」，但服务端返回模型为「{returned_model}」。"
                f"可能不是你选择的模型，请检查 API Key / 模型名是否正确。"
            )

    @staticmethod
    def _normalize_messages(messages):
        """清洗并规整消息序列，避免部分厂商(如智谱)返回 400。"""
        # 1. 过滤空内容
        msgs = [m for m in messages if isinstance(m, dict)
                and str(m.get("content", "")).strip() != ""]
        # 2. 拆分 system 与对话
        sys_msgs = [m for m in msgs if m.get("role") == "system"]
        conv = [m for m in msgs if m.get("role") != "system"]
        # 3. 交替规整：合并连续相同 role，首条强制 user
        cleaned = []
        for m in conv:
            role = m.get("role")
            if role not in ("user", "assistant"):
                role = "user"
            if cleaned and cleaned[-1]["role"] == role:
                # 同 role 相邻：智谱不允许，合并内容
                cleaned[-1]["content"] += "\n" + str(m.get("content", ""))
            else:
                cleaned.append({"role": role, "content": str(m.get("content", ""))})
        # 4. 首条必须是 user
        while cleaned and cleaned[0]["role"] != "user":
            cleaned.pop(0)
        # 5. 重新拼装：system 在前
        result = list(sys_msgs) + cleaned
        return result if result else [{"role": "user", "content": "你好"}]

    def _chat_anthropic(self, messages, on_token=None):
        url = f"{self.base_url}/messages"
        # 转成 anthropic 格式
        sys = next((m["content"] for m in messages if m["role"] == "system"), None)
        conv = [m for m in messages if m["role"] != "system"]
        payload = {"model": self.model, "messages": conv, "max_tokens": 4096}
        if sys:
            payload["system"] = sys
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        if self.api_key:
            req.add_header("x-api-key", self.api_key)
        req.add_header("anthropic-version", "2023-06-01")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        text = "".join(block.get("text", "") for block in out.get("content", []))
        if on_token:
            on_token(text)
        return text

    def test_connection(self):
        """发一个最小请求验证连通性。返回 (ok: bool, msg: str)。"""
        if not self.base_url:
            return False, "未配置 Base URL"
        if not self.api_key:
            return False, "未填写 API Key"
        try:
            out = self._do_chat([
                {"role": "user", "content": "ping"},
            ])
            if out and out.strip():
                return True, f"连接成功 [OK] 模型已响应：{out[:40]}"
            return True, "连接成功 [OK]（模型返回为空，但链路正常）"
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}：{e.reason}"
        except Exception as e:
            return False, f"连接失败：{e}"


def is_free_tier(provider_name, model=""):
    """判断某 provider/模型是否走免费 1 并发串行。供 UI 提示用。"""
    preset = PROVIDER_PRESETS.get(provider_name, {})
    if preset.get("free_tier"):
        return True
    m = (model or "").lower()
    return any(fm in m for fm in ZHIPU_FREE_MODELS)


def default_model_for(provider_name):
    """返回某 provider 的默认模型（若有预设）。"""
    return PROVIDER_PRESETS.get(provider_name, {}).get("default_model", "")
