// shared/xss.js - XSS 转义工具（**兼容路径别名**）
//
// P1 切片 4：`escapeHtml` 的 **唯一实现** 已在 `static/core/ui/xss.js`。
// 本文件保留历史路径 `SAL.shared.xss`，但 **不再拥有** 任何实现 ——
// 它只委托到 `SAL.core.ui.xss`，避免第二份转义实现漂移。
//
// 新代码请直接用 `SAL.core.ui.escapeHtml(...)`。

(function () {
  function escapeHtml(s) {
    const xss = window.SAL && window.SAL.core && window.SAL.core.ui &&
      window.SAL.core.ui.xss;
    if (!xss || typeof xss.escapeHtml !== 'function') {
      throw new Error('[shared/xss] 缺少 SAL.core.ui.xss（core/ui/xss.js 必须先加载）');
    }
    return xss.escapeHtml(s);
  }

  function setText(el, value) {
    const xss = window.SAL && window.SAL.core && window.SAL.core.ui &&
      window.SAL.core.ui.xss;
    if (!xss || typeof xss.setText !== 'function') {
      throw new Error('[shared/xss] 缺少 SAL.core.ui.xss（core/ui/xss.js 必须先加载）');
    }
    return xss.setText(el, value);
  }

  window.SAL = window.SAL || {};
  window.SAL.shared = window.SAL.shared || {};
  window.SAL.shared.xss = { escapeHtml: escapeHtml, setText: setText };
})();
