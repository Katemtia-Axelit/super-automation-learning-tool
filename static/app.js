
"use strict";

// ============ 全局错误捕获 ============
window.onerror = function (m, s, l) {
  console.error('[app.js]', 'L' + l + ':', m, s || '');
  return false;
};

// ============ API CLIENT ============
const API = '';
async function api(url, opts) {
  opts = opts || {};
  var r = await fetch(API + url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts
  });
  var data = {};
  try {
    data = await r.json();
  } catch (e) {
    data = {};
  }
  if (!r.ok) {
    var msg = data.error || data.message || ('请求失败 (' + r.status + ')');
    throw new Error(msg);
  }
  return data;
}

// ============ UI HELPERS ============
function toast(msg, type) {
  type = type || 'inf';
  var c = document.getElementById('toastContainer');
  var d = document.createElement('div');
  d.className = 'toast ' + type;
  d.textContent = msg;
  c.appendChild(d);
  setTimeout(function () { d.remove(); }, 3500);
}
function showModal(id) { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

// ============ 温情文案库 ============
var WARM_MESSAGES = {
  poolEmpty: '今天的你已经完成了所有挑战，明天继续加油！',
  skipped: '好的，这张牌先收起来，随时可以再抽',
  refused: '好的，已经记下来了',
  discarded: '先放一边，等状态好的时候再试试',
  completedEarly: '太棒了，比预计快这么多',
  timeout: '还在努力呢，不着急，慢慢来',
  unlock: '恭喜解锁了新任务'
};

// ============ TASK EVENT FEEDBACK (P1-5B, 简化版) ============
var TASK_FEEDBACK_PRESETS = {
  skip: {
    eventType: 'skip_task',
    question: '这次为什么跳过？',
    options: [
      { label: '精力不足', category: 'state_issue', detail: '精力不足' },
      { label: '时间不够', category: 'time_estimation_issue', detail: '时间不够' },
      { label: '太难了', category: 'ability_issue', detail: '太难了' },
      { label: '其他', category: 'other', detail: '其他' }
    ]
  },
  abandon: {
    eventType: 'abandon_task',
    question: '为什么放弃？',
    options: [
      { label: '状态不好', category: 'state_issue', detail: '状态不好' },
      { label: '被打断了', category: 'external_interrupt', detail: '被打断了' },
      { label: '太复杂了', category: 'time_estimation_issue', detail: '太复杂了' },
      { label: '其他', category: 'other', detail: '其他' }
    ]
  }
};

var _taskFeedbackResolve = null;
var _taskFeedbackContext = null;
var _taskFeedbackPresetKey = null;

function submitTaskFeedbackEvent(payload) {
  return api('/api/task-feedback', {
    method: 'POST',
    body: JSON.stringify(payload)
  }).catch(function (e) {
    toast(e.message || '反馈保存失败', 'err');
  });
}

function promptTaskFeedback(presetKey, context) {
  var preset = TASK_FEEDBACK_PRESETS[presetKey];
  if (!preset) return Promise.resolve({ saved: false });
  _taskFeedbackContext = context || {};
  _taskFeedbackPresetKey = presetKey;
  document.getElementById('taskFeedbackQuestion').textContent = preset.question;
  var html = preset.options.map(function (opt, idx) {
    return '<label class="feedback-option"><input type="radio" name="taskFbOpt" value="' + idx +
      '"> ' + opt.label + '</label>';
  }).join('');
  document.getElementById('taskFeedbackOptions').innerHTML = html;
  document.getElementById('taskFeedbackNote').value = '';
  showModal('taskFeedbackModal');
  return new Promise(function (resolve) {
    _taskFeedbackResolve = resolve;
  });
}

function confirmTaskFeedbackModal() {
  var selected = document.querySelector('input[name="taskFbOpt"]:checked');
  var ctx = _taskFeedbackContext || {};
  var preset = TASK_FEEDBACK_PRESETS[_taskFeedbackPresetKey];
  var opt = null;
  if (selected) {
    var idx = parseInt(selected.value, 10);
    opt = preset ? preset.options[idx] : null;
  }
  var note = (document.getElementById('taskFeedbackNote').value || '').trim();
  var payload = {
    task_id: ctx.taskId,
    event_type: preset ? preset.eventType : 'unknown',
    planned_minutes: ctx.plannedMinutes,
    actual_minutes: ctx.actualMinutes,
    completion_status: ctx.completionStatus,
    reason_category: opt ? opt.category : 'other',
    reason_detail: opt ? opt.detail : (note || '未选择'),
    note: note || null
  };
  closeModal('taskFeedbackModal');
  var resolve = _taskFeedbackResolve;
  _taskFeedbackResolve = null;
  _taskFeedbackContext = null;
  _taskFeedbackPresetKey = null;
  submitTaskFeedbackEvent(payload).finally(function () {
    if (resolve) resolve({ saved: true });
  });
}

function cancelTaskFeedbackModal() {
  closeModal('taskFeedbackModal');
  var resolve = _taskFeedbackResolve;
  _taskFeedbackResolve = null;
  _taskFeedbackContext = null;
  _taskFeedbackPresetKey = null;
  if (resolve) resolve({ saved: false });
}

function getTaskFeedbackContext(taskId) {
  var task = allTasks.find(function (x) { return x.id === taskId; });
  return {
    taskId: taskId,
    plannedMinutes: task ? task.estimated_time : null,
    actualMinutes: null,
    completionStatus: null
  };
}

// ============ 页面切换 ============
function showPage(id) {
  // 离开页面时清理抽卡动画残留（P0-3 修复）
  if (id !== 'gacha') {
    var flyLayer = document.getElementById('cardFlyLayer');
    if (flyLayer) flyLayer.innerHTML = '';
    var deck = document.getElementById('gachaDeck');
    if (deck) {
      deck.classList.remove('is-drawing');
      deck.classList.remove('is-revealing');
    }
    // P0-3: 清除抽卡结果区里残留 .drawn-card 的 is-drawing 状态
    // 双 rAF 在页面隐藏时可能被节流，导致卡片卡在 is-drawing 永不 is-revealing
    var drawnCards = document.querySelectorAll('#gachaResult .task-card.drawn-card');
    drawnCards.forEach(function (c) {
      c.classList.remove('is-drawing');
    });
    if (window._inlineTimerHandle) {
      clearInterval(window._inlineTimerHandle);
      window._inlineTimerHandle = null;
    }
  }
  document.querySelectorAll('.page').forEach(function (p) { p.classList.remove('active'); });
  document.getElementById('page-' + id).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(function (b) { b.classList.remove('active'); });
  document.querySelector('[data-page="' + id + '"]').classList.add('active');
  if (id === 'gacha') { refreshGachaStats(); updateTimerDock(); }
  if (id === 'tasks') { renderTasks(); loadTags(); loadTimerPanel(); }
  if (id === 'schedule') {
    renderSchedule();
    loadSleepPanel();
    loadStateAssessmentPanel();
  }
  if (id === 'knowledge') loadCategories();
  if (id === 'config') {
    loadConfigForm();
    loadPromptList();
  }
}

function taskNameById(id) {
  var t = allTasks.find(function (x) { return x.id === id; });
  return t ? t.name : ('ID=' + id);
}

function prereqHint(task) {
  if (task.is_unlocked !== false && task.is_unlocked !== 0) return '';
  var ids = task.prerequisite_ids || [];
  if (!ids.length) return '';
  return '等待前置：' + ids.map(taskNameById).join('、');
}

function readSelectedPrereqs() {
  var boxes = document.querySelectorAll('#tfDepList input[type=checkbox]:checked');
  var ids = [];
  boxes.forEach(function (b) {
    var v = parseInt(b.value, 10);
    if (v) ids.push(v);
  });
  return ids;
}

function validatePrereqsLocal(taskId, prereqIds) {
  taskId = parseInt(taskId, 10) || 0;
  prereqIds = prereqIds || [];
  if (taskId && prereqIds.indexOf(taskId) >= 0) {
    return '任务不能依赖自身';
  }
  return null;
}

// ============ 导航事件 ============
document.querySelectorAll('.nav-btn').forEach(function (b) {
  b.addEventListener('click', function () {
    var p = b.dataset.page;
    showPage(p);
  });
});

// ============ 健康检查 ============
setInterval(function () {
  fetch('/api/health').then(function (r) {
    if (r.ok) {
      document.getElementById('apiDot').className = 'dot online';
      document.getElementById('apiStatus').textContent = '已连接';
    } else throw new Error();
  }).catch(function () {
    document.getElementById('apiDot').className = 'dot offline';
    document.getElementById('apiStatus').textContent = '断开';
  });
}, 5000);

document.getElementById('fbEnergy').addEventListener('input', function () {
  document.getElementById('fbEnergyVal').textContent = this.value;
});

// ============ 卡牌主题 ============
var CARD_THEME_SYMBOLS = {
  'theme-math': '\u03A3', 'theme-lang': 'Aa', 'theme-history': '\u23F3',
  'theme-code': '{ }', 'theme-write': '\u270E', 'theme-science': '\u269B',
  'theme-review': '\u21BB', 'theme-default': '\u25C6'
};
var CARD_CORNER_LABELS = { study: '学习', exercise: '运动', work: '工作', life: '生活', other: '其他' };
var CARD_REPEAT_LABELS = { none: '单次', daily: '每日', weekly: '每周', accumulation: '积累' };

function taskTextBlob(task) {
  var tags = (task.tags || []).join(' ');
  return ((task.category || '') + ' ' + tags + ' ' + (task.name || '') + ' ' + (task.description || '')).toLowerCase();
}

function resolveTaskCardTheme(task) {
  var blob = taskTextBlob(task);
  if (/数学|高数|理工|几何|代数|math|calculus/.test(blob)) return 'theme-math';
  if (/英语|语言|单词|托福|雅思|english|language|词汇/.test(blob)) return 'theme-lang';
  if (/历史|记忆|档案|timeline|history|近代|古代/.test(blob)) return 'theme-history';
  if (/编程|程序|代码|python|java|js|技术|terminal|dev|code/.test(blob)) return 'theme-code';
  if (/写作|论文|文章|创作|write|输出|稿/.test(blob)) return 'theme-write';
  if (/科学|物理|化学|生物|实验|science/.test(blob)) return 'theme-science';
  if (task.repeat_type === 'daily' || task.repeat_type === 'weekly' || /复习|回顾|review/.test(blob)) return 'theme-review';
  return 'theme-default';
}

function getTaskCardStatusClass(task) {
  if (task.completed) return 'status-completed';
  if (task.in_discard_pile) return 'status-discarded';
  if (task.is_unlocked === false || task.is_unlocked === 0) return 'status-blocked';
  return 'status-active';
}

// ============ 动画系统 ============
function playCardAnim(taskId, animClasses, ms) {
  ms = ms || 650;
  var classes = animClasses.split(/\s+/).filter(Boolean);
  var el = document.querySelector('.task-card[data-task-id="' + taskId + '"]');
  if (!el) return Promise.resolve();
  classes.forEach(function (c) { el.classList.add(c); });
  return new Promise(function (resolve) {
    setTimeout(function () {
      classes.forEach(function (c) { el.classList.remove(c); });
      resolve();
    }, ms);
  });
}

function cardActButtons(html) {
  return html.replace(/class="btn /g, 'class="btn card-act-btn ');
}

function buildLangPatternHtml() {
  var words = ['verb', 'noun', 'the', 'and', 'word', 'tense', 'phrase', 'read', 'speak'];
  return '<div class="task-card-pattern lang-pattern" aria-hidden="true">' +
    words.map(function (w) { return '<span class="lang-word">' + w + '</span>'; }).join('') +
    '</div>';
}

function buildTaskCardBodyHtml(task, opts) {
  opts = opts || {};
  var theme = resolveTaskCardTheme(task);
  var sym = CARD_THEME_SYMBOLS[theme] || '\u25C6';
  var corner = CARD_CORNER_LABELS[task.category] || '任务';
  var tags = (task.tags || []).map(function (x) {
    return '<span class="badge bg-gold">' + escapeHtml(x) + '</span>';
  }).join('');
  var repeatLbl = CARD_REPEAT_LABELS[task.repeat_type] || '单次';
  var mins = task.estimated_time || '?';
  var priority = task.priority || '?';
  var patternHtml = theme === 'theme-lang'
    ? buildLangPatternHtml()
    : '<div class="task-card-pattern" aria-hidden="true"><span>' + sym + '</span></div>';
  return '<span class="task-card-ornament tl"></span><span class="task-card-ornament tr"></span>' +
    '<span class="task-card-ornament bl"></span><span class="task-card-ornament br"></span>' +
    patternHtml +
    '<div class="task-card-header">' +
    '<div class="task-card-header-main">' +
    '<span class="task-card-corner">' + corner + '</span>' +
    (opts.statusHtml || '') +
    '</div>' +
    '<span class="task-card-mark" title="优先级">P' + priority + '</span>' +
    '</div>' +
    '<div class="task-card-body-zone">' +
    '<div class="task-card-title">' + escapeHtml(task.name) + '</div>' +
    '<div class="task-card-desc">' + escapeHtml((task.description || '').substring(0, opts.descLen || 100)) + '</div>' +
    (opts.blockedNote || '') +
    '<div class="task-card-meta">' +
    '<span class="task-card-stat"><i class="fa-solid fa-clock"></i>' + mins + ' 分</span>' +
    '<span class="task-card-stat stat-priority"><i class="fa-solid fa-star"></i>优先级 ' + priority + '</span>' +
    (opts.showRepeat !== false ? '<span class="task-card-stat"><i class="fa-solid fa-repeat"></i>' + repeatLbl + '</span>' : '') +
    '</div>' +
    (tags ? '<div class="task-card-tags">' + tags + '</div>' : '') +
    '</div>' +
    (opts.actionsHtml ? '<div class="task-card-footer"><div class="task-card-actions card-actions">' +
    cardActButtons(opts.actionsHtml) + '</div></div>' : '');
}

function buildTaskCardHtml(task, opts) {
  var theme = resolveTaskCardTheme(task);
  var status = getTaskCardStatusClass(task);
  return '<div class="task-card card ' + theme + ' ' + status + '" data-task-id="' + task.id + '">' +
    buildTaskCardBodyHtml(task, opts) + '</div>';
}

// ============ 抽卡 ============
var gachaState = { energy: 'medium', pool: 'fragment', canReplace: true, replacedTaskId: null, feedbackMood: 3, currentTaskId: null, selectedTag: '' };
var isDrawing = false;

// 初始化：加载标签到抽卡选择框
async function initGachaTagSelect() {
  var sel = document.getElementById('gachaTagSelect');
  if (!sel) return;
  sel.innerHTML = '<option value="">不限</option>';
  try {
    var tags = await api('/api/tags');
    tags.forEach(function (t) {
      var opt = document.createElement('option');
      opt.value = t.name;
      opt.textContent = t.name + ' (' + t.task_count + ')';
      sel.appendChild(opt);
    });
  } catch (e) { /* ignore */ }
}
initGachaTagSelect();

// 标签选择联动
document.getElementById('gachaTagSelect').addEventListener('change', function () {
  gachaState.selectedTag = this.value;
  var hint = document.getElementById('gachaTagHint');
  hint.textContent = this.value ? '🎯 ' + this.value : '';
});

// 精力和卡池选择保留 JS 逻辑（隐藏 UI 但逻辑可用）
document.querySelectorAll('.energy-btn').forEach(function (b) {
  b.addEventListener('click', function () {
    document.querySelectorAll('.energy-btn').forEach(function (x) { x.classList.remove('active'); });
    b.classList.add('active');
    gachaState.energy = b.dataset.e;
  });
});
document.querySelectorAll('.pool-btn').forEach(function (b) {
  b.addEventListener('click', function () {
    document.querySelectorAll('.pool-btn').forEach(function (x) { x.classList.remove('active'); });
    b.classList.add('active');
    gachaState.pool = b.dataset.pool;
  });
});

// ============ 计时器Dock（主页面常驻）============
var timerDockSession = null;
var timerDockTick = null;
var timerDockPaused = false;
var timerDockPausedElapsed = 0;

function initTimerDock() {
  loadTimerDockActive();
  // 每秒更新
  if (timerDockTick) clearInterval(timerDockTick);
  timerDockTick = setInterval(updateTimerDockDisplay, 1000);
}

async function loadTimerDockActive() {
  try {
    var r = await api('/api/timer/active');
    timerDockSession = r && r.id ? r : null;
    // P3-Bug: 从后端读取 paused 状态（刷新后可恢复）
    timerDockPaused = !!(r && r.is_paused);
    timerDockPausedElapsed = (r && r.paused_seconds) ? r.paused_seconds * 1000 : 0;
    updateTimerDockDisplay();
    // P3-Bug-A: 同步到任务页计时器状态（统一状态源）
    if (timerActiveSession !== timerDockSession) {
      timerActiveSession = timerDockSession;
      if (document.getElementById('page-tasks') && document.getElementById('page-tasks').classList.contains('active')) {
        updateTimerDisplay();
      }
    }
  } catch (e) {
    timerDockSession = null;
    timerDockPaused = false;
    timerDockPausedElapsed = 0;
    updateTimerDockDisplay();
  }
}

function updateTimerDockDisplay() {
  var idleEl = document.getElementById('timerDockIdle');
  var activeEl = document.getElementById('timerDockActive');
  var taskNameEl = document.getElementById('timerDockTaskName');
  var timeEl = document.getElementById('timerDockTime');
  var barEl = document.getElementById('timerDockBar');
  var pauseBtn = document.getElementById('timerDockPauseBtn');

  if (!idleEl || !activeEl) return;

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

async function toggleTimerDockPause() {
  if (!timerDockSession) return;
  if (!timerDockPaused) {
    // P3-Bug-B: 调用后端 API 暂停（持久化）
    try {
      var r = await api('/api/timer/pause', {
        method: 'POST',
        body: JSON.stringify({ session_id: timerDockSession.id })
      });
      timerDockPaused = true;
      timerDockPausedElapsed = (r && r.paused_seconds) ? r.paused_seconds * 1000 : timerDockPausedElapsed;
      // P3-Bug-A: 同步到任务页
      if (timerActiveSession && timerActiveSession.id === timerDockSession.id) {
        timerActiveSession = timerDockSession;
        if (document.getElementById('page-tasks') && document.getElementById('page-tasks').classList.contains('active')) {
          updateTimerDisplay();
        }
      }
    } catch (e) {
      toast(e.message || '暂停失败', 'err');
      return;
    }
  } else {
    // P3-Bug-B: 调用后端 API 恢复（持久化）
    try {
      var r2 = await api('/api/timer/resume', {
        method: 'POST',
        body: JSON.stringify({ session_id: timerDockSession.id })
      });
      timerDockPaused = false;
      // 更新 started_at（后端返回的新起点时间）
      if (r2 && r2.started_at) {
        timerDockSession.started_at = r2.started_at;
      }
      // P3-Bug-A: 同步到任务页
      if (timerActiveSession && timerActiveSession.id === timerDockSession.id) {
        timerActiveSession = timerDockSession;
        if (document.getElementById('page-tasks') && document.getElementById('page-tasks').classList.contains('active')) {
          updateTimerDisplay();
        }
      }
    } catch (e) {
      toast(e.message || '恢复失败', 'err');
      return;
    }
  }
  updateTimerDockDisplay();
}

document.getElementById('timerDockPauseBtn').addEventListener('click', toggleTimerDockPause);
document.getElementById('timerDockStopBtn').addEventListener('click', function () {
  if (!timerDockSession) return;
  stopTimerFromDock(timerDockSession.id);
});

async function stopTimerFromDock(sessionId) {
  if (!confirm('确定提前结束此任务？')) return;
  var session = timerDockSession;
  try {
    if (session && session.id) {
      // P3-Bug-A: 计算实际时间（考虑暂停时间）
      var started = new Date(session.started_at).getTime();
      var elapsedMs = Date.now() - started;
      // 如果当前是暂停状态，用 paused_seconds 计算
      if (timerDockPaused) elapsedMs = timerDockPausedElapsed;
      var actualMin = Math.max(1, Math.round(elapsedMs / 60000));
      // P0-2 (bug 3.4) 修复：提前结束 → result=abandoned，不标记任务为完成
      // 任务保持"可用/未完成"状态，可重新计时；仅 timer_sessions.result='abandoned' 留痕
      await api('/api/timer/complete', {
        method: 'POST',
        body: JSON.stringify({ session_id: session.id, actual_minutes: actualMin, result: 'abandoned', reason: 'early_finish' })
      });
    }
    timerDockSession = null;
    timerActiveSession = null;  // P3-Bug-A: 同步清空
    timerDockPaused = false;
    timerDockPausedElapsed = 0;
    updateTimerDockDisplay();
    updateTimerDisplay();  // P3-Bug-A: 两处 UI 同步更新
    if (session && session.task_id) {
      // P0-2: 不调用 completeWithFeedback（它会把任务标记完成并放入弃牌堆）
      // 任务保持可用，仅刷新列表让 UI 显示最新状态
      await loadTasks();
      await refreshGachaStats();
    } else {
      loadTasks();
      refreshGachaStats();
    }
    toast('已中断任务，任务可重新计时', 'inf');
  } catch (e) {
    toast(e.message || '停止失败', 'err');
  }
}

function updateTimerDock() {
  loadTimerDockActive();
}

// ============ 抽卡主流程 ============
document.getElementById('gachaBtn').addEventListener('click', drawGacha);

async function drawGacha() {
  if (isDrawing) return;
  var btn = document.getElementById('gachaBtn');
  if (btn) btn.disabled = true;
  isDrawing = true;

  var result = document.getElementById('gachaResult');
  var deck = document.getElementById('gachaDeck');
  var flyLayer = document.getElementById('cardFlyLayer');
  // 清掉上一次的飞行卡片残留，防止快速二次抽卡时动画叠层（P0-3）
  if (flyLayer) flyLayer.innerHTML = '';
  // 清掉抽卡结果区，避免新旧卡牌同时显示
  if (result) result.innerHTML = '';
  if (deck) {
    deck.classList.remove('is-drawing');
    deck.classList.remove('is-revealing');
    deck.classList.add('is-drawing');
  }

  try {
    var r = await api('/api/gacha/draw', {
      method: 'POST',
      body: JSON.stringify({
        pool: gachaState.pool,
        energy: gachaState.energy,
        available_time: parseInt(document.getElementById('gachaTimeInput').value, 10) || 25,
        preferred_tag: gachaState.selectedTag || null
      })
    });
    if (r.task) {
      gachaState.canReplace = r.can_replace !== false;
      gachaState.currentTaskId = r.task.id;
      var stage = renderDrawnCard(r.task, 0);
      result.appendChild(stage);
      // 播放飞行动画
      await playCardFlyAnimation(r.task);
      updateDiscardPileVisual();
    } else {
      result.innerHTML = '<div class="empty-state mt24"><i class="fa-solid fa-box-open"></i><p>' + WARM_MESSAGES.poolEmpty + '</p></div>';
      gachaState.currentTaskId = null;
    }
  } catch (e) {
    toast(e.message || '抽卡失败', 'err');
    gachaState.currentTaskId = null;
  }

  if (deck) deck.classList.remove('is-drawing');
  if (btn) btn.disabled = false;
  isDrawing = false;
  refreshGachaStats();
}

// 飞行动画：从牌堆飞向中央
async function playCardFlyAnimation(task) {
  var deck = document.getElementById('gachaDeck');
  var stage = document.querySelector('.drawn-card-stage');
  var flyLayer = document.getElementById('cardFlyLayer');
  if (!deck || !stage || !flyLayer) return;

  var deckRect = deck.getBoundingClientRect();
  var stageRect = stage.getBoundingClientRect();

  // 创建飞行的卡牌（竖向尺寸，用于飞行动画）
  var flyingCard = document.createElement('div');
  flyingCard.className = 'flying-card';
  flyingCard.style.left = deckRect.left + 'px';
  flyingCard.style.top = deckRect.top + 'px';
  flyingCard.style.width = '140px';
  flyingCard.style.height = '98px';
  flyingCard.style.opacity = '0.9';
  flyLayer.appendChild(flyingCard);

  // 等待下一帧
  await new Promise(function(resolve) { requestAnimationFrame(resolve); });

  // 移动到舞台中心（卡片从竖向过渡到横向）
  var targetX = stageRect.left + stageRect.width / 2 - 125;
  var targetY = stageRect.top;

  flyingCard.style.transition = 'all 0.7s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
  flyingCard.style.left = targetX + 'px';
  flyingCard.style.top = targetY + 'px';
  flyingCard.style.width = '250px';
  flyingCard.style.height = '150px';
  flyingCard.style.transform = 'rotate(0deg)';

  await new Promise(function(resolve) { setTimeout(resolve, 700); });

  // 移除飞行卡牌，触发翻牌动画
  flyingCard.remove();
}

function renderDrawnCard(task, idx) {
  var theme = resolveTaskCardTheme(task);
  var urgent = task.deadline && new Date(task.deadline) > new Date() &&
    (new Date(task.deadline) - new Date()) / 86400000 < 1;
  var isOneOff = task.repeat_type === 'none';

  // 抽卡后的操作按钮（noteBtn 内含文件路径，必须双重转义：单引号 + HTML 实体）
  var safeNotePath = task.linked_note_path
    ? task.linked_note_path.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;')
    : '';
  var noteBtn = task.linked_note_path
    ? '<button class="btn" onclick="openNoteFromCard(\'' + safeNotePath + '\')" style="margin-bottom:6px;width:100%;background:rgba(88,166,255,0.15);border-color:rgba(88,166,255,0.4);color:#7ab8ff"><i class="fa-brands fa-markdown"></i> 在Obsidian中打开</button>'
    : '';
  var actions =
    '<button class="btn pri" onclick="startTask(' + task.id + ')" style="margin-bottom:6px;width:100%"><i class="fa-solid fa-play"></i> 开始任务</button>' +
    noteBtn +
    '<button class="btn" onclick="handleSkip(' + task.id + ')" style="margin-bottom:6px;width:100%"><i class="fa-solid fa-forward"></i> 跳过</button>' +
    '<button class="btn danger" onclick="handleRefuse(' + task.id + ')" style="margin-bottom:6px;width:100%"><i class="fa-solid fa-xmark"></i> 拒绝</button>' +
    (gachaState.canReplace ? '<button class="btn" onclick="showReplaceReason(' + task.id + ')" style="width:100%"><i class="fa-solid fa-shuffle"></i> 换一张</button>' : '');

  var wrap = document.createElement('div');
  wrap.className = 'drawn-card-stage';
  var card = document.createElement('div');
  card.className = 'task-card card drawn-card ' + theme + (urgent ? ' urgent' : '') + (isOneOff ? ' is-oneoff' : '');
  card.setAttribute('data-task-id', task.id);
  card.style.animationDelay = (idx * 0.15) + 's';

  // 横向布局：左侧任务信息，右侧操作按钮
  var corner = { study: '学习', exercise: '运动', work: '工作', life: '生活', other: '其他' }[task.category] || '任务';
  var repeatLbl = { none: '单次', daily: '每日', weekly: '每周' }[task.repeat_type] || '单次';
  var safeName = escapeHtml(task.name);
  var safeDesc = escapeHtml((task.description || '').substring(0, 150));
  var safeTagsHtml = (task.tags || []).map(function(x) { return '<span class="badge bg-gold">' + escapeHtml(x) + '</span>'; }).join('');

  var leftHtml =
    '<div class="task-card-header" style="width:100%;border-bottom:1px solid rgba(255,255,255,0.06);padding:8px 10px;background:linear-gradient(180deg,rgba(0,0,0,0.18),transparent)">' +
    '<div style="display:flex;align-items:center;gap:8px">' +
    '<span style="font-size:.68rem;padding:2px 8px;border-radius:8px;background:rgba(0,0,0,0.28);border:1px solid var(--card-border);color:var(--card-accent);font-family:var(--font-heading)">' + corner + '</span>' +
    '<span style="font-size:.68rem;padding:2px 8px;border-radius:8px;background:rgba(0,0,0,0.28);border:1px solid var(--card-border);color:var(--card-accent);font-family:var(--font-heading)">P' + (task.priority || '?') + '</span>' +
    '</div></div>' +
    '<div style="flex:1;padding:8px 10px;display:flex;flex-direction:column;justify-content:center;min-height:0">' +
    '<div style="font-family:var(--font-heading);font-size:1.05rem;margin-bottom:6px;font-weight:600">' + safeName + '</div>' +
    '<div style="font-size:.82rem;color:var(--text-secondary);margin-bottom:6px;line-height:1.4">' + safeDesc + '</div>' +
    '<div style="display:flex;gap:6px;flex-wrap:wrap">' +
    '<span style="font-size:.75rem;color:var(--text-muted);display:flex;align-items:center;gap:3px"><i class="fa-solid fa-clock" style="color:var(--gold);font-size:.7rem"></i>' + (task.estimated_time || '?') + '分</span>' +
    '<span style="font-size:.75rem;color:var(--text-muted);display:flex;align-items:center;gap:3px"><i class="fa-solid fa-repeat" style="color:var(--gold);font-size:.7rem"></i>' + repeatLbl + '</span>' +
    '</div>' +
    (safeTagsHtml ? '<div style="margin-top:6px;display:flex;gap:4px;flex-wrap:wrap">' + safeTagsHtml + '</div>' : '') +
    '</div>';

  var rightHtml =
    '<div class="drawn-card-right-panel" style="flex:1;padding:10px;display:flex;flex-direction:column;justify-content:center;align-items:stretch">' +
    actions +
    '</div>';

  card.innerHTML =
    '<div class="task-card-inner">' +
    '<div class="task-card-face task-card-back"><div class="card-back-pattern"></div><div class="card-back-emblem">\u2726</div></div>' +
    '<div class="task-card-face task-card-front">' +
    '<div style="flex:2;display:flex;flex-direction:column">' + leftHtml + '</div>' +
    '<div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding:8px;border-left:1px solid rgba(255,255,255,0.06)">' + rightHtml + '</div>' +
    '</div></div>';
  card.classList.add('is-drawing');
  wrap.appendChild(card);

  // 双 rAF 触发动画
  requestAnimationFrame(function () {
    requestAnimationFrame(function () { card.classList.add('is-revealing'); });
  });
  return wrap;
}

// ============ 开始任务（计时器）============
async function startTask(taskId) {
  var task = allTasks.find(function (x) { return x.id === taskId; });
  if (!task) { toast('任务不存在', 'err'); return; }
  if (!task.is_unlocked && task.is_unlocked !== undefined) {
    toast(prereqHint(task) || '任务被前置依赖阻塞', 'err');
    return;
  }

  var planned = task.estimated_time || 30;
  var card = document.querySelector('.task-card.drawn-card[data-task-id="' + taskId + '"]');
  if (!card) { toast('请先抽一张卡牌', 'err'); return; }

  var rightPanel = card.querySelector('.drawn-card-right-panel');
  if (!rightPanel) return;

  rightPanel.innerHTML =
    '<div style="text-align:center;margin-bottom:8px">' +
    '<div style="font-size:.78rem;color:var(--text-secondary);margin-bottom:4px">执行中...</div>' +
    '<div class="card-timer-display" style="font-family:var(--font-heading);font-size:1.3rem;color:var(--gold);margin-bottom:6px">00:00</div>' +
    '<div style="font-size:.68rem;color:var(--text-muted)">计划 ' + planned + ' 分</div>' +
    '</div>' +
    '<button class="btn" onclick="pauseInlineTimer(' + taskId + ')" style="width:100%;margin-bottom:6px"><i class="fa-solid fa-pause"></i> 暂停</button>' +
    '<button class="btn pri" onclick="confirmComplete(' + taskId + ')" style="width:100%"><i class="fa-solid fa-check"></i> 确认完成任务</button>';

  try {
    var r = await api('/api/timer/start', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId, planned_minutes: planned })
    });
    timerDockSession = {
      id: r.session_id,
      task_id: r.task_id,
      started_at: r.started_at,
      planned_minutes: r.planned_minutes,
      task_name: task.name
    };
    timerDockPaused = false;
    timerDockPausedElapsed = 0;
    updateTimerDockDisplay();
    startInlineTimer(taskId, r.started_at, planned);
    toast('计时已开始，加油！', 'suc');
  } catch (e) {
    toast(e.message || '启动计时失败', 'err');
    if (rightPanel) {
      rightPanel.innerHTML = '<button class="btn pri" onclick="startTask(' + taskId + ')" style="width:100%"><i class="fa-solid fa-play"></i> 开始任务</button>';
    }
  }
}

// 内嵌计时器更新
function startInlineTimer(taskId, startedAt, planned) {
  if (window._inlineTimerHandle) clearInterval(window._inlineTimerHandle);
  var card = document.querySelector('.task-card.drawn-card[data-task-id="' + taskId + '"]');
  if (!card) return;
  window._inlineTimerHandle = setInterval(function () {
    if (!timerDockSession || timerDockSession.task_id !== taskId) {
      clearInterval(window._inlineTimerHandle);
      return;
    }
    var display = card.querySelector('.card-timer-display');
    if (!display) { clearInterval(window._inlineTimerHandle); return; }
    var started = new Date(timerDockSession.started_at).getTime();
    var elapsed = Date.now() - started;
    if (timerDockPaused) elapsed = timerDockPausedElapsed;
    var sec = Math.floor(Math.max(0, elapsed) / 1000);
    var m = Math.floor(sec / 60);
    var s = sec % 60;
    display.textContent = (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }, 1000);
}

// 内嵌暂停
async function pauseInlineTimer(taskId) {
  if (!timerDockSession || timerDockSession.task_id !== taskId) return;
  toggleTimerDockPause();
  var card = document.querySelector('.task-card.drawn-card[data-task-id="' + taskId + '"]');
  if (!card) return;
  var rightPanel = card.querySelector('.drawn-card-right-panel');
  if (!rightPanel) return;
  var pauseBtn = rightPanel.querySelector('button[onclick*="pauseInlineTimer"]');
  if (pauseBtn) {
    pauseBtn.innerHTML = timerDockPaused
      ? '<i class="fa-solid fa-play"></i> 继续'
      : '<i class="fa-solid fa-pause"></i> 暂停';
  }
}

// 确认完成任务（需要先停止计时器）
async function confirmComplete(taskId) {
  // 先停止计时器
  if (timerDockSession && timerDockSession.id) {
    try {
      var started = new Date(timerDockSession.started_at).getTime();
      var actualMin = Math.max(1, Math.round((Date.now() - started) / 60000));
      await api('/api/timer/complete', {
        method: 'POST',
        body: JSON.stringify({ session_id: timerDockSession.id, actual_minutes: actualMin, result: 'completed' })
      });
    } catch (e) { /* ignore timer stop error */ }
  }
  timerDockSession = null;
  updateTimerDockDisplay();
  await completeWithFeedback(taskId);
}

async function checkTaskTimerStatus(taskId) {
  try {
    var r = await api('/api/timer/active');
    if (r && r.task_id === taskId) {
      // 仍在计时，超时提醒
      var started = new Date(r.started_at).getTime();
      var planned = r.planned_minutes || 30;
      var elapsed = (Date.now() - started) / 60000;
      if (elapsed > planned * 0.8) {
        toast(WARM_MESSAGES.timeout, 'inf');
      }
    }
  } catch (e) { /* ignore */ }
}

function showReplaceReason(taskId) {
  gachaState.replacedTaskId = taskId;
  var bar = document.getElementById('replaceReasonBar');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'replaceReasonBar';
    bar.className = 'replace-reason';
    bar.innerHTML =
      '<input type="radio" name="reason" value="low_energy" id="rr_low"><label for="rr_low">精力不足</label>' +
      '<input type="radio" name="reason" value="no_time" id="rr_no"><label for="rr_no">时间不够</label>' +
      '<input type="radio" name="reason" value="similar_done" id="rr_sim"><label for="rr_sim">刚做过类似</label>' +
      '<input type="radio" name="reason" value="other" id="rr_ot"><label for="rr_ot">其他</label>' +
      '<button class="btn pri sm" onclick="doReplace()">确认换牌</button>';
    var card = document.getElementById('gachaResult').querySelector('.task-card.drawn-card');
    if (card) card.appendChild(bar);
  } else {
    bar.style.display = 'flex';
  }
}

async function doReplace() {
  var rid = gachaState.replacedTaskId;
  var reasonEl = document.querySelector('input[name="reason"]:checked');
  var reason = reasonEl ? reasonEl.value : 'other';
  try {
    var r = await api('/api/gacha/replace', {
      method: 'POST',
      body: JSON.stringify({
        task_id: rid,
        reason: reason,
        pool: gachaState.pool,
        energy: gachaState.energy,
        preferred_tag: gachaState.selectedTag || null
      })
    });
    if (r.task) {
      gachaState.canReplace = false;
      document.getElementById('gachaResult').innerHTML = '';
      document.getElementById('gachaResult').appendChild(renderDrawnCard(r.task, 0));
      toast('已换牌', 'inf');
    }
  } catch (e) {
    toast(e.message || '换牌失败', 'err');
  }
}

// ============ 完成任务（自动反馈）============
// opts.finishEarly = true 表示"提前完成"（计时器未到计划时间），用 event_type=finish_early 上报
async function completeWithFeedback(id, opts) {
  opts = opts || {};
  var finishEarly = !!opts.finishEarly;
  var task = allTasks.find(function (x) { return x.id === id; });
  if (task && !task.is_unlocked) {
    toast(prereqHint(task) || '任务被前置依赖阻塞', 'err');
    return;
  }

  var drawnCard = document.querySelector('.task-card.drawn-card[data-task-id="' + id + '"]');

  try {
    var r = await api('/api/tasks/' + id + '/complete', { method: 'POST' });
    if (r.unlocked_tasks && r.unlocked_tasks.length) {
      toast(WARM_MESSAGES.unlock + ': ' + r.unlocked_tasks.join('、'), 'suc');
    }

    if (drawnCard) {
      await flyCardToDiscard(drawnCard);
    }

    // 先将任务放入弃牌堆，再标记完成
    await api('/api/tasks/' + id + '/move-to-discard', { method: 'POST' });

    var feedbackBody = { energy_after: 5, mood_after: 3 };
    if (finishEarly) feedbackBody.event_type = 'finish_early';
    api('/api/tasks/' + id + '/feedback', {
      method: 'POST',
      body: JSON.stringify(feedbackBody)
    }).catch(function () { });

    loadTasks();
    refreshGachaStats();
    updateDiscardPileVisual();
    timerDockSession = null;
    updateTimerDockDisplay();

    // 弹出关怀问询框
    showCareModal(id, task ? task.category : null);
  } catch (e) {
    toast(e.message || '完成失败', 'err');
  }
}

// ============ 任务完成关怀问询 ============
var _careContext = null;

var CARE_ENCOURAGES = [
  '太棒了！又完成了一项挑战！',
  '坚持就是胜利，你真棒！',
  '今天的你比昨天更优秀！',
  '小步快跑，大目标在前方等你！',
  '完成就是进步，继续加油！'
];

var CARE_CATEGORY_LABELS = { study: '学习', exercise: '运动', work: '工作', life: '生活', other: '其他' };

function showCareModal(taskId, category) {
  _careContext = { taskId: taskId, category: category };
  var encText = CARE_ENCOURAGES[Math.floor(Math.random() * CARE_ENCOURAGES.length)];
  document.getElementById('careEncourage').textContent = encText;
  var catLabel = category ? (CARE_CATEGORY_LABELS[category] || category) : '当前';
  document.getElementById('careTaskInfo').textContent = '当前科目：' + catLabel;
  document.getElementById('gachaResult').innerHTML = '';
  showModal('careModal');
}

function careSameCategory() {
  var cat = _careContext ? _careContext.category : null;
  closeModal('careModal');
  _careContext = null;
  if (!cat) {
    toast('无科目信息，将继续抽卡', 'inf');
  }
  drawGachaWithCategory(cat, null);
}

function careSwitchCategory() {
  var cat = _careContext ? _careContext.category : null;
  closeModal('careModal');
  _careContext = null;
  drawGachaWithCategory(null, cat);
}

function careRest() {
  closeModal('careModal');
  _careContext = null;
  document.getElementById('gachaResult').innerHTML =
    '<div class="empty-state"><i class="fa-solid fa-circle-check" style="color:var(--gold)"></i><p>休息也是一种进步，好好放松！</p></div>';
}

async function drawGachaWithCategory(includeCategory, excludeCategory) {
  if (isDrawing) return;
  isDrawing = true;
  var btn = document.getElementById('gachaBtn');
  if (btn) btn.disabled = true;
  var result = document.getElementById('gachaResult');
  result.innerHTML = '<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>正在抽卡...</p></div>';

  try {
    var r = await api('/api/gacha/care-draw', {
      method: 'POST',
      body: JSON.stringify({
        pool: gachaState.pool,
        energy: gachaState.energy,
        available_time: parseInt(document.getElementById('gachaTimeInput').value, 10) || 25,
        preferred_tag: gachaState.selectedTag || null,
        include_category: includeCategory || null,
        exclude_category: excludeCategory || null
      })
    });
    if (r.task) {
      gachaState.canReplace = r.can_replace !== false;
      gachaState.currentTaskId = r.task.id;
      result.innerHTML = '';
      var stage = renderDrawnCard(r.task, 0);
      result.appendChild(stage);
      await playCardFlyAnimation(r.task);
      updateDiscardPileVisual();
    } else {
      result.innerHTML = '<div class="empty-state mt24"><i class="fa-solid fa-box-open"></i><p>卡池空了，明天继续！</p></div>';
      gachaState.currentTaskId = null;
    }
  } catch (e) {
    toast(e.message || '抽卡失败', 'err');
    result.innerHTML = '';
    gachaState.currentTaskId = null;
  }

  if (btn) btn.disabled = false;
  isDrawing = false;
  refreshGachaStats();
}

// 将卡牌飞向弃牌堆
async function flyCardToDiscard(cardEl) {
  if (!cardEl) return;
  var pile = document.getElementById('discardPile');
  var flyLayer = document.getElementById('cardFlyLayer');
  if (!pile || !flyLayer) return;

  var cardRect = cardEl.getBoundingClientRect();
  var pileRect = pile.getBoundingClientRect();

  var flying = document.createElement('div');
  flying.className = 'flying-card';
  flying.style.left = cardRect.left + 'px';
  flying.style.top = cardRect.top + 'px';
  flying.style.width = cardRect.width + 'px';
  flying.style.height = cardRect.height + 'px';
  flying.style.opacity = '1';
  flying.style.transition = 'none';
  flyLayer.appendChild(flying);

  cardEl.style.opacity = '0';

  await new Promise(function (resolve) { requestAnimationFrame(resolve); });

  var tx = pileRect.left + pileRect.width / 2 - cardRect.width / 2;
  var ty = pileRect.top + pileRect.height / 2 - cardRect.height / 2;

  flying.style.transition = 'all 0.7s cubic-bezier(0.4, 0, 0.2, 1)';
  flying.style.left = tx + 'px';
  flying.style.top = ty + 'px';
  flying.style.transform = 'scale(0.6) rotate(8deg)';
  flying.style.opacity = '0.35';
  flying.style.filter = 'grayscale(0.6) brightness(0.7)';

  await new Promise(function (resolve) { setTimeout(resolve, 720); });
  flying.remove();
}

function setMood(v, el) {
  gachaState.feedbackMood = v;
  document.querySelectorAll('.feedback-emoji button').forEach(function (b) { b.classList.remove('sel'); });
  el.classList.add('sel');
}

function submitFeedback() {
  var tid = document.getElementById('fbTaskId').value;
  var energy = parseInt(document.getElementById('fbEnergy').value, 10);
  var mood = gachaState.feedbackMood;
  api('/api/tasks/' + tid + '/feedback', {
    method: 'POST',
    body: JSON.stringify({ energy_after: energy, mood_after: mood })
  }).catch(function () { });
  closeModal('feedbackModal');
  document.getElementById('gachaResult').innerHTML =
    '<div class="empty-state"><i class="fa-solid fa-circle-check" style="color:var(--green)"></i><p>太棒了，继续加油！</p></div>';
  refreshGachaStats();
}

function cancelFeedback() {
  closeModal('feedbackModal');
}

async function handleSkip(id) {
  var ctx = getTaskFeedbackContext(id);
  ctx.completionStatus = 'skipped';
  await promptTaskFeedback('skip', ctx);
  try {
    var r = await api('/api/tasks/' + id + '/skip', { method: 'POST' });
    await playCardAnim(id, 'is-skipping');
    document.getElementById('gachaResult').innerHTML =
      '<div class="empty-state"><i class="fa-solid fa-forward"></i><p>' + WARM_MESSAGES.skipped + '</p></div>';
    if (r.unlocked_tasks && r.unlocked_tasks.length) toast(WARM_MESSAGES.unlock + ': ' + r.unlocked_tasks.join('、'), 'suc');
    refreshGachaStats();
    loadTasks();
  } catch (e) {
    toast(e.message || '跳过失败', 'err');
  }
}

async function handleRefuse(id) {
  var ctx = getTaskFeedbackContext(id);
  ctx.completionStatus = 'refused';
  await promptTaskFeedback('skip', ctx);
  try {
    await api('/api/tasks/' + id + '/refuse', { method: 'POST' });
    await playCardAnim(id, 'is-refusing');
    document.getElementById('gachaResult').innerHTML =
      '<div class="empty-state"><i class="fa-solid fa-xmark"></i><p>' + WARM_MESSAGES.refused + '</p></div>';
    refreshGachaStats();
  } catch (e) {
    toast(e.message || '拒绝失败', 'err');
  }
}

async function refreshGachaStats() {
  try {
    var r = await api('/api/gacha/statistics');
    var se = document.getElementById('statDraws');
    var sr = document.getElementById('statRate');
    var srej = document.getElementById('statRejects');
    if (se) se.textContent = r.total_draws || 0;
    if (sr) sr.textContent = r.acceptance_rate != null ? (Math.round(r.acceptance_rate) + '%') : '--';
    if (srej) srej.textContent = r.rejections || 0;
  } catch (e) { /* 统计失败不阻塞 */ }
}

// ============ 弃牌堆视觉 ============
async function updateDiscardPileVisual() {
  try {
    var items = await api('/api/discard-pile');
    var stack = document.getElementById('discardPileStack');
    var empty = document.getElementById('discardPileEmpty');
    if (!stack) return;
    // 移除所有视觉卡
    stack.querySelectorAll('.discard-pile-visual-card').forEach(function (el) { el.remove(); });
    // 显示空状态或堆叠卡
    if (empty) empty.style.display = items && items.length > 0 ? 'none' : 'flex';
    if (items && items.length > 0) {
      var show = Math.min(items.length, 5);
      for (var i = 0; i < show; i++) {
        var card = document.createElement('div');
        card.className = 'discard-pile-visual-card discard-pile-card';
        card.style.setProperty('--di', i);
        card.style.zIndex = i;
        stack.appendChild(card);
      }
    }
  } catch (e) { /* ignore */ }
}

// ============ 卡牌大小滑块 ============
(function () {
  var saved = localStorage.getItem('cardScale');
  if (saved) {
    document.documentElement.style.setProperty('--card-scale', saved / 100);
    var slider = document.getElementById('cardSizeRange');
    if (slider) slider.value = saved;
  }
})();
document.getElementById('cardSizeRange').addEventListener('input', function () {
  var v = this.value / 100;
  document.documentElement.style.setProperty('--card-scale', v);
  localStorage.setItem('cardScale', this.value);
});

// ============ TASKS ============
var allTasks = [], allTags = [], selectedTagFilter = null;

async function loadTasks() {
  try {
    allTasks = await api('/api/tasks?unlocked_only=false');
    renderTasks();
    populateTimerTaskSelect();
  } catch (e) {
    toast('加载任务失败: ' + (e.message || ''), 'err');
  }
}

async function loadTags() {
  try {
    allTags = await api('/api/tags');
    var bar = document.getElementById('tagsBar');
    bar.innerHTML = allTags.map(function (t) {
      return '<span class="badge ' + (selectedTagFilter === t.id ? 'bg-gold' : 'bg-blue') +
        '" onclick="filterByTag(' + escapeHtml(String(t.id)) + ')">' + escapeHtml(t.name) + ' (' + escapeHtml(String(t.task_count)) + ')</span>';
    }).join('');
    if (selectedTagFilter) {
      bar.innerHTML += '<span class="badge bg-red" onclick="filterByTag(null)">清除</span>';
    }
  } catch (e) { /* ignore */ }
}

function filterByTag(id) {
  selectedTagFilter = id;
  loadTags();
  renderTasks();
}

function renderTasks() {
  if (window._renderLock) { window._renderPending = true; return; }
  window._renderLock = true;
  if (!allTasks) { window._renderLock = false; return; }
  var search = document.getElementById('taskSearch').value.toLowerCase();
  var filter = document.getElementById('taskFilter').value;
  var tasks = allTasks;
  if (search) tasks = tasks.filter(function (t) { return (t.name || '').toLowerCase().indexOf(search) >= 0; });
  if (filter === 'unlocked') tasks = tasks.filter(function (t) { return !t.completed && t.is_unlocked !== false; });
  if (filter === 'all') { /* no extra filter */ }
  if (filter === 'daily') tasks = tasks.filter(function (t) { return t.repeat_type === 'daily'; });
  if (filter === 'weekly') tasks = tasks.filter(function (t) { return t.repeat_type === 'weekly'; });
  if (filter === 'urgent') {
    tasks = tasks.filter(function (t) {
      return t.deadline && (new Date(t.deadline) - new Date()) / 86400000 < 3;
    });
  }
  if (selectedTagFilter) {
    tasks = tasks.filter(function (t) {
      return t.tags && allTags.find(function (at) {
        return at.id === selectedTagFilter && t.tags.indexOf(at.name) >= 0;
      });
    });
  }
  var grid = document.getElementById('taskGrid');
  if (tasks.length === 0) {
    grid.innerHTML = '<div class="empty-state"><i class="fa-solid fa-inbox"></i><p>没有匹配的任务</p></div>';
    window._renderLock = false;
    return;
  }
  var html = '', batch = '';
  for (var i = 0; i < tasks.length; i++) {
    var t = tasks[i];
    var statusIcons = [];
    if (t.completed) statusIcons.push('<span class="badge bg-green">已完成</span>');
    if (t.in_discard_pile) statusIcons.push('<span class="badge bg-red">弃牌堆</span>');
    if (!t.is_unlocked) statusIcons.push('<span class="badge bg-purple">阻塞</span>');
    var hint = prereqHint(t);
    var blockedNote = hint ? '<div class="card-meta mt8" style="color:var(--purple)">' + hint + '</div>' : '';
    var canAct = t.is_unlocked !== false && !t.completed;
    var actions =
      '<button class="btn sm" onclick="openTaskEdit(' + t.id + ')"><i class="fa-solid fa-pen"></i> 编辑</button>' +
      (canAct ? '<button class="btn pri sm" onclick="completeWithFeedback(' + t.id + ')"><i class="fa-solid fa-check"></i> 完成</button>' : '') +
      (canAct ? '<button class="btn sm" onclick="taskSkip(' + t.id + ')"><i class="fa-solid fa-forward"></i> 跳过</button>' : '') +
      (canAct ? '<button class="btn sm" onclick="taskRefuse(' + t.id + ')"><i class="fa-solid fa-xmark"></i> 拒绝</button>' : '') +
      (!t.in_discard_pile && !t.completed ? '<button class="btn sm" onclick="moveToDiscard(' + t.id + ')"><i class="fa-solid fa-box-archive"></i> 弃牌</button>' : '') +
      '<button class="btn danger sm" onclick="deleteTask(' + t.id + ')"><i class="fa-solid fa-trash"></i> 删除</button>';
    batch += buildTaskCardHtml(t, {
      statusHtml: statusIcons.join(''),
      blockedNote: blockedNote,
      actionsHtml: actions
    });
    if (batch.length > 8000) { html += batch; batch = ''; }
  }
  grid.innerHTML = html + batch;
  window._renderLock = false;
  if (window._renderPending) { window._renderPending = false; renderTasks(); }
}

async function taskSkip(id) {
  var ctx = getTaskFeedbackContext(id);
  ctx.completionStatus = 'skipped';
  await promptTaskFeedback('skip', ctx);
  try {
    var r = await api('/api/tasks/' + id + '/skip', { method: 'POST' });
    await playCardAnim(id, 'is-skipping');
    toast('已跳过', 'suc');
    if (r.unlocked_tasks && r.unlocked_tasks.length) toast(WARM_MESSAGES.unlock + ': ' + r.unlocked_tasks.join('、'), 'suc');
    loadTasks();
  } catch (e) {
    toast(e.message || '跳过失败', 'err');
  }
}

async function taskRefuse(id) {
  var ctx = getTaskFeedbackContext(id);
  ctx.completionStatus = 'refused';
  await promptTaskFeedback('skip', ctx);
  try {
    await api('/api/tasks/' + id + '/refuse', { method: 'POST' });
    await playCardAnim(id, 'is-refusing');
    toast('已记录', 'inf');
    loadTasks();
  } catch (e) {
    toast(e.message || '拒绝失败', 'err');
  }
}

async function moveToDiscard(id) {
  try {
    await api('/api/tasks/' + id + '/move-to-discard', { method: 'POST' });
    await playCardAnim(id, 'is-discarding');
    toast(WARM_MESSAGES.discarded, 'inf');
    loadTasks();
    updateDiscardPileVisual();
  } catch (e) {
    toast(e.message || '操作失败', 'err');
  }
}

var REPEAT_LABELS = { none: '单次', daily: '每日', weekly: '每周', accumulation: '积累' };

function formatDiscardTime(iso) {
  if (!iso) return '-';
  try {
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso.slice(0, 16).replace('T', ' ');
    return d.toLocaleString('zh-CN', { hour12: false });
  } catch (e) {
    return iso.slice(0, 16);
  }
}

function discardTaskStatus(t) {
  if (t.completed) return '已完成';
  if (t.in_discard_pile) return '弃牌堆';
  if (t.is_unlocked === false) return '阻塞';
  return '可用';
}

async function openDiscardPileModal() {
  showModal('discardPileModal');
  loadDiscardPileList();
}

async function loadDiscardPileList() {
  var wrap = document.getElementById('discardPileList');
  if (!wrap) return;
  wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
  try {
    var items = await api('/api/discard-pile');
    if (!items || !items.length) {
      wrap.innerHTML = '<div class="empty-state" style="padding:16px"><i class="fa-solid fa-inbox"></i><p>暂无弃牌任务</p></div>';
      return;
    }
    wrap.innerHTML = items.map(function (t) {
      var tags = (t.tags || []).map(function (x) {
        return '<span class="badge bg-gold">' + String(x).replace(/</g, '&lt;') + '</span>';
      }).join(' ');
      var repeat = REPEAT_LABELS[t.repeat_type] || t.repeat_type || '-';
      var safeName = String(t.name || '').replace(/</g, '&lt;').replace(/"/g, '&quot;');
      return '<div class="activity-row discard-row" data-id="' + t.id + '">' +
        '<div style="flex:1;min-width:0">' +
        '<div><strong>#' + t.id + '</strong> ' + safeName +
        ' <span class="badge bg-red" style="font-size:.75rem">' + discardTaskStatus(t) + '</span></div>' +
        '<div style="color:var(--text-muted);font-size:.8rem;margin-top:4px">' +
        repeat + ' · ' + formatDiscardTime(t.last_completed_at || t.updated_at) + '</div>' +
        (tags ? '<div class="flex gap8 wrap mt4">' + tags + '</div>' : '') +
        '</div>' +
        '<button type="button" class="btn pri sm discard-restore-btn" data-id="' + t.id + '" data-name="' + safeName + '">' +
        '<i class="fa-solid fa-rotate-left"></i> 恢复</button></div>';
    }).join('');
    wrap.querySelectorAll('.discard-restore-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        restoreFromDiscard(parseInt(btn.getAttribute('data-id'), 10), btn.getAttribute('data-name'));
      });
    });
  } catch (e) {
    wrap.innerHTML = '<p style="color:var(--text-muted)">弃牌堆加载失败</p>';
    toast(e.message || '弃牌堆加载失败', 'err');
  }
}

function restoreFromDiscard(id, name) {
  if (!confirm('确定将「' + (name || ('#' + id)) + '」从弃牌堆恢复？')) return;
  api('/api/discard-pile/' + id + '/restore', { method: 'POST', body: JSON.stringify({}) }).then(function () {
    toast('已恢复任务', 'suc');
    loadDiscardPileList();
    loadTasks();
    refreshGachaStats();
    updateDiscardPileVisual();
  }).catch(function (e) {
    toast(e.message || '恢复失败', 'err');
  });
}

function closeDiscardPileModal() {
  closeModal('discardPileModal');
}

function openTaskEdit(id) {
  showModal('taskModal');
  document.getElementById('tfId').value = '';
  document.getElementById('taskModalTitle').textContent = '新建任务';
  document.getElementById('taskDelBtn').style.display = 'none';
  loadNoteOptionsForTaskModal();
  document.getElementById('tfExistingTags').innerHTML = allTags.map(function (t) {
    return '<span class="badge bg-blue tag-pick" data-tag="' + escapeHtml(t.name) + '">' + escapeHtml(t.name) + '</span>';
  }).join('');
  document.querySelectorAll('#tfExistingTags .tag-pick').forEach(function (el) {
    el.addEventListener('click', function () { toggleExistingTag(el.getAttribute('data-tag')); });
  });
  buildDepList([]);
  if (id) {
    var t = allTasks.find(function (x) { return x.id === id; });
    if (t) {
      document.getElementById('tfId').value = t.id;
      document.getElementById('taskModalTitle').textContent = '编辑: ' + t.name;
      document.getElementById('taskDelBtn').style.display = 'inline-flex';
      document.getElementById('tfName').value = t.name || '';
      document.getElementById('tfCat').value = t.category || 'study';
      document.getElementById('tfPri').value = t.priority || 5;
      document.getElementById('tfTime').value = t.estimated_time || 30;
      document.getElementById('tfDdl').value = t.deadline || '';
      document.getElementById('tfRes').value = t.resistance || 'medium';
      document.getElementById('tfEnergy').value = t.energy_required || 'medium';
      document.getElementById('tfRepeat').value = t.repeat_type || 'none';
      document.getElementById('tfProfile').value = t.task_profile || 'deadline_flexible';
      document.getElementById('tfDesc').value = t.description || '';
      buildDepList(t.prerequisite_ids || []);
      document.getElementById('tfTagChips').innerHTML = '';
      window._tfTags = (t.tags || []).slice();
      window._tfTags.forEach(function (x) { addTagChipEl('tf', x); });
      return;
    }
  }
  ['tfName', 'tfDesc', 'tfDdl'].forEach(function (x) { document.getElementById(x).value = ''; });
  document.getElementById('tfCat').value = 'study';
  document.getElementById('tfPri').value = '5';
  document.getElementById('tfTime').value = '30';
  document.getElementById('tfRes').value = 'medium';
  document.getElementById('tfEnergy').value = 'medium';
  document.getElementById('tfRepeat').value = 'none';
  document.getElementById('tfProfile').value = 'deadline_flexible';
  document.getElementById('tfLinkedNote').value = '';
  document.getElementById('tfTagChips').innerHTML = '';
  window._tfTags = [];
  buildDepList([]);
}

async function loadNoteOptionsForTaskModal() {
  var sel = document.getElementById('tfLinkedNote');
  if (!sel || sel.options.length > 1) return;
  try {
    var notes = await api('/api/knowledge/notes');
    notes.slice(0, 200).forEach(function (n) {
      var opt = document.createElement('option');
      opt.value = n.path || '';
      opt.textContent = (n.category || '') + ' / ' + (n.name || n.path || '');
      sel.appendChild(opt);
    });
  } catch (e) { /* ignore */ }
}

function buildDepList(selectedIds) {
  selectedIds = selectedIds || [];
  var searchEl = document.getElementById('tfDepSearch');
  var search = (searchEl ? searchEl.value : '').toLowerCase();
  var currentId = parseInt(document.getElementById('tfId').value, 10) || 0;
  var tasks = allTasks.filter(function (t) {
    if (!t.id || t.id === currentId) return false;
    if (search && t.name.toLowerCase().indexOf(search) < 0) return false;
    return true;
  }).slice(0, 50);
  var listEl = document.getElementById('tfDepList');
  listEl.innerHTML = tasks.map(function (t) {
    var checked = selectedIds.indexOf(t.id) >= 0 ? ' checked' : '';
    var done = t.completed ? ' (已完成)' : '';
    return '<label class="note-item" style="display:flex;align-items:center;gap:8px;cursor:pointer">' +
      '<input type="checkbox" class="dep-cb" value="' + t.id + '"' + checked + ' style="width:auto"> ' +
      escapeHtml(t.name) + done + ' <span class="note-meta">ID:' + t.id + '</span></label>';
  }).join('');
  listEl.querySelectorAll('.dep-cb').forEach(function (cb) {
    cb.addEventListener('change', function () { window._depSelected = readSelectedPrereqs(); });
  });
  window._depSelected = selectedIds.slice();
}

function toggleExistingTag(name) {
  if (!window._tfTags) window._tfTags = [];
  var idx = window._tfTags.indexOf(name);
  if (idx >= 0) window._tfTags.splice(idx, 1);
  else window._tfTags.push(name);
  document.getElementById('tfTagChips').innerHTML = '';
  window._tfTags.forEach(function (x) { addTagChipEl('tf', x); });
}

async function saveTask() {
  var id = document.getElementById('tfId').value;
  var name = document.getElementById('tfName').value.trim();
  if (!name) { toast('请填写任务名称', 'err'); return; }
  var prereqIds = readSelectedPrereqs();
  var localErr = validatePrereqsLocal(id, prereqIds);
  if (localErr) { toast(localErr, 'err'); return; }
  var data = {
    name: name,
    category: document.getElementById('tfCat').value,
    priority: parseInt(document.getElementById('tfPri').value, 10),
    estimated_time: parseInt(document.getElementById('tfTime').value, 10),
    deadline: document.getElementById('tfDdl').value || null,
    resistance: document.getElementById('tfRes').value,
    energy_required: document.getElementById('tfEnergy').value,
    repeat_type: document.getElementById('tfRepeat').value,
    task_profile: document.getElementById('tfProfile').value,
    description: document.getElementById('tfDesc').value,
    tags: window._tfTags || [],
    prerequisite_ids: prereqIds
  };
  var linkedNote = document.getElementById('tfLinkedNote').value;
  if (linkedNote) data.linked_note_path = linkedNote;
  try {
    await api(id ? '/api/tasks/' + id : '/api/tasks', {
      method: id ? 'PUT' : 'POST',
      body: JSON.stringify(data)
    });
    closeModal('taskModal');
    toast(id ? '已更新' : '已创建', 'suc');
    loadTasks();
    loadTags();
  } catch (e) {
    toast(e.message || '保存失败', 'err');
  }
}

async function deleteTask(id) {
  var msg = '确认删除该任务？';
  try {
    var info = await api('/api/tasks/' + id + '/dependents');
    if (info.count > 0) {
      var names = info.dependents.map(function (d) { return d.name; }).join('、');
      msg = '该任务被 ' + info.count + ' 个任务依赖（' + names + '）。删除后将自动清理依赖，是否继续？';
    }
  } catch (e) { /* 继续默认确认 */ }
  if (!confirm(msg)) return;
  try {
    var r = await api('/api/tasks/' + id, { method: 'DELETE' });
    if (r.dependents_cleaned && r.dependents_cleaned.length) {
      toast('已清理 ' + r.dependents_cleaned.length + ' 个下游依赖', 'inf');
    }
    loadTasks();
    toast('已删除', 'suc');
  } catch (e) {
    toast(e.message || '删除失败', 'err');
  }
}

function deleteCurrentTask() {
  var id = document.getElementById('tfId').value;
  if (id) { deleteTask(id); closeModal('taskModal'); }
}

function addTagChip(prefix) {
  var inp = document.getElementById(prefix + 'TagInput');
  var tagName = inp.value.trim();
  if (!tagName) return;
  inp.value = '';
  if (!window['_' + prefix + 'Tags']) window['_' + prefix + 'Tags'] = [];
  if (window['_' + prefix + 'Tags'].indexOf(tagName) < 0) {
    window['_' + prefix + 'Tags'].push(tagName);
    addTagChipEl(prefix, tagName);
  }
}

function addTagChipEl(prefix, tagName) {
  var chips = document.getElementById(prefix + 'TagChips');
  var chip = document.createElement('span');
  chip.className = 'tag-chip';
  chip.innerHTML = tagName + '<span class="remove" data-prefix="' + prefix + '" data-name="' +
    tagName.replace(/"/g, '&quot;') + '">&times;</span>';
  chip.querySelector('.remove').addEventListener('click', function () {
    removeTagChip(this.getAttribute('data-prefix'), this.getAttribute('data-name'));
  });
  chips.appendChild(chip);
}

function removeTagChip(prefix, tagName) {
  window['_' + prefix + 'Tags'] = window['_' + prefix + 'Tags'].filter(function (x) { return x !== tagName; });
  document.getElementById(prefix + 'TagChips').innerHTML = '';
  window['_' + prefix + 'Tags'].forEach(function (x) { addTagChipEl(prefix, x); });
}

async function openBatchTags() {
  toast('选择任务后点击编辑，在标签栏中添加标签即可', 'inf');
}

async function openDepGraph() {
  try {
    var r = await api('/api/dependencies');
    var nodes = r.nodes || [];
    var edges = r.edges || [];
    var view = '<div class="g2"><div class="card"><div class="section-title"><i class="fa-solid fa-circle-nodes"></i> 节点 (' + nodes.length + ')</div>';
    nodes.slice(0, 100).forEach(function (n) {
      var cls = n.completed ? 'bg-green' : (n.is_unlocked ? 'bg-blue' : 'bg-purple');
      view += '<div class="flex gap8 ac mb8"><span class="badge ' + cls + '">' +
        (n.completed ? '完成' : (n.is_unlocked ? '解锁' : '阻塞')) + '</span> ' + n.name + ' (ID:' + n.id + ')</div>';
    });
    view += '</div><div class="card"><div class="section-title"><i class="fa-solid fa-link"></i> 依赖关系 (' + edges.length + ')</div>';
    edges.slice(0, 100).forEach(function (e) {
      var from = nodes.find(function (n) { return n.id === e.from; });
      var to = nodes.find(function (n) { return n.id === e.to; });
      view += '<div class="flex gap8 ac mb8"><span class="badge bg-blue">' + (from ? from.name : 'ID:' + e.from) +
        '</span> <i class="fa-solid fa-arrow-right"></i> <span class="badge bg-purple">' +
        (to ? to.name : 'ID:' + e.to) + '</span></div>';
    });
    view += '</div></div>';
    var m = document.createElement('div');
    m.className = 'modal-overlay';
    m.innerHTML = '<div class="modal" style="max-width:800px"><h2>依赖关系图</h2>' + view +
      '<div class="modal-actions"><button class="btn" id="depGraphClose">关闭</button></div></div>';
    document.body.appendChild(m);
    m.querySelector('#depGraphClose').addEventListener('click', function () { m.remove(); });
    m.addEventListener('click', function (ev) { if (ev.target === m) m.remove(); });
  } catch (e) {
    toast(e.message || '加载失败', 'err');
  }
}

// ============ SCHEDULE ============
var schedDate = new Date(), slots = [], weeklyData = {}, dailyData = [];

function shiftDate(d) {
  schedDate.setDate(schedDate.getDate() + d);
  renderSchedule();
}

async function renderSchedule() {
  var ds = schedDate.toISOString().slice(0, 10);
  document.getElementById('schedDate').textContent = ds;
  try {
    slots = await api('/api/schedule/slots');
    weeklyData = await api('/api/schedule/weekly');
    dailyData = await api('/api/schedule/daily?date=' + ds);
  } catch (e) {
    toast('日程加载失败（可能数据库表未就绪）', 'err');
    slots = slots || [];
  }
  var dow = schedDate.getDay();
  var wd = weeklyData[(dow === 0 ? 6 : dow - 1).toString()] || {};
  var html = '';
  slots.forEach(function (s) {
    var daily = dailyData.find(function (d) { return d.slot_id === s.slot_id; });
    var activity = daily ? daily.activity : (wd[s.slot_id] ? wd[s.slot_id].activity : '');
    html += '<div class="sched-time"><div>' + s.start_time + '</div><div style="font-size:.65rem">' + s.end_time + '</div></div>';
    html += '<div class="sched-slot" data-slot="' + s.slot_id + '">' +
      '<input class="slot-act full-width" value="' + (activity || '').replace(/"/g, '&quot;') + '" placeholder="点击编辑..." readonly></div>';
  });
  var grid = document.getElementById('schedGrid');
  grid.innerHTML = html || '<div class="empty-state"><p>暂无日程时段</p></div>';
  grid.querySelectorAll('.sched-slot').forEach(function (el) {
    el.addEventListener('click', function () { editSlot(el.getAttribute('data-slot'), el); });
  });
}

async function editSlot(slotId, el) {
  var act = prompt('活动名称:', el.querySelector('.slot-act').value || '');
  if (act === null) return;
  try {
    await api('/api/schedule/daily', {
      method: 'POST',
      body: JSON.stringify({ date: schedDate.toISOString().slice(0, 10), slot_id: slotId, activity: act })
    });
    renderSchedule();
    toast('已保存', 'suc');
  } catch (e) {
    toast(e.message || '保存失败', 'err');
  }
}

async function openActivityMgr() {
  showModal('activityMgrModal');
  loadActivityList();
}

async function loadActivityList() {
  var wrap = document.getElementById('activityList');
  if (!wrap) return;
  wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
  try {
    var items = await api('/api/schedule/activities');
    if (!items || !items.length) {
      wrap.innerHTML = '<div class="empty-state" style="padding:16px"><p>暂无活动</p></div>';
      return;
    }
    wrap.innerHTML = items.map(function (a) {
      var type = a.type || 'custom';
      var dur = a.duration_minutes != null ? a.duration_minutes : 30;
      return '<div class="activity-row" data-id="' + a.id + '">' +
        '<div><strong>' + String(a.name).replace(/</g, '&lt;') + '</strong>' +
        '<span style="color:var(--text-muted);font-size:.8rem;margin-left:8px">' + type + ' · ' + dur + '分</span></div>' +
        '<button type="button" class="btn danger sm activity-del-btn" data-id="' + a.id + '" data-name="' +
        String(a.name).replace(/"/g, '&quot;') + '"><i class="fa-solid fa-trash"></i></button></div>';
    }).join('');
    wrap.querySelectorAll('.activity-del-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        deleteActivity(parseInt(btn.getAttribute('data-id'), 10), btn.getAttribute('data-name'));
      });
    });
  } catch (e) {
    wrap.innerHTML = '<p style="color:var(--text-muted)">活动列表加载失败</p>';
    toast(e.message || '活动列表加载失败', 'err');
  }
}

async function addActivity() {
  var nameEl = document.getElementById('activityNewName');
  var name = nameEl.value.trim();
  if (!name) {
    toast('请输入活动名称', 'err');
    return;
  }
  var body = {
    name: name,
    type: (document.getElementById('activityNewType').value || 'custom').trim() || 'custom',
    duration_minutes: parseInt(document.getElementById('activityNewDuration').value, 10) || 30
  };
  try {
    await api('/api/schedule/activities', { method: 'POST', body: JSON.stringify(body) });
    toast('活动已添加', 'suc');
    nameEl.value = '';
    loadActivityList();
  } catch (e) {
    toast(e.message || '添加失败', 'err');
  }
}

function deleteActivity(id, name) {
  if (!confirm('确定删除活动「' + name + '」？')) return;
  api('/api/schedule/activities/' + id, { method: 'DELETE' }).then(function () {
    toast('已删除', 'suc');
    loadActivityList();
  }).catch(function (e) {
    toast(e.message || '删除失败', 'err');
  });
}

function closeActivityMgr() {
  closeModal('activityMgrModal');
}

// ============ KNOWLEDGE ============
var currentNotePath = '';

// P3-Bug-D: 前端缓存已加载的笔记数据（按分类）
var _noteCache = {};
var _noteCacheCat = null;

async function loadCategories() {
  try {
    var cats = await api('/api/knowledge/categories');
    var list = document.getElementById('catList');
    list.innerHTML = cats.map(function (c) {
      return '<div class="cat-item" data-id="' + c.id + '" data-name="' + c.name + '">' + c.name +
        '<span class="cat-count">' + c.count + '</span></div>';
    }).join('');
    list.querySelectorAll('.cat-item').forEach(function (el) {
      el.addEventListener('click', function () {
        loadCategoryNotes(el.getAttribute('data-id'), el.getAttribute('data-name'));
      });
    });
    if (cats.length > 0) loadCategoryNotes(cats[0].id, cats[0].name);
  } catch (e) {
    toast('加载分类失败', 'err');
  }
}

async function loadCategoryNotes(catId, catName) {
  document.querySelectorAll('.cat-item').forEach(function (x) {
    x.classList.toggle('active', x.getAttribute('data-name') === catName);
  });
  try {
    var notes;
    // P3-Bug-D: 缓存逻辑——同分类复用已加载数据
    if (_noteCacheCat === catName && _noteCache[catName]) {
      notes = _noteCache[catName];
    } else {
      notes = await api('/api/knowledge/notes');
      _noteCache[catName] = notes;
      _noteCacheCat = catName;
    }
    var filtered = notes.filter(function (n) { return n.category === catName; });
    var list = document.getElementById('noteList');
    list.innerHTML = '<div class="cat-item" style="font-size:.8rem;color:var(--text-muted)">' +
      catName + ' (' + filtered.length + '篇)</div>';
    filtered.forEach(function (n) {
      var item = document.createElement('div');
      item.className = 'note-item';
      item.textContent = n.name;
      item.addEventListener('click', function () { loadNote(n.path); });
      list.appendChild(item);
    });
    if (filtered.length > 0) loadNote(filtered[0].path);
  } catch (e) {
    toast('加载笔记列表失败', 'err');
  }
}

async function loadNote(path) {
  currentNotePath = path;
  try {
    var r = await api('/api/knowledge/note-content/' + encodeURIComponent(path));
    document.getElementById('knowTitle').innerHTML = '<i class="fa-solid fa-file-lines"></i> ' + path;
    document.getElementById('knowContent').innerHTML = mdToHtml(r.content || '');
    document.getElementById('knowActions').style.display = 'flex';
  } catch (e) {
    document.getElementById('knowContent').innerHTML = '<div class="empty-state"><p>无法加载笔记</p></div>';
    toast(e.message || '加载失败', 'err');
  }
}

// P3-Bug-C: 使用 marked.js 解析 Markdown（支持代码块、表格、删除线等）
function mdToHtml(md) {
  if (!md) return '';
  // 配置 marked 选项
  if (typeof marked !== 'undefined') {
    marked.setOptions({
      breaks: true,      // GFM 换行符
      gfm: true,        // 启用 GFM（表格、删除线等）
      headerIds: false, // 不生成 header id（避免冲突）
      mangle: false     // 不转义内容
    });
    try {
      return marked.parse(md);
    } catch (e) {
      console.warn('marked.js 解析失败，回退到正则:', e);
    }
  }
  // 备用正则解析（仅基础功能）
  var h = md.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    .replace(/^\- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, function (m) { return '<ul>' + m + '</ul>'; })
    .replace(/\n{2,}/g, '</p><p>');
  return '<p>' + h + '</p>';
}

async function openNoteFromCard(filePath) {
  try {
    await api('/api/knowledge/open-in-obsidian', {
      method: 'POST',
      body: JSON.stringify({ file_path: filePath })
    });
    toast('已在Obsidian中打开', 'suc');
  } catch (e) {
    toast('打开失败: ' + (e.message || e), 'err');
  }
}

async function openCurrentInObsidian() {
  if (!currentNotePath) { toast('请先选择笔记', 'err'); return; }
  try {
    await api('/api/knowledge/open-in-obsidian', {
      method: 'POST',
      body: JSON.stringify({ file_path: currentNotePath })
    });
    toast('已在Obsidian中打开', 'suc');
  } catch (e) {
    toast(e.message || '打开失败', 'err');
  }
}

// ============ CONFIG ============
async function loadConfigForm() {
  try {
    var r = await api('/api/config');
    document.getElementById('cfgPort').value = r.port || 5000;
    document.getElementById('cfgNotesDir').value = r.notes_directory || '';
    document.getElementById('cfgVaultPath').value = r.vault_path || '';
    document.getElementById('cfgApiBase').value = r.api_base || 'https://api.openai.com/v1';
    document.getElementById('cfgModel').value = r.model || 'gpt-4o-mini';
    refreshAgentReadonlyHint(r);
  } catch (e) {
    toast('加载配置失败', 'err');
  }
}

// ============ AGENT READONLY (P1-6) ============
var agentRoList = [];
var agentRawSubdir = '';
var agentVaultSubject = '';

function refreshAgentReadonlyHint(cfg) {
  var hint = document.getElementById('agentReadonlyHint');
  var banner = document.getElementById('agentReadonlyBanner');
  var hasKey = cfg && (cfg.has_openai_key || cfg.has_claude_key);
  var msg = hasKey
    ? '只读浏览模式：可查看 Agent 与文件，本页不执行 Agent、不写入 Vault。'
    : '未配置 API Key：只读浏览仍可用；运行 Agent 需在上方填入密钥（本模式不执行）。';
  if (hint) hint.textContent = msg;
  if (banner) banner.textContent = msg;
}

async function openAgentReadonlyModal() {
  showModal('agentReadonlyModal');
  try {
    var cfg = await api('/api/config');
    refreshAgentReadonlyHint(cfg);
  } catch (e) { /* ignore */ }
  switchAgentTab('agents');
  loadAgentRoList();
}

function closeAgentReadonlyModal() {
  closeModal('agentReadonlyModal');
}

function switchAgentTab(tab) {
  document.querySelectorAll('.agent-ro-tab').forEach(function (b) {
    b.classList.toggle('active', b.getAttribute('data-agent-tab') === tab);
  });
  document.getElementById('agentTabAgents').classList.toggle('hidden', tab !== 'agents');
  document.getElementById('agentTabRaw').classList.toggle('hidden', tab !== 'raw');
  document.getElementById('agentTabVault').classList.toggle('hidden', tab !== 'vault');
  if (tab === 'raw') loadAgentRawList(agentRawSubdir);
  if (tab === 'vault') loadAgentVaultList(agentVaultSubject);
}

async function loadAgentRoList() {
  var wrap = document.getElementById('agentRoList');
  if (!wrap) return;
  wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
  try {
    agentRoList = await api('/api/agent/agents');
    if (!agentRoList.length) {
      wrap.innerHTML = '<p style="color:var(--text-muted)">暂无 Agent</p>';
      return;
    }
    wrap.innerHTML = agentRoList.map(function (a) {
      return '<div class="agent-ro-item" data-id="' + a.id + '"><i class="fa-solid ' + (a.icon || 'fa-robot') +
        '"></i> ' + String(a.name).replace(/</g, '&lt;') + '</div>';
    }).join('');
    wrap.querySelectorAll('.agent-ro-item').forEach(function (el) {
      el.addEventListener('click', function () {
        selectAgentReadonly(el.getAttribute('data-id'), el);
      });
    });
    selectAgentReadonly(agentRoList[0].id, wrap.querySelector('.agent-ro-item'));
  } catch (e) {
    wrap.innerHTML = '<p style="color:var(--text-muted)">Agent 列表加载失败</p>';
    toast(e.message || 'Agent 列表加载失败', 'err');
  }
}

async function selectAgentReadonly(id, el) {
  document.querySelectorAll('#agentRoList .agent-ro-item').forEach(function (x) { x.classList.remove('active'); });
  if (el) el.classList.add('active');
  var agent = agentRoList.find(function (a) { return a.id === id; });
  var detail = document.getElementById('agentRoDetail');
  var ta = document.getElementById('agentRoPromptView');
  if (!agent || !detail) return;
  var actions = (agent.action_labels || agent.actions || []).join('；') || '无';
  detail.innerHTML =
    '<p><strong>' + String(agent.name).replace(/</g, '&lt;') + '</strong>（' + id + '）</p>' +
    '<p>' + String(agent.desc || '').replace(/</g, '&lt;') + '</p>' +
    '<p>输入：' + (agent.input_type_label || agent.input_type) + '</p>' +
    '<p>写操作（本模式禁用）：' + actions + '</p>' +
    '<p>提示词文件：' + (agent.prompt_file || '-') + '</p>';
  if (ta) ta.value = '加载中...';
  try {
    var pr = await api('/api/agent/agents/' + encodeURIComponent(id) + '/prompt');
    document.getElementById('agentRoPromptLabel').textContent =
      '提示词内容（只读）' + (pr.exists ? ' · ' + pr.size + ' 字符' : ' · 文件缺失');
    ta.value = pr.exists ? (pr.content || '') : '（提示词文件不存在）';
  } catch (e) {
    ta.value = '';
    toast(e.message || '提示词加载失败', 'err');
  }
}

async function loadAgentRawList(subdir) {
  agentRawSubdir = subdir || '';
  var wrap = document.getElementById('agentRawList');
  var pathEl = document.getElementById('agentRawPath');
  if (!wrap) return;
  wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
  if (pathEl) pathEl.textContent = '当前目录：' + (agentRawSubdir || '未分类/');
  try {
    var q = agentRawSubdir ? '?subdir=' + encodeURIComponent(agentRawSubdir) : '';
    var r = await api('/api/agent/files/raw' + q);
    var html = '';
    if (agentRawSubdir) {
      var parent = agentRawSubdir.indexOf('/') >= 0
        ? agentRawSubdir.slice(0, agentRawSubdir.lastIndexOf('/'))
        : '';
      html += '<div class="agent-ro-item" data-raw-nav=".."><i class="fa-solid fa-arrow-up"></i> 上级</div>';
    }
    (r.subdirs || []).forEach(function (d) {
      html += '<div class="agent-ro-item" data-raw-dir="' + String(d.name).replace(/"/g, '&quot;') +
        '"><i class="fa-solid fa-folder"></i> ' + d.name + ' (' + d.file_count + ')</div>';
    });
    (r.files || []).forEach(function (f) {
      html += '<div class="agent-ro-item" data-raw-file="' + String(f.path).replace(/"/g, '&quot;') +
        '"><i class="fa-solid fa-file-lines"></i> ' + f.name + '</div>';
    });
    if (!html) html = '<p style="color:var(--text-muted);padding:8px">暂无 txt 文件</p>';
    wrap.innerHTML = html;
    wrap.querySelectorAll('[data-raw-nav]').forEach(function (el) {
      el.addEventListener('click', function () {
        var parent = agentRawSubdir.indexOf('/') >= 0
          ? agentRawSubdir.slice(0, agentRawSubdir.lastIndexOf('/'))
          : '';
        loadAgentRawList(parent);
      });
    });
    wrap.querySelectorAll('[data-raw-dir]').forEach(function (el) {
      el.addEventListener('click', function () {
        var name = el.getAttribute('data-raw-dir');
        var next = agentRawSubdir ? agentRawSubdir + '/' + name : name;
        loadAgentRawList(next);
      });
    });
    wrap.querySelectorAll('[data-raw-file]').forEach(function (el) {
      el.addEventListener('click', function () {
        loadAgentRawContent(el.getAttribute('data-raw-file'));
      });
    });
  } catch (e) {
    wrap.innerHTML = '<p style="color:var(--text-muted)">Raw 列表加载失败</p>';
    toast(e.message || 'Raw 列表加载失败', 'err');
  }
}

async function loadAgentRawContent(path) {
  var box = document.getElementById('agentRawContent');
  if (!box) return;
  box.textContent = '加载中...';
  try {
    var r = await api('/api/agent/files/raw/content?path=' + encodeURIComponent(path));
    box.textContent = r.content || '';
    document.getElementById('agentRawPath').textContent = '文件：' + path + '（' + (r.size || 0) + ' 字节）';
  } catch (e) {
    box.textContent = '加载失败';
    toast(e.message || 'Raw 文件读取失败', 'err');
  }
}

async function loadAgentVaultList(subject) {
  agentVaultSubject = subject || '';
  var wrap = document.getElementById('agentVaultList');
  var pathEl = document.getElementById('agentVaultPath');
  if (!wrap) return;
  wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
  if (pathEl) pathEl.textContent = '当前目录：' + (agentVaultSubject || 'Vault 根目录');
  try {
    var q = agentVaultSubject ? '?subject=' + encodeURIComponent(agentVaultSubject) : '';
    var r = await api('/api/agent/files/vault' + q);
    var html = '';
    if (agentVaultSubject) {
      html += '<div class="agent-ro-item" data-vault-nav=".."><i class="fa-solid fa-arrow-up"></i> 上级</div>';
    }
    (r.dirs || []).forEach(function (d) {
      html += '<div class="agent-ro-item" data-vault-dir="' + String(d.name).replace(/"/g, '&quot;') +
        '"><i class="fa-solid fa-folder"></i> ' + d.name + ' (' + d.file_count + ')</div>';
    });
    (r.files || []).forEach(function (f) {
      html += '<div class="agent-ro-item" data-vault-file="' + String(f.path).replace(/"/g, '&quot;') +
        '"><i class="fa-solid fa-file-lines"></i> ' + f.name + '</div>';
    });
    if (!html) html = '<p style="color:var(--text-muted);padding:8px">暂无 Markdown 文件</p>';
    wrap.innerHTML = html;
    wrap.querySelectorAll('[data-vault-nav]').forEach(function (el) {
      el.addEventListener('click', function () {
        var parent = agentVaultSubject.indexOf('/') >= 0
          ? agentVaultSubject.slice(0, agentVaultSubject.lastIndexOf('/'))
          : '';
        loadAgentVaultList(parent);
      });
    });
    wrap.querySelectorAll('[data-vault-dir]').forEach(function (el) {
      el.addEventListener('click', function () {
        var name = el.getAttribute('data-vault-dir');
        var next = agentVaultSubject ? agentVaultSubject + '/' + name : name;
        loadAgentVaultList(next);
      });
    });
    wrap.querySelectorAll('[data-vault-file]').forEach(function (el) {
      el.addEventListener('click', function () {
        loadAgentVaultContent(el.getAttribute('data-vault-file'));
      });
    });
  } catch (e) {
    wrap.innerHTML = '<p style="color:var(--text-muted)">Vault 列表加载失败</p>';
    toast(e.message || 'Vault 列表加载失败', 'err');
  }
}

async function loadAgentVaultContent(path) {
  var box = document.getElementById('agentVaultContent');
  if (!box) return;
  box.textContent = '加载中...';
  try {
    var r = await api('/api/agent/files/vault/content?path=' + encodeURIComponent(path));
    box.textContent = r.content || '';
    document.getElementById('agentVaultPath').textContent = '文件：' + path + '（' + (r.size || 0) + ' 字节）';
  } catch (e) {
    box.textContent = '加载失败';
    toast(e.message || 'Vault 文件读取失败', 'err');
  }
}

async function saveConfigForm() {
  var data = {
    port: parseInt(document.getElementById('cfgPort').value, 10) || 5000,
    notes_directory: document.getElementById('cfgNotesDir').value,
    vault_path: document.getElementById('cfgVaultPath').value,
    openai_api_key: document.getElementById('cfgApiKey').value,
    api_base: document.getElementById('cfgApiBase').value,
    model: document.getElementById('cfgModel').value
  };
  try {
    var r = await api('/api/config/save', { method: 'POST', body: JSON.stringify(data) });
    if (r.success) toast('已保存，重启服务器后生效', 'suc');
    else toast('保存失败: ' + (r.error || ''), 'err');
  } catch (e) {
    toast(e.message || '保存失败', 'err');
  }
}

// ============ PROMPTS ============
var promptFiles = [];
var promptCurrentContent = '';
var promptOriginalContent = '';
var promptSelectedName = '';
var promptEditMode = false;

function setPromptEditMode(on) {
  promptEditMode = !!on;
  var ta = document.getElementById('promptContentView');
  var readBtns = document.getElementById('promptReadBtns');
  var editBtns = document.getElementById('promptEditBtns');
  var hint = document.getElementById('promptModeHint');
  if (ta) ta.readOnly = !promptEditMode;
  if (readBtns) readBtns.classList.toggle('hidden', promptEditMode);
  if (editBtns) editBtns.classList.toggle('hidden', !promptEditMode);
  if (hint) {
    hint.textContent = promptEditMode
      ? '编辑模式：修改后请预览差异并确认保存（保存前自动备份）'
      : '默认只读；进入编辑模式后可预览差异并保存（保存前自动备份）';
  }
  document.getElementById('promptCopyBtn').style.display = promptEditMode ? 'none' : '';
  document.getElementById('promptEditBtn').style.display = promptEditMode ? 'none' : '';
}

function computePromptDiff(oldText, newText) {
  var oldL = (oldText || '').split('\n');
  var newL = (newText || '').split('\n');
  var max = Math.max(oldL.length, newL.length);
  var added = 0, removed = 0, changed = 0;
  var lines = [];
  for (var i = 0; i < max; i++) {
    var o = oldL[i], n = newL[i];
    if (o === undefined) {
      added++;
      lines.push({ type: 'add', text: n });
    } else if (n === undefined) {
      removed++;
      lines.push({ type: 'rem', text: o });
    } else if (o !== n) {
      changed++;
      lines.push({ type: 'chg', old: o, new: n });
    }
  }
  return { added: added, removed: removed, changed: changed, lines: lines.slice(0, 80) };
}

async function refreshPromptBackupStatus() {
  var btn = document.getElementById('promptRestoreBtn');
  if (!btn || !promptSelectedName || promptEditMode) {
    if (btn) btn.style.display = 'none';
    return;
  }
  try {
    var r = await api('/api/prompts/' + encodeURIComponent(promptSelectedName) + '/backup/latest');
    btn.style.display = r.exists ? '' : 'none';
  } catch (e) {
    btn.style.display = 'none';
  }
}

async function loadPromptList() {
  var list = document.getElementById('promptFileList');
  if (!list) return;
  if (promptEditMode) {
    toast('请先退出编辑模式', 'err');
    return;
  }
  list.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
  try {
    promptFiles = await api('/api/prompts');
    if (!promptFiles || !promptFiles.length) {
      list.innerHTML = '<div class="empty-state" style="padding:12px"><p>暂无提示词文件</p></div>';
      document.getElementById('promptContentView').value = '';
      document.getElementById('promptCurrentLabel').textContent = '选择文件查看内容';
      promptCurrentContent = '';
      promptOriginalContent = '';
      promptSelectedName = '';
      return;
    }
    list.innerHTML = promptFiles.map(function (f, idx) {
      var safe = String(f.name).replace(/&/g, '&amp;').replace(/</g, '&lt;');
      return '<div class="prompt-file-item" data-idx="' + idx + '">' + safe + '</div>';
    }).join('');
    list.querySelectorAll('.prompt-file-item').forEach(function (el) {
      el.addEventListener('click', function () {
        if (promptEditMode) {
          toast('请先保存或取消编辑', 'err');
          return;
        }
        var i = parseInt(el.getAttribute('data-idx'), 10);
        if (promptFiles[i]) loadPromptContent(promptFiles[i].name, el);
      });
    });
  } catch (e) {
    list.innerHTML = '<div class="empty-state" style="padding:12px"><p>提示词列表加载失败</p></div>';
    toast('提示词列表加载失败', 'err');
  }
}

async function loadPromptContent(name, el) {
  if (!name || promptEditMode) return;
  document.querySelectorAll('.prompt-file-item').forEach(function (x) { x.classList.remove('active'); });
  if (el) el.classList.add('active');
  try {
    var r = await api('/api/prompts/' + encodeURIComponent(name));
    promptSelectedName = name;
    promptCurrentContent = r.content || '';
    promptOriginalContent = promptCurrentContent;
    document.getElementById('promptContentView').value = promptCurrentContent;
    document.getElementById('promptCurrentLabel').textContent = name;
    refreshPromptBackupStatus();
  } catch (e) {
    toast(e.message || '加载提示词失败', 'err');
  }
}

function enterPromptEdit() {
  if (!promptSelectedName) {
    toast('请先选择提示词文件', 'err');
    return;
  }
  promptOriginalContent = promptCurrentContent;
  setPromptEditMode(true);
  document.getElementById('promptRestoreBtn').style.display = 'none';
}

function cancelPromptEdit() {
  var ta = document.getElementById('promptContentView');
  var dirty = ta && ta.value !== promptOriginalContent;
  if (dirty && !confirm('内容已修改，确定放弃编辑？')) return;
  if (ta) ta.value = promptOriginalContent;
  promptCurrentContent = promptOriginalContent;
  setPromptEditMode(false);
  refreshPromptBackupStatus();
}

function previewPromptDiff() {
  if (!promptSelectedName) return;
  var newContent = document.getElementById('promptContentView').value;
  if (newContent === promptOriginalContent) {
    toast('内容未变化', 'inf');
    return;
  }
  var diff = computePromptDiff(promptOriginalContent, newContent);
  document.getElementById('promptDiffSummary').innerHTML =
    '原内容 ' + promptOriginalContent.length + ' 字符 → 新内容 ' + newContent.length + ' 字符<br>' +
    '新增行 ' + diff.added + ' · 删除行 ' + diff.removed + ' · 修改行 ' + diff.changed;
  var html = '';
  diff.lines.forEach(function (ln) {
    if (ln.type === 'add') html += '<div class="diff-line-add">+ ' + escapeHtml(ln.text) + '</div>';
    else if (ln.type === 'rem') html += '<div class="diff-line-rem">- ' + escapeHtml(ln.text) + '</div>';
    else html += '<div class="diff-line-chg">~ ' + escapeHtml(ln.old) + ' → ' + escapeHtml(ln.new) + '</div>';
  });
  if (!diff.lines.length) html = '<div style="color:var(--text-muted)">（无逐行差异，可能仅末尾换行不同）</div>';
  document.getElementById('promptDiffLines').innerHTML = html;
  window._promptPendingSave = newContent;
  showModal('promptDiffModal');
}

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

async function confirmPromptSave() {
  if (!promptSelectedName || window._promptPendingSave === undefined) return;
  var content = window._promptPendingSave;
  try {
    await api('/api/prompts/' + encodeURIComponent(promptSelectedName), {
      method: 'PUT',
      body: JSON.stringify({ content: content })
    });
    closeModal('promptDiffModal');
    promptCurrentContent = content;
    promptOriginalContent = content;
    document.getElementById('promptContentView').value = content;
    setPromptEditMode(false);
    toast('保存成功', 'suc');
    refreshPromptBackupStatus();
    window._promptPendingSave = undefined;
  } catch (e) {
    toast(e.message || '保存失败，原文件未破坏（已先备份）', 'err');
  }
}

function cancelPromptDiffModal() {
  closeModal('promptDiffModal');
  window._promptPendingSave = undefined;
}

async function restorePromptLatest() {
  if (!promptSelectedName || promptEditMode) return;
  if (!confirm('确定恢复最近一次备份？当前文件会先自动备份。')) return;
  try {
    await api('/api/prompts/' + encodeURIComponent(promptSelectedName) + '/restore-latest', {
      method: 'POST',
      body: JSON.stringify({})
    });
    var r = await api('/api/prompts/' + encodeURIComponent(promptSelectedName));
    promptCurrentContent = r.content || '';
    promptOriginalContent = promptCurrentContent;
    document.getElementById('promptContentView').value = promptCurrentContent;
    toast('已恢复最近备份', 'suc');
    refreshPromptBackupStatus();
  } catch (e) {
    toast(e.message || '恢复失败', 'err');
  }
}

function copyPromptContent() {
  if (promptEditMode) return;
  if (!promptCurrentContent) {
    toast('请先选择提示词文件', 'err');
    return;
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(promptCurrentContent).then(function () {
      toast('已复制到剪贴板', 'suc');
    }).catch(function () {
      toast('复制失败', 'err');
    });
  } else {
    var ta = document.getElementById('promptContentView');
    ta.focus();
    ta.select();
    try {
      if (document.execCommand('copy')) toast('已复制到剪贴板', 'suc');
      else toast('复制失败', 'err');
    } catch (err) {
      toast('复制失败', 'err');
    }
  }
}

// ============ SLEEP TRACKING ============
function todayDateStr() {
  return new Date().toISOString().slice(0, 10);
}

function validateBedTime(val) {
  if (!val || !String(val).trim()) return '请输入入睡时间';
  if (!/^\d{2}:\d{2}$/.test(val)) return '入睡时间格式应为 HH:MM';
  var parts = val.split(':');
  var h = parseInt(parts[0], 10);
  var m = parseInt(parts[1], 10);
  if (isNaN(h) || isNaN(m) || h < 0 || h > 23 || m < 0 || m > 59) return '入睡时间无效';
  return null;
}

async function loadSleepPanel() {
  await loadSleepInfo();
  await loadWeeklyEnergyTable();
}

// ============ STATE ASSESSMENT ============
var assessmentQuestions = [];
var assessmentAnswers = {};

var TONE_LABELS = { high: '高能量', normal: '正常', low: '低能量', rest: '休息' };

function formatAssessmentScore(v) {
  if (v == null || v === '') return '-';
  return String(v);
}

async function loadStateAssessmentPanel() {
  await loadStateAssessmentSummary();
  await loadStateAssessmentHistory();
}

async function loadStateAssessmentSummary() {
  var wrap = document.getElementById('stateAssessmentSummary');
  var btn = document.getElementById('stateAssessmentOpenBtn');
  if (!wrap) return;
  wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
  try {
    var r = await api('/api/state/assessment');
    if (r.completed) {
      var tone = TONE_LABELS[r.daily_tone] || r.daily_tone || '-';
      wrap.innerHTML =
        '<div class="state-scores">' +
        '<div class="state-score"><div class="num">' + formatAssessmentScore(r.energy_score) + '</div><div class="lbl">精力</div></div>' +
        '<div class="state-score"><div class="num">' + formatAssessmentScore(r.focus_score) + '</div><div class="lbl">专注</div></div>' +
        '<div class="state-score"><div class="num">' + formatAssessmentScore(r.mood_score) + '</div><div class="lbl">情绪</div></div>' +
        '<div class="state-score"><div class="num" style="font-size:1rem">' + tone + '</div><div class="lbl">基调</div></div>' +
        '</div>';
      if (btn) btn.innerHTML = '<i class="fa-solid fa-pen"></i> 修改评估';
    } else {
      wrap.innerHTML = '<div class="empty-state" style="padding:12px"><p>今日还没有评估</p></div>';
      if (btn) btn.innerHTML = '<i class="fa-solid fa-pen"></i> 填写评估';
    }
  } catch (e) {
    wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">状态评估加载失败</p>';
    toast(e.message || '状态评估加载失败', 'err');
  }
}

async function loadStateAssessmentHistory() {
  var wrap = document.getElementById('stateAssessmentHistory');
  if (!wrap) return;
  try {
    var rows = await api('/api/state/assessment/history?days=7');
    if (!rows || !rows.length) {
      wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">暂无历史记录</p>';
      return;
    }
    var html = '<table class="energy-table"><thead><tr><th>日期</th><th>精力</th><th>专注</th><th>情绪</th><th>基调</th></tr></thead><tbody>';
    rows.slice(0, 7).forEach(function (r) {
      html += '<tr><td>' + r.date + '</td><td>' + formatAssessmentScore(r.energy_score) +
        '</td><td>' + formatAssessmentScore(r.focus_score) +
        '</td><td>' + formatAssessmentScore(r.mood_score) +
        '</td><td>' + (TONE_LABELS[r.daily_tone] || r.daily_tone || '-') + '</td></tr>';
    });
    html += '</tbody></table>';
    wrap.innerHTML = html;
  } catch (e) {
    wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">历史记录加载失败</p>';
  }
}

async function openStateAssessmentModal() {
  var form = document.getElementById('stateAssessmentForm');
  if (!form) return;
  form.innerHTML = '<p style="color:var(--text-muted)">加载中...</p>';
  showModal('stateAssessmentModal');
  try {
    var r = await api('/api/state/assessment');
    var qResp = await api('/api/state/questions');
    assessmentQuestions = r.questions || qResp.questions || [];
    assessmentAnswers = {};
    if (r.completed && r.answers) {
      assessmentAnswers = Object.assign({}, r.answers);
    }
    renderAssessmentForm();
  } catch (e) {
    form.innerHTML = '<p style="color:var(--text-muted)">加载失败</p>';
    toast(e.message || '评估表单加载失败', 'err');
  }
}

function renderAssessmentForm() {
  var form = document.getElementById('stateAssessmentForm');
  if (!form || !assessmentQuestions.length) {
    if (form) form.innerHTML = '<p style="color:var(--text-muted)">暂无评估问题</p>';
    return;
  }
  form.innerHTML = assessmentQuestions.map(function (q) {
    var val = assessmentAnswers[q.id] != null ? assessmentAnswers[q.id] : 3;
    assessmentAnswers[q.id] = val;
    return '<div class="assess-q" data-qid="' + q.id + '">' +
      '<label>' + String(q.q).replace(/</g, '&lt;') + '</label>' +
      '<input type="range" min="1" max="5" step="1" value="' + val + '" class="assess-range" data-qid="' + q.id + '">' +
      '<div class="assess-q-val">当前: <span class="assess-val-num">' + val + '</span></div></div>';
  }).join('');
  form.querySelectorAll('.assess-range').forEach(function (inp) {
    inp.addEventListener('input', function () {
      var qid = inp.getAttribute('data-qid');
      var v = parseInt(inp.value, 10);
      assessmentAnswers[qid] = v;
      var row = inp.closest('.assess-q');
      if (row) {
        var span = row.querySelector('.assess-val-num');
        if (span) span.textContent = String(v);
      }
    });
  });
}

async function saveStateAssessment() {
  if (!assessmentQuestions.length) {
    toast('暂无评估问题', 'err');
    return;
  }
  var answers = {};
  assessmentQuestions.forEach(function (q) {
    answers[q.id] = assessmentAnswers[q.id] != null ? assessmentAnswers[q.id] : 3;
  });
  try {
    await api('/api/state/assessment', {
      method: 'POST',
      body: JSON.stringify({ answers: answers })
    });
    closeModal('stateAssessmentModal');
    toast('评估已保存', 'suc');
    loadStateAssessmentPanel();
  } catch (e) {
    toast(e.message || '保存失败', 'err');
  }
}

function closeStateAssessmentModal() {
  closeModal('stateAssessmentModal');
}

// ============ TIMER ============
var timerActiveSession = null;
var timerTickHandle = null;

function formatElapsed(ms) {
  var sec = Math.max(0, Math.floor(ms / 1000));
  var m = Math.floor(sec / 60);
  var s = sec % 60;
  return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
}

function populateTimerTaskSelect() {
  var sel = document.getElementById('timerTaskSelect');
  if (!sel) return;
  var current = sel.value;
  var opts = '<option value="">选择任务...</option>';
  (allTasks || []).forEach(function (t) {
    if (t.completed || t.in_discard_pile) return;
    opts += '<option value="' + t.id + '">' + escapeHtml(t.name) + '</option>';
  });
  sel.innerHTML = opts;
  if (current) sel.value = current;
}

function updateTimerDisplay() {
  var statusEl = document.getElementById('timerStatusText');
  var elapsedEl = document.getElementById('timerElapsedDisplay');
  var startBtn = document.getElementById('timerStartBtn');
  var pauseBtn = document.getElementById('timerPauseBtn');
  var stopBtn = document.getElementById('timerStopBtn');
  var sel = document.getElementById('timerTaskSelect');
  var planned = document.getElementById('timerPlannedMin');
  if (!statusEl || !elapsedEl) return;

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

function startTimerTick() {
  if (timerTickHandle) clearInterval(timerTickHandle);
  timerTickHandle = setInterval(updateTimerDisplay, 1000);
}

async function loadTimerPanel() {
  populateTimerTaskSelect();
  var statusEl = document.getElementById('timerStatusText');
  if (statusEl) statusEl.textContent = '加载中...';
  try {
    var r = await api('/api/timer/active');
    // P3-Bug-A: 统一状态源——任务页也使用同一个 timerDockSession
    timerActiveSession = r && r.id ? r : null;
    // 同步 paused 状态到全局
    if (timerDockSession && timerDockSession.id === timerActiveSession?.id) {
      timerDockPaused = !!(r && r.is_paused);
      timerDockPausedElapsed = (r && r.paused_seconds) ? r.paused_seconds * 1000 : 0;
    }
    updateTimerDisplay();
    startTimerTick();
  } catch (e) {
    timerActiveSession = null;
    updateTimerDisplay();
    toast(e.message || '计时器状态加载失败', 'err');
  }
}

async function startTimer() {
  if (timerActiveSession) {
    toast('已有进行中的计时', 'err');
    return;
  }
  var sel = document.getElementById('timerTaskSelect');
  var planned = document.getElementById('timerPlannedMin');
  var taskId = sel ? parseInt(sel.value, 10) : 0;
  if (!taskId) {
    toast('请选择任务', 'err');
    return;
  }
  var minutes = planned ? parseInt(planned.value, 10) : 30;
  if (!minutes || minutes < 1) minutes = 30;
  try {
    var r = await api('/api/timer/start', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId, planned_minutes: minutes })
    });
    timerActiveSession = {
      id: r.session_id,
      task_id: r.task_id,
      started_at: r.started_at,
      planned_minutes: r.planned_minutes,
      task_name: taskNameById(r.task_id)
    };
    // P3-Bug-A: 同步到抽卡页 Dock（统一状态源）
    timerDockSession = timerActiveSession;
    timerDockPaused = false;
    timerDockPausedElapsed = 0;
    updateTimerDockDisplay();
    toast('计时已开始', 'suc');
    updateTimerDisplay();
  } catch (e) {
    toast(e.message || '开始计时失败', 'err');
  }
}

async function stopTimer() {
  if (!timerActiveSession || !timerActiveSession.id) {
    toast('当前无进行中的计时', 'err');
    return;
  }
  showModal('timerOutcomeModal');
}

async function handleTimerOutcome(outcome) {
  closeModal('timerOutcomeModal');
  if (!timerActiveSession || !timerActiveSession.id) return;

  var session = timerActiveSession;
  // P3-Bug-A: 计算实际时间（考虑暂停时间）
  var started = new Date(session.started_at).getTime();
  var elapsedMs = Date.now() - started;
  if (timerDockPaused) elapsedMs = timerDockPausedElapsed;
  var actualMinutes = Math.max(1, Math.round(elapsedMs / 60000));
  var planned = session.planned_minutes || 30;
  var timerResult = outcome === 'completed' ? 'completed' : 'abandoned';

  try {
    await api('/api/timer/complete', {
      method: 'POST',
      body: JSON.stringify({
        session_id: session.id,
        actual_minutes: actualMinutes,
        result: timerResult,
        reason: outcome
      })
    });
    timerActiveSession = null;
    // P3-Bug-A: 同步清空 dock 状态
    timerDockSession = null;
    timerDockPaused = false;
    timerDockPausedElapsed = 0;
    updateTimerDisplay();
    updateTimerDockDisplay();
    toast('计时已结束（' + actualMinutes + ' 分钟）', 'suc');

    var fbCtx = {
      taskId: session.task_id,
      plannedMinutes: planned,
      actualMinutes: actualMinutes,
      completionStatus: outcome
    };
    if (outcome === 'completed') {
      if (actualMinutes <= planned * 0.5) {
        toast(WARM_MESSAGES.completedEarly, 'inf');
      }
      await submitTaskFeedbackEvent({
        task_id: session.task_id,
        event_type: 'finish_on_time',
        planned_minutes: planned,
        actual_minutes: actualMinutes,
        completion_status: 'completed',
        reason_category: 'other',
        reason_detail: '按时完成',
        note: null
      });
    } else if (outcome === 'unfinished') {
      toast(WARM_MESSAGES.timeout, 'inf');
    } else if (outcome === 'abandoned') {
      toast(WARM_MESSAGES.timeout, 'inf');
    }
    loadTasks();
    refreshGachaStats();
  } catch (e) {
    toast(e.message || '停止计时失败', 'err');
    await loadTimerPanel();
  }
}

async function loadSleepInfo() {
  var disp = document.getElementById('sleepBedTimeDisplay');
  if (!disp) return;
  try {
    var rows = await api('/api/state/sleep');
    var today = todayDateStr();
    var row = null;
    if (Array.isArray(rows)) {
      row = rows.find(function (r) { return r.date === today; });
    }
    var bed = row && row.bed_time ? row.bed_time : '';
    var streak = row && row.sleep_early_streak != null ? row.sleep_early_streak : 0;
    disp.textContent = bed || '--';
    document.getElementById('sleepStreakDisplay').textContent = String(streak);
    var inp = document.getElementById('sleepBedTimeInput');
    if (inp) inp.value = bed ? bed.slice(0, 5) : '';
  } catch (e) {
    toast('睡眠信息加载失败', 'err');
  }
}

async function saveSleep() {
  var inp = document.getElementById('sleepBedTimeInput');
  if (!inp) return;
  var val = inp.value;
  var errMsg = validateBedTime(val);
  if (errMsg) {
    toast(errMsg, 'err');
    return;
  }
  try {
    var r = await api('/api/state/sleep', {
      method: 'POST',
      body: JSON.stringify({ bed_time: val, status: 'on_time' })
    });
    toast('睡眠记录已保存', 'suc');
    document.getElementById('sleepBedTimeDisplay').textContent = r.bed_time || val;
    document.getElementById('sleepStreakDisplay').textContent = String(
      r.sleep_early_streak != null ? r.sleep_early_streak : 0
    );
    loadWeeklyEnergyTable();
  } catch (e) {
    toast(e.message || '保存失败', 'err');
  }
}

async function loadWeeklyEnergyTable() {
  var wrap = document.getElementById('weeklyEnergyTable');
  if (!wrap) return;
  try {
    var rows = await api('/api/state/weekly-energy');
    if (!Array.isArray(rows) || !rows.length) {
      wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">暂无能量记录</p>';
      return;
    }
    var cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 6);
    var cutoffStr = cutoff.toISOString().slice(0, 10);
    var filtered = rows.filter(function (r) { return r.date >= cutoffStr; });
    if (!filtered.length) {
      wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">暂无能量记录</p>';
      return;
    }
    var html = '<table class="energy-table"><thead><tr><th>日期</th><th>早</th><th>午</th><th>晚</th><th>基调</th></tr></thead><tbody>';
    filtered.forEach(function (r) {
      html += '<tr><td>' + r.date + '</td><td>' + (r.energy_morning != null ? r.energy_morning : '-') +
        '</td><td>' + (r.energy_afternoon != null ? r.energy_afternoon : '-') +
        '</td><td>' + (r.energy_evening != null ? r.energy_evening : '-') +
        '</td><td>' + (r.daily_tone || '-') + '</td></tr>';
    });
    html += '</tbody></table>';
    wrap.innerHTML = html;
  } catch (e) {
    wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">能量数据加载失败</p>';
    toast('能量数据加载失败', 'err');
  }
}

// ============ INIT ============
document.getElementById('promptRefreshBtn').addEventListener('click', loadPromptList);
document.getElementById('promptCopyBtn').addEventListener('click', copyPromptContent);
document.getElementById('promptEditBtn').addEventListener('click', enterPromptEdit);
document.getElementById('promptPreviewBtn').addEventListener('click', previewPromptDiff);
document.getElementById('promptCancelEditBtn').addEventListener('click', cancelPromptEdit);
document.getElementById('promptRestoreBtn').addEventListener('click', restorePromptLatest);
document.getElementById('promptDiffCancelBtn').addEventListener('click', cancelPromptDiffModal);
document.getElementById('promptDiffConfirmBtn').addEventListener('click', confirmPromptSave);
document.getElementById('activityAddBtn').addEventListener('click', addActivity);
document.getElementById('activityMgrCloseBtn').addEventListener('click', closeActivityMgr);
document.getElementById('discardPileOpenBtn').addEventListener('click', openDiscardPileModal);
document.getElementById('discardPileCloseBtn').addEventListener('click', closeDiscardPileModal);
document.getElementById('stateAssessmentOpenBtn').addEventListener('click', openStateAssessmentModal);
document.getElementById('stateAssessmentCancelBtn').addEventListener('click', closeStateAssessmentModal);
document.getElementById('stateAssessmentSaveBtn').addEventListener('click', saveStateAssessment);
document.getElementById('timerStartBtn').addEventListener('click', startTimer);
document.getElementById('timerPauseBtn').addEventListener('click', toggleTimerDockPause);
document.getElementById('timerStopBtn').addEventListener('click', stopTimer);
document.getElementById('timerOutcomeCancelBtn').addEventListener('click', function () {
  closeModal('timerOutcomeModal');
});
document.querySelectorAll('[data-timer-outcome]').forEach(function (btn) {
  btn.addEventListener('click', function () {
    handleTimerOutcome(btn.getAttribute('data-timer-outcome'));
  });
});
document.getElementById('taskFeedbackConfirmBtn').addEventListener('click', confirmTaskFeedbackModal);
document.getElementById('taskFeedbackCancelBtn').addEventListener('click', cancelTaskFeedbackModal);
document.getElementById('agentReadonlyOpenBtn').addEventListener('click', openAgentReadonlyModal);
document.getElementById('agentReadonlyCloseBtn').addEventListener('click', closeAgentReadonlyModal);
document.querySelectorAll('.agent-ro-tab').forEach(function (btn) {
  btn.addEventListener('click', function () {
    switchAgentTab(btn.getAttribute('data-agent-tab'));
  });
});
document.getElementById('sleepSaveBtn').addEventListener('click', saveSleep);

// ============ 启动加载 ============
loadTasks();
loadTags();
refreshGachaStats();
renderSchedule();
loadSleepPanel();
loadStateAssessmentPanel();
loadTimerPanel();
initTimerDock();
updateDiscardPileVisual();
