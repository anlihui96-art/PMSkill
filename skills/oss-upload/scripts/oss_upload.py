#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阿里云 OSS 直传工具（纯 Python 标准库 / OSS V1 签名）

替代原先散落在 html-prototype 技能里的 `ali-oss` + Node 模板（本机没有 node/npm/ali-oss）。
零第三方依赖：只用 argparse / hashlib / hmac / http.client / urllib.parse 等标准库。

能力：
  * 单文件或整个目录递归上传（目录按相对路径映射到 --prefix 之后）
  * OSS V1 签名（HMAC-SHA1 + Base64，Authorization: OSS <AK>:<sig>）
  * 默认发送 Content-MD5 并参与签名（下载/传输完整性校验）
  * Content-Type 按扩展名推断（.html/.htm 强制 text/html; charset=utf-8）
  * 寻址方式自动判定（virtual-hosted / path-style / 自定义域名），可用
    --path-style / --virtual-hosted 显式覆盖；CanonicalizedResource 恒为 /<bucket>/<key>
  * 凭据运行时获取（环境变量 / --credentials-from 指向既有脚本），不产生新的明文副本
  * --dry-run / --print-signature / --verify(HEAD 复核) / --json / --self-test
  * 中文文件名安全（签名用未编码 key，URL path 用 RFC 3986 编码）
  * 所有 stdout/stderr/JSON 输出统一脱敏：SK 永不出现，AK 只保留前 4 位 + ****

用法:
    oss_upload.py <本地文件或目录> [更多路径...] [选项]
    oss_upload.py --self-test

退出码: 0 成功 | 2 参数/文件错误 | 3 凭据缺失 | 4 HTTP 非 2xx | 5 --verify 复核失败
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import http.client
import json
import mimetypes
import os
import re
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

# ============================================================
# 默认值（均可被命令行 / 环境变量 / 配置文件覆盖）
# ============================================================
DEFAULT_BUCKET = "demoddys"
DEFAULT_REGION = "oss-cn-shanghai"
DEFAULT_PUBLIC_BASE = "https://demo.ddys-inc.com/"
CUSTOM_DOMAIN_BUCKET = "demoddys"
CUSTOM_DOMAIN_REGION = "oss-cn-shanghai"

DEFAULT_CONFIG_PATH = "~/.pm-skill/config.yml"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CREDENTIALS = 3
EXIT_HTTP = 4
EXIT_VERIFY = 5

# 只解析这些固定键（极简手写 YAML，不依赖 PyYAML）
# 说明：oss: 段推荐只放非密钥字段；accessKeyId/accessKeySecret 仍兼容旧配置但会提示。
CONFIG_KEY_MAP = {
    "accessKeyId": "access_key_id",
    "accessKeySecret": "access_key_secret",
    "bucket": "bucket",
    "region": "region",
    "endpoint": "endpoint",
    "publicBase": "public_base",
    "credentialsFrom": "credentials_from",
}

# 旧配置里出现这些键 → 读取并提示「不建议把密钥写进配置文件」
CONFIG_LEGACY_SECRET_KEYS = ("accessKeyId", "accessKeySecret")

# ============================================================
# 输出脱敏：所有 stdout / stderr / JSON 统一走这里
# 目的：任何错误信息、traceback 之外的打印都不可能带出 SK 明文，
#       AccessKeyId 最多显示前 4 位 + ****。
# ============================================================
_SECRET_REGISTRY: list[str] = []
_ACCESS_KEY_REGISTRY: list[str] = []


def register_secret(value) -> None:
    if isinstance(value, str) and value and value not in _SECRET_REGISTRY:
        _SECRET_REGISTRY.append(value)


def register_access_key_id(value) -> None:
    if isinstance(value, str) and value and value not in _ACCESS_KEY_REGISTRY:
        _ACCESS_KEY_REGISTRY.append(value)


def redact(text: str) -> str:
    """先抹掉 SK 明文，再把 AK 替换成前 4 位 + ****。"""
    out = text
    for secret in _SECRET_REGISTRY:
        out = out.replace(secret, "****")
    for ak in _ACCESS_KEY_REGISTRY:
        out = out.replace(ak, (ak or "")[:4] + "****")
    return out


_ORIGINAL_PRINT = print


def print(*args, **kwargs):  # noqa: A001 - 有意覆盖内置 print，统一做密钥脱敏
    safe = [redact(a if isinstance(a, str) else str(a)) for a in args]
    _ORIGINAL_PRINT(*safe, **kwargs)

# ============================================================
# Content-Type 映射（优先本表，其次 mimetypes 兜底）
# ============================================================
TYPE_MAP = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".bmp": "image/bmp",
    ".pdf": "application/pdf",
    ".zip": "application/zip",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
}
FALLBACK_TYPE = "application/octet-stream"

_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ============================================================
# 基础工具
# ============================================================
def format_rfc1123(dt: datetime) -> str:
    """RFC 1123 GMT 时间，例如 Wed, 01 Jan 2025 00:00:00 GMT"""
    dt = dt.astimezone(timezone.utc)
    return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (
        _WEEKDAYS[dt.weekday()], dt.day, _MONTHS[dt.month - 1], dt.year,
        dt.hour, dt.minute, dt.second,
    )


def rfc1123_now() -> str:
    return format_rfc1123(datetime.now(timezone.utc))


def md5_base64(body: bytes) -> str:
    return base64.b64encode(hashlib.md5(body).digest()).decode("ascii")


def guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TYPE_MAP:
        return TYPE_MAP[suffix]
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed:
        if guessed.startswith("text/"):
            return guessed + "; charset=utf-8"
        return guessed
    return FALLBACK_TYPE


def encode_key_path(key: str) -> str:
    """URL path 编码（RFC 3986），保留 / 分隔符，支持中文/空格文件名。"""
    return quote(key, safe="/")


# ============================================================
# OSS V1 签名
# ============================================================
def canonicalized_oss_headers(headers: dict) -> str:
    """所有 x-oss-* 头，按名字小写升序，每行 `key:value\\n`；无则为空串。"""
    items = []
    for name, value in headers.items():
        lower = name.lower()
        if lower.startswith("x-oss-"):
            items.append((lower, str(value).strip()))
    items.sort(key=lambda kv: kv[0])
    return "".join("%s:%s\n" % (k, v) for k, v in items)


def canonicalized_resource(bucket: str, key: str) -> str:
    """/<bucket>/<key>，使用未编码的原始 key。"""
    return "/" + bucket + "/" + key


def string_to_sign(verb: str, content_md5: str, content_type: str, date: str,
                   oss_headers: dict, bucket: str, key: str) -> str:
    return (
        verb + "\n"
        + content_md5 + "\n"
        + content_type + "\n"
        + date + "\n"
        + canonicalized_oss_headers(oss_headers)
        + canonicalized_resource(bucket, key)
    )


def sign(secret: str, string_to_sign_value: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        string_to_sign_value.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def build_authorization(access_key_id: str, access_key_secret: str,
                        string_to_sign_value: str) -> str:
    return "OSS %s:%s" % (
        access_key_id, sign(access_key_secret, string_to_sign_value))


def mask_ak(access_key_id: str) -> str:
    """只暴露 AK 前 4 位。"""
    return (access_key_id or "")[:4] + "****"


def mask_authorization(access_key_id: str, signature: str) -> str:
    return "OSS %s:%s" % (mask_ak(access_key_id), signature)


# ============================================================
# 配置文件（~/.pm-skill/config.yml 的 oss: 段，极简手写解析）
# ============================================================
def _strip_yaml_scalar(raw: str) -> str:
    value = raw.strip()
    if value[:1] in ("'", '"'):
        quote_char = value[0]
        end = value.find(quote_char, 1)
        if end != -1:
            return value[1:end]
        return value[1:]
    # 去掉行内注释（仅当 ` #` 之前无引号时）
    for marker in (" #", "\t#"):
        idx = value.find(marker)
        if idx != -1:
            value = value[:idx]
    return value.strip()


def load_config(path: Path | None) -> dict:
    """读取配置文件的 oss: 段，只认固定键；文件不存在/字段缺失不报错。

    若 oss: 段里出现 accessKeyId/accessKeySecret（旧配置），仍会读入以保持兼容，
    并在 `_legacy_secret_keys` 里记录键名，供调用方给出「不建议写进配置文件」的提示。
    """
    result: dict = {}
    if path is None or not path.exists() or not path.is_file():
        return result
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return result

    in_oss = False
    legacy_keys: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        if indent == 0:
            # 顶层键：只在遇到 `oss:` 时进入 oss 段
            in_oss = stripped.rstrip(":") == "oss" and stripped.endswith(":")
            continue
        if not in_oss or ":" not in stripped:
            continue
        name, _, raw_value = stripped.partition(":")
        name = name.strip()
        if name not in CONFIG_KEY_MAP:
            continue
        value = _strip_yaml_scalar(raw_value)
        if value:
            result[CONFIG_KEY_MAP[name]] = value
            if name in CONFIG_LEGACY_SECRET_KEYS:
                legacy_keys.append(name)
    if legacy_keys:
        result["_legacy_secret_keys"] = legacy_keys
    return result


# ============================================================
# 凭据来源：从既有脚本运行时提取（只读解析，不复制、不落盘）
# ============================================================
# 兼容 JS 里形如 `accessKeyId: 'xxx'` / `const accessKeyId = "xxx"` / `accessKeySecret: xxx`
_JS_CREDENTIAL_PATTERNS = {
    "access_key_id": re.compile(
        r"""\baccessKeyId\b\s*[:=]\s*(?:"([^"\n]*)"|'([^'\n]*)'|([^\s,;'")\}\n]+))"""),
    "access_key_secret": re.compile(
        r"""\baccessKeySecret\b\s*[:=]\s*(?:"([^"\n]*)"|'([^'\n]*)'|([^\s,;'")\}\n]+))"""),
}


def parse_js_credentials(text: str) -> dict:
    """从 JS 文本里各取「第一个」accessKeyId / accessKeySecret 赋值。

    引号可有可无，单双引号均兼容；返回 {'access_key_id': ..., 'access_key_secret': ...}，
    未匹配到的键不出现在结果里。
    """
    found: dict = {}
    for field, pattern in _JS_CREDENTIAL_PATTERNS.items():
        match = pattern.search(text)
        if not match:
            continue
        value = next((group for group in match.groups() if group), None)
        if value:
            found[field] = value.strip()
    return found


def load_credentials_from_file(token: str) -> dict:
    """只读解析既有脚本，取得 AK/SK；失败一律退出码 3 且不打印任何密钥内容。"""
    path = Path(os.path.expanduser(str(token).strip()))
    if not path.exists() or not path.is_file():
        die(EXIT_CREDENTIALS,
            "凭据来源文件不存在或不是普通文件：%s\n"
            "请检查 --credentials-from / 环境变量 OSS_CREDENTIALS_FROM / "
            "配置文件 oss.credentialsFrom 指向的路径是否正确。" % path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        die(EXIT_CREDENTIALS, "读取凭据来源文件失败：%s（%s）" % (path, exc))

    found = parse_js_credentials(text)
    missing = [label for field, label in (("access_key_id", "accessKeyId"),
                                         ("access_key_secret", "accessKeySecret"))
               if not found.get(field)]
    if missing:
        die(EXIT_CREDENTIALS,
            "在凭据来源文件 %s 中未找到 %s 的赋值。\n"
            "请检查该路径下的脚本内容（本工具只做只读解析，不会写入或复制密钥）。"
            % (path, " / ".join(missing)))

    register_access_key_id(found["access_key_id"])
    register_secret(found["access_key_secret"])
    return found



# ============================================================
# 参数解析
# ============================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oss_upload.py",
        description="阿里云 OSS 上传（纯 Python 标准库，OSS V1 签名）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "凭据来源优先级：命令行参数 > 环境变量（OSS_ACCESS_KEY_ID/OSS_ACCESS_KEY_SECRET，"
            "其次 OSS_AK_ID/OSS_AK_SECRET）> --credentials-from/OSS_CREDENTIALS_FROM/"
            "配置 oss.credentialsFrom 指向的既有脚本 > ~/.pm-skill/config.yml 的 oss: 段"
            "（不推荐写密钥）\n"
            "寻址方式：按 endpoint host 自动判定（区域级 aliyuncs.com → path-style；"
            "<bucket>. 开头 → virtual-hosted；自定义域名 → /<key>），"
            "可用 --path-style / --virtual-hosted 覆盖；"
            "CanonicalizedResource 恒为 /<bucket>/<key>\n"
            "退出码：0 成功 / 2 参数或文件错误 / 3 凭据缺失 / 4 HTTP 非 2xx / 5 --verify 失败"
        ),
    )
    parser.add_argument("paths", nargs="*", help="本地文件或目录（可多个）")
    parser.add_argument("--prefix", default=None,
                        help="key 前缀，如 pages/ 或 prd/；目录上传时按相对路径追加到其后")
    parser.add_argument("--bucket", default=None, help="bucket 名，默认 demoddys")
    parser.add_argument("--region", default=None, help="region，默认 oss-cn-shanghai")
    parser.add_argument("--endpoint", default=None,
                        help="https://host / http://host / host / host:port，"
                             "默认 <bucket>.<region>.aliyuncs.com")
    addressing = parser.add_mutually_exclusive_group()
    addressing.add_argument("--path-style", dest="path_style", action="store_true",
                            help="强制 path-style 寻址（请求 path = /<bucket>/<key>）")
    addressing.add_argument("--virtual-hosted", dest="virtual_hosted", action="store_true",
                            help="强制 virtual-hosted 寻址（请求 path = /<key>）")
    parser.add_argument("--content-type", dest="content_type", default=None,
                        help="强制 Content-Type（缺省按扩展名推断）")
    parser.add_argument("--access-key-id", dest="access_key_id", default=None,
                        help="AccessKeyId（仅临时/测试用，优先于其它来源）")
    parser.add_argument("--access-key-secret", dest="access_key_secret", default=None,
                        help="AccessKeySecret（仅临时/测试用，优先于其它来源）")
    parser.add_argument("--credentials-from", dest="credentials_from", default=None,
                        metavar="PATH",
                        help="从既有脚本运行时提取 AK/SK 的文件路径（只读；不复制密钥）")
    parser.add_argument("--public-base", dest="public_base", default=None,
                        help="公网访问域名前缀，默认 https://demo.ddys-inc.com/")
    parser.add_argument("--config", default=None,
                        help="配置文件路径，默认 ~/.pm-skill/config.yml")
    parser.add_argument("--oss-header", dest="oss_headers", action="append",
                        default=[], metavar="NAME=VALUE",
                        help="额外 x-oss-* 头（可重复），会参与 V1 签名")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP 超时秒数，默认 60")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印 method/URL/headers（密钥脱敏），不发请求")
    parser.add_argument("--print-signature", dest="print_signature", action="store_true",
                        help="额外打印 StringToSign 与签名，便于排查 403")
    parser.add_argument("--verify", action="store_true",
                        help="PUT 成功后用 HEAD 复核 Content-Type / Content-Length")
    parser.add_argument("--self-test", dest="self_test", action="store_true",
                        help="离线自检并退出")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="输出机器可读结果")
    parser.add_argument("--insecure-http", dest="insecure_http", action="store_true",
                        help="允许 http:// 端点（仅测试用，防误用）")
    return parser


def die(code: int, message: str) -> "None":
    print("错误：%s" % message, file=sys.stderr)
    sys.exit(code)


# ============================================================
# 上传任务
# ============================================================
class UploadTask:
    def __init__(self, local_path: Path, key: str, content_type: str):
        self.local_path = local_path
        self.key = key
        self.content_type = content_type


def collect_tasks(paths, prefix: str, forced_content_type, as_json: bool):
    """把输入路径展开成上传任务列表。目录按相对路径追加到 prefix 后。"""
    tasks = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            die(EXIT_USAGE, "路径不存在：%s" % raw)
        if path.is_file():
            key = prefix + path.name
            tasks.append(UploadTask(path, key,
                                    forced_content_type or guess_content_type(path)))
        elif path.is_dir():
            files = sorted(p for p in path.rglob("*") if p.is_file())
            if not files:
                print("警告：目录为空，已跳过：%s" % raw, file=sys.stderr)
                continue
            for file_path in files:
                rel = file_path.relative_to(path).as_posix()
                key = prefix + rel
                tasks.append(UploadTask(file_path, key,
                                        forced_content_type or guess_content_type(file_path)))
        else:
            die(EXIT_USAGE, "不是普通文件或目录：%s" % raw)
    if not tasks:
        die(EXIT_USAGE, "没有可上传的文件（请检查路径与目录内容）")
    return tasks


def normalize_prefix(prefix: str | None) -> str:
    if not prefix:
        return ""
    prefix = prefix.strip()
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return prefix


def resolve_endpoint(endpoint: str | None, bucket: str, region: str, insecure_http: bool):
    """解析 --endpoint，返回 (scheme, host[:port])。

    接受四种写法：`https://host`、`http://host`、`host`、`host:port`
    （也容忍 `https://host:port/` 这类带尾斜杠/路径的写法，路径部分会被丢弃）。
    不加 --insecure-http 时只允许 https。
    """
    raw = (endpoint or "").strip()
    if not raw:
        raw = "%s.%s.aliyuncs.com" % (bucket, region)
    scheme = "http" if insecure_http else "https"
    if "://" in raw:
        scheme_text, _, rest = raw.partition("://")
        scheme_text = scheme_text.strip().lower()
        if scheme_text not in ("http", "https"):
            die(EXIT_USAGE, "--endpoint 只支持 http:// 或 https:// 前缀：%s" % raw)
        if scheme_text == "http" and not insecure_http:
            die(EXIT_USAGE, "http:// 端点需要显式加 --insecure-http（仅测试用）")
        scheme, raw = scheme_text, rest
    host = raw.split("/", 1)[0].split("?", 1)[0].strip()
    if not host:
        die(EXIT_USAGE, "--endpoint 不能为空")
    return scheme, host


def detect_addressing(host: str, bucket: str, path_style: bool,
                      virtual_hosted: bool) -> str:
    """判定寻址方式：virtual-hosted / path-style / custom-domain。

    规则（--path-style / --virtual-hosted 显式覆盖优先）：
      * host 以 `<bucket>.` 开头 → virtual-hosted，请求 path = /<key>
      * 其它含 aliyuncs.com 的区域级/加速 endpoint → path-style，请求 path = /<bucket>/<key>
      * 其它 host（自定义域名，CNAME 已指向 bucket）→ custom-domain，请求 path = /<key>
    注意：无论哪种寻址方式，签名用的 CanonicalizedResource 恒为 /<bucket>/<key>。
    """
    if virtual_hosted:
        return "virtual-hosted"
    if path_style:
        return "path-style"
    host_only = host.split(":", 1)[0].lower()
    if bucket and host_only.startswith(bucket.lower() + "."):
        return "virtual-hosted"
    if "aliyuncs.com" in host_only:
        return "path-style"
    return "custom-domain"


def request_path(addressing: str, bucket: str, key: str) -> str:
    """实际请求的 URL path（已做 RFC 3986 编码）。"""
    encoded = encode_key_path(key)
    if addressing == "path-style":
        return "/" + bucket + "/" + encoded
    return "/" + encoded



def resolve_public_base(cli_value, config_value, bucket: str, region: str) -> str:
    if cli_value:
        base = cli_value
    elif config_value:
        base = config_value
    elif bucket == CUSTOM_DOMAIN_BUCKET and region == CUSTOM_DOMAIN_REGION:
        base = DEFAULT_PUBLIC_BASE
    else:
        base = "https://%s.%s.aliyuncs.com/" % (bucket, region)
    if not base.endswith("/"):
        base += "/"
    return base


def public_url(public_base: str, key: str) -> str:
    return public_base + encode_key_path(key)


def http_request(method: str, scheme: str, host: str, path: str,
                 headers: dict, body, timeout: float):
    """发一个请求，返回 (status, reason, header_items, body_bytes)。"""
    port = None
    host_only = host
    if ":" in host and not host.endswith("]"):
        host_only, _, port_text = host.rpartition(":")
        if port_text.isdigit():
            port = int(port_text)
        else:
            host_only, port = host, None
    if scheme == "https":
        conn = http.client.HTTPSConnection(
            host_only, port or 443, timeout=timeout,
            context=ssl.create_default_context())
    else:
        conn = http.client.HTTPConnection(host_only, port or 80, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        payload = resp.read()
        return resp.status, resp.reason, list(resp.getheaders()), payload
    finally:
        conn.close()


def header_lookup(header_items, name: str):
    target = name.lower()
    for key, value in header_items:
        if key.lower() == target:
            return value
    return None


def print_http_error_help(status: int, body_text: str) -> None:
    if status != 403:
        return
    print("\n403 常见原因（按概率排查）：", file=sys.stderr)
    print("  1. 时钟偏差：本机时间与 OSS 相差超过 15 分钟（响应含 RequestTimeTooSkewed）"
          "→ 校准系统时间或开启自动对时", file=sys.stderr)
    print("  2. 签名错误：AK/SK 不匹配、bucket/endpoint/region 不匹配、prefix 或 key 拼错"
          "→ 用 --dry-run --print-signature 核对 StringToSign 与 CanonicalizedResource",
          file=sys.stderr)
    print("  3. 权限不足：RAM 子账号缺少 oss:PutObject，或 bucket 不属于该账号"
          "→ 检查 RAM 授权策略", file=sys.stderr)
    if "RequestTimeTooSkewed" in body_text:
        print("  ⚠ 响应体明确包含 RequestTimeTooSkewed：优先校准本机时钟。", file=sys.stderr)


def format_string_to_sign_block(string_to_sign_value: str) -> str:
    return string_to_sign_value.replace("\n", "\\n")


def run_self_test() -> int:
    """离线自检：固定测试向量断言签名 / StringToSign / 时间格式 / URL 编码。

    预期签名值均由独立的 `openssl dgst -sha1 -hmac <secret> -binary | base64`
    交叉核对后写死。
    """
    # ---- 测试向量（AK/SK/Date/Content-Type/Content-MD5/key 全部固定） ----
    vectors = [
        {
            "name": "常规请求（ASCII key + Content-MD5 + 空 CanonicalizedOSSHeaders）",
            "access_key_id": "FAKESELFTESTAKID00000000",
            "access_key_secret": "SelfTestSecretKey0123456789abcdef",
            "bucket": "demoddys",
            "key": "pages/oss-upload-selftest.html",
            "verb": "PUT",
            "date": "Wed, 01 Jan 2025 00:00:00 GMT",
            "content_type": "text/html; charset=utf-8",
            "content_md5": "zV8cwH5b71/NJIAvPssJqA==",
            "body": b'<!DOCTYPE html>\n<html lang="zh-CN"><body>\xe4\xb8\xad\xe6\x96\x87 OSS self-test</body></html>\n',
            "oss_headers": {},
            "expected_string_to_sign": (
                "PUT\n"
                "zV8cwH5b71/NJIAvPssJqA==\n"
                "text/html; charset=utf-8\n"
                "Wed, 01 Jan 2025 00:00:00 GMT\n"
                "/demoddys/pages/oss-upload-selftest.html"
            ),
            "expected_signature": "I3WWCA7o+AdhDUUJlWTeS8ql4Q8=",
        },
        {
            "name": "中文 key（URL 编码 + 未编码签名）",
            "access_key_id": "FAKESELFTESTAKID00000000",
            "access_key_secret": "SelfTestSecretKey0123456789abcdef",
            "bucket": "demoddys",
            "key": "prd/PRD-名称-测试.html",
            "verb": "PUT",
            "date": "Thu, 15 May 2025 08:30:45 GMT",
            "content_type": "text/html; charset=utf-8",
            "content_md5": "1B2M2Y8AsgTpgAmY7PhCfg==",
            "oss_headers": {},
            "expected_string_to_sign": (
                "PUT\n"
                "1B2M2Y8AsgTpgAmY7PhCfg==\n"
                "text/html; charset=utf-8\n"
                "Thu, 15 May 2025 08:30:45 GMT\n"
                "/demoddys/prd/PRD-名称-测试.html"
            ),
            "expected_signature": "fWW/1CNIeZIJaWam8E68hbw8+ZI=",
        },
        {
            "name": "空 Content-MD5 + 空 Content-Type + 空 CanonicalizedOSSHeaders",
            "access_key_id": "FAKESELFTESTAKID00000000",
            "access_key_secret": "SelfTestSecretKey0123456789abcdef",
            "bucket": "demoddys",
            "key": "nav/index.html",
            "verb": "PUT",
            "date": "Fri, 20 Jun 2025 23:59:59 GMT",
            "content_type": "",
            "content_md5": "",
            "oss_headers": {},
            "expected_string_to_sign": (
                "PUT\n"
                "\n"
                "\n"
                "Fri, 20 Jun 2025 23:59:59 GMT\n"
                "/demoddys/nav/index.html"
            ),
            "expected_signature": "suqROWOWaHKXcN4heYllMNMcXVA=",
        },
        {
            "name": "非空 CanonicalizedOSSHeaders（含空格 + 中文 key，按小写升序）",
            "access_key_id": "FAKESELFTESTAKID00000000",
            "access_key_secret": "SelfTestSecretKey0123456789abcdef",
            "bucket": "demoddys",
            "key": "pages/a b/中文 文件.html",
            "verb": "PUT",
            "date": "Sat, 01 Mar 2025 12:00:00 GMT",
            "content_type": "text/html; charset=utf-8",
            "content_md5": "1B2M2Y8AsgTpgAmY7PhCfg==",
            "oss_headers": {
                "X-OSS-Meta-Source": "oss-upload-skill",
                "x-oss-storage-class": "Standard",
                "x-oss-meta-author": "dsh",
            },
            "expected_canonical_headers": (
                "x-oss-meta-author:dsh\n"
                "x-oss-meta-source:oss-upload-skill\n"
                "x-oss-storage-class:Standard\n"
            ),
            "expected_string_to_sign": (
                "PUT\n"
                "1B2M2Y8AsgTpgAmY7PhCfg==\n"
                "text/html; charset=utf-8\n"
                "Sat, 01 Mar 2025 12:00:00 GMT\n"
                "x-oss-meta-author:dsh\n"
                "x-oss-meta-source:oss-upload-skill\n"
                "x-oss-storage-class:Standard\n"
                "/demoddys/pages/a b/中文 文件.html"
            ),
            "expected_signature": "CQaFmoT2RvYneT67LRuZ5BjuR0U=",
        },
    ]

    # ---- 预期 URL 编码（写死） ----
    expected_encodings = [
        ("pages/oss-upload-selftest.html", "pages/oss-upload-selftest.html"),
        ("prd/PRD-名称-测试.html", "prd/PRD-%E5%90%8D%E7%A7%B0-%E6%B5%8B%E8%AF%95.html"),
        ("nav/index.html", "nav/index.html"),
        ("pages/a b/中文 文件.html",
         "pages/a%20b/%E4%B8%AD%E6%96%87%20%E6%96%87%E4%BB%B6.html"),
    ]

    checks = 0
    failures = []

    def check(label: str, actual, expected):
        nonlocal checks
        checks += 1
        if actual != expected:
            failures.append((label, actual, expected))

    # ---- 1. 签名 + StringToSign + 逐字符比对 ----
    for vec in vectors:
        oss_headers = vec["oss_headers"]
        if "body" in vec:
            check("[%s] Content-MD5 = base64(MD5(body))" % vec["name"],
                  md5_base64(vec["body"]), vec["content_md5"])
        canon = canonicalized_oss_headers(oss_headers)
        if "expected_canonical_headers" in vec:
            check("[%s] CanonicalizedOSSHeaders" % vec["name"],
                  canon, vec["expected_canonical_headers"])
        check("[%s] CanonicalizedResource" % vec["name"],
              canonicalized_resource(vec["bucket"], vec["key"]),
              "/%s/%s" % (vec["bucket"], vec["key"]))
        sts = string_to_sign(vec["verb"], vec["content_md5"], vec["content_type"],
                             vec["date"], oss_headers, vec["bucket"], vec["key"])
        check("[%s] StringToSign 逐字符" % vec["name"], sts, vec["expected_string_to_sign"])
        # 逐字符定位（在整体不等时给出首个差异位置）
        if sts != vec["expected_string_to_sign"]:
            for idx, (a, b) in enumerate(zip(sts, vec["expected_string_to_sign"])):
                if a != b:
                    failures.append(("[%s] StringToSign 首个差异位置 %d" % (vec["name"], idx),
                                     repr(a), repr(b)))
                    break
        sig = sign(vec["access_key_secret"], sts)
        check("[%s] Signature(base64)" % vec["name"], sig, vec["expected_signature"])
        auth = build_authorization(vec["access_key_id"], vec["access_key_secret"], sts)
        check("[%s] Authorization 形如 OSS <AK>:<base64>" % vec["name"],
              auth.startswith("OSS %s:" % vec["access_key_id"])
              and auth.rsplit(":", 1)[1] == vec["expected_signature"], True)

    # ---- 2. RFC 1123 时间格式 ----
    check("RFC1123 2025-01-01",
          format_rfc1123(datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)),
          "Wed, 01 Jan 2025 00:00:00 GMT")
    check("RFC1123 个位数日期补零",
          format_rfc1123(datetime(2025, 1, 5, 3, 4, 5, tzinfo=timezone.utc)),
          "Sun, 05 Jan 2025 03:04:05 GMT")
    check("RFC1123 与 email.utils 解析互相印证",
          format_rfc1123(_parse_rfc1123("Fri, 20 Jun 2025 23:59:59 GMT")),
          "Fri, 20 Jun 2025 23:59:59 GMT")

    # ---- 3. 中文 key URL 编码 ----
    for raw_key, expected_encoded in expected_encodings:
        encoded = encode_key_path(raw_key)
        check("URL 编码 %s" % raw_key, encoded, expected_encoded)
        check("URL 编码后无原始中文字节：%s" % raw_key,
              all(ord(ch) < 128 for ch in encoded), True)
    check("签名使用未编码 key（含中文）",
          canonicalized_resource("demoddys", "prd/PRD-名称-测试.html"),
          "/demoddys/prd/PRD-名称-测试.html")

    # ---- 4. Content-Type 推断 ----
    check(".html Content-Type",
          guess_content_type(Path("a.html")), "text/html; charset=utf-8")
    check(".htm Content-Type",
          guess_content_type(Path("a.htm")), "text/html; charset=utf-8")
    check(".css Content-Type",
          guess_content_type(Path("a.css")), "text/css; charset=utf-8")
    check(".png Content-Type",
          guess_content_type(Path("a.png")), "image/png")

    # ---- 5. 配置文件最小解析 ----
    check("config.yml oss: 段最小解析",
          _selftest_parse_config(), {
              "access_key_id": "FAKECONFIGAKID0000000000",
              "access_key_secret": "ConfigSecret",
              "bucket": "demoddys",
              "region": "oss-cn-shanghai",
              "public_base": "https://demo.ddys-inc.com/",
              "_legacy_secret_keys": ["accessKeyId", "accessKeySecret"],
          })
    check("config.yml 缺 oss: 段返回空",
          load_config(_write_selftest_config("repoRoot: /tmp/x\n")), {})
    check("config.yml 非密钥字段（endpoint/credentialsFrom）",
          load_config(_write_selftest_config(
              "oss:\n"
              "  bucket: demoddys\n"
              "  endpoint: https://oss-cn-shanghai.aliyuncs.com\n"
              "  credentialsFrom: /tmp/some_legacy_script.js\n")),
          {"bucket": "demoddys",
           "endpoint": "https://oss-cn-shanghai.aliyuncs.com",
           "credentials_from": "/tmp/some_legacy_script.js"})

    # ---- 6. --endpoint 四种写法 ----
    check("endpoint https://host",
          resolve_endpoint("https://oss-cn-shanghai.aliyuncs.com",
                           "demoddys", "oss-cn-shanghai", False),
          ("https", "oss-cn-shanghai.aliyuncs.com"))
    check("endpoint http://host:port + --insecure-http",
          resolve_endpoint("http://127.0.0.1:8123", "demoddys", "oss-cn-shanghai", True),
          ("http", "127.0.0.1:8123"))
    check("endpoint host（默认 scheme 取决于 --insecure-http）",
          resolve_endpoint("oss-cn-shanghai.aliyuncs.com", "demoddys", "oss-cn-shanghai", False),
          ("https", "oss-cn-shanghai.aliyuncs.com"))
    check("endpoint host:port",
          resolve_endpoint("127.0.0.1:8123", "demoddys", "oss-cn-shanghai", True),
          ("http", "127.0.0.1:8123"))
    check("endpoint 尾斜杠/路径被丢弃",
          resolve_endpoint("https://demoddys.oss-cn-shanghai.aliyuncs.com/",
                           "demoddys", "oss-cn-shanghai", False),
          ("https", "demoddys.oss-cn-shanghai.aliyuncs.com"))

    # ---- 7. 寻址方式自动判定 + 显式覆盖 + 请求 path ----
    selftest_key = "ai-auction-analysis/v1-售前分析/页面 面.html"
    encoded_key = encode_key_path(selftest_key)
    addressing_cases = [
        # (host, bucket, --path-style, --virtual-hosted, 期望寻址, 期望请求 path)
        ("oss-cn-shanghai.aliyuncs.com", "demoddys", False, False,
         "path-style", "/demoddys/" + encoded_key),
        ("demoddys.oss-cn-shanghai.aliyuncs.com", "demoddys", False, False,
         "virtual-hosted", "/" + encoded_key),
        ("demo.ddys-inc.com", "demoddys", False, False,
         "custom-domain", "/" + encoded_key),
        ("oss-cn-shanghai.aliyuncs.com", "demoddys", False, True,
         "virtual-hosted", "/" + encoded_key),
        ("demo.ddys-inc.com", "demoddys", True, False,
         "path-style", "/demoddys/" + encoded_key),
        ("oss-accelerate.aliyuncs.com", "demoddys", False, False,
         "path-style", "/demoddys/" + encoded_key),
        ("oss-cn-shanghai-internal.aliyuncs.com", "demoddys", False, False,
         "path-style", "/demoddys/" + encoded_key),
        ("demoddys.oss-cn-shanghai.aliyuncs.com:443", "demoddys", False, False,
         "virtual-hosted", "/" + encoded_key),
        ("127.0.0.1:8123", "demoddys", True, False,
         "path-style", "/demoddys/" + encoded_key),
    ]
    for host, bucket_name, force_path, force_virtual, exp_addr, exp_path in addressing_cases:
        addressing = detect_addressing(host, bucket_name, force_path, force_virtual)
        check("寻址判定 %s（path-style=%s virtual-hosted=%s）"
              % (host, force_path, force_virtual), addressing, exp_addr)
        check("请求 path %s → %s" % (host, exp_addr),
              request_path(addressing, bucket_name, selftest_key), exp_path)
        # 关键不变式：任何寻址方式下 CanonicalizedResource 都是未编码的 /<bucket>/<key>
        check("CanonicalizedResource 与寻址无关 %s" % host,
              canonicalized_resource(bucket_name, selftest_key),
              "/demoddys/" + selftest_key)
    check("CanonicalizedResource 不含百分号编码",
          "%" not in canonicalized_resource("demoddys", selftest_key), True)
    check("path-style 请求 path 含 bucket 且其余部分已编码",
          request_path("path-style", "demoddys", selftest_key),
          "/demoddys/ai-auction-analysis/v1-%E5%94%AE%E5%89%8D%E5%88%86%E6%9E%90/"
          "%E9%A1%B5%E9%9D%A2%20%E9%9D%A2.html")

    # ---- 8. 凭据解析：从既有脚本提取（单双引号 / 无引号） ----
    check("JS 凭据解析（单引号 + 双引号）",
          parse_js_credentials(
              "const accessKeyId = 'FAKE-SelfTest-AkId';\n"
              'const accessKeySecret = "FAKE-SelfTest-Secret";\n'),
          {"access_key_id": "FAKE-SelfTest-AkId",
           "access_key_secret": "FAKE-SelfTest-Secret"})
    check("JS 凭据解析（无引号 + 冒号写法）",
          parse_js_credentials(
              "module.exports = {\n"
              "  accessKeyId: FAKE-NoQuote-AkId,\n"
              "  accessKeySecret: FAKE-NoQuote-Secret,\n"
              "};\n"),
          {"access_key_id": "FAKE-NoQuote-AkId",
           "access_key_secret": "FAKE-NoQuote-Secret"})
    check("JS 凭据解析取第一个匹配",
          parse_js_credentials(
              "accessKeyId: 'FAKE-First-AkId'\n"
              "accessKeyId: 'FAKE-Second-AkId'\n"),
          {"access_key_id": "FAKE-First-AkId"})
    check("JS 凭据解析：未出现 accessKeySecret 时不返回该键",
          parse_js_credentials("accessKeyId: 'FAKE-Only-AkId'\n"),
          {"access_key_id": "FAKE-Only-AkId"})
    check("JS 凭据解析：两个键都没有 → 空 dict",
          parse_js_credentials("const other = 1;\n"), {})

    # ---- 9. 脱敏：注册后的 SK/AK 不会原样出现在文本里 ----
    register_secret("FAKE-Selftest-Secret-Value")
    register_access_key_id("FAKE-Selftest-AkId-Value")
    check("脱敏抹掉 SK 明文",
          redact("Authorization: OSS FAKE-Selftest-AkId-Value:FAKE-Selftest-Secret-Value"),
          "Authorization: OSS FAKE****:****")
    check("脱敏后文本不含原 SK",
          "FAKE-Selftest-Secret-Value" in redact("含 FAKE-Selftest-Secret-Value 的报错"), False)

    # ---- 输出 ----
    if failures:
        print("SELF-TEST FAILED：%d/%d 项断言失败" % (len(failures), checks), file=sys.stderr)
        for label, actual, expected in failures:
            print("  ✗ %s\n      实际: %r\n      预期: %r" % (label, actual, expected),
                  file=sys.stderr)
        return 1
    print("SELF-TEST PASSED：%d 项断言全部通过" % checks)
    print("向量数：%d（含中文 key / Content-MD5 / 空 OSS 头 / 非空 OSS 头）" % len(vectors))
    for vec in vectors:
        print("  ✔ %s\n      StringToSign=%s\n      Signature=%s"
              % (vec["name"],
                 format_string_to_sign_block(vec["expected_string_to_sign"]),
                 vec["expected_signature"]))
    return 0


def _parse_rfc1123(value: str) -> datetime:
    from email.utils import parsedate_to_datetime
    return parsedate_to_datetime(value)


def _write_selftest_config(text: str) -> Path:
    tmp = Path("/tmp") / "oss_upload_selftest_config.yml"
    try:
        tmp.write_text(text, encoding="utf-8")
        return tmp
    except OSError:
        return Path("/nonexistent/oss-upload-selftest.yml")


def _selftest_parse_config() -> dict:
    text = (
        "repoRoot: /tmp/repo\n"
        "# 注释行\n"
        "oss:\n"
        "  accessKeyId: 'FAKECONFIGAKID0000000000'\n"
        "  accessKeySecret: ConfigSecret\n"
        "  bucket: demoddys\n"
        "  region: oss-cn-shanghai\n"
        "  publicBase: https://demo.ddys-inc.com/   # 自定义域名\n"
        "  ignoredKey: should-not-appear\n"
        "knowledgeBase: \"\"\n"
    )
    return load_config(_write_selftest_config(text))


# ============================================================
# 主流程
# ============================================================
def resolve_settings(args):
    config_path = Path(os.path.expanduser(args.config or DEFAULT_CONFIG_PATH))
    config = load_config(config_path)

    access_key_id = args.access_key_id
    access_key_secret = args.access_key_secret
    sources = []
    register_access_key_id(access_key_id)
    register_secret(access_key_secret)
    if access_key_id or access_key_secret:
        sources.append("命令行参数")

    # ---- 2) 环境变量：OSS_ACCESS_KEY_ID/SECRET 优先，其次用户既有脚本的 OSS_AK_ID/OSS_AK_SECRET ----
    if not (access_key_id and access_key_secret):
        for id_name, secret_name in (("OSS_ACCESS_KEY_ID", "OSS_ACCESS_KEY_SECRET"),
                                     ("OSS_AK_ID", "OSS_AK_SECRET")):
            env_id = os.environ.get(id_name)
            env_secret = os.environ.get(secret_name)
            register_access_key_id(env_id)
            register_secret(env_secret)
            if not access_key_id and env_id:
                access_key_id = env_id
                sources.append("环境变量 %s" % id_name)
            if not access_key_secret and env_secret:
                access_key_secret = env_secret
            if access_key_id and access_key_secret:
                break

    # ---- 3) 从既有脚本运行时提取（只存路径，不存密钥） ----
    credentials_from = (args.credentials_from
                        or os.environ.get("OSS_CREDENTIALS_FROM")
                        or config.get("credentials_from"))
    credentials_from_explicit = bool(args.credentials_from
                                     or os.environ.get("OSS_CREDENTIALS_FROM"))
    if credentials_from and (credentials_from_explicit
                             or not (access_key_id and access_key_secret)):
        parsed = load_credentials_from_file(credentials_from)
        if not access_key_id:
            access_key_id = parsed["access_key_id"]
        if not access_key_secret:
            access_key_secret = parsed["access_key_secret"]
        sources.append("凭据来源文件 %s" % credentials_from)

    # ---- 4) 配置文件 oss: 段的旧式密钥（兼容，但提示不推荐） ----
    legacy_keys = config.get("_legacy_secret_keys") or []
    if legacy_keys:
        print("提示：配置文件 %s 的 oss: 段里存在 %s。不建议把密钥写进配置文件"
              "（明文落盘易泄露），建议改用环境变量"
              "（OSS_ACCESS_KEY_ID/OSS_ACCESS_KEY_SECRET 或 OSS_AK_ID/OSS_AK_SECRET）"
              "或 oss.credentialsFrom/--credentials-from 指向既有脚本（见技能文档 SKILL.md）。"
              % (config_path, " / ".join(legacy_keys)), file=sys.stderr)
        register_access_key_id(config.get("access_key_id"))
        register_secret(config.get("access_key_secret"))
        if not access_key_id and config.get("access_key_id"):
            access_key_id = config.get("access_key_id")
            sources.append("配置文件 oss.accessKeyId（旧式，不推荐）")
        if not access_key_secret and config.get("access_key_secret"):
            access_key_secret = config.get("access_key_secret")

    bucket = (args.bucket
              or os.environ.get("OSS_BUCKET")
              or config.get("bucket")
              or DEFAULT_BUCKET)
    region = (args.region
              or os.environ.get("OSS_REGION")
              or config.get("region")
              or DEFAULT_REGION)

    if not access_key_id or not access_key_secret:
        missing = []
        if not access_key_id:
            missing.append("AccessKeyId")
        if not access_key_secret:
            missing.append("AccessKeySecret")
        print("错误：缺少 OSS 凭据（%s）" % "、".join(missing), file=sys.stderr)
        print("凭据来源优先级（任选其一）：", file=sys.stderr)
        print("  1) 命令行参数：--access-key-id / --access-key-secret（仅临时/测试用）",
              file=sys.stderr)
        print("  2) 环境变量：OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET，"
              "或用户既有脚本的 OSS_AK_ID / OSS_AK_SECRET", file=sys.stderr)
        print("  3) 从既有脚本运行时提取（推荐）：--credentials-from <脚本路径>，"
              "或环境变量 OSS_CREDENTIALS_FROM=<脚本路径>，"
              "或配置文件 oss.credentialsFrom: <脚本路径>", file=sys.stderr)
        print("  4) 配置文件 %s 的 oss: 段（仅兼容旧配置，不建议写密钥；"
              "非密钥字段 bucket/region/endpoint/publicBase/credentialsFrom 可照常用）"
              % config_path, file=sys.stderr)
        print("提示：无凭据时不要阻塞交付，改用本地 HTTP 预览"
              "（python3 -m http.server <port>），并在交付说明中注明「未上传 OSS」。",
              file=sys.stderr)
        sys.exit(EXIT_CREDENTIALS)

    scheme, host = resolve_endpoint(args.endpoint or config.get("endpoint"),
                                    bucket, region, args.insecure_http)
    addressing = detect_addressing(host, bucket, args.path_style, args.virtual_hosted)
    public_base = resolve_public_base(args.public_base, config.get("public_base"),
                                      bucket, region)

    oss_headers = {}
    for item in args.oss_headers or []:
        if "=" not in item:
            die(EXIT_USAGE, "--oss-header 需要 NAME=VALUE 格式：%s" % item)
        name, _, value = item.partition("=")
        oss_headers[name.strip()] = value.strip()

    return {
        "access_key_id": access_key_id,
        "access_key_secret": access_key_secret,
        "bucket": bucket,
        "region": region,
        "scheme": scheme,
        "host": host,
        "addressing": addressing,
        "public_base": public_base,
        "oss_headers": oss_headers,
        "config_path": config_path,
        "credentials_from": credentials_from or "",
        "credentials_sources": sources,
    }


def process_task(task: UploadTask, settings: dict, args) -> dict:
    """返回单个文件的结果字典（不退出，由调用方汇总退出码）。"""
    body = task.local_path.read_bytes()
    content_md5 = md5_base64(body)
    date = rfc1123_now()
    sts = string_to_sign("PUT", content_md5, task.content_type, date,
                         settings["oss_headers"], settings["bucket"], task.key)
    signature = sign(settings["access_key_secret"], sts)
    auth = build_authorization(settings["access_key_id"],
                               settings["access_key_secret"], sts)

    # 请求 path 随寻址方式变化；签名用的 CanonicalizedResource 恒为 /<bucket>/<key>
    canonical = canonicalized_resource(settings["bucket"], task.key)
    path = request_path(settings["addressing"], settings["bucket"], task.key)
    url = "%s://%s%s" % (settings["scheme"], settings["host"], path)
    request_headers = {
        "Date": date,
        "Content-Type": task.content_type,
        "Content-MD5": content_md5,
        "Content-Length": str(len(body)),
        "Authorization": auth,
    }
    for name, value in settings["oss_headers"].items():
        request_headers[name] = value

    result = {
        "local": str(task.local_path),
        "key": task.key,
        "method": "PUT",
        "url": url,
        "requestPath": path,
        "canonicalizedResource": canonical,
        "addressing": settings["addressing"],
        "publicUrl": public_url(settings["public_base"], task.key),
        "contentType": task.content_type,
        "contentMd5": content_md5,
        "size": len(body),
        "httpStatus": None,
        "verify": "skipped",
        "ok": True,
        "dryRun": bool(args.dry_run),
        "error": None,
    }
    if args.print_signature:
        result["stringToSign"] = sts
        result["signature"] = signature

    if not args.as_json:
        print("[%s] PUT %s" % ("DRY-RUN" if args.dry_run else "上传", url))
        print("    key: %s" % task.key)
        print("    寻址: %s  （请求 path = %s）" % (settings["addressing"], path))
        print("    CanonicalizedResource（签名用，恒为未编码 /<bucket>/<key>）: %s" % canonical)
        print("    Date: %s" % date)
        print("    Content-Type: %s" % task.content_type)
        print("    Content-MD5: %s" % content_md5)
        print("    Content-Length: %d" % len(body))
        print("    Authorization: %s" % mask_authorization(
            settings["access_key_id"], signature))
        for name, value in settings["oss_headers"].items():
            print("    %s: %s" % (name, value))
        if args.print_signature:
            print("    StringToSign: %s" % format_string_to_sign_block(sts))
            print("    Signature: %s" % signature)

    if args.dry_run:
        result["verify"] = "skipped"
        if not args.as_json:
            print("    → 公网地址（预期）: %s" % result["publicUrl"])
        return result

    try:
        status, reason, header_items, payload = http_request(
            "PUT", settings["scheme"], settings["host"], path,
            request_headers, body, args.timeout)
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        result.update(ok=False, httpStatus=None,
                      error="网络错误：%s" % exc)
        if not args.as_json:
            print("    ✗ 请求失败：%s" % exc, file=sys.stderr)
        return result

    result["httpStatus"] = status
    body_text = payload.decode("utf-8", errors="replace") if payload else ""
    if not (200 <= status < 300):
        result.update(ok=False, error="HTTP %d %s: %s" % (status, reason, body_text.strip()))
        if not args.as_json:
            print("    ✗ 上传失败：HTTP %d %s" % (status, reason), file=sys.stderr)
            if body_text.strip():
                print("    响应体：%s" % body_text.strip(), file=sys.stderr)
            print_http_error_help(status, body_text)
        return result

    if not args.as_json:
        print("    ✔ 上传成功（HTTP %d）" % status)
        print("    → 公网地址: %s" % result["publicUrl"])

    if args.verify:
        head_date = rfc1123_now()
        head_sts = string_to_sign("HEAD", "", "", head_date, {}, settings["bucket"], task.key)
        head_headers = {
            "Date": head_date,
            "Authorization": build_authorization(
                settings["access_key_id"], settings["access_key_secret"], head_sts),
        }
        try:
            h_status, h_reason, h_items, h_payload = http_request(
                "HEAD", settings["scheme"], settings["host"], path,
                head_headers, None, args.timeout)
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            result.update(ok=False, verify="failed",
                          error="--verify HEAD 失败：%s" % exc)
            return result

        if not (200 <= h_status < 300):
            result.update(ok=False, verify="failed",
                          error="--verify HEAD 返回 HTTP %d %s" % (h_status, h_reason))
            if not args.as_json:
                print("    ✗ --verify 失败：HEAD 返回 HTTP %d %s"
                      % (h_status, h_reason), file=sys.stderr)
            return result

        remote_type = (header_lookup(h_items, "Content-Type") or "").strip()
        remote_len = (header_lookup(h_items, "Content-Length") or "").strip()
        problems = []
        if _normalize_content_type(remote_type) != _normalize_content_type(task.content_type):
            problems.append("Content-Type 不一致：远端 %r / 本地 %r"
                            % (remote_type, task.content_type))
        if remote_len != str(len(body)):
            problems.append("Content-Length 不一致：远端 %r / 本地 %d"
                            % (remote_len, len(body)))
        if problems:
            result.update(ok=False, verify="failed", error="；".join(problems))
            if not args.as_json:
                for problem in problems:
                    print("    ✗ --verify 失败：%s" % problem, file=sys.stderr)
        else:
            result["verify"] = "passed"
            if not args.as_json:
                print("    ✔ --verify 通过（Content-Type=%s, Content-Length=%s）"
                      % (remote_type, remote_len))
    return result


def _normalize_content_type(value: str) -> str:
    return " ".join((value or "").split()).lower()


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if not args.paths:
        parser.print_usage(sys.stderr)
        print("错误：请至少指定一个本地文件或目录（或使用 --self-test）", file=sys.stderr)
        return EXIT_USAGE

    settings = resolve_settings(args)
    prefix = normalize_prefix(args.prefix)
    tasks = collect_tasks(args.paths, prefix, args.content_type, args.as_json)

    if not args.as_json:
        print("bucket=%s region=%s endpoint=%s://%s 寻址=%s"
              % (settings["bucket"], settings["region"],
                 settings["scheme"], settings["host"], settings["addressing"]))
        print("prefix=%r 文件数=%d%s"
              % (prefix, len(tasks), "  [DRY-RUN 不发请求]" if args.dry_run else ""))

    results = []
    http_failure = False
    verify_failure = False
    for task in tasks:
        result = process_task(task, settings, args)
        results.append(result)
        if result["ok"]:
            continue
        if result.get("verify") == "failed":
            verify_failure = True
        else:
            http_failure = True
    # 退出码优先级：HTTP 失败(4) > --verify 失败(5) > 成功(0)
    worst = EXIT_HTTP if http_failure else (EXIT_VERIFY if verify_failure else EXIT_OK)

    if args.as_json:
        print(json.dumps({
            "bucket": settings["bucket"],
            "region": settings["region"],
            "endpoint": "%s://%s" % (settings["scheme"], settings["host"]),
            "addressing": settings["addressing"],
            "publicBase": settings["public_base"],
            "credentialsFrom": settings["credentials_from"],
            "credentialsSources": settings["credentials_sources"],
            "prefix": prefix,
            "dryRun": bool(args.dry_run),
            "exitCode": worst,
            "results": results,
        }, ensure_ascii=False, indent=2))

    if not args.as_json and not args.dry_run:
        failed = [r for r in results if not r["ok"]]
        print("\n汇总：成功 %d / 失败 %d" % (len(results) - len(failed), len(failed)))
    return worst


if __name__ == "__main__":
    sys.exit(main())
