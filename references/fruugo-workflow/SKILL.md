---
name: fruugo-workflow
description: 执行 Fruugo 铺货主流程：新机器首次运行时自动从仓库自带类目表抓取热门商品链接并初始化 SQLite tracker，随后 claim 未消费商品，抓详情形成商品表，调用远端 /api/store 改写图片链接，然后生成 Fruugo 上传模板和库存表。适用于 OpenClaw 电商 agent、小龙虾、批量 Fruugo 上新流程。
---

# Fruugo Workflow

## 目标产物

- 商品表 CSV
- Fruugo 上传模板 XLSX
- 库存表 XLSX

## 推荐执行顺序

1. 新机器首次运行：自动从仓库 `assets/categories/` 抓取类目链接并初始化 tracker
2. `consume_fruugo_product_links.py`
3. `rewrite_fruugo_product_csv_images.py`
4. `generate_fruugo_xlsx.py`

如果用户要“一句话跑完整批”，优先使用：

```bash
python3 references/fruugo-workflow/scripts/run_fruugo_workflow.py \
  --count 50 \
  --operator SHOU \
  --shop 07 \
  --date-code 0416 \
  --public-base https://img.urlconverterecommerce.online \
  --store-api https://img.urlconverterecommerce.online/api/store
```

## 规则

- 商品详情必须来自 tracker 中未消费链接。
- 图片改链必须优先调用远端 `/api/store`。
- 不要把 Fruugo 原图链接留在最终 CSV 或 XLSX。
- 输出时只报告最终商品表、上传模板、库存表路径。
- 新机器默认使用仓库自带模板和类目 CSV。

## 脚本位置

所有核心脚本都在 `references/fruugo-workflow/scripts/`。
