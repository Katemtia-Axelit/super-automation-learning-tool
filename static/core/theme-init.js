// core/theme-init.js - 绑定顶栏主题切换按钮 click + 同步 icon
// 必须在 app.js 之后加载（依赖 btn DOM）。
(function(){
  function getIcon() {
    const current = window.SAL.core.theme.getTheme();
    // dark 主题显示月亮（点击会切到 light）
    // light 主题显示太阳（点击会切到 dark）
    return current === 'light' ? 'fa-sun' : 'fa-moon';
  }
  function refreshIcon() {
    const el = document.getElementById('themeToggleIcon');
    if (!el) return;
    const cls = getIcon();
    el.className = 'fa-solid ' + cls;
  }
  function bind() {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;
    btn.addEventListener('click', function(){
      const next = window.SAL.core.theme.toggleTheme();
      refreshIcon();
      const bus = window.SAL.core.eventBus;
      if (bus) bus.emit('theme:user-toggled', { theme: next });
    });
    refreshIcon();
    // 监听 state 变化（外部 setTheme）保证图标同步
    const bus = window.SAL.core.eventBus;
    if (bus) bus.on('theme:change', refreshIcon);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
