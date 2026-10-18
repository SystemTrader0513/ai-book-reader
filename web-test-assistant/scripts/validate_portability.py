#!/usr/bin/env python3
"""Validate a web-test-assistant package for Codex and GitHub Copilot."""

import argparse
import re
import sys
from collections import namedtuple
from pathlib import Path


ValidationError = namedtuple("ValidationError", "path code message")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")
REQUIRED_REFERENCE = Path("references/host-compatibility.md")


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    fields = {}
    for line in match.group(1).splitlines():
        field = FIELD_RE.match(line)
        if field:
            fields[field.group(1)] = field.group(2).strip().strip("\"'")
    return fields, text


def _relative_target(raw_target):
    target = raw_target.strip().strip("<>")
    if not target or target.startswith(EXTERNAL_PREFIXES):
        return None
    if " " in target:
        target = target.split(" ", 1)[0]
    return target.split("#", 1)[0]


def validate(skill_dir):
    skill_dir = Path(skill_dir).resolve()
    errors = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [ValidationError(str(skill_md), "missing_skill", "SKILL.md is required")]

    fields, _ = _frontmatter(skill_md)
    if fields.get("name") != skill_dir.name:
        errors.append(ValidationError(
            str(skill_md),
            "invalid_name",
            "Skill name must match its directory",
        ))
    if not fields.get("description"):
        errors.append(ValidationError(
            str(skill_md),
            "missing_description",
            "Skill description is required",
        ))

    compatibility = skill_dir / REQUIRED_REFERENCE
    if not compatibility.is_file():
        errors.append(ValidationError(
            str(compatibility),
            "missing_host_compatibility",
            "Host compatibility reference is required",
        ))

    for markdown in skill_dir.rglob("*.md"):
        text = markdown.read_text(encoding="utf-8")
        for raw_target in LINK_RE.findall(text):
            target = _relative_target(raw_target)
            if target is None:
                continue
            candidate = (markdown.parent / target).resolve()
            try:
                candidate.relative_to(skill_dir)
            except ValueError:
                errors.append(ValidationError(
                    str(markdown),
                    "nonportable_reference",
                    "Local Markdown references must stay inside the skill directory",
                ))
                continue
            if not candidate.exists():
                errors.append(ValidationError(
                    str(markdown),
                    "broken_reference",
                    "Referenced skill resource does not exist",
                ))
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", type=Path)
    args = parser.parse_args(argv)
    errors = validate(args.skill_dir)
    for error in errors:
        print(f"{error.code}: {error.path}: {error.message}", file=sys.stderr)
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
