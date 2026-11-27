// static/modules/free-card/index.js - AR03-P3-A 自由卡 ESM 业务 owner
//
// 自由卡接受 / 结束全流程的 **唯一业务 owner**：
//   - 接受表单的草稿（activity / reason）与「帮我选」建议；
//   - 结束表单的草稿（是否顺利 / 是否中断 / 实际活动 / 原因）；
//   - 提交进行中标记（防重入）与补偿状态。
//
// 依赖注入（owner 内 **不** 偷查 window）：
//   api / toast / escapeHtml / normalizeCardType
//   getDrawnTask（查当前卡对象）
//   getTimerOwner（唯一计时事实源）
//   timerSnapshot / refreshTimerViews / startInlineTimer
//   getActionsCache / setActionsCache（卡片操作栏快照）
//   onReturnToGacha（回到统一抽卡链）
//
// 语义保护（与迁移前 static/app.js 逐条一致，**不改产品行为**）：
//   - resolveFreeCardMinutes：free_card_dispatchable === true 且
//     effective_minutes ∈ {25, 55}，否则 null（fail closed）；
//   - normalizeFreeCardInputs：trim / 长度上限 200 / 控制字符拒绝 /
//     理由缺省 = 产品约定的缺省理由；
//   - suggestFreeCardActivity：只读 GET /api/gacha/free-card/suggestion，
//     **只** 填活动输入框，**不** 自动提交 / **不** 启动计时 / **不** 改理由；
//     失败保留用户输入；
//   - openFreeCardAcceptForm：DOM API 构建（value 走属性赋值，绝不拼进
//     innerHTML / inline JS）；无批准时长 → 显示不可执行提示 + 返回按钮，
//     **不** 显示开始路径；
//   - submitFreeCardAccept：**先** 启动计时（经 timer owner），**再** 写
//     accept 事件；失败走 compensateFreeCardAcceptFailure 补偿，
//     **绝不** 留下半完成状态；
//   - submitFreeCardEnd：先按用户选择停止计时，再写既有反馈事件；
//     中断绝不记为已完成；停止失败 → 保留现状，绝不写反馈。
//
// 边界约束：
//   - 只 import `./` 同目录文件 + `../timer/index.js` / `../gacha/index.js`
//     的 **公共入口**（不 import 它们的内部文件）；
//   - 不新建第二份计时状态 —— 一切计时读写经 timer owner 快照 / 方法。

// ---------------------------------------------------------------------------
// 常量（与迁移前 app.js 逐字一致）
// ---------------------------------------------------------------------------

var FREE_CARD_MINUTES_OPTIONS = [25, 55];
var FREE_CARD_DEFAULT_REASON = '没有什么理由，我就是想。';
var FREE_CARD_MAX_ACTIVITY_LENGTH = 200;

//: 接受表单的 DOM id 前缀（同一张卡片内展开，不新建页面）。
var FREE_CARD_FORM_ID_PREFIX = 'freeCardAcceptForm_';

//: 结束反馈表单的 DOM id 前缀。
var FREE_CARD_END_FORM_ID_PREFIX = 'freeCardEndForm_';

/**
 * 从卡对象解析本次发行的合法自由卡时长；非法 / 缺失 → null（fail closed）。
 * @param {Object} task
 * @returns {number|null}
 */
export function resolveFreeCardMinutes(task) {
  if (!task || typeof task !== 'object') return null;
  if (task.free_card_dispatchable !== true) return null;
  var raw = task.effective_minutes;
  if (typeof raw !== 'number' || !isFinite(raw)) return null;
  if (Math.floor(raw) !== raw) return null;
  if (FREE_CARD_MINUTES_OPTIONS.indexOf(raw) < 0) return null;
  return raw;
}

/**
 * 校验 / 规范化用户输入的活动与理由（与后端规则一致的前端预检）。
 * @param {string} activity
 * @param {string} reason
 * @returns {{ok: boolean, error: string|null, activity: string, reason: string}}
 */
export function normalizeFreeCardInputs(activity, reason) {
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

/**
 * 创建自由卡 owner 实例。
 * @param {Object} deps 注入依赖（见文件头说明）
 */
export function createFreeCardOwner(deps) {
  var d = deps || {};

  var api = typeof d.api === 'function' ? d.api : null;
  var toast = typeof d.toast === 'function' ? d.toast : function () {};
  var escapeHtml = typeof d.escapeHtml === 'function'
    ? d.escapeHtml
    : function (s) { return String(s == null ? '' : s); };
  var normalizeCardType = typeof d.normalizeCardType === 'function'
    ? d.normalizeCardType
    : function () { return 'standard'; };
  var documentRef = d.documentRef || (typeof document !== 'undefined' ? document : null);

  var getDrawnTask = typeof d.getDrawnTask === 'function'
    ? d.getDrawnTask
    : function () { return null; };
  var getTimerOwner = typeof d.getTimerOwner === 'function'
    ? d.getTimerOwner
    : function () { return Promise.resolve(null); };
  var timerSnapshot = typeof d.timerSnapshot === 'function'
    ? d.timerSnapshot
    : function () { return { session: null, paused: false, pausedElapsedMs: 0 }; };
  var refreshTimerViews = typeof d.refreshTimerViews === 'function'
    ? d.refreshTimerViews
    : function () {};
  var startInlineTimer = typeof d.startInlineTimer === 'function'
    ? d.startInlineTimer
    : function () {};
  var getActionsCache = typeof d.getActionsCache === 'function'
    ? d.getActionsCache
    : function () { return null; };
  var setActionsCache = typeof d.setActionsCache === 'function'
    ? d.setActionsCache
    : function () {};
  var onReturnToGacha = typeof d.onReturnToGacha === 'function'
    ? d.onReturnToGacha
    : function () {};

  // ---- 唯一可变状态（闭包私有）------------------------------------------
  var pendingAcceptId = null;        // 正在提交的自由卡接受（防重入）
  var pendingEndId = null;           // 正在提交的自由卡结束反馈（防重入）
  var acceptedActivities = {};       // 接受时填写的活动（结束反馈的可编辑预填）
  var endState = {};                 // 结束反馈的表单状态（按 taskId 存）
  var actionsCache = {};             // 每张已渲染卡片的操作栏 HTML 快照

  function requireApi() {
    if (!api) throw new Error('自由卡 owner 缺少 api 依赖');
    return api;
  }

  function numericTaskId(taskId) {
    var numericId = (typeof taskId === 'number') ? taskId : parseInt(taskId, 10);
    if (!isFinite(numericId) || numericId <= 0) return null;
    return numericId;
  }

  function findCard(numericId) {
    if (!documentRef) return null;
    return documentRef.querySelector(
      '.task-card.drawn-card[data-task-id="' + numericId + '"]'
    );
  }

  function findRightPanel(numericId) {
    var card = findCard(numericId);
    if (!card) return null;
    return card.querySelector('.drawn-card-right-panel');
  }

  // ---- 操作栏快照（取消接受时原样恢复）---------------------------------
  function cacheCardActions(numericId, html) {
    var external = getActionsCache(numericId);
    if (typeof external === 'string') {
      actionsCache[numericId] = external;
      return;
    }
    actionsCache[numericId] = html;
    setActionsCache(numericId, html);
  }

  function readCachedActions(numericId) {
    var external = getActionsCache(numericId);
    if (typeof external === 'string') return external;
    var local = actionsCache[numericId];
    return typeof local === 'string' ? local : null;
  }

  // ---- 卡型判定（沿用既有规则，不发明新的识别规则）----------------------
  /**
   * 是否是正式自由卡。
   * @param {Object} task
   * @returns {boolean}
   */
  function isFreeCardTask(task) {
    return !!task && normalizeCardType(task.task_type) === 'free';
  }

  // ---- 「帮我选」（只读建议）-------------------------------------------
  /**
   * 调用只读接口 GET /api/gacha/free-card/suggestion，把返回的 **一条**
   * 建议填进活动输入框。
   *
   * 硬约束：
   * - 只读、**无模型 API**（后端只从已批准策略的候选池里取一条）；
   * 成功时 **只** 填活动输入框：**不** 自动提交、**不** 启动计时、
   *   **不** 改理由输入框；
   * - 失败 → **保留** 用户当前输入与理由。
   *
   * @param {number|string} taskId
   */
  async function suggestFreeCardActivity(taskId) {
    var numericId = numericTaskId(taskId);
    if (numericId === null) return;

    var formId = FREE_CARD_FORM_ID_PREFIX + numericId;
    var activityEl = documentRef ? documentRef.getElementById(formId + '_activity') : null;

    var data = null;
    try {
      data = await requireApi()('/api/gacha/free-card/suggestion', { method: 'GET' });
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

  // ---- 接受表单 ---------------------------------------------------------
  /**
   * 在 **同一张卡片** 内渲染自由卡接受表单。
   *
   * 活动 / 理由输入框用 **DOM API** 创建（value 通过属性赋值，绝不拼进
   * inline JS 或未转义 HTML）。
   * @param {number|string} taskId
   * @param {Object} [values] 失败后 **原样保留** 用户已填内容
   */
  function openFreeCardAcceptForm(taskId, values) {
    var numericId = numericTaskId(taskId);
    if (numericId === null) {
      toast('任务不存在', 'err');
      return;
    }
    if (!documentRef) return;
    var rightPanel = findRightPanel(numericId);
    if (!rightPanel) {
      toast('请先抽一张卡牌', 'err');
      return;
    }

    var task = getDrawnTask(numericId);
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
    var box = documentRef.createElement('div');
    box.className = 'free-card-accept-form';

    var intro = documentRef.createElement('div');
    intro.style.cssText = 'font-size:.76rem;color:var(--text-secondary);margin-bottom:6px';
    intro.textContent = '接受这张自由卡，本次时长 ' + minutes + ' 分钟。';
    box.appendChild(intro);

    var activityLabel = documentRef.createElement('label');
    activityLabel.setAttribute('for', formId + '_activity');
    activityLabel.style.cssText = 'font-size:.72rem;color:var(--text-muted);display:block;margin-bottom:3px';
    activityLabel.textContent = '接下来做什么（必填，最多 200 字）';
    box.appendChild(activityLabel);

    var activityInput = documentRef.createElement('input');
    activityInput.setAttribute('type', 'text');
    activityInput.setAttribute('id', formId + '_activity');
    activityInput.setAttribute('maxlength', String(FREE_CARD_MAX_ACTIVITY_LENGTH));
    activityInput.setAttribute('placeholder', '例如：看 20 分钟纪录片');
    activityInput.style.cssText = 'flex:1;min-width:0;padding:6px;border-radius:8px;border:1px solid var(--card-border);background:rgba(0,0,0,0.25);color:var(--text-primary)';
    if (prior && typeof prior.activity === 'string') activityInput.value = prior.activity;

    // 「帮我选」：一次点击即得 **一个** 具体活动建议。
    // 只调用现有只读接口 GET /api/gacha/free-card/suggestion；**无模型 API**、
    // 不发行卡、不写库；成功时 **只** 填活动输入框。
    var activityRow = documentRef.createElement('div');
    activityRow.style.cssText = 'display:flex;gap:6px;align-items:center;margin-bottom:6px';
    activityRow.appendChild(activityInput);

    var suggestBtn = documentRef.createElement('button');
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

    var reasonLabel = documentRef.createElement('label');
    reasonLabel.setAttribute('for', formId + '_reason');
    reasonLabel.style.cssText = 'font-size:.72rem;color:var(--text-muted);display:block;margin-bottom:3px';
    reasonLabel.textContent = '理由（可编辑）';
    box.appendChild(reasonLabel);

    var reasonInput = documentRef.createElement('input');
    reasonInput.setAttribute('type', 'text');
    reasonInput.setAttribute('id', formId + '_reason');
    reasonInput.setAttribute('maxlength', String(FREE_CARD_MAX_ACTIVITY_LENGTH));
    reasonInput.style.cssText = 'width:100%;margin-bottom:6px;padding:6px;border-radius:8px;border:1px solid var(--card-border);background:rgba(0,0,0,0.25);color:var(--text-primary)';
    // 默认值精确为产品约定的缺省理由（通过 DOM 属性赋值，不是 HTML 拼接）。
    reasonInput.value = (prior && typeof prior.reason === 'string' && prior.reason)
      ? prior.reason
      : FREE_CARD_DEFAULT_REASON;
    box.appendChild(reasonInput);

    var reminder = documentRef.createElement('div');
    reminder.style.cssText = 'font-size:.7rem;color:var(--text-muted);line-height:1.4;margin-bottom:8px';
    reminder.textContent = '开始后请同时为手机手动设置计时器；网页计时不应替代手机提醒。';
    box.appendChild(reminder);

    var startBtn = documentRef.createElement('button');
    startBtn.className = 'btn pri';
    startBtn.style.cssText = 'width:100%;margin-bottom:6px';
    startBtn.textContent = '开始';
    startBtn.addEventListener('click', function () { submitFreeCardAccept(numericId); });
    box.appendChild(startBtn);

    var cancelBtn = documentRef.createElement('button');
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

  /**
   * 取消接受 → 恢复卡片操作。
   * @param {number|string} taskId
   */
  function cancelFreeCardAcceptForm(taskId) {
    var numericId = numericTaskId(taskId);
    if (numericId === null) return;
    if (!documentRef) return;
    var rightPanel = findRightPanel(numericId);
    if (!rightPanel) return;
    // 原样恢复该卡渲染时的操作栏（保持既有按钮与行为逐字不变）。
    var cached = readCachedActions(numericId);
    if (typeof cached === 'string') {
      rightPanel.innerHTML = cached;
    }
  }

  // ---- 补偿（接受事件写入失败）-----------------------------------------
  /**
   * 接受事件写入失败 → 尽力结束刚创建的计时 session，绝不留下
   * 「静默运行且没有活动记录」的计时器。
   * @param {number} taskId
   * @param {number|string|null} sessionId
   */
  async function compensateFreeCardAcceptFailure(taskId, sessionId) {
    var sid = sessionId;
    if (sid === null || sid === undefined) {
      var snap = timerSnapshot();
      sid = snap.session ? snap.session.id : null;
    }
    if (sid === null || sid === undefined) return;
    try {
      var owner = await getTimerOwner();
      if (!owner) return;
      await owner.completeSession({
        sessionId: sid,
        actualMinutes: 1,
        result: 'abandoned',
        reason: 'free_card_acceptance_event_failed'
      });
      owner.stopInlineTimer();
      refreshTimerViews();
    } catch (e) {
      toast('计时状态可能仍需你手动处理（自动结束失败）', 'err');
    }
  }

  // ---- 提交接受 ---------------------------------------------------------
  /**
   * 提交自由卡接受：启动既有计时器 + 写 accept_task 事件。
   *
   * 顺序严格为「**先** 启动计时，**再** 写 accept 事件」；写事件失败 →
   * 补偿（尽力结束计时）并保留用户输入，绝不留下半完成状态。
   * @param {number|string} taskId
   */
  async function submitFreeCardAccept(taskId) {
    var numericId = numericTaskId(taskId);
    if (numericId === null) {
      toast('任务不存在', 'err');
      return;
    }
    if (pendingAcceptId === numericId) return;
    pendingAcceptId = numericId;

    var task = getDrawnTask(numericId);
    if (!task) {
      pendingAcceptId = null;
      toast('任务不存在', 'err');
      return;
    }
    var minutes = resolveFreeCardMinutes(task);
    if (minutes === null) {
      pendingAcceptId = null;
      toast('这张自由卡本次没有已批准的可执行时长，无法开始', 'err');
      return;
    }

    var formId = FREE_CARD_FORM_ID_PREFIX + numericId;
    var activityEl = documentRef ? documentRef.getElementById(formId + '_activity') : null;
    var reasonEl = documentRef ? documentRef.getElementById(formId + '_reason') : null;
    var activityRaw = activityEl ? activityEl.value : '';
    var reasonRaw = reasonEl ? reasonEl.value : '';

    var normalized = normalizeFreeCardInputs(activityRaw, reasonRaw);
    if (!normalized.ok) {
      pendingAcceptId = null;
      toast(normalized.error, 'err');
      return;
    }

    var rightPanel = findRightPanel(numericId);

    // 计时启动统一经 ESM timer owner（唯一计时生命周期所有者）。
    // 自由卡接受路径启用 **严格 session_id 校验**。
    var owner = null;
    try {
      owner = await getTimerOwner();
    } catch (e) {
      pendingAcceptId = null;
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
      pendingAcceptId = null;
      toast(e.message || '启动计时失败', 'err');
      return;
    }

    // === 严格规范 session_id ============================================
    // timer/start 已经成功返回，但 session_id 缺失 / 非法时：
    //   - 绝不向计时完成接口发送无效 ID；
    //   - 绝不设置活动 session（owner 也绝不设置）；
    //   - 绝不启动内嵌计时器、绝不显示"执行中"状态；
    //   - 绝不声称"已停止"；
    //   - 显示明确警告，并保留活动 / 理由供用户恢复。
    if (!started || !started.ok) {
      pendingAcceptId = null;
      openFreeCardAcceptForm(numericId, { activity: normalized.activity, reason: normalized.reason });
      toast('无法确认计时已停止，请检查计时状态/必要时手动处理。你的活动与理由已保留。', 'err');
      return;
    }
    var sessionId = started.session ? started.session.id : null;

    // 计时已启动 → 复用既有内嵌计时流程（owner 持有唯一 session）。
    refreshTimerViews();
    startInlineTimer(numericId);

    // 记住本次接受时填写的活动 → 结束反馈的 **可编辑预填**。
    acceptedActivities[numericId] = normalized.activity;

    // 右侧执行状态显示用户填写的活动。
    if (rightPanel) {
      // 自由卡的结束按钮走"结束并记录反馈"（先问清楚，再停止计时、再写事件）；
      // 普通/微型/目标卡保持"确认完成任务"不变。
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
      await requireApi()('/api/task-feedback', {
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
      pendingAcceptId = null;
      return;
    }
    pendingAcceptId = null;
    toast('计时已开始，请同时为手机设置计时器！', 'suc');
  }

  // ---- 结束反馈 ---------------------------------------------------------
  /**
   * 在 **同一张卡片** 内展开「结束反馈」表单（不新建页面）。
   *
   * 是否顺利 / 是否被中断 **默认都不选中**：绝不替用户选择"顺利"。
   * @param {number|string} taskId
   */
  function openFreeCardEndForm(taskId) {
    var numericId = numericTaskId(taskId);
    if (numericId === null) {
      toast('任务不存在', 'err');
      return;
    }
    if (!documentRef) return;
    var rightPanel = findRightPanel(numericId);
    if (!rightPanel) {
      toast('请先抽一张卡牌', 'err');
      return;
    }

    var formId = FREE_CARD_END_FORM_ID_PREFIX + numericId;
    // 记住当前面板（取消时原样恢复"执行中"面板，计时继续走）。
    // 只记第一次：再次打开（保存失败后重试）时 **不** 覆盖成表单本身。
    var state = endState[numericId] || {};
    if (typeof state.panelHtml !== 'string') {
      state.panelHtml = rightPanel.innerHTML;
    }
    endState[numericId] = state;

    rightPanel.innerHTML = '';

    // 运行状态（保留计时显示：打开表单 **不代表** 计时已停止）。
    var running = documentRef.createElement('div');
    running.style.cssText = 'text-align:center;margin-bottom:8px';
    var runningText = documentRef.createElement('div');
    runningText.style.cssText = 'font-size:.78rem;color:var(--text-secondary);margin-bottom:4px';
    runningText.textContent = '执行中...';
    running.appendChild(runningText);
    var timerDisplay = documentRef.createElement('div');
    timerDisplay.className = 'card-timer-display';
    timerDisplay.style.cssText = 'font-family:var(--font-heading);font-size:1.3rem;color:var(--gold);margin-bottom:6px';
    timerDisplay.textContent = '00:00';
    running.appendChild(timerDisplay);
    rightPanel.appendChild(running);

    var box = documentRef.createElement('div');
    box.className = 'free-card-end-form';

    var intro = documentRef.createElement('div');
    intro.style.cssText = 'font-size:.76rem;color:var(--text-secondary);margin-bottom:6px';
    intro.textContent = '结束这张自由卡了？如实记一下，保存成功后才算数。';
    box.appendChild(intro);

    var outcomeLabel = documentRef.createElement('div');
    outcomeLabel.style.cssText = 'font-size:.72rem;color:var(--text-muted);margin-bottom:3px';
    outcomeLabel.textContent = '这次是否顺利（必选，二选一）';
    box.appendChild(outcomeLabel);

    var smoothInput = documentRef.createElement('input');
    smoothInput.setAttribute('type', 'radio');
    smoothInput.setAttribute('name', 'freeCardEndOutcome_' + numericId);
    smoothInput.setAttribute('id', formId + '_smooth');
    smoothInput.setAttribute('value', 'smooth');
    var smoothLabel = documentRef.createElement('label');
    smoothLabel.setAttribute('for', formId + '_smooth');
    smoothLabel.style.cssText = 'font-size:.78rem;display:flex;gap:6px;align-items:center;margin-bottom:4px';
    var smoothText = documentRef.createElement('span');
    smoothText.textContent = '顺利完成了';
    smoothLabel.appendChild(smoothInput);
    smoothLabel.appendChild(smoothText);
    box.appendChild(smoothLabel);

    var interruptedInput = documentRef.createElement('input');
    interruptedInput.setAttribute('type', 'radio');
    interruptedInput.setAttribute('name', 'freeCardEndOutcome_' + numericId);
    interruptedInput.setAttribute('id', formId + '_interrupted');
    interruptedInput.setAttribute('value', 'interrupted');
    var interruptedLabel = documentRef.createElement('label');
    interruptedLabel.setAttribute('for', formId + '_interrupted');
    interruptedLabel.style.cssText = 'font-size:.78rem;display:flex;gap:6px;align-items:center;margin-bottom:6px';
    var interruptedText = documentRef.createElement('span');
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

    var activityLabel = documentRef.createElement('label');
    activityLabel.setAttribute('for', formId + '_activity');
    activityLabel.style.cssText = 'font-size:.72rem;color:var(--text-muted);display:block;margin-bottom:3px';
    activityLabel.textContent = '实际做了什么（必填，可修改）';
    box.appendChild(activityLabel);

    var activityInput = documentRef.createElement('input');
    activityInput.setAttribute('type', 'text');
    activityInput.setAttribute('id', formId + '_activity');
    activityInput.setAttribute('maxlength', String(FREE_CARD_MAX_ACTIVITY_LENGTH));
    activityInput.setAttribute('placeholder', '例如：看了一集纪录片');
    activityInput.style.cssText = 'width:100%;margin-bottom:6px;padding:6px;border-radius:8px;border:1px solid var(--card-border);background:rgba(0,0,0,0.25);color:var(--text-primary)';
    // 可编辑预填：接受时填写的活动（没有就留空，**绝不** 编造事实）。
    var priorActivity = acceptedActivities[numericId];
    if (typeof priorActivity === 'string' && priorActivity) activityInput.value = priorActivity;
    box.appendChild(activityInput);

    var reasonLabel = documentRef.createElement('label');
    reasonLabel.setAttribute('for', formId + '_reason');
    reasonLabel.style.cssText = 'font-size:.72rem;color:var(--text-muted);display:block;margin-bottom:3px';
    reasonLabel.textContent = '原因（可选）';
    box.appendChild(reasonLabel);

    var reasonInput = documentRef.createElement('input');
    reasonInput.setAttribute('type', 'text');
    reasonInput.setAttribute('id', formId + '_reason');
    reasonInput.setAttribute('maxlength', String(FREE_CARD_MAX_ACTIVITY_LENGTH));
    reasonInput.setAttribute('placeholder', '例如：手机响了');
    reasonInput.style.cssText = 'width:100%;margin-bottom:6px;padding:6px;border-radius:8px;border:1px solid var(--card-border);background:rgba(0,0,0,0.25);color:var(--text-primary)';
    box.appendChild(reasonInput);

    var saveBtn = documentRef.createElement('button');
    saveBtn.className = 'btn pri';
    saveBtn.setAttribute('id', formId + '_save');
    saveBtn.style.cssText = 'width:100%;margin-bottom:6px';
    saveBtn.textContent = '保存反馈';
    saveBtn.addEventListener('click', function () { submitFreeCardEnd(numericId); });
    box.appendChild(saveBtn);

    var cancelBtn = documentRef.createElement('button');
    cancelBtn.className = 'btn';
    cancelBtn.setAttribute('id', formId + '_cancel');
    cancelBtn.style.cssText = 'width:100%';
    cancelBtn.textContent = '取消';
    cancelBtn.addEventListener('click', function () { cancelFreeCardEndForm(numericId); });
    box.appendChild(cancelBtn);

    rightPanel.appendChild(box);
  }

  /**
   * 取消结束反馈：取消 = 没有保存任何反馈，绝不谎报保存成功。
   * @param {number|string} taskId
   */
  function cancelFreeCardEndForm(taskId) {
    var numericId = numericTaskId(taskId);
    if (numericId === null) return;
    var state = endState[numericId] || {};
    if (state.timerStopped) {
      // 计时已经停了 → 表单保留，用户可以再试一次保存。
      toast('已取消保存，本次反馈还没有记录（可以再试一次）', 'inf');
      return;
    }
    var rightPanel = findRightPanel(numericId);
    if (rightPanel && typeof state.panelHtml === 'string') {
      // 原样恢复"执行中"面板（计时没有被停止，任务仍在进行）。
      rightPanel.innerHTML = state.panelHtml;
    }
    delete endState[numericId];
    toast('已取消，本次反馈没有保存', 'inf');
  }

  /**
   * 提交自由卡结束反馈：先按用户的选择停止计时，再写既有反馈事件。
   * @param {number|string} taskId
   */
  async function submitFreeCardEnd(taskId) {
    var numericId = numericTaskId(taskId);
    if (numericId === null) {
      toast('任务不存在', 'err');
      return;
    }
    // 避免重复提交（同一张卡在保存途中不再发起第二次提交）。
    if (pendingEndId === numericId) return;

    var formId = FREE_CARD_END_FORM_ID_PREFIX + numericId;
    var smoothEl = documentRef ? documentRef.getElementById(formId + '_smooth') : null;
    var interruptedEl = documentRef ? documentRef.getElementById(formId + '_interrupted') : null;
    var activityEl = documentRef ? documentRef.getElementById(formId + '_activity') : null;
    var reasonEl = documentRef ? documentRef.getElementById(formId + '_reason') : null;

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

    var state = endState[numericId] || {};
    var planned = state.planned != null ? state.planned : null;
    var actual = state.actual != null ? state.actual : null;

    pendingEndId = numericId;
    try {
      // 停止计时统一经 ESM timer owner（唯一生命周期所有者）。
      var owner = await getTimerOwner();
      if (!owner) {
        toast('计时模块未就绪，反馈没有保存，请重试', 'err');
        return;
      }
      // === 停止计时（结果跟随用户的选择）===============================
      if (!state.timerStopped) {
        var snap = timerSnapshot();
        var session = snap.session;
        if (session && session.id) {
          // 计时属于别的任务 → 绝不动它，也绝不声称"结束成功"。
          if (Number(session.task_id) !== numericId) {
            toast('当前计时属于另一张卡，反馈没有保存，请重试', 'err');
            return;
          }
          // 实际分钟数由 owner 统一计算（暂停时用 pausedElapsedMs，
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
          endState[numericId] = state;
          // 计时已停 → 锁定结论（重试时结论不会与计时状态相矛盾）。
          if (smoothEl) smoothEl.disabled = true;
          if (interruptedEl) interruptedEl.disabled = true;
          owner.stopInlineTimer();
          refreshTimerViews();
        } else {
          // 没有进行中的计时（例如计时早已被停掉）：不重复停止，
          // 直接进入"写反馈"阶段。
          state.timerStopped = true;
          state.outcome = outcome;
          endState[numericId] = state;
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
          await requireApi()('/api/task-feedback', {
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
          endState[numericId] = state;
          toast((e.message || '反馈保存失败') + '；已保留你填写的内容，请重试', 'err');
          return;
        }
        state.feedbackSaved = true;
        endState[numericId] = state;
      }

      // === 顺利结束 → 复用既有"任务完成"端点（中断绝不记为已完成）======
      if (outcome === 'smooth' && !state.taskCompleted) {
        try {
          await requireApi()('/api/tasks/' + numericId + '/complete', { method: 'POST' });
          await requireApi()('/api/tasks/' + numericId + '/move-to-discard', { method: 'POST' });
        } catch (e) {
          // 反馈已经保存；任务完成失败 → 如实告知，绝不谎报"全部完成"。
          toast((e.message || '任务完成记录失败') + '；本次反馈已保存', 'err');
          return;
        }
        state.taskCompleted = true;
        endState[numericId] = state;
      }

      delete endState[numericId];
      delete acceptedActivities[numericId];
      toast('已记录这次自由卡的反馈', 'suc');
      onReturnToGacha();
    } finally {
      pendingEndId = null;
    }
  }

  return {
    // --- 接受 ---
    openFreeCardAcceptForm: openFreeCardAcceptForm,
    cancelFreeCardAcceptForm: cancelFreeCardAcceptForm,
    submitFreeCardAccept: submitFreeCardAccept,
    suggestFreeCardActivity: suggestFreeCardActivity,
    compensateFreeCardAcceptFailure: compensateFreeCardAcceptFailure,
    // --- 结束 ---
    openFreeCardEndForm: openFreeCardEndForm,
    cancelFreeCardEndForm: cancelFreeCardEndForm,
    submitFreeCardEnd: submitFreeCardEnd,
    // --- 只读辅助 ---
    isFreeCardTask: isFreeCardTask,
    resolveFreeCardMinutes: resolveFreeCardMinutes,
    normalizeFreeCardInputs: normalizeFreeCardInputs,
    // --- 状态（供 classic facade / 诊断读取）---
    cacheCardActions: cacheCardActions,
    readCachedActions: readCachedActions,
    getAcceptedActivity: function (taskId) {
      var numericId = numericTaskId(taskId);
      if (numericId === null) return null;
      var v = acceptedActivities[numericId];
      return typeof v === 'string' ? v : null;
    },
    setAcceptedActivity: function (taskId, activity) {
      var numericId = numericTaskId(taskId);
      if (numericId === null) return;
      acceptedActivities[numericId] = activity;
    },
    getEndState: function (taskId) {
      var numericId = numericTaskId(taskId);
      if (numericId === null) return null;
      var s = endState[numericId];
      return s ? Object.assign({}, s) : null;
    },
    isAcceptPending: function (taskId) {
      var numericId = numericTaskId(taskId);
      return numericId !== null && pendingAcceptId === numericId;
    },
    isEndPending: function (taskId) {
      var numericId = numericTaskId(taskId);
      return numericId !== null && pendingEndId === numericId;
    }
  };
}

export default {
  createFreeCardOwner: createFreeCardOwner,
  resolveFreeCardMinutes: resolveFreeCardMinutes,
  normalizeFreeCardInputs: normalizeFreeCardInputs
};
