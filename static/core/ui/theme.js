// core/ui/theme.js - 主题（Phase 1 收紧版）
// 与 core/theme.js 等价；本文件仅作为 ui/theme.js 别名（任务规格要求 ui/ 下）
(function () {
  // 重导出 core.theme（保持单权威）；新模块可走 core/ui/theme
  function get() {
    return window.SAL && window.SAL.core && window.SAL.core.theme
      ? window.SAL.core.theme.getTheme()
      : 'dark';
  }
  function set(name) {
    if (window.SAL && window.SAL.core && window.SAL.core.theme) {
      return window.SAL.core.theme.setTheme(name);
    }
    return name;
  }
  function toggle() {
    if (window.SAL && window.SAL.core && window.SAL.core.theme) {
      return window.SAL.core.theme.toggleTheme();
    }
    return 'dark';
  }
  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.ui = window.SAL.core.ui || {};
  window.SAL.core.ui.theme = { get: get, set: set, toggle: toggle };
})();
