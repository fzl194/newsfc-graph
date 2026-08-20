# pipeline 包：产品文档导入

「上传产品文档」的后端能力：`.hwics` → 解压导出 → 自动构建四类图谱资产 + 原始 md 留存。

## 文件构成与来源（同步纪律）

| 文件 | 来源（权威：三层图谱构建规范/） | 版本 |
|---|---|---|
| `product_doc_md_exporter_optimized.py` | `scripts/product_doc_md_exporter_optimized.py` | **v0.24.0**（read_text_auto 编码探测重写：BOM/UTF-8 自校验/meta 声明优先，chardet 兜底——修整文件乱码） |
| `command/_common.py` `build_commands.py` `build_configobjects.py` | `command/scripts/` | **v0.20.0**（参见边全文锚定） |
| `feature/_common.py` `build_features.py` `build_licenses.py` | `feature/scripts/` | **v0.22.0**（依赖特性全文锚定+使用命令边+License校验+图片） |
| `test_build_*_edges.py` | 同目录脚本配套回归测试（26 用例） | 随脚本 |

**拷贝为字节一致**（不加平台侧改动），规范升级后人工同步 = 直接覆盖拷贝。

### 同步后护栏（必跑）

```bash
cd backend
python -m unittest discover -s app/pipeline/command -p "test_*.py"
python -m unittest discover -s app/pipeline/feature -p "test_*.py"
```

### 脚本为何保持原样

- 构建脚本经 subprocess 以独立进程运行（`import _common` 平面导入依赖脚本目录作 sys.path[0]，包内相对导入反而会破坏）；
- 存储位置由 `--storage` 参数注入（平台传 `GAP_DATA_DIR/assets`），产物路径 `{Type}/{nf}/{version}/` 与平台资产布局天然一致；
- 与规范侧完全一致 = 可 diff、可回归、可回溯（规范 CHANGELOG 即平台构建行为变更日志）。

## 编排（runner.py，顺序 = 规范《图谱边定义.md》§0）

```
.hwics → 临时目录解压(html 中间态) → exporter 转 md → output/{nf}_{version}/ 留存※
  → 定位 mml / feature / license 目录（rglob，UDG/UNC 层级差异兜底）
  → build_commands → build_configobjects → build_licenses → build_features
  → svc.rebuild()（图谱索引）
```

※ `output/{nf}_{version}/` 在 `GAP_DATA_DIR/output/` 下，**不进数据库、不进图谱**，
前端「原始产品文档」tab 只读浏览；html 中间态随临时目录删除（用户要求：md 留、html 删）。

构建顺序注意：**commands 必须先于 features**（特性层「使用命令」边校验依赖已建 Command 资产）；
licenses 先于 features（「所需License」校验依赖已建 License）。

## 重复上传（用户决策 2026-08-18）

同 `nf+version` 已有任一类资产 → 默认拒（409 + 计数）；勾选「覆盖重建」→ 先清理
`assets/{Command,ConfigObject,Feature,License}/{nf}/{version}/` 再全量重建
（Task/Business 层与产品文档无关，不参与覆盖清理）。
