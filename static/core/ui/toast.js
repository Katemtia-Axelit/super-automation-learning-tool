// core/ui/toast.js - 轻量提示（Phase 1 收紧版）
// 与 core/ui.js 的 toast 等价；新模块可独立 import。
(function () {
  function toast(msg, type) {
    type = type || 'inf';
    const c = document.getElementById('toastContainer');
    if (!c) return;
    const d = document.createElement('div');
    d.className = 'toast ' + type;
    d.textContent = msg;
    c.appendChild(d);
    setTimeout(function () { d.remove(); }, 3500);
  }
  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.ui = window.SAL.core.ui || {};
  window.SAL.core.ui.toast = { show: toast };
})();
