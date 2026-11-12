// static/modules/timer/index.js - AR03-G08 计时器 ESM 业务 owner
//
// 前端计时器的 **唯一业务 owner**：唯一 active session、唯一 paused 状态、
// Dock / 任务页 / 任务卡内嵌计时器的 interval handle、全部 /api/timer/* 生命周期
// 请求、实际分钟数计算 —— 全部收敛在这个闭包内。app.js 侧只保留最薄 classic
// facade（唯一 import promise + 唯一 owner 引用），**不再有任何 session /
// paused / interval 镜像**，也**不再有任何直接的 /api/timer/* 请求**。
//
// 呈现层：静态 import ./presentation.js（唯一 Dock / 任务页 DOM 写入点）。
// 依赖注入：api / taskNameById / formatElapsed。
//
// 语义保护（与迁移前 static/app.js 逐行一致）：
//   - pause / resume API 失败 → 抛错且 **不** 伪更新 paused 状态、不丢 session；
//   - complete API 失败 → 抛错且 **保留** 活动 session（绝不伪清空）；
//   - actual_minutes = Math.max(1, Math.round(elapsedMs / 60000))，
//     运行中计入历史 paused_seconds，暂停时使用 pausedElapsedMs。

import { updateTimerDockDisplay, updateTimerDisplay } from './presentation.js';

var TIMER_ACTIVE_URL = '/api/timer/active';
var TIMER_START_URL = '/api/timer/start';
var TIMER_PAUSE_URL = '/api/timer/pause';
var TIMER_RESUME_URL = '/api/timer/resume';
var TIMER_COMPLETE_URL = '/api/timer/complete';

// 任务页面板的毫秒格式化（缺省实现；app.js 会注入自己的同名实现）。
function defaultFormatElapsed(ms) {
  var sec = Math.max(0, Math.floor(ms / 1000));
  var m = Math.floor(sec / 60);
  var s = sec % 60;
  return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
}

// 严格规范 timer/start 返回的 session_id（与迁移前 app.js 逐行一致）。
// 接受：正整数 number，或仅由数字组成且代表正整数的字符串。
// 拒绝：missing / null / 空串 / boolean / 非数字 / 0 / 负数 / 小数 / 不安全整数。
// **绝不** 伪造 session_id；非法一律返回 null（fail closed）。
function normalizeTimerSessionId(raw) {
  if (typeof raw === 'boolean') return null;
  if (typeof raw === 'number') {
    if (!isFinite(raw)) return null;
    if (Math.floor(raw) !== raw) return null;      // 小数
    if (raw <= 0) return null;                     // 0 / 负数
    if (typeof Number.isSafeInteger === 'function' && !Number.isSafeInteger(raw)) return null;
    return raw;
  }
  if (typeof raw === 'string') {
    if (!/^[0-9]+$/.test(raw)) return null;        // 空串 / 非数字字符 / 小数 / 负号
    var parsed = Number(raw);
    if (!isFinite(parsed)) return null;
    if (Math.floor(parsed) !== parsed) return null;
    if (parsed <= 0) return null;
    if (typeof Number.isSafeInteger === 'function' && !Number.isSafeInteger(parsed)) return null;
    return parsed;
  }
  return null;                                     // missing / null / 对象 / 数组
}

/**
 * 创建唯一的计时器 owner 实例。
 * @param {Object} deps 注入依赖：api / taskNameById / formatElapsed
 */
export function createTimerOwner(deps) {
  var d = deps || {};
  var api = typeof d.api === 'function' ? d.api : null;
  var taskNameById = typeof d.taskNameById === 'function'
    ? d.taskNameById
    : function () { return ''; };
  var formatElapsed = typeof d.formatElapsed === 'function'
    ? d.formatElapsed
    : defaultFormatElapsed;

  // ---- 唯一可变状态（闭包私有，外部只能通过快照读取）--------------------
  var session = null;            // 唯一活动 session
  var paused = false;            // 唯一暂停标志
  var pausedElapsedMs = 0;       // 暂停时刻累计毫秒
  var dockTickHandle = null;     // Dock 每秒刷新
  var panelTickHandle = null;    // 任务页面板每秒刷新
  var inlineTickHandle = null;   // 任务卡内嵌计时器
  var inlineTaskId = null;       // 内嵌计时器所属 task id

  function requireApi() {
    if (!api) throw new Error('计时器 owner 缺少 api 依赖');
    return api;
  }

  // ---- 状态读取 ---------------------------------------------------------
  function getSession() { return session; }
  function getPaused() { return paused; }
  function getPausedElapsed() { return pausedElapsedMs; }

  /** 浅拷贝快照：调用方绝不直接修改 owner 内部对象。 */
  function getSnapshot() {
    return {
      session: session ? Object.assign({}, session) : null,
      paused: paused,
      pausedElapsedMs: pausedElapsedMs
    };
  }

  // ---- 呈现（唯一 DOM 写入点在 presentation.js）--------------------------
  function updateDock() {
    try {
      updateTimerDockDisplay({
        getSession: getSession,
        getPaused: getPaused,
        getPausedElapsed: getPausedElapsed,
        taskNameById: taskNameById
      });
    } catch (e) {
      console.error('[timer] updateDock', e);
    }
  }

  function updatePanel() {
    try {
      updateTimerDisplay({
        getActiveSession: getSession,
        getPaused: getPaused,
        getPausedElapsed: getPausedElapsed,
        taskNameById: taskNameById,
        formatElapsed: formatElapsed
      });
    } catch (e) {
      console.error('[timer] updatePanel', e);
    }
  }

  // ---- 生命周期请求（全部 /api/timer/* 只在这里出现）--------------------
  /**
   * 只读读取当前活动 session（**不** 改写 owner 状态）。
   */
  async function getActive() {
    var r = await requireApi()(TIMER_ACTIVE_URL, { method: 'GET' });
    return r || null;
  }

  /**
   * 读取活动 session 并同步到 owner 状态（Dock 与任务页共享同一 session）。
   * 失败时抛错，**不** 改写状态（调用方决定如何降级）。
   */
  async function loadActive() {
    var r = await requireApi()(TIMER_ACTIVE_URL, { method: 'GET' });
    session = (r && r.id) ? r : null;
    paused = !!(r && r.is_paused);
    pausedElapsedMs = (r && r.paused_seconds) ? r.paused_seconds * 1000 : 0;
    updateDock();
    updatePanel();
    return getSnapshot();
  }

  /**
   * 开始一个计时 session。
   * @param {Object} opts { taskId, plannedMinutes, taskName, requireValidSessionId }
   *        taskName 可以是字符串，也可以是 function(taskId) -> string。
   * @returns {Promise<Object>} { ok, error, sessionId, session }
   *        requireValidSessionId 为真且 session_id 非法 → ok=false，
   *        **绝不** 设置 session、**绝不** 启动任何计时器。
   */
  async function startSession(opts) {
    var o = opts || {};
    var r = await requireApi()(TIMER_START_URL, {
      method: 'POST',
      body: JSON.stringify({
        task_id: o.taskId,
        planned_minutes: o.plannedMinutes
      })
    });
    var rawSessionId = r ? r.session_id : undefined;
    var strict = !!o.requireValidSessionId;
    var normalizedId = normalizeTimerSessionId(rawSessionId);
    if (strict && normalizedId === null) {
      // Fail closed：绝不设置 session、绝不启动任何计时器。
      return {
        ok: false,
        error: 'invalid_session_id',
        sessionId: null,
        session: null
      };
    }
    var sessionId = strict ? normalizedId : rawSessionId;
    var resolvedName = o.taskName;
    if (typeof resolvedName === 'function') {
      resolvedName = resolvedName(r ? r.task_id : o.taskId);
    } else if (resolvedName === undefined || resolvedName === null) {
      resolvedName = taskNameById(r ? r.task_id : o.taskId);
    }
    session = {
      id: sessionId,
      task_id: r ? r.task_id : o.taskId,
      started_at: r ? r.started_at : null,
      planned_minutes: r ? r.planned_minutes : o.plannedMinutes,
      task_name: resolvedName
    };
    paused = false;
    pausedElapsedMs = 0;
    updateDock();
    updatePanel();
    return {
      ok: true,
      error: null,
      sessionId: sessionId,
      session: Object.assign({}, session)
    };
  }

  /**
   * 暂停。失败 → 抛错，**不** 伪更新 paused 状态、不丢 session。
   */
  async function pauseSession() {
    if (!session || !session.id) throw new Error('没有进行中的计时');
    var r = await requireApi()(TIMER_PAUSE_URL, {
      method: 'POST',
      body: JSON.stringify({ session_id: session.id })
    });
    paused = true;
    pausedElapsedMs = (r && r.paused_seconds) ? r.paused_seconds * 1000 : pausedElapsedMs;
    // M1.3B：把服务端权威的 paused_seconds / started_at 回写到 session，
    // 这样 resume 之后的运行侧 elapsed 仍然是单调的。
    if (r && r.paused_seconds != null) session.paused_seconds = r.paused_seconds;
    if (r && r.started_at) session.started_at = r.started_at;
    updateDock();
    updatePanel();
    return getSnapshot();
  }

  /**
   * 恢复。失败 → 抛错，**不** 伪更新 paused 状态、不丢 session。
   */
  async function resumeSession() {
    if (!session || !session.id) throw new Error('没有进行中的计时');
    var r = await requireApi()(TIMER_RESUME_URL, {
      method: 'POST',
      body: JSON.stringify({ session_id: session.id })
    });
    paused = false;
    if (r && r.started_at) session.started_at = r.started_at;
    updateDock();
    updatePanel();
    return getSnapshot();
  }

  /**
   * 结束一个 session。
   * 失败 → 抛错且 **保留** 活动 session（绝不伪清空、绝不继续后续流程）。
   * 成功 → 清空唯一 session（Dock 与任务页同步）。
   */
  async function completeSession(opts) {
    var o = opts || {};
    var body = {
      session_id: o.sessionId,
      actual_minutes: o.actualMinutes,
      result: o.result
    };
    // reason 只在真正给出时才带上（null / undefined → 字段缺席，
    // 与迁移前 app.js 的 body 字段逐字一致）。
    if (o.reason !== undefined && o.reason !== null) body.reason = o.reason;
    var r = await requireApi()(TIMER_COMPLETE_URL, {
      method: 'POST',
      body: JSON.stringify(body)
    });
    clear();
    return r;
  }

  /**
   * 清空 owner 的活动 session（**不** 发任何请求）。
   * 用于"任务在别处被完成"这类既有语义：Dock 回到空闲。
   */
  function clear() {
    session = null;
    paused = false;
    pausedElapsedMs = 0;
    stopInlineTimer();
    updateDock();
    updatePanel();
  }

  /**
   * 实际分钟数：Math.max(1, Math.round(elapsedMs / 60000))。
   * 运行中计入历史 paused_seconds；暂停时使用 pausedElapsedMs。
   */
  function getActualMinutes(nowMs) {
    if (!session) return null;
    var startedMs = new Date(session.started_at).getTime();
    var now = (nowMs === undefined || nowMs === null) ? Date.now() : nowMs;
    var elapsedMs = isFinite(startedMs) ? (now - startedMs) : 0;
    if (paused) {
      elapsedMs = pausedElapsedMs;
    } else {
      elapsedMs += (session.paused_seconds || 0) * 1000;
    }
    return Math.max(1, Math.round(elapsedMs / 60000));
  }

  /**
   * 只读检查：某个任务是否仍在计时，且是否已超过计划时长的 80%。
   * （用于既有的超时提醒语义。）
   */
  async function checkTaskTimerStatus(taskId) {
    try {
      var r = await getActive();
      if (r && r.task_id === taskId && r.started_at) {
        var started = new Date(r.started_at).getTime();
        var planned = r.planned_minutes || 30;
        var elapsed = (Date.now() - started) / 60000;
        if (elapsed > planned * 0.8) {
          return { overdue: true, elapsedMinutes: elapsed, plannedMinutes: planned };
        }
        return { overdue: false, elapsedMinutes: elapsed, plannedMinutes: planned };
      }
    } catch (e) { /* ignore */ }
    return { overdue: false };
  }

  // ---- 内嵌计时器（任务卡内）-------------------------------------------
  function startInlineTimer(taskId) {
    stopInlineTimer();
    var card = document.querySelector('.task-card.drawn-card[data-task-id="' + taskId + '"]');
    if (!card) return;
    inlineTaskId = taskId;
    inlineTickHandle = setInterval(function () {
      if (!session || session.task_id !== taskId) {
        stopInlineTimer();
        return;
      }
      var display = card.querySelector('.card-timer-display');
      if (!display) { stopInlineTimer(); return; }
      var started = new Date(session.started_at).getTime();
      var elapsed = Date.now() - started;
      if (paused) elapsed = pausedElapsedMs;
      var sec = Math.floor(Math.max(0, elapsed) / 1000);
      var m = Math.floor(sec / 60);
      var s = sec % 60;
      display.textContent = (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
    }, 1000);
  }

  function stopInlineTimer() {
    if (inlineTickHandle) clearInterval(inlineTickHandle);
    inlineTickHandle = null;
    inlineTaskId = null;
  }

  function hasInlineTimer() {
    return !!inlineTickHandle;
  }

  // ---- 呈现节拍 ---------------------------------------------------------
  function startDockTick() {
    if (dockTickHandle) clearInterval(dockTickHandle);
    dockTickHandle = setInterval(updateDock, 1000);
  }

  function startPanelTick() {
    if (panelTickHandle) clearInterval(panelTickHandle);
    panelTickHandle = setInterval(updatePanel, 1000);
  }

  return {
    getSnapshot: getSnapshot,
    getActive: getActive,
    loadActive: loadActive,
    startSession: startSession,
    pauseSession: pauseSession,
    resumeSession: resumeSession,
    completeSession: completeSession,
    clear: clear,
    getActualMinutes: getActualMinutes,
    checkTaskTimerStatus: checkTaskTimerStatus,
    updateDock: updateDock,
    updatePanel: updatePanel,
    startInlineTimer: startInlineTimer,
    stopInlineTimer: stopInlineTimer,
    hasInlineTimer: hasInlineTimer,
    startDockTick: startDockTick,
    startPanelTick: startPanelTick
  };
}
