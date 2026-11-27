# _pwsh.ps1 — Agent / 开发者统一的 PowerShell 7 调用入口
#
# 目的：
#   1) 把所有 .ps1 / 含中文的 PowerShell 调用统一走 PS7，避免 PS 5.1 中文编码静默失配
#   2) 在脚本入口强制设置 UTF-8 输入/输出，不用 .ps1 写 BOM、不用全 ASCII
#   3) 让 `Shell` 工具的内联命令无法绕开编码问题的场景，有一条"显式走 PS7"的路
#
# 用法（从任意父进程调用，推荐用绝对路径）：
#   & "D:\Axelit\software\PowerShell-7.6.5-win-x64\pwsh.exe" -NoProfile -File scripts/_pwsh.ps1 -Command '<内联命令>'
#   & pwsh -NoProfile -File scripts/_pwsh.ps1 -ScriptBlock { ... }
#
# 配套 AGENTS.md「协作防坑指令」第 9 条；2026-09-28 新增。

[CmdletBinding()]
param(
    [string]$Command = "",
    [scriptblock]$ScriptBlock = $null,
    [string[]]$Arguments = @()
)

# === UTF-8 环境预设（PS7 默认 UTF-8，但显式声明更稳） ===
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

# === 版本自检（失败即大声报错） ===
$expectedMajor = 7
$actualMajor = $PSVersionTable.PSVersion.Major
if ($actualMajor -ne $expectedMajor) {
    Write-Error "[_pwsh.ps1] Expected PowerShell $expectedMajor but got $actualMajor. Aborting." -ErrorAction Stop
}

# === 主体执行 ===
if ($ScriptBlock) {
    & $ScriptBlock @Arguments
} elseif ($Command) {
    # 直接 & 执行比 Invoke-Expression 更稳，避免 + 链表达式被 IE 二次解析
    $sb = [scriptblock]::Create($Command)
    & $sb @Arguments
} else {
    Write-Error "[_pwsh.ps1] No -Command or -ScriptBlock given. Nothing to do." -ErrorAction Stop
}
