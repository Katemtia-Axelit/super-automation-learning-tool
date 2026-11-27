// core/api.js - fetch 包装 + 错误处理（与原 app.js L11-29 行为一致）
// 包装在 IIFE 内，避免与 app.js 的全局 const API 冲突；通过 window.SAL.core.api 暴露。
(function(){
  async function api(url, opts) {
    opts = opts || {};
    const r = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...opts
    });
    let data = {};
    try { data = await r.json(); } catch (e) { data = {}; }
    if (!r.ok) {
      const msg = data.error || data.message || ('请求失败 (' + r.status + ')');
      throw new Error(msg);
    }
    return data;
  }
  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.api = api;
})();
