
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
  setTimeout(function () { d.remove(); }, 3000);
}
function showModal(id) { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

// ============ ENCOURAGEMENT FEEDBACK (温情心理安抚版) ============
var TASK_FEEDBACK_PRESETS = {
  refuse: {
    title: '换个任务也好',
    subtitle: '今天适合自己的节奏最重要',
    options: [
      { label: '想换个轻松点的', category: 'refuse_easier', detail: '想换个轻松点的' },
      { label: '今天不太想做这个', category: 'refuse_mood', detail: '今天不太想做这个' },
      { label: '现在精力不够', category: 'refuse_energy', detail: '现在精力不够' },
      { label: '只是想看看', category: 'refuse_curious', detail: '只是想看看' }
    ],
    cancelLabel: '不用了',
    confirmLabel: '换个任务',
    encouragementType: 0
  },
  overtime: {
    title: '这次花的时间比预计长，但你坚持做完了，这很棒',
    subtitle: '',
    options: [
      { label: '把任务拆小一点', category: 'overtime_split', detail: '把任务拆小一点' },
      { label: '下次多预留时间', category: 'overtime_more_time', detail: '下次多预留时间' },
      { label: '先做更简单的热身', category: 'overtime_warmup', detail: '先做更简单的热身' }
    ],
    cancelLabel: '知道了',
    confirmLabel: '谢谢鼓励',
    encouragementType: 0
  },
  finish_early: {
    title: '这么快就完成了，状态不错',
    subtitle: '',
    options: [
      { label: '今天状态特别好', category: 'early_good_state', detail: '今天状态特别好' },
      { label: '任务比预期简单', category: 'early_easier', detail: '任务比预期简单' },
      { label: '之前已经复习过了', category: 'early_reviewed', detail: '之前已经复习过了' }
    ],
    cancelLabel: '开心',
    confirmLabel: '记录',
    encouragementType: 0
  },
  abandon: {
    title: '今天先到这里，休息一下也好',
    subtitle: '调整节奏才能走得更远',
    options: [
      { label: '延期到明天', category: 'abandon_defer', detail: '延期到明天' },
      { label: '拆成更小的步骤', category: 'abandon_split', detail: '拆成更小的步骤' },
      { label: '换一个更轻松的任务', category: 'abandon_easier', detail: '换一个更轻松的任务' }
    ],
    cancelLabel: '休息一下',
    confirmLabel: '帮我调整',
    encouragementType: 0
  },
  skip: {
    title: '先跳过没关系，记得回来就好',
    subtitle: '',
    options: [
      { label: '今天状态不太好', category: 'skip_mood', detail: '今天状态不太好' },
      { label: '这个任务不太紧急', category: 'skip_priority', detail: '这个任务不太紧急' },
      { label: '想先做别的', category: 'skip_other', detail: '想先做别的' }
    ],
    cancelLabel: '好的',
    confirmLabel: '跳过',
    encouragementType: 0
  },
  complete_encourage: {
    title: '又完成一个，今日进度加一',
    subtitle: '',
    options: [],
    cancelLabel: '',
    confirmLabel: '继续努力',
    encouragementType: 1
  },
  daily_greeting: {
    title: '早安，今天又是充满可能的一天',
    subtitle: '',
    options: [],
    cancelLabel: '',
    confirmLabel: '看看任务',
    encouragementType: 3
  },
  streak: {
    title: '连续完成 5 个任务',
    subtitle: '继续保持这个节奏',
    options: [],
    cancelLabel: '继续',
    confirmLabel: '保持节奏',
    encouragementType: 2
  }
};

var _taskFeedbackResolve = null;
var _taskFeedbackContext = null;
var _taskFeedbackPresetKey = null;
var _completedStreak = 0;
var _completedToday = 0;

function submitTaskFeedbackEvent(payload) {
  return api('/api/task-feedback', {
    method: 'POST',
    body: JSON.stringify(payload)
  }).catch(function (e) {
    toast(e.message || '保存失败', 'err');
  });
}

function showEncouragement(key) {
  var preset = TASK_FEEDBACK_PRESETS[key];
  if (!preset) return;
  var modal = document.getElementById('taskFeedbackModal');
  document.getElementById('taskFeedbackTitle').textContent = preset.title;
  document.getElementById('taskFeedbackQuestion').textContent = preset.subtitle || '';
  var sub = document.getElementById('taskFeedbackSubtitle');
  if (preset.subtitle) {
    sub.textContent = preset.subtitle;
    sub.style.display = '';
  } else {
    sub.style.display = 'none';
  }
  var html = preset.options.map(function (opt, idx) {
    return '<label class="feedback-option"><input type="radio" name="taskFbOpt" value="' + idx +
      '"> ' + opt.label + '</label>';
  }).join('');
  document.getElementById('taskFeedbackOptions').innerHTML = html;
  if (preset.options.length === 0) {
    document.getElementById('taskFeedbackOptions').style.display = 'none';
    document.getElementById('taskFeedbackNote').parentElement.style.display = 'none';
  } else {
    document.getElementById('taskFeedbackOptions').style.display = '';
    document.getElementById('taskFeedbackNote').parentElement.style.display = '';
  }
  document.getElementById('taskFeedbackNote').value = '';
  document.getElementById('taskFeedbackCancelBtn').textContent = preset.cancelLabel || '关闭';
  document.getElementById('taskFeedbackConfirmBtn').textContent = preset.confirmLabel || '好的';
  _taskFeedbackPresetKey = key;
  showModal('taskFeedbackModal');
}

function promptTaskFeedback(presetKey, context) {
  var preset = TASK_FEEDBACK_PRESETS[presetKey];
  if (!preset) return Promise.resolve({ saved: false });
  _taskFeedbackContext = context || {};
  showEncouragement(presetKey);
  return new Promise(function (resolve) {
    _taskFeedbackResolve = resolve;
  });
}

function confirmTaskFeedbackModal() {
  var preset = TASK_FEEDBACK_PRESETS[_taskFeedbackPresetKey];
  if (!preset) { closeModal('taskFeedbackModal'); return; }

  var selected = document.querySelector('input[name="taskFbOpt"]:checked');
  var opt = null;
  if (selected && preset.options.length > 0) {
    var idx = parseInt(selected.value, 10);
    opt = preset.options[idx];
  }

  var ctx = _taskFeedbackContext || {};
  var note = (document.getElementById('taskFeedbackNote').value || '').trim();
  var payload = {
    task_id: ctx.taskId || null,
    event_type: _taskFeedbackPresetKey,
    planned_minutes: ctx.plannedMinutes,
    actual_minutes: ctx.actualMinutes,
    completion_status: ctx.completionStatus,
    reason_category: opt ? opt.category : 'none',
    reason_detail: opt ? opt.detail : '',
    note: note || null,
    encouragement_shown: preset.encouragementType || 0,
    encouragement_type: preset.encouragementType || 0
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

function runWithSkipFeedback(taskId, actionFn) {
  var ctx = getTaskFeedbackContext(taskId);
  ctx.completionStatus = 'skipped';
  return promptTaskFeedback('skip', ctx).then(function () {
    return actionFn();
  });
}

function showPage(id) {
  document.querySelectorAll('.page').forEach(function (p) { p.classList.remove('active'); });
  document.getElementById('page-' + id).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(function (b) { b.classList.remove('active'); });
  document.querySelector('[data-page="' + id + '"]').classList.add('active');
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

// Nav
document.querySelectorAll('.nav-btn').forEach(function (b) {
  b.addEventListener('click', function () {
    var p = b.dataset.page;
    showPage(p);
    if (p === 'gacha') refreshGachaStats();
    if (p === 'tasks') { renderTasks(); loadTags(); loadTimerPanel(); }
    if (p === 'schedule') {
      renderSchedule();
      loadSleepPanel();
      loadStateAssessmentPanel();
    }
    if (p === 'knowledge') loadCategories();
    if (p === 'config') {
      loadConfigForm();
      loadPromptList();
    }
  });
});

// Health check
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

// ============ TASK CARD (P1-Visual-1) ============
var CARD_THEME_SYMBOLS = {
  'theme-math': '∑', 'theme-lang': 'Aa', 'theme-history': '⏳',
  'theme-code': '{ }', 'theme-write': '✎', 'theme-science': '⚛',
  'theme-review': '↻', 'theme-default': '◆'
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
  var sym = CARD_THEME_SYMBOLS[theme] || '◆';
  var corner = CARD_CORNER_LABELS[task.category] || '任务';
  var tags = (task.tags || []).map(function (x) {
    return '<span class="badge bg-gold">' + x + '</span>';
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
    '<div class="task-card-title">' + task.name + '</div>' +
    '<div class="task-card-desc">' + (task.description || '').substring(0, opts.descLen || 100) + '</div>' +
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

// ============ GACHA ============
var gachaState = { energy: 'medium', pool: 'fragment', canReplace: true, replacedTaskId: null, feedbackMood: 3 };
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
document.getElementById('gachaBtn').addEventListener('click', drawGacha);

function disableGachaBtn() {
  var btn = document.getElementById('gachaBtn');
  if (btn) { btn.disabled = true; btn.classList.add('btn-disabled'); }
}
function enableGachaBtn() {
  var btn = document.getElementById('gachaBtn');
  if (btn) { btn.disabled = false; btn.classList.remove('btn-disabled'); }
}

async function drawGacha() {
  disableGachaBtn();
  var time = parseInt(document.getElementById('gachaTime').value, 10) || 30;
  var count = parseInt(document.getElementById('gachaCount').value, 10) || 1;
  var result = document.getElementById('gachaResult');
  var deck = document.getElementById('gachaDeck');
  result.innerHTML = '';
  if (deck) deck.classList.add('is-drawing');
  for (var i = 0; i < count; i++) {
    try {
      var r = await api('/api/gacha/draw', {
        method: 'POST',
        body: JSON.stringify({ pool: gachaState.pool, energy: gachaState.energy, available_time: time })
      });
      if (r.task) {
        gachaState.canReplace = r.can_replace !== false;
        var wrap = await flyCardToResult(deck, result, r.task);
        result.appendChild(wrap);
      } else if (count === 1) {
        if (deck) deck.classList.remove('is-drawing');
        result.innerHTML = '<div class="empty-state mt24"><i class="fa-solid fa-box-open"></i><p></p></div>';
        enableGachaBtn();
        return;
      }
    } catch (e) {
      if (deck) deck.classList.remove('is-drawing');
      toast(e.message || '抽卡失败', 'err');
      enableGachaBtn();
      return;
    }
  }
  if (deck) deck.classList.remove('is-drawing');
  refreshGachaStats();
}

function flyCardToResult(deckEl, resultEl, task) {
  return new Promise(function (resolve) {
    if (!deckEl) { resolve(); return; }
    var start = deckEl.getBoundingClientRect();
    var end = resultEl.getBoundingClientRect();

    if (end.height < 20) {
      var vw = window.innerWidth, vh = window.innerHeight;
      end = { left: vw / 2 - 74, top: vh * 0.38 - 98, width: 148, height: 196 };
    }

    var startX = start.left + start.width / 2 - 74;
    var startY = start.top + start.height / 2 - 98;
    var endX = end.left + end.width / 2 - 140;
    var endY = end.top + end.height / 2 - 98;

    // Build the final task card structure
    var theme = resolveTaskCardTheme(task);
    var urgent = task.deadline && new Date(task.deadline) > new Date() &&
      (new Date(task.deadline) - new Date()) / 86400000 < 1;
    var actions =
      '<button class="btn pri sm" onclick="startTaskWithTimer(' + task.id + ')" title="开始计时完成任务"><i class="fa-solid fa-play"></i> 开始</button>' +
      (gachaState.canReplace ? '<button class="btn sm" onclick="showReplaceReason(' + task.id + ')" title="换一张牌"><i class="fa-solid fa-shuffle"></i> 换牌</button>' : '');

    var wrap = document.createElement('div');
    wrap.className = 'drawn-card-stage';

    var card = document.createElement('div');
    card.className = 'task-card card drawn-card ' + theme + (urgent ? ' urgent' : '');
    card.setAttribute('data-task-id', task.id);
    card.innerHTML =
      '<div class="task-card-inner">' +
      '<div class="task-card-face task-card-back"><div class="card-back-pattern"></div><div class="card-back-emblem">\u2726</div></div>' +
      '<div class="task-card-face task-card-front">' +
      buildTaskCardBodyHtml(task, { actionsHtml: actions, descLen: 120, showRepeat: false }) +
      '</div></div>';

    // Start as fixed-position flight card
    card.classList.add('flying-card-no-transform');
    card.style.position = 'fixed';
    card.style.left = startX + 'px';
    card.style.top = startY + 'px';
    card.style.zIndex = '9999';
    card.style.opacity = '0';
    card.style.transform = 'scale(0.5)';
    card.style.width = '148px';
    card.style.height = '196px';
    card.style.pointerEvents = 'none';
    card.style.transition = 'none';
    wrap.appendChild(card);
    document.body.appendChild(wrap);

    var mid = { left: window.innerWidth * 0.3, top: window.innerHeight * 0.2 };
    var startTime = performance.now();
    var duration = 600;

    function easeOutQuad(p) { return 1 - (1 - p) * (1 - p); }

    function animate(now) {
      var elapsed = now - startTime;
      var t = Math.min(1, elapsed / duration);

      var left, top, scale, rotate, opacity;
      if (t < 0.4) {
        var p = t / 0.4;
        var e = easeOutQuad(p);
        left = startX + (mid.left - startX) * e;
        top = startY + (mid.top - startY) * e;
        scale = 0.5 + (1.2 - 0.5) * e;
        rotate = 0 + 20 * e;
        opacity = 0.6 + (1 - 0.6) * e;
      } else {
        var p2 = (t - 0.4) / 0.6;
        var e2 = easeOutQuad(p2);
        left = mid.left + (endX - mid.left) * e2;
        top = mid.top + (endY - mid.top) * e2;
        scale = 1.2 + (1.0 - 1.2) * e2;
        rotate = 20 * (1 - e2);
        opacity = 1;
      }

      card.style.left = left + 'px';
      card.style.top = top + 'px';
      card.style.transform = 'scale(' + scale + ') rotate(' + rotate + 'deg)';
      card.style.opacity = opacity;

      if (t < 1) {
        requestAnimationFrame(animate);
      } else {
        // Land: convert to final display card
        card.classList.remove('flying-card-no-transform');
        card.style.position = '';
        card.style.left = '';
        card.style.top = '';
        card.style.zIndex = '';
        card.style.opacity = '';
        card.style.transform = '';
        card.style.width = '';
        card.style.height = '';
        card.style.pointerEvents = '';
        card.style.transition = '';

        wrap.style.position = '';
        wrap.style.left = '';
        wrap.style.top = '';
        wrap.style.zIndex = '';
        wrap.style.width = '';

        // Remove from body, will be re-appended by caller
        document.body.removeChild(wrap);

        // Trigger flip animation
        requestAnimationFrame(function () {
          card.classList.add('is-drawing');
          requestAnimationFrame(function () {
            requestAnimationFrame(function () {
              card.classList.add('is-revealing');
            });
          });
        });

        resolve(wrap);
      }
    }

    requestAnimationFrame(animate);
  });
}

function renderDrawnCard(task, idx) {
  var theme = resolveTaskCardTheme(task);
  var urgent = task.deadline && new Date(task.deadline) > new Date() &&
    (new Date(task.deadline) - new Date()) / 86400000 < 1;
  var actions =
    '<button class="btn pri sm" onclick="startTaskWithTimer(' + task.id + ')" title="开始计时完成任务"><i class="fa-solid fa-play"></i> 开始</button>' +
    (gachaState.canReplace ? '<button class="btn sm" onclick="showReplaceReason(' + task.id + ')" title="换一张牌"><i class="fa-solid fa-shuffle"></i> 换牌</button>' : '');
  var wrap = document.createElement('div');
  wrap.className = 'drawn-card-stage';
  var card = document.createElement('div');
  card.className = 'task-card card drawn-card ' + theme + (urgent ? ' urgent' : '');
  card.setAttribute('data-task-id', task.id);
  card.style.animationDelay = (idx * 0.15) + 's';
  card.innerHTML =
    '<div class="task-card-inner">' +
    '<div class="task-card-face task-card-back"><div class="card-back-pattern"></div><div class="card-back-emblem">✦</div></div>' +
    '<div class="task-card-face task-card-front">' +
    buildTaskCardBodyHtml(task, { actionsHtml: actions, descLen: 120, showRepeat: false }) +
    '</div></div>';
  card.classList.add('is-drawing');
  wrap.appendChild(card);
  requestAnimationFrame(function () {
    requestAnimationFrame(function () { card.classList.add('is-revealing'); });
  });
  return wrap;
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
      body: JSON.stringify({ task_id: rid, reason: reason, pool: gachaState.pool, energy: gachaState.energy })
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

function handleSkip(id) {
  runWithSkipFeedback(id, function () {
    return api('/api/tasks/' + id + '/skip', { method: 'POST' }).then(function (r) {
      return playCardAnim(id, 'is-skipping', 400).then(function () {
        document.getElementById('gachaResult').innerHTML =
          '<div class="empty-state"><i class="fa-solid fa-forward"></i><p>已跳过</p></div>';
        enableGachaBtn();
        if (r.unlocked_tasks && r.unlocked_tasks.length) toast('已解锁: ' + r.unlocked_tasks.join('、'), 'suc');
        refreshGachaStats();
        loadTasks();
      });
    });
  }).catch(function (e) { toast(e.message || '跳过失败', 'err'); });
}

function handleRefuse(id) {
  var ctx = getTaskFeedbackContext(id);
  ctx.completionStatus = 'refused';
  promptTaskFeedback('refuse', ctx).then(function () {
    return api('/api/tasks/' + id + '/refuse', { method: 'POST' });
  }).then(function () {
    return playCardAnim(id, 'is-refusing');
  }).then(function () {
    document.getElementById('gachaResult').innerHTML =
      '<div class="empty-state"><i class="fa-solid fa-xmark"></i><p>已拒绝</p></div>';
    enableGachaBtn();
    refreshGachaStats();
  }).catch(function (e) { toast(e.message || '拒绝失败', 'err'); });
}

async function completeWithFeedback(id) {
  var task = allTasks.find(function (x) { return x.id === id; });
  if (task && !task.is_unlocked) {
    toast(prereqHint(task) || '任务被前置依赖阻塞', 'err');
    return;
  }
  try {
    var r = await api('/api/tasks/' + id + '/complete', { method: 'POST' });
    if (r.unlocked_tasks && r.unlocked_tasks.length) {
      toast('已解锁: ' + r.unlocked_tasks.join('、'), 'suc');
    }
    await playCardAnim(id, 'is-completing is-evaporating is-fly-to-pile', 500);
    document.getElementById('fbTaskId').value = id;
    document.getElementById('fbEnergy').value = 5;
    document.getElementById('fbEnergyVal').textContent = '5';
    gachaState.feedbackMood = 3;
    showModal('feedbackModal');
    setTimeout(function () { submitFeedback(); closeModal('feedbackModal'); }, 3000);
    enableGachaBtn();
    loadTasks();
    refreshGachaStats();
  } catch (e) {
    toast(e.message || '完成失败', 'err');
  }
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
    '<div class="empty-state"><i class="fa-solid fa-circle-check" style="color:var(--green)"></i><p>任务完成!</p></div>';
  refreshGachaStats();
}

function cancelFeedback() {
  closeModal('feedbackModal');
}

async function refreshGachaStats() {
  try {
    var r = await api('/api/gacha/statistics');
    var s = document.getElementById('gachaStats');
    s.innerHTML =
      '<div class="card stat-card"><div class="stat-val">' + r.total_draws + '</div><div class="stat-lbl">总抽卡</div></div>' +
      '<div class="card stat-card"><div class="stat-val">' + r.acceptance_rate + '%</div><div class="stat-lbl">接受率</div></div>' +
      '<div class="card stat-card"><div class="stat-val">' + r.rejections + '</div><div class="stat-lbl">拒绝数</div></div>';
  } catch (e) { /* 统计失败不阻塞 */ }
}

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
        '" onclick="filterByTag(' + t.id + ')">' + t.name + ' (' + t.task_count + ')</span>';
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
  var search = document.getElementById('taskSearch').value.toLowerCase();
  var filter = document.getElementById('taskFilter').value;
  var tasks = allTasks;
  if (search) tasks = tasks.filter(function (t) { return t.name.toLowerCase().indexOf(search) >= 0; });
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
      '<button class="btn sm" onclick="openTaskEdit(' + t.id + ')" title="编辑任务"><i class="fa-solid fa-pen"></i> 编辑</button>' +
      (canAct ? '<button class="btn pri sm" onclick="completeWithFeedback(' + t.id + ')" title="标记完成"><i class="fa-solid fa-check"></i> 完成</button>' : '') +
      (canAct ? '<button class="btn sm" onclick="taskSkip(' + t.id + ')" title="跳过任务"><i class="fa-solid fa-forward"></i> 跳过</button>' : '') +
      (canAct ? '<button class="btn sm" onclick="taskRefuse(' + t.id + ')" title="拒绝任务"><i class="fa-solid fa-xmark"></i> 拒绝</button>' : '') +
      (!t.in_discard_pile && !t.completed ? '<button class="btn sm" onclick="moveToDiscard(' + t.id + ')" title="移入弃牌堆"><i class="fa-solid fa-box-archive"></i> 弃牌</button>' : '') +
      '<button class="btn danger sm" onclick="deleteTask(' + t.id + ')" title="删除任务"><i class="fa-solid fa-trash"></i> 删除</button>';
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

function taskSkip(id) {
  runWithSkipFeedback(id, function () {
    return api('/api/tasks/' + id + '/skip', { method: 'POST' }).then(function (r) {
      return playCardAnim(id, 'is-skipping', 400).then(function () {
        toast('已跳过', 'suc');
        if (r.unlocked_tasks && r.unlocked_tasks.length) toast('已解锁: ' + r.unlocked_tasks.join('、'), 'suc');
        loadTasks();
      });
    });
  }).catch(function (e) { toast(e.message || '跳过失败', 'err'); });
}

function taskRefuse(id) {
  var ctx = getTaskFeedbackContext(id);
  ctx.completionStatus = 'refused';
  promptTaskFeedback('skip', ctx).then(function () {
    return api('/api/tasks/' + id + '/refuse', { method: 'POST' });
  }).then(function () {
    return playCardAnim(id, 'is-refusing');
  }).then(function () {
    toast('已记录拒绝', 'inf');
    loadTasks();
  }).catch(function (e) { toast(e.message || '拒绝失败', 'err'); });
}

function moveToDiscard(id) {
  var ctx = getTaskFeedbackContext(id);
  ctx.completionStatus = 'abandoned';
  promptTaskFeedback('abandon', ctx).then(function () {
    return api('/api/tasks/' + id + '/move-to-discard', { method: 'POST' });
  }).then(function () {
    return playCardAnim(id, 'is-discarding', 500);
  }).then(function () {
    toast('已移入弃牌堆', 'inf');
    loadTasks();
  }).catch(function (e) { toast(e.message || '操作失败', 'err'); });
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
      var status = discardTaskStatus(t);
      var discardedAt = formatDiscardTime(t.last_completed_at || t.updated_at);
      var safeName = String(t.name || '').replace(/</g, '&lt;').replace(/"/g, '&quot;');
      return '<div class="activity-row discard-row" data-id="' + t.id + '">' +
        '<div style="flex:1;min-width:0">' +
        '<div><strong>#' + t.id + '</strong> ' + safeName +
        ' <span class="badge bg-red" style="font-size:.75rem">' + status + '</span></div>' +
        '<div style="color:var(--text-muted);font-size:.8rem;margin-top:4px">' +
        repeat + ' · 弃牌于 ' + discardedAt + '</div>' +
        (tags ? '<div class="flex gap8 wrap mt4">' + tags + '</div>' : '') +
        '</div>' +
        '<button type="button" class="btn pri sm discard-restore-btn" data-id="' + t.id + '" data-name="' + safeName + '" title="恢复任务到列表">' +
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
  if (!confirm('确定将「' + (name || ('#' + id)) + '」从弃牌堆恢复？恢复后可重新参与抽卡。')) return;
  api('/api/discard-pile/' + id + '/restore', { method: 'POST', body: JSON.stringify({}) }).then(function () {
    toast('已恢复任务', 'suc');
    loadDiscardPileList();
    loadTasks();
    refreshGachaStats();
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
  document.getElementById('tfExistingTags').innerHTML = allTags.map(function (t) {
    return '<span class="badge bg-blue tag-pick" data-tag="' + t.name.replace(/"/g, '&quot;') + '">' + t.name + '</span>';
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
  document.getElementById('tfTagChips').innerHTML = '';
  window._tfTags = [];
  buildDepList([]);
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
      t.name + done + ' <span class="note-meta">ID:' + t.id + '</span></label>';
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
    var notes = await api('/api/knowledge/notes');
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

function mdToHtml(md) {
  if (!md) return '';
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
    ta.value = pr.exists ? (pr.content || '') : '（提示词文件不存在：' + (agent.prompt_file || '') + '）';
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
        if (name === '已分类') next = '已分类';
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
    if (r.success) toast('已保存', 'suc');
    else toast('保存失败: ' + (r.error || ''), 'err');
  } catch (e) {
    toast(e.message || '保存失败', 'err');
  }
}

// ============ PROMPTS (read-only + editable) ============
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
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
    opts += '<option value="' + t.id + '">' + String(t.name).replace(/</g, '&lt;') + '</option>';
  });
  sel.innerHTML = opts;
  if (current) sel.value = current;
}

function updateTimerDisplay() {
  var statusEl = document.getElementById('timerStatusText');
  var elapsedEl = document.getElementById('timerElapsedDisplay');
  var startBtn = document.getElementById('timerStartBtn');
  var stopBtn = document.getElementById('timerStopBtn');
  var sel = document.getElementById('timerTaskSelect');
  var planned = document.getElementById('timerPlannedMin');
  if (!statusEl || !elapsedEl) return;

  if (timerActiveSession && timerActiveSession.started_at) {
    var started = new Date(timerActiveSession.started_at).getTime();
    var pausedSec = timerActiveSession.paused_duration || 0;
    var isPaused = timerActiveSession.status === 'paused';
    var elapsed = isPaused ? (new Date(timerActiveSession.paused_at).getTime() - started - pausedSec * 1000) : (Date.now() - started - pausedSec * 1000);
    elapsedEl.textContent = formatElapsed(elapsed);
    var name = timerActiveSession.task_name || taskNameById(timerActiveSession.task_id);
    statusEl.textContent = (isPaused ? '已暂停 · ' : '计时中 · ') + name + '（计划 ' + (timerActiveSession.planned_minutes || '?') + ' 分）';
    statusEl.className = isPaused ? 'timer-paused' : '';
    if (startBtn) startBtn.classList.add('hidden');
    if (stopBtn) stopBtn.classList.remove('hidden');
    if (sel) sel.disabled = true;
    if (planned) planned.disabled = true;
  } else {
    elapsedEl.textContent = '00:00';
    statusEl.textContent = '未在计时';
    statusEl.className = 'timer-idle';
    if (startBtn) startBtn.classList.remove('hidden');
    if (stopBtn) stopBtn.classList.add('hidden');
    if (sel) sel.disabled = false;
    if (planned) planned.disabled = false;
  }
  updateGachaTimerBar();
}

function updateGachaTimerBar() {
  var bar = document.getElementById('gachaTimerBar');
  var empty = document.getElementById('gachaTimerEmpty');
  if (!bar || !empty) return;
  if (timerActiveSession && timerActiveSession.started_at) {
    var started = new Date(timerActiveSession.started_at).getTime();
    var pausedSec = timerActiveSession.paused_duration || 0;
    var isPaused = timerActiveSession.status === 'paused';
    var elapsed = isPaused ? (new Date(timerActiveSession.paused_at).getTime() - started - pausedSec * 1000) : (Date.now() - started - pausedSec * 1000);
    var name = timerActiveSession.task_name || taskNameById(timerActiveSession.task_id);
    document.getElementById('gachaTimerElapsed').textContent = formatElapsed(elapsed);
    document.getElementById('gachaTimerTaskName').textContent = (isPaused ? '[已暂停] ' : '') + name;
    bar.style.display = 'flex';
    empty.style.display = 'none';
    // Update pause/resume button
    var btn = bar.querySelector('.timer-bar-actions button:first-child');
    if (btn) {
      if (isPaused) {
        btn.textContent = '继续';
        btn.setAttribute('onclick', 'resumeTimer()');
      } else {
        btn.textContent = '暂停';
        btn.setAttribute('onclick', 'pauseTimer()');
      }
    }
  } else {
    bar.style.display = 'none';
    empty.style.display = 'flex';
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
    timerActiveSession = r && r.id ? r : null;
    updateTimerDisplay();
    startTimerTick();
    if (timerActiveSession && timerActiveSession.task_id) {
      restoreGachaCardFromSession();
    }
  } catch (e) {
    timerActiveSession = null;
    updateTimerDisplay();
    toast(e.message || '计时器状态加载失败', 'err');
  }
}

async function restoreGachaCardFromSession() {
  var taskId = timerActiveSession.task_id;
  var result = document.getElementById('gachaResult');
  if (!result) return;
  try {
    var r = await api('/api/tasks/' + taskId);
    if (!r || !r.id) return;
    var task = r;
    var theme = resolveTaskCardTheme(task);
    var urgent = task.deadline && new Date(task.deadline) > new Date() &&
      (new Date(task.deadline) - new Date()) / 86400000 < 1;

    var isPaused = timerActiveSession.status === 'paused';
    var actions;
    if (isPaused) {
      actions = '<button class="btn sm" onclick="resumeTimer()" title="恢复计时">继续</button>' +
        '<button class="btn pri sm" onclick="completeFromGachaCard(' + task.id + ')" title="完成任务">完成</button>';
    } else {
      actions = '<button class="btn sm" onclick="pauseTimer()" title="暂停计时">暂停</button>' +
        '<button class="btn pri sm" onclick="completeFromGachaCard(' + task.id + ')" title="完成任务">完成</button>';
    }

    var wrap = document.createElement('div');
    wrap.className = 'drawn-card-stage';
    var card = document.createElement('div');
    card.className = 'task-card card drawn-card ' + theme + (urgent ? ' urgent' : '');
    card.setAttribute('data-task-id', task.id);
    card.setAttribute('data-restored', '1');
    card.innerHTML =
      '<div class="task-card-inner">' +
      '<div class="task-card-face task-card-back"><div class="card-back-pattern"></div><div class="card-back-emblem">\u2726</div></div>' +
      '<div class="task-card-face task-card-front">' +
      buildTaskCardBodyHtml(task, { actionsHtml: actions, descLen: 120, showRepeat: false }) +
      '</div></div>';
    card.classList.add('is-revealing');
    wrap.appendChild(card);

    result.innerHTML = '';
    result.appendChild(wrap);
    disableGachaBtn();
  } catch (e) {
    // silent — task may have been deleted
  }
}

window.addEventListener('beforeunload', function (e) {
  if (timerActiveSession && timerActiveSession.status === 'running') {
    e.preventDefault();
    e.returnValue = '有任务正在进行中，确定要退出吗？';
    return e.returnValue;
  }
});

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
  var started = new Date(session.started_at).getTime();
  var pausedSec = session.paused_duration || 0;
  var now = session.status === 'paused' && session.paused_at ? new Date(session.paused_at).getTime() : Date.now();
  var actualMinutes = Math.max(1, Math.round((now - started - pausedSec * 1000) / 60000));
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
    updateTimerDisplay();
    toast('计时已结束（' + actualMinutes + ' 分钟）', 'suc');

    var fbCtx = {
      taskId: session.task_id,
      plannedMinutes: planned,
      actualMinutes: actualMinutes,
      completionStatus: outcome
    };
    if (outcome === 'completed') {
      if (actualMinutes <= planned * 0.5) {
        await promptTaskFeedback('finish_early', fbCtx);
      } else if (actualMinutes >= planned * 1.2 && planned > 0) {
        await promptTaskFeedback('overtime', fbCtx);
      } else {
        _completedToday++;
        if (_completedToday === 1) _completedStreak = 1;
        else _completedStreak++;
        if (_completedStreak >= 5) showEncouragement('streak');
        else if (_completedToday <= 3) showEncouragement('complete_encourage');
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
      }
    } else if (outcome === 'unfinished') {
      await promptTaskFeedback('overtime', fbCtx);
    } else if (outcome === 'abandoned') {
      await promptTaskFeedback('abandon', fbCtx);
    }
  } catch (e) {
    toast(e.message || '停止计时失败', 'err');
    await loadTimerPanel();
  }
}

async function startTaskWithTimer(taskId) {
  if (timerActiveSession && timerActiveSession.status !== 'paused') {
    toast('已有进行中的计时，请先完成当前任务', 'err');
    return;
  }
  var task = allTasks.find(function (x) { return x.id === taskId; });
  var minutes = task ? (task.estimated_time || 30) : 30;
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
    toast('计时已开始', 'suc');
    updateTimerDisplay();
    updateGachaCardButtons(taskId);
  } catch (e) {
    toast(e.message || '开始计时失败', 'err');
  }
}

function updateGachaCardButtons(taskId) {
  var card = document.querySelector('.task-card.drawn-card[data-task-id="' + taskId + '"]');
  if (!card) return;
  var footer = card.querySelector('.task-card-footer .task-card-actions');
  if (!footer) return;
  var canReplace = gachaState.canReplace;
  if (timerActiveSession && timerActiveSession.task_id === taskId) {
    footer.innerHTML =
      '<button class="btn sm" onclick="completeFromGachaCard(' + taskId + ')" title="完成任务并记录用时"><i class="fa-solid fa-check"></i> 完成</button>' +
      (canReplace ? '<button class="btn sm" onclick="showReplaceReason(' + taskId + ')" title="换一张牌"><i class="fa-solid fa-shuffle"></i> 换牌</button>' : '');
  } else {
    footer.innerHTML =
      '<button class="btn pri sm" onclick="startTaskWithTimer(' + taskId + ')" title="开始计时完成任务"><i class="fa-solid fa-play"></i> 开始</button>' +
      (canReplace ? '<button class="btn sm" onclick="showReplaceReason(' + taskId + ')" title="换一张牌"><i class="fa-solid fa-shuffle"></i> 换牌</button>' : '');
  }
}

async function completeFromGachaCard(taskId) {
  if (!timerActiveSession || timerActiveSession.task_id !== taskId) {
    toast('请先开始计时', 'err');
    return;
  }
  try {
    var started = new Date(timerActiveSession.started_at).getTime();
    var actualMinutes = Math.max(1, Math.round((Date.now() - started) / 60000));
    await stopTimer();
    var r = await api('/api/tasks/' + taskId + '/complete', { method: 'POST' });
    if (r.unlocked_tasks && r.unlocked_tasks.length) {
      toast('已解锁: ' + r.unlocked_tasks.join('、'), 'suc');
    }
    await playCardAnim(taskId, 'is-completing is-evaporating is-fly-to-pile', 500);
    enableGachaBtn();
    _completedToday++;
    if (_completedToday === 1) _completedStreak = 1;
    else _completedStreak++;
    if (_completedStreak >= 5) showEncouragement('streak');
    else showEncouragement('complete_encourage');
    loadTasks();
    refreshGachaStats();
  } catch (e) {
    toast(e.message || '操作失败', 'err');
  }
}

async function pauseTimer() {
  if (!timerActiveSession || !timerActiveSession.id) {
    toast('当前无进行中的计时', 'err');
    return;
  }
  try {
    var r = await api('/api/timer/pause', { method: 'POST' });
    if (r.status === 'paused') {
      timerActiveSession.status = 'paused';
      timerActiveSession.paused_at = new Date().toISOString();
      updateTimerDisplay();
      toast('计时已暂停', 'suc');
    }
  } catch (e) {
    toast(e.message || '暂停失败', 'err');
  }
}

async function resumeTimer() {
  if (!timerActiveSession || !timerActiveSession.id) {
    toast('当前无暂停的计时', 'err');
    return;
  }
  try {
    var r = await api('/api/timer/resume', { method: 'POST' });
    if (r.status === 'resumed') {
      timerActiveSession.status = 'running';
      timerActiveSession.paused_duration = r.paused_duration || 0;
      timerActiveSession.paused_at = null;
      updateTimerDisplay();
      toast('计时已恢复', 'suc');
    }
  } catch (e) {
    toast(e.message || '恢复失败', 'err');
  }
}

async function completeTimerFromGacha() {
  if (!timerActiveSession || !timerActiveSession.id) {
    toast('当前无进行中的计时', 'err');
    return;
  }
  await stopTimer();
  updateTimerDisplay();
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

async function loadSleepPanel() {
  await loadSleepInfo();
  await loadWeeklyEnergyTable();
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

loadTasks();
loadTags();
refreshGachaStats();
renderSchedule();
loadSleepPanel();
loadStateAssessmentPanel();
loadTimerPanel();
