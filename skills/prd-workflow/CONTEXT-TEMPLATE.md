# PRD 项目上下文模板

> 本文件定义 `output/{project-id}/{iteration-id}/context.md` 的标准结构。主 Agent 在初始化 PRD 项目时参考本模板创建 context.md，并在每个 Phase 完成后追加结论。

---

## 模板

```markdown
# PRD 项目上下文

## 项目信息

- **项目ID**：{project-id}
- **项目名称**：{project-name}
- **迭代ID**：{iteration-id}
- **迭代名称**：{iteration-name}
- **输出路径**：output/{project-id}/{iteration-id}/

## 基本信息

| 字段 | 值 |
|------|-----|
| 项目名称 | {项目名称} |
| 应用 | {中台 / 这里拍 / 这里查} |
| 目标端 | {用户小程序端 / 商家端 / 运营管理端 / 用户PC端 / 服务商端 / 律所端 / 运营端} |
| 启动日期 | {YYYY-MM-DD} |
| 优先级 | {P0 / P1 / P2} |
| 状态 | {Phase 0 / Phase 1 / Phase 2 / Phase 3 / Phase 4 / 已完成} |

## 需求背景

{描述业务现状、痛点、为什么需要这个功能}

## 需求目标

{期望达成的目标，可量化的衡量指标}

## 影响范围

### 涉及的端
- {端名1}：{影响说明}
- {端名2}：{影响说明}

### 涉及的模块
- {模块1}：{新增/修改}
- {模块2}：{新增/修改}

### 相关知识库文档
- {文档路径1} — {说明}
- {文档路径2} — {说明}

## 核心用户故事

| 角色 | 用户故事 | 优先级 |
|------|---------|:------:|
| {角色} | 作为{角色}，我希望{功能}，以便{价值} | P0 |

## 特殊约束

- {约束1}
- {约束2}

---

## Phase 0 结论（需求澄清）

- [ ] 需求范围已确认
- [ ] 涉及端已确认
- [ ] 优先级已确认
- [ ] 特殊约束已识别

**关键决策**：
{澄清过程中的关键决策记录}

---

## Phase 1 结论（需求与设计协作）

- [ ] 功能列表已确认
- [ ] 页面结构方案已选定
- [ ] 选定方案：{方案名称}

**关键决策**：
{设计方案的选定原因和调整说明}

---

## Phase 2 结论（PRD 初稿）

- [ ] PRD 初稿已完成
- [ ] 用户审阅通过

**PRD 文件**：output/{project-id}/{iteration-id}/prd/PRD-{name}-v1.md

**用户反馈**：
{用户的修改意见}

---

## Phase 3 结论（深度评审）

- [ ] DEV 技术评审完成
- [ ] QA 测试评审完成
- [ ] 评审意见已整合
- [ ] PRD v2 已生成

**评审文件**：
- 技术评审：output/{project-id}/{iteration-id}/reviews/dev-review.md
- 测试评审：output/{project-id}/{iteration-id}/reviews/qa-review.md
- 整合报告：output/{project-id}/{iteration-id}/reviews/integration-report.md

**最终 PRD**：output/{project-id}/{iteration-id}/prd/PRD-{name}-v2.md

---

## Phase 4 结论（原型交付）

- [ ] HTML 原型已生成
- [ ] 用户确认

**原型文件**：
- 导航首页：output/{project-id}/{iteration-id}/prototype/index.html
- 页面列表：{页面文件名列表}
```

---

## 使用说明

1. Phase 0 开始时，主 Agent 创建 context.md，填充"基本信息"和"需求背景"
2. 每个 Phase 完成后，主 Agent 在 context.md 中追加对应 Phase 的结论
3. 调用 Subagent 时，在 prompt 中引用 context.md 让 Subagent 了解全局上下文
4. context.md 是追加式的，不删除之前的内容，保留完整的决策历史
