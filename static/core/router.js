// core/router.js - 真 hash 路由（P1 切片 4）
//
// P1 之前
// ---------
// 本文件只导出 ``PAGES`` 常量数组，**没有任何路由能力**：无 hash 解析、
// 无 ``navigate``、无 mount/unmount 调度。``app.entry.js`` 的 ``wireNav()``
// 虽然广播 ``page:change``，但没有订阅者真正 dispatch 到模块。
//
// 现在
// ----
// * ``parseHash(hash)`` → 解析出当前页面 id（``#gacha`` → ``'gacha'``）；
// * ``getCurrentPage()`` → 读取当前 hash 对应的页面（无 hash 时回落到
//   默认页 ``gacha``）；
// * ``navigate(page)`` → 写 hash（并广播 ``page:change``）；
// * ``start()`` → 监听 ``hashchange``，把变化广播成 ``page:change``；
// * ``onRouteChange(cb)`` → 订阅路由变化（返回取消订阅函数）。
//
// 约束
// ----
// 1. 本文件 **不** import ``modules/*``（内核不反向依赖业务）；它只负责
//    "当前是哪一页" 这件事，**调度** 由 ``app.entry.js`` 通过
//    ``core/registry.js`` 完成。
// 2. ``PAGES`` 与 ``core/constants.js`` 的 ``PAGES`` 保持一致（单一权威：
//    ``core/constants.js``）。这里做一次 **读取**，不再复制一份数组。
// 3. 旧 ``app.js`` 的 ``showPage(id)`` **不** 被替换 —— inline handler 与
//    既有 E2E 仍然走它。router 只提供 **可选** 的 hash 同步能力。

(function () {
  const DEFAULT_PAGE = 'gacha';

  function pages() {
    const constants = window.SAL && window.SAL.core && window.SAL.core.constants;
    if (constants && Array.isArray(constants.PAGES)) return constants.PAGES;
    return [DEFAULT_PAGE];
  }

  /**
   * 解析 hash → 页面 id。
   * 非法 / 未注册的页面一律返回 null（调用方决定回落策略）。
   */
  function parseHash(hash) {
    let raw = String(hash == null ? '' : hash);
    if (raw.charAt(0) === '#') raw = raw.slice(1);
    if (!raw) return null;
    // 只取第一段（'#/gacha' → 'gacha'），忽略查询串。
    const page = raw.split('?')[0].split('/')[0].trim();
    if (!page) return null;
    if (pages().indexOf(page) === -1) return null;
    return page;
  }

  function currentHash() {
    try {
      return window.location.hash || '';
    } catch (e) {
      return '';
    }
  }

  /**
   * 当前页面 id；没有合法 hash 时回落到默认页。
   */
  function getCurrentPage() {
    return parseHash(currentHash()) || DEFAULT_PAGE;
  }

  function isKnownPage(page) {
    return typeof page === 'string' && pages().indexOf(page) !== -1;
  }

  const listeners = [];

  function emit(page) {
    const bus = window.SAL && window.SAL.core && window.SAL.core.eventBus;
    if (bus) bus.emit('page:change', { page: page });
    listeners.slice().forEach(function (fn) {
      try {
        fn(page);
      } catch (e) {
        console.error('[core/router] listener failed', e);
      }
    });
  }

  /**
   * 订阅路由变化；返回取消订阅函数。
   */
  function onRouteChange(cb) {
    if (typeof cb !== 'function') return function () {};
    listeners.push(cb);
    return function () {
      const index = listeners.indexOf(cb);
      if (index !== -1) listeners.splice(index, 1);
    };
  }

  /**
   * 导航到某页：写 hash（触发 hashchange → start() 的广播）。
   * 已经是目标页时也 **显式** 广播一次（保证 mount 一定发生）。
   */
  function navigate(page) {
    if (!isKnownPage(page)) {
      throw new Error('[core/router] 未知页面：' + page);
    }
    const next = '#' + page;
    try {
      if (currentHash() === next) {
        emit(page);
        return page;
      }
      window.location.hash = next;
    } catch (e) {
      // 环境没有 location（合成测试）→ 退化为直接广播。
      emit(page);
    }
    return page;
  }

  let _started = false;
  let _lastPage = null;

  /**
   * 启动路由：监听 hashchange 并广播。
   * 幂等：重复调用只生效一次。
   */
  function start() {
    if (_started) return false;
    _started = true;
    window.addEventListener('hashchange', function () {
      const page = getCurrentPage();
      if (page === _lastPage) return;
      _lastPage = page;
      emit(page);
    });
    _lastPage = getCurrentPage();
    return true;
  }

  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.router = {
    PAGES: pages(),
    DEFAULT_PAGE: DEFAULT_PAGE,
    parseHash: parseHash,
    getCurrentPage: getCurrentPage,
    isKnownPage: isKnownPage,
    navigate: navigate,
    onRouteChange: onRouteChange,
    start: start
  };
})();
