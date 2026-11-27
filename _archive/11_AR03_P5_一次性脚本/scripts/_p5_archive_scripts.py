#!/usr/bin/env python3
"""AR03-P5 —— scripts/ 分级归档的 **清单驱动** 执行器。

设计要点
--------
1. **只归档、不删除**：全部通过 ``shutil.move`` 移动到
   ``_archive/11_AR03_P5_一次性脚本/scripts/``。
2. **清单驱动**：归档列表显式写在 ``ARCHIVE_LIST`` 里，每个条目带
   **归档理由** 与 **核实结论** —— 便于复核，不依赖命名通配符。
3. **可重复执行**：已归档的文件自动跳过（幂等）。
4. **拒绝危险路径**：任何试图移动 ``src/notes/**``、
   ``data/task_publisher.db*``、``config/config.json`` 的条目都会
   **fail closed**。

用法
----
    python scripts/_p5_archive_scripts.py            # 执行归档
    python scripts/_p5_archive_scripts.py --dry-run  # 只打印计划
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ARCHIVE = ROOT / "_archive" / "11_AR03_P5_一次性脚本" / "scripts"

#: 红线路径（相对项目根的段）—— 任何命中一律 fail closed。
REDLINE_PREFIXES = (("src", "notes"),)
REDLINE_FILES = (
    ("data", "task_publisher.db"),
    ("data", "task_publisher.db-wal"),
    ("data", "task_publisher.db-shm"),
    ("config", "config.json"),
)


# ---------------------------------------------------------------------------
# 归档清单
#
# 分类：
#   A. 一次性提取 / 文档处理工具（输入是一次性素材，产出已入库）
#   B. 一次性探查 / 调试脚本（写生产 DB 或打生产端口）
#   C. 一次性 HTTP 冒烟测试（打生产端口 + 写生产 DB）
#   D. 一次性验证脚本（已被正式测试套件取代）
#   E. Phase-1 时期的 shell / ps1 包装器（早已被 tests/characterize 取代）
#   F. 迁移期的一次性迁移器（迁移已完成，Schema 权威已上移到 server/schema/）
#
# 每条: (文件名, 分类, 归档理由, 核实结论)
# ---------------------------------------------------------------------------
ARCHIVE_LIST: tuple[tuple[str, str, str, str], ...] = (
    # ---- A. 一次性提取 / 文档处理 ------------------------------------------
    ("extract_all_exams.py", "A-一次性提取",
     "考试卷/素材提取器：输入是一次性素材，产物早已入库",
     "零引用（grep 全仓除自身外无命中）；非 pytest 收集目标"),
    ("extract_ch5.py", "A-一次性提取",
     "第 5 章提取器：一次性素材处理",
     "零引用；非 pytest 收集目标"),
    ("extract_linalg.py", "A-一次性提取",
     "线性代数素材提取器：一次性素材处理",
     "零引用；非 pytest 收集目标"),
    ("extract_ppt_all.py", "A-一次性提取",
     "PPT 批量提取器：一次性素材处理",
     "唯一引用是 ai_workspace/01_requests 的历史请求文本，非代码引用"),
    ("read_doc_files.py", "A-一次性提取",
     "文档读取器：一次性素材处理",
     "零引用；非 pytest 收集目标"),
    ("read_docx_v2.py", "A-一次性提取",
     "docx 读取器 v2：一次性素材处理",
     "零引用；非 pytest 收集目标"),
    ("filter_extracted_images.py", "A-一次性提取",
     "提取图片过滤器：一次性素材处理",
     "仅 README.md 结构图提及（描述性，非引用）"),
    ("split_english_course.py", "A-一次性提取",
     "英语课程拆分器：一次性素材处理",
     "仅 README.md 结构图提及（描述性，非引用）"),
    ("download_vendor.py", "A-一次性提取",
     "vendor 包下载器：一次性环境准备",
     "仅历史文档提及"),
    ("download_python.bat", "A-一次性提取",
     "Python 下载器：一次性环境准备",
     "opencode.json 与 README 提及；非运行期依赖"),

    # ---- B. 一次性探查 / 调试（写生产 DB）---------------------------------
    ("_inspect_db.py", "B-一次性探查",
     "生产 DB 探查器：直接 sqlite3.connect('data/task_publisher.db')",
     "零运行时引用；直连生产 DB（已属红线面），长期留在 scripts/ 有误用风险"),
    ("_inspect_db2.py", "B-一次性探查",
     "生产 DB 深度探查器：直连生产 DB",
     "零运行时引用；直连生产 DB（已属红线面）"),
    ("_read_exact.py", "B-一次性探查",
     "生产 DB 精确读取器：直连生产 DB",
     "零运行时引用；直连生产 DB（已属红线面）"),
    ("_phase1_baseline_tables.py", "B-一次性探查",
     "生产 DB 表基线快照器：直连生产 DB",
     "零运行时引用；直连生产 DB（已属红线面）"),
    ("debug_tags.py", "B-一次性探查",
     "标签创建问题调试器：直连生产 DB 并写表",
     "零运行时引用；直连生产 DB **并写表**（红线面）"),
    ("debug_tags2.py", "B-一次性探查",
     "标签 lastrowid 调试器：直连生产 DB 并写表",
     "零运行时引用；直连生产 DB **并写表**（红线面）"),
    ("_probe_task_get_500.py", "B-一次性探查",
     "任务 GET 500 问题的一次性复现探针（P2 期间用于定位）",
     "零运行时引用；该 500 已在 P2 修复，探针使命结束"),
    ("debug_5_1_probe.js", "B-一次性探查",
     "5.1 版本浏览器探针：硬编码生产端口 127.0.0.1:5000",
     "零运行时引用；硬编码生产端口，误跑会打活实例"),
    ("debug_5_1_3000ms.js", "B-一次性探查",
     "5.1 版本 3000ms 时序探针：硬编码生产端口 127.0.0.1:5000",
     "零运行时引用；硬编码生产端口，误跑会打活实例"),
    ("debug_5_2_replay.js", "B-一次性探查",
     "5.2 版本回放探针：硬编码生产端口 127.0.0.1:5000",
     "零运行时引用；硬编码生产端口，误跑会打活实例"),

    # ---- C. 一次性 HTTP 冒烟（打生产端口 + 写生产 DB）----------------------
    ("test_api_endpoints.py", "C-一次性HTTP冒烟",
     "HTTP 端点冒烟脚本：硬编码 127.0.0.1:5000",
     "**pytest 可收集**（pytest scripts → 1 test collected）；但被正式 "
     "tests/e2e-manual.js 与 tests/characterize 取代"),
    ("test_flask_tags.py", "C-一次性HTTP冒烟",
     "Flask 标签冒烟脚本：硬编码 127.0.0.1:5000",
     "零运行时引用；已被正式测试取代"),
    ("test_flask_tags2.py", "C-一次性HTTP冒烟",
     "Flask 标签冒烟脚本 v2：硬编码 127.0.0.1:5000",
     "零运行时引用；已被正式测试取代"),
    ("test_http_detailed.py", "C-一次性HTTP冒烟",
     "HTTP 详细响应冒烟脚本：硬编码 127.0.0.1:5000",
     "零运行时引用；已被正式测试取代"),
    ("test_health_and_tags.py", "C-一次性HTTP冒烟",
     "健康检查 + 标签冒烟脚本：硬编码 127.0.0.1:5000",
     "零运行时引用；已被 tests/characterize/test_health_contract.py 取代"),
    ("test_tags.py", "C-一次性HTTP冒烟",
     "标签创建冒烟脚本：硬编码 127.0.0.1:5000",
     "零运行时引用；已被正式测试取代"),
    ("test_simple.py", "C-一次性HTTP冒烟",
     "最简 HTTP 冒烟脚本：硬编码 127.0.0.1:5000",
     "零运行时引用；已被正式测试取代"),
    ("test_regex.py", "C-一次性HTTP冒烟",
     "正则表达式一次性试验脚本",
     "零运行时引用；与标签/接口无关的临时试验"),

    # ---- D. 一次性验证（已被正式套件取代）---------------------------------
    ("full_verification.py", "D-一次性验证",
     "全量 HTTP 验证脚本：硬编码 127.0.0.1:5000",
     "零运行时引用；已被 tests/e2e-manual.js（36/36）与 "
     "tests/characterize 取代"),
    ("verify_fixes.py", "D-一次性验证",
     "修复验证脚本：硬编码 127.0.0.1:5000",
     "零运行时引用；已被正式测试取代"),
    ("verify_tables.py", "D-一次性验证",
     "生产 DB 表结构验证脚本：直连生产 DB",
     "零运行时引用；表结构权威已上移到 server/schema/ + "
     "scripts/check_schema_consistency.py"),
    ("check_database.py", "D-一次性验证",
     "生产 DB 检查脚本：直连生产 DB",
     "零运行时引用；表结构权威已上移到 server/schema/ + "
     "scripts/check_schema_consistency.py"),

    # ---- E. Phase-1 时期的 shell / ps1 包装器 ------------------------------
    ("phase1_db_check.sh", "E-Phase1包装器",
     "Phase-1 期 DB 检查包装器：直连生产 DB",
     "零运行时引用；Phase-1 检查已由 tests/characterize 全面取代"),
    ("phase1_import_check.sh", "E-Phase1包装器",
     "Phase-1 期 import 检查包装器",
     "零运行时引用；已被 scripts/check_module_imports.js 取代"),
    ("phase1_node_check.sh", "E-Phase1包装器",
     "Phase-1 期 node 检查包装器",
     "零运行时引用；已被 scripts/check_module_imports.js 取代"),
    ("phase1_py_check.sh", "E-Phase1包装器",
     "Phase-1 期 python 检查包装器",
     "零运行时引用；已被 tests/characterize 取代"),
    ("phase1_py_compile.ps1", "E-Phase1包装器",
     "Phase-1 期 py_compile 包装器",
     "零运行时引用；已被 tests/characterize 取代"),
    ("phase1_py_compile_runner.ps1", "E-Phase1包装器",
     "Phase-1 期 py_compile runner 包装器",
     "零运行时引用；已被 tests/characterize 取代"),
    ("phase1_node_check.bat", "E-Phase1包装器",
     "Phase-1 期 node 检查 bat 包装器",
     "零运行时引用；已被 scripts/check_module_imports.js 取代"),
    ("phase1_smoke.bat", "E-Phase1包装器",
     "Phase-1 期 smoke bat 包装器",
     "零运行时引用；已被 tests/characterize 取代"),
    ("phase1_smoke_with_venv.bat", "E-Phase1包装器",
     "Phase-1 期 venv smoke bat 包装器",
     "零运行时引用；已被 tests/characterize 取代"),
    ("phase1_smoke.py", "E-Phase1包装器",
     "Phase-1 期 smoke 脚本",
     "仅 scripts/ 内部历史引用；已被 tests/characterize 取代"),
    ("_tmp_py_compile.ps1", "E-Phase1包装器",
     "临时 py_compile 包装器（文件名自带 tmp 语义）",
     "零运行时引用；临时产物"),
    ("_j_static_check.py", "E-Phase1包装器",
     "Phase-1 期静态检查脚本",
     "零运行时引用；已被 scripts/check_module_imports.js 取代"),
    ("_phase1_inspect_backend.py", "E-Phase1包装器",
     "Phase-1 期后端结构勘察脚本",
     "零运行时引用；勘察使命结束"),
    ("_phase1_inspect_tables.py", "E-Phase1包装器",
     "Phase-1 期表结构勘察脚本",
     "零运行时引用；勘察使命结束"),
    ("_run_verify.py", "E-Phase1包装器",
     "verify_p0_cleanup 的 venv 包装器（一次性便利脚本）",
     "零运行时引用；当前直接用 .venv\\Scripts\\python.exe 即可"),
    ("_run_verify_p0.ps1", "E-Phase1包装器",
     "P0 验证 ps1 包装器 v1",
     "零运行时引用；历史验收脚本"),
    ("_run_verify_p0_v2.ps1", "E-Phase1包装器",
     "P0 验证 ps1 包装器 v2",
     "零运行时引用；历史验收脚本"),
    ("verify_todo5.bat", "E-Phase1包装器",
     "Todo-5 验收 bat 包装器",
     "零运行时引用；历史验收脚本"),
    ("run_ar02_safe_baseline.ps1", "E-Phase1包装器",
     "AR02 安全基线 ps1 包装器",
     "零运行时引用；历史验收脚本"),
    ("run_node_check.ps1", "E-Phase1包装器",
     "node 检查 ps1 包装器",
     "零运行时引用；已被 scripts/check_module_imports.js 取代"),
    ("write_pycompile_runner.js", "E-Phase1包装器",
     "生成 py_compile runner 的一次性生成器",
     "零运行时引用；生成目标已归档"),
    ("count_py_lines.ps1", "E-Phase1包装器",
     "Python 行数统计 ps1（一次性度量工具）",
     "零运行时引用；一次性度量工具"),
    ("rebuild_premigration_index.js", "E-Phase1包装器",
     "重建迁移前 CSS 基线索引（AR03-P4 离线核对用）",
     "仅 P4 交付文档提及（历史复现命令）；迁移已完成，"
     "基线产物已归档于 _archive/11_AR03_P5_一次性脚本/_temp_artifacts/root/"),

    # ---- F. 迁移期一次性迁移器 ---------------------------------------------
    ("migrate_fix_missing_tables.py", "F-迁移期迁移器",
     "补建缺失表的一次性迁移器：直连生产 DB **并写表**",
     "零运行时引用；Schema 权威已上移到 server/schema/ + "
     "scripts/check_schema_consistency.py；直连生产 DB 且写表（红线面）"),
    ("_build_p2_migration_map.py", "F-迁移期迁移器",
     "P2 三层映射生成器（生成 tests/fixtures/p2_migration_map.json）",
     "产物已冻结且被 test_static_route_inventory.py 等引用；"
     "生成器本身无运行时引用"),
    ("_freeze_legacy_baseline.py", "F-迁移期迁移器",
     "legacy 基线冻结器（生成 tests/fixtures/legacy_baseline.json）",
     "产物已冻结且被 test_health_contract.py / "
     "test_legacy_divergence_ledger.py 引用；生成器本身无运行时引用"),
    ("legacy_baseline.py", "F-迁移期迁移器",
     "legacy 基线采集器（一次性生成冻结产物）",
     "产物已冻结；采集器本身无运行时引用"),
    ("legacy_divergence_probe.py", "F-迁移期迁移器",
     "legacy/Factory 差异探针",
     "⚠️ **被 test_legacy_divergence_ledger.py import** —— "
     "**必须保留原位**，不归档"),
)


#: 明确 **不** 归档的 scripts/ 成员（附理由），用于生成对照表。
KEEP_IN_PLACE: tuple[tuple[str, str], ...] = (
    ("launch_server.py", "生产启动链入口（启动学习工具.bat → start_web_safe.bat → 本脚本）"),
    ("start_web_safe.bat", "生产启动链中间层（安全启动）"),
    ("stop_web_safe.bat", "生产停止入口"),
    ("stop_server.py", "停止入口（Python 侧）"),
    ("启动学习工具.bat", "生产启动链根入口（双击启动）"),
    ("start.bat", "简版启动入口"),
    ("start_web_legacy.bat", "legacy 启动（launch_server.py 支持但 fail closed 拒绝）"),
    ("start_learn_phase2.bat", "Phase-2 启动（run_app.py 路径）"),
    ("start_alpha_local.bat", "alpha 本地启动配套"),
    ("start-desktop.bat", "桌面端入口（PySide6 已归档，fail closed）"),
    ("backup_user_data.bat", "用户数据备份入口（AGENTS.md 记载）"),
    ("main.py", "桌面端 fail-closed 入口 —— **被 test_desktop_archive_integrity.py 断言**"),
    ("route_inventory.py", "静态路由清单 oracle —— 被 3 个 characterization 测试 import"),
    ("golden_snapshot.py", "黄金 HTTP 快照 —— 被 test_golden_http_snapshot.py import"),
    ("legacy_divergence_probe.py", "差异探针 —— 被 test_legacy_divergence_ledger.py import"),
    ("verify_p0_cleanup.py", "P0 契约门禁（T1–T6）"),
    ("phase2_gacha_golden.py", "Gacha Golden 100250 组基线"),
    ("agent_policy_publisher.py", "受控 Publisher（外部 Agent 提案发布）"),
    ("run_e2e_isolated.js", "隔离 E2E 入口（36/36）"),
    ("check_module_imports.js", "模块边界门禁"),
    ("check_css_architecture.js", "CSS 架构门禁（6 门禁）"),
    ("check_layout_utility_conflicts.js", "布局工具类冲突扫描"),
    ("capture_css_baselines.js", "CSS 迁移基线采集"),
    ("check_schema_consistency.py", "**P5 新增** Schema 一致性门禁（14+2 表）"),
    ("art-asset-registry.js", "美术资产登记表（被 src/index.html 引入）"),
    ("art-asset-registry.test.js", "美术资产登记表自测"),
    ("export_tasks_for_ai.py", "协作工具：导出任务快照（ai_workspace 流程，长期保留）"),
    ("validate_task_patch.py", "协作工具：校验 AI 任务修改草稿（长期保留）"),
    ("verify_transferred_project.bat", "迁移后项目结构校验"),
    ("run_stable_acceptance.bat", "稳定验收入口"),
    ("_pwsh.ps1", "PowerShell 7 引导封装"),
    ("批量处理笔记.ps1", "笔记批量处理工具（用户运维脚本）"),
    ("remove_note_links.ps1", "笔记链接清理工具（用户运维脚本）"),
)


def _is_redline(rel: Path) -> bool:
    """判断相对路径是否命中红线（fail closed）。"""
    parts = rel.parts
    for prefix in REDLINE_PREFIXES:
        if parts[: len(prefix)] == prefix:
            return True
    for f in REDLINE_FILES:
        if parts == f:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不执行")
    args = parser.parse_args()

    ARCHIVE.mkdir(parents=True, exist_ok=True)

    moved: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    missing: list[str] = []

    for name, category, reason, verification in ARCHIVE_LIST:
        src = SCRIPTS / name
        rel = src.relative_to(ROOT)
        if _is_redline(rel):
            print(f"[REDLINE] 拒绝归档红线路径: {rel}", file=sys.stderr)
            return 2

        if not src.exists():
            alt = ARCHIVE / name
            if alt.exists():
                skipped.append((name, category))
                print(f"[SKIP] 已在归档目录: {name}")
                continue
            missing.append(name)
            print(f"[MISS] 源文件不存在且归档目录也没有: {name}", file=sys.stderr)
            continue

        if args.dry_run:
            print(f"[PLAN] {category:16s} {name}  ->  {ARCHIVE.relative_to(ROOT)}/{name}")
            print(f"       理由: {reason}")
            print(f"       核实: {verification}")
            moved.append((name, category))
            continue

        dst = ARCHIVE / name
        shutil.move(str(src), str(dst))
        moved.append((name, category))
        print(f"[MOVED] {category:16s} {name}")

    print()
    print(f"归档 {len(moved)} 项 / 已归档跳过 {len(skipped)} 项 / 缺失 {len(missing)} 项")
    if missing:
        for m in missing:
            print(f"  [MISS] {m}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
