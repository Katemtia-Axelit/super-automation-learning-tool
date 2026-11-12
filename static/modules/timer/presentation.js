// static/modules/timer/presentation.js - AR03-G04 真实生产 ESM owner
//
// 拥有计时器两处 DOM 呈现：
//   - updateTimerDockDisplay(deps): 全局 Dock（#timerDock*）时间 / 进度 / 暂停图标
//   - updateTimerDisplay(deps): 任务页计时面板（#timer*）时间 / 状态文案 / 按钮可见性
//
// 语义与迁移前 static/app.js 内同名函数逐行一致。旧 app.js 只保留最薄 classic
// facade（唯一共享 import promise + 代际防过期），**不再有任何第二份实现**。
//
// 本模块 **不持有** session / paused / interval / API 状态：所有字段在写 DOM
// 的那一刻从注入的 getter 读取，因此异步 import 与每秒 tick 之间永远是最新状态获胜。
//
// 依赖注入约定（不通过 window 查找私有 helper）：
//   getSession() / getActiveSession()  -> classic 唯一 session
//   getPaused() / getPausedElapsed()   -> classic 唯一暂停标志与毫秒
//   taskNameById(id)                   -> classic 任务名查找
//   formatElapsed(ms)                  -> classic 毫秒格式化（仅任务页）

/**
 * 全局 Dock 计时呈现（唯一 Dock DOM 写入点）。
 * @param {Object} deps classic 层注入的 getter / helper
 */
export function updateTimerDockDisplay(deps) {
  var d = deps || {};
  var getSession = typeof d.getSession === 'function' ? d.getSession : function () { return null; };
  var getPaused = typeof d.getPaused === 'function' ? d.getPaused : function () { return false; };
  var getPausedElapsed = typeof d.getPausedElapsed === 'function'
    ? d.getPausedElapsed
    : function () { return 0; };
  var taskNameById = typeof d.taskNameById === 'function'
    ? d.taskNameById
    : function () { return ''; };

  var idleEl = document.getElementById('timerDockIdle');
  var activeEl = document.getElementById('timerDockActive');
  var taskNameEl = document.getElementById('timerDockTaskName');
  var timeEl = document.getElementById('timerDockTime');
  var barEl = document.getElementById('timerDockBar');
  var pauseBtn = document.getElementById('timerDockPauseBtn');

  if (!idleEl || !activeEl) return;

  var timerDockSession = getSession();
  var timerDockPaused = !!getPaused();
  var timerDockPausedElapsed = getPausedElapsed() || 0;

  if (!timerDockSession || !timerDockSession.started_at) {
    idleEl.classList.remove('hidden');
    activeEl.classList.add('hidden');
    return;
  }

  idleEl.classList.add('hidden');
  activeEl.classList.remove('hidden');

  var started = new Date(timerDockSession.started_at).getTime();
  var elapsed = Date.now() - started;
  // P3-Bug-B: 暂停状态时 elapsed 已被后端暂停累积值覆盖
  if (timerDockPaused) {
    elapsed = timerDockPausedElapsed;
  } else {
    // 运行时：加入历史暂停时间（resume 后 paused_seconds 仍保留）
    var sessionPausedMs = (timerDockSession.paused_seconds || 0) * 1000;
    elapsed += sessionPausedMs;
  }

  var sec = Math.floor(elapsed / 1000);
  var m = Math.floor(sec / 60);
  var s = sec % 60;
  var timeStr = (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;

  var name = timerDockSession.task_name || taskNameById(timerDockSession.task_id) || '进行中';
  var planned = timerDockSession.planned_minutes || 30;
  var progress = Math.min(100, (elapsed / 1000 / 60 / planned) * 100);

  if (taskNameEl) taskNameEl.textContent = name;
  if (timeEl) timeEl.textContent = timeStr;
  if (barEl) barEl.style.width = progress + '%';
  if (pauseBtn) {
    if (timerDockPaused) {
      pauseBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
      pauseBtn.title = '继续计时器';
    } else {
      pauseBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
      pauseBtn.title = '暂停计时器';
    }
  }
}

/**
 * 任务页计时面板呈现（唯一任务页计时 DOM 写入点）。
 * @param {Object} deps classic 层注入的 getter / helper
 */
export function updateTimerDisplay(deps) {
  var d = deps || {};
  var getActiveSession = typeof d.getActiveSession === 'function'
    ? d.getActiveSession
    : function () { return null; };
  var getPaused = typeof d.getPaused === 'function' ? d.getPaused : function () { return false; };
  var getPausedElapsed = typeof d.getPausedElapsed === 'function'
    ? d.getPausedElapsed
    : function () { return 0; };
  var taskNameById = typeof d.taskNameById === 'function'
    ? d.taskNameById
    : function () { return ''; };
  var formatElapsed = typeof d.formatElapsed === 'function'
    ? d.formatElapsed
    : function (ms) {
        var sec = Math.max(0, Math.floor(ms / 1000));
        var mm = Math.floor(sec / 60);
        var ss = sec % 60;
        return (mm < 10 ? '0' : '') + mm + ':' + (ss < 10 ? '0' : '') + ss;
      };

  var statusEl = document.getElementById('timerStatusText');
  var elapsedEl = document.getElementById('timerElapsedDisplay');
  var startBtn = document.getElementById('timerStartBtn');
  var pauseBtn = document.getElementById('timerPauseBtn');
  var stopBtn = document.getElementById('timerStopBtn');
  var sel = document.getElementById('timerTaskSelect');
  var planned = document.getElementById('timerPlannedMin');
  if (!statusEl || !elapsedEl) return;

  var timerActiveSession = getActiveSession();
  var timerDockPaused = !!getPaused();
  var timerDockPausedElapsed = getPausedElapsed() || 0;

  if (timerActiveSession && timerActiveSession.started_at) {
    var started = new Date(timerActiveSession.started_at).getTime();
    var elapsed = Date.now() - started;
    // P3-Bug-A: 从全局读取暂停状态（两处 UI 同步）
    if (timerDockPaused) {
      elapsed = timerDockPausedElapsed;
    } else {
      // 运行时：加入历史暂停时间（resume 后 paused_seconds 仍保留）
      var sessionPausedMs = (timerActiveSession.paused_seconds || 0) * 1000;
      elapsed += sessionPausedMs;
    }
    elapsedEl.textContent = formatElapsed(elapsed);
    var name = timerActiveSession.task_name || taskNameById(timerActiveSession.task_id);
    var pauseIndicator = timerDockPaused ? ' (已暂停)' : '';
    statusEl.textContent = '计时中 · ' + name + '（计划 ' + (timerActiveSession.planned_minutes || '?') + ' 分）' + pauseIndicator;
    statusEl.className = timerDockPaused ? 'timer-paused' : '';
    if (startBtn) startBtn.classList.add('hidden');
    if (stopBtn) stopBtn.classList.remove('hidden');
    if (pauseBtn) {
      pauseBtn.classList.remove('hidden');
      if (timerDockPaused) {
        pauseBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
        pauseBtn.title = '继续计时器';
      } else {
        pauseBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
        pauseBtn.title = '暂停计时器';
      }
    }
    if (sel) sel.disabled = true;
    if (planned) planned.disabled = true;
  } else {
    elapsedEl.textContent = '00:00';
    statusEl.textContent = '未在计时';
    statusEl.className = 'timer-idle';
    if (startBtn) startBtn.classList.remove('hidden');
    if (stopBtn) stopBtn.classList.add('hidden');
    if (pauseBtn) pauseBtn.classList.add('hidden');
    if (sel) sel.disabled = false;
    if (planned) planned.disabled = false;
  }
}
