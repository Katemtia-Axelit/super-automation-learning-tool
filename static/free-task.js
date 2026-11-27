// static/free-task.js
// 自由任务 · 正式主界面 MVP（LT_RETENTION_FREE_TASK_MAIN_UI_MVP_20261023_Q）
//
// 目的
// ----
// 让用户在**正式学习工具**的「任务」页直接使用自由任务流程：
//   draft -> running <-> paused -> completed / interrupted / failed
//
// 边界（必须诚实，不得冒充正式统计）
// --------------------------------
// - 本文件是独立 IIFE，只挂载 #freeTaskPanel；不修改 window.showPage、
//   不触碰旧 app.js 的任何全局函数、不访问其它 app 组件。
// - 全部数据只保存在浏览器 localStorage 的**单一命名空间**
//   SAL_FREE_TASK_LOCAL_V1 中；不写入 data/、config/、src/notes/**，
//   不调用任何后端 API，因此**不计入**抽卡数、既有任务完成数与
//   服务端已验证学习分钟 / 番茄统计。
// - 计时到 0 只停止计时，**绝不自动完成**；完成必须由用户明确点击。
// - 暂停 / 恢复不把经过时间当作已验证分钟：只有用户手填的
//   「自报学习分钟（未独立核实）」会被记录，且娱乐类恒为 0。
// - localStorage 不可用或写入失败时必须显示可见错误，并明确说明
//   仅保存在内存、刷新会丢失；绝不假装已经保存。

(function () {
  'use strict';

  var STORAGE_KEY = 'SAL_FREE_TASK_LOCAL_V1';
  var MAX_HISTORY = 30;   // 最多保留 30 条任务历史
  var MAX_EVENTS = 100;    // 最多保留 100 条事件
  var MAX_NAME = 60;
  var TICK_MS = 250;

  var STATUS_LABEL = {
    draft: '未开始',
    running: '进行中',
    paused: '已暂停',
    expired: '已到计划时长',
    completed: '已完成',
    interrupted: '已中断',
    failed: '失败'
  };

  var els = {};
  var current = null;   // 当前任务对象
  var history = [];     // 已结束任务（最多 MAX_HISTORY 条）
  var events = [];      // 事件流水（最多 MAX_EVENTS 条）
  var memoryOnly = false;
  var tickHandle = null;
  var mounted = false;

  // ------------------------------------------------------------- helpers

  function byId(id) { return document.getElementById(id); }

  function nowMs() { return Date.now(); }

  function todayKey(ts) {
    var d = new Date(ts);
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  }

  function pad2(n) { return (n < 10 ? '0' : '') + n; }

  function fmtClock(totalSeconds) {
    var s = Math.max(0, Math.floor(totalSeconds));
    var m = Math.floor(s / 60);
    var r = s % 60;
    return (m < 10 ? '0' : '') + m + ':' + (r < 10 ? '0' : '') + r;
  }

  function fmtStamp(ts) {
    var d = new Date(ts);
    return pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) + ' ' +
      pad2(d.getHours()) + ':' + pad2(d.getMinutes());
  }

  function trimmedName(raw) {
    if (typeof raw !== 'string') return '';
    // 去掉控制字符与首尾空白；不改变其它字符（XSS 一律靠 textContent 兜底）
    return raw.replace(/[\u0000-\u001f\u007f]/g, '').trim();
  }

  function clampMinutes(v) {
    var n = parseInt(v, 10);
    if (!isFinite(n) || n < 0) n = 0;
    if (n > 1440) n = 1440;
    return n;
  }

  // --------------------------------------------------------- storage I/O

  function showStorageError(msg) {
    if (!els.storageError) return;
    els.storageError.textContent = msg;
    els.storageError.hidden = false;
  }

  function clearStorageError() {
    if (!els.storageError) return;
    els.storageError.textContent = '';
    els.storageError.hidden = true;
  }

  function readStore() {
    var raw;
    try {
      raw = window.localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      memoryOnly = true;
      showStorageError('本地存储不可用（浏览器拒绝访问 localStorage）：本次记录仅保存在当前页面内存中，刷新后会丢失。');
      return;
    }
    if (!raw) return;
    var data;
    try {
      data = JSON.parse(raw);
    } catch (e) {
      // 腐败 JSON：不静默吞掉，明确提示并从空状态开始
      try { window.localStorage.removeItem(STORAGE_KEY); } catch (e2) { /* ignore */ }
      showStorageError('本地记录无法解析，已重置为空白。可继续使用，但旧记录已不可恢复。');
      return;
    }
    if (!data || typeof data !== 'object') return;
    if (Array.isArray(data.history)) {
      history = data.history.filter(function (h) {
        return h && typeof h === 'object' && typeof h.name === 'string';
      }).slice(-MAX_HISTORY);
    }
    if (Array.isArray(data.events)) {
      events = data.events.filter(function (e) {
        return e && typeof e === 'object';
      }).slice(-MAX_EVENTS);
    }
    if (data.current && typeof data.current === 'object' &&
        typeof data.current.name === 'string') {
      current = sanitizeCurrent(data.current);
    }
  }

  function sanitizeCurrent(c) {
    var status = STATUS_LABEL[c.status] ? c.status : 'draft';
    var planned = (c.plannedMinutes === 55) ? 55 : 25;
    return {
      name: String(c.name).slice(0, MAX_NAME),
      category: c.category === 'entertainment' ? 'entertainment' : 'study',
      plannedMinutes: planned,
      status: status,
      startedAt: (typeof c.startedAt === 'number' && isFinite(c.startedAt)) ? c.startedAt : 0,
      accumulatedMs: (typeof c.accumulatedMs === 'number' && isFinite(c.accumulatedMs) && c.accumulatedMs > 0) ? c.accumulatedMs : 0,
      selfReportedMinutes: clampMinutes(c.selfReportedMinutes),
      createdAt: (typeof c.createdAt === 'number' && isFinite(c.createdAt)) ? c.createdAt : nowMs()
    };
  }

  function writeStore() {
    if (memoryOnly) return false;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
        v: 1,
        current: current,
        history: history,
        events: events
      }));
      return true;
    } catch (e) {
      memoryOnly = true;
      showStorageError('本地保存失败（可能是存储空间已满或浏览器限制）：本次改动仅保存在内存中，刷新后会丢失。');
      return false;
    }
  }

  // ------------------------------------------------------------- events

  function pushEvent(status, name, extraMinutes) {
    events.push({
      t: nowMs(),
      s: status,
      n: name,
      m: (typeof extraMinutes === 'number') ? extraMinutes : 0
    });
    if (events.length > MAX_EVENTS) events = events.slice(-MAX_EVENTS);
  }

  // ----------------------------------------------------------- timing

  function elapsedMs() {
    if (!current) return 0;
    var base = current.accumulatedMs || 0;
    if (current.status === 'running' && current.startedAt) {
      base += Math.max(0, nowMs() - current.startedAt);
    }
    return base;
  }

  function plannedSeconds() {
    return current ? current.plannedMinutes * 60 : 0;
  }

  function remainingSeconds() {
    if (!current) return 0;
    return Math.max(0, plannedSeconds() - Math.floor(elapsedMs() / 1000));
  }

  function stopTicking() {
    if (tickHandle) {
      window.clearInterval(tickHandle);
      tickHandle = null;
    }
  }

  function startTicking() {
    stopTicking();
    tickHandle = window.setInterval(tick, TICK_MS);
  }

  function tick() {
    if (!current || current.status !== 'running') { stopTicking(); return; }
    if (remainingSeconds() <= 0) {
      // 计时到 0：只停止，不自动完成
      current.status = 'expired';
      current.accumulatedMs = plannedSeconds() * 1000;
      current.startedAt = 0;
      pushEvent('expired', current.name, 0);
      writeStore();
      stopTicking();
      render();
      return;
    }
    renderTimer();
  }

  // ------------------------------------------------------ state machine

  function createTask(name, category, minutes) {
    current = {
      name: name,
      category: category,
      plannedMinutes: minutes,
      status: 'draft',
      startedAt: 0,
      accumulatedMs: 0,
      selfReportedMinutes: 0,
      createdAt: nowMs()
    };
    pushEvent('draft', name, 0);
    writeStore();
    render();
  }

  function startTask() {
    if (!current || current.status !== 'draft') return false;
    current.status = 'running';
    current.startedAt = nowMs();
    pushEvent('running', current.name, 0);
    writeStore();
    startTicking();
    render();
    return true;
  }

  function pauseTask() {
    if (!current || current.status !== 'running') return false;
    current.accumulatedMs = elapsedMs();
    current.startedAt = 0;
    current.status = 'paused';
    pushEvent('paused', current.name, 0);
    writeStore();
    stopTicking();
    render();
    return true;
  }

  function resumeTask() {
    if (!current || current.status !== 'paused') return false;
    current.status = 'running';
    current.startedAt = nowMs();
    pushEvent('running', current.name, 0);
    writeStore();
    startTicking();
    render();
    return true;
  }

  function readSelfReported() {
    if (!current || current.category !== 'study') return 0;
    if (!els.selfMinutes) return 0;
    return clampMinutes(els.selfMinutes.value);
  }

  function finishTask(status) {
    if (!current) return false;
    if (['running', 'paused', 'expired'].indexOf(current.status) === -1) return false;
    current.accumulatedMs = elapsedMs();
    current.startedAt = 0;
    current.status = status;
    current.selfReportedMinutes = readSelfReported();
    var entry = {
      name: current.name,
      category: current.category,
      plannedMinutes: current.plannedMinutes,
      status: status,
      endedAt: nowMs(),
      day: todayKey(nowMs()),
      selfReportedMinutes: current.selfReportedMinutes
    };
    history.push(entry);
    if (history.length > MAX_HISTORY) history = history.slice(-MAX_HISTORY);
    pushEvent(status, current.name, current.selfReportedMinutes);
    writeStore();
    stopTicking();
    render();
    return true;
  }

  function resetForNewTask() {
    current = null;
    writeStore();
    if (els.nameInput) els.nameInput.value = '';
    if (els.selfMinutes) els.selfMinutes.value = '0';
    render();
    if (els.nameInput) els.nameInput.focus();
  }

  // -------------------------------------------------------------- stats

  function todayStats() {
    var today = todayKey(nowMs());
    var done = 0;
    var self = 0;
    history.forEach(function (h) {
      if (h.status !== 'completed') return;
      if (h.day !== today) return;
      done += 1;
      self += (h.category === 'study') ? (h.selfReportedMinutes || 0) : 0;
    });
    return { done: done, self: self };
  }

  // ------------------------------------------------------------- render

  function renderTimer() {
    if (els.remaining) {
      if (!current) { els.remaining.textContent = '--:--'; }
      else { els.remaining.textContent = fmtClock(remainingSeconds()); }
    }
    renderHomeStatus();
  }

  // --------------------------------------- 首页「当前自由任务」只读状态条
  //
  // 这是本模块 current / elapsedMs / remainingSeconds / tick 的**只读展示层**，
  // 不是第二个计时器：没有新增 setInterval、没有新增数据源、没有事件循环。
  //
  // 规则（刻意保持安静）：
  // - 无活动，或活动处于 draft / completed / interrupted / failed → 隐藏；
  // - running：显示剩余时间，随已有 250ms tick 实时递减（导航到抽卡页也继续刷新）；
  // - paused：剩余时间固定；expired：显示「已到计划时长」，绝不自动完成。
  //
  // 只读：只写 textContent 与 hidden 属性，不 append events、不 POST、
  // 不写 localStorage，也不碰旧 dock / 旧计时器 / 抽卡按钮。
  var HOME_SHOWN_STATUS = { running: true, paused: true, expired: true };

  function renderHomeStatus() {
    if (!els.homeStatus) return;
    var visible = !!current && HOME_SHOWN_STATUS[current.status] === true;
    if (!visible) {
      if (!els.homeStatus.hidden) {
        els.homeStatus.hidden = true;
        if (els.homeStatusText) els.homeStatusText.textContent = '';
        if (els.homeStatusClock) els.homeStatusClock.textContent = '';
      }
      return;
    }
    els.homeStatus.hidden = false;

    // 无障碍：状态区（aria-live=polite）只在**名称/状态变化**时改写，
    // 每 250ms 变动的秒数放在独立 aria-hidden 视觉 span，避免高频报时。
    var head = '自由任务：' + current.name + ' · ' + (STATUS_LABEL[current.status] || current.status);
    if (els.homeStatusText && els.homeStatusText.textContent !== head) {
      els.homeStatusText.textContent = head;   // 活动名一律 textContent，HTML 只当字面量
    }
    if (els.homeStatusClock) {
      els.homeStatusClock.textContent = (current.status === 'expired')
        ? ' · 已停止计时'
        : ' · 剩余 ' + fmtClock(remainingSeconds());
    }
  }

  function renderStatusNotice() {
    if (!els.notice) return;
    if (!current) { els.notice.textContent = ''; return; }
    switch (current.status) {
      case 'draft':
        els.notice.textContent = '草稿：点击「开始」后本机才开始计时。';
        break;
      case 'running':
        els.notice.textContent = '计时中 · 刷新页面后按真实墙钟继续 · 计时到 0 会停止，但不会自动完成。';
        break;
      case 'paused':
        els.notice.textContent = '已暂停 · 暂停期间的墙钟时间不计入任何学习分钟。';
        break;
      case 'expired':
        els.notice.textContent = '已到计划时长，计时已停止（不会自动完成）。请选择「明确完成 / 中断 / 失败」。';
        break;
      case 'completed':
        els.notice.textContent = '已完成 · 已记入本地记录（仅本浏览器）。';
        break;
      case 'interrupted':
        els.notice.textContent = '已中断 · 已记入本地记录（仅本浏览器）。';
        break;
      case 'failed':
        els.notice.textContent = '失败 · 已记入本地记录（仅本浏览器）。';
        break;
      default:
        els.notice.textContent = '';
    }
  }

  function renderButtons() {
    var st = current ? current.status : null;
    var setState = function (btn, enabled) {
      if (!btn) return;
      btn.disabled = !enabled;
    };
    setState(els.startBtn, st === 'draft');
    setState(els.pauseBtn, st === 'running');
    setState(els.resumeBtn, st === 'paused');
    setState(els.completeBtn, st === 'running' || st === 'paused' || st === 'expired');
    setState(els.interruptBtn, st === 'running' || st === 'paused' || st === 'expired');
    setState(els.failBtn, st === 'running' || st === 'paused' || st === 'expired');
    if (els.resetBtn) {
      var terminal = st === 'completed' || st === 'interrupted' || st === 'failed';
      els.resetBtn.classList.toggle('hidden', !terminal);
    }
    if (els.form) els.form.hidden = !!current;
    if (els.current) els.current.hidden = !current;
  }

  function renderSelfHint() {
    if (!els.selfHint) return;
    if (!current) {
      els.selfHint.textContent = '创建任务后可填写自报学习分钟；该数值未独立核实，也不计入服务端已验证学习分钟。';
      return;
    }
    if (current.category === 'entertainment') {
      els.selfHint.textContent = '娱乐类不计自报学习分钟，恒为 0。';
      return;
    }
    if (current.status === 'completed' || current.status === 'interrupted' || current.status === 'failed') {
      els.selfHint.textContent = '本条记录的自报学习分钟：' + (current.selfReportedMinutes || 0) + '（未独立核实）。';
      return;
    }
    els.selfHint.textContent = '自报学习分钟（未独立核实）：只在你手动填写后才记录，暂停 / 恢复不会自动累加。';
  }

  function renderHistory() {
    if (!els.historyList) return;
    while (els.historyList.firstChild) els.historyList.removeChild(els.historyList.firstChild);
    var recent = events.slice(-10).reverse();
    if (!recent.length) {
      var li = document.createElement('li');
      li.textContent = '暂无本地记录。';
      els.historyList.appendChild(li);
      return;
    }
    recent.forEach(function (e) {
      var item = document.createElement('li');
      var label = STATUS_LABEL[e.s] || e.s;
      var text = fmtStamp(e.t) + ' · ' + label + ' · ' + e.n;
      if (e.m > 0) text += '（自报 ' + e.m + ' 分钟，未独立核实）';
      item.textContent = text;
      els.historyList.appendChild(item);
    });
  }

  function renderStats() {
    var s = todayStats();
    if (els.statDone) els.statDone.textContent = String(s.done);
    if (els.statSelf) els.statSelf.textContent = String(s.self);
  }

  function render() {
    if (els.stateBadge) {
      els.stateBadge.textContent = current ? (STATUS_LABEL[current.status] || current.status) : '未开始';
    }
    if (els.currentName) {
      els.currentName.textContent = current ? current.name : '';
    }
    if (els.meta) {
      if (!current) {
        els.meta.textContent = '';
      } else {
        var catText = current.category === 'entertainment' ? '娱乐' : '学习';
        var extra = current.status === 'completed'
          ? ' · 状态：已完成'
          : '';
        els.meta.textContent = '类别：' + catText + ' · 计划时长：' + current.plannedMinutes +
          ' 分钟 · 已用时：' + fmtClock(Math.floor(elapsedMs() / 1000)) + extra;
      }
    }
    if (els.selfMinutes) {
      if (!current) {
        els.selfMinutes.value = '0';
        els.selfMinutes.disabled = true;
      } else if (current.category === 'entertainment') {
        els.selfMinutes.value = '0';
        els.selfMinutes.disabled = true;
      } else {
        els.selfMinutes.disabled = (current.status === 'completed' ||
          current.status === 'interrupted' || current.status === 'failed');
        if (current.status === 'completed' || current.status === 'interrupted' || current.status === 'failed') {
          els.selfMinutes.value = String(current.selfReportedMinutes || 0);
        }
      }
    }
    renderStatusNotice();
    renderButtons();
    renderSelfHint();
    renderStats();
    renderHistory();
    renderTimer();
  }

  function showError(msg) {
    if (!els.error) return;
    els.error.textContent = msg;
    els.error.hidden = false;
  }

  function clearError() {
    if (!els.error) return;
    els.error.textContent = '';
    els.error.hidden = true;
  }

  // -------------------------------------------------------------- wiring

  function selectedValue(name) {
    var nodes = document.getElementsByName(name);
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].checked) return nodes[i].value;
    }
    return null;
  }

  function onSubmit(ev) {
    ev.preventDefault();
    clearError();
    var name = trimmedName(els.nameInput ? els.nameInput.value : '');
    if (!name) {
      showError('活动名称不能为空，请先填写再创建。');
      if (els.nameInput) els.nameInput.focus();
      return;
    }
    if (name.length > MAX_NAME) name = name.slice(0, MAX_NAME);
    var category = selectedValue('freeTaskCategory') === 'entertainment' ? 'entertainment' : 'study';
    var minutes = selectedValue('freeTaskMinutes') === '55' ? 55 : 25;
    createTask(name, category, minutes);
    if (els.startBtn) els.startBtn.focus();
  }

  function onClearClick() {
    if (!els.confirmBox) return;
    els.confirmBox.hidden = false;
    if (els.clearConfirmBtn) els.clearConfirmBtn.focus();
  }

  function onClearCancel() {
    if (els.confirmBox) els.confirmBox.hidden = true;
    if (els.clearBtn) els.clearBtn.focus();
  }

  function onClearConfirm() {
    if (els.confirmBox) els.confirmBox.hidden = true;
    hideImportConfirm();
    clearBackupError();
    showBackupStatus('已清理本浏览器的自由任务记录；之前导出的 JSON 备份文件不受影响，可用它恢复。');
    history = [];
    events = [];
    current = null;
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      memoryOnly = true;
      showStorageError('清理失败（浏览器拒绝访问 localStorage）：当前页面内存中的记录已清空，但浏览器存储可能仍保留旧数据。');
    }
    if (els.nameInput) els.nameInput.value = '';
    if (els.selfMinutes) els.selfMinutes.value = '0';
    render();
    if (els.nameInput) els.nameInput.focus();
  }

  // ------------------------------------------------- 本地备份（导出/导入）
  //
  // 边界（必须诚实）：
  // - 只读写本模块唯一的 localStorage 键 SAL_FREE_TASK_LOCAL_V1；
  //   不读其它 key、不发任何网络请求、不写服务器文件、不写 data/。
  // - 导出只是把内存中的快照序列化成本机 JSON 文件；**不改变**正在进行的
  //   活动状态（快照另存，不修改 current 本身）。
  // - 导出快照会**冻结**运行中任务的已用时并清零 startedAt，这样导入时
  //   绝不会用两台设备之间的墙钟差自动流逝计时。
  // - 导入必须先校验、再经用户显式二次确认才写入；非法文件一律拒绝，
  //   并且绝不覆盖原有存储。
  // - 导入后的任务仍只是本地记录：不产生新事件、不计入抽卡 / 番茄 /
  //   服务端已验证学习分钟。

  var MAX_IMPORT_BYTES = 256 * 1024;   // 备份文件上限 256 KiB
  var IMPORTABLE_STATUS = ['draft', 'running', 'paused', 'expired', 'completed', 'interrupted', 'failed'];
  var pendingImport = null;            // 待用户二次确认的导入快照

  function hasRecords() {
    return !!current || history.length > 0 || events.length > 0;
  }

  function showBackupStatus(msg) {
    if (!els.backupStatus) return;
    els.backupStatus.textContent = msg || '';
  }

  function showBackupError(msg) {
    if (!els.backupError) return;
    els.backupError.textContent = msg;
    els.backupError.hidden = false;
  }

  function clearBackupError() {
    if (!els.backupError) return;
    els.backupError.textContent = '';
    els.backupError.hidden = true;
  }

  function hideImportConfirm() {
    if (els.importConfirmBox) els.importConfirmBox.hidden = true;
    pendingImport = null;
  }

  /** 导出用快照：复制 current，并把运行中计时冻结为「累计已用时」。 */
  function snapshotCurrent() {
    if (!current) return null;
    var copy = {};
    Object.keys(current).forEach(function (k) { copy[k] = current[k]; });
    if (copy.status === 'running') {
      copy.accumulatedMs = elapsedMs();
      copy.startedAt = 0;   // 快照内不留墙钟起点，导入端无法自行流逝
    }
    return copy;
  }

  function exportBackup() {
    clearBackupError();
    if (!hasRecords()) {
      showBackupError('当前没有可导出的自由任务记录：先在本面板创建并结束一个自由任务，再导出备份。');
      showBackupStatus('');
      return;
    }
    var payload;
    try {
      payload = {
        v: 1,
        current: snapshotCurrent(),
        history: JSON.parse(JSON.stringify(history)),
        events: JSON.parse(JSON.stringify(events))
      };
    } catch (e) {
      showBackupError('导出失败：无法序列化当前记录（' + '记录结构异常' + '），请先截图保存关键信息。');
      showBackupStatus('');
      return;
    }
    var text;
    try {
      text = JSON.stringify(payload, null, 2);
    } catch (e) {
      showBackupError('导出失败：本机 JSON 序列化失败，未生成任何文件，现有记录未改变。');
      showBackupStatus('');
      return;
    }
    var blob = new Blob([text], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'sal-free-task-backup-' + todayKey(nowMs()) + '.json';
    a.rel = 'noopener';
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    window.setTimeout(function () {
      if (a.parentNode) a.parentNode.removeChild(a);
      URL.revokeObjectURL(url);
    }, 0);
    var head = payload.current ? '1 条进行中/当前活动' : '无进行中活动';
    showBackupStatus('已在浏览器下载 ' + a.download + '（' + head + '，' +
      payload.history.length + ' 条历史、' + payload.events.length + ' 条事件）。' +
      '备份文件仅在本机生成，不上传服务器。');
  }

  function isPlainObject(v) {
    return !!v && typeof v === 'object' && !Array.isArray(v);
  }

  function isFiniteNumber(v) {
    return typeof v === 'number' && isFinite(v);
  }

  function isHistoryEntry(h) {
    return isPlainObject(h) &&
      typeof h.name === 'string' && h.name.length > 0 && h.name.length <= MAX_NAME &&
      (h.category === 'study' || h.category === 'entertainment') &&
      (h.plannedMinutes === 25 || h.plannedMinutes === 55) &&
      IMPORTABLE_STATUS.indexOf(h.status) !== -1 &&
      isFiniteNumber(h.endedAt) &&
      typeof h.day === 'string' && h.day.length > 0 &&
      isFiniteNumber(h.selfReportedMinutes) &&
      h.selfReportedMinutes >= 0 && h.selfReportedMinutes <= 1440;
  }

  function isEventEntry(e) {
    return isPlainObject(e) &&
      isFiniteNumber(e.t) &&
      IMPORTABLE_STATUS.indexOf(e.s) !== -1 &&
      typeof e.n === 'string' && e.n.length <= MAX_NAME &&
      isFiniteNumber(e.m) && e.m >= 0 && e.m <= 1440;
  }

  function isCurrentEntry(c) {
    return isPlainObject(c) &&
      typeof c.name === 'string' && c.name.length > 0 && c.name.length <= MAX_NAME &&
      (c.category === 'study' || c.category === 'entertainment') &&
      (c.plannedMinutes === 25 || c.plannedMinutes === 55) &&
      IMPORTABLE_STATUS.indexOf(c.status) !== -1 &&
      isFiniteNumber(c.startedAt) && c.startedAt >= 0 &&
      isFiniteNumber(c.accumulatedMs) && c.accumulatedMs >= 0 &&
      isFiniteNumber(c.selfReportedMinutes) && c.selfReportedMinutes >= 0 && c.selfReportedMinutes <= 1440 &&
      isFiniteNumber(c.createdAt) && c.createdAt >= 0;
  }

  /** 严格校验：不合格一律拒绝，不做任何「猜测修复」。 */
  function validateBackup(data) {
    if (!isPlainObject(data)) return { ok: false, message: '备份内容不是一个 JSON 对象，已拒绝导入。' };
    if (data.v !== 1) return { ok: false, message: '备份版本不支持（需要 v=1，实际 v=' + String(data.v) + '），已拒绝导入。' };
    if (!('history' in data) || !Array.isArray(data.history)) {
      return { ok: false, message: '备份缺少合法的 history 数组，已拒绝导入。' };
    }
    if (!('events' in data) || !Array.isArray(data.events)) {
      return { ok: false, message: '备份缺少合法的 events 数组，已拒绝导入。' };
    }
    if (data.history.length > MAX_HISTORY) {
      return { ok: false, message: '备份包含 ' + data.history.length + ' 条历史，超过上限 ' + MAX_HISTORY + ' 条，已拒绝导入。' };
    }
    if (data.events.length > MAX_EVENTS) {
      return { ok: false, message: '备份包含 ' + data.events.length + ' 条事件，超过上限 ' + MAX_EVENTS + ' 条，已拒绝导入。' };
    }
    if (!('current' in data) || (data.current !== null && !isCurrentEntry(data.current))) {
      return { ok: false, message: '备份的 current 字段不合法，已拒绝导入。' };
    }
    for (var i = 0; i < data.history.length; i++) {
      if (!isHistoryEntry(data.history[i])) {
        return { ok: false, message: '备份第 ' + (i + 1) + ' 条历史记录格式不合法，已拒绝导入。' };
      }
    }
    for (var j = 0; j < data.events.length; j++) {
      if (!isEventEntry(data.events[j])) {
        return { ok: false, message: '备份第 ' + (j + 1) + ' 条事件格式不合法，已拒绝导入。' };
      }
    }
    return { ok: true, data: data };
  }

  function readFileText(file) {
    if (file && typeof file.text === 'function') return file.text();
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(String(reader.result)); };
      reader.onerror = function () { reject(new Error('read failed')); };
      reader.readAsText(file);
    });
  }

  function onImportFileChange() {
    clearBackupError();
    hideImportConfirm();
    showBackupStatus('');
    var file = els.importFile && els.importFile.files ? els.importFile.files[0] : null;
    // 清空选择，允许用户再次选择同一个文件时仍能触发 change
    if (els.importFile) els.importFile.value = '';
    if (!file) return;
    if (file.size > MAX_IMPORT_BYTES) {
      showBackupError('备份文件过大（' + file.size + ' 字节，上限 ' + MAX_IMPORT_BYTES + ' 字节），已拒绝导入，现有本地记录未改变。');
      return;
    }
    readFileText(file).then(function (text) {
      var parsed;
      try {
        parsed = JSON.parse(text);
      } catch (e) {
        showBackupError('无法解析该文件为 JSON：不是有效的备份文件，已拒绝导入，现有本地记录未改变。');
        return;
      }
      var check = validateBackup(parsed);
      if (!check.ok) {
        showBackupError(check.message + ' 现有本地记录未改变。');
        return;
      }
      pendingImport = check.data;
      var cur = check.data.current;
      var curText = cur ? ('1 条当前活动（' + STATUS_LABEL[cur.status] + '：' + cur.name + '）') : '无当前活动';
      if (cur && cur.status === 'running') {
        curText = '1 条当前活动（导出时为进行中，导入后会恢复为「已暂停」，已用时按导出那一刻的快照，不按导入时的墙钟流逝）';
      }
      if (els.importConfirmText) {
        els.importConfirmText.textContent = '确认用该备份覆盖现有本地记录？备份含 ' + curText + '、' +
          check.data.history.length + ' 条历史、' + check.data.events.length + ' 条事件。覆盖后旧记录无法从浏览器找回。';
      }
      if (els.importConfirmBox) els.importConfirmBox.hidden = false;
      showBackupStatus('已读取本机文件 ' + file.name + '，等待你确认覆盖。文件不会离开本机。');
      if (els.importConfirmBtn) els.importConfirmBtn.focus();
    }, function () {
      showBackupError('读取该文件失败（浏览器无法读取所选文件），已拒绝导入，现有本地记录未改变。');
    });
  }

  /** 只写入本模块自己的键；失败时不吞错、不改内存/UI。 */
  function persistSnapshot(cur, hist, evts) {
    if (memoryOnly) {
      return { ok: false, message: '本地存储不可用（浏览器拒绝访问 localStorage），导入未保存；现有记录仍只在当前页面内存中，刷新后会丢失。' };
    }
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
        v: 1, current: cur, history: hist, events: evts
      }));
      return { ok: true };
    } catch (e) {
      return {
        ok: false,
        message: '写入本地存储失败（可能是存储空间已满或浏览器限制）：导入未保存，现有本地记录保持不变，页面内记录也保持原样。'
      };
    }
  }

  function onImportConfirm() {
    clearBackupError();
    if (!pendingImport) {
      hideImportConfirm();
      showBackupStatus('没有待导入的备份，请重新选择文件。');
      return;
    }
    var data = pendingImport;
    var wasRunning = !!(data.current && data.current.status === 'running');
    var importedCurrent = data.current ? sanitizeCurrent(data.current) : null;
    if (importedCurrent && wasRunning) {
      // 运行中任务导入后一律转为已暂停；已用时沿用导出快照，绝不跨设备流逝
      importedCurrent.status = 'paused';
      importedCurrent.startedAt = 0;
    }
    var result = persistSnapshot(importedCurrent, data.history, data.events);
    hideImportConfirm();
    if (!result.ok) {
      showBackupError(result.message);
      showBackupStatus('');
      render();
      return;
    }
    stopTicking();
    current = importedCurrent;
    history = data.history.slice(-MAX_HISTORY);
    events = data.events.slice(-MAX_EVENTS);
    if (els.nameInput) els.nameInput.value = '';
    if (els.selfMinutes) els.selfMinutes.value = '0';
    render();
    var msg = '导入完成：已用备份覆盖本浏览器的自由任务记录（' +
      history.length + ' 条历史、' + events.length + ' 条事件）。记录仍只在本机，不是服务端已验证数据。';
    if (wasRunning) {
      msg += '备份中正在进行的任务已恢复为「已暂停」，已用时按导出快照保留，导入期间不会自动流逝、也不会自动完成。';
    }
    showBackupStatus(msg);
  }

  function onImportCancel() {
    hideImportConfirm();
    clearBackupError();
    showBackupStatus('已取消导入：现有本地记录未做任何修改。');
    if (els.importBtn) els.importBtn.focus();
  }

  function collect() {
    els.form = byId('freeTaskForm');
    els.nameInput = byId('freeTaskName');
    els.error = byId('freeTaskError');
    els.storageError = byId('freeTaskStorageError');
    els.current = byId('freeTaskCurrent');
    els.currentName = byId('freeTaskCurrentName');
    els.remaining = byId('freeTaskRemaining');
    els.meta = byId('freeTaskMeta');
    els.notice = byId('freeTaskNotice');
    els.stateBadge = byId('freeTaskStateBadge');
    els.startBtn = byId('freeTaskStartBtn');
    els.pauseBtn = byId('freeTaskPauseBtn');
    els.resumeBtn = byId('freeTaskResumeBtn');
    els.completeBtn = byId('freeTaskCompleteBtn');
    els.interruptBtn = byId('freeTaskInterruptBtn');
    els.failBtn = byId('freeTaskFailBtn');
    els.resetBtn = byId('freeTaskResetBtn');
    els.selfMinutes = byId('freeTaskSelfMinutes');
    els.selfHint = byId('freeTaskSelfHint');
    els.statDone = byId('freeTaskStatDone');
    els.statSelf = byId('freeTaskStatSelf');
    els.historyList = byId('freeTaskHistoryList');
    els.clearBtn = byId('freeTaskClearBtn');
    els.clearConfirmBtn = byId('freeTaskClearConfirmBtn');
    els.clearCancelBtn = byId('freeTaskClearCancelBtn');
    els.confirmBox = byId('freeTaskConfirmBox');
    els.exportBtn = byId('freeTaskExportBtn');
    els.importBtn = byId('freeTaskImportBtn');
    els.importFile = byId('freeTaskImportFile');
    els.backupStatus = byId('freeTaskBackupStatus');
    els.backupError = byId('freeTaskBackupError');
    els.importConfirmBox = byId('freeTaskImportConfirmBox');
    els.importConfirmText = byId('freeTaskImportConfirmText');
    els.importConfirmBtn = byId('freeTaskImportConfirmBtn');
    els.importCancelBtn = byId('freeTaskImportCancelBtn');
    // 首页只读状态条（LT_RETENTION_FREE_TASK_HOME_STATUS_20261023_T）：节点可能不存在，属渐进增强
    els.homeStatus = byId('freeTaskHomeStatus');
    els.homeStatusText = byId('freeTaskHomeStatusText');
    els.homeStatusClock = byId('freeTaskHomeStatusClock');
  }

  function wire() {
    if (els.form) els.form.addEventListener('submit', onSubmit);
    if (els.startBtn) els.startBtn.addEventListener('click', function () { startTask(); });
    if (els.pauseBtn) els.pauseBtn.addEventListener('click', function () { pauseTask(); });
    if (els.resumeBtn) els.resumeBtn.addEventListener('click', function () { resumeTask(); });
    if (els.completeBtn) els.completeBtn.addEventListener('click', function () { finishTask('completed'); });
    if (els.interruptBtn) els.interruptBtn.addEventListener('click', function () { finishTask('interrupted'); });
    if (els.failBtn) els.failBtn.addEventListener('click', function () { finishTask('failed'); });
    if (els.resetBtn) els.resetBtn.addEventListener('click', resetForNewTask);
    if (els.clearBtn) els.clearBtn.addEventListener('click', onClearClick);
    if (els.clearConfirmBtn) els.clearConfirmBtn.addEventListener('click', onClearConfirm);
    if (els.clearCancelBtn) els.clearCancelBtn.addEventListener('click', onClearCancel);
    if (els.exportBtn) els.exportBtn.addEventListener('click', exportBackup);
    if (els.importBtn) {
      els.importBtn.addEventListener('click', function () {
        clearBackupError();
        showBackupStatus('');
        if (els.importFile) els.importFile.click();
      });
    }
    if (els.importFile) els.importFile.addEventListener('change', onImportFileChange);
    if (els.importConfirmBtn) els.importConfirmBtn.addEventListener('click', onImportConfirm);
    if (els.importCancelBtn) els.importCancelBtn.addEventListener('click', onImportCancel);
    if (els.selfMinutes) {
      els.selfMinutes.addEventListener('change', function () {
        if (!current || current.category !== 'study') return;
        if (['completed', 'interrupted', 'failed'].indexOf(current.status) >= 0) return;
        current.selfReportedMinutes = readSelfReported();
        writeStore();
      });
    }
  }

  function init() {
    if (mounted) return;
    var panel = byId('freeTaskPanel');
    if (!panel) return;
    mounted = true;
    collect();
    if (!els.form) return;
    readStore();
    // 刷新恢复：running 任务按真实墙钟继续；若已超时则降级为 expired（不自动完成）
    if (current && current.status === 'running') {
      if (remainingSeconds() <= 0) {
        current.status = 'expired';
        current.accumulatedMs = plannedSeconds() * 1000;
        current.startedAt = 0;
        pushEvent('expired', current.name, 0);
        writeStore();
      } else {
        startTicking();
      }
    }
    wire();
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
