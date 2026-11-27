// core/ui/xss.js - HTML 转义的 **唯一实现**（P1 切片 4）
//
// P1 之前：`static/core/ui.js` 与 `static/shared/xss.js` 各有一份
// ``escapeHtml``（后者还要回落到第三份内联实现）。转义属于 **安全边界**，
// 重复实现 = 漂移风险。
//
// 现在：本文件是 **唯一** 实现点。
//   * `static/core/ui.js` 委托到这里；
//   * `static/shared/xss.js` 是兼容路径别名，指向同一个实现。

(function () {
  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function setText(el, value) {
    if (!el) return;
    el.textContent = value == null ? '' : String(value);
  }

  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.ui = window.SAL.core.ui || {};
  window.SAL.core.ui.xss = { escapeHtml: escapeHtml, setText: setText };
})();
