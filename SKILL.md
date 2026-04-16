---
name: fruugo-openclaw-workflow
description: 面向 OpenClaw 小龙虾/电商 agent 的 Fruugo 铺货技能仓库。覆盖热门商品抓取、tracker 消费、商品表生成、远端 /api/store 改图、Fruugo 上传模板生成、库存表生成，以及把这套 workflow 注入 OpenClaw ecom agent 的部署方法。用户提到 Fruugo 铺货、商品表、库存表、DMS 模板、OpenClaw、小龙虾时使用。
version: 0.2.0
alwaysApply: false
keywords:
  - fruugo
  - openclaw
  - xiaolongxia
  - 小龙虾
  - ecom
  - dms
  - inventory
  - tracker
  - urlconverter
  - 铺货
---

# Fruugo OpenClaw Workflow Skill

这是一个给 OpenClaw agent 复用的 Fruugo 铺货技能仓库。

核心目标不是“分析”，而是稳定产出：

- 商品表 CSV
- Fruugo 上传模板 XLSX
- 库存表 XLSX

## 核心能力

1. 热门商品抓取
2. tracker 去重与消费控制
3. 商品详情采集
4. 远端 `/api/store` 图片改链
5. Fruugo 上传模板生成
6. 库存表生成
7. OpenClaw ecom agent 部署

## 子技能

- [references/fruugo-workflow/SKILL.md](references/fruugo-workflow/SKILL.md)
  具体的 Fruugo 采集与出表流程
- [references/openclaw-deploy/SKILL.md](references/openclaw-deploy/SKILL.md)
  把 Fruugo workflow 注入 OpenClaw `ecom` agent 的方法

## 关键规则

- 不要绕过 tracker。
- 图片不能保留 Fruugo 原图链接。
- 最终图片必须是 `https://.../stored/...`
- Fruugo 上传文件名必须以 `Prod_1772601378_NEW_FRU_GBR_01_1772601383` 开头。
- 在 Feishu/OpenClaw 里，优先使用明确命令，不要只发 `$fruugo-dms-workflow`。
