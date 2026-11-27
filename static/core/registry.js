// core/registry.js - Feature 模块注册表（P1 切片 4）
//
// 定位
// ----
// 模块契约（docs/ARCHITECTURE_REDESIGN_2026-08-16.md §4.1）规定每个
// Feature 模块导出 ``meta`` / ``mount(rootEl, ctx)`` / ``unmount(rootEl)``。
// 本文件是这些契约的 **唯一登记处**：模块实现（ESM）由
// ``static/app.entry.js`` 在启动时注册进来，本文件本身 **不** import 任何
// 业务模块（内核不反向依赖业务）。
//
// 为什么需要它
// ------------
// P1 之前 ``app.entry.js`` 的 ``wireNav()`` 监听 ``page:change`` 后只
// ``console.debug``，**从不** dispatch 到任何 module —— 契约形同虚设。
// 注册表把"页面切换 → 模块挂载/卸载"变成 **可机械校验** 的事：
// 未注册的模块不会被静默忽略，而是被记录成一次 **可见的失败**。
//
// 约束
// ----
// 1. 本文件是 **classic script**（不是 ESM）：它必须能在 ``app.js`` 之前
//    独立加载，且 **绝不** import ``modules/*``（内核不反向依赖业务）。
// 2. 注册失败（缺 meta / 缺 mount / 缺 unmount）**fail closed**：抛错，
//    绝不"半注册"一个缺方法的模块。
// 3. ``deps`` 是 **页面级依赖名**（如 ``'timer-dock'``），只做 **记录与
//    校验**：未知依赖不阻断挂载，但会被记录成 ``missingDeps``，供诊断。

(function () {
  const modules = new Map();      // name -> { meta, mount, unmount }
  const mounted = new Set();      // 已挂载的模块名
  const diagnostics = [];         // 挂载过程中的可见诊断

  function fail(message) {
    throw new Error('[core/registry] ' + message);
  }

  /**
   * 注册一个 Feature 模块。
   * @param {string} name 模块名（= 页面 id，如 'gacha' / 'tasks'）
   * @param {Object} meta  { name, version, deps? }
   * @param {Function} mount   (rootEl, ctx) => void|Promise
   * @param {Function} unmount (rootEl) => void|Promise
   */
  function register(name, meta, mount, unmount) {
    if (typeof name !== 'string' || !name.trim()) {
      fail('模块名必须是非空字符串');
    }
    if (!meta || typeof meta !== 'object') {
      fail(name + ': meta 必须是对象');
    }
    if (typeof mount !== 'function') {
      fail(name + ': mount 必须是函数');
    }
    if (typeof unmount !== 'function') {
      fail(name + ': unmount 必须是函数');
    }
    if (modules.has(name)) {
      fail('模块 "' + name + '" 已注册（绝不重复注册）');
    }
    const deps = Array.isArray(meta.deps) ? meta.deps.slice() : [];
    modules.set(name, {
      meta: Object.assign({}, meta, { name: name, deps: deps }),
      mount: mount,
      unmount: unmount
    });
    return name;
  }

  function has(name) {
    return modules.has(name);
  }

  function get(name) {
    return modules.get(name) || null;
  }

  function list() {
    return Array.from(modules.keys()).sort();
  }

  function mountedList() {
    return Array.from(mounted).sort();
  }

  function isMounted(name) {
    return mounted.has(name);
  }

  /**
   * 挂载一个模块。已挂载 → 直接返回（幂等）。
   * 未注册 → 返回 false 并记录诊断（**绝不**静默吞掉）。
   */
  function mount(name, ctx) {
    const entry = modules.get(name);
    if (!entry) {
      diagnostics.push({ type: 'mount-missing-module', name: name });
      return false;
    }
    if (mounted.has(name)) {
      return true;
    }
    const missingDeps = entry.meta.deps.filter(function (dep) {
      return !modules.has(dep);
    });
    if (missingDeps.length) {
      // 依赖缺失 **不阻断** 挂载，但必须 **可见**（页面级依赖常常是
      // 外部组件而不是另一个 Feature 模块）。
      diagnostics.push({
        type: 'mount-missing-deps',
        name: name,
        deps: missingDeps
      });
    }
    try {
      const result = entry.mount(ctx && ctx.rootEl, ctx);
      mounted.add(name);
      if (result && typeof result.then === 'function') {
        return result.catch(function (err) {
          mounted.delete(name);
          diagnostics.push({ type: 'mount-failed', name: name, error: String(err) });
          throw err;
        });
      }
      return true;
    } catch (err) {
      diagnostics.push({ type: 'mount-failed', name: name, error: String(err) });
      throw err;
    }
  }

  /**
   * 卸载一个模块。未挂载 → 直接返回（幂等）。
   */
  function unmount(name) {
    const entry = modules.get(name);
    if (!entry) {
      diagnostics.push({ type: 'unmount-missing-module', name: name });
      return false;
    }
    if (!mounted.has(name)) {
      return true;
    }
    try {
      const result = entry.unmount();
      mounted.delete(name);
      if (result && typeof result.then === 'function') {
        return result.catch(function (err) {
          diagnostics.push({ type: 'unmount-failed', name: name, error: String(err) });
          throw err;
        });
      }
      return true;
    } catch (err) {
      diagnostics.push({ type: 'unmount-failed', name: name, error: String(err) });
      throw err;
    }
  }

  function mountAll(ctx) {
    list().forEach(function (name) { mount(name, ctx); });
  }

  function unmountAll() {
    mountedList().reverse().forEach(function (name) { unmount(name); });
  }

  function getDiagnostics() {
    return diagnostics.slice();
  }

  function clearDiagnostics() {
    diagnostics.length = 0;
  }

  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.registry = {
    register: register,
    has: has,
    get: get,
    list: list,
    mount: mount,
    unmount: unmount,
    mountAll: mountAll,
    unmountAll: unmountAll,
    isMounted: isMounted,
    mountedList: mountedList,
    getDiagnostics: getDiagnostics,
    clearDiagnostics: clearDiagnostics
  };
})();
