#!/usr/bin/env python3
"""Render a web-test-assistant result summary as Markdown."""

import argparse
import json
import re
import sys
from pathlib import Path


REDACTIONS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{6,}", re.I), "Bearer [REDACTED]"),
    (re.compile(r"((?:password|passwd|secret|token|authorization)\s*[:=]\s*)[^\s,;]+", re.I), r"\1[REDACTED]"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[REDACTED]"),
]


def _safe(value):
    text = str(value if value is not None else "")
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text.replace("|", "\\|").replace("\n", " ")


def _percent(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def render(summary):
    run = summary.get("run", {})
    counts = summary.get("counts", {})
    rates = summary.get("rates", {})
    lines = [
        "# 网页测试结果报告",
        "",
        "## 1. 执行摘要",
        "",
        f'- Run ID: `{_safe(run.get("runId"))}`',
        f'- 模式: `{_safe(run.get("mode"))}`',
        f'- 总测试数: {counts.get("total", 0)}',
        f'- 稳定通过率: {_percent(rates.get("stablePassRate"))}',
        f'- 需求覆盖率: {_percent(rates.get("requirementCoverageRate"))}',
        f'- 发布建议: **{_safe(summary.get("releaseRecommendation", "review"))}**',
        "",
        "## 2. 测试环境",
        "",
        f'- 环境: `{_safe(run.get("environment"))}`',
        f'- Base URL: `{_safe(run.get("baseUrl"))}`',
        "",
        "## 3. 结果统计",
        "",
        "| 结果 | 数量 |",
        "|---|---:|",
    ]
    for status in ("passed", "failed", "flaky", "skipped", "blocked", "infrastructure_error"):
        lines.append(f"| `{status}` | {counts.get(status, 0)} |")

    lines.extend(["", "## 4. 需求覆盖矩阵", "", "| 需求 ID | 状态 | 测试 |", "|---|---|---|"])
    for item in summary.get("requirements", []):
        tests = ", ".join(_safe(title) for title in item.get("tests", [])) or "—"
        lines.append(f'| `{_safe(item.get("requirementId"))}` | `{_safe(item.get("status"))}` | {tests} |')

    lines.extend(["", "## 5. 失败与阻塞详情", ""])
    failures = summary.get("failures", [])
    if not failures:
        lines.append("无失败或基础设施错误。")
    for failure in failures:
        lines.extend([
            f'### {_safe(failure.get("requirementId") or "未映射")} — {_safe(failure.get("title"))}',
            "",
            f'- 分类: `{_safe(failure.get("classification"))}`',
            f'- 信息: {_safe(failure.get("message")) or "无"}',
            "- 证据:",
        ])
        evidence = failure.get("evidence", [])
        lines.extend([f'  - [{_safe(Path(path).name)}]({_safe(path)})' for path in evidence] or ["  - 无"])

    lines.extend(["", "## 6. 证据与未映射测试", ""])
    unmapped = summary.get("unmappedTests", [])
    lines.extend(
        [f'- `{_safe(item.get("file"))}` — {_safe(item.get("title"))}' for item in unmapped]
        or ["所有测试均已映射到需求。"]
    )

    lines.extend(["", "## 7. 自动修复记录", ""])
    history = summary.get("healHistory", [])
    if history:
        for entry in history:
            lines.append(
                f'- `{_safe(entry.get("testId"))}` 第 {entry.get("round", "?")} 轮：'
                f'`{_safe(entry.get("changeType"))}` → `{_safe(entry.get("result"))}`'
            )
    else:
        lines.append("本次运行没有自动修复记录。")

    lines.extend(["", "## 8. 未执行范围", ""])
    unexecuted = summary.get("unexecutedRequirements", [])
    lines.extend([f'- `{_safe(item)}`' for item in unexecuted] or ["无。"])

    lines.extend(["", "## 9. 残余风险与发布建议", ""])
    risks = summary.get("residualRisks", [])
    lines.extend([f'- {_safe(item)}' for item in risks] or ["未发现已知残余风险。"])
    lines.extend(["", f'最终建议：**{_safe(summary.get("releaseRecommendation", "review"))}**', ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        summary = json.loads(args.summary.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read summary: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
