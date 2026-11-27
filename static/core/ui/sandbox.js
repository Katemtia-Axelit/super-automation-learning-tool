// core/ui/sandbox.js - OpenClaw 嵌入检测（Phase 1 收紧版）
// 任务规格 §6：双向 postMessage 协议
// Phase 1 仅作 stub：暴露 isEmbedded() / postToParent()；完整协议 Phase 4 接入
(function () {
  function isEmbedded() {
    try {
      return window.parent !== window && !!window.parent.postMessage;
    } catch (e) {
      return false;
    }
  }
  function postToParent(type, payload) {
    if (!isEmbedded()) return;
    try {
      window.parent.postMessage(
        { source: 'sal', version: 1, type: type, payload: payload || {} },
        '*'  // Phase 1 stub: targetOrigin 显式化待 Phase 4
      );
    } catch (e) {
      console.error('[sandbox] postMessage failed', e);
    }
  }
  function onParentMessage(type, handler) {
    const bus = window.SAL && window.SAL.core && window.SAL.core.eventBus;
    if (!bus) return;
    bus.on('sandbox:parent:' + type, handler);
    window.addEventListener('message', function (ev) {
      const data = ev.data;
      if (!data || data.source !== 'sal' || data.type !== type) return;
      bus.emit('sandbox:parent:' + type, data.payload || {});
    });
  }
  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.ui = window.SAL.core.ui || {};
  window.SAL.core.ui.sandbox = {
    isEmbedded: isEmbedded,
    postToParent: postToParent,
    onParentMessage: onParentMessage,
  };
})();
