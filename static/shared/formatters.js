// shared/formatters.js - 时间/日期格式化（**唯一实现**）
//
// AR03-P3-D（计划 §3.4）：把散落在 classic `static/app.js` 的格式化
// 收敛为 **唯一实现**，classic 层与 ESM 层都委托这里 → 消除重复实现。
//
// 唯一权威清单
// ------------
// | 函数 | 语义 | 原先位置 |
// |---|---|---|
// | `formatElapsedMs` | 毫秒 → `mm:ss`（计时面板） | app.js |
// | `formatDiscardTimestamp` | ISO → 本地绝对时间（弃牌列表） | app.js |
// | `todayDateStr` | 今天日期 `YYYY-MM-DD` | shared（本文件） |
// | `formatHHMM` | 当前时刻 `HH:MM` | shared（本文件） |
// | `formatRelativeTime` | ISO → 「N 秒前 / 分钟前 …」 | shared（本文件） |
// | `formatTimerMMSS` | 秒 → `mm:ss` | shared（本文件） |
//
// **命名冲突澄清**（重要）：迁移前 shared 曾有一个叫 `formatDiscardTime`
// 的「相对时间」函数，而 app.js 的 `formatDiscardTime` 是「绝对时间」
// —— 两者 **语义完全不同**，绝不能合并。为避免歧义，本文件把它们改名
// 为 `formatRelativeTime` / `formatDiscardTimestamp`，各自保持原语义。

(function () {
  function pad2(n) { return n < 10 ? '0' + n : '' + n; }

  function todayDateStr(d) {
    d = d || new Date();
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  }

  function formatHHMM(d) {
    d = d || new Date();
    return pad2(d.getHours()) + ':' + pad2(d.getMinutes());
  }

  /**
   * 毫秒 → `mm:ss`（**不** 限制小时数，超过 60 分钟继续累计）。
   * 与迁移前 app.js::formatElapsed 逐字等价。
   */
  function formatElapsedMs(ms) {
    var sec = Math.max(0, Math.floor(ms / 1000));
    var m = Math.floor(sec / 60);
    var s = sec % 60;
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }

  /**
   * ISO → **本地绝对时间**（弃牌列表显示）。
   * 与迁移前 app.js::formatDiscardTime 逐字等价。
   */
  function formatDiscardTimestamp(iso) {
    if (!iso) return '-';
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return iso.slice(0, 16).replace('T', ' ');
      return d.toLocaleString('zh-CN', { hour12: false });
    } catch (e) {
      return iso.slice(0, 16);
    }
  }

  /**
   * ISO → **相对时间**（「N 秒前 / N 分钟前 / N 小时前 / N 天前」）。
   * 与迁移前 shared::formatDiscardTime 逐字等价。
   */
  function formatRelativeTime(iso) {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      const now = new Date();
      const diff = (now - d) / 1000;
      if (diff < 60) return Math.floor(diff) + ' 秒前';
      if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前';
      if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前';
      return Math.floor(diff / 86400) + ' 天前';
    } catch (e) {
      return iso;
    }
  }

  function formatTimerMMSS(totalSeconds) {
    const sec = Math.max(0, Math.floor(totalSeconds || 0));
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return pad2(m) + ':' + pad2(s);
  }

  window.SAL = window.SAL || {};
  window.SAL.shared = window.SAL.shared || {};
  window.SAL.shared.formatters = {
    todayDateStr: todayDateStr,
    formatHHMM: formatHHMM,
    formatElapsedMs: formatElapsedMs,
    formatDiscardTimestamp: formatDiscardTimestamp,
    formatRelativeTime: formatRelativeTime,
    formatTimerMMSS: formatTimerMMSS
  };
})();
