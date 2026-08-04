"""
归档清理脚本
将项目中的非核心文件移动到 _archive 目录
"""
import os
import shutil
from pathlib import Path
import json
from datetime import datetime

# 项目根目录
PROJECT_ROOT = Path(r"D:\Axelit\.工作\trae\超级自动化学习工具")

# 归档目录基础路径
ARCHIVE_ROOT = PROJECT_ROOT / "_archive"

# 统计
stats = {
    "moved_files": 0,
    "moved_dirs": 0,
    "skipped": 0,
    "errors": [],
    "files_list": {}
}

def log(msg):
    print(f"  {msg}")

def ensure_dir(path):
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)

def move_item(src, dst_dir, category_name):
    """移动文件或目录"""
    try:
        if not src.exists():
            return False, "源不存在"
        
        dst = dst_dir / src.name
        if dst.exists():
            # 如果目标已存在，添加时间戳
            dst = dst_dir / f"{src.stem}_{datetime.now().strftime('%H%M%S')}{src.suffix}"
        
        if src.is_dir():
            shutil.move(str(src), str(dst))
            stats["moved_dirs"] += 1
        else:
            shutil.move(str(src), str(dst))
            stats["moved_files"] += 1
        
        rel_path = dst.relative_to(ARCHIVE_ROOT)
        stats["files_list"][str(rel_path)] = str(src.relative_to(PROJECT_ROOT))
        return True, str(dst.name)
    except Exception as e:
        stats["errors"].append(f"{src}: {str(e)}")
        return False, str(e)

def main():
    print("=" * 60)
    print("归档清理脚本")
    print("=" * 60)
    print(f"\n项目目录: {PROJECT_ROOT}")
    print(f"归档目录: {ARCHIVE_ROOT}\n")
    
    # 创建归档目录结构
    print("[1] 创建归档目录结构...")
    archive_dirs = [
        "01_临时脚本",
        "02_缓存数据",
        "03_数据库备份",
        "04_PPT提取物",
        "05_过时文档/docs",
        "06_测试脚本",
        "07_工具脚本",
        "08_提示词备份",
        "09_审计报告",
        "10_其他杂项",
    ]
    for d in archive_dirs:
        ensure_dir(ARCHIVE_ROOT / d)
    print(f"    创建了 {len(archive_dirs)} 个目录\n")
    
    # ==================== 01_临时脚本 ====================
    print("[2] 01_临时脚本...")
    patterns = ["*_*.py", "ocr_*.py", "ocr_*.txt", "ocr_windows.ps1", "extract_*.py"]
    for p in patterns:
        for f in PROJECT_ROOT.glob(p):
            if f.name.startswith("_") or f.name.startswith("ocr_") or f.name.startswith("extract_"):
                if f.is_file() and f.suffix in ['.py', '.txt', '.ps1']:
                    ok, _ = move_item(f, ARCHIVE_ROOT / "01_临时脚本", "临时脚本")
                    if ok:
                        log(f"  + {f.name}")
    
    # ==================== 02_缓存数据 ====================
    print("[3] 02_缓存数据...")
    cache_dirs = ["data/extracted", "data/ai_exports", "data/ai_imports"]
    for d in cache_dirs:
        src_path = PROJECT_ROOT / d
        if src_path.exists():
            ok, _ = move_item(src_path, ARCHIVE_ROOT / "02_缓存数据", "缓存数据")
            if ok:
                log(f"  + {d}/")
    
    # ==================== 03_数据库备份 ====================
    print("[4] 03_数据库备份...")
    for f in PROJECT_ROOT.glob("data/*backup*.db"):
        ok, _ = move_item(f, ARCHIVE_ROOT / "03_数据库备份", "数据库备份")
        if ok:
            log(f"  + {f.name}")
    
    # ==================== 04_PPT提取物 ====================
    print("[5] 04_PPT提取物...")
    ppt_dir = PROJECT_ROOT / "src/notes/ppt_extracted"
    if ppt_dir.exists():
        ok, _ = move_item(ppt_dir, ARCHIVE_ROOT / "04_PPT提取物", "PPT提取物")
        if ok:
            log(f"  + src/notes/ppt_extracted/")
    
    # ==================== 05_过时文档 ====================
    print("[6] 05_过时文档...")
    docs_dir = PROJECT_ROOT / "docs"
    keep_files = ["README.md", "项目重启方案.md"]
    if docs_dir.exists():
        for f in docs_dir.glob("*.md"):
            if f.name not in keep_files:
                ok, _ = move_item(f, ARCHIVE_ROOT / "05_过时文档/docs", "过时文档")
                if ok:
                    log(f"  + docs/{f.name}")
        # docs/reports
        reports_dir = docs_dir / "reports"
        if reports_dir.exists():
            ok, _ = move_item(reports_dir, ARCHIVE_ROOT / "05_过时文档/docs", "报告目录")
            if ok:
                log(f"  + docs/reports/")
        # docs/项目文档
        proj_docs_dir = docs_dir / "项目文档"
        if proj_docs_dir.exists():
            ok, _ = move_item(proj_docs_dir, ARCHIVE_ROOT / "05_过时文档/docs", "项目文档")
            if ok:
                log(f"  + docs/项目文档/")
    
    # ==================== 06_测试脚本 ====================
    print("[7] 06_测试脚本...")
    scripts_dir = PROJECT_ROOT / "scripts"
    test_patterns = [
        "p0_*", "p1_*", "debug_*", "fix_*", "check_*",
        "_crop_*", "_extract_*", "_fix_*", "_check_*",
        "link_*", "rebuild_*", "inspect_db*.py",
        "deep_verify.py", "scan_*", "generate_*"
    ]
    if scripts_dir.exists():
        for p in test_patterns:
            for f in scripts_dir.glob(p):
                ok, _ = move_item(f, ARCHIVE_ROOT / "06_测试脚本", "测试脚本")
                if ok:
                    log(f"  + scripts/{f.name}")
        # scripts/archive 和 tests
        for d in ["archive", "tests"]:
            sub_dir = scripts_dir / d
            if sub_dir.exists():
                ok, _ = move_item(sub_dir, ARCHIVE_ROOT / "06_测试脚本", d)
                if ok:
                    log(f"  + scripts/{d}/")
    
    # ==================== 07_工具脚本 ====================
    print("[8] 07_工具脚本...")
    tools_dir = PROJECT_ROOT / "tools"
    if tools_dir.exists():
        ok, _ = move_item(tools_dir, ARCHIVE_ROOT / "07_工具脚本", "工具脚本")
        if ok:
            log(f"  + tools/")
    
    # ==================== 08_提示词备份 ====================
    print("[9] 08_提示词备份...")
    backup_dir = PROJECT_ROOT / "src/notes/prompts/.backups"
    if backup_dir.exists():
        ok, _ = move_item(backup_dir, ARCHIVE_ROOT / "08_提示词备份", "提示词备份")
        if ok:
            log(f"  + src/notes/prompts/.backups/")
    
    # ==================== 09_审计报告 ====================
    print("[10] 09_审计报告...")
    # 根目录和src目录下的审计/审查/质检文件
    audit_patterns = ["*审计*", "*审查*", "*质检*"]
    for p in audit_patterns:
        for f in PROJECT_ROOT.glob(p):
            if f.is_file():
                ok, _ = move_item(f, ARCHIVE_ROOT / "09_审计报告", "审计报告")
                if ok:
                    log(f"  + {f.name}")
        for f in (PROJECT_ROOT / "src").glob(p):
            if f.is_file():
                ok, _ = move_item(f, ARCHIVE_ROOT / "09_审计报告", "审计报告")
                if ok:
                    log(f"  + src/{f.name}")
        for f in (PROJECT_ROOT / "src/notes").glob(p):
            if f.is_file():
                ok, _ = move_item(f, ARCHIVE_ROOT / "09_审计报告", "审计报告")
                if ok:
                    log(f"  + src/notes/{f.name}")
    
    # ==================== 10_其他杂项 ====================
    print("[11] 10_其他杂项...")
    misc_patterns = ["_p5_3*.json", "*.tmp", "*.log"]
    for p in misc_patterns:
        for f in PROJECT_ROOT.glob(p):
            if f.is_file():
                ok, _ = move_item(f, ARCHIVE_ROOT / "10_其他杂项", "其他杂项")
                if ok:
                    log(f"  + {f.name}")
    
    # ==================== 生成报告 ====================
    print("\n" + "=" * 60)
    print("归档完成！")
    print("=" * 60)
    print(f"\n统计:")
    print(f"  移动文件: {stats['moved_files']}")
    print(f"  移动目录: {stats['moved_dirs']}")
    print(f"  错误数: {len(stats['errors'])}")
    
    if stats['errors']:
        print(f"\n错误列表:")
        for e in stats['errors'][:10]:
            print(f"  - {e}")
    
    # 保存详细报告
    report_path = ARCHIVE_ROOT / "归档报告.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告: {report_path}")
    
    return stats

if __name__ == "__main__":
    main()
