# vendor/ — 本地供应商库（零 CDN）

本目录只放**本地固定版本**的第三方源码，供 `skills/prd-writer/scripts/render_prd_html.mjs`
在生成单文件 PRD 浏览页时**内联**进 HTML。产物不得出现任何指向 CDN / 远程地址的资源引用。

## marked.umd.js

| 项 | 值 |
|---|---|
| 库 | marked（Markdown → HTML） |
| 版本 | **18.1.0**（固定，不随 latest 漂移） |
| 发布物路径 | `lib/marked.umd.js`（官方 UMD 构建；该版本 npm 包内**没有** `marked.min.js`，`lib/marked.umd.js` 本身已是 esbuild 压缩构建） |
| 来源 URL（用于同步/校验） | https://cdn.jsdelivr.net/npm/marked@18.1.0/lib/marked.umd.js <br> https://unpkg.com/marked@18.1.0/lib/marked.umd.js |
| 大小 | 47225 字节 |
| sha256（hex） | `f424dcb508fdf93e0137a970cfce8f3207ea2e3f37eca5f7556a52875683632a` |
| sha256（base64 / SRI） | `9CTctQj9+T4BN6lwz86PMgfqLj837KX3VWpSh1aDYyo=`（与 jsDelivr 官方 SRI 校验和一致） |
| 形态 | **UMD**：文件头第 11 行三分支包装 —— CJS（`module.exports`）/ AMD（`define.amd`）/ **浏览器全局 `globalThis.marked`**；文件内无 `export` / `import` 语句，不是 ESM-only |
| 许可 | MIT。版权声明保留在文件头（MarkedJS 2018-2026 / Christopher Jeffrey 2011-2018）；完整许可见 `LICENSE.marked` |
| 加载方式 | 生成器用 `node:vm` 在沙箱中求值（走 CJS 分支做构建期预渲染）；浏览器端走全局分支，由页面内联脚本使用 |

### 确认要点

- **不是 ESM-only**：`grep -c -E '^[[:space:]]*(export|import)[[:space:]]' vendor/marked.umd.js` → `0`；
  在**没有 `module`/`exports`/`define`** 的沙箱里求值后 `typeof globalThis.marked === 'object'`、`typeof marked.parse === 'function'`。
- **零 CDN**：生成器读取本文件内容并**内联**进 HTML，不 `require` 远程地址、不安装 npm 包。
- 内联时会把末尾的 `//# sourceMappingURL=marked.umd.js.map` 去掉，避免浏览器 devtools 去请求 `.map`（属于外部请求）。
  本文件本身保持与官方发布物**逐字节一致**，不做任何改动。

### 升级方式

1. 取新版本 `https://cdn.jsdelivr.net/npm/marked@<新版本>/lib/marked.umd.js`；
2. 用 jsDelivr 的 `https://data.jsdelivr.com/v1/packages/npm/marked@<新版本>` 返回的 `lib/marked.umd.js` 哈希（base64）核对字节一致；
3. 更新 `render_prd_html.mjs` 里的 `MARKED_VERSION` 常量与本文件的版本表；
4. 重跑渲染 + 校验（见 `skills/prd-writer/SKILL.md` 的验证要点：零外部引用、TOC 与正文标题一一对应、内联脚本 `node --check` 通过）。

## 不引入的依赖

- **mermaid**：dist 体积过大（123MB / 208 chunk），无法本地 vendor，严格 CSP 下动态导入易失败 → 流程图改为手绘 SVG 内联。
- **任何 npm/pnpm 安装**：本目录内容一次性引入后固定，构建与渲染全程离线可用。
