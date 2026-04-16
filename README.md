# Fruugo OpenClaw Workflow Skill

![Version](https://img.shields.io/badge/version-0.2.0-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Target](https://img.shields.io/badge/target-OpenClaw-orange)

这是一个给 OpenClaw Xiaolongxia 复用的 Fruugo 工作流技能仓库。

它解决的不是单条文案生成，而是整条 Fruugo 批处理链路：

- 从 tracker claim 未消费链接
- 抓热门商品链接
- 抓商品详情到 CSV
- 通过远端 `/api/store` 改图片链接
- 生成 Fruugo 上传模板
- 生成库存表

## 适合谁用

- 已经有 Fruugo 采集仓库的团队
- 用 OpenClaw + Feishu 跑小龙虾的团队
- 想把 Fruugo SOP 固化给其他机器/其他 agent 复用的人

## 仓库结构

```text
fruugo-skills/
├── SKILL.md
├── skill.json
├── requirements.txt
├── package.json
├── references/
│   ├── fruugo-workflow/
│   │   ├── SKILL.md
│   │   └── scripts/
│   └── openclaw-deploy/
│       ├── SKILL.md
│       └── scripts/
│           └── install_openclaw_fruugo_prompt.py
├── README.md
└── LICENSE
```

## OpenClaw 安装

在目标机器执行：

```bash
python3 references/openclaw-deploy/scripts/install_openclaw_fruugo_prompt.py \
  --repo-root /abs/path/to/fruugo \
  --db /abs/path/to/fruugo/0326/fruugo_product_links.sqlite3 \
  --template /abs/path/to/fruugo/0313/Prod_1772601378_NEW_FRU_GBR_01_1772601383ZJW031204.xlsx \
  --public-base https://img.urlconverterecommerce.online \
  --store-api https://img.urlconverterecommerce.online/api/store \
  --openclaw-workspace ~/.openclaw/workspaces/ecom
```

它会把 Fruugo 工作流注入：

- `~/.openclaw/workspaces/ecom/AGENTS.md`

## 运行依赖

Python:

```bash
pip install -r requirements.txt
```

Node:

```bash
npm install
```

## 推荐给 Xiaolongxia 的触发语句

```text
执行这个 skill 仓库里的 references/fruugo-workflow/scripts/run_fruugo_workflow.py，跑下一批 50 个 Fruugo 商品，图片必须走远端 /api/store，最后只返回商品表、上传模板和库存表路径。
```

## 注意

不要指望在 Feishu 里只发 `$fruugo-dms-workflow`。  
对 OpenClaw `ecom` agent，明确工作流命令比裸 skill token 更稳定。
