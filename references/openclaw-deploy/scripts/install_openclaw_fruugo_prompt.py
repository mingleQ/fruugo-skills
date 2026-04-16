#!/usr/bin/env python3
import argparse
from pathlib import Path


SECTION_START = "<!-- FRUUGO_WORKFLOW_START -->"
SECTION_END = "<!-- FRUUGO_WORKFLOW_END -->"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the Fruugo workflow prompt block into an OpenClaw ecom workspace."
    )
    parser.add_argument("--repo-root", required=True, help="Absolute Fruugo repo root on the target machine.")
    parser.add_argument("--db", required=True, help="Tracker SQLite DB path.")
    parser.add_argument("--template", required=True, help="Fruugo workbook template path.")
    parser.add_argument("--public-base", required=True, help="Public HTTPS base for stored images.")
    parser.add_argument("--store-api", required=True, help="Remote urlconverter /api/store endpoint.")
    parser.add_argument(
        "--openclaw-workspace",
        default=str(Path.home() / ".openclaw" / "workspaces" / "ecom"),
        help="OpenClaw ecom workspace directory. Defaults to ~/.openclaw/workspaces/ecom",
    )
    return parser.parse_args()


def replace_managed_section(original: str, new_section: str) -> str:
    if SECTION_START in original and SECTION_END in original:
        start = original.index(SECTION_START)
        end = original.index(SECTION_END) + len(SECTION_END)
        prefix = original[:start].rstrip()
        suffix = original[end:].lstrip()
        parts = [part for part in [prefix, new_section.strip(), suffix] if part]
        return "\n\n".join(parts) + "\n"

    base = original.rstrip()
    if base:
        return base + "\n\n" + new_section.strip() + "\n"
    return new_section.strip() + "\n"


def render_section(args: argparse.Namespace) -> str:
    skill_root = Path(__file__).resolve().parents[3]
    workflow_script = skill_root / "references" / "fruugo-workflow" / "scripts" / "run_fruugo_workflow.py"
    return f"""{SECTION_START}
## Fruugo 自动化工作流

- 技能仓库根目录：`{skill_root}`
- Fruugo 数据仓库根目录：`{Path(args.repo_root).resolve()}`
- Tracker 数据库：`{Path(args.db).resolve()}`
- 模板文件：`{Path(args.template).resolve()}`
- 图片公网前缀：`{args.public_base.rstrip('/')}`
- 图片存储接口：`{args.store_api.rstrip('/')}`

处理 Fruugo 批量任务时，优先执行这条一键命令：

```bash
python3 {workflow_script} \\
  --db {Path(args.db).resolve()} \\
  --count 50 \\
  --output-dir {Path(args.repo_root).resolve()}/0416/workflow_batch_50 \\
  --template {Path(args.template).resolve()} \\
  --operator SHOU \\
  --shop 07 \\
  --date-code 0416 \\
  --public-base {args.public_base.rstrip('/')} \\
  --store-api {args.store_api.rstrip('/')}
```

必须遵守：

- 不要绕过 tracker。
- 图片必须通过远端 `/api/store` 改成自有 HTTPS 链接。
- 最终图片链接必须是 `{args.public_base.rstrip('/')}/stored/...`
- 交付时只返回：
  - 商品表路径
  - 上传模板路径
  - 库存表路径

如果用户在飞书里要求“小龙虾跑下一批 Fruugo”，优先把请求解释为执行这个 skill 仓库里的 `run_fruugo_workflow.py`，而不是把 `$fruugo-dms-workflow` 当作 shell 命令。
{SECTION_END}"""


def main() -> int:
    args = parse_args()
    workspace_root = Path(args.openclaw_workspace).expanduser()
    workspace_root.mkdir(parents=True, exist_ok=True)
    agents_path = workspace_root / "AGENTS.md"
    existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else "# AGENTS.md\n"
    updated = replace_managed_section(existing, render_section(args))
    agents_path.write_text(updated, encoding="utf-8")
    print(f"Updated OpenClaw AGENTS: {agents_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
