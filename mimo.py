#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-platform MiMo V2.5 helper for the deepseek-vision skill.

这是一个可直接运行的命令行工具（CLI），用于调用小米 MiMo V2.5 模型。
它支持四类核心能力：

1. analyze：分析图片/音频/视频内容（本地文件或公网 URL 都可以）。
2. asr：将 wav/mp3 音频转写为文字。
3. configure/use/status：配置和切换两种计费方式（按量付费 / Token Plan）。
4. check/diagnose：检查 API Key、DNS 和网络是否可用。

此外还提供 jobs/poll/worker，用于把耗时任务放到后台执行后再查询结果。

为了让初学者快速读懂，代码里对每个函数都加了中文注释：
- 函数开头的 docstring 说明用途、参数和返回值；
- 关键实现行附近用 # 注释解释“为什么这样做”。
"""

# ---- 标准库导入 ----
# Python 内置模块，不需要额外安装。
import argparse  # 解析命令行参数，例如 python mimo.py analyze --files x.jpg
import base64  # Base64 编解码，本地文件会转成 Base64 字符串传给 API
import getpass  # 交互式输入 API Key（输入内容不会回显到屏幕）
import json  # 解析/生成 JSON 数据（API 请求和配置都使用 JSON）
import os  # 读取环境变量、操作系统信息、设置文件权限等
import shutil  # 查找系统中已安装的可执行程序（如 curl、ffprobe）
import signal  # 用 SIGALRM 实现“请求超时”控制（仅 Unix 可用）
import socket  # 网络相关，如 DNS 解析、设置默认超时
import ssl  # 创建 HTTPS 安全连接上下文
import subprocess  # 启动子进程（调用 curl、powershell、security 等）
import sys  # 访问系统参数、标准输入输出
import time  # 时间戳、休眠、轮询
import uuid  # 生成唯一 ID，用作后台任务编号
import urllib.error  # urllib 网络请求的错误类型
import urllib.parse  # URL 解析，例如从 URL 提取扩展名/主机名
import urllib.request  # 发起 HTTP/HTTPS 请求
import wave  # 解析 WAV 音频文件头部信息（用于计算音频时长）
from contextlib import contextmanager  # 装饰器，用来写 with 语句的上下文管理器
from datetime import date  # 获取今天日期，拼进 system prompt
from pathlib import Path  # 现代文件路径操作，例如 Path("a/b.png")

# ---- 跨平台可选导入 ----
# fcntl 只存在于 Unix（macOS/Linux），Windows 没有；
# msvcrt 只存在于 Windows。用 try/except 保证两套系统都能运行。
try:
    import fcntl  # Unix 文件锁，避免多个进程并发写配置
except ImportError:
    fcntl = None

try:
    import msvcrt  # Windows 文件锁
except ImportError:
    msvcrt = None

# ---- 全局常量 ----
# 按量付费 API 的默认地址（后面拼接 /chat/completions 得到完整接口）
DEFAULT_BASE_URL = "https://api.xiaomimimo.com/v1"
# Token Plan 页面展示的示例 Base URL，仅用于给用户做提示
TOKEN_PLAN_EXAMPLE = "https://token-plan-cn.xiaomimimo.com/v1"
# 通用多模态模型：可同时理解文本、图片、音频、视频
DEFAULT_MODEL = "mimo-v2.5"
# 专用语音识别模型（ASR = Automatic Speech Recognition）
ASR_MODEL = "mimo-v2.5-asr"
# 本地文件转成 Base64 后的体积上限：50MB，防止请求过大被 API 拒绝
BASE64_LIMIT = 50 * 1024 * 1024
# 两种计费方式的中文显示名，方便输出提示信息
PAYG_LABEL = "按量付费"
TOKEN_LABEL = "Token Plan"
# 全局缓存的 SSL 上下文，避免每次请求都重新读取证书文件
_SSL_CONTEXT = None
# 单次 HTTP 请求的超时秒数
REQUEST_TIMEOUT = 60


class _RequestTimeout(Exception):
    """自定义异常：表示一次请求超过了规定时间。"""

    pass


def _request_timeout_call(seconds, func):
    """在指定秒数内执行 func()，超时就抛出 _RequestTimeout。

    原理：
    - Unix 上通过 signal.alarm 设置“闹钟”，到点触发 _handler 抛异常；
    - Windows 没有 SIGALRM，改用 socket.setdefaulttimeout 做全局超时。
    """
    if hasattr(signal, "SIGALRM"):
        def _handler(_signum, _frame):
            raise _RequestTimeout()

        previous = signal.signal(signal.SIGALRM, _handler)  # 保存旧的处理函数
        signal.alarm(seconds)  # seconds 秒后触发 SIGALRM
        try:
            return func()
        finally:
            signal.alarm(0)  # 取消闹钟
            signal.signal(signal.SIGALRM, previous)  # 恢复旧的处理函数
    socket.setdefaulttimeout(seconds)
    return func()


# 文件扩展名 -> MIME 类型 的映射表。
# MIME 类型告诉 API“这段数据是图片、音频还是视频”，是标准的互联网媒体类型。
EXT_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "flac": "audio/flac",
    "m4a": "audio/mp4",
    "ogg": "audio/ogg",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "avi": "video/x-msvideo",
    "wmv": "video/x-ms-wmv",
}


class MiMoError(Exception):
    """业务错误异常，带错误码 code，便于上层判断错误种类。

    例如 code="timeout" 表示超时，code=401 表示认证失败。
    """

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def _default_pricing():
    """返回内置的价格表（单位：元 / 百万 token）。

    注意：这里只是兜底参考值，真实扣费以官方账单为准。
    """
    return {
        DEFAULT_MODEL: {
            "input_uncached_cny_per_mtok": 1.0,
            "input_cached_cny_per_mtok": 0.02,
            "output_cny_per_mtok": 2.0,
        },
        ASR_MODEL: {
            "cny_per_audio_hour": 0.5,
        },
    }


def _default_config():
    """返回一份全新的默认配置结构。

    配置最终保存为 JSON，结构如下：
    - active_plan: 当前生效的计费方式，只能是 "payg" 或 "token"
    - payg: 按量付费的 API Key 和 Base URL
    - token: Token Plan 的 API Key 和专属 Base URL
    - pricing: 价格表（仅用于本地估算费用）
    - pricing_updated: 价格表更新时间
    """
    return {
        "active_plan": "",
        "payg": {"api_key": "", "base_url": DEFAULT_BASE_URL},
        "token": {"api_key": "", "base_url": ""},
        "pricing": _default_pricing(),
        "pricing_updated": "2026-08-03",
    }


def _config_dir():
    """返回配置目录。

    - Windows: %APPDATA%\\deepseek-vision
    - 其他系统: ~/.config/deepseek-vision
    优先读取环境变量 APPDATA / XDG_CONFIG_HOME，找不到再用默认路径。
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "deepseek-vision"


def _credentials_path():
    """返回保存凭据的 JSON 文件完整路径。"""
    return _config_dir() / "credentials.json"


def _lock_path():
    """返回锁文件路径，用于避免多进程同时写配置。"""
    return _config_dir() / ".credentials.lock"


def _jobs_dir():
    """返回后台任务目录，每个任务对应一个 JSON 文件。"""
    return _config_dir() / "jobs"


def _worker_log_path():
    """返回后台 worker 的日志文件路径。"""
    return _config_dir() / "worker.log"


def _job_path(job_id):
    """根据任务 ID 返回对应的 JSON 文件路径。"""
    return _jobs_dir() / f"{job_id}.json"


def _use_file_backend():
    """是否强制使用普通文件保存凭据。

    环境变量 MIMO_CREDENTIAL_BACKEND=file 时返回 True，
    否则使用默认的 "auto"，由平台自动选择存储方式。
    """
    return os.environ.get("MIMO_CREDENTIAL_BACKEND", "auto").strip().lower() == "file"


def _sanitize_text(text, secrets=()):
    """把日志/错误信息中的敏感内容替换成 ***，并压缩为一行。

    text: 原始文本，可能是报错信息或 API 返回内容。
    secrets: 需要隐藏的字符串列表，例如 API Key、Base URL。
    返回值最多保留 500 个字符，避免把完整响应打印到终端。
    """
    text = text or ""
    for secret in secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, "***")
    return " ".join(text.split())[:500]


def _ssl_context():
    """创建并缓存 SSL 上下文（HTTPS 证书校验配置）。

    优先使用系统中已有的 CA 证书文件，找不到再退回 Python 默认证书，
    这样能避免某些系统上 HTTPS 校验失败。
    """
    global _SSL_CONTEXT
    if _SSL_CONTEXT is None:
        candidates = [
            os.environ.get("SSL_CERT_FILE"),
            "/etc/ssl/cert.pem",
            "/etc/pki/tls/certs/ca-bundle.crt",
            "/etc/ssl/certs/ca-certificates.crt",
        ]
        for path in candidates:
            if path and Path(path).exists():
                _SSL_CONTEXT = ssl.create_default_context(cafile=path)
                break
        else:
            _SSL_CONTEXT = ssl.create_default_context()
    return _SSL_CONTEXT


def _mask_value(value):
    """把 API Key 打码后显示，例如 sk-a123****5678。"""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def _mask_url(value):
    """把 Base URL 打码，只保留协议部分，例如 https://***。"""
    if not value:
        return ""
    scheme = value.split("://", 1)[0] if "://" in value else "http"
    return f"{scheme}://***"


def _restrict_windows_file(path):
    """Windows 上收紧文件权限，只允许当前用户读写。

    使用 icacls 命令：先去掉继承权限，再给当前用户 R/W 权限，
    防止凭据文件被其他用户读取。
    """
    user = os.environ.get("USERNAME")
    if not user:
        return
    subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(R,W)"],
        capture_output=True,
        text=True,
    )


def _keychain_read():
    """从 macOS Keychain 读取配置内容。

    通过系统的 security 命令查找服务名 deepseek-vision 的密码项，
    找不到时返回 None（不视为错误）。
    """
    proc = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-a",
            "default",
            "-s",
            "deepseek-vision",
            "-w",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def _keychain_write(payload):
    """把配置写入 macOS Keychain。

    使用 security add-generic-password，-U 表示已存在时更新。
    写入失败会抛出 MiMoError，code 为 "keychain"。
    """
    proc = subprocess.run(
        [
            "security",
            "add-generic-password",
            "-U",
            "-a",
            "default",
            "-s",
            "deepseek-vision",
            "-w",
            payload,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise MiMoError(
            f"无法写入 macOS Keychain: {_sanitize_text(proc.stderr.strip())}",
            code="keychain",
        )


def _dpapi_read():
    """从 Windows DPAPI 加密文件读取配置。

    流程：先读取本地加密的 secret 文件，再调用 PowerShell 解密。
    DPAPI 的加密密钥与当前 Windows 用户绑定，换用户后无法解密。
    """
    secret = _config_dir() / "secret"
    if not secret.exists():
        return None
    command = (
        "$e = Get-Content -LiteralPath $env:MIMO_SECRET_FILE -Raw; "
        "$s = $e | ConvertTo-SecureString; "
        "$b = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($s); "
        "try { [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } "
        "finally { [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }"
    )
    env = {**os.environ, "MIMO_SECRET_FILE": str(secret)}
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        raise MiMoError(
            f"无法读取 Windows 凭据: {_sanitize_text(proc.stderr.strip())}",
            code="dpapi",
        )
    value = proc.stdout.strip()
    return value or None


def _dpapi_write(payload):
    """用 Windows DPAPI 加密并写入配置。

    先把 JSON 明文传给 PowerShell，ConvertTo-SecureString 加密后再写入文件。
    """
    secret = _config_dir() / "secret"
    _config_dir().mkdir(parents=True, exist_ok=True)
    command = (
        "$s = ConvertTo-SecureString $env:MIMO_CREDENTIALS_JSON -AsPlainText -Force; "
        "$e = ConvertFrom-SecureString $s; "
        "Set-Content -LiteralPath $env:MIMO_SECRET_FILE -Value $e -NoNewline"
    )
    env = {
        **os.environ,
        "MIMO_CREDENTIALS_JSON": payload,
        "MIMO_SECRET_FILE": str(secret),
    }
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        raise MiMoError(
            f"无法写入 Windows 凭据: {_sanitize_text(proc.stderr.strip())}",
            code="dpapi",
        )


def _read_file():
    """从普通 JSON 文件读取配置原文，文件不存在时返回 None。"""
    path = _credentials_path()
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _write_file(payload):
    """把配置写入普通 JSON 文件。

    采用“先写临时文件，再原子替换”的方式：
    - 先写同目录下的 .tmp 文件；
    - 写完后用 os.replace 一次性替换正式文件。
    这样即使中途崩溃，也不会留下半个文件损坏正式配置。
    """
    path = _credentials_path()
    _config_dir().mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    if os.name != "nt":
        os.chmod(tmp, 0o600)  # 非 Windows 系统：只允许当前用户读写
    os.replace(tmp, path)  # 原子替换，保证文件要么是旧的、要么是新的
    if os.name == "nt":
        _restrict_windows_file(path)


def _remove_file():
    """删除凭据文件；文件不存在或删除失败时静默忽略。"""
    try:
        _credentials_path().unlink(missing_ok=True)
    except OSError:
        pass


@contextmanager
def _config_lock():
    """跨平台文件锁，配合 with 语句使用。

    用法示例：
        with _config_lock():
            读写配置

    这样多个进程不会同时改写配置，避免互相覆盖。
    """
    _config_dir().mkdir(parents=True, exist_ok=True)
    with open(_lock_path(), "a+b") as handle:
        if fcntl:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)  # Unix 加锁
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)  # Unix 解锁
        elif msvcrt:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)  # Windows 加锁
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)  # Windows 解锁
        else:
            yield  # 两个锁模块都不可用时退化为无锁


def _write_job_file(job):
    """把后台任务对象写成 JSON 文件，文件名是任务 ID。"""
    path = _job_path(job["id"])
    _jobs_dir().mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    if os.name != "nt":
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)  # 同样采用原子替换


def _read_job(job_id):
    """按任务 ID 读取任务 JSON，任务不存在时报错。"""
    path = _job_path(job_id)
    if not path.exists():
        raise MiMoError(f"任务不存在：{job_id}", code="job_not_found")
    return json.loads(path.read_text(encoding="utf-8"))


def _claim_next_job():
    """领取一个待处理任务，并把状态从 pending 改为 running。

    后台 worker 每次启动会循环调用这个函数，直到没有 pending 任务为止。
    状态变更会立刻写回文件，防止两个 worker 同时处理同一个任务。
    """
    _jobs_dir().mkdir(parents=True, exist_ok=True)
    for path in sorted(_jobs_dir().glob("*.json")):  # 按文件名（时间顺序）扫描
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if job.get("status") == "pending":
            job["status"] = "running"
            _write_job_file(job)
            return job
    return None


def _spawn_worker():
    """以“后台进程”方式启动 worker，执行本脚本的 worker 子命令。

    后台进程与终端分离（start_new_session / DETACHED_PROCESS），
    这样即使主命令结束，worker 也能继续跑完剩余任务。
    日志统一写入 worker.log。
    """
    script = Path(__file__).resolve()
    _config_dir().mkdir(parents=True, exist_ok=True)
    with open(_worker_log_path(), "ab") as log:
        kwargs = {
            "stdin": subprocess.DEVNULL,
            "stdout": log,
            "stderr": subprocess.STDOUT,
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([sys.executable, str(script), "worker"], **kwargs)


def _job_command(job):
    """把一个任务对象还原成命令行参数列表。

    后台 worker 实际上会再执行一次 python mimo.py analyze/asr ...，
    这里就是根据任务字段重新拼出那行完整命令。
    """
    script = Path(__file__).resolve()
    if job.get("command") == "analyze":
        cmd = [
            sys.executable,
            str(script),
            "analyze",
            "--max-tokens",
            str(job.get("max_tokens", 1024)),
            "--fps",
            str(job.get("fps", 2.0)),
            "--resolution",
            str(job.get("resolution", "default")),
        ]
        for file_path in job.get("files", []):
            cmd += ["--files", file_path]
        for url in job.get("urls", []):
            cmd += ["--urls", url]
        if job.get("kind"):
            cmd += ["--kind", job["kind"]]
        cmd += ["--prompt", job.get("prompt") or "请基于附件内容直接、简洁地回答。"]
        return cmd
    cmd = [
        sys.executable,
        str(script),
        "asr",
        "--file",
        str(job.get("file", "")),
        "--language",
        str(job.get("language", "auto")),
        "--max-tokens",
        str(job.get("max_tokens", 2048)),
    ]
    return cmd


def _load_raw_config():
    """读取配置原文，优先使用系统安全存储，最后退回普通文件。

    - macOS: 优先 Keychain；
    - Windows: 优先 DPAPI；
    - 其他系统或设置了 MIMO_CREDENTIAL_BACKEND=file：读普通文件。
    """
    if sys.platform == "darwin" and not _use_file_backend():
        try:
            value = _keychain_read()
        except MiMoError:
            value = None
        if value:
            return value
    if os.name == "nt" and not _use_file_backend():
        try:
            value = _dpapi_read()
        except MiMoError:
            value = None
        if value:
            return value
    return _read_file()


def _decode_config_raw(raw):
    """把配置原文解析成 Python 字典。

    支持两种格式：
    1. 普通 JSON 文本；
    2. 十六进制编码的 JSON（历史上兼容旧版本存储格式）。
    """
    candidates = [raw]
    try:
        candidates.append(bytes.fromhex(raw.strip()).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        pass
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise MiMoError("全局配置损坏，请重新运行 configure", code="config")


def _merge_defaults(cfg):
    """把默认配置合并进已有配置，补齐缺失的键。

    这样即使旧版本配置文件缺少某些字段，程序也能正常读取，
    不会因为 KeyError 崩溃。
    """
    defaults = _default_config()
    for key, default_value in defaults.items():
        if key not in cfg or cfg[key] is None:
            cfg[key] = default_value
        elif isinstance(default_value, dict) and isinstance(cfg[key], dict):
            merged = dict(default_value)
            merged.update({k: v for k, v in cfg[key].items() if v not in (None, "")})
            cfg[key] = merged
    return cfg


def load_config():
    """加载并解析完整配置。

    如果安全存储读取失败，会尝试用普通文件兜底；
    最后统一用 _merge_defaults 补齐默认字段。
    """
    raw = _load_raw_config()
    if not raw:
        cfg = _default_config()
    else:
        try:
            cfg = _decode_config_raw(raw)
        except MiMoError:
            fallback = _read_file()
            if not fallback:
                raise
            cfg = _decode_config_raw(fallback)
    return _merge_defaults(cfg)


def save_config(cfg):
    """保存配置：写入所有可用的存储后端，并带文件锁保护。"""
    payload = json.dumps(cfg, ensure_ascii=False, indent=2)
    with _config_lock():
        if sys.platform == "darwin" and not _use_file_backend():
            try:
                _keychain_write(payload)
            except MiMoError:
                pass  # Keychain 写入失败不影响文件后端，继续尝试
        if os.name == "nt" and not _use_file_backend():
            try:
                _dpapi_write(payload)
            except MiMoError:
                pass
        _write_file(payload)


def _plan_credentials(cfg, plan):
    """取某个计费方式（payg/token）下的凭据字典，没有则返回空字典。"""
    return cfg.get(plan) or {}


def active_plan(cfg):
    """返回当前生效的计费方式；只有 payg/token 才被认为是合法的。"""
    plan = cfg.get("active_plan") or ""
    return plan if plan in ("payg", "token") else ""


def active_credentials(cfg):
    """返回当前生效的完整凭据（API Key + Base URL）。

    token 方式必须同时有 base_url，否则视为未配置完成，返回 None。
    """
    plan = active_plan(cfg)
    creds = _plan_credentials(cfg, plan)
    if creds.get("api_key") and (plan != "token" or creds.get("base_url")):
        return creds
    return None


def _env_credentials(plan):
    """从环境变量构造临时凭据，不需要写入配置文件。"""
    key = os.environ.get("MIMO_API_KEY", "").strip()
    url = os.environ.get("MIMO_BASE_URL", "").strip()
    if not key:
        return None
    if plan == "payg":
        url = url or DEFAULT_BASE_URL  # 按量付费可以不传 Base URL，用默认值
    if plan == "token" and not url:  # Token Plan 必须有专属 Base URL
        return None
    return {"api_key": key, "base_url": url}


def _stdin_tty():
    """判断标准输入是否是终端（是否适合做交互式提问）。"""
    return sys.stdin is not None and sys.stdin.isatty()


def _choose_plan_interactively():
    """交互式询问用户选择计费方式，返回 "payg" 或 "token"。"""
    print("请选择配置方式：", file=sys.stderr)
    print("1) 按量付费 API Key（sk-xxxxx）", file=sys.stderr)
    print("2) Token Plan（tp-xxxxx + 专属 Base URL）", file=sys.stderr)
    choice = input("请输入 1 或 2: ").strip()
    return {"1": "payg", "2": "token"}.get(choice)


def _validate_prefix(plan, key):
    """校验 API Key 前缀是否与所选计费方式匹配。

    按量付费的 Key 通常以 sk- 开头，
    Token Plan 的 Key 通常以 tp- 开头，
    传反了会给出明确报错，避免用户配错。
    """
    if plan == "payg" and key.startswith("tp-"):
        raise MiMoError(
            f"key 以 tp- 开头，看起来是 {TOKEN_LABEL}；请使用 --plan token"
        )
    if plan == "token" and key.startswith("sk-"):
        raise MiMoError(
            f"key 以 sk- 开头，看起来是 {PAYG_LABEL}；请使用 --plan payg"
        )


def _http_json(url, credentials, payload=None, method="POST", retries=2, auth_header="api-key"):
    """发起一次 HTTP 请求并返回 (解析后的 JSON, HTTP 状态码)。

    优先使用系统 curl 命令（稳定、能拿到 HTTP 状态码），
    没有 curl 时退回 Python 标准库 urllib。

    参数：
    - url: 完整接口地址；
    - credentials: {"api_key": "...", "base_url": "..."}；
    - payload: 要发送的字典，会自动转成 JSON；
    - method: HTTP 方法，默认 POST；
    - retries: 失败后最多重试的次数；
    - auth_header: 认证方式，api-key 或 bearer。

    对 429/5xx 这类“可能临时恢复”的错误会自动重试，
    401/403 等确定性错误直接抛出。
    """
    key = credentials.get("api_key", "")
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    curl = shutil.which("curl")
    if curl:
        # 让 curl 在正常输出后追加一行 HTTP 状态码（如 200），方便解析
        cmd = [
            curl,
            "--silent",
            "--show-error",
            "--max-time",
            str(REQUEST_TIMEOUT),
            "--connect-timeout",
            "15",
            "--write-out",
            "\n%{http_code}",
            "-X",
            method,
        ]
        if auth_header == "api-key":
            cmd += ["-H", f"api-key: {key}"]
        else:
            cmd += ["-H", f"Authorization: Bearer {key}"]
        cmd += ["-H", "Content-Type: application/json"]
        if data is not None:
            cmd += ["--data-binary", "@-"]
        cmd.append(url)

        last_error = None
        for attempt in range(retries + 1):
            try:
                proc = subprocess.run(
                    cmd,
                    input=data,
                    capture_output=True,
                    timeout=REQUEST_TIMEOUT + 5,
                )
            except subprocess.TimeoutExpired:
                message = f"请求超时（超过 {REQUEST_TIMEOUT} 秒），请稍后重试或改用更小的文件"
                last_error = MiMoError(message, code="timeout")
                if attempt < retries:
                    time.sleep(1 + attempt)
                    continue
                raise last_error

            output = proc.stdout.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                stderr = proc.stderr.decode("utf-8", errors="replace")
                message = (
                    "网络错误: "
                    + _sanitize_text(stderr or output, [key, credentials.get("base_url", "")])
                )
                last_error = MiMoError(message, code="network")
                if attempt < retries:
                    time.sleep(1 + attempt)  # 重试前等 1 秒、2 秒……逐渐变长
                    continue
                raise last_error

            body = output
            status = 0
            if "\n" in output:  # 把最后一行状态码和响应体分开
                body, status_raw = output.rsplit("\n", 1)
                try:
                    status = int(status_raw.strip())
                except ValueError:
                    status = 0

            if status >= 400:
                message = f"HTTP {status}: {_sanitize_text(body, [key, credentials.get('base_url', '')])}"
                last_error = MiMoError(message, code=status)
                if status in (429, 500, 502, 503, 504) and attempt < retries:  # 可重试的状态码
                    time.sleep(1 + attempt)
                    continue
                raise last_error

            try:
                return json.loads(body), status or 200
            except json.JSONDecodeError:
                message = f"响应解析失败: {_sanitize_text(body, [key, credentials.get('base_url', '')])}"
                last_error = MiMoError(message, code="parse")
                if attempt < retries:
                    time.sleep(1 + attempt)
                    continue
                raise last_error
        raise last_error or MiMoError("请求失败", code="unknown")

    headers = {"Content-Type": "application/json"}
    if auth_header == "api-key":
        headers["api-key"] = key
    else:
        headers["Authorization"] = f"Bearer {key}"
    # 下面是 urllib 分支，逻辑与 curl 分支基本一致
    last_error = None
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with _request_timeout_call(
                REQUEST_TIMEOUT,
                lambda: urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT, context=_ssl_context()),
            ) as response:
                body = response.read().decode("utf-8", errors="replace")
                return json.loads(body), response.status
        except _RequestTimeout:
            message = f"请求超时（超过 {REQUEST_TIMEOUT} 秒），请稍后重试或改用更小的文件"
            last_error = MiMoError(message, code="timeout")
            if attempt < retries:
                time.sleep(1 + attempt)
                continue
            raise last_error
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            message = f"HTTP {exc.code}: {_sanitize_text(body, [key, credentials.get('base_url', '')])}"
            last_error = MiMoError(message, code=exc.code)
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(1 + attempt)
                continue
            raise last_error
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            message = f"网络错误: {_sanitize_text(str(exc), [key, credentials.get('base_url', '')])}"
            last_error = MiMoError(message, code="network")
            if attempt < retries:
                time.sleep(1 + attempt)
                continue
            raise last_error
    raise MiMoError("请求失败", code="unknown")


def chat_completions(credentials, payload):
    """调用 /chat/completions 接口，发送对话请求。

    部分服务同时支持 api-key 和 Bearer 两种认证方式，
    这里先试 api-key，若返回 401/403 再试 Bearer。
    """
    url = credentials["base_url"].rstrip("/") + "/chat/completions"
    last_error = None
    for auth_header in ("api-key", "bearer"):
        try:
            return _http_json(url, credentials, payload=payload, auth_header=auth_header)
        except MiMoError as exc:
            if exc.code in (401, 403):
                last_error = exc
                continue
            raise
    raise last_error or MiMoError("认证失败", code=401)


def list_models(credentials):
    """调用 /models 接口，返回可用模型 ID 列表。

    兼容两种返回格式：{"data": [...]} 或直接是数组；
    如果接口不支持（404/405），返回空列表而不是报错。
    """
    url = credentials["base_url"].rstrip("/") + "/models"
    last_error = None
    for auth_header in ("api-key", "bearer"):
        try:
            data, _ = _http_json(url, credentials, method="GET", retries=1, auth_header=auth_header)
            if isinstance(data, dict):
                return data.get("data") or []
            if isinstance(data, list):
                return data
            return []
        except MiMoError as exc:
            if exc.code in (401, 403):
                last_error = exc
                continue
            if exc.code in (404, 405):
                return []
            raise
    raise last_error or MiMoError("认证失败", code=401)


def _data_uri(path):
    """把本地文件转成 Data URI 字符串。

    Data URI 的格式：
        data:image/png;base64,AAAA...
    也就是把文件内容用 Base64 编码后嵌进请求里，
    这样 API 不需要先下载文件就能拿到完整内容。

    返回值：(data_uri, mime_type)
    """
    ext = path.suffix.lower().lstrip(".")
    mime = EXT_MIME.get(ext)
    if not mime:
        raise MiMoError(
            f"不支持的媒体格式 .{ext or '?'}：{path}；支持 png/jpg/gif/webp/bmp、mp3/wav/flac/m4a/ogg、mp4/mov/avi/wmv"
        )
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise MiMoError(f"无法读取文件 {path}：{exc}", code="file") from exc
    encoded = base64.b64encode(data).decode("ascii")
    if len(encoded) > BASE64_LIMIT:
        raise MiMoError(
            f"文件 Base64 超过 50MB 限制：{path}（Base64 约 {len(encoded)} 字节）；请压缩、转码或改用公网 URL"
        )
    return f"data:{mime};base64,{encoded}", mime


def _part_for_mime(mime, data, fps, resolution):
    """根据媒体类型，构造符合 OpenAI 风格的多模态消息片段。

    - 图片: {"type": "image_url", ...}
    - 音频: {"type": "input_audio", ...}
    - 视频: {"type": "video_url", ...}，额外带 fps 和分辨率参数
    """
    if mime.startswith("image/"):
        return {"type": "image_url", "image_url": {"url": data}}
    if mime.startswith("audio/"):
        return {"type": "input_audio", "input_audio": {"data": data}}
    if mime.startswith("video/"):
        return {
            "type": "video_url",
            "video_url": {"url": data},
            "fps": fps,
            "media_resolution": resolution,
        }
    raise MiMoError(f"未知媒体类型 {mime}")


def _file_parts(paths, fps, resolution):
    """把一组本地文件路径转换成 API 消息片段列表。"""
    parts = []
    for raw_path in paths:
        data_uri, mime = _data_uri(Path(raw_path))
        parts.append(_part_for_mime(mime, data_uri, fps, resolution))
    return parts


def _url_parts(urls, kind, fps, resolution):
    """把一组公网 URL 转换成 API 消息片段列表。

    如果 URL 没有扩展名，无法从后缀判断类型，
    就使用 --kind 参数指定的 image/audio/video 来补全 MIME 类型。
    """
    parts = []
    for url in urls:
        ext = Path(urllib.parse.urlparse(url).path).suffix.lower().lstrip(".")
        mime = EXT_MIME.get(ext)
        if not mime:
            if kind == "image":
                mime = "image/jpeg"
            elif kind == "audio":
                mime = "audio/mpeg"
            elif kind == "video":
                mime = "video/mp4"
            else:
                raise MiMoError(
                    f"无法从 URL 判断媒体类型：{url}；请补充 --kind image|audio|video"
                )
        parts.append(_part_for_mime(mime, url, fps, resolution))
    return parts


def _extract_usage(data):
    """从 API 响应中提取 token 用量统计，方便展示和估算费用。"""
    usage = data.get("usage") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "cached_tokens": prompt_details.get("cached_tokens", 0),
        "image_tokens": prompt_details.get("image_tokens"),
        "audio_tokens": prompt_details.get("audio_tokens"),
        "video_tokens": prompt_details.get("video_tokens"),
        "reasoning_tokens": completion_details.get("reasoning_tokens"),
    }


def _extract_content(data):
    """从 API 响应中提取真正的回答文本。

    返回 (content, reasoning_fallback)：
    - content: 回答内容；
    - reasoning_fallback: 当 content 为空但模型输出了 reasoning_content 时，
      把思考内容当作最终答案返回，并标记为 True。
    """
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content")
    reasoning = message.get("reasoning_content")
    if content is None or content == "":
        if reasoning:
            return reasoning, True
        return "", False
    return content, False


def _finish_reason(data):
    """获取模型停止生成的原因。

    常见值：
    - stop: 正常结束；
    - length: 因为达到 token 上限被截断。
    """
    choice = (data.get("choices") or [{}])[0]
    return choice.get("finish_reason")


def _chat_with_retry(credentials, body, max_tokens):
    """调用模型，若因输出长度不足被截断，自动增大 max_tokens 重试。

    最多重试 4 次，token 上限最多放大到 4096，
    避免回答到一半被截断，也避免无限放大请求。
    """
    data, _ = chat_completions(credentials, body)
    current_max = max_tokens
    for _ in range(4):
        content, _ = _extract_content(data)
        if content and _finish_reason(data) != "length":
            break
        if current_max >= 4096:
            break
        current_max = min(current_max * 2, 4096)
        body["max_completion_tokens"] = current_max
        data, _ = chat_completions(credentials, body)
    return data


def _audio_duration(path):
    """估算音频时长（秒）。

    优先用 ffprobe（精确且通用），
    没有 ffprobe 时，对 wav 文件用 Python 标准库 wave 直接算。
    """
    ext = path.suffix.lower().lstrip(".")
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            proc = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return float(proc.stdout.strip())
        except (OSError, ValueError):
            pass
    if ext == "wav":
        try:
            with wave.open(str(path), "rb") as audio:
                rate = float(audio.getframerate() or 1)
                return audio.getnframes() / rate
        except (OSError, wave.Error, ZeroDivisionError):
            pass
    return None


def _cost_for(plan, model, usage, duration, pricing):
    """按量付费模式下估算本次调用费用，返回 (金额, 提示文本)。

    - 文本/多模态按 token 计费：输入 token 又区分缓存/未缓存两种价格；
    - ASR 语音识别按“音频小时数”计费；
    - Token Plan 或缺少价格配置时返回 None，表示以官方账单为准。
    """
    if plan != "payg":
        return None, None
    rates = pricing.get(model) or pricing.get(DEFAULT_MODEL) or {}
    if model == ASR_MODEL:
        rate = rates.get("cny_per_audio_hour")
        if rate is None or duration is None:
            return None, "金额以官方账单为准"
        return round(duration / 3600.0 * rate, 4), None
    input_rate = rates.get("input_uncached_cny_per_mtok")
    cached_rate = rates.get("input_cached_cny_per_mtok")
    output_rate = rates.get("output_cny_per_mtok")
    if input_rate is None or cached_rate is None or output_rate is None:
        return None, "缺少价格配置，金额以官方账单为准"
    prompt = usage.get("prompt_tokens", 0)
    cached = usage.get("cached_tokens", 0)
    uncached = max(prompt - cached, 0)
    cost = (
        uncached / 1_000_000.0 * input_rate
        + cached / 1_000_000.0 * cached_rate
        + usage.get("completion_tokens", 0) / 1_000_000.0 * output_rate
    )
    return round(cost, 4), None


def _print_dry_run(command, plan, credentials, body, extra=None):
    """--dry-run 模式：只打印将要发送的请求内容，不真正调用 API。"""
    output = {
        "ok": True,
        "command": command,
        "dry_run": True,
        "plan": plan,
        "base_url": _mask_url(credentials.get("base_url", "")),
        "request": body,
    }
    if extra:
        output.update(extra)
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_configure(args):
    """configure 命令：配置 API Key 和 Base URL。

    流程：
    1. 确定计费方式（命令行参数或交互式选择）；
    2. 确定 Base URL（按量付费可省略，Token Plan 必须提供）；
    3. 获取 API Key（环境变量或交互输入，不回显）；
    4. 校验 Key 前缀是否匹配计费方式；
    5. 保存配置并设为当前生效的 plan。
    """
    plan = args.plan
    if not plan:
        if not _stdin_tty():
            raise MiMoError(
                "请指定 --plan payg 或 --plan token；也可交互式运行 configure 选择",
                code="usage",
            )
        plan = _choose_plan_interactively()
        if not plan:
            raise MiMoError("未选择有效的配置方式", code="usage")

    if plan == "payg":
        base_url = args.base_url or os.environ.get("MIMO_BASE_URL", "").strip() or DEFAULT_BASE_URL
    else:
        base_url = args.base_url or os.environ.get("MIMO_BASE_URL", "").strip()
        if not base_url and _stdin_tty():
            print(
                f"Token Plan 专属 Base URL 请从 Token Plan 页面复制（示例：{TOKEN_PLAN_EXAMPLE}，以页面显示为准）",
                file=sys.stderr,
            )
            base_url = input("专属 Base URL: ").strip()  # 交互输入时不会校验格式，只做非空检查
        if not base_url:
            raise MiMoError(
                "Token Plan 需要专属 Base URL；请从 Token Plan 页面复制后通过 --base-url 提供",
                code="usage",
            )

    key = os.environ.get("MIMO_API_KEY", "").strip()
    if not key and _stdin_tty():
        key = getpass.getpass(f"请输入 {TOKEN_LABEL if plan == 'token' else PAYG_LABEL} API Key（输入不回显）: ").strip()
    if not key:
        raise MiMoError(
            "未提供 API Key；请通过 MIMO_API_KEY 环境变量提供，或交互式运行 configure",
            code="usage",
        )
    _validate_prefix(plan, key)

    cfg = load_config()
    cfg[plan] = {"api_key": key, "base_url": base_url}  # 更新对应计费方式的凭据
    cfg["active_plan"] = plan  # 同时把它设为当前生效的 plan
    save_config(cfg)
    print(
        json.dumps(
            {
                "ok": True,
                "command": "configure",
                "plan": plan,
                "configured": True,
                "next": "run check to verify",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_use(args):
    """use 命令：在两种计费方式之间切换。

    如果目标方式还没配置，会尝试从环境变量构造凭据；
    环境变量也没有时直接报错，提示先运行 configure。
    """
    cfg = load_config()
    creds = _plan_credentials(cfg, args.plan)
    missing = not creds.get("api_key") or (args.plan == "token" and not creds.get("base_url"))
    if missing:
        env_creds = _env_credentials(args.plan)
        if env_creds and (args.plan == "payg" or env_creds.get("base_url")):
            cfg[args.plan] = env_creds  # 用环境变量临时补上配置
        else:
            label = TOKEN_LABEL if args.plan == "token" else PAYG_LABEL
            raise MiMoError(
                f"{label} 尚未配置；请先运行 configure --plan {args.plan} 配置一次",
                code="not_configured",
            )
    cfg["active_plan"] = args.plan  # 只切换生效标记，不覆盖另一套配置
    save_config(cfg)
    print(
        json.dumps(
            {
                "ok": True,
                "command": "use",
                "active_plan": args.plan,
                "switched": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_status(args):
    """status 命令：查看当前配置状态（Key 和 URL 都会打码显示）。"""
    cfg = load_config()
    plan = active_plan(cfg)
    creds = _plan_credentials(cfg, plan)
    print(
        json.dumps(
            {
                "ok": True,
                "command": "status",
                "active_plan": plan or None,
                "payg_configured": bool(cfg.get("payg", {}).get("api_key")),
                "token_configured": bool(cfg.get("token", {}).get("api_key")),
                "active_key": _mask_value(creds.get("api_key", "")),
                "active_base_url": _mask_url(creds.get("base_url", "")),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_check(args):
    """check 命令：用当前凭据请求 /models，验证 API Key 是否可用。"""
    cfg = load_config()
    plan = active_plan(cfg)
    creds = active_credentials(cfg)
    if not creds:
        raise MiMoError("尚未配置 active plan；请先运行 configure", code="not_configured")
    models = list_models(creds)
    model_ids = []
    for item in models or []:
        if isinstance(item, dict):
            model_ids.append(str(item.get("id") or ""))
        elif isinstance(item, str):
            model_ids.append(item)
    has_v25 = DEFAULT_MODEL in model_ids
    has_asr = ASR_MODEL in model_ids
    print(
        json.dumps(
            {
                "ok": True,
                "command": "check",
                "plan": plan,
                "models_listed": bool(model_ids),
                "models": sorted(set(model_ids))[:50],
                "mimo-v2.5": has_v25,
                "mimo-v2.5-asr": has_asr,
                "base_url": _mask_url(creds.get("base_url", "")),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_diagnose(args):
    """diagnose 命令：逐步排查配置、DNS 和网络问题。"""
    cfg = load_config()
    plan = active_plan(cfg)
    creds = active_credentials(cfg)
    result = {
        "ok": True,
        "command": "diagnose",
        "active_plan": plan or None,
        "config_ok": bool(creds),
        "dns_ok": None,
        "network_ok": None,
    }
    if not creds:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    host = urllib.parse.urlparse(creds.get("base_url", "")).hostname
    if host:
        try:
            socket.getaddrinfo(host, 443)  # 能解析出 IP 说明 DNS 正常
            result["dns_ok"] = True
        except Exception as exc:
            result["dns_ok"] = False
            result["dns_error"] = _sanitize_text(str(exc), [creds.get("base_url", "")])
    try:
        models = list_models(creds)
        model_ids = []
        for item in models or []:
            if isinstance(item, dict):
                model_ids.append(str(item.get("id") or ""))
            elif isinstance(item, str):
                model_ids.append(item)
        result["network_ok"] = True
        result["models"] = sorted(set(model_ids))[:50]
    except MiMoError as exc:
        result["network_ok"] = False
        result["network_error"] = str(exc)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_poll(args):
    """poll 命令：轮询后台任务状态，等它完成或到达等待上限。"""
    deadline = time.time() + args.wait
    while True:
        job = _read_job(args.job)
        status = job.get("status")
        if status in ("done", "error"):  # 任务结束：打印结果并清理任务文件
            result = job.get("result") or {}
            try:
                _job_path(args.job).unlink(missing_ok=True)
            except OSError:
                pass
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        if time.time() >= deadline:  # 超时：返回当前状态，不报错
            print(
                json.dumps(
                    {
                        "ok": True,
                        "command": "poll",
                        "job_id": args.job,
                        "status": status,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        time.sleep(1)  # 每 1 秒看一次


def cmd_jobs(args):
    """jobs 命令：列出所有后台任务及状态。"""
    _jobs_dir().mkdir(parents=True, exist_ok=True)
    jobs = []
    for path in sorted(_jobs_dir().glob("*.json")):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        jobs.append(
            {
                "job_id": job.get("id"),
                "command": job.get("command"),
                "status": job.get("status"),
                "created": job.get("created"),
            }
        )
    print(
        json.dumps(
            {"ok": True, "command": "jobs", "jobs": jobs},
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_worker(args):
    """worker 命令：后台任务执行器，由 --async 自动启动。

    循环执行：
    1. 加锁并领取一个 pending 任务；
    2. 用子进程重新运行 analyze/asr 命令；
    3. 把结果（ok/error）写回任务文件。
    没有任务时就退出。
    """
    while True:
        with _config_lock():
            job = _claim_next_job()
        if not job:
            break
        job_id = job["id"]
        try:
            proc = subprocess.run(
                _job_command(job),
                capture_output=True,
                text=True,
                timeout=REQUEST_TIMEOUT * 4 + 30,
            )
            output = (proc.stdout or "").strip()
            try:
                result = json.loads(output)  # 子命令输出的是 JSON
            except json.JSONDecodeError:
                result = {
                    "ok": False,
                    "error": _sanitize_text(output or proc.stderr),
                    "code": "worker_parse",
                }
            if not result.get("ok"):
                result = {
                    "ok": False,
                    "error": result.get("error", "worker failed"),
                    "code": result.get("code", "worker"),
                }
        except subprocess.TimeoutExpired:
            result = {"ok": False, "error": "后台任务超时", "code": "worker_timeout"}
        except Exception as exc:
            result = {"ok": False, "error": _sanitize_text(str(exc)), "code": "worker"}
        with _config_lock():
            job["status"] = "done" if result.get("ok") else "error"
            job["result"] = result
            _write_job_file(job)


def cmd_analyze(args):
    """analyze 命令：让 mimo-v2.5 分析图片/音频/视频。

    三种运行模式：
    - --dry-run: 只打印请求体，不发请求；
    - --async: 写入任务文件并启动后台 worker，立即返回 job_id；
    - 默认: 同步等待结果并输出。
    """
    cfg = load_config()
    plan = active_plan(cfg)
    creds = active_credentials(cfg)

    if not args.files and not args.urls:
        raise MiMoError("请提供 --files 或 --urls", code="usage")

    parts = _file_parts(args.files, args.fps, args.resolution)
    parts.extend(_url_parts(args.urls, args.kind, args.fps, args.resolution))
    if not parts:
        raise MiMoError("没有可处理的媒体内容", code="usage")

    prompt = args.prompt or "请基于附件内容直接、简洁地回答。"
    today = date.today().isoformat()
    system = (
        "You are MiMo, an AI assistant developed by Xiaomi. "
        f"Today is {today}. Answer the user's latest request directly and concisely. "
        "Do not add unrelated reasoning unless asked."
    )
    body = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": [*parts, {"type": "text", "text": prompt}]},
        ],
        "max_completion_tokens": args.max_tokens,  # 回答最多生成的 token 数
        "stream": False,  # 不用流式，直接等完整 JSON 响应
    }

    if args.dry_run:
        dry_plan = plan or os.environ.get("MIMO_PLAN", "payg")
        dry_creds = creds or {
            "api_key": "sk-dry-run",
            "base_url": DEFAULT_BASE_URL,
        }
        _print_dry_run("analyze", dry_plan, dry_creds, body)
        return

    if args.async_mode:
        # 异步模式：任务写进磁盘，worker 稍后处理
        job = {
            "id": uuid.uuid4().hex,  # 随机生成的任务 ID
            "created": time.time(),
            "status": "pending",
            "command": "analyze",
            "files": args.files,
            "urls": args.urls,
            "kind": args.kind,
            "prompt": prompt,
            "max_tokens": args.max_tokens,
            "fps": args.fps,
            "resolution": args.resolution,
        }
        _write_job_file(job)
        _spawn_worker()
        print(
            json.dumps(
                {
                    "ok": True,
                    "command": "analyze",
                    "async": True,
                    "job_id": job["id"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if not creds:
        raise MiMoError("尚未配置 active plan；请先运行 configure", code="not_configured")

    data = _chat_with_retry(creds, body, args.max_tokens)
    content, reasoning_fallback = _extract_content(data)
    finish_reason = _finish_reason(data)
    usage = _extract_usage(data)
    if not content:
        raise MiMoError("MiMo 未返回可用内容，请缩小问题或提高 --max-tokens 重试", code="empty")

    result = {
        "ok": True,
        "command": "analyze",
        "mimo_used": True,
        "content": content,
        "model": DEFAULT_MODEL,
        "plan": plan,
        "usage": usage,
        "finish_reason": finish_reason,
        "reasoning_fallback": reasoning_fallback,
    }
    if plan == "payg":
        cost, note = _cost_for(plan, DEFAULT_MODEL, usage, None, cfg.get("pricing", {}))
        result["cost_cny"] = cost
        if note:
            result["cost_note"] = note
    else:
        result["tokens"] = usage.get("total_tokens", 0)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_asr(args):
    """asr 命令：用 mimo-v2.5-asr 把 wav/mp3 音频转成文字。"""
    path = Path(args.file)
    if not path.exists():
        raise MiMoError(f"文件不存在：{path}", code="file")
    ext = path.suffix.lower().lstrip(".")
    if ext not in ("wav", "mp3"):
        raise MiMoError("ASR 仅支持 wav/mp3 音频", code="usage")

    if args.async_mode:
        job = {
            "id": uuid.uuid4().hex,
            "created": time.time(),
            "status": "pending",
            "command": "asr",
            "file": args.file,
            "language": args.language,
            "max_tokens": args.max_tokens,
        }
        _write_job_file(job)
        _spawn_worker()
        print(
            json.dumps(
                {
                    "ok": True,
                    "command": "asr",
                    "async": True,
                    "job_id": job["id"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    data_uri, _ = _data_uri(path)
    body = {
        "model": ASR_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {"data": data_uri},
                    }
                ],
            }
        ],
        "asr_options": {"language": args.language},
        "max_completion_tokens": args.max_tokens,
        "stream": False,
    }

    cfg = load_config()
    plan = active_plan(cfg)
    creds = active_credentials(cfg)
    if args.dry_run:
        dry_plan = plan or os.environ.get("MIMO_PLAN", "payg")
        dry_creds = creds or {
            "api_key": "sk-dry-run",
            "base_url": DEFAULT_BASE_URL,
        }
        _print_dry_run("asr", dry_plan, dry_creds, body)
        return

    if not creds:
        raise MiMoError("尚未配置 active plan；请先运行 configure", code="not_configured")

    data = _chat_with_retry(creds, body, args.max_tokens)
    content, reasoning_fallback = _extract_content(data)
    finish_reason = _finish_reason(data)
    usage = _extract_usage(data)
    duration = _audio_duration(path)
    if not content:
        raise MiMoError("MiMo ASR 未返回可用内容，请重试或检查音频格式", code="empty")

    result = {
        "ok": True,
        "command": "asr",
        "mimo_used": True,
        "content": content,
        "model": ASR_MODEL,
        "plan": plan,
        "usage": usage,
        "finish_reason": finish_reason,
        "duration_seconds": duration,
        "reasoning_fallback": reasoning_fallback,
    }
    if plan == "payg":
        cost, note = _cost_for(plan, ASR_MODEL, usage, duration, cfg.get("pricing", {}))
        result["cost_cny"] = cost
        if note:
            result["cost_note"] = note
    else:
        result["tokens"] = usage.get("total_tokens", 0)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser():
    """构建命令行参数解析器。

    使用 argparse 的 add_subparsers 注册子命令：
    - configure/use/status: 配置管理
    - check/diagnose: 环境检查
    - analyze/asr: 核心 AI 功能
    - jobs/poll/worker: 后台任务管理
    """
    parser = argparse.ArgumentParser(description="MiMo V2.5 helper for deepseek-vision")
    subparsers = parser.add_subparsers(dest="command", required=True)

    configure = subparsers.add_parser("configure", help="Configure pay-as-you-go or Token Plan")
    configure.add_argument("--plan", choices=["payg", "token"], help="Plan to configure")
    configure.add_argument("--base-url", help="Base URL (required for Token Plan)")

    use = subparsers.add_parser("use", help="Switch global active plan")
    use.add_argument("--plan", required=True, choices=["payg", "token"])

    subparsers.add_parser("status", help="Show masked configuration status")
    subparsers.add_parser("check", help="Validate current credentials against MiMo API")
    subparsers.add_parser("diagnose", help="Check config, DNS and MiMo network connectivity")

    analyze = subparsers.add_parser("analyze", help="Analyze image/audio/video with mimo-v2.5")
    analyze.add_argument("--files", action="append", default=[], help="Local media file (repeatable)")  # 可重复使用
    analyze.add_argument("--urls", action="append", default=[], help="Remote media URL (repeatable)")
    analyze.add_argument("--kind", choices=["image", "audio", "video"], help="Media kind for URLs")
    analyze.add_argument("--prompt", help="Question for MiMo")
    analyze.add_argument("--max-tokens", type=int, default=1024)  # 回答长度上限
    analyze.add_argument("--fps", type=float, default=2.0)  # 视频抽帧帧率
    analyze.add_argument("--resolution", default="default")  # 视频分辨率
    analyze.add_argument("--dry-run", action="store_true")
    analyze.add_argument("--async", dest="async_mode", action="store_true")  # 后台执行

    asr = subparsers.add_parser("asr", help="Transcribe audio with mimo-v2.5-asr")
    asr.add_argument("--file", required=True)
    asr.add_argument("--language", default="auto")  # 识别语言，auto 自动检测
    asr.add_argument("--max-tokens", type=int, default=2048)
    asr.add_argument("--dry-run", action="store_true")
    asr.add_argument("--async", dest="async_mode", action="store_true")

    poll = subparsers.add_parser("poll", help="Poll an async MiMo job")
    poll.add_argument("--job", required=True, help="Job id returned by --async")
    poll.add_argument("--wait", type=int, default=0, help="Seconds to wait for completion")

    subparsers.add_parser("jobs", help="List pending and completed async jobs")
    subparsers.add_parser("worker", help="Internal background worker for async jobs")  # 一般不需要手动执行

    return parser


def main():
    """程序入口：解析参数、分发到对应命令、统一处理错误。"""
    parser = build_parser()
    args = parser.parse_args()
    # 子命令名 -> 处理函数 的映射表
    handlers = {
        "configure": cmd_configure,
        "use": cmd_use,
        "status": cmd_status,
        "check": cmd_check,
        "diagnose": cmd_diagnose,
        "poll": cmd_poll,
        "jobs": cmd_jobs,
        "worker": cmd_worker,
        "analyze": cmd_analyze,
        "asr": cmd_asr,
    }
    handler = handlers.get(args.command)
    try:
        if handler:
            handler(args)
    except MiMoError as exc:
        # 已知业务错误：输出 JSON 错误信息并以状态码 1 退出
        print(
            json.dumps(
                {
                    "ok": False,
                    "command": args.command,
                    "error": str(exc),
                    "code": exc.code,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - CLI boundary 意外错误兜底
        print(
            json.dumps(
                {
                    "ok": False,
                    "command": args.command,
                    "error": _sanitize_text(str(exc)),
                    "code": "unexpected",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()  # 只有直接运行 python mimo.py 时才执行；被 import 时不执行
