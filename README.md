# PMSkill · 产品经理 AI 协作技能库

面向不动产 SaaS 产品（中台 / 这里拍 / 这里查）的一套 **Qoder 产品经理工作流资产**，包含多 Agent 协作工作流、9 个技能（Skills）、4 个角色 Agent 和项目约定，覆盖从**需求澄清 → PRD 编写 → 技术/测试评审 → HTML 原型交付**的完整链路。

## 目录结构

```
PMSkill/
├── skills/          # 9 个技能定义（含工作流编排）
├── agents/          # 4 个角色 Agent（被 prd-workflow 编排调用）
└── rules/           # PRD 项目通用约定
```

## 核心工作流

`skills/prd-workflow` 是整套体系的主线，编排 4 个角色 Agent 完成 4 阶段流程：

```
Phase 0 需求澄清（主 Agent 对话 + 知识库辅助）
   ↓
Phase 1 需求分析（pd-agent）→ 用户确认
   ↓
Phase 2 PRD 初稿（pd-agent，13 章模板）→ 用户审阅
   ↓
Phase 3 深度评审（dev-agent + qa-agent → pd-agent 整合）→ 最终 PRD
   ↓
Phase 4 原型交付（主 Agent 交互设计 → ued-agent 生成 HTML → 用户确认 → 链接回写 PRD）
```

各 Subagent 通过**文件系统**传递上下文（`context.md` / `phase1-feature-list.md` / `PRD-*-v1/v2.md` / `reviews/*.md` / `interaction-design.md` / `prototype/*`），并内置 Phase 间的流程回退规则。

## 角色 Agents（agents/）

| Agent | 角色 | 职责 |
|-------|------|------|
| `pd-agent` | 产品经理 | 需求澄清、需求分析、PRD 文档创作、评审意见整合 |
| `ued-agent` | UED 设计师 | 页面结构设计、交互设计、HTML 原型生成 |
| `dev-agent` | 技术架构师 | 技术可行性评审、架构设计、接口设计、风险评估 |
| `qa-agent` | 测试工程师 | 测试场景评审、验收标准定义、边界条件分析、PRD 质量评估 |

## 技能 Skills（skills/）

| 技能 | 说明 |
|------|------|
| `prd-workflow` | PRD 多 Agent 协作工作流编排，管理 4 阶段全流程（含 `WORKFLOW-DETAIL.md` 详细 prompt 模板、`CONTEXT-TEMPLATE.md` 上下文模板） |
| `prd-writer` | PRD 编写规范与 13 章标准模板，含影响分析 12 维度（`templates/prd-template.md`） |
| `incremental-prd` | PRD 增量编写约束：修改已有功能时仅描述新增/变更部分，禁止重复定义已有字段 |
| `prd-sync` | PRD 关联文件全量同步：变更影响识别 → Grep 扫描 → 批量同步 → Grep 验证 |
| `html-prototype` | HTML 原型生成规范：纯原生 CSS/JS 单文件方案、DDYS 设计系统（含 `DESIGN-SPEC.md`） |
| `effort-estimate` | 按角色（PM/UED/后端/前端/QA）拆解工期预估并输出 Excel（含 `scripts/generate-estimate.js`） |
| `knowledge-base-nav` | 产品知识库导航，覆盖中台/这里拍/这里查三个应用的业务文档 |
| `tech-review` | 技术可行性评审规范：评审维度、风险等级 P0-P3、工作量估算与输出格式 |
| `test-review` | 测试场景评审规范：测试维度、用例设计、验收标准、PRD 问题标记 |

## 项目约定（rules/）

`prd-project-conventions.md` 定义 PRD 项目的通用约定（命名、输出路径、章节规范等），供各 Agent 与技能共同遵循。

## 使用方式

1. 将 `skills/`、`agents/`、`rules/` 放入 Qoder 项目的 `.qoder/` 目录下：

   ```
   <你的项目>/.qoder/
   ├── skills/
   ├── agents/
   └── rules/
   ```

2. 在 Qoder 对话中提出 PRD 相关需求（如"写一份 XX 功能的 PRD"），`prd-workflow` 会自动触发并编排各角色 Agent 完成全流程。
3. 也可单独调用某个技能（如 `effort-estimate` 估算工期、`prd-sync` 同步关联文件）。

## 说明

- 技能与 Agent 中的知识库路径、项目名（中台/这里拍/这里查）为原始团队环境配置，迁移到其他项目时需按实际情况调整。
- 本仓库为团队内部产品工作流资产，欢迎在此基础上扩展新的技能与角色 Agent。
