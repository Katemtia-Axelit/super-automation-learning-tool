// shared/timer.js - 计时器状态的 **只读视图**（P1 切片 4）
//
// P1 之前
// ---------
// 本文件自己维护了 ``state = { current, paused, pausedElapsed }``，但
// ``mount()`` 是 **空实现** —— 也就是说它是一个"看起来有状态、实际什么都不
// 做"的 stub，与真正的计时器 owner（``static/modules/timer/index.js``，
// AR03-G08 起的 **唯一** 写者）构成第二份状态来源。
//
// 现在
// ----
// * 本文件 **不再持有任何计时状态**（没有 ``state``、没有 ``set``）；
// * ``get()`` 返回 **唯一 owner** 的只读快照（owner 未就绪时返回空快照，
//   而不是伪造一个 session）；
// * ``mount()`` 委托给唯一 owner（``window._getTimerOwner()``），
//   **绝不**新建第二份 session；
// * ``subscribe(fn)`` 订阅 ``timer:state`` 总线事件。
//
// 唯一写者仍然是 ``static/modules/timer/index.js``。

(function () {
  const listeners = new Set();

  function emptySnapshot() {
    return { session: null, paused: false, pausedElapsedMs: 0 };
  }

  function ownerOf() {
    // app.js 暴露的唯一 owner 解析器（AR03-G08）。
    if (typeof window._getTimerOwner !== 'function') return null;
    try {
      return window._getTimerOwner();
    } catch (e) {
      return null;
    }
  }

  /**
   * 只读快照：owner 尚未就绪（promise 未 resolve）时返回空快照。
   * 绝不伪造 session。
   */
  function get() {
    const owner = ownerOf();
    if (!owner || typeof owner.then === 'function') return emptySnapshot();
    try {
      return owner.getSnapshot();
    } catch (e) {
      return emptySnapshot();
    }
  }

  /**
   * 计时状态的 **唯一写者** 是 modules/timer owner。
   * 本文件 **不** 提供写入口（写入口属于 owner 的业务 API）。
   */
  function set() {
    throw new Error(
      '[shared/timer] 计时状态的唯一写者是 static/modules/timer/index.js；' +
      'shared/timer 只提供只读视图。'
    );
  }

  function subscribe(fn) {
    if (typeof fn !== 'function') return function () {};
    listeners.add(fn);
    const bus = window.SAL && window.SAL.core && window.SAL.core.eventBus;
    let off = null;
    if (bus) {
      off = bus.on('timer:state', function () {
        try {
          fn(get());
        } catch (e) {
          console.error('[shared/timer] subscriber failed', e);
        }
      });
    }
    return function () {
      listeners.delete(fn);
      if (off) off();
    };
  }

  /**
   * 挂载：委托唯一 owner（**不新建** session / 不新建状态）。
   * 返回一个 Promise，resolve 后是 owner 的只读快照。
   */
  function mount() {
    const owner = ownerOf();
    if (!owner) return Promise.resolve(emptySnapshot());
    if (typeof owner.then === 'function') {
      return owner.then(function (real) {
        try {
          return real.getSnapshot();
        } catch (e) {
          return emptySnapshot();
        }
      }).catch(function () {
        return emptySnapshot();
      });
    }
    try {
      return Promise.resolve(owner.getSnapshot());
    } catch (e) {
      return Promise.resolve(emptySnapshot());
    }
  }

  window.SAL = window.SAL || {};
  window.SAL.shared = window.SAL.shared || {};
  window.SAL.shared.timer = {
    get: get,
    set: set,
    subscribe: subscribe,
    mount: mount
  };
})();
