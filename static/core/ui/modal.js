// core/ui/modal.js - 模态对话框工具（Phase 1 收紧版）
// 与 core/ui.js 的 showModal/closeModal 等价；新模块可独立 import。
(function () {
  function showModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('hidden');
  }
  function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('hidden');
  }
  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.ui = window.SAL.core.ui || {};
  window.SAL.core.ui.modal = { show: showModal, close: closeModal };
})();
