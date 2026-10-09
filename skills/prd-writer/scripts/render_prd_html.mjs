#!/usr/bin/env node
/**
 * render_prd_html.mjs — 把 PRD Markdown 渲染成「自包含单文件 HTML 浏览页」
 *
 * 用法：
 *   node render_prd_html.mjs <输入.md> -o <输出.html> [--title "标题"] [--version "v1.5"]
 *
 * 产物特征：
 *   - 单文件，零 CDN / 零外部请求：marked 源码、CSS、页面 JS 全部内联；
 *   - 左侧目录（H1–H6 全 6 级）、滚动高亮、目录栏整体收起/展开；
 *   - 每个 H2 章节可折叠（默认展开，滚动到该章节自动展开）；
 *   - 顶部粘性标题栏（可选版本号徽章）、回到顶部按钮、移动端自适应、表格/代码块/引用块样式。
 *
 * 依赖：仅 Node 自带模块（node:fs / node:path / node:vm / node:process / node:url）
 *       + 本地 vendor 的 marked 源文件（skills/prd-writer/vendor/marked.umd.js）。
 *       不使用 npm / pnpm，不联网。
 *
 * 版本：marked 18.1.0（MIT），见 vendor/README.md 的固定版本与校验和。
 */

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const VENDOR_MARKED = path.join(__dirname, '..', 'vendor', 'marked.umd.js');
const RUNTIME_SOURCE = path.join(__dirname, 'prd-page-runtime.js');
const MARKED_VERSION = '18.1.0';

const USAGE = `用法：
  node render_prd_html.mjs <输入.md> -o <输出.html> [--title "标题"] [--version "v1.5"]

参数：
  <输入.md>          Markdown 源文件（PRD 正文）
  -o, --out <文件>   输出的单文件 HTML
  --title <文本>     顶部标题栏文案（缺省取正文第一个 H1，再缺省取输入文件名）
  --version <文本>   版本号徽章（缺省不渲染徽章）
  -h, --help         显示本帮助
`;

/* ------------------------------------------------------------------ *
 * 1. 命令行参数
 * ------------------------------------------------------------------ */

function parseArgs(argv) {
  const opts = { input: null, output: null, title: null, version: null, help: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '-h' || arg === '--help') {
      opts.help = true;
    } else if (arg === '-o' || arg === '--out') {
      opts.output = argv[i + 1];
      i += 1;
    } else if (arg === '--title') {
      opts.title = argv[i + 1];
      i += 1;
    } else if (arg === '--version') {
      opts.version = argv[i + 1];
      i += 1;
    } else if (arg.startsWith('-') && arg !== '-') {
      throw new Error(`未知参数：${arg}`);
    } else if (!opts.input) {
      opts.input = arg;
    } else {
      throw new Error(`多余的参数：${arg}`);
    }
  }
  if (opts.help) return opts;
  if (!opts.input) throw new Error('缺少输入 Markdown 文件');
  if (!opts.output) throw new Error('缺少 -o <输出.html>');
  if (opts.title === undefined || opts.title === null) opts.title = null;
  if (opts.version === undefined || opts.version === null) opts.version = null;
  return opts;
}

/* ------------------------------------------------------------------ *
 * 2. 加载 vendored marked（UMD：CJS 分支 → module.exports；浏览器分支 → 全局 marked）
 *    这里用 node:vm 在沙箱里求值，不 require、不安装任何包。
 * ------------------------------------------------------------------ */

function loadMarked(source, filename) {
  const sandbox = { module: { exports: {} }, exports: {}, console };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename });
  const lib = sandbox.module.exports;
  if (!lib || typeof lib.parse !== 'function') {
    throw new Error('vendor 的 marked 未能导出 parse()：请检查 vendor/marked.umd.js');
  }
  return { lib, form: typeof sandbox.marked === 'object' && sandbox.marked ? 'global' : 'cjs' };
}

/** 加载页面运行时（同一份文件既用于构建期预渲染，也被内联进页面） */
function loadRuntime(source, filename) {
  const sandbox = { console };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename });
  const api = sandbox.__PRD_PAGE__;
  if (!api || typeof api.renderPrdMarkdown !== 'function') {
    throw new Error('页面运行时未导出 __PRD_PAGE__.renderPrdMarkdown');
  }
  return api;
}

/* ------------------------------------------------------------------ *
 * 3. HTML / CSS 模板
 * ------------------------------------------------------------------ */

const CSS = `:root{
  --sidebar-w:300px;
  --topbar-h:54px;
  --c-bg:#ffffff;
  --c-bg-soft:#f7f8fa;
  --c-border:#e5e7eb;
  --c-text:#1f2328;
  --c-text-soft:#57606a;
  --c-accent:#1a73e8;
  --c-accent-soft:#e8f0fe;
  --c-code-bg:#f6f8fa;
}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--c-bg);color:var(--c-text);font-size:15px;line-height:1.75;
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Helvetica Neue",Arial,sans-serif;}
.icon-btn{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;padding:0;
  border:1px solid var(--c-border);border-radius:6px;background:#fff;color:var(--c-text-soft);font-size:14px;
  line-height:1;cursor:pointer;transition:color .15s ease,border-color .15s ease,background .15s ease}
.icon-btn:hover{color:var(--c-accent);border-color:var(--c-accent);background:var(--c-accent-soft)}

/* 顶部粘性标题栏 + 版本徽章 */
.topbar{position:sticky;top:0;z-index:50;height:var(--topbar-h);border-bottom:1px solid var(--c-border);
  background:rgba(255,255,255,.94);-webkit-backdrop-filter:saturate(180%) blur(8px);backdrop-filter:saturate(180%) blur(8px)}
.topbar-inner{display:flex;align-items:center;height:100%;gap:10px;padding:0 18px;min-width:0}
.topbar-title{font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.version-badge{flex:0 0 auto;padding:1px 8px;border:1px solid var(--c-accent);border-radius:999px;
  background:var(--c-accent-soft);color:var(--c-accent);font-size:12px;font-weight:600;line-height:18px}
#sidebar-open{display:none;flex:0 0 auto}
body.sidebar-collapsed #sidebar-open{display:inline-flex}

/* 布局：左目录 + 右正文 */
.layout{display:flex;align-items:flex-start}
.sidebar{flex:0 0 var(--sidebar-w);width:var(--sidebar-w);position:sticky;top:var(--topbar-h);
  height:calc(100vh - var(--topbar-h));overflow-y:auto;overscroll-behavior:contain;
  padding:12px 0 40px;border-right:1px solid var(--c-border);background:var(--c-bg-soft);
  transition:margin-left .25s ease}
body.sidebar-collapsed .sidebar{margin-left:calc(-1 * var(--sidebar-w))}
.sidebar-head{display:flex;align-items:center;justify-content:space-between;gap:8px;
  padding:0 12px 8px 16px;margin-bottom:6px;border-bottom:1px solid var(--c-border)}
.sidebar-head-title{font-size:13px;font-weight:600;color:var(--c-text-soft);letter-spacing:.04em}
.prd-body{flex:1 1 auto;min-width:0;max-width:1000px;padding:26px 40px 140px;
  overflow-wrap:break-word;word-wrap:break-word}

/* 目录：H1–H6 全 6 级，缩进 0/12/24/36/48/60px */
.toc{font-size:13px}
.toc-list{list-style:none;margin:0;padding:2px 0}
.toc-item{margin:0}
.toc-link{display:block;padding:3px 14px 3px 0;color:var(--c-text-soft);text-decoration:none;
  font-size:13px;line-height:1.5;border-left:2px solid transparent;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;transition:color .15s ease,background .15s ease}
.toc-item.toc-level-1>.toc-link{padding-left:0;font-weight:700;color:var(--c-text);font-size:13.5px}
.toc-item.toc-level-2>.toc-link{padding-left:12px;font-weight:600;color:var(--c-text)}
.toc-item.toc-level-3>.toc-link{padding-left:24px}
.toc-item.toc-level-4>.toc-link{padding-left:36px}
.toc-item.toc-level-5>.toc-link{padding-left:48px}
.toc-item.toc-level-6>.toc-link{padding-left:60px;font-size:12px}
.toc-link:hover{color:var(--c-accent);background:var(--c-accent-soft)}
.toc-link.active{color:var(--c-accent);background:var(--c-accent-soft);
  border-left-color:var(--c-accent);font-weight:600}
.toc-empty{padding:8px 16px;color:var(--c-text-soft);font-size:12px}

/* 正文排版 */
.prd-body>p:first-child{margin-top:0}
.prd-body h1,.prd-body h2,.prd-body h3,.prd-body h4,.prd-body h5,.prd-body h6{
  font-weight:600;line-height:1.35;color:var(--c-text);
  scroll-margin-top:calc(var(--topbar-h) + 14px)}
.prd-body h1{font-size:2em;margin:8px 0 18px;padding-bottom:10px;border-bottom:2px solid var(--c-border)}
.prd-body h2{font-size:1.5em;margin:0 0 14px;padding-top:4px}
.prd-body h3{font-size:1.2em;margin:24px 0 10px}
.prd-body h4{font-size:1.05em;margin:20px 0 8px}
.prd-body h5{font-size:.95em;margin:16px 0 8px;color:#3d444d}
.prd-body h6{font-size:.9em;margin:14px 0 8px;color:var(--c-text-soft)}
.prd-body p{margin:10px 0}
.prd-body a{color:var(--c-accent);text-decoration:none;border-bottom:1px solid rgba(26,115,232,.35)}
.prd-body a:hover{border-bottom-color:var(--c-accent)}
.prd-body ul,.prd-body ol{margin:10px 0;padding-left:26px}
.prd-body li{margin:4px 0}
.prd-body hr{height:1px;margin:26px 0;border:0;background:var(--c-border)}
.prd-body strong{font-weight:600}

/* 表格 / 代码块 / 引用块 */
.table-wrap{margin:14px 0;overflow-x:auto;border:1px solid var(--c-border);border-radius:8px}
.table-wrap>table{margin:0;width:100%;border-collapse:collapse;font-size:13px}
.prd-body table{border-collapse:collapse;font-size:13px}
.prd-body th,.prd-body td{border:1px solid var(--c-border);padding:7px 10px;text-align:left;vertical-align:top}
.prd-body thead th{background:var(--c-bg-soft);font-weight:600;white-space:nowrap}
.prd-body tbody tr:nth-child(even){background:#fcfcfd}
.prd-body code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
  font-size:12.5px;background:var(--c-code-bg);border:1px solid var(--c-border);border-radius:4px;padding:1px 5px}
.prd-body pre{margin:14px 0;padding:12px 14px;background:var(--c-code-bg);border:1px solid var(--c-border);
  border-radius:8px;overflow-x:auto;font-size:12.5px;line-height:1.6}
.prd-body pre code{background:none;border:0;border-radius:0;padding:0;font-size:inherit;white-space:pre}
.prd-body blockquote{margin:14px 0;padding:10px 16px;border-left:4px solid var(--c-accent);
  border-radius:0 6px 6px 0;background:var(--c-bg-soft);color:var(--c-text-soft)}
.prd-body blockquote>p:first-child{margin-top:0}
.prd-body blockquote>p:last-child{margin-bottom:0}
.prd-body img{max-width:100%;height:auto}

/* H2 章节折叠 */
.h2-section{margin-top:22px;padding-top:8px;border-top:1px solid var(--c-border)}
.h2-section:first-of-type{margin-top:6px}
.h2-head{position:relative;display:flex;align-items:flex-start;gap:8px}
.h2-head>h2{flex:1 1 auto;min-width:0;padding-right:34px}
.h2-toggle{position:absolute;right:0;top:.62em;width:24px;height:24px;padding:0;cursor:pointer;
  display:inline-flex;align-items:center;justify-content:center;font-size:11px;line-height:1;
  color:var(--c-text-soft);background:#fff;border:1px solid var(--c-border);border-radius:6px;
  transition:color .15s ease,border-color .15s ease,background .15s ease}
.h2-toggle:hover{color:var(--c-accent);border-color:var(--c-accent);background:var(--c-accent-soft)}
.h2-section.collapsed .h2-body{display:none}
.h2-section.collapsed>.h2-head>h2{color:var(--c-text-soft)}

/* 回到顶部 */
.back-to-top{position:fixed;right:22px;bottom:26px;z-index:60;width:42px;height:42px;padding:0;
  border:1px solid var(--c-border);border-radius:50%;background:#fff;color:var(--c-text-soft);
  font-size:18px;line-height:1;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.12);
  opacity:0;visibility:hidden;transform:translateY(8px);
  transition:opacity .2s ease,transform .2s ease,visibility .2s ease,color .15s ease}
.back-to-top.show{opacity:1;visibility:visible;transform:none}
.back-to-top:hover{color:var(--c-accent);border-color:var(--c-accent)}

/* 移动端自适应：隐藏侧边栏，改为可按需拉出的浮层 */
@media (max-width:900px){
  :root{--sidebar-w:min(84vw,320px)}
  .layout{display:block}
  .sidebar{display:none}
  .sidebar.mobile-open{display:block;position:fixed;left:0;top:var(--topbar-h);bottom:0;height:auto;
    z-index:60;width:var(--sidebar-w);flex:none;margin-left:0;box-shadow:0 10px 30px rgba(0,0,0,.18)}
  body.sidebar-collapsed .sidebar{margin-left:0}
  #sidebar-open{display:inline-flex}
  .topbar-inner{padding:0 12px}
  .prd-body{max-width:none;padding:18px 16px 110px}
  .prd-body h1{font-size:1.6em}
  .prd-body h2{font-size:1.3em}
  .back-to-top{right:14px;bottom:18px}
}
`;

/* ------------------------------------------------------------------ *
 * 4. 组装单文件 HTML
 * ------------------------------------------------------------------ */

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function buildHtml({ title, version, bodyHtml, tocHtml, markdown, markedSource, runtimeSource }) {
  const badge = version
    ? `    <span class="version-badge" id="version-badge">${escHtml(version)}</span>\n`
    : '';
  const markdownJson = JSON.stringify({ markdown }).replace(/</g, '\\u003c');
  return `<!DOCTYPE html>
<html lang="zh-CN" data-generator="prd-writer/render_prd_html.mjs" data-marked-version="${MARKED_VERSION}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>${escHtml(title)}</title>
<!-- 自包含单文件 PRD 浏览页：零 CDN、零外部请求。marked v${MARKED_VERSION} (MIT) 本地 vendor 后内联，版权见其文件头。 -->
<style>
${CSS}</style>
</head>
<body>
<header class="topbar" id="topbar">
  <div class="topbar-inner">
    <button class="icon-btn" id="sidebar-open" type="button" aria-label="展开目录" title="展开目录">\u2630</button>
    <span class="topbar-title">${escHtml(title)}</span>
${badge}  </div>
</header>
<div class="layout">
  <aside class="sidebar" id="sidebar" aria-label="目录导航">
    <div class="sidebar-head">
      <span class="sidebar-head-title">目录</span>
      <button class="icon-btn" id="sidebar-close" type="button" aria-label="收起目录" title="收起目录">\u2715</button>
    </div>
    <nav class="toc" id="toc" aria-label="正文目录">
${tocHtml}
    </nav>
  </aside>
  <main class="prd-body" id="prd-body">
${bodyHtml}  </main>
</div>
<button class="back-to-top" id="back-to-top" type="button" aria-label="回到顶部" title="回到顶部">\u2191</button>
<script type="application/json" id="prd-markdown-source">${markdownJson}</script>
<!-- 渲染库：marked v${MARKED_VERSION}（MIT，本地 vendor，内联，无外部请求） -->
<script>
${markedSource}</script>
<!-- 页面运行时：目录滚动高亮 / H2 章节折叠 / 侧边栏收起展开 / 回到顶部 -->
<script>
${runtimeSource}</script>
</body>
</html>
`;
}

/* ------------------------------------------------------------------ *
 * 5. 自检：外部资源引用 / script 内联安全
 * ------------------------------------------------------------------ */

function selfCheck(html, markedSource, runtimeSource) {
  const problems = [];
  // 只在「真正的标记」上做资源引用检查：内联的 JS/CSS 文本里出现 <img src="…"> 这类
  // 字符串属于渲染库源码，不是文档里的资源引用，先把 script/style 的内容挖空。
  const markup = html
    .replace(/(<script\b[^>]*>)[\s\S]*?(<\/script>)/gi, '$1$2')
    .replace(/(<style\b[^>]*>)[\s\S]*?(<\/style>)/gi, '$1$2');
  // 资源引用检查：只放行「自包含」的目标——data: URI（内联）与页内锚点(#)。
  // 其余一律算违规，包括相对路径：那意味着引用了未内联的本地文件，传到 OSS 会 404。
  // 正文区单独再扫一遍（不挖空 script/style）：生成器自己的脚本与 CSS 不在 <main> 内，
  // 因此作者写在 <style> 里的 @import / url(...) 也能被抓住。
  const bodyRegion = (html.match(/<main\b[^>]*id="prd-body"[^>]*>[\s\S]*?<\/main>/i) || [''])[0];
  const refPattern = /<(script|link|img|iframe|source)\b[^>]*\b(?:src|href)\s*=\s*["']([^"']*)["']/gi;
  const nonInlineRefs = [];
  for (const region of [markup, bodyRegion]) {
    for (const m of region.matchAll(refPattern)) {
      const target = m[2].trim();
      if (/^data:/i.test(target) || target.startsWith('#')) continue;
      if (!nonInlineRefs.includes(m[0])) nonInlineRefs.push(m[0]);
    }
  }
  if (nonInlineRefs.length > 0) {
    problems.push(`发现非内联资源引用：${nonInlineRefs.slice(0, 3).join(' | ')}`);
  }
  // @import 永远是外部文件引用（data: 形式无意义），一律拦下
  const imports = [];
  const cssUrls = [];
  for (const region of [markup, bodyRegion]) {
    imports.push(...(region.match(/@import\s+(?:url\()?\s*["']/gi) || []));
    cssUrls.push(...(region.match(/url\(\s*["']?\s*(?:https?:)?\/\//gi) || []));
  }
  if (imports.length > 0) problems.push(`发现外部资源引用 @import …：${imports.slice(0, 3).join(' | ')}`);
  if (cssUrls.length > 0) problems.push(`发现外部资源引用 CSS url(//…)：${cssUrls.slice(0, 3).join(' | ')}`);
  const externalRefs = markup.match(/(?:src|href)\s*=\s*["']https?:/gi) || [];
  for (const [label, src] of [['marked', markedSource], ['页面运行时', runtimeSource]]) {
    if (/<\/?script/i.test(src)) problems.push(`内联的${label}源码含 "<script" / "</script" 字面量，会破坏 HTML 解析`);
    const opens = (src.match(/<!--/g) || []).length;
    const closes = (src.match(/-->/g) || []).length;
    if (opens > closes) problems.push(`内联的${label}源码含未闭合的 "<!--"（HTML 转义态风险）`);
  }
  return {
    problems,
    externalRefs,
    bodyLinks: (markup.match(/<a\b[^>]*\bhref\s*=\s*["']https?:/gi) || []).length,
  };
}

/* ------------------------------------------------------------------ *
 * 6. main
 * ------------------------------------------------------------------ */

function main() {
  let opts;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (err) {
    process.stderr.write(`参数错误：${err.message}\n\n${USAGE}`);
    process.exit(2);
  }
  if (opts.help) {
    process.stdout.write(USAGE);
    return;
  }

  const inputPath = path.resolve(process.cwd(), opts.input);
  const outputPath = path.resolve(process.cwd(), opts.output);
  if (!fs.existsSync(inputPath)) {
    process.stderr.write(`找不到输入文件：${inputPath}\n`);
    process.exit(1);
  }

  const markdown = fs.readFileSync(inputPath, 'utf8');
  const markedRaw = fs.readFileSync(VENDOR_MARKED, 'utf8');
  const runtimeSource = fs.readFileSync(RUNTIME_SOURCE, 'utf8');

  // 内联时去掉 sourceMappingURL（否则浏览器 devtools 会去请求 .map，属于外部请求）
  const markedSource = markedRaw.replace(/\n\/\/# sourceMappingURL=[^\n]*\n?/g, '\n');

  const loaded = loadMarked(markedSource, 'vendor/marked.umd.js');
  const api = loadRuntime(runtimeSource, 'scripts/prd-page-runtime.js');
  const rendered = api.renderPrdMarkdown(markdown, loaded.lib);

  const title = opts.title
    || (rendered.firstH1 && rendered.firstH1.text)
    || path.basename(inputPath).replace(/\.md$/i, '');

  const html = buildHtml({
    title,
    version: opts.version,
    bodyHtml: rendered.bodyHtml,
    tocHtml: rendered.tocHtml,
    markdown,
    markedSource,
    runtimeSource,
  });

  const check = selfCheck(html, markedSource, runtimeSource);
  if (check.problems.length) {
    process.stderr.write(`自检未通过：\n- ${check.problems.join('\n- ')}\n`);
    process.exit(1);
  }

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, html, 'utf8');

  const levels = [1, 2, 3, 4, 5, 6]
    .map((lv) => `H${lv}=${rendered.headings.filter((h) => h.level === lv).length}`)
    .join(' ');
  const h2Sections = (rendered.bodyHtml.match(/class="h2-section"/g) || []).length;
  process.stdout.write([
    `已生成 ${outputPath}`,
    `  大小：${Buffer.byteLength(html, 'utf8')} 字节（内联 marked ${Buffer.byteLength(markedSource, 'utf8')} 字节）`,
    `  标题：${rendered.headings.length} 个（${levels}）；目录条目 ${(rendered.tocHtml.match(/class="toc-link"/g) || []).length} 个；H2 折叠章节 ${h2Sections} 个`,
    `  标题栏：${title}${opts.version ? `；版本徽章 ${opts.version}` : '；无版本徽章（未传 --version）'}`,
    `  外部资源引用：0（正文内作者书写的链接 ${check.bodyLinks} 个，属于内容，不计入）`,
    `  marked：v${MARKED_VERSION}（UMD，通过 ${loaded.form === 'global' ? '全局变量' : 'CJS 分支'} 加载）`,
    '',
  ].join('\n'));
}

try {
  main();
} catch (err) {
  process.stderr.write(`渲染失败：${err && err.stack ? err.stack : err}\n`);
  process.exit(1);
}
