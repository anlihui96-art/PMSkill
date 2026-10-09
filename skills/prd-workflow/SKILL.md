---
name: prd-workflow
description: >
  PRD 多 Agent 协作工作流编排。管理从需求澄清到原型交付的完整 4 阶段流程。
  当用户需要生成 PRD、进行需求分析、启动产品设计流程、编写产品文档时使用。
  编排 pd-agent、ued-agent、dev-agent、qa-agent 四个 Subagent 协作完成。
  触发词：PRD、需求分析、产品设计、生成文档、需求文档。
---

# PRD 多 Agent 协作工作流

> 本 Skill 指导主 Agent 编排 4 个角色（pd-agent、ued-agent、dev-agent、qa-agent）完成从需求澄清到原型交付的完整流程。
> DSH 环境下这些角色由 `subagent` 工具 + 仓库 `agents/*.md` 角色定义实现，具体见下方「运行环境与前置配置」。

## 流程总览

```
Phase 0：需求澄清（主 Agent 与用户对话）
    ↓
Phase 1：需求分析（pd-agent）
    ↓ 用户确认
Phase 2：PRD 初稿（pd-agent）
    ↓ 用户审阅
Phase 3：深度评审（dev-agent + qa-agent → pd-agent 整合）
    ↓
Phase 4：原型交付（交互设计 → ued-agent 生成 → 用户确认结构 → 链接回写）
    ↓
完成交付
```

## 运行环境与前置配置（必读）

本 Skill 从 Qoder 迁移到 DSH 运行。下面 4 条约定是**所有 Phase 的前提**，每次进入工作流前先确认。

### 1. 本机路径配置

本机相关的绝对路径统一记录在用户级配置文件里，**不要在文档或 prompt 中硬编码本机路径**：

```
~/.pm-skill/config.yml
```

| 字段 | 含义 | 缺失/为空时的行为 |
|------|------|------------------|
| `repoRoot` | PMSkill 仓库在本机的克隆路径（`agents/*.md` 角色定义所在仓库根目录） | 用 `glob` 工具按 `**/agents/pd-agent.md` 定位仓库根目录，定位到后写回该配置 |
| `knowledgeBase` | 产品知识库根目录（原 Qoder 环境为 `openclaw-skills-knowledge-base`） | 视为**未配置**：跳过所有知识库读取步骤，并在回复开头提示用户「知识库未配置」 |

读取方式（文件可能不存在）：

```bash
cat "$HOME/.pm-skill/config.yml" 2>/dev/null || echo "NOT_CONFIGURED"
```

配置不存在或字段为空时：先向用户确认，拿到答案后创建/更新该文件再继续。**知识库未配置不阻塞流程**，按「未配置」降级即可。

下文出现的 `{knowledgeBase}` 均指该配置中的知识库根目录。

### 2. Subagent 委派约定

DSH **没有** `pd-agent` / `ued-agent` / `dev-agent` / `qa-agent` 这类预置子代理，也读不到 Qoder 的 agent 注册表。这 4 个角色在本仓库里就是普通的 Markdown 角色定义文件：

```
{repoRoot}/agents/pd-agent.md
{repoRoot}/agents/ued-agent.md
{repoRoot}/agents/dev-agent.md
{repoRoot}/agents/qa-agent.md
```

**委派一个角色 = 用 `subagent` 工具发起一次委派**，prompt 按以下结构拼接：

```
<读取 {repoRoot}/agents/<角色>.md 得到的完整正文>

---

## 本次任务

<对应 Phase 的「任务 prompt」，即本文件各 Phase 代码块内的内容>
```

要点：

- 角色定义正文必须**原样放在 prompt 最前面**，它包含该角色的身份、职责与输出规范。
- 角色文件 frontmatter 里的 `tools` / `skills` 是 Qoder 写法，DSH 会忽略；请在 prompt 末尾明确写出该角色要加载的技能，例如「用 `skill` 工具加载 `tech-review`，按其维度评审」。
- **需要并行时**（Phase 3 的 dev-agent + qa-agent），在**同一条回复里同时发起两个 `subagent` 调用**，不要串行等待。
- 子代理之间不共享上下文，全部靠文件系统传递：prompt 里必须写清要读、要写的**具体文件路径**。
- 委派前先用 `mkdir -p` 建好输出目录，避免子代理写文件失败。
- 若当前会话没有 `subagent` 工具，退化为顺序执行各角色任务（由主 Agent 依次扮演角色），并在交付报告中说明。

### 3. 技能与同目录资源的引用方式

- 其它技能用 `skill` 工具**按名字**加载：`prd-writer`、`incremental-prd`、`prd-sync`、`html-prototype`、`tech-review`、`test-review`、`effort-estimate`、`knowledge-base-nav`。
- 本 Skill 目录下的资源文件，用加载本 Skill 时返回的**基目录**拼接定位（工具结果里的 `resourceBase`，即提示中的「Base directory for this skill」）：
  - `<基目录>/WORKFLOW-DETAIL.md` — 各 Phase 的详细 prompt 模板
  - `<基目录>/CONTEXT-TEMPLATE.md` — `context.md` 字段模板
- **不要**用 `../../` 之类相对路径向上找仓库根目录：技能是通过软链接注册的，基目录就是 `~/.dsh/skills/prd-workflow` 这个软链，向上回溯到不了仓库。需要仓库内的路径（如 `agents/*.md`）时，用配置里的 `repoRoot`。

### 4. 能力缺失时的降级

| 能力 | DSH 现状 | 处理方式 |
|------|---------|---------|
| 知识库读取 | 取决于 `knowledgeBase` 是否配置 | 未配置则跳过，并提示用户 |
| 原型 / PRD 发布 | Qoder 用 Vercel（`/vercel-deploy`），DSH 没有该命令 | 改用 `oss-upload` 上传并挂总导航 `https://demo.ddys-inc.com/index.html`，**交付完成的标志是给出线上 URL**。本地预览只是次级备选，**不得占用 PRD 主链接位**；取不到凭据时如实说明「未上传 OSS，交付未完成」 |
| Qoder 的 agent 自动编排 | 不存在 | 用上面的 `subagent` 委派约定代替 |

---

## 初始化

收到用户的 PRD 需求后，按以下步骤初始化：

1. 确认项目与迭代标识：
   - **项目ID**：确认属于哪个项目（如 zhelicha、zhelipai、zhongtai），若为新项目则创建 `output/{project-id}/project-meta.md`
   - **迭代ID**：确认本次迭代标识（如 v3-支付对接），格式为 `v{n}-{功能简述}`
   - **输出根路径**：确认为 `output/{project-id}/{iteration-id}/`
   若用户未明确指定，通过提问确认。确认后所有后续产出均存放于该路径下。

2. 创建输出目录（如不存在）：
```bash
mkdir -p output/{project-id}/{iteration-id}/prd output/{project-id}/{iteration-id}/reviews output/{project-id}/{iteration-id}/prototype/pages
```

3. 读取 [CONTEXT-TEMPLATE.md] 创建 `output/{project-id}/{iteration-id}/context.md` 初始文件

4. 向用户确认基本信息：
   - 应用名（中台 / 这里拍 / 这里查）
   - 目标端（用户小程序端 / 商家端 / 运营管理端 等）
   - 需求概述（一句话描述）

---

## Phase 0：需求澄清（主 Agent 直接对话 + 知识库辅助）

**目标**：理解需求背景，明确范围。

**执行步骤**：

1. 确定项目与迭代标识（Phase 0 首步）：

   在开始需求澄清前，主Agent需确认：
   - **项目ID**：确认属于哪个项目（如 zhelicha、zhelipai、zhongtai），若为新项目则创建 project-meta.md
   - **迭代ID**：确认本次迭代标识（如 v3-支付对接），格式为 `v{n}-{功能简述}`
   - **输出根路径**：确认为 `output/{project-id}/{iteration-id}/`

   若用户未明确指定，通过提问确认。确认后所有后续产出均存放于该路径下。

2. 读取知识库入口文件建立业务上下文（**若 `knowledgeBase` 未配置则跳过本步并提示用户**）：
   - `{knowledgeBase}/CLAUDE.md` — 系统全貌
   - `{knowledgeBase}/index.md` — 定位相关文档
   - 根据用户描述的应用名，读取对应应用的名词解释和相关业务文档

3. 使用结构化提问与用户澄清（每轮可同时提出多个问题，按 4 个维度组织）：
   - **目标与背景**：用户的目标是什么？为什么需要这个功能？解决什么问题？
   - **范围与边界**：涉及哪些端？哪些页面？哪些用户角色？
   - **优先级与约束**：优先级如何？有没有特殊约束或限制？
   - **关联与影响**：与现有功能的关系是什么？是否影响其他端？

4. 读取知识库中相关文档，验证业务理解是否准确

5. 将澄清结果写入 `output/{project-id}/{iteration-id}/context.md`

**完成标志**：用户确认需求范围，或用户表示"需求已足够清晰，跳过澄清"。

---

## Phase 1：需求分析

**目标**：确定功能范围、交互流程和端联动影响。

### Step 1：委派 pd-agent

按「Subagent 委派约定」用 `subagent` 工具委派 `pd-agent`（角色定义：`{repoRoot}/agents/pd-agent.md`），prompt 中的任务部分如下：

```
先读取以下文件了解业务背景：
1. output/{project-id}/{iteration-id}/context.md — 需求上下文
2. {knowledgeBase}/{应用名}/名词解释.md — 术语对齐（知识库未配置则跳过）
3. 知识库中与需求相关的业务文档

任务：
1. 输出功能列表（按端→模块分组，每个功能含优先级P0-P3和用户故事）
2. 输出核心交互流程（每个功能的正常流程和异常流程）
3. 输出交互设计清单（每个页面的关键交互：字段联动、状态转换、异常反馈、表单校验规则）
4. 完成各端联动影响分析，根据所属应用确定联动范围：
   - **这里拍**：运营端、商家端、服务商端、用户端（4端联动）
   - **这里查**：运营端、渠道端、用户端（3端联动）

将结果写入 output/{project-id}/{iteration-id}/prd/phase1-feature-list.md
```

### Step 2：用户确认

向用户展示功能列表和交互设计清单：
- 功能列表（pd-agent 产出）
- 交互设计清单（每个页面的关键交互）

询问用户：
- ✅ 方案 OK，进入 Phase 2
- ⚠️ 有小调整，说明后继续
- ❌ 需要重新设计

确认后更新 `output/{project-id}/{iteration-id}/context.md` 追加 Phase 1 结论。

---

## Phase 2：PRD 初稿

**目标**：输出完整的 PRD 文档（13 个章节）。

### Step 1：委派 pd-agent 生成 PRD

按「Subagent 委派约定」用 `subagent` 工具委派 `pd-agent`；委派前先用 `skill` 工具加载 `prd-writer` 与 `incremental-prd` 并在 prompt 中要求该角色遵循。prompt 中的任务部分如下：

```
先读取以下文件：
1. output/{project-id}/{iteration-id}/context.md — 全局上下文
2. output/{project-id}/{iteration-id}/prd/phase1-feature-list.md — Phase 1 功能列表（含交互设计清单）
3. 知识库中所有相关文档（按 index.md 定位；知识库未配置则跳过）

任务：
1. 先完成影响分析（12 维度 + 各端联动），输出影响分析确认
2. 按 13 章标准模板生成完整 PRD
3. 第十一章"功能需求"必须严格按五段式组织：
   - ##### 需求描述（多段文字，不允许只写一句话）
   - ##### 核心交互流程（按 Case 编号）
   - ##### 页面说明（页面层级结构 + 字段说明表 + 校验规则表 + 异常处理表 + 原型占位）

将 PRD 写入 output/{project-id}/{iteration-id}/prd/PRD-{功能名称}-v1.md
```

### Step 2：用户审阅

向用户展示 PRD 初稿，附带轻量确认提示：

```markdown
## ⚡ 轻量确认（Phase 2 完成）
- ✅ 无大问题，继续评审（进入 Phase 3）
- ⚠️ 有小问题，评审时调整：[说明]
- ❌ 有大问题，需要重新写：[说明]
```

如有修改，再次调用 pd-agent 修订。确认后更新 `output/{project-id}/{iteration-id}/context.md`。

---

## Phase 3：深度评审 + 最终 PRD

**目标**：通过技术和测试视角评审，整合后输出最终版本。

### Step 1：并行委派 dev-agent 和 qa-agent

在**同一条回复里同时发起两个 `subagent` 调用**（角色定义分别为 `{repoRoot}/agents/dev-agent.md`、`{repoRoot}/agents/qa-agent.md`）；委派前先加载 `tech-review` / `test-review` 技能，并要求对应角色按其维度评审。

**dev-agent 的任务 prompt**：
```
先读取以下文件：
1. output/{project-id}/{iteration-id}/prd/PRD-{name}-v1.md — 待评审 PRD
2. output/{project-id}/{iteration-id}/context.md — 项目背景
3. 知识库中相关架构文档（知识库未配置则跳过）

任务：对 PRD 进行技术可行性评审，输出：
1. 综合评分（1-5）
2. 工作量估算（人天）
3. 逐项评审（按 PRD 章节，含技术可行性和风险等级）
4. 风险清单（含缓解方案）
5. 技术方案建议（数据模型/接口/权限）

将评审报告写入 output/{project-id}/{iteration-id}/reviews/dev-review.md
```

**qa-agent 的任务 prompt**：
```
先读取以下文件：
1. output/{project-id}/{iteration-id}/prd/PRD-{name}-v1.md — 待评审 PRD
2. output/{project-id}/{iteration-id}/context.md — 项目背景
3. 知识库中相关业务文档（知识库未配置则跳过）

任务：对 PRD 进行测试场景评审，输出：
1. 测试场景覆盖度评估
2. PRD 问题清单（分类标记：模糊/遗漏/矛盾/不可测）
3. 测试场景矩阵（每个功能模块的正常+异常场景）
4. 验收标准建议
5. 边界条件分析

将评审报告写入 output/{project-id}/{iteration-id}/reviews/qa-review.md
```

### Step 2：委派 pd-agent 整合评审

按「Subagent 委派约定」委派 `pd-agent`（委派前先加载 `incremental-prd` 技能），任务 prompt 如下：

```
先读取以下文件：
1. output/{project-id}/{iteration-id}/prd/PRD-{name}-v1.md — PRD 初稿
2. output/{project-id}/{iteration-id}/reviews/dev-review.md — 技术评审报告
3. output/{project-id}/{iteration-id}/reviews/qa-review.md — 测试评审报告

任务：
1. 汇总 DEV 和 QA 的评审意见
2. 按优先级（高风险>中风险>低风险）逐条处理
3. 输出整合报告（章节/建议/采纳情况/修改内容）
4. 修订 PRD 生成 v2 版本

将整合报告写入 output/{project-id}/{iteration-id}/reviews/integration-report.md
将最终 PRD 写入 output/{project-id}/{iteration-id}/prd/PRD-{name}-v2.md
```

### Step 3：向用户展示

展示最终 PRD + 评审报告 + 整合报告，用户确认后进入 Phase 4。

---

## Phase 4：原型交付

**目标**：基于最终 PRD 生成高质量 HTML 原型（布局+交互），用户确认页面结构后链接回写。

### Step 1：交互设计（主 Agent）

在调用 ued-agent 之前，主 Agent 先从 PRD 第十一章提取每个页面的**交互设计清单**，写入 `output/{project-id}/{iteration-id}/prd/interaction-design.md`：

```markdown
# 交互设计清单

## {页面名}
| # | 交互 | 触发条件 | 行为 | 反馈 |
|---|------|---------|------|------|
| 1 | 切换客户类型 | 点击律师/案件申请人Tab | 表单字段联动更新、费用重新计算 | Toast提示 |
| 2 | OCR上传 | 选择文件后 | 显示加载动画 → 识别结果填充表单 | 识别失败提示 |
| ... |
```

**设计原则**：
- 每个页面至少 3 个有意义的交互（不是只有 Toast）
- 多步骤流程必须包含步骤间状态保持和进度指示
- 表单必须包含前端校验（非空、格式、长度）
- 列表页必须包含筛选/搜索/分页的完整交互
- 弹窗/抽屉必须有关闭、overlay、ESC关闭

### Step 2：委派 ued-agent 生成原型

按「Subagent 委派约定」委派 `ued-agent`（角色定义：`{repoRoot}/agents/ued-agent.md`）；委派前先用 `skill` 工具加载 `html-prototype`，并要求该角色遵循其中的端布局类型与交互规范。任务 prompt 如下：

```
先读取以下文件：
1. output/{project-id}/{iteration-id}/prd/PRD-{name}-v2.md — 最终 PRD
2. output/{project-id}/{iteration-id}/prd/interaction-design.md — 交互设计清单

技术要求：
- 技术栈：纯原生 CSS + 原生 JS + 单文件 HTML（零 CDN 依赖，`:root` CSS 变量承载 DDYS 设计令牌）
- 布局规范：参考 html-prototype Skill 中的端布局类型
- **交互组件**：modal/drawer/tabs/toast 一律手写（原生 HTML/CSS/JS），参照 v8 原型既有模式，必须完整实现打开/关闭/overlay/ESC 关闭
- **分步生成**：先完成静态布局（所有字段、表格、布局），再注入交互逻辑

交互质量要求（重要）：
- 每个页面必须实现 interaction-design.md 中列出的所有交互
- 禁止用 showToast('功能开发中') 这种占位交互替代真实交互
- 多步骤流程必须有真实的步骤状态管理（上一步/下一步/进度条）
- 表单必须有前端校验（实时或提交时）
- 弹窗/抽屉必须有打开/关闭/overlay/ESC关闭的完整交互
- Tab切换必须保持内容区联动
- 列表页筛选/搜索必须有实时过滤效果

任务：
1. 解析 PRD 第十一章 + 交互设计清单，提取所有页面
2. 为每个页面按 DDYS 设计令牌手写组件样式生成静态布局，再注入业务交互逻辑
3. 生成导航首页 index.html（链接到各页面）
4. 启动本地 HTTP 服务验证页面可正常渲染

输出：
- HTML 文件 → output/{project-id}/{iteration-id}/prototype/pages/*.html
- 导航首页 → output/{project-id}/{iteration-id}/prototype/index.html
```

> **注意**：任务 1-4 由 ued-agent 执行，**不做截图**（团队约定取消截图环节，交付物不含 `screenshots/`）。发布不在 ued-agent 内做：ued-agent 完成后由主 Agent 用 `oss-upload` 技能上传（`--prefix` 按项目），并挂到总导航 `https://demo.ddys-inc.com/index.html`。**发布是共享资源操作，需当次明确授权**：先与线上 diff 确认无他人改动 → 备份 → 只追加不重排 → 上传后回归其他项目 Tab。

### Step 3：用户确认页面结构

原型生成后，向用户展示：
- **线上预览地址**（`oss-upload` 上传后的 `https://demo.ddys-inc.com/<项目前缀>/...`）；未获当次发布授权或取不到凭据时，才用本地预览作次级备选并注明「未上传 OSS，交付未完成」

询问用户：
- ✅ 结构 OK，继续回写
- ⚠️ 需要调整：[说明哪些页面需要修改]
- ❌ 重新生成：[说明原因]

如有调整，再次调用 ued-agent 修订。确认后进入回写步骤。

### Step 4：回写原型到 PRD

原型确认后，主 Agent 将原型信息回写到 PRD 第十一章：

```
遍历 PRD 第十一章每个页面的 `###### 原型` 段落，填入：
- **预览链接**：线上地址（https://demo.ddys-inc.com/<项目前缀>/...）或仓库内相对路径
- 替换所有"待 UED 填充"占位符
```

> 团队约定：「发布」与「把线上地址写回 PRD」是两件**可分开授权**的事。照常发布并回报线上 URL，但 PRD 第 3 章默认保留仓库内相对路径——**写不写线上地址按当次授权**。

### Step 5：完成交付

汇总所有交付物，输出交付报告：

```markdown
# PRD 交付报告

## 交付物清单
| 文件 | 说明 |
|------|------|
| output/{project-id}/{iteration-id}/prd/PRD-{name}-v2.md | 最终 PRD（含原型预览链接） |
| output/{project-id}/{iteration-id}/prd/interaction-design.md | 交互设计清单 |
| output/{project-id}/{iteration-id}/reviews/dev-review.md | 技术评审 |
| output/{project-id}/{iteration-id}/reviews/qa-review.md | 测试评审 |
| output/{project-id}/{iteration-id}/reviews/integration-report.md | 整合报告 |
| output/{project-id}/{iteration-id}/prototype/index.html | 原型导航 |
| output/{project-id}/{iteration-id}/prototype/pages/*.html | 原型页面 |
| 线上地址 | 公网可访问原型（https://demo.ddys-inc.com/<项目前缀>/...，挂总导航后） |
```

---

## 上下文传递机制

所有 Subagent 通过**文件系统**传递上下文：

| 文件 | 用途 | 维护者 |
|------|------|--------|
| `output/{project-id}/{iteration-id}/context.md` | 全局上下文，逐步追加 | 主 Agent |
| `output/{project-id}/{iteration-id}/prd/phase1-feature-list.md` | Phase 1 产出（功能列表+交互设计清单） | pd-agent |
| `output/{project-id}/{iteration-id}/prd/PRD-*-v1.md` | PRD 初稿 | pd-agent |
| `output/{project-id}/{iteration-id}/reviews/*.md` | 评审报告 | dev-agent / qa-agent |
| `output/{project-id}/{iteration-id}/prd/PRD-*-v2.md` | 最终 PRD | pd-agent |
| `output/{project-id}/{iteration-id}/prd/interaction-design.md` | 交互设计清单 | 主 Agent |
| `output/{project-id}/{iteration-id}/prototype/*` | HTML 原型 | ued-agent |

每次调用 Subagent 时，在 prompt 中指明需要读取的文件路径。

## 流程回退规则

```
Phase 3 → Phase 1：有范围问题，回退重新确认需求
Phase 3 → Phase 2：有设计问题，回退重写 PRD
Phase 4 → Phase 2：PRD 有重大遗漏，回退补充
```

## 详细参考资料

- 各 Phase 的详细 prompt 模板见 `<基目录>/WORKFLOW-DETAIL.md`
- context.md 的字段模板见 `<基目录>/CONTEXT-TEMPLATE.md`

> `<基目录>` 是本 Skill 被 `skill` 工具加载时返回的目录路径，见「技能与同目录资源的引用方式」。
