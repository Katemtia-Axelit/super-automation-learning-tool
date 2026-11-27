// core/state.js - 可订阅的 Proxy 状态 store（P1 切片 4）
//
// P1 之前
// ---------
// ``createStore`` 从未被任何生产代码调用（``app.js`` / ``modules/*`` 中
// ``SAL.core.*`` 引用数为 0），且没有 ``subscribe`` —— 跨模块共享状态
// 没有任何机制。
//
// 现在
// ----
// * ``createStore(initial)`` 返回一个 Proxy：``set`` 时自动 emit
//   ``state:change``（``{ key, value, old }``）；
// * ``subscribe(key, cb)`` 订阅 **单个 key**（``'*'`` 表示全部）；
// * ``unsubscribe(fn)`` 取消订阅（返回的取消函数也可直接调用）；
// * ``get(key)`` / ``set(key, value)`` 显式读写接口；
// * ``snapshot()`` 返回一份 **浅拷贝**（诊断用，不暴露内部对象）。
//
// 约束
// ----
// 1. 本模块 **不** 持有任何全局单例状态：每次 ``createStore`` 都是独立
//    的 store（多 app / 多测试互不串扰）。
// 2. 订阅者抛错 **绝不** 影响 store 本身（与 ``core/event-bus.js`` 语义
//    一致：隔离故障，不静默吞掉 —— 会 ``console.error``）。

(function () {
  function busOf() {
    return window.SAL && window.SAL.core && window.SAL.core.eventBus;
  }

  function createStore(initial) {
    const bus = busOf();
    const state = Object.assign({}, initial || {});
    const subscribers = [];   // { key, fn }

    function notify(key, value, old) {
      subscribers.slice().forEach(function (entry) {
        if (entry.key !== '*' && entry.key !== key) return;
        try {
          entry.fn(value, { key: key, value: value, old: old });
        } catch (e) {
          console.error('[core/state] subscriber failed for key ' + key, e);
        }
      });
    }

    const proxy = new Proxy(state, {
      set(target, key, value) {
        const old = target[key];
        // 值未变化 → 不发事件（避免无谓的重绘）。
        if (old === value) return true;
        target[key] = value;
        if (bus) bus.emit('state:change', { key: key, value: value, old: old });
        notify(key, value, old);
        return true;
      },
      deleteProperty(target, key) {
        const old = target[key];
        delete target[key];
        if (bus) bus.emit('state:change', { key: key, value: undefined, old: old });
        notify(key, undefined, old);
        return true;
      }
    });

    function get(key) {
      return proxy[key];
    }

    function set(key, value) {
      proxy[key] = value;
      return value;
    }

    /**
     * 订阅某个 key（``'*'`` = 全部）。返回取消订阅函数。
     */
    function subscribe(key, cb) {
      if (typeof key === 'function' && cb === undefined) {
        cb = key;
        key = '*';
      }
      if (typeof cb !== 'function') {
        throw new Error('[core/state] subscribe 需要一个回调函数');
      }
      const entry = { key: key, fn: cb };
      subscribers.push(entry);
      return function () {
        const index = subscribers.indexOf(entry);
        if (index !== -1) subscribers.splice(index, 1);
      };
    }

    function unsubscribe(fn) {
      for (let i = subscribers.length - 1; i >= 0; i -= 1) {
        if (subscribers[i].fn === fn) subscribers.splice(i, 1);
      }
    }

    function snapshot() {
      return Object.assign({}, state);
    }

    function subscriberCount() {
      return subscribers.length;
    }

    // 兼容：store **本身就是** 那个 Proxy（与 P1 之前的返回形态一致），
    // 额外挂载的辅助方法都是 **不可枚举** 的，因此不会污染 state 的键集合。
    const api = {
      get: get,
      set: set,
      subscribe: subscribe,
      unsubscribe: unsubscribe,
      snapshot: snapshot,
      subscriberCount: subscriberCount
    };
    Object.keys(api).forEach(function (key) {
      Object.defineProperty(proxy, key, {
        value: api[key],
        enumerable: false,
        configurable: true,
        writable: false
      });
    });
    return proxy;
  }

  // -------------------------------------------------------------------------
  // AR03-P3-D：派生映射 store（**只读派生**，绝不是第二状态源）
  // -------------------------------------------------------------------------
  //
  // `createDerivedMap` 承载 **轻量派生数据**（典型用途：任务 id → 任务名称）。
  //
  // 硬约束（计划 §3.4）：
  //   1. **不** 维护一份完整的 `allTasks` 镜像 —— 只存 id → name 这类
  //      小型派生值；
  //   2. 数据来源是 Tasks Owner 的 **只读 getter**，Tasks Owner 仍是
  //      「有哪些任务」的唯一权威；
  //   3. store 内容 **只读派生**，**绝不放** 可写权威业务状态。
  //
  // 因此本 API **不暴露** `set`（只有 `replace` 整体替换）与 `remove`，
  // 避免调用方把权威状态写进派生容器。

  /**
   * 创建一个 **只读派生** 映射 store。
   *
   * @param {Function} readSource 返回「[{id, name}, ...]」形态的只读来源；
   *   返回 null / undefined 视为「暂无数据」，不会清空既有映射。
   * @param {Object} options
   *   - options.keyOf: (item) => id，默认 ``item.id``
   *   - options.valueOf: (item) => value，默认 ``item.name``
   * @returns {Object} 只读派生映射 API
   */
  function createDerivedMap(readSource, options) {
    const opts = options || {};
    // 注意：必须用 **自有属性** 判定，不能用 `typeof opts.valueOf === 'function'`。
    // `Object.prototype.valueOf` / `Object.prototype.hasOwnProperty` 本身都是
    // 函数，`typeof` 判定会误把原型继承来的内置方法当成「用户提供的取值器」，
    // 随后 `Object.prototype.valueOf.call(null)` 抛
    // “Cannot convert undefined or null to object”。
    const hasKeyOf = Object.prototype.hasOwnProperty.call(opts, 'keyOf');
    const hasValueOf = Object.prototype.hasOwnProperty.call(opts, 'valueOf');
    const keyOf = hasKeyOf && typeof opts.keyOf === 'function'
      ? opts.keyOf
      : function (item) { return item && item.id; };
    const valueOf = hasValueOf && typeof opts.valueOf === 'function'
      ? opts.valueOf
      : function (item) { return item && item.name; };

    // 内部用普通对象（**不是** Proxy）：派生容器不需要逐键订阅语义。
    let mapping = Object.create(null);

    /**
     * 从只读来源整体刷新派生映射。
     * @returns {boolean} 是否发生了内容变化
     */
    function refresh() {
      if (typeof readSource !== 'function') return false;
      let source;
      try {
        source = readSource();
      } catch (e) {
        console.error('[core/state] derived map source failed', e);
        return false;
      }
      if (!source || typeof source.length !== 'number') return false;

      const next = Object.create(null);
      for (let i = 0; i < source.length; i += 1) {
        const item = source[i];
        if (item === null || item === undefined) continue;
        const key = keyOf(item);
        if (key === null || key === undefined || key === '') continue;
        next[String(key)] = valueOf(item);
      }

      // 内容相同 → 不替换（避免无谓的通知）。
      const oldKeys = Object.keys(mapping);
      const newKeys = Object.keys(next);
      let same = oldKeys.length === newKeys.length;
      if (same) {
        for (let i = 0; i < newKeys.length; i += 1) {
          const k = newKeys[i];
          if (mapping[k] !== next[k]) { same = false; break; }
        }
      }
      if (same) return false;

      mapping = next;
      return true;
    }

    /**
     * 读一个派生值。
     * @param {*} key
     * @param {*} fallback 未命中时的缺省值
     */
    function lookup(key, fallback) {
      if (key === null || key === undefined || key === '') return fallback;
      const k = String(key);
      return Object.prototype.hasOwnProperty.call(mapping, k) ? mapping[k] : fallback;
    }

    /** 是否命中。 */
    function has(key) {
      if (key === null || key === undefined || key === '') return false;
      return Object.prototype.hasOwnProperty.call(mapping, String(key));
    }

    /** 派生映射的浅拷贝（诊断用）。 */
    function snapshot() {
      return Object.assign({}, mapping);
    }

    /** 派生项数量。 */
    function size() {
      return Object.keys(mapping).length;
    }

    return {
      refresh: refresh,
      lookup: lookup,
      has: has,
      snapshot: snapshot,
      size: size
    };
  }

  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.state = {
    createStore: createStore,
    createDerivedMap: createDerivedMap
  };
})();