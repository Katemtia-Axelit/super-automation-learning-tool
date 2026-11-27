// core/theme.js - data-theme 持久化 + 系统主题跟随
// 兼容：head 内联脚本已经早期同步 data-theme；本模块只负责 setTheme / toggle / 监听系统。
(function(){
  const STORAGE_KEY = 'sal.theme';

  function getTheme() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  }
  function setTheme(name, opts) {
    opts = opts || {};
    const final = (name === 'light' || name === 'dark') ? name : 'dark';
    document.documentElement.setAttribute('data-theme', final);
    if (opts.persist !== false) {
      try { localStorage.setItem(STORAGE_KEY, final); } catch (e) {}
    }
    const bus = window.SAL && window.SAL.core && window.SAL.core.eventBus;
    if (bus) bus.emit('theme:change', { theme: final });
    return final;
  }
  function toggleTheme() {
    return setTheme(getTheme() === 'dark' ? 'light' : 'dark');
  }
  let _sysMql = null;
  function bindSystemTheme() {
    if (!window.matchMedia) return;
    _sysMql = window.matchMedia('(prefers-color-scheme: light)');
    const handler = (e) => {
      let stored = null;
      try { stored = localStorage.getItem(STORAGE_KEY); } catch (er) {}
      if (stored === 'light' || stored === 'dark') return;
      setTheme(e.matches ? 'light' : 'dark', { persist: false });
    };
    if (_sysMql.addEventListener) _sysMql.addEventListener('change', handler);
    else if (_sysMql.addListener) _sysMql.addListener(handler);
  }
  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.theme = { getTheme, setTheme, toggleTheme, bindSystemTheme, STORAGE_KEY };
})();
