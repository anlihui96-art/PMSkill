/*!
 * prd-page-runtime.js — PRD 浏览页渲染 + 交互运行时（零依赖）
 *
 * 同一份实现被两个环境复用，避免"构建期一套 / 运行期一套"的逻辑漂移：
 *   1) 构建期：render_prd_html.mjs 用 node:vm 加载本文件，预渲染正文 + 目录 + 标题 id
 *      （因此输出 HTML 里是静态可解析的正文，无 JS 也能看，且可被静态断言校验）；
 *   2) 运行期：本文件被原样内联进输出的单文件 HTML，配合内联的 marked 从内嵌
 *      Markdown 源重建正文与目录，并接管目录高亮 / H2 折叠 / 回到顶部 / 侧边栏收起。
 *
 * 两种环境调用同一个 renderPrdMarkdown()，输出逐字节一致。
 *
 * 许可：本文件为 PMSkill 自有代码；内联的 marked 版权见 vendor/marked.umd.js 文件头。
 */
(function (root) {
  'use strict';

  var HEADING_RE = /<h([1-6])([^>]*)>([\s\S]*?)<\/h\1>/g;

  /* ------------------------------------------------------------------ *
   * 纯字符串渲染（构建期 / 运行期共用）
   * ------------------------------------------------------------------ */

  function decodeEntities(s) {
    return String(s)
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/&apos;/g, "'")
      .replace(/&amp;/g, '&');
  }

  /** 把一段内联 HTML 压成纯文本（与 DOM textContent 语义一致：标签不占位、空白折叠） */
  function plainText(html) {
    return decodeEntities(String(html).replace(/<[^>]*>/g, ''))
      .replace(/\s+/g, ' ')
      .trim();
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function escAttr(s) {
    return escHtml(s);
  }

  /** 生成稳定 id：保留中文/字母/数字/点/下划线/短横，其余折叠为短横 */
  function slugify(text) {
    var s = String(text).toLowerCase();
    s = s.replace(/\.\s+/g, '-'); // "1. 需求背景" → "1-需求背景"，避免出现 "1.-需求背景"
    s = s.replace(/[\s\u3000]+/g, '-');
    s = s.replace(/[^\p{L}\p{N}._-]+/gu, '-');
    s = s.replace(/-{2,}/g, '-');
    s = s.replace(/^[-._]+/, '').replace(/[-._]+$/, '');
    return s || 'section';
  }

  function uniqueId(base, used) {
    var id = base;
    var n = 1;
    while (Object.prototype.hasOwnProperty.call(used, id)) {
      n += 1;
      id = base + '-' + n;
    }
    used[id] = true;
    return id;
  }

  /** 给 H1–H6 注入稳定 id，重复标题自动加 -2/-3 后缀；返回标题清单供目录使用 */
  function assignHeadingIds(rawHtml) {
    var used = Object.create(null);
    var headings = [];
    var html = String(rawHtml).replace(HEADING_RE, function (match, level, attrs, inner) {
      var text = plainText(inner);
      var existing = /\sid="([^"]*)"/.exec(attrs);
      var id = existing && existing[1] ? uniqueId(existing[1], used) : uniqueId(slugify(text), used);
      var rest = String(attrs).replace(/\sid="[^"]*"/, '');
      headings.push({ level: Number(level), id: id, text: text });
      return '<h' + level + ' id="' + escAttr(id) + '"' + rest + '>' + inner + '</h' + level + '>';
    });
    return { html: html, headings: headings };
  }

  /** 表格外面套一层可横向滚动的容器（纯字符串层面做，构建期/运行期一致） */
  function wrapTables(html) {
    return String(html)
      .replace(/<table>/g, '<div class="table-wrap"><table>')
      .replace(/<\/table>/g, '</table></div>');
  }

  /**
   * 把每个 H2 及其后的内容包成可折叠 section：
   *   <section class="h2-section"><div class="h2-head"><button class="h2-toggle">…</button><h2 …>…</h2></div>
   *     <div class="h2-body" id="h2-body-N">…</div></section>
   * 首个 H2 之前的内容（含 H1 与文件头注释）保持原样，不参与折叠。
   */
  function wrapH2Sections(html) {
    var lines = String(html).split('\n');
    var pre = [];
    var sections = [];
    var current = null;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var m = /^<h2\s+id="([^"]*)"/.exec(line);
      if (m) {
        current = { id: m[1], head: line, body: [] };
        sections.push(current);
      } else if (current) {
        current.body.push(line);
      } else {
        pre.push(line);
      }
    }
    var out = pre.join('\n');
    for (var j = 0; j < sections.length; j++) {
      var sec = sections[j];
      var bodyId = 'h2-body-' + (j + 1);
      out += '\n<section class="h2-section" data-h2-id="' + escAttr(sec.id) + '">\n'
        + '<div class="h2-head">'
        + '<button class="h2-toggle" type="button" aria-expanded="true" aria-controls="' + bodyId + '"'
        + ' title="收起本章" aria-label="收起本章">\u25be</button>'
        + sec.head
        + '</div>\n'
        + '<div class="h2-body" id="' + bodyId + '">\n'
        + sec.body.join('\n')
        + '\n</div>\n</section>\n';
    }
    return out;
  }

  /** 目录：覆盖 H1–H6，扁平列表 + 层级 class 控制缩进 */
  function buildTocHtml(headings) {
    if (!headings || !headings.length) {
      return '<div class="toc-empty">（正文中未发现标题）</div>';
    }
    var parts = ['<ul class="toc-list">'];
    for (var i = 0; i < headings.length; i++) {
      var h = headings[i];
      parts.push('<li class="toc-item toc-level-' + h.level + '">'
        + '<a class="toc-link" href="#' + escAttr(h.id) + '" data-target="' + escAttr(h.id) + '"'
        + ' title="' + escAttr(h.text) + '">' + escHtml(h.text) + '</a></li>');
    }
    parts.push('</ul>');
    return parts.join('\n');
  }

  /**
   * 渲染入口。markedLib 是 marked 的命名空间对象（构建期由 node:vm 注入，运行期取 window.marked）。
   * 返回 { bodyHtml, tocHtml, headings, firstH1 }
   */
  function renderPrdMarkdown(markdown, markedLib) {
    if (!markedLib || typeof markedLib.parse !== 'function') {
      throw new Error('marked 不可用：无法渲染 Markdown');
    }
    var rawHtml = markedLib.parse(String(markdown), { gfm: true, breaks: false });
    var withIds = assignHeadingIds(wrapTables(rawHtml));
    var bodyHtml = wrapH2Sections(withIds.html);
    var firstH1 = null;
    for (var i = 0; i < withIds.headings.length; i++) {
      if (withIds.headings[i].level === 1) { firstH1 = withIds.headings[i]; break; }
    }
    return {
      bodyHtml: bodyHtml,
      tocHtml: buildTocHtml(withIds.headings),
      headings: withIds.headings,
      firstH1: firstH1
    };
  }

  /* ------------------------------------------------------------------ *
   * 运行期交互（仅浏览器；Node 里 document 未定义，这些函数不会被调用）
   * ------------------------------------------------------------------ */

  function byId(id) {
    return document.getElementById(id);
  }

  function each(list, fn) {
    Array.prototype.forEach.call(list, fn);
  }

  function isMobileSidebar() {
    return !!(window.matchMedia && window.matchMedia('(max-width: 900px)').matches);
  }

  function openSidebar() {
    var sidebar = byId('sidebar');
    if (!sidebar) { return; }
    if (isMobileSidebar()) {
      sidebar.classList.add('mobile-open');
      document.body.classList.add('nav-open');
    } else {
      document.body.classList.remove('sidebar-collapsed');
    }
  }

  function closeSidebar() {
    var sidebar = byId('sidebar');
    if (!sidebar) { return; }
    if (isMobileSidebar()) {
      sidebar.classList.remove('mobile-open');
      document.body.classList.remove('nav-open');
    } else {
      document.body.classList.add('sidebar-collapsed');
    }
  }

  function setupSidebar() {
    var open = byId('sidebar-open');
    var close = byId('sidebar-close');
    if (open && open.getAttribute('data-bound') !== '1') {
      open.setAttribute('data-bound', '1');
      open.addEventListener('click', function () {
        if (!isMobileSidebar() && !document.body.classList.contains('sidebar-collapsed')) { closeSidebar(); return; }
        openSidebar();
      });
    }
    if (close && close.getAttribute('data-bound') !== '1') {
      close.setAttribute('data-bound', '1');
      close.addEventListener('click', closeSidebar);
    }
  }

  function closestSection(el) {
    var node = el;
    while (node && node !== document.body) {
      if (node.classList && node.classList.contains('h2-section')) { return node; }
      node = node.parentNode;
    }
    return null;
  }

  function setCollapsed(section, collapsed) {
    if (!section) { return; }
    var btn = section.querySelector('.h2-toggle');
    if (collapsed) { section.classList.add('collapsed'); } else { section.classList.remove('collapsed'); }
    if (btn) {
      btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      btn.setAttribute('title', collapsed ? '展开本章' : '收起本章');
      btn.setAttribute('aria-label', collapsed ? '展开本章' : '收起本章');
      btn.textContent = collapsed ? '\u25b8' : '\u25be';
    }
  }

  /** 每个 H2 章节绑定折叠控件，默认展开 */
  function setupH2Collapse() {
    each(document.querySelectorAll('.prd-body .h2-section'), function (section) {
      var btn = section.querySelector('.h2-toggle');
      if (!btn || btn.getAttribute('data-bound') === '1') { return; }
      btn.setAttribute('data-bound', '1');
      btn.addEventListener('click', function () {
        setCollapsed(section, !section.classList.contains('collapsed'));
      });
      setCollapsed(section, false);
    });
  }

  function expandChapterOf(heading) {
    var section = closestSection(heading);
    if (section && section.classList.contains('collapsed')) { setCollapsed(section, false); }
  }

  function keepTocLinkVisible(link) {
    var box = byId('sidebar');
    if (!box || !link) { return; }
    var top = link.offsetTop;
    var height = link.offsetHeight;
    var viewTop = box.scrollTop;
    var viewBottom = viewTop + box.clientHeight;
    if (top < viewTop + 8) { box.scrollTop = Math.max(0, top - 8); }
    else if (top + height > viewBottom - 8) { box.scrollTop = top + height - box.clientHeight + 8; }
  }

  /** 滚动高亮：滚动时定位当前标题 → TOC 高亮 + 自动展开所属 H2 章节 */
  function setupScrollSpy() {
    var headings = Array.prototype.slice.call(
      document.querySelectorAll('.prd-body h1, .prd-body h2, .prd-body h3, .prd-body h4, .prd-body h5, .prd-body h6')
    );
    if (!headings.length) { return; }
    var tocLinks = document.querySelectorAll('#toc .toc-link');
    var linkById = Object.create(null);
    each(tocLinks, function (a) { linkById[a.getAttribute('data-target')] = a; });

    var ticking = false;
    function currentHeading() {
      var y = window.pageYOffset || document.documentElement.scrollTop || 0;
      var probe = y + 90;
      var found = headings[0];
      for (var i = 0; i < headings.length; i++) {
        if (headings[i].offsetTop <= probe) { found = headings[i]; } else { break; }
      }
      return found;
    }
    function highlight() {
      ticking = false;
      var active = currentHeading();
      each(tocLinks, function (a) { a.classList.remove('active'); });
      if (!active) { return; }
      var link = linkById[active.id];
      if (link) {
        link.classList.add('active');
        keepTocLinkVisible(link);
      }
      expandChapterOf(active);
    }
    function onScroll() {
      if (ticking) { return; }
      ticking = true;
      if (window.requestAnimationFrame) { window.requestAnimationFrame(highlight); } else { setTimeout(highlight, 16); }
    }
    if (document.body.getAttribute('data-spy-bound') !== '1') {
      document.body.setAttribute('data-spy-bound', '1');
      window.addEventListener('scroll', onScroll, { passive: true });
      window.addEventListener('resize', onScroll);
    }
    highlight();
  }

  function setupBackToTop() {
    var btn = byId('back-to-top');
    if (!btn) { return; }
    function sync() {
      var y = window.pageYOffset || document.documentElement.scrollTop || 0;
      if (y > 400) { btn.classList.add('show'); } else { btn.classList.remove('show'); }
    }
    if (btn.getAttribute('data-bound') !== '1') {
      btn.setAttribute('data-bound', '1');
      btn.addEventListener('click', function () {
        try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch (e) { window.scrollTo(0, 0); }
      });
      window.addEventListener('scroll', sync, { passive: true });
    }
    sync();
  }

  function setupTocLinks() {
    each(document.querySelectorAll('#toc .toc-link'), function (a) {
      if (a.getAttribute('data-bound') === '1') { return; }
      a.setAttribute('data-bound', '1');
      a.addEventListener('click', function () {
        var target = byId(a.getAttribute('data-target'));
        if (target && target.scrollIntoView) { target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
        if (isMobileSidebar()) { closeSidebar(); }
      });
    });
  }

  /** 用内联的 marked 从内嵌 Markdown 源重建正文；任何异常都保留构建期预渲染的正文 */
  function hydrateFromSource() {
    var host = byId('prd-body');
    var toc = byId('toc');
    var src = byId('prd-markdown-source');
    if (!host || !toc || !src) { return false; }
    if (!root.marked || typeof root.marked.parse !== 'function') { return false; }
    var markdown = '';
    try { markdown = JSON.parse(src.textContent || '{}').markdown || ''; } catch (e) { return false; }
    if (!markdown) { return false; }
    var out = renderPrdMarkdown(markdown, root.marked);
    if (!out.bodyHtml || !/<h[1-6][\s>]/.test(out.bodyHtml)) { return false; }
    host.innerHTML = out.bodyHtml;
    toc.innerHTML = out.tocHtml;
    return true;
  }

  function initPage() {
    try { hydrateFromSource(); } catch (e) { /* 保留构建期预渲染正文 */ }
    setupSidebar();
    setupH2Collapse();
    setupScrollSpy();
    setupTocLinks();
    setupBackToTop();
  }

  root.__PRD_PAGE__ = {
    decodeEntities: decodeEntities,
    plainText: plainText,
    escHtml: escHtml,
    slugify: slugify,
    assignHeadingIds: assignHeadingIds,
    wrapTables: wrapTables,
    wrapH2Sections: wrapH2Sections,
    buildTocHtml: buildTocHtml,
    renderPrdMarkdown: renderPrdMarkdown,
    initPage: initPage
  };

  if (typeof document !== 'undefined' && document.addEventListener) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initPage);
    } else {
      initPage();
    }
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
