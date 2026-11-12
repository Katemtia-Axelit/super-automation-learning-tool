
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

// ============ M02-S03-G02-W03：统一抽卡行为事件上报 =============
// 合同（LT_M02_S03_G02）：本 W03 **只** 覆盖"抽卡 / 展示 / 帮我选 / 换卡"。
// - 复用既有 POST /api/task-feedback（后端 server/services/feedback.py 已验收）；
// - note = {schema_version:1, event_id, session_id, source:'unified_gacha', context:{...}}
// - 只记录 **真实** 发生的事：真实 task_id、真实 session/event id、真实参数；
//   绝不虚构时间、完成状态或用户文本（计时/弃牌那 6 个类型留给后续 W04）。
// - 失败必须 **可见**（toast 提示"未送达"），绝不谎称已保存；
// - 发送是 fire-and-forget：**不 await、不阻塞**用户主操作，也不伪造成功。

var UNIFIED_GACHA_EVENT_SOURCE = 'unified_gacha';
var UNIFIED_GACHA_EVENT_SCHEMA_VERSION = 1;

// 本轮抽卡 session：新的 draw / multi / care 开启新 session；
// 同一条连续换卡链 **沿用** 同一个 session；离开抽卡页即结束。
var _unifiedGachaSessionId = null;
// 事件序号：保证同一页面生命周期内 event_id 互不相同。
var _unifiedGachaEventSeq = 0;
// 未送达状态（可复用）：成功 / 失败 / 在途计数 + 最近一次错误 + 可重放的载荷。
// lastFailed 保留 **原 event_id**，所以重发同一个行为仍然是同一个 id（后端幂等）。
var _unifiedGachaEventDelivery = {
  sent: 0,
  failed: 0,
  pending: 0,
  lastError: null,
  lastFailed: null
};
window.unifiedGachaEventDelivery = _unifiedGachaEventDelivery;

// 生成一个真实的 event_id（非空字符串、无控制字符、长度 < 128）。
function newUnifiedGachaEventId(prefix) {
  _unifiedGachaEventSeq += 1;
  return String(prefix || 'evt') + '-' + Date.now().toString(36) +
    '-' + _unifiedGachaEventSeq.toString(36) +
    '-' + Math.random().toString(36).slice(2, 10);
}

// 一次 **真实用户动作** 的标识（一次点击 = 一个 action id）。
// 同一动作派生出的多个事件（card_drawn / card_shown …）共用它，
// 因此重发该动作时 event_id 保持不变（后端按 event_id 幂等）。
function newUnifiedGachaActionId(kind) {
  return newUnifiedGachaEventId('act-' + (kind || 'draw'));
}

// 由 action id 派生出某类事件的稳定 event_id。
function unifiedGachaEventId(actionId, eventType, taskId) {
  var id = String(actionId) + ':' + String(eventType);
  if (taskId !== undefined && taskId !== null) id += ':' + String(taskId);
  return id;
}

// 卡片 **真正渲染进结果区** 后记录 card_shown。
// 去重键 = session + task + 展示面（surface）+ 动作（action）：
// 同一动作内的重复渲染不会造成事件洪水；不同展示面（连抽列表 vs 激活到主卡位）
// 与换牌链上再次出现的同一张卡，都是各自真实的"展示"时刻，分别记一条。
var _unifiedGachaShownKeys = {};
function reportUnifiedGachaCardShown(taskId, context, actionId) {
  var tid = unifiedGachaTaskId(taskId);
  if (tid === null) return Promise.resolve({ ok: false, error: 'invalid task_id' });
  var surface = (context && context.surface) ? String(context.surface) : 'default';
  var action = actionId || ('shown-' + tid);
  var key = getUnifiedGachaSessionId() + '#' + tid + '#' + surface + '#' + action;
  if (_unifiedGachaShownKeys[key]) {
    return Promise.resolve({ ok: true, duplicate: true, skipped: true });
  }
  _unifiedGachaShownKeys[key] = true;
  return sendUnifiedGachaEvent('card_shown', tid, context,
    unifiedGachaEventId(action, 'card_shown', tid));
}

// 开启新 session（一次新的抽卡动作）。
function beginUnifiedGachaSession() {
  _unifiedGachaEventSeq += 1;
  _unifiedGachaSessionId = 'sess-' + Date.now().toString(36) +
    '-' + _unifiedGachaEventSeq.toString(36) +
    '-' + Math.random().toString(36).slice(2, 8);
  // 新 session → card_shown 去重表重置。
  _unifiedGachaShownKeys = {};
  return _unifiedGachaSessionId;
}

// 结束 session（离开抽卡页）。
function endUnifiedGachaSession() {
  _unifiedGachaSessionId = null;
}

// 取当前 session id；没有就开一个（保证 session_id 永远非空）。
function getUnifiedGachaSessionId() {
  if (!_unifiedGachaSessionId) beginUnifiedGachaSession();
  return _unifiedGachaSessionId;
}

// 严格取正整数 task id；不是正整数返回 null（绝不伪造 id）。
function unifiedGachaTaskId(value) {
  var n = (typeof value === 'number') ? value : Number(value);
  if (!isFinite(n) || Math.floor(n) !== n || n <= 0) return null;
  return n;
}

// 发送一条统一抽卡行为事件。
// eventType ∈ {card_drawn, card_shown, help_me_choose, card_replaced}
// context  只放 **真实已知** 的实际参数。
// eventId  由调用方在"用户动作发生的那一刻"生成一次；同一动作重发用同一个
//           id（后端按 event_id 幂等）。
function sendUnifiedGachaEvent(eventType, taskId, context, eventId) {
  var tid = unifiedGachaTaskId(taskId);
  if (tid === null) {
    // 没有真实 task id → 绝不发送，也绝不谎称成功。
    return Promise.resolve({ ok: false, error: 'invalid task_id' });
  }
  var eid = eventId || newUnifiedGachaEventId(eventType);
  var note = {
    schema_version: UNIFIED_GACHA_EVENT_SCHEMA_VERSION,
    event_id: eid,
    session_id: getUnifiedGachaSessionId(),
    source: UNIFIED_GACHA_EVENT_SOURCE,
    context: (context && typeof context === 'object') ? context : {}
  };
  _unifiedGachaEventDelivery.pending += 1;
  var payload = {
    task_id: tid,
    event_type: eventType,
    reason_category: 'other',
    note: JSON.stringify(note)
  };
  return api('/api/task-feedback', {
    method: 'POST',
    body: JSON.stringify(payload)
  }).then(function (res) {
    _unifiedGachaEventDelivery.pending -= 1;
    _unifiedGachaEventDelivery.sent += 1;
    _unifiedGachaEventDelivery.lastFailed = null;
    return {
      ok: true,
      id: res && res.id,
      status: res && res.status,
      duplicate: !!(res && res.duplicate)
    };
  }).catch(function (e) {
    _unifiedGachaEventDelivery.pending -= 1;
    _unifiedGachaEventDelivery.failed += 1;
    _unifiedGachaEventDelivery.lastError = (e && e.message) ? e.message : '未知错误';
    // 保留未送达载荷（供重试；event_id 不变）。
    _unifiedGachaEventDelivery.lastFailed = payload;
    // 可见的失败提示：没送达就说没送达，绝不谎称保存成功。
    toast('行为记录未送达（' + _unifiedGachaEventDelivery.lastError + '）', 'err');
    return { ok: false, error: e };
  });
}

// ============ 页面切换 ============
function showPage(id) {
  // 离开页面时清理抽卡动画残留（P0-3 修复）
  if (id !== 'gacha') {
    // M02-S03-G01-W04：离开抽卡页即结束本链（清空已换掉的卡、
    // 开关 A 回到默认关闭；开关 B 本就是每次表单默认不勾选）。
    if (typeof resetReplaceChain === 'function') resetReplaceChain();
    // M02-S03-G02-W03：离开抽卡页 → 结束本轮行为事件 session。
    if (typeof endUnifiedGachaSession === 'function') endUnifiedGachaSession();
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
    // AR03-G08：内嵌计时的句柄归 ESM timer owner 所有，离开抽卡页
    // 由 owner 停止（app.js 不再持有内嵌计时句柄副本）。
    if (_timerOwner) {
      _timerOwner.stopInlineTimer();
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

// ============ 卡类型（M02-S01-G02-W03）============
// 卡类型（tasks.task_type）与「类别」（tasks.category）**正交**：
//   category = 内容维度 —— 这张卡是关于什么的（学习／锻炼／工作／生活／其他）
//   task_type = 卡类型维度 —— 这张卡是哪一类的卡（标准／自由／微型／目标）
// 两者互不覆盖、互不猜测、互不改写。
//
// 归一规则（**纯展示侧**）：只有严格的四个小写正式值被保留，
// 其余一切（历史值 normal/other/daily/...、NULL、空串、非字符串、
// 未知未来值）**一律** 归一为 'standard'。
// 归一只影响「怎么解释它」，**绝不** 改写用户旧数据。
var CARD_TYPE_LABELS = { standard: '标准卡', free: '自由卡', micro: '微型卡', goal: '目标卡' };
var CARD_TYPE_VALUES = ['standard', 'free', 'micro', 'goal'];

// 归一：只有**严格小写**的四个正式值被保留；其余一切
// （历史值 normal/other/daily/…、NULL、空串、非字符串、未知未来值、
//  大小写变体如 'FREE'、以及 '__proto__' 之类的原型链污染串）
// **一律**归一为 'standard'。
//
// 用 Object.prototype.hasOwnProperty.call 而不是 `in`，是为了让
// '__proto__' / 'constructor' / 'toString' 这类原型链上的键
// **不会**被当成合法卡类型。
function normalizeCardType(value) {
  if (typeof value !== 'string') return 'standard';
  // Preserve the exact public card-type vocabulary; padded values are not official types.
  for (var i = 0; i < CARD_TYPE_VALUES.length; i++) {
    if (value === CARD_TYPE_VALUES[i]) return value;
  }
  return 'standard';
}

// 标签映射：结果永远来自上面那张**静态**表，绝不来自用户输入，
// 因此不可能携带 HTML 注入载荷（调用方仍应 escapeHtml 以策万全）。
function cardTypeLabel(value) {
  var v = normalizeCardType(value);
  return Object.prototype.hasOwnProperty.call(CARD_TYPE_LABELS, v)
    ? CARD_TYPE_LABELS[v]
    : '标准卡';
}

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
  // 独立的卡类型角标（与上面的内容类别角标并存，互不替代）。
  var cardType = cardTypeLabel(task.task_type);
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
    '<span class="task-card-corner" title="卡类型" style="color:var(--gold)">' + escapeHtml(cardType) + '</span>' +
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
// M02-S03-G01-W04：连续换卡链。
//   replacedTaskIds    —— 本链 **已成功换掉** 的 task id（去重数组）。
//   allowRepeatReplaced —— 开关 A 的状态（新链默认关闭，链内保持用户选择）。
// 链的结束点是 开始/接受卡片、跳过/拒绝、重新抽卡、离开抽卡页（showPage）。
// hide_today（开关 B）只作用于本次被换掉的卡，每次打开表单默认不勾选，
// 因此 **不** 存进 gachaState，而是每次从表单读取。
var gachaState = { energy: 'medium', pool: 'fragment', canReplace: true, replacedTaskId: null, replacedTaskIds: [], allowRepeatReplaced: false, feedbackMood: 3, currentTaskId: null, selectedTag: '' };
var isDrawing = false;

// 结束本链：清空已换掉的卡并恢复开关 A 的默认（关闭）状态。
function resetReplaceChain() {
  if (typeof gachaState !== 'object' || !gachaState) return;
  gachaState.replacedTaskIds = [];
  gachaState.allowRepeatReplaced = false;
  gachaState.replacedTaskId = null;
}
window.resetReplaceChain = resetReplaceChain;

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
// AR03-G08：计时状态与计时生命周期的 **唯一** 所有者是 ESM timer owner
// （static/modules/timer/index.js）。本节只保留最薄 classic facade：
//   - app.js **不** 持有任何会话 / 暂停 / interval 副本；
//   - app.js **不** 直连计时接口（active/start/pause/resume/complete
//     全部集中在 owner 内，method 与 body 字段逐字保持不变）；
//   - app.js 只负责流程编排（toast、任务列表刷新、自由卡反馈分流）。
//
// 单一共享的 owner promise：并发调用与每秒 tick 不会重复加载模块；
// 加载失败时清空 promise，允许后续重试。
var _timerOwner = null;
var _timerOwnerPromise = null;

function _getTimerOwner() {
  if (_timerOwner) return Promise.resolve(_timerOwner);
  if (!_timerOwnerPromise) {
    // 动态 import 放在 Promise 链里：即便运行环境完全不支持 ESM 动态导入，
    // 失败也只是 **一个被拒绝的 promise**（绝不抛出到调用栈上、绝不中断
    // app.js 的启动流程），且下一次调用可以重试。
    _timerOwnerPromise = Promise.resolve()
      .then(function () {
        return import('/static/modules/timer/index.js');
      })
      .then(function (mod) {
        _timerOwner = mod.createTimerOwner({
          api: api,
          taskNameById: taskNameById,
          formatElapsed: formatElapsed
        });
        return _timerOwner;
      })
      .catch(function (err) {
        // 允许重试：下一次调用会重新 import。
        _timerOwnerPromise = null;
        throw err;
      });
  }
  return _timerOwnerPromise;
}

// 同步读取 owner 快照（只读）。owner 尚未就绪时返回空快照 —— 此时不可能
// 存在任何进行中的计时（计时只能由 owner 启动）。
function _timerSnapshot() {
  if (!_timerOwner) return { session: null, paused: false, pausedElapsedMs: 0 };
  return _timerOwner.getSnapshot();
}

// 是否存在"正在运行的内嵌计时"（用于多抽 / 激活卡的互斥判断）。
function _timerRunning() {
  if (!_timerOwner) return false;
  var snap = _timerOwner.getSnapshot();
  return !!(snap.session && _timerOwner.hasInlineTimer());
}

// 两处计时 UI 同步刷新（任务页只有在其可见时才需要重绘）。
function _refreshTimerViews() {
  if (!_timerOwner) return;
  _timerOwner.updateDock();
  var page = document.getElementById('page-tasks');
  if (page && page.classList.contains('active')) {
    _timerOwner.updatePanel();
  }
}

function initTimerDock() {
  // Dock 每秒刷新（句柄归 owner 所有）。
  _getTimerOwner().then(function (owner) {
    owner.startDockTick();
  }).catch(function (e) {
    console.error('[timer] initTimerDock', e);
  });
  // 读取活动计时（刷新后从服务端恢复唯一 session）。
  loadTimerDockActive();
}

async function loadTimerDockActive() {
  try {
    var owner = await _getTimerOwner();
    await owner.loadActive();
  } catch (e) {
    // 读取失败 → 视为无活动计时（与迁移前语义一致），并清空 owner，
    // 绝不让 Dock 与任务页各自保留一份副本。
    if (_timerOwner) _timerOwner.clear();
  }
  _refreshTimerViews();
}

// AR03-G08：Dock / 任务页计时 DOM 呈现已迁至
// static/modules/timer/presentation.js（真实生产 ESM owner，导出
// updateTimerDockDisplay / updateTimerDisplay），并由 ESM timer owner
// （static/modules/timer/index.js）调用。
//
// app.js 这里只保留 **最薄 classic facade**：
//   - 状态一律来自 owner 快照（getter 注入直接读 owner，不持有镜像）；
//   - 暂停 / 恢复一律经 owner 的 pauseSession / resumeSession，
//     失败时 owner 不改状态，facade 只提示错误。
async function updateTimerDockDisplay() {
  try {
    var owner = await _getTimerOwner();
    owner.updateDock();
  } catch (e) {
    console.error('[timer] updateTimerDockDisplay', e);
  }
}

async function toggleTimerDockPause() {
  try {
    var owner = await _getTimerOwner();
    var snap = owner.getSnapshot();
    if (!snap.session) return;
    if (snap.paused) {
      // P3-Bug-B: 调用后端 API 恢复（持久化）。失败 → 状态不变。
      await owner.resumeSession();
    } else {
      // P3-Bug-B: 调用后端 API 暂停（持久化）。失败 → 状态不变。
      await owner.pauseSession();
    }
  } catch (e) {
    var msg = e && e.message ? e.message : '';
    toast(msg || (_timerSnapshot().paused ? '恢复失败' : '暂停失败'), 'err');
    return;
  }
  _refreshTimerViews();
}

document.getElementById('timerDockPauseBtn').addEventListener('click', toggleTimerDockPause);
document.getElementById('timerDockStopBtn').addEventListener('click', function () {
  // AR03-G08：唯一活动 session 来自 ESM timer owner 快照。
  var snap = _timerSnapshot();
  if (!snap.session) return;
  stopTimerFromDock(snap.session.id);
});

// M02-S02-G03：识别 Dock 里正在计时的 session 是否属于
// **当前正在执行的正式自由卡**（最小、可靠；不发明新的卡型判定规则）。
//
// 判定顺序：
//   1. session 必须带合法的 task_id；
//   2. 该 task_id 对应的卡必须能被既有缓存找到（findDrawnTask：
//      _currentDrawnTask → multiDrawResults → allTasks）且是正式自由卡
//      （isFreeCardTask → normalizeCardType，沿用既有卡型词表）；
//   3. 屏幕上的卡片元素（.task-card.drawn-card[data-task-id=...]）自带
//      data-card-type="free" 时同样算自由卡（缓存尚未加载时的兜底）。
//
// 识别不出来 → 一律走既有 Dock 提前结束路径（语义逐字不变）。
function resolveDockFreeCardTaskId(session) {
  if (!session) return null;
  var numericId = parseInt(session.task_id, 10);
  if (!isFinite(numericId) || numericId <= 0) return null;
  var task = null;
  try { task = findDrawnTask(numericId); } catch (e) { task = null; }
  var freeByTask = !!(task && isFreeCardTask(task));
  var freeByCard = false;
  try {
    var card = document.querySelector('.task-card.drawn-card[data-task-id="' + numericId + '"]');
    freeByCard = !!(card && card.getAttribute && card.getAttribute('data-card-type') === 'free');
  } catch (e) { freeByCard = false; }
  if (!freeByTask && !freeByCard) return null;
  return numericId;
}

// M02-S02-G03：从 Dock 停止按钮打开 **既有** 的自由卡结束反馈表单
// （openFreeCardEndForm → submitFreeCardEnd，绝不另建表单 / 状态 / API）。
//
// 硬约束：
//   - **绝不** 先弹旧的"提前结束"确认、**绝不** 直接调用计时完成接口、
//     **绝不** 清空活动 session：计时停止与事件记录完全交给
//     submitFreeCardEnd 现有流程；
//   - 找不到这张卡的表单 → **fail closed**：保留计时与 Dock 状态并明确
//     提示用户，绝不静默退回旧的"直接中断"路径。
function openFreeCardEndFormFromDock(taskId) {
  var numericId = parseInt(taskId, 10);
  var card = null;
  var rightPanel = null;
  try {
    card = document.querySelector('.task-card.drawn-card[data-task-id="' + numericId + '"]');
    rightPanel = card ? card.querySelector('.drawn-card-right-panel') : null;
  } catch (e) { card = null; rightPanel = null; }
  if (!card || !rightPanel) {
    // Fail closed：绝不静默退回旧的"直接中断"路径（那会绕过 G03 反馈）。
    // 保留计时与 Dock 状态，并明确提示用户去哪里结束。
    // （刻意 **不** 切页：计时 Dock 就在统一抽卡页上，且切页会触发
    //   updateTimerDock() → loadTimerDockActive() 的异步重载，
    //   在网络异常时可能把 Dock 状态清空。）
    toast('找不到这张自由卡的结束反馈表单，计时仍在继续（未被中断）；请在抽卡页找到这张卡后再结束', 'err');
    return;
  }
  openFreeCardEndForm(numericId);
}

async function stopTimerFromDock(sessionId) {
  // M02-S02-G03：Dock 停止按钮属于 **当前正式自由卡** 时，
  // 必须先走自由卡结束反馈表单（是否顺利 / 是否中断 / 实际活动 / 原因），
  // 绝不直接中断计时、绝不绕过 G03 反馈。
  var owner = null;
  try {
    owner = await _getTimerOwner();
  } catch (e) {
    toast('计时模块加载失败，计时状态未改变', 'err');
    return;
  }
  var snap = owner.getSnapshot();
  var freeCardTaskId = resolveDockFreeCardTaskId(snap.session);
  if (freeCardTaskId !== null) {
    openFreeCardEndFormFromDock(freeCardTaskId);
    return;
  }
  if (!confirm('确定提前结束此任务？')) return;
  var session = snap.session;
  try {
    if (session && session.id) {
      // P3-Bug-A：实际分钟数由 owner 统一计算（考虑历史暂停时间，下限 1）。
      var actualMin = owner.getActualMinutes();
      // P0-2 (bug 3.4) 修复：提前结束 → result=abandoned，不标记任务为完成
      // 任务保持"可用/未完成"状态，可重新计时；仅 timer_sessions.result='abandoned' 留痕
      // 失败 → owner 保留活动 session（可重试），绝不谎报"已中断"。
      await owner.completeSession({
        sessionId: session.id,
        actualMinutes: actualMin,
        result: 'abandoned',
        reason: 'early_finish'
      });
    } else {
      owner.clear();
    }
    owner.stopInlineTimer();
    _refreshTimerViews();
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

function getGachaAvailableMinutes() {
  var input = document.getElementById('gachaTimeInput');
  var raw = input ? input.value.trim() : '';
  var minutes = Number(raw);
  if (!/^[0-9]+$/.test(raw) || !Number.isInteger(minutes) || minutes < 1 || minutes > 480) {
    throw new Error('可用时间请输入 1–480 之间的整数分钟');
  }
  return minutes;
}

async function drawGacha() {
  if (isDrawing) return;
  var btn = document.getElementById('gachaBtn');
  if (btn) btn.disabled = true;
  isDrawing = true;
  // 发起新抽卡 → 本链结束。
  resetReplaceChain();
  // M02-S03-G02-W03：一次新的抽卡 → 开启新的行为事件 session。
  beginUnifiedGachaSession();
  var actionId = newUnifiedGachaActionId('draw');

  var result = document.getElementById('gachaResult');
  var deck = document.getElementById('gachaDeck');
  var flyLayer = document.getElementById('cardFlyLayer');
  var multiResultArea = document.getElementById('gachaMultiResult');
  // 清掉上一次的飞行卡片残留，防止快速二次抽卡时动画叠层（P0-3）
  if (flyLayer) flyLayer.innerHTML = '';
  // 清掉抽卡结果区，避免新旧卡牌同时显示
  if (result) result.innerHTML = '';
  // 切换到单抽时隐藏多抽结果（但不清理计时器或已选任务）
  if (multiResultArea) multiResultArea.classList.add('hidden');
  multiDrawResults = [];
  if (deck) {
    deck.classList.remove('is-drawing');
    deck.classList.remove('is-revealing');
    deck.classList.add('is-drawing');
  }

  try {
    var availableMinutes = getGachaAvailableMinutes();
    var r = await api('/api/gacha/draw', {
      method: 'POST',
      body: JSON.stringify({
        pool: gachaState.pool,
        energy: gachaState.energy,
        available_time: availableMinutes,
        preferred_tag: gachaState.selectedTag || null
      })
    });
    if (r.task) {
      if (r.pool) gachaState.pool = r.pool;
      gachaState.canReplace = r.can_replace !== false;
      gachaState.currentTaskId = r.task.id;
      // M1.3A: cache the active drawn task so startTask() can find it
      // even when allTasks has not yet been populated by /api/tasks.
      _currentDrawnTask = r.task;
      // M02-S03-G02-W03：服务端返回真实 task 后才记录 card_drawn。
      var drawnTaskId = unifiedGachaTaskId(r.task.id);
      var drawContext = {
        source: 'single_draw',
        pool: r.pool || gachaState.pool,
        energy: gachaState.energy,
        available_time: availableMinutes,
        preferred_tag: gachaState.selectedTag || null
      };
      sendUnifiedGachaEvent('card_drawn', drawnTaskId, drawContext,
        unifiedGachaEventId(actionId, 'card_drawn', drawnTaskId));
      var stage = renderDrawnCard(r.task, 0);
      result.appendChild(stage);
      // 卡片真正进入结果区后才记录 card_shown。
      reportUnifiedGachaCardShown(drawnTaskId,
        { source: 'single_draw', surface: 'result', pool: drawContext.pool }, actionId);
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

// ============ 多抽连抽功能 ============
// 存储多抽结果（用于点击激活）
var multiDrawResults = [];

// 多抽按钮事件绑定
document.getElementById('gachaMultiBtn').addEventListener('click', drawGachaMulti);

async function drawGachaMulti() {
  // 检查共享锁
  if (isDrawing) return;

  // 检查计时器状态
  if (window._inlineTimerHandle && timerDockSession) {
    var taskId = timerDockSession.task_id;
    var activeCard = document.querySelector('.task-card.drawn-card[data-task-id="' + taskId + '"]');
    if (activeCard) {
      toast('请先完成当前计时任务', 'inf');
      return;
    }
  }

  var multiBtn = document.getElementById('gachaMultiBtn');
  var singleBtn = document.getElementById('gachaBtn');
  var countSelect = document.getElementById('gachaMultiCount');

  if (multiBtn) multiBtn.disabled = true;
  if (singleBtn) singleBtn.disabled = true;

  isDrawing = true;

  var result = document.getElementById('gachaResult');
  var deck = document.getElementById('gachaDeck');

  // 清空单抽结果区（发起新连抽 → 本链结束）
  resetReplaceChain();
  if (result) result.innerHTML = '';
  // M02-S03-G02-W03：一次新的连抽 → 开启新的行为事件 session。
  beginUnifiedGachaSession();
  var actionId = newUnifiedGachaActionId('multi');

  try {
    // 获取连抽数量
    var count = parseInt(countSelect ? countSelect.value : '3', 10);
    count = Math.max(2, Math.min(5, count));
    var availableMinutes = getGachaAvailableMinutes();

    // 调用多抽API
    var r = await api('/api/gacha/multi-draw', {
      method: 'POST',
      body: JSON.stringify({
        available_time: availableMinutes,
        count: count,
        energy: gachaState.energy,
        preferred_tag: gachaState.selectedTag || null
      })
    });

    if (r.tasks && r.tasks.length > 0) {
      multiDrawResults = r.tasks;
      var renderedCount = renderMultiResults(r);
      // M02-S03-G02-W03：每张 **有效** 卡（真实 task id）各记一次 card_drawn。
      r.tasks.forEach(function (task) {
        var tid = unifiedGachaTaskId(task && task.id);
        if (tid === null) return;  // 没有真实 task id → 不记录
        sendUnifiedGachaEvent('card_drawn', tid, {
          source: 'multi_draw',
          pool: r.pool || gachaState.pool,
          energy: gachaState.energy,
          available_time: availableMinutes,
          preferred_tag: gachaState.selectedTag || null,
          multi_count: count
        }, unifiedGachaEventId(actionId, 'card_drawn', tid));
      });
      // 结果列表 **确实渲染** 出来 → 这些卡已进入结果区 → card_shown。
      // 没渲染出来（容器缺失）→ 绝不记 card_shown。
      if (renderedCount > 0) {
        r.tasks.forEach(function (task) {
          var tid = unifiedGachaTaskId(task && task.id);
          if (tid === null) return;
          reportUnifiedGachaCardShown(tid, {
            source: 'multi_draw',
            surface: 'multi_list',
            pool: r.pool || gachaState.pool
          }, actionId);
        });
      }
      toast('抽到 ' + r.tasks.length + ' 张卡牌', 'suc');
    } else {
      // 空池或404
      var multiResultArea = document.getElementById('gachaMultiResult');
      if (multiResultArea) {
        multiResultArea.classList.add('hidden');
      }
      multiDrawResults = [];
      toast('没有合适的任务', 'inf');
    }
  } catch (e) {
    toast(e.message || '连抽失败', 'err');
    // 清空多抽结果
    var multiResultArea = document.getElementById('gachaMultiResult');
    if (multiResultArea) {
      multiResultArea.classList.add('hidden');
    }
    multiDrawResults = [];
  } finally {
    if (multiBtn) multiBtn.disabled = false;
    if (singleBtn) singleBtn.disabled = false;
    isDrawing = false;
    refreshGachaStats();
  }
}

function renderMultiResults(response) {
  var container = document.getElementById('gachaMultiResult');
  var summary = document.getElementById('gachaMultiSummary');
  var list = document.getElementById('gachaMultiList');

  if (!container || !summary || !list) return;

  var tasks = response.tasks || [];
  var totalMinutes = response.total_minutes || 0;
  var remainingMinutes = response.remaining_minutes || 0;

  // Helper: build one summary chip.
  // iconClass is a STATIC trusted class name (no interpolation).
  function appendSummaryChip(iconClass, valueText, suffixText) {
    var span = document.createElement('span');
    var icon = document.createElement('i');
    icon.className = iconClass;
    span.appendChild(icon);
    span.appendChild(document.createTextNode(' ' + suffixText + ' '));
    var strong = document.createElement('strong');
    strong.textContent = String(valueText);
    span.appendChild(strong);
    // Append the static unit suffix without interpolation (e.g. " 分钟").
    if (iconClass === 'fa-solid fa-clock' || iconClass === 'fa-solid fa-hourglass-half') {
      span.appendChild(document.createTextNode(' 分钟'));
    } else if (iconClass === 'fa-solid fa-layer-group') {
      span.appendChild(document.createTextNode(' 张'));
    }
    summary.appendChild(span);
  }
  appendSummaryChip('fa-solid fa-layer-group', tasks.length, '抽到');
  appendSummaryChip('fa-solid fa-clock', totalMinutes, '共');
  appendSummaryChip('fa-solid fa-hourglass-half', remainingMinutes, '剩余');

  // 渲染卡牌列表 - 全部使用 createElement + textContent，无 innerHTML 拼接
  list.textContent = '';

  tasks.forEach(function(task, idx) {
    // 使用原生 <button type="button">：天然支持键盘 Enter/Space，无需 tabindex/handler hack
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'gacha-multi-item';
    btn.setAttribute('data-task-id', task.id);
    btn.setAttribute('data-idx', idx);
    btn.setAttribute('aria-pressed', 'false');
    // 可访问名称：任务标题（DOM 文本 → AT 名称）
    var titleDiv = document.createElement('span');
    titleDiv.className = 'gacha-multi-item-title';
    titleDiv.textContent = task.name || '未知任务';
    btn.appendChild(titleDiv);

    // 安全渲染元信息
    var metaDiv = document.createElement('span');
    metaDiv.className = 'gacha-multi-item-meta';
    var timeSpan = document.createElement('span');
    timeSpan.textContent = (task.estimated_time != null ? String(task.estimated_time) : '?') + '分';
    metaDiv.appendChild(timeSpan);

    // 安全渲染标签
    var tags = Array.isArray(task.tags) ? task.tags : [];
    if (tags.length > 0) {
      var tagSpan = document.createElement('span');
      tagSpan.className = 'gacha-multi-item-tag';
      tagSpan.textContent = tags[0];
      metaDiv.appendChild(tagSpan);
    }

    btn.appendChild(metaDiv);

    // 点击/键盘激活单张卡牌 - 原生 button 自带 Enter/Space
    btn.addEventListener('click', (function(t, i) {
      return function() {
        activateMultiCard(t, i);
      };
    })(task, idx));

    list.appendChild(btn);
  });

  container.classList.remove('hidden');
  // M02-S03-G02-W03：返回"确实渲染进结果区"的张数，供调用方决定是否记 card_shown。
  return tasks.length;
}

function activateMultiCard(task, idx) {
  // 检查是否有计时器正在运行
  // AR03-G08：唯一 session 来自 ESM timer owner。
  var _snap = _timerSnapshot();
  if (_snap.session && _timerRunning()) {
    var activeTaskId = _snap.session.task_id;
    if (activeTaskId && activeTaskId !== task.id) {
      var activeCard = document.querySelector('.task-card.drawn-card[data-task-id="' + activeTaskId + '"]');
      if (activeCard) {
        toast('请先完成当前计时任务', 'inf');
        return;
      }
    }
  }

  // 更新选中状态UI + aria-pressed 同步
  var items = document.querySelectorAll('.gacha-multi-item');
  items.forEach(function(item) {
    item.classList.remove('activated');
    if (item.setAttribute) {
      item.setAttribute('aria-pressed', 'false');
    }
  });
  var selectedItem = document.querySelector('.gacha-multi-item[data-task-id="' + task.id + '"]');
  if (selectedItem) {
    selectedItem.classList.add('activated');
    if (selectedItem.setAttribute) {
      selectedItem.setAttribute('aria-pressed', 'true');
    }
    // M1.2 a11y: keep keyboard focus on the selected button so the
    // keyboard user does not lose their position after activation.
    selectedItem.focus({ preventScroll: true });
  }

  // 清除单抽结果区
  var result = document.getElementById('gachaResult');
  if (result) result.innerHTML = '';

  // 激活卡牌 - 使用现有renderDrawnCard
  gachaState.currentTaskId = task.id;
  gachaState.canReplace = false; // 多抽激活的卡牌不允许换卡

  // M1.3A: cache the active drawn task so startTask() finds it even
  // when the loadTasks() /api/tasks request hasn't completed yet.
  _currentDrawnTask = task;

  var stage = renderDrawnCard(task, 0);
  if (result && stage) {
    result.appendChild(stage);
    // M02-S03-G02-W03：激活的卡真正进入结果区 → card_shown。
    // 复用当前 session（不新开 session：这是同一轮连抽的延续）。
    reportUnifiedGachaCardShown(task.id, {
      source: 'multi_draw',
      surface: 'multi_activated',
      pool: gachaState.pool
    });
  }
}

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
  // M1.2 hardening: every interpolated field must be escapeHtml'd before
  // landing in innerHTML. task.id must be coerced to a safe integer
  // literal so a payload of '1);alert(1)//' cannot break out of the
  // onclick=... attribute.
  var safeId = parseInt(task.id, 10);
  if (!isFinite(safeId)) safeId = 0;
  var safeNotePath = task.linked_note_path
    ? escapeHtml(
        task.linked_note_path
          .replace(/\\/g, '\\\\')
          .replace(/'/g, "\\'")
          .replace(/"/g, '&quot;')
      )
    : '';
  var noteBtn = task.linked_note_path
    ? '<button class="btn" onclick="openNoteFromCard(\'' + safeNotePath + '\')" style="margin-bottom:6px;width:100%;background:rgba(88,166,255,0.15);border-color:rgba(88,166,255,0.4);color:#7ab8ff"><i class="fa-brands fa-markdown"></i> 在Obsidian中打开</button>'
    : '';
  // M02-S02-G01-W08：自由卡的主操作是"接受自由卡"（点击后由 startTask 委派到
  // 同一张卡片内的接受表单），普通/微型/目标卡的主操作与既有计时器流程保持原样。
  // 按钮统一走 startTask(<safeId>)：自由卡在 startTask 内部**委派**到
  // openFreeCardAcceptForm，**绝不** 走行内估时的普通启动路径。
  var isFreeCard = normalizeCardType(task.task_type) === 'free';
  var freeMinutes = isFreeCard ? resolveFreeCardMinutes(task) : null;
  var primaryActionLabel = isFreeCard ? '接受自由卡' : '开始任务';
  var primaryActionIcon = isFreeCard ? 'fa-solid fa-check' : 'fa-solid fa-play';
  var actions =
    '<button class="btn pri" onclick="startTask(' + safeId + ')" style="margin-bottom:6px;width:100%"><i class="' + primaryActionIcon + '"></i> ' + primaryActionLabel + '</button>' +
    noteBtn +
    '<button class="btn" onclick="handleSkip(' + safeId + ')" style="margin-bottom:6px;width:100%"><i class="fa-solid fa-forward"></i> 跳过</button>' +
    '<button class="btn danger" onclick="handleRefuse(' + safeId + ')" style="margin-bottom:6px;width:100%"><i class="fa-solid fa-xmark"></i> 拒绝</button>' +
    (gachaState.canReplace ? '<button class="btn" onclick="showReplaceReason(' + safeId + ')" style="width:100%"><i class="fa-solid fa-shuffle"></i> 换一张</button>' : '');
  // 记住该卡的操作栏 HTML：取消接受时用它 **原样** 恢复卡片操作。
  _drawnCardActionsCache[safeId] = actions;

  var wrap = document.createElement('div');
  wrap.className = 'drawn-card-stage';
  var card = document.createElement('div');
  card.className = 'task-card card drawn-card ' + theme + (urgent ? ' urgent' : '') + (isOneOff ? ' is-oneoff' : '');
  card.setAttribute('data-task-id', task.id);
  // data-card-type 存的是**归一后**的合法值（standard/free/micro/goal），
  // 绝不是用户/DB 里的原始字符串，因此不可能夹带 HTML。
  card.setAttribute('data-card-type', normalizeCardType(task.task_type));
  card.style.animationDelay = (idx * 0.15) + 's';

  // 横向布局：左侧任务信息，右侧操作按钮
  // corner = **内容类别**角标（原语义不变）；cardType = **独立的卡类型**角标
  // （自由卡／微型卡／目标卡／标准卡），两者同时出现、互不替代。
  var corner = { study: '学习', exercise: '运动', work: '工作', life: '生活', other: '其他' }[task.category] || '任务';
  var cardType = cardTypeLabel(task.task_type);
  var repeatLbl = { none: '单次', daily: '每日', weekly: '每周' }[task.repeat_type] || '单次';
  var safeName = escapeHtml(task.name);
  var safeDesc = escapeHtml((task.description || '').substring(0, 150));
  var safeTagsHtml = (task.tags || []).map(function(x) { return '<span class="badge bg-gold">' + escapeHtml(x) + '</span>'; }).join('');

  var leftHtml =
    '<div class="task-card-header" style="width:100%;border-bottom:1px solid rgba(255,255,255,0.06);padding:8px 10px;background:linear-gradient(180deg,rgba(0,0,0,0.18),transparent)">' +
    '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">' +
    '<span style="font-size:.68rem;padding:2px 8px;border-radius:8px;background:rgba(0,0,0,0.28);border:1px solid var(--card-border);color:var(--card-accent);font-family:var(--font-heading)" title="活动类别">' + corner + '</span>' +
    '<span style="font-size:.68rem;padding:2px 8px;border-radius:8px;background:rgba(0,0,0,0.28);border:1px solid var(--card-border);color:var(--gold);font-family:var(--font-heading)" title="卡类型">' + escapeHtml(cardType) + '</span>' +
    '<span style="font-size:.68rem;padding:2px 8px;border-radius:8px;background:rgba(0,0,0,0.28);border:1px solid var(--card-border);color:var(--card-accent);font-family:var(--font-heading)">P' + escapeHtml(String(task.priority == null ? '?' : task.priority)) + '</span>' +
    '</div></div>' +
    '<div style="flex:1;padding:8px 10px;display:flex;flex-direction:column;justify-content:center;min-height:0">' +
    '<div style="font-family:var(--font-heading);font-size:1.05rem;margin-bottom:6px;font-weight:600">' + safeName + '</div>' +
    '<div style="font-size:.82rem;color:var(--text-secondary);margin-bottom:6px;line-height:1.4">' + safeDesc + '</div>' +
    // 自由卡提示：本次发行的合法时长（25/55）来自 effective_minutes；
    // 没有可派发时长时 **绝不** 显示误导性的行内估时。
    // （25/55 自动时长与"接受"流程已上线；"帮我选"与结束时的顺利/中断
    //   反馈仍属后续工单，因此这里仍如实标注其尚未上线。）
    (isFreeCard
      ? (freeMinutes === null
        ? '<div style="font-size:.72rem;color:var(--text-muted);margin-bottom:6px;line-height:1.4">自由卡：本次没有可用的已批准时长（25/55 分钟），暂不能开始。</div>'
        : '<div style="font-size:.72rem;color:var(--text-muted);margin-bottom:6px;line-height:1.4">自由卡：本次时长 ' + freeMinutes + ' 分钟（来自策略本次发行）；结束时的顺利/中断反馈即将上线。</div>')
      : '') +
    '<div style="display:flex;gap:6px;flex-wrap:wrap">' +
    '<span style="font-size:.75rem;color:var(--text-muted);display:flex;align-items:center;gap:3px"><i class="fa-solid fa-clock" style="color:var(--gold);font-size:.7rem"></i>' +
      (isFreeCard
        ? (freeMinutes === null ? '时长待定' : freeMinutes + '分')
        : escapeHtml(String(task.estimated_time == null ? '?' : task.estimated_time)) + '分') +
    '</span>' +
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

// ============ 自由卡接受（M02-S02-G01-W08）============
// 合同要点：
// - 自由卡时长 **只** 来自当前卡对象的 ``effective_minutes``；且要求
//   ``free_card_dispatchable === true`` 且时长是严格整数 25 / 55。
//   缺字段 / false / 非法值 → **fail closed**（绝不回落 ``estimated_time``，
//   也绝不硬编码 25 / 55）。
// - 活动内容必填（最多 200 字）；理由默认值精确为
//   "没有什么理由，我就是想。"，空白理由按同一默认值规范化。
// - 活动 / 理由一律通过 DOM ``value`` 读取，用户输入 **绝不** 拼进
//   inline JavaScript 或未转义 HTML。
// - 开始后复用 **现有** 计时启动接口（planned_minutes 严格等于
//   effective_minutes）与现有唯一计时 session / 内嵌计时 / 暂停 / 结束流程；
//   **绝不** 建立第二套计时器。
var FREE_CARD_MINUTES_OPTIONS = [25, 55];
var FREE_CARD_DEFAULT_REASON = '没有什么理由，我就是想。';
var FREE_CARD_MAX_ACTIVITY_LENGTH = 200;
// 自由卡接受表单的 DOM id 前缀（同一张卡片内展开，不新建页面）。
var FREE_CARD_FORM_ID_PREFIX = 'freeCardAcceptForm_';
// 正在提交的自由卡接受（幂等保护，避免重复启动计时）。
var _pendingFreeCardAcceptId = null;
// 每张已渲染卡片的操作栏 HTML（取消接受时原样恢复）。
var _drawnCardActionsCache = {};

// 从卡对象解析本次发行的合法自由卡时长；非法 / 缺失 → null（fail closed）。
function resolveFreeCardMinutes(task) {
  if (!task || typeof task !== 'object') return null;
  if (task.free_card_dispatchable !== true) return null;
  var raw = task.effective_minutes;
  if (typeof raw !== 'number' || !isFinite(raw)) return null;
  if (Math.floor(raw) !== raw) return null;
  if (FREE_CARD_MINUTES_OPTIONS.indexOf(raw) < 0) return null;
  return raw;
}

// 找出当前卡对象（与 startTask 使用同一套安全缓存）。
function findDrawnTask(taskId) {
  var numericId = (typeof taskId === 'number') ? taskId : parseInt(taskId, 10);
  if (!isFinite(numericId) || numericId <= 0) return null;
  var task = null;
  if (_currentDrawnTask && Number(_currentDrawnTask.id) === numericId) {
    task = _currentDrawnTask;
  } else if (Array.isArray(multiDrawResults) && multiDrawResults.length) {
    for (var i = 0; i < multiDrawResults.length; i += 1) {
      var m = multiDrawResults[i];
      if (m && Number(m.id) === numericId) { task = m; break; }
    }
  }
  if (!task && Array.isArray(allTasks)) {
    task = allTasks.find(function (x) { return x.id === numericId; }) || null;
  }
  return task;
}

// 校验 / 规范化用户输入的活动与理由（与后端规则一致的前端预检）。
function normalizeFreeCardInputs(activity, reason) {
  var cleanActivity = (typeof activity === 'string') ? activity.trim() : '';
  if (!cleanActivity) {
    return { ok: false, error: '请先填写接下来要做什么', activity: '', reason: '' };
  }
  if (cleanActivity.length > FREE_CARD_MAX_ACTIVITY_LENGTH) {
    return { ok: false, error: '活动内容最多 200 字', activity: cleanActivity, reason: '' };
  }
  if (/[\x00-\x1f\x7f]/.test(cleanActivity)) {
    return { ok: false, error: '活动内容包含非法字符', activity: cleanActivity, reason: '' };
  }
  var cleanReason = (typeof reason === 'string') ? reason.trim() : '';
  if (!cleanReason) cleanReason = FREE_CARD_DEFAULT_REASON;
  if (cleanReason.length > FREE_CARD_MAX_ACTIVITY_LENGTH) {
    return { ok: false, error: '理由最多 200 字', activity: cleanActivity, reason: '' };
  }
  if (/[\x00-\x1f\x7f]/.test(cleanReason)) {
    return { ok: false, error: '理由包含非法字符', activity: cleanActivity, reason: '' };
  }
  return { ok: true, error: null, activity: cleanActivity, reason: cleanReason };
}

// "帮我选"（M02-S02-G02）：调用现有只读接口
// ``GET /api/gacha/free-card/suggestion``，把返回的 **一条** 建议填进活动
// 输入框。
//
// 硬约束（与产品意图一致）：
// - 只读、**无模型 API**：后端只从同一份已批准策略的候选池里取一条，
//   **绝不** 在前端编造候选；
// - 成功时 **只** 填活动输入框：**不** 自动提交表单、**不** 启动计时、
//   **不** 改理由输入框（用户可继续编辑，然后自行点"开始"）；
// - 失败（422 / 缺少合法 activity / 网络失败）→ **保留** 用户当前输入与
//   理由，给出简短提示，让用户手动填写继续；**绝不** 追加问卷。
async function suggestFreeCardActivity(taskId) {
  var numericId = (typeof taskId === 'number') ? taskId : parseInt(taskId, 10);
  if (!isFinite(numericId) || numericId <= 0) return;

  var formId = FREE_CARD_FORM_ID_PREFIX + numericId;
  var activityEl = document.getElementById(formId + '_activity');

  var data = null;
  try {
    data = await api('/api/gacha/free-card/suggestion', { method: 'GET' });
  } catch (e) {
    // 422 / 网络失败 / 其它错误：保留用户当前输入与理由。
    toast('暂时拿不到建议，可以自己写一个再开始', 'err');
    return;
  }

  var suggestion = data && data.suggestion ? data.suggestion : null;
  var activity = suggestion && typeof suggestion.activity === 'string'
    ? suggestion.activity.trim()
    : '';
  if (!activity) {
    // 响应里没有合法活动 → 绝不编造，保留用户当前输入与理由。
    toast('暂时没有可用的活动建议，可以自己写一个再开始', 'err');
    return;
  }
  if (activity.length > FREE_CARD_MAX_ACTIVITY_LENGTH) {
    toast('建议内容过长，请自己写一个再开始', 'err');
    return;
  }
  if (/[\x00-\x1f\x7f]/.test(activity)) {
    toast('建议内容包含非法字符，请自己写一个再开始', 'err');
    return;
  }

  // 只写活动输入框：理由与计时流程完全不受影响。
  if (activityEl) activityEl.value = activity;
  toast('已填入一条建议，可以直接改成你自己的做法', 'inf');
}

// 在 **同一张卡片** 内渲染自由卡接受表单。
// 活动 / 理由输入框用 **DOM API** 创建（value 通过属性赋值，绝不拼进
// inline JS 或未转义 HTML）；提交时再通过 ``element.value`` 读回。
// ``values`` 可用于失败后 **原样保留** 用户已填内容以便重试。
function openFreeCardAcceptForm(taskId, values) {
  var numericId = (typeof taskId === 'number') ? taskId : parseInt(taskId, 10);
  if (!isFinite(numericId) || numericId <= 0) {
    toast('任务不存在', 'err');
    return;
  }
  var card = document.querySelector('.task-card.drawn-card[data-task-id="' + numericId + '"]');
  if (!card) { toast('请先抽一张卡牌', 'err'); return; }
  var rightPanel = card.querySelector('.drawn-card-right-panel');
  if (!rightPanel) return;

  var task = findDrawnTask(numericId);
  var minutes = task ? resolveFreeCardMinutes(task) : null;
  if (minutes === null) {
    // Fail closed：没有已批准的可派发时长 → 不显示可执行的开始路径。
    rightPanel.innerHTML =
      '<div style="font-size:.78rem;color:var(--text-secondary);margin-bottom:8px">自由卡本次没有可用的已批准时长（25/55 分钟），因此不能开始计时。</div>' +
      '<button class="btn" onclick="cancelFreeCardAcceptForm(' + numericId + ')" style="width:100%"><i class="fa-solid fa-arrow-left"></i> 返回</button>';
    toast('这张自由卡本次没有已批准的可执行时长，无法开始', 'err');
    return;
  }

  var prior = values || null;
  var formId = FREE_CARD_FORM_ID_PREFIX + numericId;
  rightPanel.innerHTML = '';
  var box = document.createElement('div');
  box.className = 'free-card-accept-form';

  var intro = document.createElement('div');
  intro.style.cssText = 'font-size:.76rem;color:var(--text-secondary);margin-bottom:6px';
  intro.textContent = '接受这张自由卡，本次时长 ' + minutes + ' 分钟。';
  box.appendChild(intro);

  var activityLabel = document.createElement('label');
  activityLabel.setAttribute('for', formId + '_activity');
  activityLabel.style.cssText = 'font-size:.72rem;color:var(--text-muted);display:block;margin-bottom:3px';
  activityLabel.textContent = '接下来做什么（必填，最多 200 字）';
  box.appendChild(activityLabel);

  var activityInput = document.createElement('input');
  activityInput.setAttribute('type', 'text');
  activityInput.setAttribute('id', formId + '_activity');
  activityInput.setAttribute('maxlength', String(FREE_CARD_MAX_ACTIVITY_LENGTH));
  activityInput.setAttribute('placeholder', '例如：看 20 分钟纪录片');
  activityInput.style.cssText = 'flex:1;min-width:0;padding:6px;border-radius:8px;border:1px solid var(--card-border);background:rgba(0,0,0,0.25);color:var(--text-primary)';
  if (prior && typeof prior.activity === 'string') activityInput.value = prior.activity;

  // "帮我选"（M02-S02-G02）：一次点击即得 **一个** 具体活动建议。
  // - 只调用现有只读接口 GET /api/gacha/free-card/suggestion（它只从同一份
  //   已批准策略的候选池里取一条）；**无模型 API**、不发行卡、不写库；
  // - 成功时 **只** 填活动输入框；**绝不** 自动提交、**绝不** 启动计时、
  //   **绝不** 改理由输入框（用户可继续编辑后自行点"开始"）。
  var activityRow = document.createElement('div');
  activityRow.style.cssText = 'display:flex;gap:6px;align-items:center;margin-bottom:6px';
  activityRow.appendChild(activityInput);

  var suggestBtn = document.createElement('button');
  suggestBtn.className = 'btn';
  suggestBtn.setAttribute('id', formId + '_suggest');
  suggestBtn.setAttribute('type', 'button');
  suggestBtn.style.cssText = 'flex:0 0 auto;white-space:nowrap;padding:6px 10px';
  suggestBtn.textContent = '帮我选';
  suggestBtn.addEventListener('click', function () {
    suggestFreeCardActivity(numericId);
  });
  activityRow.appendChild(suggestBtn);
  box.appendChild(activityRow);

  var reasonLabel = document.createElement('label');
  reasonLabel.setAttribute('for', formId + '_reason');
  reasonLabel.style.cssText = 'font-size:.72rem;color:var(--text-muted);display:block;margin-bottom:3px';
  reasonLabel.textContent = '理由（可编辑）';
  box.appendChild(reasonLabel);

  var reasonInput = document.createElement('input');
  reasonInput.setAttribute('type', 'text');
  reasonInput.setAttribute('id', formId + '_reason');
  reasonInput.setAttribute('maxlength', String(FREE_CARD_MAX_ACTIVITY_LENGTH));
  reasonInput.style.cssText = 'width:100%;margin-bottom:6px;padding:6px;border-radius:8px;border:1px solid var(--card-border);background:rgba(0,0,0,0.25);color:var(--text-primary)';
  // 默认值精确为产品约定的缺省理由（通过 DOM 属性赋值，不是 HTML 拼接）。
  reasonInput.value = (prior && typeof prior.reason === 'string' && prior.reason)
    ? prior.reason
    : FREE_CARD_DEFAULT_REASON;
  box.appendChild(reasonInput);

  var reminder = document.createElement('div');
  reminder.style.cssText = 'font-size:.7rem;color:var(--text-muted);line-height:1.4;margin-bottom:8px';
  reminder.textContent = '开始后请同时为手机手动设置计时器；网页计时不应替代手机提醒。';
  box.appendChild(reminder);

  var startBtn = document.createElement('button');
  startBtn.className = 'btn pri';
  startBtn.style.cssText = 'width:100%;margin-bottom:6px';
  startBtn.textContent = '开始';
  startBtn.addEventListener('click', function () { submitFreeCardAccept(numericId); });
  box.appendChild(startBtn);

  var cancelBtn = document.createElement('button');
  cancelBtn.className = 'btn';
  cancelBtn.style.cssText = 'width:100%';
  cancelBtn.textContent = '取消';
  cancelBtn.addEventListener('click', function () { cancelFreeCardAcceptForm(numericId); });
  box.appendChild(cancelBtn);

  rightPanel.appendChild(box);

  if (typeof activityInput.focus === 'function') {
    try { activityInput.focus(); } catch (e) { /* ignore */ }
  }
}

// 取消接受 → 恢复卡片操作。
function cancelFreeCardAcceptForm(taskId) {
  var numericId = (typeof taskId === 'number') ? taskId : parseInt(taskId, 10);
  if (!isFinite(numericId) || numericId <= 0) return;
  var card = document.querySelector('.task-card.drawn-card[data-task-id="' + numericId + '"]');
  if (!card) return;
  var rightPanel = card.querySelector('.drawn-card-right-panel');
  if (!rightPanel) return;
  // 原样恢复该卡渲染时的操作栏（保持既有按钮与行为逐字不变）。
  var cached = _drawnCardActionsCache[numericId];
  if (typeof cached === 'string') {
    rightPanel.innerHTML = cached;
  }
}

// 严格规范 timer/start 返回的 session_id。
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

// 提交自由卡接受：启动既有计时器 + 写 accept_task 事件。
async function submitFreeCardAccept(taskId) {
  var numericId = (typeof taskId === 'number') ? taskId : parseInt(taskId, 10);
  if (!isFinite(numericId) || numericId <= 0) {
    toast('任务不存在', 'err');
    return;
  }
  if (_pendingFreeCardAcceptId === numericId) return;
  _pendingFreeCardAcceptId = numericId;

  var task = findDrawnTask(numericId);
  if (!task) {
    _pendingFreeCardAcceptId = null;
    toast('任务不存在', 'err');
    return;
  }
  var minutes = resolveFreeCardMinutes(task);
  if (minutes === null) {
    _pendingFreeCardAcceptId = null;
    toast('这张自由卡本次没有已批准的可执行时长，无法开始', 'err');
    return;
  }

  var formId = FREE_CARD_FORM_ID_PREFIX + numericId;
  var activityEl = document.getElementById(formId + '_activity');
  var reasonEl = document.getElementById(formId + '_reason');
  var activityRaw = activityEl ? activityEl.value : '';
  var reasonRaw = reasonEl ? reasonEl.value : '';

  var normalized = normalizeFreeCardInputs(activityRaw, reasonRaw);
  if (!normalized.ok) {
    _pendingFreeCardAcceptId = null;
    toast(normalized.error, 'err');
    return;
  }

  var card = document.querySelector('.task-card.drawn-card[data-task-id="' + numericId + '"]');
  var rightPanel = card ? card.querySelector('.drawn-card-right-panel') : null;

  // AR03-G08：计时启动统一经 ESM timer owner（唯一计时生命周期所有者）。
  // 自由卡接受路径启用 **严格 session_id 校验**。
  var owner = null;
  try {
    owner = await _getTimerOwner();
  } catch (e) {
    _pendingFreeCardAcceptId = null;
    toast('计时模块加载失败，启动计时失败', 'err');
    return;
  }
  var started = null;
  try {
    started = await owner.startSession({
      taskId: numericId,
      plannedMinutes: minutes,
      taskName: normalized.activity,
      requireValidSessionId: true
    });
  } catch (e) {
    _pendingFreeCardAcceptId = null;
    toast(e.message || '启动计时失败', 'err');
    return;
  }

  // === 严格规范 session_id（M02-S02-G01-W11）=========================
  // timer/start 已经成功返回，但 session_id 缺失 / 非法时：
  //   - 绝不向计时完成接口发送无效 ID；
  //   - 绝不设置活动 session（owner 也绝不设置）；
  //   - 绝不启动内嵌计时器、绝不显示"执行中"状态；
  //   - 绝不声称"已停止"（我们无从确认计时是否真的停了）；
  //   - 显示明确警告，并保留活动 / 理由供用户恢复。
  if (!started || !started.ok) {
    _pendingFreeCardAcceptId = null;
    openFreeCardAcceptForm(numericId, { activity: normalized.activity, reason: normalized.reason });
    toast('无法确认计时已停止，请检查计时状态/必要时手动处理。你的活动与理由已保留。', 'err');
    return;
  }
  var sessionId = started.session ? started.session.id : null;

  // 计时已启动 → 复用既有内嵌计时流程（owner 持有唯一 session）。
  _refreshTimerViews();
  startInlineTimer(numericId);

  // 记住本次接受时填写的活动 → 结束反馈的 **可编辑预填**。
  _freeCardAcceptedActivities[numericId] = normalized.activity;

  // 右侧执行状态显示用户填写的活动。
  if (rightPanel) {
    // M02-S02-G03：自由卡的结束按钮走"结束并记录反馈"（先问清楚，
    // 再停止计时、再写事件）；普通/微型/目标卡保持"确认完成任务"不变。
    var endButton = isFreeCardTask(task)
      ? '<button class="btn pri" onclick="openFreeCardEndForm(' + numericId + ')" style="width:100%"><i class="fa-solid fa-check"></i> 结束并记录反馈</button>'
      : '<button class="btn pri" onclick="confirmComplete(' + numericId + ')" style="width:100%"><i class="fa-solid fa-check"></i> 确认完成任务</button>';
    rightPanel.innerHTML =
      '<div style="text-align:center;margin-bottom:8px">' +
      '<div style="font-size:.78rem;color:var(--text-secondary);margin-bottom:4px">执行中...</div>' +
      '<div class="card-timer-display" style="font-family:var(--font-heading);font-size:1.3rem;color:var(--gold);margin-bottom:6px">00:00</div>' +
      '<div style="font-size:.72rem;color:var(--text-muted);margin-bottom:6px;word-break:break-all">' + escapeHtml(normalized.activity) + '</div>' +
      '<div style="font-size:.68rem;color:var(--text-muted);margin-bottom:6px">计划 ' + minutes + ' 分</div>' +
      '<div style="font-size:.66rem;color:var(--text-muted);line-height:1.4;margin-bottom:6px">请同时为手机手动设置计时器；网页计时不应替代手机提醒。</div>' +
      '</div>' +
      '<button class="btn" onclick="pauseInlineTimer(' + numericId + ')" style="width:100%;margin-bottom:6px"><i class="fa-solid fa-pause"></i> 暂停</button>' +
      endButton;
  }

  // 写 accept_task 事件（绑定返回的 session_id 与活动文本）。
  try {
    await api('/api/task-feedback', {
      method: 'POST',
      body: JSON.stringify({
        task_id: numericId,
        event_type: 'accept_task',
        planned_minutes: minutes,
        completion_status: 'accepted',
        reason_category: 'other',
        reason_detail: normalized.reason,
        note: JSON.stringify({
          schema_version: 1,
          session_id: sessionId,
          activity: normalized.activity
        })
      })
    });
  } catch (e) {
    await compensateFreeCardAcceptFailure(numericId, sessionId);
    // 保留活动 / 理由输入，便于用户重试。
    openFreeCardAcceptForm(numericId, { activity: normalized.activity, reason: normalized.reason });
    toast((e.message || '接受记录保存失败') + '；已尽力结束刚创建的计时，请重试', 'err');
    _pendingFreeCardAcceptId = null;
    return;
  }
  _pendingFreeCardAcceptId = null;
  toast('计时已开始，请同时为手机设置计时器！', 'suc');
}

// 补偿：接受事件写入失败 → 尽力结束刚创建的计时 session，绝不留下
// "静默运行且没有活动记录"的计时器。
async function compensateFreeCardAcceptFailure(taskId, sessionId) {
  var sid = sessionId;
  if (sid === null || sid === undefined) {
    var snap = _timerSnapshot();
    sid = snap.session ? snap.session.id : null;
  }
  if (sid === null || sid === undefined) return;
  try {
    var owner = await _getTimerOwner();
    await owner.completeSession({
      sessionId: sid,
      actualMinutes: 1,
      result: 'abandoned',
      reason: 'free_card_acceptance_event_failed'
    });
    owner.stopInlineTimer();
    _refreshTimerViews();
  } catch (e) {
    toast('计时状态可能仍需你手动处理（自动结束失败）', 'err');
  }
}

// ============ 自由卡结束反馈（M02-S02-G03）============
// 合同要点：
// - 只作用于 **正式自由卡**（沿用源码里已有的卡型判定
//   ``normalizeCardType(task.task_type) === 'free'``）；普通 / 微型 /
//   目标卡的完成、关怀与计时行为 **逐字不变**。
// - 用户 **主动结束** 自由卡时，先问清楚（是否顺利 / 是否被中断 /
//   实际活动 / 可选原因），用户确认后才停止计时并写事件：
//   **绝不** 自动替用户选择"顺利"，**绝不** 把"打开了表单"或
//   "计时已停止"当作反馈已保存。
// - 反馈只复用既有 ``POST /api/task-feedback`` 与既有合法 event_type /
//   reason_category；实际活动与本次结论放进既有 note 字段（JSON，
//   与 accept_task 的 schema_version 约定兼容）。
// - 中断绝不记为已完成：timer/complete 的 result 与事件的
//   completion_status 都跟随用户的选择；计时停止失败 → 保留现状，
//   绝不写反馈。
// - 保存失败 → 保留表单内容、允许重试；取消 → 绝不谎报保存成功。
// - 成功保存 → 回到统一抽卡。
var FREE_CARD_END_FORM_ID_PREFIX = 'freeCardEndForm_';
// 接受自由卡时填写的活动（结束反馈的 **可编辑预填**；没有就留空）。
var _freeCardAcceptedActivities = {};
// 结束反馈的表单状态（面板快照 / 计时是否已停 / 时长），按 taskId 存。
var _freeCardEndState = {};
// 正在提交的自由卡结束反馈（避免重复提交）。
var _pendingFreeCardEndId = null;

// 是否是正式自由卡（沿用既有卡型判定，不发明新的卡型识别规则）。
function isFreeCardTask(task) {
  return !!task && normalizeCardType(task.task_type) === 'free';
}

// 在 **同一张卡片** 内展开"结束反馈"表单（不新建页面）。
// 是否顺利 / 是否被中断 **默认都不选中**：绝不替用户选择"顺利"。
function openFreeCardEndForm(taskId) {
  var numericId = (typeof taskId === 'number') ? taskId : parseInt(taskId, 10);
  if (!isFinite(numericId) || numericId <= 0) {
    toast('任务不存在', 'err');
    return;
  }
  var card = document.querySelector('.task-card.drawn-card[data-task-id="' + numericId + '"]');
  if (!card) { toast('请先抽一张卡牌', 'err'); return; }
  var rightPanel = card.querySelector('.drawn-card-right-panel');
  if (!rightPanel) return;

  var formId = FREE_CARD_END_FORM_ID_PREFIX + numericId;
  // 记住当前面板（取消时原样恢复"执行中"面板，计时继续走）。
  // 只记第一次：再次打开（保存失败后重试）时 **不** 覆盖成表单本身。
  var state = _freeCardEndState[numericId] || {};
  if (typeof state.panelHtml !== 'string') {
    state.panelHtml = rightPanel.innerHTML;
  }
  _freeCardEndState[numericId] = state;

  rightPanel.innerHTML = '';

  // 运行状态（保留计时显示：打开表单 **不代表** 计时已停止）。
  var running = document.createElement('div');
  running.style.cssText = 'text-align:center;margin-bottom:8px';
  var runningText = document.createElement('div');
  runningText.style.cssText = 'font-size:.78rem;color:var(--text-secondary);margin-bottom:4px';
  runningText.textContent = '执行中...';
  running.appendChild(runningText);
  var timerDisplay = document.createElement('div');
  timerDisplay.className = 'card-timer-display';
  timerDisplay.style.cssText = 'font-family:var(--font-heading);font-size:1.3rem;color:var(--gold);margin-bottom:6px';
  timerDisplay.textContent = '00:00';
  running.appendChild(timerDisplay);
  rightPanel.appendChild(running);

  var box = document.createElement('div');
  box.className = 'free-card-end-form';

  var intro = document.createElement('div');
  intro.style.cssText = 'font-size:.76rem;color:var(--text-secondary);margin-bottom:6px';
  intro.textContent = '结束这张自由卡了？如实记一下，保存成功后才算数。';
  box.appendChild(intro);

  var outcomeLabel = document.createElement('div');
  outcomeLabel.style.cssText = 'font-size:.72rem;color:var(--text-muted);margin-bottom:3px';
  outcomeLabel.textContent = '这次是否顺利（必选，二选一）';
  box.appendChild(outcomeLabel);

  var smoothInput = document.createElement('input');
  smoothInput.setAttribute('type', 'radio');
  smoothInput.setAttribute('name', 'freeCardEndOutcome_' + numericId);
  smoothInput.setAttribute('id', formId + '_smooth');
  smoothInput.setAttribute('value', 'smooth');
  var smoothLabel = document.createElement('label');
  smoothLabel.setAttribute('for', formId + '_smooth');
  smoothLabel.style.cssText = 'font-size:.78rem;display:flex;gap:6px;align-items:center;margin-bottom:4px';
  var smoothText = document.createElement('span');
  smoothText.textContent = '顺利完成了';
  smoothLabel.appendChild(smoothInput);
  smoothLabel.appendChild(smoothText);
  box.appendChild(smoothLabel);

  var interruptedInput = document.createElement('input');
  interruptedInput.setAttribute('type', 'radio');
  interruptedInput.setAttribute('name', 'freeCardEndOutcome_' + numericId);
  interruptedInput.setAttribute('id', formId + '_interrupted');
  interruptedInput.setAttribute('value', 'interrupted');
  var interruptedLabel = document.createElement('label');
  interruptedLabel.setAttribute('for', formId + '_interrupted');
  interruptedLabel.style.cssText = 'font-size:.78rem;display:flex;gap:6px;align-items:center;margin-bottom:6px';
  var interruptedText = document.createElement('span');
  interruptedText.textContent = '中途被打断了';
  interruptedLabel.appendChild(interruptedInput);
  interruptedLabel.appendChild(interruptedText);
  box.appendChild(interruptedLabel);

  // 两个单选互斥（并 **不** 预选任何一项）。
  smoothInput.addEventListener('click', function () {
    smoothInput.checked = true;
    interruptedInput.checked = false;
  });
  interruptedInput.addEventListener('click', function () {
    interruptedInput.checked = true;
    smoothInput.checked = false;
  });

  var activityLabel = document.createElement('label');
  activityLabel.setAttribute('for', formId + '_activity');
  activityLabel.style.cssText = 'font-size:.72rem;color:var(--text-muted);display:block;margin-bottom:3px';
  activityLabel.textContent = '实际做了什么（必填，可修改）';
  box.appendChild(activityLabel);

  var activityInput = document.createElement('input');
  activityInput.setAttribute('type', 'text');
  activityInput.setAttribute('id', formId + '_activity');
  activityInput.setAttribute('maxlength', String(FREE_CARD_MAX_ACTIVITY_LENGTH));
  activityInput.setAttribute('placeholder', '例如：看了一集纪录片');
  activityInput.style.cssText = 'width:100%;margin-bottom:6px;padding:6px;border-radius:8px;border:1px solid var(--card-border);background:rgba(0,0,0,0.25);color:var(--text-primary)';
  // 可编辑预填：接受时填写的活动（没有就留空，**绝不** 编造事实）。
  var priorActivity = _freeCardAcceptedActivities[numericId];
  if (typeof priorActivity === 'string' && priorActivity) activityInput.value = priorActivity;
  box.appendChild(activityInput);

  var reasonLabel = document.createElement('label');
  reasonLabel.setAttribute('for', formId + '_reason');
  reasonLabel.style.cssText = 'font-size:.72rem;color:var(--text-muted);display:block;margin-bottom:3px';
  reasonLabel.textContent = '原因（可选）';
  box.appendChild(reasonLabel);

  var reasonInput = document.createElement('input');
  reasonInput.setAttribute('type', 'text');
  reasonInput.setAttribute('id', formId + '_reason');
  reasonInput.setAttribute('maxlength', String(FREE_CARD_MAX_ACTIVITY_LENGTH));
  reasonInput.setAttribute('placeholder', '例如：手机响了');
  reasonInput.style.cssText = 'width:100%;margin-bottom:6px;padding:6px;border-radius:8px;border:1px solid var(--card-border);background:rgba(0,0,0,0.25);color:var(--text-primary)';
  box.appendChild(reasonInput);

  var saveBtn = document.createElement('button');
  saveBtn.className = 'btn pri';
  saveBtn.setAttribute('id', formId + '_save');
  saveBtn.style.cssText = 'width:100%;margin-bottom:6px';
  saveBtn.textContent = '保存反馈';
  saveBtn.addEventListener('click', function () { submitFreeCardEnd(numericId); });
  box.appendChild(saveBtn);

  var cancelBtn = document.createElement('button');
  cancelBtn.className = 'btn';
  cancelBtn.setAttribute('id', formId + '_cancel');
  cancelBtn.style.cssText = 'width:100%';
  cancelBtn.textContent = '取消';
  cancelBtn.addEventListener('click', function () { cancelFreeCardEndForm(numericId); });
  box.appendChild(cancelBtn);

  rightPanel.appendChild(box);
}

// 取消结束反馈：取消 = 没有保存任何反馈，绝不谎报保存成功。
function cancelFreeCardEndForm(taskId) {
  var numericId = (typeof taskId === 'number') ? taskId : parseInt(taskId, 10);
  if (!isFinite(numericId) || numericId <= 0) return;
  var state = _freeCardEndState[numericId] || {};
  if (state.timerStopped) {
    // 计时已经停了 → 表单保留，用户可以再试一次保存。
    toast('已取消保存，本次反馈还没有记录（可以再试一次）', 'inf');
    return;
  }
  var card = document.querySelector('.task-card.drawn-card[data-task-id="' + numericId + '"]');
  if (card) {
    var rightPanel = card.querySelector('.drawn-card-right-panel');
    if (rightPanel && typeof state.panelHtml === 'string') {
      // 原样恢复"执行中"面板（计时没有被停止，任务仍在进行）。
      rightPanel.innerHTML = state.panelHtml;
    }
  }
  delete _freeCardEndState[numericId];
  toast('已取消，本次反馈没有保存', 'inf');
}

// 提交自由卡结束反馈：先按用户的选择停止计时，再写既有反馈事件。
async function submitFreeCardEnd(taskId) {
  var numericId = (typeof taskId === 'number') ? taskId : parseInt(taskId, 10);
  if (!isFinite(numericId) || numericId <= 0) {
    toast('任务不存在', 'err');
    return;
  }
  // 避免重复提交（同一张卡在保存途中不再发起第二次提交）。
  if (_pendingFreeCardEndId === numericId) return;

  var formId = FREE_CARD_END_FORM_ID_PREFIX + numericId;
  var smoothEl = document.getElementById(formId + '_smooth');
  var interruptedEl = document.getElementById(formId + '_interrupted');
  var activityEl = document.getElementById(formId + '_activity');
  var reasonEl = document.getElementById(formId + '_reason');

  // 是否顺利 / 是否被中断：必须由用户 **明确选择**（默认两者都不选中）。
  var outcome = '';
  if (smoothEl && smoothEl.checked) outcome = 'smooth';
  else if (interruptedEl && interruptedEl.checked) outcome = 'interrupted';
  if (!outcome) {
    toast('请先选择：顺利完成了，还是中途被打断了', 'err');
    return;
  }

  // 实际活动：必填（没填就 **绝不** 把它伪装成事实）。
  var activityRaw = activityEl && typeof activityEl.value === 'string' ? activityEl.value : '';
  var activity = activityRaw.trim();
  if (!activity) {
    toast('请填写这次实际做了什么', 'err');
    return;
  }
  if (activity.length > FREE_CARD_MAX_ACTIVITY_LENGTH) {
    toast('实际活动最多 200 字', 'err');
    return;
  }
  if (/[\x00-\x1f\x7f]/.test(activity)) {
    toast('实际活动包含非法字符', 'err');
    return;
  }
  var reason = reasonEl && typeof reasonEl.value === 'string' ? reasonEl.value.trim() : '';
  if (reason.length > FREE_CARD_MAX_ACTIVITY_LENGTH) {
    toast('原因最多 200 字', 'err');
    return;
  }

  var state = _freeCardEndState[numericId] || {};
  var planned = state.planned != null ? state.planned : null;
  var actual = state.actual != null ? state.actual : null;

  _pendingFreeCardEndId = numericId;
  try {
    // AR03-G08：停止计时统一经 ESM timer owner（唯一生命周期所有者）。
    var owner = await _getTimerOwner();
    // === 停止计时（结果跟随用户的选择）===============================
    if (!state.timerStopped) {
      var _snap = _timerSnapshot();
      var session = _snap.session;
      if (session && session.id) {
        // 计时属于别的任务 → 绝不动它，也绝不声称"结束成功"。
        if (Number(session.task_id) !== numericId) {
          toast('当前计时属于另一张卡，反馈没有保存，请重试', 'err');
          return;
        }
        // AR03-G08：实际分钟数由 owner 统一计算（暂停时用 pausedElapsedMs，
        // 运行时用 now-started + paused_seconds*1000，下限 1）。
        actual = owner.getActualMinutes();
        planned = session.planned_minutes != null ? session.planned_minutes : null;
        var stopResult = (outcome === 'smooth') ? 'completed' : 'abandoned';
        // 中断：绝不记为已完成（沿用既有"提前结束"的 abandoned 语义）。
        var stopReason = (outcome === 'smooth') ? null : 'early_finish';
        try {
          await owner.completeSession({
            sessionId: session.id,
            actualMinutes: actual,
            result: stopResult,
            reason: stopReason
          });
        } catch (e) {
          // 计时停止失败 → 保留现状：不写反馈、不清 dock、表单内容保留。
          toast((e.message || '停止计时失败') + '；反馈没有保存，请重试', 'err');
          return;
        }
        state.timerStopped = true;
        state.outcome = outcome;
        state.planned = planned;
        state.actual = actual;
        _freeCardEndState[numericId] = state;
        // 计时已停 → 锁定结论（重试时结论不会与计时状态相矛盾）。
        if (smoothEl) smoothEl.disabled = true;
        if (interruptedEl) interruptedEl.disabled = true;
        owner.stopInlineTimer();
        _refreshTimerViews();
      } else {
        // 没有进行中的计时（例如计时早已被停掉）：不重复停止，
        // 直接进入"写反馈"阶段。
        state.timerStopped = true;
        state.outcome = outcome;
        _freeCardEndState[numericId] = state;
      }
    }

    // === 写既有反馈事件（复用既有 /api/task-feedback 与合法字段）======
    var eventType;
    var completionStatus;
    var reasonCategory;
    var reasonDetail;
    var outcomeLabel = outcome === 'smooth' ? '顺利完成' : '中途被打断';
    if (outcome === 'smooth') {
      eventType = (planned != null && actual != null && actual >= planned)
        ? 'finish_on_time'
        : 'finish_early';
      completionStatus = 'completed';
      reasonCategory = 'other';
      reasonDetail = reason || '顺利完成';
    } else {
      eventType = 'abandon_task';
      completionStatus = 'abandoned';
      reasonCategory = 'external_interrupt';
      reasonDetail = reason || '被中断';
    }
    // note：既有允许的 note 字段（自由事件的 note 语义保持自由），
    // 用与 accept_task 一致的 schema_version 约定 + 一句可读摘要。
    var note = JSON.stringify({
      schema_version: 1,
      outcome: outcome === 'smooth' ? 'smooth' : 'interrupted',
      interrupted: outcome !== 'smooth',
      activity: activity,
      summary: outcomeLabel + '｜实际活动：' + activity
    });

    if (!state.feedbackSaved) {
      try {
        await api('/api/task-feedback', {
          method: 'POST',
          body: JSON.stringify({
            task_id: numericId,
            event_type: eventType,
            planned_minutes: planned,
            actual_minutes: actual,
            completion_status: completionStatus,
            reason_category: reasonCategory,
            reason_detail: reasonDetail,
            note: note
          })
        });
      } catch (e) {
        // 保存失败 → 保留表单内容、允许重试（绝不谎报保存成功）。
        state.feedbackSaved = false;
        _freeCardEndState[numericId] = state;
        toast((e.message || '反馈保存失败') + '；已保留你填写的内容，请重试', 'err');
        return;
      }
      state.feedbackSaved = true;
      _freeCardEndState[numericId] = state;
    }

    // === 顺利结束 → 复用既有"任务完成"端点（中断绝不记为已完成）======
    if (outcome === 'smooth' && !state.taskCompleted) {
      try {
        await api('/api/tasks/' + numericId + '/complete', { method: 'POST' });
        await api('/api/tasks/' + numericId + '/move-to-discard', { method: 'POST' });
      } catch (e) {
        // 反馈已经保存；任务完成失败 → 如实告知，绝不谎报"全部完成"。
        toast((e.message || '任务完成记录失败') + '；本次反馈已保存', 'err');
        return;
      }
      state.taskCompleted = true;
      _freeCardEndState[numericId] = state;
    }

    delete _freeCardEndState[numericId];
    delete _freeCardAcceptedActivities[numericId];
    toast('已记录这次自由卡的反馈', 'suc');
    returnToUnifiedGachaAfterFreeCard();
  } finally {
    _pendingFreeCardEndId = null;
  }
}

// 保存成功 → 回到统一抽卡（清理本次卡片，清空抽卡状态）。
function returnToUnifiedGachaAfterFreeCard() {
  var result = document.getElementById('gachaResult');
  if (result) {
    result.innerHTML =
      '<div class="empty-state"><i class="fa-solid fa-circle-check" style="color:var(--green)"></i>' +
      '<p>已记录这次自由卡的反馈，可以继续抽卡了。</p></div>';
  }
  if (typeof gachaState === 'object' && gachaState) {
    gachaState.currentTaskId = null;
    gachaState.canReplace = false;
  }
  _currentDrawnTask = null;
  loadTasks();
  refreshGachaStats();
  updateDiscardPileVisual();
}

// ============ 开始任务（计时器）============
// Module-level caches used by startTask() so a card rendered via the
// multi/single/care/replace paths is startable even before /api/tasks
// populates allTasks (M1.3A). Safe to write from any draw path.
var _currentDrawnTask = null;
// Idempotency guard for the timer-start POST reentrancy (M1.3A).
var _pendingStartTaskId = null;

async function startTask(taskId) {
  // Coerce taskId to a positive integer literal. The onclick= handler
  // already emits startTask(parseInt(task.id,10)), but hostile payloads
  // or programmatic callers could pass a non-numeric; we must NOT
  // let such a value reach the allTasks.find callback. (M1.3A)
  var numericId = (typeof taskId === 'number') ? taskId : parseInt(taskId, 10);
  if (!isFinite(numericId) || numericId <= 0) {
    toast('任务不存在', 'err');
    return;
  }
  // Drop a second immediate activation while the POST is pending.
  if (_pendingStartTaskId === numericId) return;
  _pendingStartTaskId = numericId;
  try {
  // 1) Prefer the active drawn card we just rendered (handles the
  //    race where allTasks hasn't loaded yet but the card is on
  //    screen via renderMultiResults → activateMultiCard → renderDrawnCard).
  var task = null;
  if (_currentDrawnTask && Number(_currentDrawnTask.id) === numericId) {
    task = _currentDrawnTask;
  } else if (Array.isArray(multiDrawResults) && multiDrawResults.length) {
    for (var i = 0; i < multiDrawResults.length; i += 1) {
      var m = multiDrawResults[i];
      if (m && Number(m.id) === numericId) { task = m; break; }
    }
  }
  // 2) Fall back to the loaded catalog (legacy / single-draw / care-draw
  //    after /api/tasks has loaded).
  if (!task && Array.isArray(allTasks)) {
    task = allTasks.find(function (x) { return x.id === numericId; }) || null;
  }
  if (!task) {
    toast('任务不存在', 'err');
    return;
  }
  if (!task.is_unlocked && task.is_unlocked !== undefined) {
    toast(prereqHint(task) || '任务被前置依赖阻塞', 'err');
    return;
  }
  // 开始/接受当前卡 → 本链结束。
  resetReplaceChain();

  // M02-S02-G01-W08：自由卡的"开始"必须先走 **接受流程**（填写活动 + 理由），
  // 绝不允许用行内 estimated_time 直接启动计时。普通/微型/目标卡保持原样。
  if (normalizeCardType(task.task_type) === 'free') {
    _pendingStartTaskId = null;
    openFreeCardAcceptForm(numericId);
    return;
  }

  // M1.3B: coerce task.estimated_time to a finite positive integer
  // before it is concatenated into the rightPanel innerHTML string
  // AND before it is sent to the timer-start request. A hostile or stale
  // value (string, NaN, <1, >480) must NOT reach the DOM, the URL,
  // or the API. This is the only XSS path in startTask.
  var rawEstimated = Number(task.estimated_time);
  var planned = (isFinite(rawEstimated) && Math.floor(rawEstimated) === rawEstimated
                 && rawEstimated >= 1 && rawEstimated <= 480)
                ? Math.floor(rawEstimated) : 30;
  var card = document.querySelector('.task-card.drawn-card[data-task-id="' + numericId + '"]');
  if (!card) { toast('请先抽一张卡牌', 'err'); return; }

  var rightPanel = card.querySelector('.drawn-card-right-panel');
  if (!rightPanel) return;

  rightPanel.innerHTML =
    '<div style="text-align:center;margin-bottom:8px">' +
    '<div style="font-size:.78rem;color:var(--text-secondary);margin-bottom:4px">执行中...</div>' +
    '<div class="card-timer-display" style="font-family:var(--font-heading);font-size:1.3rem;color:var(--gold);margin-bottom:6px">00:00</div>' +
    '<div style="font-size:.68rem;color:var(--text-muted)">计划 ' + planned + ' 分</div>' +
    '</div>' +
    '<button class="btn" onclick="pauseInlineTimer(' + numericId + ')" style="width:100%;margin-bottom:6px"><i class="fa-solid fa-pause"></i> 暂停</button>' +
    '<button class="btn pri" onclick="confirmComplete(' + numericId + ')" style="width:100%"><i class="fa-solid fa-check"></i> 确认完成任务</button>';

  try {
    // AR03-G08：计时启动统一经 ESM timer owner（唯一生命周期所有者）。
    // 普通任务路径 **不** 启用严格 session_id 校验（沿用既有语义）。
    var owner = await _getTimerOwner();
    await owner.startSession({
      taskId: numericId,
      plannedMinutes: planned,
      taskName: task.name
    });
    _refreshTimerViews();
    startInlineTimer(numericId);
    toast('计时已开始，加油！', 'suc');
  } catch (e) {
    toast(e.message || '启动计时失败', 'err');
    if (rightPanel) {
      rightPanel.innerHTML = '<button class="btn pri" onclick="startTask(' + numericId + ')" style="width:100%"><i class="fa-solid fa-play"></i> 开始任务</button>';
    }
  }
  } finally {
    _pendingStartTaskId = null;
  }
}

// 内嵌计时器更新
// AR03-G08：内嵌计时的句柄与唯一 session 归 ESM timer owner 所有；
// 这里只是 classic facade（卡内 DOM 的既有位置与文案保持不变）。
function startInlineTimer(taskId, startedAt, planned) {
  var owner = _timerOwner;
  if (!owner) {
    // owner 尚未就绪 → 异步取到后再启动（句柄始终在 owner 手里）。
    _getTimerOwner().then(function (o) {
      o.startInlineTimer(taskId);
    }).catch(function (e) {
      console.error('[timer] startInlineTimer', e);
    });
    return;
  }
  owner.startInlineTimer(taskId);
}

// 内嵌暂停
async function pauseInlineTimer(taskId) {
  var snap = _timerSnapshot();
  if (!snap.session || snap.session.task_id !== taskId) return;
  await toggleTimerDockPause();
  var card = document.querySelector('.task-card.drawn-card[data-task-id="' + taskId + '"]');
  if (!card) return;
  var rightPanel = card.querySelector('.drawn-card-right-panel');
  if (!rightPanel) return;
  var pauseBtn = rightPanel.querySelector('button[onclick*="pauseInlineTimer"]');
  if (pauseBtn) {
    pauseBtn.innerHTML = _timerSnapshot().paused
      ? '<i class="fa-solid fa-play"></i> 继续'
      : '<i class="fa-solid fa-pause"></i> 暂停';
  }
}

// 确认完成任务（需要先停止计时器）
// 合约（M1.3C）：
//   - 计时器停API失败时：保留现有timer-active状态，不完成、不弃牌、不重置；显示错误。
//   - API成功时：才清空dock，再走原有completeWithFeedback流程。
//   - 实际时长需考虑历史paused_seconds累积（暂停段已被服务端扣除并累加）。
async function confirmComplete(taskId) {
  // 先停止计时器
  var owner = null;
  try {
    owner = await _getTimerOwner();
  } catch (e) {
    toast('计时模块加载失败，任务未完成', 'err');
    return;
  }
  var snap = owner.getSnapshot();
  if (snap.session && snap.session.id) {
    // AR03-G08：实际分钟数由 owner 统一计算（暂停时用 pausedElapsedMs，
    // 运行时用 now-started + paused_seconds*1000，下限 1）。
    var actualMin = owner.getActualMinutes();
    try {
      await owner.completeSession({
        sessionId: snap.session.id,
        actualMinutes: actualMin,
        result: 'completed'
      });
    } catch (e) {
      // M1.3C：API失败 → 不重置dock、不调用completeWithFeedback、不标记任务完成；
      // 保留现有timer-active状态让用户能重试。
      toast(e.message || '停止计时失败，任务未完成', 'err');
      return;
    }
  }
  // API成功（或无计时器）→ 清理dock状态，走原有任务完成/弃牌流程
  owner.stopInlineTimer();
  _refreshTimerViews();
  await completeWithFeedback(taskId);
}

async function checkTaskTimerStatus(taskId) {
  try {
    var owner = await _getTimerOwner();
    var r = await owner.checkTaskTimerStatus(taskId);
    if (r && r.overdue) {
      toast(WARM_MESSAGES.timeout, 'inf');
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
    // 理由 **没有** 默认选中项：用户必须自己明确选一个。
    // 开关 A 复用本链状态；开关 B 每次新表单默认不勾选（不写入 gachaState）。
    bar.innerHTML =
      '<input type="radio" name="reason" value="low_energy" id="rr_low"><label for="rr_low">精力不足</label>' +
      '<input type="radio" name="reason" value="no_time" id="rr_no"><label for="rr_no">时间不够</label>' +
      '<input type="radio" name="reason" value="similar_done" id="rr_sim"><label for="rr_sim">刚做过类似</label>' +
      '<input type="radio" name="reason" value="other" id="rr_ot"><label for="rr_ot">其他</label>' +
      '<label class="replace-opt" for="rr_allow_repeat"><input type="checkbox" id="rr_allow_repeat"> 允许曾被更换的卡牌再次抽出</label>' +
      '<label class="replace-opt" for="rr_hide_today"><input type="checkbox" id="rr_hide_today"> 我今天内不想再看到这张卡</label>' +
      '<button class="btn pri sm" onclick="doReplace()">确认换牌</button>';
    var card = document.getElementById('gachaResult').querySelector('.task-card.drawn-card');
    if (card) card.appendChild(bar);
  } else {
    bar.style.display = 'flex';
  }
  // 每次打开表单都按链状态同步开关 A，并确保开关 B 未被勾选。
  var allowEl = document.getElementById('rr_allow_repeat');
  if (allowEl) allowEl.checked = !!gachaState.allowRepeatReplaced;
  var hideEl = document.getElementById('rr_hide_today');
  if (hideEl) hideEl.checked = false;
}

// 读取表单里的开关 A，并同步成本链状态（用户选择在链内保持）。
function readAllowRepeatReplaced() {
  var el = document.getElementById('rr_allow_repeat');
  var value = !!(el && el.checked);
  gachaState.allowRepeatReplaced = value;
  return value;
}

async function doReplace() {
  var rid = gachaState.replacedTaskId;
  // M02-S03-G01-W04：理由 **必须显式选择**，绝不静默回落成 other。
  var reasonEl = document.querySelector('#replaceReasonBar input[name="reason"]:checked');
  if (!reasonEl) {
    toast('请先选择换牌理由', 'err');
    return;
  }
  var reason = reasonEl.value;
  var allowRepeat = readAllowRepeatReplaced();
  var hideEl = document.getElementById('rr_hide_today');
  var hideToday = !!(hideEl && hideEl.checked);
  var chainIds = Array.isArray(gachaState.replacedTaskIds) ? gachaState.replacedTaskIds.slice() : [];
  // M02-S03-G02-W03：同一条连续换卡链沿用同一个 session；
  // 本次换牌是一个新的真实动作 → 新的 action id。
  var actionId = newUnifiedGachaActionId('replace');
  var replacedTaskId = unifiedGachaTaskId(rid);
  try {
    var availableMinutes = getGachaAvailableMinutes();
    var r = await api('/api/gacha/replace', {
      method: 'POST',
      body: JSON.stringify({
        task_id: rid,
        reason: reason,
        pool: gachaState.pool,
        energy: gachaState.energy,
        available_time: availableMinutes,
        preferred_tag: gachaState.selectedTag || null,
        replaced_task_ids: chainIds,
        allow_repeat_replaced: allowRepeat,
        hide_today: hideToday
      })
    });
    if (r.task) {
      if (r.pool) gachaState.pool = r.pool;
      // 只有 **成功** 才把旧卡并入本链；失败时链与当前卡都保持不变。
      if (chainIds.indexOf(rid) === -1) chainIds.push(rid);
      gachaState.replacedTaskIds = chainIds;
      gachaState.currentTaskId = r.task.id;
      // 单抽路径换卡成功后 **仍可** 继续换卡（不永久关闭 canReplace）。
      gachaState.canReplace = true;
      // M1.3A: cache the active drawn task after a replace.
      _currentDrawnTask = r.task;
      document.getElementById('gachaResult').innerHTML = '';
      document.getElementById('gachaResult').appendChild(renderDrawnCard(r.task, 0));
      // M02-S03-G02-W03：只有成功才记录 card_replaced。
      // task_id 指 **真实被换出的那张牌**；context 记录新牌 id、明确选择的
      // 换牌理由、开关 A/B 与真实 pool。
      var newTaskId = unifiedGachaTaskId(r.task.id);
      if (replacedTaskId !== null) {
        sendUnifiedGachaEvent('card_replaced', replacedTaskId, {
          new_task_id: newTaskId,
          reason: reason,
          allow_repeat_replaced: allowRepeat,
          hide_today: hideToday,
          pool: r.pool || gachaState.pool,
          replaced_task_ids: chainIds.slice()
        }, unifiedGachaEventId(actionId, 'card_replaced', replacedTaskId));
      }
      // 换卡得到的 **新牌** 也是一次真实发牌 → card_drawn（新牌的真实 id）。
      sendUnifiedGachaEvent('card_drawn', newTaskId, {
        source: 'replace',
        pool: r.pool || gachaState.pool,
        energy: gachaState.energy,
        available_time: availableMinutes,
        preferred_tag: gachaState.selectedTag || null
      }, unifiedGachaEventId(actionId, 'card_drawn', newTaskId));
      // 新牌真正渲染进结果区 → 记录新牌的 card_shown。
      reportUnifiedGachaCardShown(r.task.id, {
        source: 'replace',
        surface: 'result',
        pool: r.pool || gachaState.pool
      }, actionId);
      toast('已换牌', 'inf');
    }
  } catch (e) {
    // 失败：保留当前卡、保留表单与开关状态，显示错误并允许重试。
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

    // M1.3D: 任务完成链路的最终环节改为询问用户真实感受。
    // 不再隐式 POST 硬编码的 energy/mood 值；改由 submitFeedback/cancelFeedback
    // 在用户明确操作后再调用 /api/tasks/<id>/feedback。完成清理
    // （loadTasks/refreshGachaStats/updateDiscardPileVisual/dock 重置）
    // 在 feedback 关闭后再做，保证与原有"任务已完成+弃牌"语义一致。
    loadTasks();
    refreshGachaStats();
    updateDiscardPileVisual();
    // AR03-G08：清空唯一计时状态（owner 持有），并同步两处计时 UI。
    if (_timerOwner) {
      _timerOwner.clear();
      _timerOwner.stopInlineTimer();
    }
    _refreshTimerViews();

    // 把后续切换交给 focus 关怀；用户取消/提交后再走 care modal。
    openFeedbackModalForTask(id, task ? task.category : null, finishEarly);
  } catch (e) {
    toast(e.message || '完成失败', 'err');
  }
}

// ============ 反馈表单（modal）============
// 仅当用户主动 确认 才会 POST /api/tasks/<id>/feedback；取消则零网络。
// 提交失败时停留在 modal 上、允许重试；不静默关闭。
var _pendingFeedbackSubmit = null;  // reentrancy guard: 当前正在 POST 的 taskId
function openFeedbackModalForTask(taskId, category, finishEarly) {
  // 把上下文记下，供 submitFeedback / cancelFeedback 后续恢复 care modal
  _feedbackContext = {
    taskId: taskId,
    category: category || null,
    finishEarly: !!finishEarly
  };
  // 预填表字段
  var idEl = document.getElementById('fbTaskId');
  if (idEl) idEl.value = String(taskId);
  var energyEl = document.getElementById('fbEnergy');
  if (energyEl) energyEl.value = '5';
  var energyVal = document.getElementById('fbEnergyVal');
  if (energyVal) energyVal.textContent = '5';
  // 默认心情复位为 3（"满意"），并清除旧 .sel 标记
  gachaState.feedbackMood = 3;
  document.querySelectorAll('.feedback-emoji button').forEach(function (b) {
    b.classList.remove('sel');
    if (b.getAttribute('data-mood') === '3') b.classList.add('sel');
  });
  // 完成早退时不强制改值；保留用户原输入。无需清理额外字段。
  _pendingFeedbackSubmit = null;  // 进入模态时清掉旧锁
  showModal('feedbackModal');
}

var _feedbackContext = null;

function transitionToCareModal() {
  var ctx = _feedbackContext;
  _feedbackContext = null;
  _pendingFeedbackSubmit = null;
  if (!ctx) return;
  showCareModal(ctx.taskId, ctx.category);
}

function submitFeedback() {
  var ctx = _feedbackContext;
  if (!ctx) {
    closeModal('feedbackModal');
    return;
  }
  var taskId = ctx.taskId;
  // reentrancy: 阻止快速重复点击造成并发 POST
  if (_pendingFeedbackSubmit === taskId) return;
  var energyEl = document.getElementById('fbEnergy');
  var energy = parseInt(energyEl ? energyEl.value : '5', 10);
  if (!isFinite(energy) || energy < 1 || energy > 10) energy = 5;
  var mood = gachaState.feedbackMood;
  if (!isFinite(mood) || mood < 1 || mood > 5) mood = 3;
  var body = { energy_after: energy, mood_after: mood };
  if (ctx.finishEarly) body.event_type = 'finish_early';

  _pendingFeedbackSubmit = taskId;
  // 不先关闭 modal —— 失败时要停留以供重试
  api('/api/tasks/' + taskId + '/feedback', {
    method: 'POST',
    body: JSON.stringify(body)
  }).then(function () {
    closeModal('feedbackModal');
    document.getElementById('gachaResult').innerHTML =
      '<div class="empty-state"><i class="fa-solid fa-circle-check" style="color:var(--green)"></i><p>太棒了，继续加油！</p></div>';
    refreshGachaStats();
    transitionToCareModal();
  }).catch(function (e) {
    _pendingFeedbackSubmit = null;  // 解锁，允许用户重新点确认
    toast((e && e.message) || '反馈提交失败，请重试', 'err');
    // 模态保持打开，不清空用户输入
  });
}

function cancelFeedback() {
  closeModal('feedbackModal');
  // 取消 = 不上报；直接走 care modal 以保持原"任务完成关怀"语义
  transitionToCareModal();
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
  // 发起新抽卡 → 本链结束。
  resetReplaceChain();
  // M02-S03-G02-W03：一次新的抽卡 → 开启新的行为事件 session。
  beginUnifiedGachaSession();
  var actionId = newUnifiedGachaActionId('care');
  var btn = document.getElementById('gachaBtn');
  if (btn) btn.disabled = true;
  var result = document.getElementById('gachaResult');
  result.innerHTML = '<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>正在抽卡...</p></div>';

  try {
    var availableMinutes = getGachaAvailableMinutes();
    var r = await api('/api/gacha/care-draw', {
      method: 'POST',
      body: JSON.stringify({
        pool: gachaState.pool,
        energy: gachaState.energy,
        available_time: availableMinutes,
        preferred_tag: gachaState.selectedTag || null,
        include_category: includeCategory || null,
        exclude_category: excludeCategory || null
      })
    });
    if (r.task) {
      if (r.pool) gachaState.pool = r.pool;
      gachaState.canReplace = r.can_replace !== false;
      gachaState.currentTaskId = r.task.id;
      // M1.3A: cache the active drawn task for the care-draw path.
      _currentDrawnTask = r.task;
      // M02-S03-G02-W03：服务端返回真实 task 后才记录 card_drawn。
      var careTaskId = unifiedGachaTaskId(r.task.id);
      var careContext = {
        source: 'care_draw',
        pool: r.pool || gachaState.pool,
        energy: gachaState.energy,
        available_time: availableMinutes,
        preferred_tag: gachaState.selectedTag || null,
        include_category: includeCategory || null,
        exclude_category: excludeCategory || null
      };
      sendUnifiedGachaEvent('card_drawn', careTaskId, careContext,
        unifiedGachaEventId(actionId, 'card_drawn', careTaskId));
      // M02-S03-G02-W03："帮我选"（关怀模态的同科/换口味两条路径走
      // /api/gacha/care-draw）成功返回新牌 → 记录 help_me_choose。
      // context 只放 **实际** 的 include/exclude category 与 pool。
      sendUnifiedGachaEvent('help_me_choose', careTaskId, {
        include_category: includeCategory || null,
        exclude_category: excludeCategory || null,
        pool: careContext.pool
      }, unifiedGachaEventId(actionId, 'help_me_choose', careTaskId));
      result.innerHTML = '';
      var stage = renderDrawnCard(r.task, 0);
      result.appendChild(stage);
      // 卡片真正进入结果区后才记录 card_shown。
      reportUnifiedGachaCardShown(careTaskId,
        { source: 'care_draw', surface: 'result', pool: careContext.pool }, actionId);
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

// submitFeedback / cancelFeedback 由 openFeedbackModalForTask 上方
// （M1.3D 区域）的版本提供；这里不再重复定义以免覆盖重入守卫。

async function handleSkip(id) {
  resetReplaceChain();
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
  resetReplaceChain();
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
    var m = await import('/static/modules/gacha/presentation.js');
    await m.refreshGachaStats(api);
  } catch (e) { /* 统计失败不阻塞 */ }
}

// ============ 弃牌堆视觉 ============
async function updateDiscardPileVisual() {
  try {
    var m = await import('/static/modules/gacha/presentation.js');
    await m.updateDiscardPileVisual(api);
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

// ============ TASK EDITOR (AR03-G13) ============
// 任务编辑器模态框（#taskModal）的**全部业务实现**与**唯一状态**
// （原始卡类型 / 当前标签数组 / 当前依赖选择数组）已迁至
// static/modules/tasks/editor.js（真实生产 ESM owner）。
// 此处**不再**保留任何影子实现；既有同步入口名
// （openTaskEdit / buildDepList / addTagChip / saveTask /
//   deleteCurrentTask）由 static/app.entry.js 在模块入口阶段**同步**
// 绑定到 window，src/index.html 的 inline handler 无需改动。
//
// 仍由 classic 层持有（owner **注入调用**，不复制）：
//   normalizeCardType —— 唯一实现（展示侧归一）；
//   allTasks / allTags —— 唯一任务 / 标签数据来源；
//   loadTasks / loadTags —— 唯一任务数据加载；
//   deleteTask —— 唯一任务删除（含 dependents 确认）。

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

// deleteCurrentTask 已迁至 static/modules/tasks/editor.js（ESM owner）。

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
// AR03-G12:「日程」页的**全部日程业务实现与唯一业务状态**
// （schedDate / slots / weeklyData / dailyData）已迁至
// static/modules/schedule/index.js（真实生产 ESM owner）。
// 此处**只**保留最薄 classic facade：
//   - 唯一共享的 ESM import promise（并发调用不会重复加载；加载失败清缓存重试）；
//   - 依赖注入 api / toast / showModal / closeModal：ESM 侧不新建独立
//     client、不引入全局 Store 或事件总线、不新建缓存 / 重试层；
//   - 旧函数名全部保留（renderSchedule / shiftDate / openActivityMgr /
//     closeActivityMgr / addActivity），src/index.html 的 inline onclick
//     （shiftDate / openActivityMgr）、app.js 内的 addEventListener 调用点
//     与导航 / INIT 调用点无需改动；
//   - classic 层**不再**持有第二份日程业务实现，也不直连 /api/schedule/*。
var _scheduleOwnerPromise = null;
var _scheduleOwner = null;

function _loadScheduleOwner() {
  if (!_scheduleOwnerPromise) {
    _scheduleOwnerPromise = import('/static/modules/schedule/index.js')
      .then(function (m) {
        _scheduleOwner = m.createScheduleOwner({
          api: api,
          toast: toast,
          showModal: showModal,
          closeModal: closeModal
        });
        return _scheduleOwner;
      })
      .catch(function (err) {
        _scheduleOwnerPromise = null;
        throw err;
      });
  }
  return _scheduleOwnerPromise;
}

function _scheduleCall(method, args) {
  return _loadScheduleOwner().then(function (owner) {
    return owner[method].apply(owner, args || []);
  }).catch(function (err) {
    console.error('[schedule] ' + method, err);
  });
}

function renderSchedule() {
  return _scheduleCall('renderSchedule');
}

function shiftDate(d) {
  return _scheduleCall('shiftDate', [d]);
}

function openActivityMgr() {
  return _scheduleCall('openActivityMgr');
}

function closeActivityMgr() {
  return _scheduleCall('closeActivityMgr');
}

function addActivity() {
  return _scheduleCall('addActivity');
}

// ============ KNOWLEDGE ============
// AR03-G06:「知识库」页的真实知识浏览业务实现与**唯一会话状态**
// （currentNotePath / 分类笔记缓存 / 当前分类）已迁至
// static/modules/knowledge/index.js（真实生产 ESM owner）。
// 此处**只**保留最薄 classic facade：
//   - 唯一共享的 ESM import promise（并发调用不会重复加载；加载失败清缓存重试）；
//   - 依赖注入 api / toast / mdToHtml / escapeHtml：ESM 侧不新建独立
//     client、不读真实 filesystem、不引入全局 Store 或事件总线；
//   - 旧函数名全部保留，src/index.html 的 inline onclick
//     （openCurrentInObsidian）与 app.js 内的调用点无需改动。
// mdToHtml 仍是 classic 层唯一的**同步** Markdown 呈现 helper（依赖页面既有
// marked 全局与其正则 fallback），仅作为依赖注入交给 ESM owner 使用，
// 本模块不复制实现、也不改成 async facade。
var _knowledgeOwnerPromise = null;
var _knowledgeOwner = null;

function _loadKnowledgeOwner() {
  if (!_knowledgeOwnerPromise) {
    _knowledgeOwnerPromise = import('/static/modules/knowledge/index.js')
      .then(function (m) {
        _knowledgeOwner = m.createKnowledgeOwner({
          api: api,
          toast: toast,
          mdToHtml: mdToHtml,
          escapeHtml: escapeHtml
        });
        return _knowledgeOwner;
      })
      .catch(function (err) {
        _knowledgeOwnerPromise = null;
        throw err;
      });
  }
  return _knowledgeOwnerPromise;
}

function _knowledgeCall(method, args) {
  return _loadKnowledgeOwner().then(function (owner) {
    return owner[method].apply(owner, args || []);
  }).catch(function (err) {
    console.error('[knowledge] ' + method, err);
  });
}

async function loadCategories() {
  await _knowledgeCall('loadCategories');
}

async function loadCategoryNotes(catId, catName) {
  await _knowledgeCall('loadCategoryNotes', [catId, catName]);
}

async function loadNote(path) {
  await _knowledgeCall('loadNote', [path]);
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

function openNoteFromCard(filePath) {
  return _knowledgeCall('openNoteFromCard', [filePath]);
}

function openCurrentInObsidian() {
  return _knowledgeCall('openCurrentInObsidian');
}

// ============ CONFIG ============
// AR03-G11：「设置」页「系统配置」表单的**全部业务实现**已迁至
// static/modules/config/index.js（真实生产 ESM owner）。
// 此处**只**保留最薄 classic facade：
//   - 唯一共享的 ESM import promise（并发调用不会重复加载；加载失败清缓存重试）；
//   - 依赖注入 api / toast / refreshAgentReadonlyHint：ESM 侧不新建独立
//     client、不引入全局 Store 或事件总线、不新建缓存 / 重试层；
//   - refreshAgentReadonlyHint 仍是 Agent 只读 owner 的既有 facade（唯一实现
//     在 static/modules/agent-readonly/index.js），config owner **只调用**它，
//     不复制第二份提示逻辑；
//   - 旧函数名 loadConfigForm / saveConfigForm 全部保留，src/index.html 的经典
//     inline onclick 与 app.js 内的导航调用点无需改动。
var _configOwnerPromise = null;
var _configOwner = null;

function _loadConfigOwner() {
  if (!_configOwnerPromise) {
    _configOwnerPromise = import('/static/modules/config/index.js')
      .then(function (m) {
        _configOwner = m.createConfigOwner({
          api: api,
          toast: toast,
          refreshAgentReadonlyHint: refreshAgentReadonlyHint
        });
        return _configOwner;
      })
      .catch(function (err) {
        _configOwnerPromise = null;
        throw err;
      });
  }
  return _configOwnerPromise;
}

function _configCall(method, args) {
  return _loadConfigOwner().then(function (owner) {
    return owner[method].apply(owner, args || []);
  }).catch(function (err) {
    console.error('[config] ' + method, err);
  });
}

function loadConfigForm() {
  return _configCall('loadConfigForm');
}

function saveConfigForm() {
  return _configCall('saveConfigForm');
}

// ============ AGENT READONLY (P1-6) ============
// AR03-G07：「设置」页 Agent 只读浏览面板的**全部业务实现与唯一会话状态**
// （agentRoList / agentRawSubdir / agentVaultSubject）已迁至
// static/modules/agent-readonly/index.js（真实生产 ESM owner）。
// 此处**只**保留最薄 classic facade：
//   - 唯一共享的 ESM import promise（并发调用不会重复加载；加载失败清缓存重试）；
//   - 依赖注入 api / toast / showModal / closeModal / escapeHtml：ESM 侧不新建
//     独立 client、不读真实 filesystem、不引入全局 Store 或事件总线；
//   - refreshAgentReadonlyHint 是**唯一实现**（CONFIG 表单提示与面板横幅共用
//     同一份 ESM 实现），classic 层不复制第二份文案逻辑；
//   - 旧函数名全部保留，app.js 内的 addEventListener 调用点无需改动。
var _agentRoOwnerPromise = null;
var _agentRoOwner = null;

function _loadAgentRoOwner() {
  if (!_agentRoOwnerPromise) {
    _agentRoOwnerPromise = import('/static/modules/agent-readonly/index.js')
      .then(function (m) {
        _agentRoOwner = m.createAgentReadonlyOwner({
          api: api,
          toast: toast,
          showModal: showModal,
          closeModal: closeModal,
          escapeHtml: escapeHtml
        });
        return _agentRoOwner;
      })
      .catch(function (err) {
        _agentRoOwnerPromise = null;
        throw err;
      });
  }
  return _agentRoOwnerPromise;
}

function _agentRoCall(method, args) {
  return _loadAgentRoOwner().then(function (owner) {
    return owner[method].apply(owner, args || []);
  }).catch(function (err) {
    console.error('[agent-readonly] ' + method, err);
  });
}

// CONFIG 表单提示与 Agent 面板横幅共用 ESM owner 的**唯一**实现。
function refreshAgentReadonlyHint(cfg) {
  return _agentRoCall('refreshHint', [cfg]);
}

async function openAgentReadonlyModal() {
  return _agentRoCall('openModal');
}

function closeAgentReadonlyModal() {
  return _agentRoCall('closeModal');
}

function switchAgentTab(tab) {
  return _agentRoCall('switchTab', [tab]);
}

async function loadAgentRoList() {
  return _agentRoCall('loadAgentList');
}

async function selectAgentReadonly(id, el) {
  return _agentRoCall('selectAgent', [id, el]);
}

async function loadAgentRawList(subdir) {
  return _agentRoCall('loadRawList', [subdir]);
}

async function loadAgentRawContent(path) {
  return _agentRoCall('loadRawContent', [path]);
}

async function loadAgentVaultList(subject) {
  return _agentRoCall('loadVaultList', [subject]);
}

async function loadAgentVaultContent(path) {
  return _agentRoCall('loadVaultContent', [path]);
}

// ============ PROMPTS ============
// AR03-G05:「设置」页提示词文件浏览器（#promptPanel）的**全部业务实现与唯一
// 会话状态**已迁至 static/modules/prompts/index.js（真实生产 ESM owner）。
// 此处**只**保留最薄 classic facade：
//   - 唯一共享的 ESM import promise（并发调用不会重复加载；加载失败清缓存重试）；
//   - 依赖注入 api / toast / showModal / closeModal / escapeHtml：ESM 侧不新建
//     独立 client、不读真实 filesystem、不引入全局事件总线；
//   - 最小代际（generation）防过期：列表与正文请求各领一个号，旧一代响应到达后
//     不再写 DOM（较新的用户选择获胜）；
//   - 旧函数名全部保留，src/index.html 的经典 onclick 与 app.js 内的
//     addEventListener 调用点无需改动。
// promptFiles / promptCurrentContent / promptOriginalContent / promptSelectedName /
// promptEditMode / 待保存内容由 ESM owner 持有**唯一一份**，classic 层不镜像。
var _promptsOwnerPromise = null;
var _promptsOwner = null;
var _promptsListGeneration = 0;
var _promptsContentGeneration = 0;

function _loadPromptsOwner() {
  if (!_promptsOwnerPromise) {
    _promptsOwnerPromise = import('/static/modules/prompts/index.js')
      .then(function (m) {
        _promptsOwner = m.createPromptsOwner({
          api: api,
          toast: toast,
          showModal: showModal,
          closeModal: closeModal,
          escapeHtml: escapeHtml
        });
        return _promptsOwner;
      })
      .catch(function (err) {
        _promptsOwnerPromise = null;
        throw err;
      });
  }
  return _promptsOwnerPromise;
}

function _promptsCall(method, args) {
  return _loadPromptsOwner().then(function (owner) {
    return owner[method].apply(owner, args || []);
  }).catch(function (err) {
    console.error('[prompts] ' + method, err);
  });
}

async function loadPromptList() {
  var generation = ++_promptsListGeneration;
  try {
    var owner = await _loadPromptsOwner();
    if (generation !== _promptsListGeneration) return;
    await owner.loadPromptList();
  } catch (e) {
    console.error('[prompts] loadPromptList', e);
  }
}

async function loadPromptContent(name, el) {
  var generation = ++_promptsContentGeneration;
  try {
    var owner = await _loadPromptsOwner();
    if (generation !== _promptsContentGeneration) return;
    await owner.loadPromptContent(name, el);
  } catch (e) {
    console.error('[prompts] loadPromptContent', e);
  }
}

function setPromptEditMode(on) { _promptsCall('setPromptEditMode', [on]); }
async function computePromptDiff(oldText, newText) {
  try {
    var owner = await _loadPromptsOwner();
    return owner.computePromptDiff(oldText, newText);
  } catch (e) {
    console.error('[prompts] computePromptDiff', e);
    return { added: 0, removed: 0, changed: 0, lines: [] };
  }
}
function enterPromptEdit() { _promptsCall('enterPromptEdit'); }
function cancelPromptEdit() { _promptsCall('cancelPromptEdit'); }
function previewPromptDiff() { _promptsCall('previewPromptDiff'); }
function cancelPromptDiffModal() { _promptsCall('cancelPromptDiffModal'); }
async function confirmPromptSave() { await _promptsCall('confirmPromptSave'); }
async function restorePromptLatest() { await _promptsCall('restorePromptLatest'); }
async function refreshPromptBackupStatus() { await _promptsCall('refreshPromptBackupStatus'); }
function copyPromptContent() { _promptsCall('copyPromptContent'); }

// 共享的严格 HTML 转义（app.js 其它模块与 ESM owner 共用同一实现）。
function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
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
// AR03-G09：「日程」页「今日状态评估」面板与模态的**全部业务实现与唯一
// 业务状态**（assessmentQuestions / assessmentAnswers / TONE_LABELS /
// formatAssessmentScore）已迁至 static/modules/state-assessment/index.js
// （真实生产 ESM owner）。
// 此处**只**保留最薄 classic facade：
//   - 唯一共享的 ESM import promise（并发调用不会重复加载；加载失败清缓存重试）；
//   - 依赖注入 api / toast / showModal / closeModal：ESM 侧不新建独立
//     client、不创建全局 Store 或事件总线；
//   - 旧函数名全部保留（loadStateAssessmentPanel / openStateAssessmentModal /
//     saveStateAssessment / closeStateAssessmentModal），app.js 内的
//     addEventListener 调用点与启动调用无需改动；
//   - classic 层**不再**持有第二份题目 / 答案状态，也不直连 /api/state/*。
var _stateAssessmentOwnerPromise = null;
var _stateAssessmentOwner = null;

function _loadStateAssessmentOwner() {
  if (!_stateAssessmentOwnerPromise) {
    _stateAssessmentOwnerPromise = import('/static/modules/state-assessment/index.js')
      .then(function (m) {
        _stateAssessmentOwner = m.createStateAssessmentOwner({
          api: api,
          toast: toast,
          showModal: showModal,
          closeModal: closeModal
        });
        return _stateAssessmentOwner;
      })
      .catch(function (err) {
        _stateAssessmentOwnerPromise = null;
        throw err;
      });
  }
  return _stateAssessmentOwnerPromise;
}

function _stateAssessmentCall(method, args) {
  return _loadStateAssessmentOwner().then(function (owner) {
    return owner[method].apply(owner, args || []);
  }).catch(function (err) {
    console.error('[state-assessment] ' + method, err);
  });
}

function loadStateAssessmentPanel() {
  return _stateAssessmentCall('loadPanel');
}

function openStateAssessmentModal() {
  return _stateAssessmentCall('openModal');
}

function saveStateAssessment() {
  return _stateAssessmentCall('save');
}

function closeStateAssessmentModal() {
  return _stateAssessmentCall('closeModal');
}

// ============ TIMER ============
// AR03-G08：计时状态与计时生命周期的唯一所有者是 ESM timer owner
// （static/modules/timer/index.js）。这里 **不再** 声明任何会话 / 暂停 /
// interval 副本，也不直连计时接口。

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

// AR03-G04 / AR03-G08：任务页计时 DOM 呈现委托 ESM timer owner
// （owner 内部再调用 static/modules/timer/presentation.js）。
// app.js 只保留最薄 classic facade：状态一律来自 owner 快照。
async function updateTimerDisplay() {
  try {
    var owner = await _getTimerOwner();
    owner.updatePanel();
  } catch (e) {
    console.error('[timer] updateTimerDisplay', e);
  }
}

async function loadTimerPanel() {
  populateTimerTaskSelect();
  var statusEl = document.getElementById('timerStatusText');
  if (statusEl) statusEl.textContent = '加载中...';
  try {
    var owner = await _getTimerOwner();
    // AR03-G08：任务页与 Dock 共享 **同一** 活动 session（唯一状态源）。
    await owner.loadActive();
    owner.updatePanel();
    owner.startPanelTick();
  } catch (e) {
    if (_timerOwner) _timerOwner.clear();
    _refreshTimerViews();
    toast(e.message || '计时器状态加载失败', 'err');
  }
}

async function startTimer() {
  var snap = _timerSnapshot();
  if (snap.session) {
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
    // AR03-G08：启动计时统一经 ESM timer owner（唯一生命周期所有者）。
    var owner = await _getTimerOwner();
    await owner.startSession({
      taskId: taskId,
      plannedMinutes: minutes,
      taskName: function (id) { return taskNameById(id); }
    });
    _refreshTimerViews();
    toast('计时已开始', 'suc');
  } catch (e) {
    toast(e.message || '开始计时失败', 'err');
  }
}

async function stopTimer() {
  var snap = _timerSnapshot();
  if (!snap.session || !snap.session.id) {
    toast('当前无进行中的计时', 'err');
    return;
  }
  showModal('timerOutcomeModal');
}

async function handleTimerOutcome(outcome) {
  closeModal('timerOutcomeModal');
  var owner = null;
  try {
    owner = await _getTimerOwner();
  } catch (e) {
    toast('计时模块加载失败，停止计时失败', 'err');
    return;
  }
  var snap = owner.getSnapshot();
  if (!snap.session || !snap.session.id) return;

  var session = snap.session;
  // P3-Bug-A：实际分钟数由 owner 统一计算（考虑暂停时间，下限 1）。
  var actualMinutes = owner.getActualMinutes();
  var planned = session.planned_minutes || 30;
  var timerResult = outcome === 'completed' ? 'completed' : 'abandoned';

  try {
    await owner.completeSession({
      sessionId: session.id,
      actualMinutes: actualMinutes,
      result: timerResult,
      reason: outcome
    });
    owner.stopInlineTimer();
    _refreshTimerViews();
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

// classic 层不再保留第二份实现，也不再直连睡眠状态类接口。

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
