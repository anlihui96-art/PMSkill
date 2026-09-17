# DDYS 运营管理平台 — 原型设计规范

> 本规范定义了 DDYS 运营管理平台（这里查/这里拍/中台）原型的视觉标准。
> 设计语言来源：omp.ddys.tech 运营管理平台实际 CSS 提取。
> 实现方案：**纯原生 CSS + 原生 JS + 单文件 HTML**（零 CDN 依赖，`:root` CSS 变量承载 DDYS 设计令牌）。

## 一、设计哲学

DDYS 是 **B2B 企业级后台管理系统**，设计语言核心是 **功能优先、克制品牌**：

- **单一品牌色** `#2c3f89`（深邃靛蓝）承载所有交互信号——主按钮、链接、选中态、Tab 激活、表单聚焦
- **无装饰**：工作台界面不使用渐变、不使用卡片阴影、不使用装饰图片
- **高密度**：表格 14px、按钮 12px、表单紧凑间距，信息密度优先
- **色差分层**：白色卡片与 `#f7f8fa` 画布的色差建立层次，不靠阴影

## 二、主题配置

### 全局 CSS 主题

每个页面的 `<head>` 中**必须**包含以下样式块：

```html
<style>
  [data-theme="ddys"] {
    color-scheme: light;

    /* ── 品牌色 ── */
    --color-primary: #2c3f89;
    --color-primary-content: #ffffff;

    /* ── 语义色 ── */
    --color-secondary: #59626f;
    --color-secondary-content: #ffffff;
    --color-accent: #fa8c16;
    --color-accent-content: #ffffff;
    --color-neutral: #1d2129;
    --color-neutral-content: #f9fafb;

    /* ── 画布 & 表面 ── */
    --color-base-100: #ffffff;
    --color-base-200: #f7f8fa;
    --color-base-300: #e3e5e9;
    --color-base-content: #1d2129;

    /* ── 状态色 ── */
    --color-info: #2c3f89;
    --color-info-content: #ffffff;
    --color-success: #52c41a;
    --color-success-content: #ffffff;
    --color-warning: #faad14;
    --color-warning-content: #000000;
    --color-error: #da342e;
    --color-error-content: #ffffff;

    /* ── 圆角 ── */
    --radius-selector: 4px;   /* 交互元素：按钮、输入框、Radio */
    --radius-field: 4px;
    --radius-box: 8px;        /* 容器：卡片、弹窗、表格、侧边栏 */

    /* ── 尺寸 ── */
    --size-selector: 0.25rem;
    --size-field: 0.25rem;
    --border: 1px;
    --depth: 0;
    --noise: 0;

    /* ── DDYS 自定义 Token ── */
    --ddys-ink: #1d2129;
    --ddys-body: #1d2129;
    --ddys-body-secondary: #59626f;
    --ddys-body-muted: #86909c;
    --ddys-body-disabled: #999999;
    --ddys-border: #e3e5e9;
    --ddys-border-secondary: #d9d9d9;
    --ddys-divider: #f0f0f0;
    --ddys-divider-soft: #eeeeee;
    --ddys-surface-hover: #f5f5f5;
    --ddys-surface-table-header: #fafafa;
    --ddys-surface-gray: #f2f3f5;
    --ddys-surface-selected: #e6f7ff;
    --ddys-sider-bg: hsla(0, 0%, 100%, 0.72);
    --ddys-canvas-gradient: linear-gradient(180deg, #f3f7ff, rgba(247,248,250,0)), #f7f8fa;
    --ddys-primary-tint: #f2f4ff;
    --ddys-primary-tint-border: #dcebff;
    --ddys-danger-bright: #eb0045;
    --ddys-danger-hover: #ff3a3c;
    --ddys-danger-bg: #ffebec;
    --ddys-success-bg: #ebfaf5;
    --ddys-warning-bg: #fff8e6;
    --ddys-link-blue: #569cd6;

    /* ── 阴影 ── */
    --ddys-shadow-floating: 0 4px 10px 0 rgba(0,0,0,0.3);
    --ddys-shadow-card: 0 2px 8px rgba(0,0,0,0.1);
    --ddys-shadow-modal: 0 10px 20px 0 rgba(0,0,0,0.24);
    --ddys-shadow-popover: 0 3px 14px 2px rgba(0,0,0,0.05), 0 8px 10px 1px rgba(0,0,0,0.06), 0 5px 5px -3px rgba(0,0,0,0.1);
    --ddys-shadow-focus-ring: 0 0 0 2px #eb0045;

    /* ── 全局过渡 ── */
    --ddys-transition: all 0.3s;
  }
</style>
```

**HTML 根元素必须设置**：`<html lang="zh-CN" data-theme="ddys">`

### 画布渐变背景（必写）

页面 body 必须设置画布渐变：

```css
body {
  background: var(--ddys-canvas-gradient);
  min-height: 100vh;
}
```

### 色板说明

| 角色 | 色值 | 用途 |
|------|------|------|
| **Primary** | `#2c3f89` 深邃靛蓝 | 主按钮、链接、Tab选中、表单聚焦、菜单选中文字 |
| **Ink** | `#1d2129` 墨黑 | 标题、正文、表格单元格（**禁止使用 #000**） |
| **Body Secondary** | `#59626f` | 次级文本、时间戳、描述 |
| **Body Muted** | `#86909c` | 表单标签、占位符、禁用态 |
| **Canvas** | `#ffffff` | 卡片背景、弹窗背景 |
| **Canvas Light** | `#f7f8fa` | 页面背景、输入框背景 |
| **Surface Hover** | `#f5f5f5` | 表格行 hover、列表 hover |
| **Surface Table Header** | `#fafafa` | 表格表头背景 |
| **Border** | `#e3e5e9` | 系统主边框（卡片、表格、输入框） |
| **Divider** | `#f0f0f0` | 弹窗分割线、细分隔 |
| **Success** | `#52c41a` / bg `#ebfaf5` | 成功状态标签 |
| **Danger** | `#da342e` / hover `#ff3a3c` / bg `#ffebec` | 危险操作、删除 |
| **Sider BG** | `hsla(0,0%,100%,0.72)` | 侧边栏半透明白色 |

## 三、字体系统

### 字体族

```css
body {
  font-family: "PingFang SC", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
```

- **正文/UI**：PingFang SC（macOS）→ Segoe UI（Windows）→ Roboto（Linux）
- **数字展示**：`"DIN-700", "PingFang SC", sans-serif`（大屏数据看板）
- **代码**：`Menlo, Monaco, Consolas, monospace`

### 层级体系

| 层级 | 字号 | 字重 | 行高 | CSS 写法 | 用途 |
|------|------|------|------|-------------|------|
| 大标题 | 20px | 600 | 28px | `font-size:20px; font-weight:600` | 页面标题、Tab文字 |
| 弹窗标题 | 18px | 600 | 26px | `font-size:18px; font-weight:600` | 弹窗标题 |
| 副标题 | 16px | 500/600 | 24px | `font-size:16px; font-weight:500/600` | 卡片标题、区块标题 |
| 正文 | 14px | 400 | 22px | `font-size:14px; line-height:22px` | 默认正文、表格、表单 |
| 正文强调 | 14px | 500/600 | 22px | `font-size:14px; font-weight:500/600` | 表头、标签强调 |
| 辅助文本 | 12px | 400 | 20px | `font-size:12px; line-height:20px` | 标签、状态标签、时间戳 |
| 辅助强调 | 12px | 600 | 20px | `font-size:12px; font-weight:600` | 消息标题、小标题 |
| **按钮** | **12px** | 400 | 20px | `font-size:12px; line-height:20px` | **按钮文字（比正文小一档）** |

### 行高规则

**行高 = 字号 + 8px**，严格遵守：

- 12px → 20px（`leading-5`）
- 14px → 22px（`leading-[22px]`）
- 16px → 24px（`leading-6`）
- 18px → 26px（`leading-[26px]`）
- 20px → 28px（`leading-7`）

### 字重阶梯

仅使用 400 / 500 / 600 / 700，**禁止使用 300**。

- 400：正文默认
- 500：卡片标题中等强调（`font-medium`）
- 600：标题、表头（`font-semibold`）
- 700：仅 DIN 数字字体（`font-bold`）

## 四、PC 端布局规范（B 端管理后台）

适用：运营端、渠道端、中台

### 全局布局

```
┌────────────────────────────────────────────────────┐
│  Header (h-[56px], transparent, 渐变画布透出)        │
├────────────┬───────────────────────────────────────┤
│            │  Content Area (p-6)                   │
│  Sidebar   │  ┌─────────────────────────────────┐  │
│  w-[240px] │  │ Card (bg-white, rounded-lg)     │  │
│  m-4       │  │   p-6, 无阴影                    │  │
│  rounded-lg│  │                                 │  │
│  半透明白   │  └─────────────────────────────────┘  │
└────────────┴───────────────────────────────────────┘
```

### 侧边栏（浮岛式）

- 宽度 **240px**，外边距 **16px**（`m-4`），圆角 **8px**（`rounded-lg`）
- 背景 `hsla(0,0%,100%,0.72)` — **半透明白色**，悬浮在渐变画布上
- **不使用右边框**，靠色差和间距与内容区分离
- 菜单项：文字 `#59626f`（`text-[#59626f]`），14px/600
- 选中/hover：文字变为 `#1d2129`（`text-[#1d2129]`）
- **菜单中不使用品牌色 `#2c3f89` 作为文字色**
- 菜单内边距：上下 16px、左右 8px（`py-4 px-2`）

### 顶部导航栏

- 高度 **56px**（`h-14`）
- 背景**透明**（让画布渐变透出）
- 左侧：系统 Logo + 名称
- 右侧：消息通知 + 用户头像 + 下拉菜单

### 内容区

- 页面背景：画布渐变（`var(--ddys-canvas-gradient)`）
- 内边距：`p-6`（24px）
- 卡片：**白色背景 + 8px 圆角 + 24px 内边距 + 无阴影**
  - `bg-white rounded-lg p-6` — **不要加 shadow**
- 卡片间距：`gap-4`（16px）

### 数据表格

- 表头：背景 `#fafafa`，文字 `#1d2129` / 14px / 600
  - `bg-[#fafafa] text-[#1d2129] text-sm font-semibold`
- 单元格：文字 `#1d2129` / 14px / 400
- 行 hover：背景 `#f5f5f5`（`hover:bg-[#f5f5f5]`）
- 表格边框：`1px solid #e3e5e9`
- 表格圆角：`rounded-lg`（8px）+ `overflow-hidden`
- **表格行和状态标签不加圆角**（保持直角传达严谨性）

### 表单

- 标签：`#86909c` / 14px（`text-[#86909c] text-sm`）
- 输入框（工作台）：白色背景 + `1px solid #e3e5e9` 边框 + 4px 圆角 + 高度 32px
  - `bg-white border border-[#e3e5e9] rounded p-2 text-sm h-8`
- 输入框（登录页）：`#f7f8fa` 背景 + 无边框 + 4px 圆角 + 高度 44px
  - `bg-[#f7f8fa] border-0 rounded p-[13px_16px] h-11`
- 聚焦：边框变为 `#2c3f89`
- 表单项间距：`mb-4`（16px，**不超过 16px**）
- 必填标记：红色 `*`（`text-error`）

### 弹窗（Modal）

标准三段式结构：

```
┌──────────────────────────────┐
│ 标题 (18px/600)    [✕ 关闭] │  ← padding-bottom: 16px
│──────── 1px #f0f0f0 ────────│  ← 分割线
│                              │
│  内容区 (表单/表格)            │  ← padding: 24px
│                              │
│──────── 1px #f0f0f0 ────────│  ← 分割线
│         [取消]  [确认]        │  ← padding-top: 16px
└──────────────────────────────┘
```

- 圆角 8px，内边距 24px
- 标题：18px / 600 / `#1d2129`
- 关闭按钮：32×32px 圆形，hover 背景 `rgba(0,0,0,0.06)`
- 弹窗阴影：`0 10px 20px 0 rgba(0,0,0,0.24)`

### Tab 标签页

- Tab 文字：20px / 400（`text-xl`）
- 未选中：`#86909c`
- 选中：`#2c3f89`
- 激活下划线：**4px 高 × 40px 宽，胶囊形**（`rounded-full`），色 `#2c3f89`

### 按钮体系

| 类型 | 样式 | 用途 |
|------|------|------|
| 主按钮 | `bg-[#2c3f89] text-white rounded h-8 text-xs px-3` | 提交、确认 |
| 次按钮 | `bg-white text-[#1d2129] border border-[#e3e5e9] rounded h-8 text-xs px-3` | 取消、上一步 |
| 文字链接 | `text-[#2c3f89] bg-transparent border-0 text-xs` | 表格行内操作（查看/编辑） |
| 危险链接 | `text-[#ff3a3c] bg-transparent border-0 text-xs` | 表格行内删除 |
| 关闭按钮 | `w-8 h-8 rounded-full bg-transparent` | 弹窗关闭 |

**按钮高度统一 32px，文字统一 12px。**

### 状态标签

| 状态 | 样式 |
|------|------|
| 成功 | `bg-[#ebfaf5] text-[#52c41a] text-xs px-1`（无圆角） |
| 危险 | `bg-[#ffebec] text-[#da342e] text-xs px-1`（无圆角） |
| 警告 | `bg-[#fff8e6] text-[#faad14] text-xs px-1`（无圆角） |

**状态标签不加圆角**（`rounded-none`）。

### 树形侧栏

- 白色背景，宽度 240px，右侧 1px `#f0f0f0` 分割线
- 节点文字：12px / `#1d2129`
- 选中节点背景：`#e6f7ff`
- 常与右侧表格形成「树 + 表」布局

### 配置行

- 背景 `#f7f8fa`，圆角 8px，高度 44px，内边距 0 16px
- 左侧标签 12px / `#86909c`，右侧值 14px / `#1d2129`

## 五、移动端设计规范（C 端用户）

适用：用户端（律师查询、案件申请人查询）

### 布局

```
┌────────────────────────┐
│ Navbar (h-12, 固定顶部) │
├────────────────────────┤
│                        │
│  Content (p-4)         │
│  max-w-[414px]         │
│                        │
├────────────────────────┤
│ Dock (固定底部, 如需)   │
└────────────────────────┘
```

### 导航栏

- 高度 48px（`h-12`），白色背景 + 底部阴影
- 左侧：返回按钮 + 页面标题（`text-base font-medium`）
- 最大宽度 414px，居中

### 内容区

- 页面背景 `bg-base-200`
- 最大宽度 `max-w-[414px] mx-auto`
- 内边距 `p-4`
- 卡片：`bg-white rounded-xl p-4`（移动端圆角更大 12px）
- 卡片间距 `mb-4`

### 表单

- 输入框高度 44px（满足触摸目标）
- 按钮通栏：`btn btn-primary w-full`
- 上传区域：`border-2 border-dashed border-[#e3e5e9] rounded-xl p-6 text-center`

### 底部操作栏

- 固定底部（`fixed bottom-0`）
- 白色背景 + 顶部阴影 `shadow-[0_-2px_8px_rgba(0,0,0,0.06)]`
- 按钮通栏 + padding `p-4 pb-6`

## 六、阴影与层级

| 层级 | 值 | 用途 |
|------|---|------|
| Flat | 无阴影 | 页面画布、卡片、表格行 |
| 软边框 | `1px solid #e3e5e9` | 卡片、表格、输入框 |
| 浮动 | `0 4px 10px rgba(0,0,0,0.3)` | 下拉菜单、Popover |
| 弹窗 | `0 10px 20px rgba(0,0,0,0.24)` | Modal |
| 焦点环 | `0 0 0 2px #eb0045` | 输入框聚焦（红色） |

**核心原则**：
- **卡片无阴影**——靠白色与 `#f7f8fa` 画布的色差建立层次
- **阴影仅用于浮动元素**（下拉、弹窗、Popover）
- **焦点环用红色 `#eb0045`**，不用品牌色

## 七、圆角体系

| Token | 值 | 用途 |
|-------|---|------|
| `rounded-none` | 0px | 表格行、状态标签、分割线 |
| `rounded` | 4px | 按钮、输入框、交互元素 |
| `rounded-lg` | 8px | 卡片、弹窗、表格、侧边栏（**容器标准**） |
| `rounded-xl` | 12px | 大型卡片（移动端） |
| `rounded-2xl` | 16px | 登录面板（**仅品牌场景**） |
| `rounded-full` | 50% | 关闭按钮、圆形图标 |

## 八、间距系统

基础单位 4px，所有间距必须是 4 的倍数：

| Token | 值 | CSS 写法 | 用途 |
|-------|---|----------|------|
| xxs | 4px | `gap:4px` / `padding:4px` | 最小间距 |
| xs | 8px | `gap:8px` / `padding:8px` | 紧凑元素间距 |
| sm | 12px | `gap:12px` / `padding:12px` | 小间距 |
| md | 16px | `gap:16px` / `padding:16px` | **最常用**（卡片间距、表单项间距） |
| lg | 24px | `gap:24px` / `padding:24px` | 卡片内边距、内容区 padding |
| xl | 32px | `gap:32px` / `padding:32px` | 大区块分隔 |
| xxl | 40px | `padding:40px` | 特殊场景 |
| section | 56px | `padding:56px` | 登录面板内边距 |

## 九、Do's and Don'ts

### Do

- 使用 `#2c3f89` 作为唯一品牌交互色
- 卡片：白色 + 8px 圆角 + 24px 内边距，无阴影
- 表格：`#fafafa` 表头 + 14px/600 表头 + hover `#f5f5f5` + 1px `#e3e5e9` 边框
- 按钮文字 12px，高度 32px
- 弹窗三段式：标题头 + 分割线 + 内容 + 分割线 + 底部
- 行高 = 字号 + 8px
- 侧边栏半透明白色 + 浮岛效果
- 过渡动画统一 `transition-all duration-300`
- 间距值必须是 4 的倍数
- 文本色始终使用 `#1d2129`（墨黑），不用纯黑

### Don't

- **不要引入第二个品牌色**——所有交互信号都是 `#2c3f89`
- **不要在工作台使用渐变**——渐变仅限登录页
- **不要给卡片加阴影**——靠色差分层
- **不要用 16px 作正文字号**——正文统一 14px
- **不要在表格中用大于 14px 的字号**
- **不要给表格行/状态标签加圆角**
- **不要用 #000000**——用 `#1d2129`
- **不要在侧边栏用品牌色作文本色**——用 `#59626f`
- **不要用 300 字重**——阶梯为 400/500/600/700
- **不要表单项间距超过 16px**

## 十、登录页（品牌场景）

登录页是系统中**唯一使用大面积渐变和 16px 圆角**的场景：

- 背景：双层径向蓝色渐变（清晨天空感）
- 布局：左侧品牌展示 + 右侧登录面板（宽 540px）
- 面板：白色 + 16px 圆角 + 56px 内边距
- 输入框：`#f7f8fa` 背景 + 无边框 + 44px 高度
- Tab 切换：20px 文字 + 4px×40px 胶囊下划线
- ≤1200px：左侧品牌区隐藏，面板居中
