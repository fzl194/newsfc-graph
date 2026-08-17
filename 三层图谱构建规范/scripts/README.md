# scripts/ — 构建管线

> 原始产品文档 → 三层图谱资产的脚本链。本规范包的执行工具。

---

## 核心认知

本规范的**输入起点是原始产品文档**（华为 HDX/HWICS 归档），不是已导出的 md。
因此脚本链从"产品文档导出"开始，**不是**从中间态（output/ 或 jsonl）开始。

---

## 脚本分布

构建脚本**按层就近放置**，不在顶层集中：

| 位置 | 内容 |
|---|---|
| `scripts/`（顶层，本目录） | 仅**阶段 0**：原始产品文档导出器（所有层共用入口） |
| `command/scripts/` | 命令层构建（命令 + 配置对象，Spec 体裁） |
| `feature/scripts/` | 特性层构建（Feature + License，Spec 体裁） |
| `task/scripts/` | task 层辅助脚本（如 `collect_command_examples.py`；Procedure 体裁，主体靠 Agent 写 md） |
| `business/` | 业务层无 `scripts/`（Procedure 体裁，靠 Agent 读文档写 md） |

> 每层构建脚本随该层能力包独立维护，详见各层 `SKILL.md`。

---

## 阶段 0：产品文档导出（已纳入）

| 项 | 值 |
|---|---|
| 脚本 | `product_doc_md_exporter_optimized.py`（1328 行） |
| 输入 | 华为 HDX/HWICS 归档（`.hwics` / `.hdx`，HTML 文档打包格式） |
| 输出 | Markdown 文件树 + `html_to_md_mapping.json`（HTML→MD 路径映射） |
| 依赖 | `chardet`、`beautifulsoup4` |
| 入口函数 | `main(hdx_file)` 归档→md；`main_from_extracted(extracted_dir, output_dir)` 已解压→md；`main2(input_dir, output_dir)` 纯 HTML 批量→md |
| 纳入方式 | 复制（根目录原文件保留，过渡期双存，待规范包验证为唯一源后删根目录副本） |

> 脚本的完整 CLI 契约、与阶段 1（命令图构建）的衔接细节，**随命令层共创时补完**。
