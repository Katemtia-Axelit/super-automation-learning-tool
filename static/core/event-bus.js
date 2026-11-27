// core/event-bus.js - 极简发布订阅（O(n) 遍历；够用）
(function(){
  const listeners = new Map();
  function on(type, fn) {
    if (!listeners.has(type)) listeners.set(type, new Set());
    listeners.get(type).add(fn);
    return () => off(type, fn);
  }
  function off(type, fn) {
    const set = listeners.get(type);
    if (set) set.delete(fn);
  }
  function emit(type, payload) {
    const set = listeners.get(type);
    if (!set) return;
    for (const fn of Array.from(set)) {
      try { fn(payload); } catch (e) { console.error('[event-bus]', type, e); }
    }
  }
  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.eventBus = { on, off, emit };
})();
