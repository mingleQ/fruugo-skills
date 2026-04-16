---
name: fruugo-openclaw-deploy
description: 把 Fruugo 工作流部署到 OpenClaw `ecom` agent。适用于已经有 Fruugo 数据仓库的机器，通过脚本把标准 Fruugo workflow 段落注入到 `~/.openclaw/workspaces/ecom/AGENTS.md`，让 Xiaolongxia 能稳定执行这个 skill 仓库中的 `run_fruugo_workflow.py`。
---

# OpenClaw Deploy

这个子能力只负责部署，不负责运行 Fruugo 批次。

## 目标

把标准 Fruugo workflow 注入 OpenClaw `ecom` agent 的 `AGENTS.md`，让 Feishu/Xiaolongxia 触发时更稳定，并且直接调用这个 skill 仓库内置的脚本。

## 安装命令

```bash
python3 references/openclaw-deploy/scripts/install_openclaw_fruugo_prompt.py \
  --repo-root /abs/path/to/fruugo \
  --db /abs/path/to/fruugo/0326/fruugo_product_links.sqlite3 \
  --template /abs/path/to/fruugo/0313/Prod_1772601378_NEW_FRU_GBR_01_1772601383ZJW031204.xlsx \
  --public-base https://img.urlconverterecommerce.online \
  --store-api https://img.urlconverterecommerce.online/api/store \
  --openclaw-workspace ~/.openclaw/workspaces/ecom
```

## 写入内容

- 更新 `~/.openclaw/workspaces/ecom/AGENTS.md`
- 使用标记块覆盖旧的 Fruugo workflow，避免重复追加

## 部署后推荐触发语句

```text
在仓库根目录执行 run_fruugo_workflow.py，跑下一批 50 个 Fruugo 商品，图片必须走远端 /api/store，最后只返回商品表、上传模板和库存表路径。
```
