#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工期预估 Excel 生成器（Python / openpyxl 版）

替代原 `generate-estimate.js`（依赖本机不存在的 `xlsx` npm 包）。
对外契约与原脚本保持一致：命令行参数、数据 JSON 结构、工作表/列/表头结构、列宽。

用法:
    python3 generate_estimate.py --name "迭代名称" --output "输出路径.xlsx" --data "数据JSON路径"
    python3 generate_estimate.py --print-template          # 打印数据 JSON 模板

数据 JSON 结构见 DEFAULT_DATA / `--print-template` 输出。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

# 与原 generate-estimate.js 一致：默认输出到技能根目录下的「工期预估.xlsx」
SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = SKILL_DIR / "工期预估.xlsx"

# ============================================================
# DATA_TEMPLATE —— 与原 JS 内置示例数据逐项一致
# ============================================================
DEFAULT_DATA = {
    "projectInfo": {
        "name": "项目工期预估",
        "scope": "用户端（Web + H5）",
        "featureCount": "待填写",
        "excluded": "无改动",
    },
    "roles": [
        {"name": "产品经理", "items": [
            {"task": "评审整合", "days": 1},
            {"task": "交互设计确认 + 原型验收", "days": 0.5},
            {"task": "验收标准 + 验收用例", "days": 1},
            {"task": "UAT 验收 + 问题跟踪", "days": 0.5},
        ]},
        {"name": "UED设计师", "items": [
            {"task": "页面设计（Web+H5）", "days": 2},
            {"task": "标注交付 + 设计走查", "days": 0.5},
        ]},
        {"name": "后端开发", "items": [
            {"task": "DB变更", "complexity": "中", "days": 1},
            {"task": "API开发", "complexity": "中", "days": 3},
            {"task": "联调 + 自测", "complexity": "-", "days": 1.5},
        ]},
        {"name": "前端-Web", "items": [
            {"task": "页面开发", "complexity": "高", "days": 4},
            {"task": "联调 + 自测", "complexity": "-", "days": 1},
        ]},
        {"name": "前端-H5", "items": [
            {"task": "页面开发（移动端适配）", "complexity": "高", "days": 4.5},
            {"task": "联调 + 自测", "complexity": "-", "days": 1.5},
        ]},
        {"name": "QA测试", "items": [
            {"task": "测试用例编写", "days": 1.5},
            {"task": "功能测试", "days": 2},
            {"task": "跨端测试", "days": 0.5},
            {"task": "回归测试", "days": 1},
            {"task": "Bug验证 + UAT配合", "days": 1},
        ]},
    ],
    "risks": [
        {"name": "示例风险", "level": "高", "impact": "示例影响", "mitigation": "示例应对"},
    ],
    "cycleEstimate": {
        "parallel": "约3~3.5周",
        "compressed": "若Web/H5同一组前端，可压缩至约2.5~3周",
    },
}

TITLE_FONT = Font(bold=True, size=14)
SECTION_FONT = Font(bold=True)

_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")


# ============================================================
# 工具函数
# ============================================================
def to_days(value, where: str) -> float:
    """把 days 字段转成数字（原 JS 用 `sum + i.days`，字符串会变成拼接，这里修掉）。"""
    if isinstance(value, bool):
        raise ValueError(f"{where}: days 不能是布尔值")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            pass
    raise ValueError(f"{where}: days 必须是数字，实际为 {value!r}")


def num(value: float):
    """整数写成 int（4.0 -> 4），与原 JS 写出效果一致。"""
    return int(value) if float(value).is_integer() else round(float(value), 4)


def safe_sheet_name(name: str, used: set) -> str:
    """清理 Sheet 名：去掉 Excel 非法字符、截断到 31 字符、去重（原 JS 未处理会直接报错）。"""
    title = _INVALID_SHEET_CHARS.sub("-", str(name)).strip() or "Sheet"
    title = title[:31]
    base, i = title, 2
    while title in used:
        suffix = f"_{i}"
        title = base[: 31 - len(suffix)] + suffix
        i += 1
    used.add(title)
    return title


def write_rows(ws, rows):
    """按行写入，空行同样占位（对齐原 JS `aoa_to_sheet` 的行为）。"""
    r = 1
    for row in rows:
        if row:
            for c, value in enumerate(row, start=1):
                ws.cell(row=r, column=c, value=value)
        r += 1


def load_data(data_path: str | None, project_name: str) -> dict:
    if data_path is None:
        data = json.loads(json.dumps(DEFAULT_DATA))  # 深拷贝
        data["projectInfo"]["name"] = project_name
        return data

    p = Path(data_path)
    if not p.is_file():
        # 原 JS 在校验失败时静默回落到内置示例数据；这里改为显式报错，避免生成假数据。
        sys.exit(f"错误：--data 指定的文件不存在或不是文件：{data_path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"错误：--data 文件不是合法 JSON：{data_path}\n{exc}")
    if not isinstance(data, dict):
        sys.exit(f"错误：--data 顶层必须是 JSON 对象：{data_path}")
    # 原 JS 在 --data 缺 projectInfo.name 时会崩溃；这里回落到 --name。
    data.setdefault("projectInfo", {})
    data["projectInfo"].setdefault("name", project_name)
    return data


# ============================================================
# Excel 构建
# ============================================================
def build_workbook(data: dict) -> Workbook:
    project_info = data.get("projectInfo") or {}
    roles = data.get("roles") or []
    cycle = data.get("cycleEstimate") or {}

    wb = Workbook()
    wb.remove(wb.active)

    # ---------- Sheet 1: 总览 ----------
    role_totals = [(r, sum(to_days(i.get("days"), f"{r.get('name')}/{i.get('task')}")
                           for i in r.get("items") or []))
                   for r in roles]
    total_days = sum(t for _, t in role_totals)

    overview_rows = [
        [f"{project_info.get('name', '')} · 全角色工期预估"],
        [],
        ["项目信息"],
        ["迭代名称", project_info.get("name", "")],
        ["涉及端", project_info.get("scope", "")],
        ["功能点数", project_info.get("featureCount", "")],
        ["运营端/渠道端", project_info.get("excluded", "")],
        [],
        ["角色总览", "人天", "占比"],
    ]
    for role, days in role_totals:
        pct = f"{(days / total_days * 100):.1f}%" if total_days else "0.0%"
        overview_rows.append([role.get("name", ""), num(days), pct])
    overview_rows.append(["合计", num(total_days), "100%"])
    overview_rows.append([])
    overview_rows.append(["自然日周期（并行）", cycle.get("parallel", "")])
    if cycle.get("compressed"):
        overview_rows.append(["压缩周期", cycle["compressed"]])

    ws1 = wb.create_sheet("总览")
    write_rows(ws1, overview_rows)
    ws1.column_dimensions["A"].width = 42
    ws1.column_dimensions["B"].width = 12
    ws1.column_dimensions["C"].width = 10
    ws1["A1"].font = TITLE_FONT
    ws1["A3"].font = SECTION_FONT
    ws1["A9"].font = SECTION_FONT
    ws1["B9"].font = SECTION_FONT
    ws1["C9"].font = SECTION_FONT
    total_row = 10 + len(role_totals)
    for col in ("A", "B", "C"):
        ws1[f"{col}{total_row}"].font = SECTION_FONT

    # ---------- 各角色 Sheet ----------
    used_names = {"总览"}
    for role in roles:
        items = role.get("items") or []
        has_complexity = any(i.get("complexity") for i in items)
        headers = ["工作项", "复杂度", "人天"] if has_complexity else ["工作项", "人天"]
        rows = [headers]
        subtotal = 0.0
        for item in items:
            days = to_days(item.get("days"), f"{role.get('name')}/{item.get('task')}")
            subtotal += days
            if has_complexity:
                rows.append([item.get("task", ""), item.get("complexity") or "-", num(days)])
            else:
                rows.append([item.get("task", ""), num(days)])
        rows.append(["小计", "", num(subtotal)] if has_complexity
                    else ["小计", num(subtotal)])

        ws = wb.create_sheet(safe_sheet_name(role.get("name", ""), used_names))
        write_rows(ws, rows)
        if has_complexity:
            ws.column_dimensions["A"].width = 65
            ws.column_dimensions["B"].width = 10
            ws.column_dimensions["C"].width = 10
        else:
            ws.column_dimensions["A"].width = 55
            ws.column_dimensions["B"].width = 10
        for cell in ws[1]:
            cell.font = SECTION_FONT
        for cell in ws[ws.max_row]:
            cell.font = SECTION_FONT

    # ---------- 风险项 Sheet ----------
    risks = data.get("risks") or []
    if risks:
        risk_rows = [["风险项", "风险等级", "影响", "应对措施"]]
        for r in risks:
            risk_rows.append([r.get("name", ""), r.get("level", ""),
                              r.get("impact", ""), r.get("mitigation", "")])
        ws = wb.create_sheet("风险项")
        write_rows(ws, risk_rows)
        ws.column_dimensions["A"].width = 30
        ws.column_dimensions["B"].width = 10
        ws.column_dimensions["C"].width = 30
        ws.column_dimensions["D"].width = 40
        for cell in ws[1]:
            cell.font = SECTION_FONT

    return wb


# ============================================================
# 入口
# ============================================================
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="工期预估 Excel 生成器（按角色拆解工期，输出 .xlsx）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--name", default="项目工期预估",
                        help="迭代/项目名称（--data 未提供 projectInfo.name 时作为兜底）")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help=f"输出 .xlsx 路径，默认：{DEFAULT_OUTPUT}")
    parser.add_argument("--data", default=None,
                        help="数据 JSON 路径；缺省时使用内置示例数据")
    parser.add_argument("--print-template", action="store_true",
                        help="打印数据 JSON 模板（DATA_TEMPLATE）并退出，不生成 Excel")
    args = parser.parse_args(argv)

    if args.print_template:
        print(json.dumps(DEFAULT_DATA, ensure_ascii=False, indent=2))
        return 0

    data = load_data(args.data, args.name)
    wb = build_workbook(data)

    output_path = Path(args.output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"Excel generated: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
