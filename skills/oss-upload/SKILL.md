---
name: oss-upload
description: >
  阿里云 OSS 上传。把本地文件或目录上传到 OSS 并返回公网可访问链接，覆盖签名、Content-Type、目录前缀映射与上传后校验。
  当需要部署 HTML 原型、上传 PRD 在线浏览页/导航页、生成可分享链接，或排查 OSS 上传 403/签名/下载而非渲染等问题时使用。
---

# 阿里云 OSS 上传 Skill

用**纯 Python 标准库**实现的 OSS V1 签名 PUT 上传，零第三方依赖（不需要 `node` / `ali-oss` / `oss2`）。
本仓库其它技能（`html-prototype` / `prd-writer` / `prd-sync`）需要上传 OSS 时统一调用本技能。

## 触发条件

- 生成/修改 HTML 原型、PRD 在线浏览页、导航页后需要**公网可访问链接**
- 需要把本地文件或整个目录发布到 OSS（含中文文件名）
- OSS 上传报 403、`RequestTimeTooSkewed`，或浏览器**下载而不是渲染**页面

## 运行时

本机唯一可用（且只用标准库，无需联网安装）：

```
$HOME/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
```

下文统一用 `$PY` 代指；若 `python3` 在 PATH 中能找到（Python 3.8+），也可直接用 `python3`。

```bash
PY=$HOME/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
SKILL=$REPO/skills/oss-upload
```

> 上面两个路径是**本机的值**，换机器需要替换：`PY` 是 DSH 随附的 Python（`$DSH_HOME/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3`），`SKILL` 是本仓库的克隆路径（即 `~/.pm-skill/config.yml` 里的 `repoRoot`）+ `/skills/oss-upload`。脚本本身零第三方依赖，任何 Python 3.8+ 都能跑。

## 怎么用（可直接复制）

**先离线自检**（不联网、不需要凭据，验证签名算法与编码正确）：
```bash
"$PY" "$SKILL/scripts/oss_upload.py" --self-test
```

**上传单个文件**（`.html` 自动用 `text/html; charset=utf-8`；`--prefix` 必须用**本项目**的既有上传前缀）：
```bash
"$PY" "$SKILL/scripts/oss_upload.py" \
  "/absolute/path/prototype/pages/user-web-query-lawyer.html" \
  --prefix "ai-auction-analysis/v1-售前分析/" \
  --verify
# → https://demo.ddys-inc.com/ai-auction-analysis/v1-售前分析/user-web-query-lawyer.html
```

**上传 PRD 在线浏览页**：
```bash
"$PY" "$SKILL/scripts/oss_upload.py" \
  "/absolute/path/prd/PRD-名称.html" \
  --prefix "ai-auction-analysis/v1-售前分析/" --verify
```

**上传整个目录**（目录内相对路径追加到 `--prefix` 之后，含子目录与中文名）：
```bash
"$PY" "$SKILL/scripts/oss_upload.py" \
  "/absolute/path/prototype/{project-id}/{iteration-id}/prototype" \
  --prefix "ai-auction-analysis/v1-售前分析/" --verify --json
```

**只演练不发请求**（密钥脱敏，可核对 URL / 请求头 / StringToSign）：
```bash
"$PY" "$SKILL/scripts/oss_upload.py" "/absolute/path/x.html" \
  --prefix "ai-auction-analysis/v1-售前分析/" --dry-run --print-signature
```

### 上传前缀（按项目，不要另起目录）

| 项目 | 前缀 |
|------|------|
| 本项目（AI 拍卖分析） | `ai-auction-analysis/v1-售前分析/` |
| ddys 数据产品 | `ddys-data/v1-首期/` |
| 家融 CRM | `jiarong-crm/` |
| 这里查 / 这里拍等 | 沿用既有线上目录（`zhelicha` 各版本目录等），不要另起 |

前缀与线上目录是**共享资源**：改总导航或大范围重传前，先与线上 `index.html` diff 确认无他人改动，并先备份。

## 默认配置

| 项 | 本机默认值 | 覆盖方式 |
|----|-----------|---------|
| bucket | `demoddys` | `--bucket` / `OSS_BUCKET` / 配置文件 `bucket` |
| region | `oss-cn-shanghai` | `--region` / `OSS_REGION` / 配置文件 `region` |
| endpoint（调用 API） | 留空 → `<bucket>.<region>.aliyuncs.com`（virtual-hosted，已实测 HTTP 200；**本 bucket 禁止 path-style**，见下） | `--endpoint` / 配置文件 `endpoint`（对本 bucket 请勿设置） |
| 自定义域名（公网入口，匿名可读） | `https://demo.ddys-inc.com/` | `--public-base` / 配置文件 `publicBase` |
| 对象直连 URL 形态 | `https://demoddys.oss-cn-shanghai.aliyuncs.com/<key>` | 由 bucket/region 推出 |

### 寻址方式 —— 本 bucket 只能用 virtual-hosted

🔴 **实测结论（2026-10-09，用真实凭据做只读签名 HEAD 探测）**：`demoddys` 这个 bucket **禁止**区域级 endpoint / path-style：

| 请求形态 | 实测结果 |
|---|---|
| Host=`demoddys.oss-cn-shanghai.aliyuncs.com`，path=`/index.html` | **HTTP 200**（Content-Type `text/html; charset=utf-8`）✓ |
| Host=`oss-cn-shanghai.aliyuncs.com`，path=`/demoddys/index.html` | HTTP 403，`SecondLevelDomainForbidden`：*must be addressed using OSS third level domain* |

**所以 `--endpoint` 必须留空**，走 `<bucket>.<region>.aliyuncs.com`。不要为了"对齐控制台上的 Endpoint"去填区域级地址——对本 bucket 无效。

脚本的自动判定规则（其它 bucket 可参考）：

| endpoint host | 寻址方式 | 请求 path |
|---|---|---|
| `<bucket>.oss-<region>.aliyuncs.com` | virtual-hosted | `/<key>` |
| `oss-<region>.aliyuncs.com`（区域级） | path-style | `/<bucket>/<key>`（**本 bucket 会 403**） |
| `demo.ddys-inc.com`（自定义域名 CNAME） | virtual-hosted | `/<key>` |

可用 `--path-style` / `--virtual-hosted` 强制覆盖。**`CanonicalizedResource` 恒为 `/<bucket>/<key>`**，与寻址方式无关。

## 凭据配置（🔴 不产生新的明文副本）

**密钥不写进本仓库，也不写进 `~/.pm-skill/config.yml`。** 运行时按下面的顺序解析（前面的优先）：

| 优先级 | 来源 | 键 |
|:-----:|------|-----|
| 1 | 命令行参数（仅临时/测试用） | `--access-key-id` / `--access-key-secret` |
| 2 | 环境变量 | `OSS_AK_ID` / `OSS_AK_SECRET`，或 `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET` |
| 3 | 既有脚本运行时提取 | `--credentials-from <path>` / `OSS_CREDENTIALS_FROM` / 配置文件 `credentialsFrom` |

第 3 项从**既有上传脚本**里读 `accessKeyId` / `accessKeySecret`（各取第一个匹配），密钥只在进程内存中流转：

```bash
# 本机配置已指向既有脚本，直接跑即可
"$PY" "$SKILL/scripts/oss_upload.py" <本地文件> --prefix "<项目前缀>" --verify

# 或用环境变量注入
OSS_AK_ID=xxx OSS_AK_SECRET=xxx \
  "$PY" "$SKILL/scripts/oss_upload.py" <本地文件> --prefix "<项目前缀>" --verify
```

`~/.pm-skill/config.yml` 的 `oss:` 段**只放非密钥字段**：

```yaml
oss:
  bucket: demoddys
  region: oss-cn-shanghai
  endpoint: https://oss-cn-shanghai.aliyuncs.com
  publicBase: https://demo.ddys-inc.com/
  credentialsFrom: /path/to/_upload_index.js
```

🔴 **安全约束（必须遵守）**
- **不打印、不复制、不回显密钥**：不要 `cat` / `grep` 既有脚本把明文贴进对话、PRD、交付说明、日志或命令回显——会话记录会被导出。
- 新工具一律**运行时读取**（环境变量或 `credentialsFrom`），不要为省事把 SK 拷进新文件。
- 脚本保证：SecretKey 在任何输出（含 `--dry-run` / `--json` / 错误信息）中都不出现；AccessKeyId 最多显示前 4 位 + `****`。
- **这对密钥已在多个脚本与会话记录中明文出现，建议尽快轮换**；轮换后只需改 `_upload_index.js` 一处，其余脚本都是运行时读取。
- 长期建议：改用**只授权 `demoddys`、只给 `oss:PutObject` + `oss:GetObject`** 的 RAM 子账号，不要用主账号 AK（也不要 `oss:*` / `oss:DeleteObject`）。

## 🔴 无凭据时的降级（次级备选，不阻断）

**交付完成的标志是线上 URL**（`https://demo.ddys-inc.com/...`），不是 localhost。缺凭据（脚本退出码 3）时：

1. **先排查凭据路径**：`credentialsFrom` 指向的既有脚本是否还在、是否仍能解析出 `accessKeyId` / `accessKeySecret`（**不要打印值**）。能修就修——优先恢复真实上传，而不是直接降级。
2. 确实拿不到凭据时才降级为本地预览：`python3 -m http.server 8080 --directory <原型目录>`
3. 降级说明必须写清「**未上传 OSS，交付未完成**」+ 缺的是哪个来源 + 恢复上传需要做什么。
4. **本地预览地址不得占用原型导航页的主链接位**（导航页保留仓库内相对路径），本地地址只作次级备注。

## 命令行参数

| 参数 | 说明 |
|------|------|
| `<本地文件或目录>...` | 可多个；目录递归上传，相对路径追加到 `--prefix` 后 |
| `--prefix` | key 前缀（如 `pages/`、`prd/`）；缺尾 `/` 时自动补 |
| `--bucket` / `--region` | 默认 `demoddys` / `oss-cn-shanghai` |
| `--endpoint` | `https://host` / `http://host` / `host` / `host:port`；缺省由 bucket+region 推导 |
| `--path-style` / `--virtual-hosted` | 强制寻址方式（互斥）；缺省按 endpoint host 自动判定 |
| `--credentials-from` | 从既有脚本**运行时**提取 AK/SK（只传路径，不传密钥明文） |
| `--public-base` | 覆盖公网地址前缀，默认 `https://demo.ddys-inc.com/` |
| `--content-type` | 强制 Content-Type；缺省按扩展名推断（`.html`/`.htm` → `text/html; charset=utf-8`，`.css`/`.js`/`.json`/`.png`… 见脚本 `TYPE_MAP`） |
| `--dry-run` | 只打印 method / URL / headers（AK 脱敏为前 4 位，SK 不出现），**不发请求** |
| `--print-signature` | 额外打印 StringToSign 与签名，排查 403 用 |
| `--verify` | PUT 成功后 HEAD 复核 Content-Type / Content-Length |
| `--self-test` | 离线自检（签名 / StringToSign / RFC1123 / URL 编码）后退出 |
| `--json` | 输出机器可读 JSON（含 `publicUrl` / `httpStatus` / `verify`），不打印人类可读日志 |
| `--insecure-http` | 允许 `http://` 端点（**仅测试**；不加时 `--endpoint` 只允许 https） |
| `--oss-header NAME=VALUE` | 额外 `x-oss-*` 头（可重复），会进入 `CanonicalizedOSSHeaders` 参与签名 |
| `--config` | 配置文件路径，默认 `~/.pm-skill/config.yml` |
| `--timeout` | HTTP 超时秒数，默认 60 |

**退出码**：

| 码 | 含义 |
|:-:|------|
| 0 | 成功（含 `--dry-run`） |
| 2 | 参数 / 文件错误（路径不存在、`http://` 未加 `--insecure-http`） |
| 3 | 凭据缺失 → 走上面的降级流程 |
| 4 | HTTP 非 2xx（响应体会打印出来） |
| 5 | `--verify` 复核失败 |

## key 映射规则

| 输入 | `--prefix` | 生成的 key |
|------|-----------|-----------|
| `user-web-query-lawyer.html` | `ai-auction-analysis/v1-售前分析/` | `ai-auction-analysis/v1-售前分析/user-web-query-lawyer.html` |
| `PRD-名称.html` | `ai-auction-analysis/v1-售前分析/` | `ai-auction-analysis/v1-售前分析/PRD-名称.html` |
| 目录 `prototype/`（含 `sub/a.html`） | `ai-auction-analysis/v1-售前分析/` | `…/sub/a.html` |
| 目录 `prototype/`（含 `子/页 面.html`） | `ai-auction-analysis/v1-售前分析/` | `…/子/页 面.html`（URL 上编码为 `%E5%AD%90/%E9%A1%B5%20%E9%9D%A2.html`） |
| 任意 | 不传 | 直接用文件名 / 相对路径（⚠️ 会落到 bucket 根目录，通常不该这样） |

- 签名用的 `CanonicalizedResource` 是**未编码**的 `/<bucket>/<key>`；实际请求 path 用 RFC 3986 编码（`quote(key, safe="/")`），中文文件名不会乱码。
- 目录上传忽略空目录；同一次调用内 key 冲突会互相覆盖（后上传者胜）。

## 🔴 上传后必须自检

1. 上传一律加 `--verify`：PUT 之后 HEAD 复核 `Content-Type` 与 `Content-Length`，**`--verify` 通过才算上传完成**（失败退出码 5，需排查后重传）。
2. **「放到总导航」= 发布到线上** `https://demo.ddys-inc.com/index.html`：原型 / PRD 改动后要重新上传并挂到总导航；**交付完成的标志是给出线上 URL，不是 localhost 预览地址**。
3. 总导航是**共享资源**，改动前：与线上 `index.html` diff 确认无他人改动 → 备份 → **只追加不重排** → diff 证明删除/修改行数符合预期 → 校验 DOM 契约 → 上传后回归其他项目 Tab。
4. 把返回的**公网链接**回填到 PRD 正文 / 在线浏览页 / 总导航页与迭代导航页（`prd-sync` 会校验回填是否遗漏）。
5. 交付说明中给出公网链接（自定义域名优先），不要给 OSS 直连域名。

```bash
# 通过即完成；失败退出码 5
"$PY" "$SKILL/scripts/oss_upload.py" "/abs/path/PRD-名称.html" --prefix prd/ --verify
```

## 常见故障排查

| 现象 / 退出码 | 根因 | 处理 |
|--------------|------|------|
| 403 `SignatureDoesNotMatch`（退出码 4） | AK/SK 或 bucket/endpoint/region 不匹配；prefix 或 key 拼错 | `--dry-run --print-signature` 核对 StringToSign 与 CanonicalizedResource；确认 AK/SK 属于该 bucket |
| 403 `RequestTimeTooSkewed` | 本机时钟与 OSS 相差超过 15 分钟 | 校准系统时间 / 开启自动对时后重传 |
| 403 `AccessDenied` | RAM 子账号缺少 `oss:PutObject`，或 bucket 不属于该账号 | 检查 RAM 授权策略（只给 `oss:PutObject` + `oss:GetObject`） |
| 浏览器**下载**而非渲染页面 | Content-Type 缺失或被写成 `application/octet-stream` | 确认 `.html` 为 `text/html; charset=utf-8`；用 `--verify` 复核远端 Content-Type |
| 中文文件名乱码 / 404 | key 未按 RFC 3986 编码，或签名单边编码 | 本脚本已正确处理（签名用原文、URL 编码）；不要手工拼 URL，直接用脚本输出的公网链接 |
| 退出码 5 | 上传成功但 HEAD 复核不一致 | 检查 CDN/回源是否改写了 Content-Type，或对象被同名覆盖 |
| 403 `SecondLevelDomainForbidden` | 用了区域级 endpoint / path-style，而本 bucket 强制三级域名寻址 | **`--endpoint` 留空**，不要设成 `https://oss-cn-shanghai.aliyuncs.com`（实测该形态 403） |
| 请求 path 少了 bucket（区域级 endpoint） | 寻址方式判定错，按 virtual-hosted 拼了路径 | 区域级 endpoint 必须生成 `/demoddys/<key>`；先 `--dry-run` 核对请求 URL，必要时加 `--path-style` |
| 退出码 3 | 无凭据 | 先排查 `credentialsFrom` 指向的既有脚本是否有效（不要打印值）；确实拿不到才按「无凭据时的降级」走本地预览（次级备选） |
| 退出码 2 且提示需要 `--insecure-http` | 传了 `http://` 端点 | 生产不要用 http；仅本地测试时显式加 `--insecure-http` |

## 自检（离线，不需要凭据与网络）

```bash
"$PY" "$SKILL/scripts/oss_upload.py" --self-test   # → SELF-TEST PASSED：36 项断言全部通过
```

断言内容：固定向量的签名值（与 `openssl dgst -sha1 -hmac` 独立核对后写死）、`StringToSign` 逐字符拼接、
`CanonicalizedOSSHeaders` 排序、RFC 1123 时间格式、中文 key 的 URL 编码、Content-Type 推断、配置文件最小解析。
任一断言失败即非零退出。
