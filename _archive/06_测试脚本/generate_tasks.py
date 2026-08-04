"""
生成所有科目的期末复习任务 JSON 导入文件。
每个科目独立定义任务列表，脚本负责生成符合任务系统格式的 JSON。
"""
import json
import os
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ai_imports")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 辅助：用任务名引用依赖
def dep(*names):
    """生成 prerequisite_ids 引用列表"""
    result = []
    for n in names:
        if n is None:
            result.append("${prev_task_id}")
        else:
            result.append(f"${{task_name:{n}}}")
    return result


# ==============================
# 一、英语四级（CET-4）考试：6月13日
# priority=9, difficulty=2-3
# ==============================
cet4_tasks = [
    # ---- 单词 ----
    {"name": "背诵100个四级单词", "estimated_time": 30, "repeat_type": "daily", "tags": ["英语", "四级", "单词"],
     "difficulty": 1, "priority": 9, "resistance": "low", "energy_required": "low"},

    # ---- 写作模块 ----
    {"name": "复习笔记「CET4-写作-保底原则与核心策略」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "写作"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「CET4-写作-议论文框架」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "写作"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「CET4-写作-三大论证方式」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "写作"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「CET4-写作-句子扩写与句型改写」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "写作"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「CET4-写作-书信与应用文」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "写作"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「CET4-写作-书信作文模板与写法」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "写作"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "写一篇四级作文（议论文或书信交替）", "estimated_time": 40, "repeat_type": "weekly",
     "tags": ["英语", "四级", "写作", "练习"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},

    # ---- 听力模块 ----
    {"name": "复习笔记「CET4-听力-长对话题型解题方法」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "听力"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「CET4-听力-长对话信号词体系与真题技巧」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "听力"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「CET4-听力-新闻与篇章解题策略」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "听力"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "做第一套四级真题听力部分", "estimated_time": 30, "repeat_type": "single",
     "tags": ["英语", "四级", "听力", "真题"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},
    {"name": "做第二套四级真题听力部分", "estimated_time": 30, "repeat_type": "single",
     "tags": ["英语", "四级", "听力", "真题"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},
    {"name": "做第三套四级真题听力部分", "estimated_time": 30, "repeat_type": "single",
     "tags": ["英语", "四级", "听力", "真题"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},
    {"name": "做第四套四级真题听力部分", "estimated_time": 30, "repeat_type": "single",
     "tags": ["英语", "四级", "听力", "真题"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},

    # ---- 阅读模块 ----
    {"name": "复习笔记「CET4-阅读-三步定位法与题型分类」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "阅读"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「CET4-阅读-题型分类与主旨题解法」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "阅读"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「CET4-阅读-仔细阅读总览与答题策略」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "阅读"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「CET4-阅读-仔细阅读泛读与主旨定位」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "阅读"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「CET4-阅读-选词填空题解题策略」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "阅读"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「CET4-阅读-长篇阅读解题方法」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "阅读"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},
    {"name": "做第一套四级真题阅读部分", "estimated_time": 40, "repeat_type": "single",
     "tags": ["英语", "四级", "阅读", "真题"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},
    {"name": "做第二套四级真题阅读部分", "estimated_time": 40, "repeat_type": "single",
     "tags": ["英语", "四级", "阅读", "真题"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},
    {"name": "做第三套四级真题阅读部分", "estimated_time": 40, "repeat_type": "single",
     "tags": ["英语", "四级", "阅读", "真题"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},
    {"name": "做第四套四级真题阅读部分", "estimated_time": 40, "repeat_type": "single",
     "tags": ["英语", "四级", "阅读", "真题"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},

    # ---- 语法模块 ----
    {"name": "复习笔记「CET4-语法-非谓语动词与被动语态」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["英语", "四级", "语法"], "difficulty": 2, "priority": 9, "resistance": "medium", "energy_required": "medium"},

    # ---- 翻译 ----
    {"name": "做第一套四级真题翻译部分", "estimated_time": 30, "repeat_type": "single",
     "tags": ["英语", "四级", "翻译", "真题"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},
    {"name": "做第二套四级真题翻译部分", "estimated_time": 30, "repeat_type": "single",
     "tags": ["英语", "四级", "翻译", "真题"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},
    {"name": "做第三套四级真题翻译部分", "estimated_time": 30, "repeat_type": "single",
     "tags": ["英语", "四级", "翻译", "真题"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},
    {"name": "做第四套四级真题翻译部分", "estimated_time": 30, "repeat_type": "single",
     "tags": ["英语", "四级", "翻译", "真题"], "difficulty": 3, "priority": 9, "resistance": "high", "energy_required": "high"},

    # ---- 完整模拟 ----
    {"name": "做第一套四级真题全卷（限时）", "estimated_time": 125, "repeat_type": "single",
     "tags": ["英语", "四级", "真题", "模拟"], "difficulty": 4, "priority": 10, "resistance": "high", "energy_required": "high"},
    {"name": "做第二套四级真题全卷（限时）", "estimated_time": 125, "repeat_type": "single",
     "tags": ["英语", "四级", "真题", "模拟"], "difficulty": 4, "priority": 10, "resistance": "high", "energy_required": "high"},
    {"name": "做第三套四级真题全卷（限时）", "estimated_time": 125, "repeat_type": "single",
     "tags": ["英语", "四级", "真题", "模拟"], "difficulty": 4, "priority": 10, "resistance": "high", "energy_required": "high"},
    {"name": "做第四套四级真题全卷（限时）", "estimated_time": 125, "repeat_type": "single",
     "tags": ["英语", "四级", "真题", "模拟"], "difficulty": 4, "priority": 10, "resistance": "high", "energy_required": "high"},
]

# CET-4 依赖关系
cet4_deps = {}
# 写作链：2→3→4→5→6→7→8
cet4_deps["复习笔记「CET4-写作-议论文框架」"] = dep("复习笔记「CET4-写作-保底原则与核心策略」")
cet4_deps["复习笔记「CET4-写作-三大论证方式」"] = dep("复习笔记「CET4-写作-议论文框架」")
cet4_deps["复习笔记「CET4-写作-句子扩写与句型改写」"] = dep("复习笔记「CET4-写作-三大论证方式」")
cet4_deps["复习笔记「CET4-写作-书信与应用文」"] = dep("复习笔记「CET4-写作-句子扩写与句型改写」")
cet4_deps["复习笔记「CET4-写作-书信作文模板与写法」"] = dep("复习笔记「CET4-写作-书信与应用文」")
cet4_deps["写一篇四级作文（议论文或书信交替）"] = dep("复习笔记「CET4-写作-书信作文模板与写法」")

# 听力链：9→10→11, 10→12→13→14→15
cet4_deps["复习笔记「CET4-听力-长对话信号词体系与真题技巧」"] = dep("复习笔记「CET4-听力-长对话题型解题方法」")
cet4_deps["复习笔记「CET4-听力-新闻与篇章解题策略」"] = dep("复习笔记「CET4-听力-长对话信号词体系与真题技巧」")
cet4_deps["做第一套四级真题听力部分"] = dep("复习笔记「CET4-听力-长对话信号词体系与真题技巧」")
cet4_deps["做第二套四级真题听力部分"] = dep("做第一套四级真题听力部分")
cet4_deps["做第三套四级真题听力部分"] = dep("做第二套四级真题听力部分")
cet4_deps["做第四套四级真题听力部分"] = dep("做第三套四级真题听力部分")

# 阅读链：16→17→18→19→20→21, 18→22→23→24→25
cet4_deps["复习笔记「CET4-阅读-题型分类与主旨题解法」"] = dep("复习笔记「CET4-阅读-三步定位法与题型分类」")
cet4_deps["复习笔记「CET4-阅读-仔细阅读总览与答题策略」"] = dep("复习笔记「CET4-阅读-题型分类与主旨题解法」")
cet4_deps["复习笔记「CET4-阅读-仔细阅读泛读与主旨定位」"] = dep("复习笔记「CET4-阅读-仔细阅读总览与答题策略」")
cet4_deps["复习笔记「CET4-阅读-选词填空题解题策略」"] = dep("复习笔记「CET4-阅读-仔细阅读泛读与主旨定位」")
cet4_deps["复习笔记「CET4-阅读-长篇阅读解题方法」"] = dep("复习笔记「CET4-阅读-选词填空题解题策略」")
cet4_deps["做第一套四级真题阅读部分"] = dep("复习笔记「CET4-阅读-仔细阅读总览与答题策略」")
cet4_deps["做第二套四级真题阅读部分"] = dep("做第一套四级真题阅读部分")
cet4_deps["做第三套四级真题阅读部分"] = dep("做第二套四级真题阅读部分")
cet4_deps["做第四套四级真题阅读部分"] = dep("做第三套四级真题阅读部分")

# 翻译链：27→28→29→30
cet4_deps["做第二套四级真题翻译部分"] = dep("做第一套四级真题翻译部分")
cet4_deps["做第三套四级真题翻译部分"] = dep("做第二套四级真题翻译部分")
cet4_deps["做第四套四级真题翻译部分"] = dep("做第三套四级真题翻译部分")

# 全卷模拟：依赖对应套数的听力+阅读+翻译
cet4_deps["做第一套四级真题全卷（限时）"] = dep("做第一套四级真题听力部分", "做第一套四级真题阅读部分", "做第一套四级真题翻译部分")
cet4_deps["做第二套四级真题全卷（限时）"] = dep("做第二套四级真题听力部分", "做第二套四级真题阅读部分", "做第二套四级真题翻译部分")
cet4_deps["做第三套四级真题全卷（限时）"] = dep("做第三套四级真题听力部分", "做第三套四级真题阅读部分", "做第三套四级真题翻译部分")
cet4_deps["做第四套四级真题全卷（限时）"] = dep("做第四套四级真题听力部分", "做第四套四级真题阅读部分", "做第四套四级真题翻译部分")


# ==============================
# 二、电子技术 | 考试：6月18日
# priority=8
# ==============================
dzjs_tasks = [
    {"name": "复习笔记「01_半导体基础与PN结」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["电子技术", "半导体", "复习"], "difficulty": 2, "priority": 8, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「02_二极管特性与等效模型」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["电子技术", "二极管", "复习"], "difficulty": 2, "priority": 8, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「03_半导体三极管原理」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["电子技术", "三极管", "复习"], "difficulty": 2, "priority": 8, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「04_直流电路分析基础」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["电子技术", "电路分析", "复习"], "difficulty": 2, "priority": 8, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「05_交流电路分析基础」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["电子技术", "电路分析", "复习"], "difficulty": 2, "priority": 8, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「06_三极管放大电路_静态分析」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["电子技术", "放大电路", "复习"], "difficulty": 3, "priority": 8, "resistance": "medium", "energy_required": "high"},
    {"name": "做静态工作点 I_BQ、I_CQ、V_CEQ 计算题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["电子技术", "放大电路", "计算"], "difficulty": 3, "priority": 8, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「07_三极管放大电路_动态分析」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["电子技术", "放大电路", "复习"], "difficulty": 3, "priority": 8, "resistance": "medium", "energy_required": "high"},
    {"name": "复习笔记「08_布尔代数与逻辑门电路」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["电子技术", "数字电路", "复习"], "difficulty": 2, "priority": 8, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「09_逻辑函数化简_公式法与卡诺图」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["电子技术", "数字电路", "卡诺图", "复习"], "difficulty": 3, "priority": 8, "resistance": "medium", "energy_required": "high"},
    {"name": "做卡诺图化简必考题（4变量，圈1原则）", "estimated_time": 30, "repeat_type": "single",
     "tags": ["电子技术", "数字电路", "卡诺图", "练习"], "difficulty": 3, "priority": 8, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「10_组合逻辑电路分析与设计」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["电子技术", "数字电路", "复习"], "difficulty": 3, "priority": 8, "resistance": "medium", "energy_required": "high"},
    {"name": "做组合逻辑电路分析题（电路→表达式→真值表→功能）", "estimated_time": 30, "repeat_type": "single",
     "tags": ["电子技术", "数字电路", "练习"], "difficulty": 3, "priority": 8, "resistance": "high", "energy_required": "high"},
    {"name": "做组合逻辑电路设计题（功能→真值表→表达式→电路图）", "estimated_time": 30, "repeat_type": "single",
     "tags": ["电子技术", "数字电路", "练习"], "difficulty": 3, "priority": 8, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「11_编码器与集成电路实现」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["电子技术", "数字电路", "复习"], "difficulty": 2, "priority": 8, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「12_数字信号与编码技术」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["电子技术", "数字电路", "编码", "复习"], "difficulty": 2, "priority": 8, "resistance": "medium", "energy_required": "medium"},
]

dzjs_deps = {}
dzjs_deps["复习笔记「02_二极管特性与等效模型」"] = dep("复习笔记「01_半导体基础与PN结」")
dzjs_deps["复习笔记「03_半导体三极管原理」"] = dep("复习笔记「02_二极管特性与等效模型」")
dzjs_deps["复习笔记「04_直流电路分析基础」"] = dep("复习笔记「03_半导体三极管原理」")
dzjs_deps["复习笔记「05_交流电路分析基础」"] = dep("复习笔记「04_直流电路分析基础」")
dzjs_deps["复习笔记「06_三极管放大电路_静态分析」"] = dep("复习笔记「05_交流电路分析基础」")
dzjs_deps["做静态工作点 I_BQ、I_CQ、V_CEQ 计算题"] = dep("复习笔记「06_三极管放大电路_静态分析」")
dzjs_deps["复习笔记「07_三极管放大电路_动态分析」"] = dep("复习笔记「06_三极管放大电路_静态分析」")
dzjs_deps["复习笔记「08_布尔代数与逻辑门电路」"] = dep("复习笔记「07_三极管放大电路_动态分析」")
dzjs_deps["复习笔记「09_逻辑函数化简_公式法与卡诺图」"] = dep("复习笔记「08_布尔代数与逻辑门电路」")
dzjs_deps["做卡诺图化简必考题（4变量，圈1原则）"] = dep("复习笔记「09_逻辑函数化简_公式法与卡诺图」")
dzjs_deps["复习笔记「10_组合逻辑电路分析与设计」"] = dep("复习笔记「09_逻辑函数化简_公式法与卡诺图」")
dzjs_deps["做组合逻辑电路分析题（电路→表达式→真值表→功能）"] = dep("复习笔记「10_组合逻辑电路分析与设计」")
dzjs_deps["做组合逻辑电路设计题（功能→真值表→表达式→电路图）"] = dep("复习笔记「10_组合逻辑电路分析与设计」")
dzjs_deps["复习笔记「11_编码器与集成电路实现」"] = dep("复习笔记「10_组合逻辑电路分析与设计」")
dzjs_deps["复习笔记「12_数字信号与编码技术」"] = dep("复习笔记「11_编码器与集成电路实现」")


# ==============================
# 三、计算机 | 考试：6月25日
# priority=7
# ==============================
jsj_tasks = [
    {"name": "复习笔记「01_计算机系统概述与硬件组成」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "系统概述", "复习"], "difficulty": 2, "priority": 7, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「02_程序设计语言发展简史」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "编程语言", "复习"], "difficulty": 2, "priority": 7, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「03_计算机层次结构与指令集」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "系统结构", "复习"], "difficulty": 2, "priority": 7, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「04_计算机硬件组成与总线」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "硬件", "复习"], "difficulty": 2, "priority": 7, "resistance": "medium", "energy_required": "medium"},
    {"name": "背诵冯诺依曼主要思想", "estimated_time": 15, "repeat_type": "single",
     "tags": ["计算机", "冯诺依曼", "背诵"], "difficulty": 1, "priority": 7, "resistance": "low", "energy_required": "low"},
    {"name": "复习笔记「05_数据表示与编码概述」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "数据编码", "复习"], "difficulty": 2, "priority": 7, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「06_数值数据的编码_原码反码补码」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["计算机", "数据编码", "补码", "复习"], "difficulty": 3, "priority": 7, "resistance": "medium", "energy_required": "high"},
    {"name": "做补码求真值计算题", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "数据编码", "补码", "计算"], "difficulty": 3, "priority": 7, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「07_非数值数据与字符编码」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "字符编码", "复习"], "difficulty": 2, "priority": 7, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「08_数据存储与单位」", "estimated_time": 20, "repeat_type": "single",
     "tags": ["计算机", "数据存储", "复习"], "difficulty": 2, "priority": 7, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习笔记「09_数据运算与位操作」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "位操作", "复习"], "difficulty": 2, "priority": 7, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习IEEE754单精度浮点数转换规则", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "IEEE754", "浮点数", "复习"], "difficulty": 3, "priority": 7, "resistance": "medium", "energy_required": "high"},
    {"name": "做IEEE754双向转换计算题（十进制↔IEEE754）", "estimated_time": 30, "repeat_type": "single",
     "tags": ["计算机", "IEEE754", "浮点数", "计算"], "difficulty": 3, "priority": 7, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「10_指令格式与数据传送」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "指令", "复习"], "difficulty": 2, "priority": 7, "resistance": "medium", "energy_required": "medium"},
    {"name": "复习寻址方式与MOV/LEA指令", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "寻址", "汇编", "复习"], "difficulty": 3, "priority": 7, "resistance": "medium", "energy_required": "high"},
    {"name": "做寻址与指令执行结果分析题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["计算机", "寻址", "汇编", "练习"], "difficulty": 3, "priority": 7, "resistance": "high", "energy_required": "high"},
    {"name": "复习加法器分析流程", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "加法器", "复习"], "difficulty": 2, "priority": 7, "resistance": "medium", "energy_required": "medium"},
    {"name": "做加法器分析题（换数据考查）", "estimated_time": 30, "repeat_type": "single",
     "tags": ["计算机", "加法器", "练习"], "difficulty": 3, "priority": 7, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「11_程序的编译链接与符号解析」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "编译链接", "复习"], "difficulty": 2, "priority": 7, "resistance": "medium", "energy_required": "medium"},
    {"name": "背诵源程序到可执行文件的转换步骤（预处理→编译→汇编→链接）", "estimated_time": 15, "repeat_type": "single",
     "tags": ["计算机", "编译链接", "背诵"], "difficulty": 1, "priority": 7, "resistance": "low", "energy_required": "low"},
    {"name": "复习笔记「12_指令执行过程详解」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["计算机", "指令执行", "复习"], "difficulty": 2, "priority": 7, "resistance": "medium", "energy_required": "medium"},
    {"name": "背诵机器指令完整执行过程（6步）", "estimated_time": 15, "repeat_type": "single",
     "tags": ["计算机", "指令执行", "背诵"], "difficulty": 1, "priority": 7, "resistance": "low", "energy_required": "low"},
]

jsj_deps = {}
jsj_deps["复习笔记「02_程序设计语言发展简史」"] = dep("复习笔记「01_计算机系统概述与硬件组成」")
jsj_deps["复习笔记「03_计算机层次结构与指令集」"] = dep("复习笔记「02_程序设计语言发展简史」")
jsj_deps["复习笔记「04_计算机硬件组成与总线」"] = dep("复习笔记「03_计算机层次结构与指令集」")
jsj_deps["背诵冯诺依曼主要思想"] = dep("复习笔记「04_计算机硬件组成与总线」")
jsj_deps["复习笔记「05_数据表示与编码概述」"] = dep("复习笔记「04_计算机硬件组成与总线」")
jsj_deps["复习笔记「06_数值数据的编码_原码反码补码」"] = dep("复习笔记「05_数据表示与编码概述」")
jsj_deps["做补码求真值计算题"] = dep("复习笔记「06_数值数据的编码_原码反码补码」")
jsj_deps["复习笔记「07_非数值数据与字符编码」"] = dep("复习笔记「05_数据表示与编码概述」")
jsj_deps["复习笔记「08_数据存储与单位」"] = dep("复习笔记「07_非数值数据与字符编码」")
jsj_deps["复习笔记「09_数据运算与位操作」"] = dep("复习笔记「08_数据存储与单位」")
jsj_deps["做IEEE754双向转换计算题（十进制↔IEEE754）"] = dep("复习IEEE754单精度浮点数转换规则")
jsj_deps["复习笔记「10_指令格式与数据传送」"] = dep("复习笔记「09_数据运算与位操作」")
jsj_deps["复习寻址方式与MOV/LEA指令"] = dep("复习笔记「10_指令格式与数据传送」")
jsj_deps["做寻址与指令执行结果分析题"] = dep("复习寻址方式与MOV/LEA指令")
jsj_deps["做加法器分析题（换数据考查）"] = dep("复习加法器分析流程")
jsj_deps["复习笔记「11_程序的编译链接与符号解析」"] = dep("复习笔记「10_指令格式与数据传送」")
jsj_deps["背诵源程序到可执行文件的转换步骤（预处理→编译→汇编→链接）"] = dep("复习笔记「11_程序的编译链接与符号解析」")
jsj_deps["复习笔记「12_指令执行过程详解」"] = dep("复习笔记「11_程序的编译链接与符号解析」")
jsj_deps["背诵机器指令完整执行过程（6步）"] = dep("复习笔记「12_指令执行过程详解」")


# ==============================
# 四、线性代数 | 考试：6月29日
# priority=6
# ==============================
xxds_tasks = [
    # 第1章 行列式
    {"name": "复习笔记「13_行列式的性质与计算」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "行列式", "复习"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "做课后习题行列式性质与计算", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "行列式", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做真题中行列式填空题/计算题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "行列式", "真题"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「07_行列式展开与逆矩阵」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "行列式", "逆矩阵", "复习"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "做课后习题行列式展开与逆矩阵", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "行列式", "逆矩阵", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做真题中伴随矩阵/逆矩阵题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "行列式", "逆矩阵", "真题"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},

    # 第2章 矩阵
    {"name": "复习笔记「11_矩阵秩的定义与计算」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "矩阵", "秩", "复习"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "做课后习题矩阵秩的计算（化为行阶梯形）", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "矩阵", "秩", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做真题中矩阵秩的填空题/选择题", "estimated_time": 25, "repeat_type": "single",
     "tags": ["线性代数", "矩阵", "秩", "真题"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「10_初等变换与标准型」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "矩阵", "初等变换", "复习"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "做课后习题初等变换与标准型", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "矩阵", "初等变换", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做真题中初等变换/矩阵等价题", "estimated_time": 25, "repeat_type": "single",
     "tags": ["线性代数", "矩阵", "初等变换", "真题"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},

    # 第3章 向量与方程组
    {"name": "复习笔记「05_向量运算与内积」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["线性代数", "向量", "内积", "复习"], "difficulty": 2, "priority": 6, "resistance": "medium", "energy_required": "medium"},
    {"name": "做课后习题向量运算与内积（夹角/距离）", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "向量", "内积", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做真题中向量内积/夹角填空题", "estimated_time": 20, "repeat_type": "single",
     "tags": ["线性代数", "向量", "内积", "真题"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "复习笔记「01_线性相关与无关判定」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "向量", "线性相关", "复习"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "做课后习题线性相关/无关判定（通过秩判断）", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "向量", "线性相关", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做真题中线性相关/无关选择题", "estimated_time": 20, "repeat_type": "single",
     "tags": ["线性代数", "向量", "线性相关", "真题"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "复习笔记「04_向量组的秩与极大无关组」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "向量", "极大无关组", "复习"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "做课后习题向量组秩与极大无关组", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "向量", "极大无关组", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做真题中极大无关组/线性表示大题", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "向量", "极大无关组", "真题"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「02_线性空间与基底维数」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "线性空间", "复习"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "做课后习题线性空间与基底维数", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "线性空间", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「03_基与维数习题讲解」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "线性空间", "复习"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "做课后习题基与维数综合题", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "线性空间", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做真题中线性方程组求解大题（齐次/非齐次）", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "线性方程组", "真题"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},

    # 第4章 特征值与对角化
    {"name": "复习笔记「08_特征值与特征向量基础」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "特征值", "特征向量", "复习"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "做课后习题特征值与特征向量计算", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "特征值", "特征向量", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做真题中特征值/特征向量填空题/计算题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "特征值", "特征向量", "真题"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「09_特征值性质与判定」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["线性代数", "特征值", "复习"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "做课后习题特征值性质判断", "estimated_time": 25, "repeat_type": "single",
     "tags": ["线性代数", "特征值", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做真题中特征值性质选择题", "estimated_time": 20, "repeat_type": "single",
     "tags": ["线性代数", "特征值", "真题"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "复习笔记「12_相似矩阵与对角化」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "相似矩阵", "对角化", "复习"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "做课后习题相似矩阵与对角化判定", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "相似矩阵", "对角化", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做真题中相似对角化大题", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "相似矩阵", "对角化", "真题"], "difficulty": 4, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「06_矩阵相似与二次型」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["线性代数", "二次型", "复习"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "high"},
    {"name": "做课后习题二次型", "estimated_time": 35, "repeat_type": "single",
     "tags": ["线性代数", "二次型", "练习"], "difficulty": 3, "priority": 6, "resistance": "high", "energy_required": "high"},

    # 综合
    {"name": "做2021-2022线性代数真题全卷（限时）", "estimated_time": 100, "repeat_type": "single",
     "tags": ["线性代数", "真题", "模拟"], "difficulty": 4, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做2022-2023线性代数真题全卷（限时）", "estimated_time": 100, "repeat_type": "single",
     "tags": ["线性代数", "真题", "模拟"], "difficulty": 4, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做2023-2024线性代数真题全卷（限时）", "estimated_time": 100, "repeat_type": "single",
     "tags": ["线性代数", "真题", "模拟"], "difficulty": 4, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "做2024-2025线性代数真题全卷（限时）", "estimated_time": 100, "repeat_type": "single",
     "tags": ["线性代数", "真题", "模拟"], "difficulty": 4, "priority": 6, "resistance": "high", "energy_required": "high"},
    {"name": "整理线代错题并重做", "estimated_time": 45, "repeat_type": "single",
     "tags": ["线性代数", "错题", "整理"], "difficulty": 3, "priority": 6, "resistance": "medium", "energy_required": "medium"},
]

xxds_deps = {}
# 行列式
xxds_deps["做课后习题行列式性质与计算"] = dep("复习笔记「13_行列式的性质与计算」")
xxds_deps["做真题中行列式填空题/计算题"] = dep("复习笔记「13_行列式的性质与计算」")
xxds_deps["复习笔记「07_行列式展开与逆矩阵」"] = dep("复习笔记「13_行列式的性质与计算」")
xxds_deps["做课后习题行列式展开与逆矩阵"] = dep("复习笔记「07_行列式展开与逆矩阵」")
xxds_deps["做真题中伴随矩阵/逆矩阵题"] = dep("复习笔记「07_行列式展开与逆矩阵」")

# 矩阵（依赖6完成即依赖做真题中伴随矩阵/逆矩阵题）
xxds_deps["复习笔记「11_矩阵秩的定义与计算」"] = dep("做真题中伴随矩阵/逆矩阵题")
xxds_deps["做课后习题矩阵秩的计算（化为行阶梯形）"] = dep("复习笔记「11_矩阵秩的定义与计算」")
xxds_deps["做真题中矩阵秩的填空题/选择题"] = dep("复习笔记「11_矩阵秩的定义与计算」")
xxds_deps["复习笔记「10_初等变换与标准型」"] = dep("复习笔记「11_矩阵秩的定义与计算」")
xxds_deps["做课后习题初等变换与标准型"] = dep("复习笔记「10_初等变换与标准型」")
xxds_deps["做真题中初等变换/矩阵等价题"] = dep("复习笔记「10_初等变换与标准型」")

# 向量与方程组（依赖12完成 = 做真题中初等变换/矩阵等价题）
xxds_deps["复习笔记「05_向量运算与内积」"] = dep("做真题中初等变换/矩阵等价题")
xxds_deps["做课后习题向量运算与内积（夹角/距离）"] = dep("复习笔记「05_向量运算与内积」")
xxds_deps["做真题中向量内积/夹角填空题"] = dep("复习笔记「05_向量运算与内积」")
xxds_deps["复习笔记「01_线性相关与无关判定」"] = dep("复习笔记「05_向量运算与内积」")
xxds_deps["做课后习题线性相关/无关判定（通过秩判断）"] = dep("复习笔记「01_线性相关与无关判定」")
xxds_deps["做真题中线性相关/无关选择题"] = dep("复习笔记「01_线性相关与无关判定」")
xxds_deps["复习笔记「04_向量组的秩与极大无关组」"] = dep("复习笔记「01_线性相关与无关判定」")
xxds_deps["做课后习题向量组秩与极大无关组"] = dep("复习笔记「04_向量组的秩与极大无关组」")
xxds_deps["做真题中极大无关组/线性表示大题"] = dep("复习笔记「04_向量组的秩与极大无关组」")
xxds_deps["复习笔记「02_线性空间与基底维数」"] = dep("复习笔记「04_向量组的秩与极大无关组」")
xxds_deps["做课后习题线性空间与基底维数"] = dep("复习笔记「02_线性空间与基底维数」")
xxds_deps["复习笔记「03_基与维数习题讲解」"] = dep("复习笔记「02_线性空间与基底维数」")
xxds_deps["做课后习题基与维数综合题"] = dep("复习笔记「03_基与维数习题讲解」")
xxds_deps["做真题中线性方程组求解大题（齐次/非齐次）"] = dep("复习笔记「03_基与维数习题讲解」")

# 特征值与对角化（依赖26完成 = 做真题中线性方程组求解大题）
xxds_deps["复习笔记「08_特征值与特征向量基础」"] = dep("做真题中线性方程组求解大题（齐次/非齐次）")
xxds_deps["做课后习题特征值与特征向量计算"] = dep("复习笔记「08_特征值与特征向量基础」")
xxds_deps["做真题中特征值/特征向量填空题/计算题"] = dep("复习笔记「08_特征值与特征向量基础」")
xxds_deps["复习笔记「09_特征值性质与判定」"] = dep("复习笔记「08_特征值与特征向量基础」")
xxds_deps["做课后习题特征值性质判断"] = dep("复习笔记「09_特征值性质与判定」")
xxds_deps["做真题中特征值性质选择题"] = dep("复习笔记「09_特征值性质与判定」")
xxds_deps["复习笔记「12_相似矩阵与对角化」"] = dep("复习笔记「09_特征值性质与判定」")
xxds_deps["做课后习题相似矩阵与对角化判定"] = dep("复习笔记「12_相似矩阵与对角化」")
xxds_deps["做真题中相似对角化大题"] = dep("复习笔记「12_相似矩阵与对角化」")
xxds_deps["复习笔记「06_矩阵相似与二次型」"] = dep("复习笔记「12_相似矩阵与对角化」")
xxds_deps["做课后习题二次型"] = dep("复习笔记「06_矩阵相似与二次型」")

# 综合真题卷：依赖各章节对应的真题/习题
xxds_deps["做2021-2022线性代数真题全卷（限时）"] = dep(
    "做真题中行列式填空题/计算题", "做真题中伴随矩阵/逆矩阵题",
    "做真题中矩阵秩的填空题/选择题", "做真题中初等变换/矩阵等价题",
    "做真题中向量内积/夹角填空题", "做真题中线性相关/无关选择题",
    "做真题中极大无关组/线性表示大题", "做课后习题线性空间与基底维数",
    "做课后习题基与维数综合题", "做真题中线性方程组求解大题（齐次/非齐次）",
    "做真题中特征值/特征向量填空题/计算题", "做真题中特征值性质选择题",
    "做真题中相似对角化大题", "做课后习题二次型",
)
xxds_deps["做2022-2023线性代数真题全卷（限时）"] = dep("做2021-2022线性代数真题全卷（限时）")
xxds_deps["做2023-2024线性代数真题全卷（限时）"] = dep("做2022-2023线性代数真题全卷（限时）")
xxds_deps["做2024-2025线性代数真题全卷（限时）"] = dep("做2023-2024线性代数真题全卷（限时）")
xxds_deps["整理线代错题并重做"] = dep("做2024-2025线性代数真题全卷（限时）")


# ==============================
# 五、大学英语Ⅱ | 考试：6月30日
# priority=5
# ==============================
eng2_tasks = [
    {"name": "做一篇英语Ⅱ听力对话", "estimated_time": 20, "repeat_type": "daily",
     "tags": ["英语", "大学英语", "英语Ⅱ", "听力"], "difficulty": 2, "priority": 5, "resistance": "low", "energy_required": "medium"},
    {"name": "做一篇英语Ⅱ阅读理解", "estimated_time": 25, "repeat_type": "daily",
     "tags": ["英语", "大学英语", "英语Ⅱ", "阅读"], "difficulty": 2, "priority": 5, "resistance": "low", "energy_required": "medium"},
    {"name": "背英语Ⅱ翻译常用句型", "estimated_time": 20, "repeat_type": "daily",
     "tags": ["英语", "大学英语", "英语Ⅱ", "翻译"], "difficulty": 1, "priority": 5, "resistance": "low", "energy_required": "low"},
    {"name": "写一篇英语Ⅱ应用文或议论文", "estimated_time": 35, "repeat_type": "weekly",
     "tags": ["英语", "大学英语", "英语Ⅱ", "写作"], "difficulty": 3, "priority": 5, "resistance": "medium", "energy_required": "high"},
]

eng2_deps = {}


# ==============================
# 六、高等数学 | 考试：7月8日
# priority=4
# ==============================
gs_tasks = []
gs_deps = {}

# 第7章 多元函数微分学
ch7_tasks = [
    ("复习笔记「07-01 多元函数的概念与极限」", ["高等数学", "高数", "多元微分", "复习"], 25),
    ("做习题册7.1节对应题", ["高等数学", "高数", "多元微分", "练习"], 30),
    ("做真题中7.1节同类题", ["高等数学", "高数", "多元微分", "真题"], 25),
    ("复习笔记「07-02 偏导数与全微分」", ["高等数学", "高数", "多元微分", "复习"], 30),
    ("做习题册7.2节对应题", ["高等数学", "高数", "多元微分", "练习"], 30),
    ("做真题中7.2节同类题", ["高等数学", "高数", "多元微分", "真题"], 25),
    ("复习笔记「07-03 多元复合函数求导法则」", ["高等数学", "高数", "多元微分", "复习"], 30),
    ("做习题册7.3节对应题", ["高等数学", "高数", "多元微分", "练习"], 30),
    ("做真题中7.3节同类题", ["高等数学", "高数", "多元微分", "真题"], 25),
    ("复习笔记「07-04 隐函数求导」", ["高等数学", "高数", "多元微分", "复习"], 30),
    ("做习题册7.4节对应题", ["高等数学", "高数", "多元微分", "练习"], 30),
    ("做真题中7.4节同类题", ["高等数学", "高数", "多元微分", "真题"], 25),
    ("复习笔记「07-05 隐函数组求导」", ["高等数学", "高数", "多元微分", "复习"], 30),
    ("做习题册7.5节对应题", ["高等数学", "高数", "多元微分", "练习"], 30),
    ("做真题中7.5节同类题", ["高等数学", "高数", "多元微分", "真题"], 25),
    ("复习笔记「07-06 多元函数的极值与条件极值」", ["高等数学", "高数", "多元微分", "复习"], 30),
    ("做习题册7.6节对应题", ["高等数学", "高数", "多元微分", "练习"], 30),
    ("做真题中7.6节同类题", ["高等数学", "高数", "多元微分", "真题"], 25),
    ("做第七章总习题", ["高等数学", "高数", "多元微分", "综合"], 45),
]

ch7_names = [t[0] for t in ch7_tasks]
for name, tags, etime in ch7_tasks:
    gs_tasks.append({
        "name": name, "estimated_time": etime, "repeat_type": "single",
        "tags": tags, "difficulty": 3 if "练习" in tags or "真题" in tags or "综合" in tags else 2,
        "priority": 4, "resistance": "high" if "练习" in tags or "真题" in tags or "综合" in tags else "medium",
        "energy_required": "high" if "练习" in tags or "真题" in tags or "综合" in tags else "medium",
    })

gs_deps["做习题册7.1节对应题"] = dep("复习笔记「07-01 多元函数的概念与极限」")
gs_deps["做真题中7.1节同类题"] = dep("复习笔记「07-01 多元函数的概念与极限」")
gs_deps["复习笔记「07-02 偏导数与全微分」"] = dep("复习笔记「07-01 多元函数的概念与极限」")
gs_deps["做习题册7.2节对应题"] = dep("复习笔记「07-02 偏导数与全微分」")
gs_deps["做真题中7.2节同类题"] = dep("复习笔记「07-02 偏导数与全微分」")
gs_deps["复习笔记「07-03 多元复合函数求导法则」"] = dep("复习笔记「07-02 偏导数与全微分」")
gs_deps["做习题册7.3节对应题"] = dep("复习笔记「07-03 多元复合函数求导法则」")
gs_deps["做真题中7.3节同类题"] = dep("复习笔记「07-03 多元复合函数求导法则」")
gs_deps["复习笔记「07-04 隐函数求导」"] = dep("复习笔记「07-03 多元复合函数求导法则」")
gs_deps["做习题册7.4节对应题"] = dep("复习笔记「07-04 隐函数求导」")
gs_deps["做真题中7.4节同类题"] = dep("复习笔记「07-04 隐函数求导」")
gs_deps["复习笔记「07-05 隐函数组求导」"] = dep("复习笔记「07-04 隐函数求导」")
gs_deps["做习题册7.5节对应题"] = dep("复习笔记「07-05 隐函数组求导」")
gs_deps["做真题中7.5节同类题"] = dep("复习笔记「07-05 隐函数组求导」")
gs_deps["复习笔记「07-06 多元函数的极值与条件极值」"] = dep("复习笔记「07-05 隐函数组求导」")
gs_deps["做习题册7.6节对应题"] = dep("复习笔记「07-06 多元函数的极值与条件极值」")
gs_deps["做真题中7.6节同类题"] = dep("复习笔记「07-06 多元函数的极值与条件极值」")
gs_deps["做第七章总习题"] = dep(
    "做习题册7.1节对应题", "做真题中7.1节同类题",
    "做习题册7.2节对应题", "做真题中7.2节同类题",
    "做习题册7.3节对应题", "做真题中7.3节同类题",
    "做习题册7.4节对应题", "做真题中7.4节同类题",
    "做习题册7.5节对应题", "做真题中7.5节同类题",
    "做习题册7.6节对应题", "做真题中7.6节同类题",
)

# 第8章 重积分
ch8_tasks = [
    ("复习笔记「08-01 二重积分的概念与性质」", ["高等数学", "高数", "重积分", "复习"], 30),
    ("做习题册8.1节对应题", ["高等数学", "高数", "重积分", "练习"], 30),
    ("做真题中8.1节同类题", ["高等数学", "高数", "重积分", "真题"], 25),
    ("复习笔记「08-02 二重积分的计算方法」", ["高等数学", "高数", "重积分", "复习"], 30),
    ("做习题册8.2节对应题", ["高等数学", "高数", "重积分", "练习"], 35),
    ("做真题中8.2节同类题", ["高等数学", "高数", "重积分", "真题"], 25),
    ("做第八章总习题", ["高等数学", "高数", "重积分", "综合"], 45),
]

for name, tags, etime in ch8_tasks:
    gs_tasks.append({
        "name": name, "estimated_time": etime, "repeat_type": "single",
        "tags": tags, "difficulty": 3 if ("练习" in tags or "真题" in tags or "综合" in tags) else 2,
        "priority": 4, "resistance": "high" if ("练习" in tags or "真题" in tags or "综合" in tags) else "medium",
        "energy_required": "high" if ("练习" in tags or "真题" in tags or "综合" in tags) else "medium",
    })

gs_deps["复习笔记「08-01 二重积分的概念与性质」"] = dep("做第七章总习题")
gs_deps["做习题册8.1节对应题"] = dep("复习笔记「08-01 二重积分的概念与性质」")
gs_deps["做真题中8.1节同类题"] = dep("复习笔记「08-01 二重积分的概念与性质」")
gs_deps["复习笔记「08-02 二重积分的计算方法」"] = dep("复习笔记「08-01 二重积分的概念与性质」")
gs_deps["做习题册8.2节对应题"] = dep("复习笔记「08-02 二重积分的计算方法」")
gs_deps["做真题中8.2节同类题"] = dep("复习笔记「08-02 二重积分的计算方法」")
gs_deps["做第八章总习题"] = dep("做习题册8.1节对应题", "做真题中8.1节同类题", "做习题册8.2节对应题", "做真题中8.2节同类题")

# 第9章 曲线积分
ch9_tasks = [
    ("复习笔记「09-01 对弧长的曲线积分」", ["高等数学", "高数", "曲线积分", "复习"], 30),
    ("做习题册9.1节对应题", ["高等数学", "高数", "曲线积分", "练习"], 30),
    ("做真题中9.1节同类题", ["高等数学", "高数", "曲线积分", "真题"], 25),
    ("复习笔记「09-02 格林公式及其应用」", ["高等数学", "高数", "曲线积分", "格林公式", "复习"], 30),
    ("做习题册9.2节对应题", ["高等数学", "高数", "曲线积分", "格林公式", "练习"], 35),
    ("做真题中9.2节同类题", ["高等数学", "高数", "曲线积分", "格林公式", "真题"], 25),
    ("做第九章总习题", ["高等数学", "高数", "曲线积分", "综合"], 45),
]

for name, tags, etime in ch9_tasks:
    gs_tasks.append({
        "name": name, "estimated_time": etime, "repeat_type": "single",
        "tags": tags, "difficulty": 3 if ("练习" in tags or "真题" in tags or "综合" in tags) else 2,
        "priority": 4, "resistance": "high" if ("练习" in tags or "真题" in tags or "综合" in tags) else "medium",
        "energy_required": "high" if ("练习" in tags or "真题" in tags or "综合" in tags) else "medium",
    })

gs_deps["复习笔记「09-01 对弧长的曲线积分」"] = dep("做第八章总习题")
gs_deps["做习题册9.1节对应题"] = dep("复习笔记「09-01 对弧长的曲线积分」")
gs_deps["做真题中9.1节同类题"] = dep("复习笔记「09-01 对弧长的曲线积分」")
gs_deps["复习笔记「09-02 格林公式及其应用」"] = dep("复习笔记「09-01 对弧长的曲线积分」")
gs_deps["做习题册9.2节对应题"] = dep("复习笔记「09-02 格林公式及其应用」")
gs_deps["做真题中9.2节同类题"] = dep("复习笔记「09-02 格林公式及其应用」")
gs_deps["做第九章总习题"] = dep("做习题册9.1节对应题", "做真题中9.1节同类题", "做习题册9.2节对应题", "做真题中9.2节同类题")

# 第10章 无穷级数
ch10_tasks = [
    ("复习笔记「10-01 常数项级数的概念与性质」", ["高等数学", "高数", "无穷级数", "复习"], 30),
    ("做习题册10.1节对应题", ["高等数学", "高数", "无穷级数", "练习"], 30),
    ("做真题中10.1节同类题", ["高等数学", "高数", "无穷级数", "真题"], 25),
    ("复习笔记「10-02 正项级数的判别法」", ["高等数学", "高数", "无穷级数", "复习"], 30),
    ("做习题册10.2节对应题", ["高等数学", "高数", "无穷级数", "练习"], 35),
    ("做真题中10.2节同类题", ["高等数学", "高数", "无穷级数", "真题"], 25),
    ("复习笔记「10-03 幂级数的收敛半径与收敛域」", ["高等数学", "高数", "无穷级数", "幂级数", "复习"], 30),
    ("做习题册10.3节对应题", ["高等数学", "高数", "无穷级数", "幂级数", "练习"], 30),
    ("做真题中10.3节同类题", ["高等数学", "高数", "无穷级数", "幂级数", "真题"], 25),
    ("复习笔记「10-04 幂级数的和函数」", ["高等数学", "高数", "无穷级数", "幂级数", "复习"], 30),
    ("做习题册10.4节对应题", ["高等数学", "高数", "无穷级数", "幂级数", "练习"], 35),
    ("做真题中10.4节同类题", ["高等数学", "高数", "无穷级数", "幂级数", "真题"], 25),
    ("复习笔记「10-05 泰勒级数与函数展开」", ["高等数学", "高数", "无穷级数", "泰勒级数", "复习"], 30),
    ("做习题册10.5节对应题", ["高等数学", "高数", "无穷级数", "泰勒级数", "练习"], 30),
    ("做真题中10.5节同类题", ["高等数学", "高数", "无穷级数", "泰勒级数", "真题"], 25),
    ("复习笔记「10-06 函数展开成幂级数的方法」", ["高等数学", "高数", "无穷级数", "幂级数", "复习"], 30),
    ("做习题册10.6节对应题", ["高等数学", "高数", "无穷级数", "幂级数", "练习"], 30),
    ("做真题中10.6节同类题", ["高等数学", "高数", "无穷级数", "幂级数", "真题"], 25),
    ("做第十章总习题", ["高等数学", "高数", "无穷级数", "综合"], 45),
]

for name, tags, etime in ch10_tasks:
    gs_tasks.append({
        "name": name, "estimated_time": etime, "repeat_type": "single",
        "tags": tags, "difficulty": 3 if ("练习" in tags or "真题" in tags or "综合" in tags) else 2,
        "priority": 4, "resistance": "high" if ("练习" in tags or "真题" in tags or "综合" in tags) else "medium",
        "energy_required": "high" if ("练习" in tags or "真题" in tags or "综合" in tags) else "medium",
    })

gs_deps["复习笔记「10-01 常数项级数的概念与性质」"] = dep("做第九章总习题")
gs_deps["做习题册10.1节对应题"] = dep("复习笔记「10-01 常数项级数的概念与性质」")
gs_deps["做真题中10.1节同类题"] = dep("复习笔记「10-01 常数项级数的概念与性质」")
gs_deps["复习笔记「10-02 正项级数的判别法」"] = dep("复习笔记「10-01 常数项级数的概念与性质」")
gs_deps["做习题册10.2节对应题"] = dep("复习笔记「10-02 正项级数的判别法」")
gs_deps["做真题中10.2节同类题"] = dep("复习笔记「10-02 正项级数的判别法」")
gs_deps["复习笔记「10-03 幂级数的收敛半径与收敛域」"] = dep("复习笔记「10-02 正项级数的判别法」")
gs_deps["做习题册10.3节对应题"] = dep("复习笔记「10-03 幂级数的收敛半径与收敛域」")
gs_deps["做真题中10.3节同类题"] = dep("复习笔记「10-03 幂级数的收敛半径与收敛域」")
gs_deps["复习笔记「10-04 幂级数的和函数」"] = dep("复习笔记「10-03 幂级数的收敛半径与收敛域」")
gs_deps["做习题册10.4节对应题"] = dep("复习笔记「10-04 幂级数的和函数」")
gs_deps["做真题中10.4节同类题"] = dep("复习笔记「10-04 幂级数的和函数」")
gs_deps["复习笔记「10-05 泰勒级数与函数展开」"] = dep("复习笔记「10-04 幂级数的和函数」")
gs_deps["做习题册10.5节对应题"] = dep("复习笔记「10-05 泰勒级数与函数展开」")
gs_deps["做真题中10.5节同类题"] = dep("复习笔记「10-05 泰勒级数与函数展开」")
gs_deps["复习笔记「10-06 函数展开成幂级数的方法」"] = dep("复习笔记「10-05 泰勒级数与函数展开」")
gs_deps["做习题册10.6节对应题"] = dep("复习笔记「10-06 函数展开成幂级数的方法」")
gs_deps["做真题中10.6节同类题"] = dep("复习笔记「10-06 函数展开成幂级数的方法」")
gs_deps["做第十章总习题"] = dep(
    "做习题册10.1节对应题", "做真题中10.1节同类题",
    "做习题册10.2节对应题", "做真题中10.2节同类题",
    "做习题册10.3节对应题", "做真题中10.3节同类题",
    "做习题册10.4节对应题", "做真题中10.4节同类题",
    "做习题册10.5节对应题", "做真题中10.5节同类题",
    "做习题册10.6节对应题", "做真题中10.6节同类题",
)

# 第11章 微分方程
ch11_tasks = [
    ("复习笔记「11-01 微分方程的概念与分类」", ["高等数学", "高数", "微分方程", "复习"], 30),
    ("做习题册11.1节对应题", ["高等数学", "高数", "微分方程", "练习"], 30),
    ("做真题中11.1节同类题", ["高等数学", "高数", "微分方程", "真题"], 25),
    ("复习笔记「11-02 一阶微分方程——变量分离与齐次方程」", ["高等数学", "高数", "微分方程", "复习"], 30),
    ("做习题册11.2节对应题", ["高等数学", "高数", "微分方程", "练习"], 35),
    ("做真题中11.2节同类题", ["高等数学", "高数", "微分方程", "真题"], 25),
    ("复习笔记「11-03 一阶线性微分方程与常数变易法」", ["高等数学", "高数", "微分方程", "复习"], 30),
    ("做习题册11.3节对应题", ["高等数学", "高数", "微分方程", "练习"], 35),
    ("做真题中11.3节同类题", ["高等数学", "高数", "微分方程", "真题"], 25),
    ("复习笔记「11-04 全微分方程判定与求解」", ["高等数学", "高数", "微分方程", "复习"], 30),
    ("做习题册11.4节对应题", ["高等数学", "高数", "微分方程", "练习"], 30),
    ("做真题中11.4节同类题", ["高等数学", "高数", "微分方程", "真题"], 25),
    ("复习笔记「11-05 二阶微分方程降阶法」", ["高等数学", "高数", "微分方程", "复习"], 30),
    ("做习题册11.5节对应题", ["高等数学", "高数", "微分方程", "练习"], 35),
    ("做真题中11.5节同类题", ["高等数学", "高数", "微分方程", "真题"], 25),
    ("复习笔记「11-06 常系数微分方程解法」", ["高等数学", "高数", "微分方程", "复习"], 30),
    ("做习题册11.6节对应题", ["高等数学", "高数", "微分方程", "练习"], 35),
    ("做真题中11.6节同类题", ["高等数学", "高数", "微分方程", "真题"], 25),
    ("复习笔记「11-07 高阶线性微分方程解的结构」", ["高等数学", "高数", "微分方程", "复习"], 30),
    ("做习题册11.7节对应题", ["高等数学", "高数", "微分方程", "练习"], 30),
    ("做真题中11.7节同类题", ["高等数学", "高数", "微分方程", "真题"], 25),
    ("做第十一章总习题", ["高等数学", "高数", "微分方程", "综合"], 45),
]

for name, tags, etime in ch11_tasks:
    gs_tasks.append({
        "name": name, "estimated_time": etime, "repeat_type": "single",
        "tags": tags, "difficulty": 3 if ("练习" in tags or "真题" in tags or "综合" in tags) else 2,
        "priority": 4, "resistance": "high" if ("练习" in tags or "真题" in tags or "综合" in tags) else "medium",
        "energy_required": "high" if ("练习" in tags or "真题" in tags or "综合" in tags) else "medium",
    })

gs_deps["复习笔记「11-01 微分方程的概念与分类」"] = dep("做第十章总习题")
gs_deps["做习题册11.1节对应题"] = dep("复习笔记「11-01 微分方程的概念与分类」")
gs_deps["做真题中11.1节同类题"] = dep("复习笔记「11-01 微分方程的概念与分类」")
gs_deps["复习笔记「11-02 一阶微分方程——变量分离与齐次方程」"] = dep("复习笔记「11-01 微分方程的概念与分类」")
gs_deps["做习题册11.2节对应题"] = dep("复习笔记「11-02 一阶微分方程——变量分离与齐次方程」")
gs_deps["做真题中11.2节同类题"] = dep("复习笔记「11-02 一阶微分方程——变量分离与齐次方程」")
gs_deps["复习笔记「11-03 一阶线性微分方程与常数变易法」"] = dep("复习笔记「11-02 一阶微分方程——变量分离与齐次方程」")
gs_deps["做习题册11.3节对应题"] = dep("复习笔记「11-03 一阶线性微分方程与常数变易法」")
gs_deps["做真题中11.3节同类题"] = dep("复习笔记「11-03 一阶线性微分方程与常数变易法」")
gs_deps["复习笔记「11-04 全微分方程判定与求解」"] = dep("复习笔记「11-03 一阶线性微分方程与常数变易法」")
gs_deps["做习题册11.4节对应题"] = dep("复习笔记「11-04 全微分方程判定与求解」")
gs_deps["做真题中11.4节同类题"] = dep("复习笔记「11-04 全微分方程判定与求解」")
gs_deps["复习笔记「11-05 二阶微分方程降阶法」"] = dep("复习笔记「11-04 全微分方程判定与求解」")
gs_deps["做习题册11.5节对应题"] = dep("复习笔记「11-05 二阶微分方程降阶法」")
gs_deps["做真题中11.5节同类题"] = dep("复习笔记「11-05 二阶微分方程降阶法」")
gs_deps["复习笔记「11-06 常系数微分方程解法」"] = dep("复习笔记「11-05 二阶微分方程降阶法」")
gs_deps["做习题册11.6节对应题"] = dep("复习笔记「11-06 常系数微分方程解法」")
gs_deps["做真题中11.6节同类题"] = dep("复习笔记「11-06 常系数微分方程解法」")
gs_deps["复习笔记「11-07 高阶线性微分方程解的结构」"] = dep("复习笔记「11-06 常系数微分方程解法」")
gs_deps["做习题册11.7节对应题"] = dep("复习笔记「11-07 高阶线性微分方程解的结构」")
gs_deps["做真题中11.7节同类题"] = dep("复习笔记「11-07 高阶线性微分方程解的结构」")
gs_deps["做第十一章总习题"] = dep(
    "做习题册11.1节对应题", "做真题中11.1节同类题",
    "做习题册11.2节对应题", "做真题中11.2节同类题",
    "做习题册11.3节对应题", "做真题中11.3节同类题",
    "做习题册11.4节对应题", "做真题中11.4节同类题",
    "做习题册11.5节对应题", "做真题中11.5节同类题",
    "做习题册11.6节对应题", "做真题中11.6节同类题",
    "做习题册11.7节对应题", "做真题中11.7节同类题",
)

# 高数综合真题卷
gs_tasks.append({"name": "做2023年高数真题全卷（限时）", "estimated_time": 120, "repeat_type": "single",
    "tags": ["高等数学", "高数", "真题", "模拟"], "difficulty": 4, "priority": 4, "resistance": "high", "energy_required": "high"})
gs_tasks.append({"name": "做2024年高数真题全卷（限时）", "estimated_time": 120, "repeat_type": "single",
    "tags": ["高等数学", "高数", "真题", "模拟"], "difficulty": 4, "priority": 4, "resistance": "high", "energy_required": "high"})
gs_tasks.append({"name": "做2025年高数真题全卷（限时）", "estimated_time": 120, "repeat_type": "single",
    "tags": ["高等数学", "高数", "真题", "模拟"], "difficulty": 4, "priority": 4, "resistance": "high", "energy_required": "high"})
gs_tasks.append({"name": "整理高数错题并重做", "estimated_time": 50, "repeat_type": "single",
    "tags": ["高等数学", "高数", "错题", "整理"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "medium"})

gs_deps["做2023年高数真题全卷（限时）"] = dep(
    "做第七章总习题", "做第八章总习题", "做第九章总习题", "做第十章总习题", "做第十一章总习题")
gs_deps["做2024年高数真题全卷（限时）"] = dep("做2023年高数真题全卷（限时）")
gs_deps["做2025年高数真题全卷（限时）"] = dep("做2024年高数真题全卷（限时）")
gs_deps["整理高数错题并重做"] = dep("做2025年高数真题全卷（限时）")


# ==============================
# 七、大学物理 | 考试：7月9日
# priority=4
# ==============================
dxwl_tasks = [
    # 模块1 静电场与质点运动学
    {"name": "复习笔记「01静电场与电场强度」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "静电场", "复习"], "difficulty": 2, "priority": 4, "resistance": "medium", "energy_required": "medium"},
    {"name": "做复习题库静电场选择题+填空题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "静电场", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「02质点运动学两类问题与例题」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "质点运动学", "复习"], "difficulty": 2, "priority": 4, "resistance": "medium", "energy_required": "medium"},
    {"name": "做复习题库力学选择题+填空题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "力学", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「03电通量与高斯定理」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "电通量", "高斯定理", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库电通量/高斯定理题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "电通量", "高斯定理", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「03自然坐标系与加速度分解」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["大学物理", "大物", "自然坐标系", "复习"], "difficulty": 2, "priority": 4, "resistance": "medium", "energy_required": "medium"},
    {"name": "做复习题库自然坐标系与加速度题", "estimated_time": 25, "repeat_type": "single",
     "tags": ["大学物理", "大物", "自然坐标系", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「04圆周运动的角量与线量」", "estimated_time": 25, "repeat_type": "single",
     "tags": ["大学物理", "大物", "圆周运动", "复习"], "difficulty": 2, "priority": 4, "resistance": "medium", "energy_required": "medium"},
    {"name": "做复习题库圆周运动题", "estimated_time": 25, "repeat_type": "single",
     "tags": ["大学物理", "大物", "圆周运动", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},

    # 模块2 动力学与动量
    {"name": "复习笔记「05动力学解题思路与受力分析」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "动力学", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库动力学分析题", "estimated_time": 35, "repeat_type": "single",
     "tags": ["大学物理", "大物", "动力学", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「06动量定理与解题步骤」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "动量", "复习"], "difficulty": 2, "priority": 4, "resistance": "medium", "energy_required": "medium"},
    {"name": "做复习题库动量定理题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "动量", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},

    # 模块3 刚体与振动
    {"name": "复习笔记「07刚体模型与定轴转动运动学」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "刚体", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库刚体运动学题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "刚体", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「08刚体定轴转动定律与转动惯量」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "刚体", "转动惯量", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库转动定律与转动惯量题", "estimated_time": 35, "repeat_type": "single",
     "tags": ["大学物理", "大物", "刚体", "转动惯量", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「09角动量定理与守恒定律」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "角动量", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库角动量定理与守恒题", "estimated_time": 35, "repeat_type": "single",
     "tags": ["大学物理", "大物", "角动量", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「10三大守恒律复习与简谐振动入门」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "守恒律", "复习"], "difficulty": 2, "priority": 4, "resistance": "medium", "energy_required": "medium"},
    {"name": "做复习题库三大守恒律+简谐振动题", "estimated_time": 35, "repeat_type": "single",
     "tags": ["大学物理", "大物", "守恒律", "简谐振动", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「11旋转矢量法与简谐振动描述」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "简谐振动", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库旋转矢量与简谐振动题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "简谐振动", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},

    # 模块4 波动
    {"name": "复习笔记「12机械波与波函数概述」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "机械波", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库机械波选择题+填空题", "estimated_time": 25, "repeat_type": "single",
     "tags": ["大学物理", "大物", "机械波", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「13波动方程与相位分析」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "波动方程", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库波动方程与相位题", "estimated_time": 35, "repeat_type": "single",
     "tags": ["大学物理", "大物", "波动方程", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},

    # 模块5 热力学
    {"name": "复习笔记「14气体动理论基础」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "热力学", "气体动理论", "复习"], "difficulty": 2, "priority": 4, "resistance": "medium", "energy_required": "medium"},
    {"name": "做复习题库气体动理论选择题+填空题", "estimated_time": 25, "repeat_type": "single",
     "tags": ["大学物理", "大物", "热力学", "气体动理论", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「15分子自由度与速率分布」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "热力学", "速率分布", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库自由度与速率分布题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "热力学", "速率分布", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「16热力学第一定律与四大过程」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "热力学", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库热力学第一定律与过程题", "estimated_time": 35, "repeat_type": "single",
     "tags": ["大学物理", "大物", "热力学", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「17热力学循环与效率计算」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "热力学", "循环", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库热力学循环与效率题", "estimated_time": 35, "repeat_type": "single",
     "tags": ["大学物理", "大物", "热力学", "循环", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},

    # 模块6 光学
    {"name": "复习笔记「18光的干涉原理与两类装置」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "光学", "干涉", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库光的干涉选择题+填空题", "estimated_time": 25, "repeat_type": "single",
     "tags": ["大学物理", "大物", "光学", "干涉", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「19_半波损失的原理与判断」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "光学", "半波损失", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库半波损失判断题", "estimated_time": 25, "repeat_type": "single",
     "tags": ["大学物理", "大物", "光学", "半波损失", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「20惠更斯-菲涅耳原理与衍射分类」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "光学", "衍射", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库衍射原理题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "光学", "衍射", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "复习笔记「21圆孔衍射与光学仪器分辨本领」", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "光学", "圆孔衍射", "复习"], "difficulty": 3, "priority": 4, "resistance": "medium", "energy_required": "high"},
    {"name": "做复习题库圆孔衍射与分辨本领题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "光学", "圆孔衍射", "练习"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},

    # 作业原题专项
    {"name": "重做波动光学作业原题（杨氏双缝、单缝衍射）", "estimated_time": 35, "repeat_type": "single",
     "tags": ["大学物理", "大物", "光学", "作业原题"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "重做刚体力学作业原题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "刚体", "作业原题"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},
    {"name": "重做热力学作业原题", "estimated_time": 30, "repeat_type": "single",
     "tags": ["大学物理", "大物", "热力学", "作业原题"], "difficulty": 3, "priority": 4, "resistance": "high", "energy_required": "high"},

    # 选择题专项
    {"name": "刷复习题库所有选择题", "estimated_time": 30, "repeat_type": "daily",
     "tags": ["大学物理", "大物", "选择题", "每日"], "difficulty": 2, "priority": 4, "resistance": "low", "energy_required": "medium"},

    # 综合
    {"name": "做大学物理综合复习题", "estimated_time": 60, "repeat_type": "single",
     "tags": ["大学物理", "大物", "综合", "复习"], "difficulty": 4, "priority": 4, "resistance": "high", "energy_required": "high"},
]

dxwl_deps = {}
# 模块1
dxwl_deps["做复习题库静电场选择题+填空题"] = dep("复习笔记「01静电场与电场强度」")
dxwl_deps["复习笔记「02质点运动学两类问题与例题」"] = dep("复习笔记「01静电场与电场强度」")
dxwl_deps["做复习题库力学选择题+填空题"] = dep("复习笔记「02质点运动学两类问题与例题」")
dxwl_deps["复习笔记「03电通量与高斯定理」"] = dep("复习笔记「02质点运动学两类问题与例题」")
dxwl_deps["做复习题库电通量/高斯定理题"] = dep("复习笔记「03电通量与高斯定理」")
dxwl_deps["复习笔记「03自然坐标系与加速度分解」"] = dep("复习笔记「03电通量与高斯定理」")
dxwl_deps["做复习题库自然坐标系与加速度题"] = dep("复习笔记「03自然坐标系与加速度分解」")
dxwl_deps["复习笔记「04圆周运动的角量与线量」"] = dep("复习笔记「03自然坐标系与加速度分解」")
dxwl_deps["做复习题库圆周运动题"] = dep("复习笔记「04圆周运动的角量与线量」")
# 模块2
dxwl_deps["复习笔记「05动力学解题思路与受力分析」"] = dep("复习笔记「04圆周运动的角量与线量」")
dxwl_deps["做复习题库动力学分析题"] = dep("复习笔记「05动力学解题思路与受力分析」")
dxwl_deps["复习笔记「06动量定理与解题步骤」"] = dep("复习笔记「05动力学解题思路与受力分析」")
dxwl_deps["做复习题库动量定理题"] = dep("复习笔记「06动量定理与解题步骤」")
# 模块3
dxwl_deps["复习笔记「07刚体模型与定轴转动运动学」"] = dep("复习笔记「06动量定理与解题步骤」")
dxwl_deps["做复习题库刚体运动学题"] = dep("复习笔记「07刚体模型与定轴转动运动学」")
dxwl_deps["复习笔记「08刚体定轴转动定律与转动惯量」"] = dep("复习笔记「07刚体模型与定轴转动运动学」")
dxwl_deps["做复习题库转动定律与转动惯量题"] = dep("复习笔记「08刚体定轴转动定律与转动惯量」")
dxwl_deps["复习笔记「09角动量定理与守恒定律」"] = dep("复习笔记「08刚体定轴转动定律与转动惯量」")
dxwl_deps["做复习题库角动量定理与守恒题"] = dep("复习笔记「09角动量定理与守恒定律」")
dxwl_deps["复习笔记「10三大守恒律复习与简谐振动入门」"] = dep("复习笔记「09角动量定理与守恒定律」")
dxwl_deps["做复习题库三大守恒律+简谐振动题"] = dep("复习笔记「10三大守恒律复习与简谐振动入门」")
dxwl_deps["复习笔记「11旋转矢量法与简谐振动描述」"] = dep("复习笔记「10三大守恒律复习与简谐振动入门」")
dxwl_deps["做复习题库旋转矢量与简谐振动题"] = dep("复习笔记「11旋转矢量法与简谐振动描述」")
# 模块4
dxwl_deps["复习笔记「12机械波与波函数概述」"] = dep("复习笔记「11旋转矢量法与简谐振动描述」")
dxwl_deps["做复习题库机械波选择题+填空题"] = dep("复习笔记「12机械波与波函数概述」")
dxwl_deps["复习笔记「13波动方程与相位分析」"] = dep("复习笔记「12机械波与波函数概述」")
dxwl_deps["做复习题库波动方程与相位题"] = dep("复习笔记「13波动方程与相位分析」")
# 模块5
dxwl_deps["复习笔记「14气体动理论基础」"] = dep("复习笔记「13波动方程与相位分析」")
dxwl_deps["做复习题库气体动理论选择题+填空题"] = dep("复习笔记「14气体动理论基础」")
dxwl_deps["复习笔记「15分子自由度与速率分布」"] = dep("复习笔记「14气体动理论基础」")
dxwl_deps["做复习题库自由度与速率分布题"] = dep("复习笔记「15分子自由度与速率分布」")
dxwl_deps["复习笔记「16热力学第一定律与四大过程」"] = dep("复习笔记「15分子自由度与速率分布」")
dxwl_deps["做复习题库热力学第一定律与过程题"] = dep("复习笔记「16热力学第一定律与四大过程」")
dxwl_deps["复习笔记「17热力学循环与效率计算」"] = dep("复习笔记「16热力学第一定律与四大过程」")
dxwl_deps["做复习题库热力学循环与效率题"] = dep("复习笔记「17热力学循环与效率计算」")
# 模块6
dxwl_deps["复习笔记「18光的干涉原理与两类装置」"] = dep("复习笔记「17热力学循环与效率计算」")
dxwl_deps["做复习题库光的干涉选择题+填空题"] = dep("复习笔记「18光的干涉原理与两类装置」")
dxwl_deps["复习笔记「19_半波损失的原理与判断」"] = dep("复习笔记「18光的干涉原理与两类装置」")
dxwl_deps["做复习题库半波损失判断题"] = dep("复习笔记「19_半波损失的原理与判断」")
dxwl_deps["复习笔记「20惠更斯-菲涅耳原理与衍射分类」"] = dep("复习笔记「19_半波损失的原理与判断」")
dxwl_deps["做复习题库衍射原理题"] = dep("复习笔记「20惠更斯-菲涅耳原理与衍射分类」")
dxwl_deps["复习笔记「21圆孔衍射与光学仪器分辨本领」"] = dep("复习笔记「20惠更斯-菲涅耳原理与衍射分类」")
dxwl_deps["做复习题库圆孔衍射与分辨本领题"] = dep("复习笔记「21圆孔衍射与光学仪器分辨本领」")
# 作业原题
dxwl_deps["重做波动光学作业原题（杨氏双缝、单缝衍射）"] = dep(
    "做复习题库光的干涉选择题+填空题", "做复习题库衍射原理题")
dxwl_deps["重做刚体力学作业原题"] = dep(
    "复习笔记「08刚体定轴转动定律与转动惯量」", "做复习题库转动定律与转动惯量题")
dxwl_deps["重做热力学作业原题"] = dep(
    "做复习题库热力学第一定律与过程题", "做复习题库热力学循环与效率题")
# 综合
dxwl_deps["做大学物理综合复习题"] = dep(
    "做复习题库静电场选择题+填空题", "做复习题库力学选择题+填空题",
    "做复习题库电通量/高斯定理题", "做复习题库自然坐标系与加速度题",
    "做复习题库圆周运动题", "做复习题库动力学分析题",
    "做复习题库动量定理题", "做复习题库刚体运动学题",
    "做复习题库转动定律与转动惯量题", "做复习题库角动量定理与守恒题",
    "做复习题库三大守恒律+简谐振动题", "做复习题库旋转矢量与简谐振动题",
    "做复习题库机械波选择题+填空题", "做复习题库波动方程与相位题",
    "做复习题库气体动理论选择题+填空题", "做复习题库自由度与速率分布题",
    "做复习题库热力学第一定律与过程题", "做复习题库热力学循环与效率题",
    "做复习题库光的干涉选择题+填空题", "做复习题库半波损失判断题",
    "做复习题库衍射原理题", "做复习题库圆孔衍射与分辨本领题",
    "重做波动光学作业原题（杨氏双缝、单缝衍射）", "重做刚体力学作业原题",
    "重做热力学作业原题",
)


# ==============================
# 组装并输出 JSON
# ==============================
def build_tasks(task_list, deps_map):
    """将任务列表和依赖映射组装为带 prerequisite_ids 的任务列表"""
    result = []
    for t in task_list:
        entry = dict(t)
        name = entry["name"]
        entry["prerequisite_ids"] = deps_map.get(name, [])
        result.append(entry)
    return result


all_tasks = (
    build_tasks(cet4_tasks, cet4_deps) +
    build_tasks(dzjs_tasks, dzjs_deps) +
    build_tasks(jsj_tasks, jsj_deps) +
    build_tasks(xxds_tasks, xxds_deps) +
    build_tasks(eng2_tasks, eng2_deps) +
    build_tasks(gs_tasks, gs_deps) +
    build_tasks(dxwl_tasks, dxwl_deps)
)

output = {
    "action": "batch_tasks",
    "tasks": all_tasks,
    "explanation": f"已创建 {len(all_tasks)} 个期末复习任务，涵盖 CET-4(6/13)、电子技术(6/18)、计算机(6/25)、线性代数(6/29)、英语Ⅱ(6/30)、高等数学(7/8)、大学物理(7/9)"
}

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"ai_output_{timestamp}.json"
filepath = os.path.join(OUTPUT_DIR, filename)

with open(filepath, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"已生成: {filepath}")
print(f"任务总数: {len(all_tasks)}")

# 统计各科目
from collections import Counter
cats = Counter()
for t in all_tasks:
    for tag in t["tags"]:
        if tag in ("英语", "四级", "电子技术", "计算机", "线性代数", "大学英语", "英语Ⅱ", "高等数学", "高数", "大学物理", "大物"):
            cats[tag] += 1
            break

# 更精确的统计
subjects = {}
for t in all_tasks:
    tags = t["tags"]
    if "四级" in tags:
        subj = "CET-4"
    elif "电子技术" in tags:
        subj = "电子技术"
    elif "计算机" in tags:
        subj = "计算机"
    elif "线性代数" in tags:
        subj = "线性代数"
    elif "英语Ⅱ" in tags:
        subj = "英语Ⅱ"
    elif "高数" in tags:
        subj = "高等数学"
    elif "大物" in tags:
        subj = "大学物理"
    else:
        subj = "其他"
    subjects[subj] = subjects.get(subj, 0) + 1

for k, v in subjects.items():
    print(f"  {k}: {v} 个任务")
