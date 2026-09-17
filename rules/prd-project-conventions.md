---
type: always_apply
---

# PRD 项目约定

本项目使用"五轮协作法"多 Agent 工作流生成 PRD 和 HTML 原型。

## 知识库

- 知识库路径：`d:\不动产qoder文件夹\openclaw-skills-knowledge-base\`
- 所有业务术语必须与知识库中的 `名词解释.md` 保持一致
- 涉及跨端功能时，需阅读所有相关端的文档

## 产出物

- 产出物根目录：`output/{project-id}/{iteration-id}/`
- PRD 文档：`output/{project-id}/{iteration-id}/prd/`
- 评审报告：`output/{project-id}/{iteration-id}/reviews/`
- HTML 原型：`output/{project-id}/{iteration-id}/prototype/pages/`
- 原型截图：`output/{project-id}/{iteration-id}/prototype/screenshots/`

## 编码约定

- PRD 使用中文编写
- HTML 原型使用 TailwindCSS CDN
- 文件命名使用 kebab-case（如 `order-list.md`、`user-detail.html`）
- 日期格式：YYYY-MM-DD

## 🔴 需求变更全量同步（强制，不可跳过）

**触发条件**：用户提出任何需求修改（新增/删除/修改字段、功能、页面、按钮、弹窗、布局、样式等）

**强制执行以下 4 步，禁止跳步或省略**：

### Step 1：执行主修改
修改用户明确指定的文件，同步记录 PRD 13.2 变更日志（Q编号连续递增）。

### Step 2：强制 Grep 全局搜索（⚠️ 必须调用 Grep 工具）
对改动涉及的关键词（功能名、字段名、页面名等）调用 Grep 工具，搜索 `output/{project-id}/{iteration-id}/` 整个目录。

### Step 3：逐一同步关联文件
根据 Grep 结果，逐一修改所有需更新的关联文件：
- PRD 主文档（功能概览表、字段说明表、交互流程、变更记录）
- phase1-feature-list.md（用户故事）
- context.md（模块描述）
- prototype/index.html（导航页卡片描述）
- 所有涉及该功能/字段的 HTML 原型页面
- prd-append.md（如适用）

### Step 4：Grep 验证无遗漏（⚠️ 必须再次调用 Grep 工具）
确认所有关联文件已同步，方可报告完成。

**违反标志：修改完文件后直接报告完成、未执行 Step 2 的 Grep 调用 = 违反此约束。**

## 工作流触发

当用户说以下内容时，自动触发 `prd-workflow` Skill：
- "生成 PRD"
- "需求分析"
- "产品设计"
- "写需求文档"
- "PRD"

## Output 目录结构规范

### 设计原则
1. **项目隔离**：不同项目的产出物完全隔离在各自的项目目录下
2. **迭代可追溯**：同一项目的多次迭代有清晰的版本线
3. **结构一致**：每个迭代内部遵循统一的子目录结构
4. **向下兼容**：新项目/迭代创建不影响已有产出

### 目录结构

    output/
    ├── {project-id}/                    # 项目层
    │   ├── project-meta.md              # 项目元信息
    │   ├── {iteration-id}/              # 迭代层
    │   │   ├── context.md              # 需求上下文
    │   │   ├── prd/                    # PRD文档
    │   │   │   ├── phase1-feature-list.md
    │   │   │   ├── phase1-page-structure.md
    │   │   │   ├── PRD-{name}-v{n}.md
    │   │   │   └── prd-append.md
    │   │   ├── reviews/                # 评审报告
    │   │   │   ├── dev-review-v{n}.md
    │   │   │   ├── qa-review-v{n}.md
    │   │   │   └── integration-report.md
    │   │   ├── prototype/              # 原型文件
    │   │   │   ├── index.html
    │   │   │   ├── shared.js
    │   │   │   ├── pages/
    │   │   │   └── screenshots/
    │   │   └── interaction-design.md
    │   └── {iteration-id-2}/
    └── _archive/                        # 归档区

### 命名约定

| 层级 | 命名规则 | 示例 |
|------|---------|------|
| 项目ID | 小写拼音或英文简写 | zhelicha、zhelipai、zhongtai |
| 迭代ID | v{n}-{功能简述} | v1-基础查询、v2-二期、v3-支付对接 |
| PRD文件 | PRD-{中文名}-v{n}.md | PRD-这里查二期-v2.md |
| 评审文件 | {type}-review-v{n}.md | dev-review-v2.md |
| 截图文件 | 静态：{page-name}.png；交互：{page-name}_{state}.png | ops-order-list.png、user-web-login_error.png |

### project-meta.md 模板

每个项目目录下必须有 project-meta.md，记录项目元信息和迭代历史：

    # 项目元信息

    - **项目名称**：{name}
    - **项目ID**：{id}
    - **创建时间**：{date}
    - **项目描述**：{description}
    - **相关知识库**：openclaw-skills-knowledge-base/{app}/

    ## 迭代记录

    | 迭代ID | 名称 | 状态 | 时间 |
    |--------|------|------|------|
    | v1-xxx | ... | 已完成/进行中 | 20xx |

### 工作流中的使用

- Phase 0 首步必须确认 project-id 和 iteration-id
- 所有Agent的输出路径均基于 `output/{project-id}/{iteration-id}/`
- 新项目首次使用时需创建 project-meta.md
- 迭代完成后在 project-meta.md 中更新状态为"已完成"
