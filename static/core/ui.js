// core/ui.js - toast / modal / 共享 UI 工具（**委托**给 core/ui/*）
//
// P1 之前
// ---------
// 本文件 **自己实现** 了 ``toast`` / ``showModal`` / ``closeModal`` /
// ``escapeHtml``，而 ``core/ui/modal.js`` 与 ``core/ui/toast.js`` 里又各有一
// 份等价实现 —— 双份实现是双源漂移的温床。
//
// 现在
// ----
// 本文件 **不再拥有** 任何实现，只做 **委托**：
//   * ``toast``       → ``SAL.core.ui.toast.show``
//   * ``showModal``   → ``SAL.core.ui.modal.show``
//   * ``closeModal``  → ``SAL.core.ui.modal.close``
//   * ``escapeHtml``  → ``SAL.core.ui.xss.escapeHtml``（唯一转义实现）
//
// **加载顺序**（src/index.html）：``core/ui/xss.js`` → ``core/ui/modal.js``
// → ``core/ui/toast.js`` → 本文件。若委托目标缺失，**fail closed**：
// 抛错，**绝不**静默回落到第二份实现（那正是双源的来源）。
//
// ``escapeHtml`` 的唯一实现放在 ``core/ui/xss.js``：转义属于 **安全边界**，
// 必须有且只有一个实现点。``shared/xss.js`` 保留为兼容路径别名，指向同一
// 个实现。

(function () {
  function requireSub(path) {
    const ui = window.SAL && window.SAL.core && window.SAL.core.ui;
    let node = ui;
    const parts = path.split('.');
    for (let i = 0; i < parts.length; i += 1) {
      if (!node) break;
      node = node[parts[i]];
    }
    if (!node) {
      throw new Error('[core/ui] 缺少委托目标：SAL.core.ui.' + path);
    }
    return node;
  }

  function toast(msg, type) {
    return requireSub('toast.show')(msg, type);
  }

  function showModal(id) {
    return requireSub('modal.show')(id);
  }

  function closeModal(id) {
    return requireSub('modal.close')(id);
  }

  function escapeHtml(s) {
    return requireSub('xss.escapeHtml')(s);
  }

  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.ui = window.SAL.core.ui || {};

  // SAL.core.ui.toast 既是 **可调用** 的（历史形态：ui.toast(msg)），
  // 又保留 ``.show``（子模块形态）。两者指向 **同一个** 实现。
  const toastImpl = requireSub('toast');
  const toastFn = function (msg, type) { return toastImpl.show(msg, type); };
  toastFn.show = toastImpl.show;
  window.SAL.core.ui.toast = toastFn;

  window.SAL.core.ui.showModal = showModal;
  window.SAL.core.ui.closeModal = closeModal;
  window.SAL.core.ui.escapeHtml = escapeHtml;
})();
