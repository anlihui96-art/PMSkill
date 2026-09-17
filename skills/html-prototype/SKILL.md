---
name: html-prototype
description: HTML 原型生成规范。定义原型技术栈（纯原生 CSS + 原生 JS）、DDYS 设计系统、页面结构规范、端布局类型、分步生成流程。当生成 HTML 原型、设计页面结构、验证原型效果时使用。使用纯原生 CSS + 原生 JS + 单文件 HTML 方案（零 CDN 依赖，`:root` CSS 变量承载 DDYS 设计令牌）。
---

# HTML 原型生成规范

## 技术栈

- **纯原生 CSS + 原生 JS + 单文件 HTML**（零 CDN 依赖，`:root` CSS 变量承载 DDYS 设计令牌）
- 设计令牌与配色主题: `ddys`（`:root` 变量定义，见 DESIGN-SPEC.md 完整 token 定义）
- 组件一律按 DDYS 设计令牌**手写组件样式**；交互组件（modal/drawer/tabs/toast）用原生 JS 实现
- 自 2026-08 v8 迭代起弃用第三方 CSS 框架与组件库（零 CDN 依赖），以 `output/zhelicha/v8-渠道后付费/prototype` 为实现基准

## 设计规范（🔴 强制遵循）

**生成任何 HTML 原型前，必须先阅读 [DESIGN-SPEC.md](./DESIGN-SPEC.md)**，严格遵循其中的：

1. 主题 CSS 变量（`[data-theme="ddys"]` 完整样式块）
2. 字体系统（PingFang SC、三档字号 12/14/16px、行高=字号+8px）
3. 色板（主色 `#2c3f89`、墨黑 `#1d2129`、画布 `#f7f8fa`）
4. 圆角体系（容器 8px、交互元素 4px、品牌 16px）
5. 阴影规则（卡片无阴影、仅浮动元素有阴影）
6. Do's and Don'ts

## 页面结构规范

- 按 DDYS 设计令牌**手写组件样式**（按钮、卡片、表格、Tabs、步骤条、状态标签、输入框、下拉框、弹窗、抽屉等），不引用任何外部组件库
- 交互组件（modal/drawer/tabs/toast）用原生 JS 实现，参照 v8 原型既有模式（类切换 + 遮罩层 + ESC/overlay 关闭）
- 表单使用字段容器 + `label` + `input`/`select` 结构（必填项红色 `*` 标记）
- 导航使用手写侧边栏 + 顶栏结构
- 步骤条使用手写 steps 组件（当前步骤色 `#2c3f89`）

### 组件 → DDYS 规范映射（手写样式）

| 组件 | DDYS 手写样式要点 |
|-------------|-------------|
| 主按钮 | 背景 `#2c3f89`，文字白色，高度 32px，**文字 12px** |
| 次按钮（描边） | 边框 `#e3e5e9`，文字 `#1d2129`，hover 边框变 `#2c3f89` |
| 卡片 | 白色背景，**8px 圆角**，24px 内边距，**无阴影** |
| 表格 | 表头 `#fafafa`，边框 `#e3e5e9`，hover `#f5f5f5` |
| Tabs | 文字 20px，选中色 `#2c3f89`，下划线 4px×40px 胶囊形 |
| 弹窗 | 8px 圆角，三段式（标题+分割线+内容+分割线+底部） |
| 状态标签 | 成功 `#ebfaf5/#52c41a`，危险 `#ffebec/#da342e`，**无圆角** |
| 输入框 | 工作台：白底+`#e3e5e9`边框+32px高；登录：`#f7f8fa`底+无边框+44px高 |
| 侧边栏菜单 | 文字 `#59626f`，选中 `#1d2129`，**不用品牌色** |
| 步骤条 | 当前步骤色 `#2c3f89` |

### PC 端全局布局骨架

```html
<html lang="zh-CN" data-theme="ddys">
<head>
  <!-- 零 CDN 依赖：:root / [data-theme="ddys"] 定义设计令牌变量（见 DESIGN-SPEC.md） -->
  <!-- 手写组件样式：侧边栏 / 顶栏 / 卡片 / 表格 / 按钮等（数值遵循 DESIGN-SPEC.md） -->
  <style>body { background: var(--ddys-canvas-gradient); } /* 画布渐变背景 */</style>
</head>
<body>
  <div class="layout"> <!-- display:flex; height:100vh; overflow:hidden -->
    <!-- 侧边栏：浮岛式 -->
    <aside class="sidebar">
      <!-- width:240px; margin:16px; border-radius:8px; background:hsla(0,0%,100%,0.72) -->
      <!-- Logo + 菜单 -->
    </aside>

    <!-- 主内容区 -->
    <main class="main"> <!-- flex:1; display:flex; flex-direction:column; overflow:auto -->
      <!-- 顶部栏：透明 -->
      <header class="topbar">...</header> <!-- height:56px; padding:0 24px; display:flex; align-items:center -->

      <!-- 内容 -->
      <div class="content"> <!-- flex:1; padding:24px; display:flex; flex-direction:column; gap:16px -->
        <!-- 卡片：白底 + 8px圆角 + 24px内边距 + 无阴影 -->
        <div class="card">...</div>
      </div>
    </main>
  </div>
</body>
</html>
```

### 移动端全局布局骨架

```html
<html lang="zh-CN" data-theme="ddys">
<body> <!-- background: #f7f8fa 画布底色 -->
  <!-- 顶部导航 -->
  <header class="navbar">
    <!-- position:fixed; top:0; width:100%; height:48px; background:#fff; 底部阴影; z-index:10 -->
    <div class="navbar-inner"> <!-- max-width:414px; margin:0 auto; height:100%; padding:0 16px; display:flex; align-items:center -->
      <span class="navbar-title">页面标题</span> <!-- 16px/500 -->
    </div>
  </header>

  <!-- 内容 -->
  <main class="content"> <!-- max-width:414px; margin:0 auto; padding:64px 16px 16px -->
    <div class="card">...</div> <!-- 白底; 圆角 12px; 内边距 16px; margin-bottom 16px -->
  </main>

  <!-- 底部操作栏（如需） -->
  <footer class="dock">
    <!-- position:fixed; bottom:0; width:100%; background:#fff; box-shadow:0 -2px 8px rgba(0,0,0,0.06); padding:16px 16px 24px -->
    <div class="dock-inner"> <!-- max-width:414px; margin:0 auto -->
      <button class="btn btn-primary btn-block">提交</button> <!-- 通栏主按钮：背景 #2c3f89，白字，100% 宽 -->
    </div>
  </footer>
</body>
</html>
```

## 端布局类型

| 端 | 布局 | 侧边栏 | 适用场景 |
|----|------|--------|---------|
| 运营端 | 浮岛侧边栏 240px + 透明顶栏 56px | 半透明白 `hsla(0,0%,100%,0.72)` | 后台管理 |
| 渠道端 | 浮岛侧边栏 240px + 透明顶栏 56px | 半透明白 | 渠道管理 |
| 用户端 Web | 居中 `max-w-5xl` | 无 | 律师/申请人查询 |
| 用户端 H5 | 全宽 `max-w-[414px]` mobile-first | 无 | 移动端查询 |
| 登录页 | 全屏渐变 + 分屏面板 | 无 | 登录/注册 |

## 跨端同类页面一致性与复用约束（🔴 强制）

**不同端承载相同业务的页面，必须尽可能保持结构、字段、交互、视觉一致，最大化复用，节省开发与评审成本。**

### 核心规则

1. **先找基准页**：新建或修改某端页面前，先检查其他端是否已有同类页面（如运营端核查单列表 vs 渠道端核查单列表、运营端用户管理 vs 渠道用户管理）。已有则以其为基准对齐：同一套 CSS 设计体系、同构的布局（侧栏/顶栏/筛选栏/表格/分页）、一致的交互模式（真实过滤、弹窗 ESC/overlay 关闭、表单校验、二次确认）。
2. **基准页升级时同步对齐**：基准页重做（如去 CDN 改自含 CSS、补全交互）后，同类的其他端页面须同步对齐，不允许同一迭代内同业务页面出现两套视觉/交互水准。
3. **端特色差异仅限业务必需**：只允许保留端特色部分——如操作列差异（运营端有审核/退款操作、渠道端只读）、菜单/品牌名差异、某端专属写操作（如渠道端的支付模式/个人额度设置弹窗）、数据隔离维度差异（渠道端无「渠道来源」筛选）。
4. **字段与口径仍以 PRD 为准**：跨端一致不覆盖 PRD 字段约束，各端字段名、枚举、展示口径以各自 PRD 章节为准（字段命名约束优先级更高）。

**生成前检查**：同一迭代/项目中新增页面前，先列出各端同类页面清单，逐一确认复用基准；修改某页后，自查其他端同类页面是否需要同步。

## 字段命名约束（🔴 强制）

原型中所有字段标签、表单 label、表格表头、详情展示名**必须与 PRD 字段说明表中的字段名完全一致**，禁止自行改名、简化或使用近义词。

**生成前检查**：编写原型内容时，须参照 PRD 对应页面的「字段说明」表，逐字段核对标签名称。

## 真实产品交互原则（🔴 最高优先级）

**原型必须像真实产品一样运作，禁止使用任何外部演示控制工具。**

### 核心规则

1. **禁止浮动工具栏/演示控制条** — 不允许在页面外部（底部浮动、顶部悬浮等）放置状态切换按钮
2. **通过真实 UI 元素驱动流程** — 点击卡片、按钮、列表项等页面自身元素来触发状态变化和页面跳转
3. **穷举所有状态** — 每个页面必须包含所有可能的业务状态，每种状态有完整的入口数据和展示

### 禁止生成「流程解释型提示」（🔴 用户明确要求，严禁违反）

**原型中禁止添加解释交互流程、设计规则的文字提示**，这类文案属于设计说明而非产品文案，真实产品不会展示给用户。

**典型禁止模式**（命中任一即违规）：

| 禁止模式 | 示例 |
|---------|------|
| 按钮行为预告 | 「点击『立即付款』后在弹框内展示二维码」「点击后弹起确认订单弹框」 |
| 流程说明句 | 「下单后将弹起确认订单与支付弹框，请选择支付方式完成付款」 |
| 设计规则解释 | 「🛡 无论钱包余额是否充足，均需选择支付方式拉起支付」 |
| 支付方式说明面板 | 选项下方的「扫码支付：银联聚合二维码 15 分钟内有效…」提示框 |
| 字段来源注释 | 「法律文书 OCR 识别后自动带出」（写在页面可见文案中） |

**允许的例外**（真实产品会有的文案）：
- 空态提示（「暂无数据」「请选择至少 1 个查询数量」）
- 表单 placeholder、校验错误提示、toast 反馈
- 产品本身的引导文案（如步骤条标题、二维码页的「请使用微信/支付宝扫码」）

**判断标准**：如果这段文案是在解释「这个交互怎么设计的」而不是「用户当前该做什么」，就是流程解释型提示，必须删除。若需向评审者说明设计决策，写在 PRD 中，不写进原型。

### 页面间状态传递

使用 **URL 参数** 在页面间传递状态，页面加载时读取参数决定展示哪个视图：

```js
// 跳转时传参
window.location.href = 'user-upload-materials.html?path=1';

// 目标页面读取参数
const params = new URLSearchParams(window.location.search);
const path = params.get('path'); // "1" or "3"
if (path === '3') showPath3Form();
else showPath12Form();
```

### 交互设计模式

| 场景 | 实现方式 |
|------|---------|
| 多路径流程（如入驻路径①②③） | 在路径选择页点击卡片 → 跳转下一页并传 path 参数 |
| 多状态列表（如审核列表） | 列表项展示不同状态 → 点击某条 → 详情页传 status 参数 |
| 详情页多视图（如审核详情） | 读取 URL 的 status/type 参数 → 展示对应数据和操作按钮 |
| 表单提交后状态变化 | 提交按钮触发跳转 → 目标页（如状态页）传 status=approved |
| 角色视角切换 | 通过顶部用户信息区域的角色切换下拉菜单（模拟真实产品） |

### 列表页穷举设计

列表页必须包含**不同状态的示例数据**，让用户能点击任意状态进入对应详情：

```html
<!-- 审核列表：包含待审核、已通过、已驳回等不同状态条目 -->
<tr data-status="pending" onclick="location.href='detail.html?status=pending&id=1'">
  <td>张三</td><td><span class="badge">待审核</span></td>
</tr>
<tr data-status="approved" onclick="location.href='detail.html?status=approved&id=2'">
  <td>李四</td><td><span class="badge">已通过</span></td>
</tr>
<tr data-status="rejected" onclick="location.href='detail.html?status=rejected&id=3'">
  <td>王五</td><td><span class="badge">已驳回</span></td>
</tr>
```

### 详情页多态设计

详情页通过 URL 参数加载不同状态的数据和操作：

```js
const status = new URLSearchParams(location.search).get('status');
switch(status) {
  case 'pending':  showPendingView(); break;   // 展示通过/驳回按钮
  case 'approved': showApprovedView(); break;  // 只读展示+审核记录
  case 'rejected': showRejectedView(); break;  // 展示驳回原因+重提入口
}
```

---

## 分步生成流程

1. **确定端类型**：运营端/渠道端/用户端Web/用户端H5/登录页
2. **注入主题**：写入 `[data-theme="ddys"]` 完整样式块 + 画布渐变
3. **搭建布局骨架**：按端类型选择对应布局模板
4. **填充内容**：卡片 → 表格/表单 → 按钮/标签
5. **添加交互**：原生 JS（Tab 切换、弹窗、表单校验、URL参数读取、页面跳转）
6. **穷举状态数据**：确保列表/详情页包含所有可能的业务状态示例
7. **清理流程解释型提示**：自检页面中是否存在「点击XX后会…」「无论…均…」「下单后将…」等解释交互/设计规则的提示文案，命中即删除（详见「真实产品交互原则」）
8. **本地验证**：启动 http-server 确认页面渲染正常，各状态入口均可正常跳转

## 关键组件样式（必须包含）

每个原型页面的 `<style>` 中除了设计令牌变量外，还需包含以下手写组件基础样式：

```css
/* 按钮文字统一 12px */
[data-theme="ddys"] .btn {
  font-size: 12px;
  height: 32px;
  min-height: 32px;
  transition: all 0.3s;
}

/* 卡片无阴影 */
[data-theme="ddys"] .card {
  box-shadow: none;
}

/* 表格表头 */
[data-theme="ddys"] .table th {
  background: #fafafa;
  font-weight: 600;
  font-size: 14px;
}

/* 表格行 hover */
[data-theme="ddys"] .table tr:hover {
  background: #f5f5f5;
}

/* 状态标签无圆角 */
[data-theme="ddys"] .badge {
  border-radius: 0;
  font-size: 12px;
}

/* 过渡动画 */
[data-theme="ddys"] * {
  transition: all 0.3s;
}

/* 全局字体 */
[data-theme="ddys"] body {
  font-family: "PingFang SC", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
```

## OSS 上传（🔴 必须执行）

**每次原型创建或修改后，必须立即上传到阿里云 OSS。**

### OSS 配置

```js
const OSS = require('ali-oss');
const client = new OSS({
  region: 'oss-cn-shanghai',
  accessKeyId: process.env.OSS_ACCESS_KEY_ID,
  accessKeySecret: process.env.OSS_ACCESS_KEY_SECRET,
  bucket: process.env.OSS_BUCKET
});
```

### 上传脚本模板

```js
const files = ['pages/xxx.html']; // 修改的文件列表
const baseDir = 'd:/不动产qoder文件夹/output/zhelicha/v2-二期/prototype';

for (const f of files) {
  const localPath = require('path').join(baseDir, f);
  await client.put(f, localPath, {
    headers: { 'Content-Type': 'text/html; charset=utf-8' }
  });
}
```

### 公网访问地址

- 自定义域名: `https://demo.ddys-inc.com/`
- OSS 直接域名: `https://demoddys.oss-cn-shanghai.aliyuncs.com/`

### ⚠️ 注意事项

- 必须显式设置 `Content-Type: text/html; charset=utf-8`，否则浏览器会下载文件而非渲染
- 上传路径相对于 bucket 根目录（如 `pages/user-web-query-lawyer.html`）
- 上传完成后告知用户公网访问地址
