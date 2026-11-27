// static/modules/tasks/lifecycle.js - AR03-G15 真实生产 ESM owner
//
// 拥有「任务生命周期」相关业务的**唯一实现**与**唯一状态**：
//   - startTask(taskId)
//   - confirmComplete(taskId)
//   - completeWithFeedback(id, opts)
//   - 反馈 / 关怀流程：openFeedback / setMood / submitFeedback /
//     cancelFeedback / transitionToCareModal / careSameCategory /
//     careSwitchCategory / careRest
//   - 跳过 / 拒绝（G15.3）：handleSkip / handleRefuse / taskSkip / taskRefuse
//   - owner 闭包私有状态：
//     _pendingStartTaskId（计时启动的幂等锁）、
//     _feedbackContext（反馈上下文）、_pendingFeedbackSubmit（提交幂等锁）、
//     feedbackMood（心情）、_careContext（关怀上下文）。
//
// 边界（与迁移前 classic 层逐条语义一致）：
//   - **不**访问宿主全局对象、**不**访问 DOM、不做任何元素查找或写入；
//     所有 DOM 读写一律经**注入的适配器**完成：
//       readFeedbackEnergy / openFeedbackModalForTask / closeModal /
//       renderFeedbackSuccess / renderCareModal / renderCareRest；
//   - **不**创建 API client / Store / 事件总线 / 缓存 / 第二份 task state；
//   - **不**拥有 Timer / Gacha / free-card / discard /
//     presentation 状态；这些一律由 classic 层或既有 ESM owner 持有，
//     本模块只**注入调用**；
//   - **跳过 / 拒绝（skip / refuse）业务编排已由 classic 层迁入本 owner**：
//     handleSkip / handleRefuse / taskSkip / taskRefuse 的完整编排
//     （换卡链复位 → 反馈 → 业务 API → 动画 → 结果区 → 提示 → 刷新）
//     由本 owner **唯一持有**；classic 层只保留最薄的全局 facade，
//     不再持有任何 skip / refuse 的业务分支、端点、动画类名或提示文案；
//   - 跳过 / 拒绝所需的 DOM / 动画能力一律经**注入的适配器**获得，
//     必要适配器缺失时 **fail closed**（绝不发出业务 API）；
//   - 手动弃牌 / 弃牌列表 / 手动恢复（G15.4）：moveToDiscard /
//     loadDiscardPileList / restoreFromDiscard 的业务编排由本 owner
//     **唯一持有**；classic 层只保留最薄的全局 facade 与列表渲染适配器；
//   - 弃牌堆列表的 DOM 渲染（加载态 / 空态 / 列表 / 错误态）一律经**注入的
//     适配器**完成；owner **不**直接触碰 DOM，也不读取宿主全局；
//   - 手动弃牌的动画适配器、手动恢复的确认适配器均为**必要依赖**，缺失时
//     **fail closed**（绝不发出业务 API）；
//   - Gacha 状态只经三个**只读** getter 读取（allTasks / _currentDrawnTask /
//     multiDrawResults），既不复制也不写入；
//   - Timer 状态仍由既有 Timer ESM owner 拥有（getTimerOwner /
//     getCurrentTimerOwner / startInlineTimer / refreshTimerViews）。
//
// 依赖注入（仅注入实际使用的依赖）：
//   getTasks / getDrawnTask / getMultiDrawResults / getTimerOwner /
//   getCurrentTimerOwner / startInlineTimer / refreshTimerViews /
//   resetReplaceChain / openFreeCardAcceptForm / renderTaskRightPanel /
//   flyDrawnCardToDiscard / loadTasks / refreshGachaStats /
//   updateDiscardPileVisual / openFeedbackModalForTask / readFeedbackEnergy /
//   closeModal / renderFeedbackSuccess / renderCareModal / renderCareRest /
//   api / toast / normalizeCardType / prereqHint / drawGachaWithCategory
//   getTaskFeedbackContext / promptTaskFeedback / playCardAnim /
//   renderDrawnCardResult / renderDiscardPileLoading /
//   renderDiscardPileEmpty / renderDiscardPileItems /
//   renderDiscardPileError / confirmDiscardRestore /
//   getDiscardPileMessage

export function createTaskLifecycleOwner(deps) {
  var d = deps || {};

  function dep(name, fallback) {
    return typeof d[name] === 'function' ? d[name] : fallback;
  }

  var getTasks = dep('getTasks', function () { return []; });
  var getDrawnTask = dep('getDrawnTask', function () { return null; });
  var getMultiDrawResults = dep('getMultiDrawResults', function () { return []; });
  var getTimerOwner = dep('getTimerOwner', function () {
    return Promise.reject(new Error('计时模块加载失败，任务未完成'));
  });
  var getCurrentTimerOwner = dep('getCurrentTimerOwner', function () { return null; });
  var startInlineTimer = dep('startInlineTimer', function () {});
  var refreshTimerViews = dep('refreshTimerViews', function () {});
  var resetReplaceChain = dep('resetReplaceChain', function () {});
  var openFreeCardAcceptForm = dep('openFreeCardAcceptForm', function () {});
  var renderTaskRightPanel = dep('renderTaskRightPanel', function () { return 'PANEL_MISSING'; });
  var flyDrawnCardToDiscard = dep('flyDrawnCardToDiscard', function () { return Promise.resolve(); });
  var loadTasks = dep('loadTasks', function () {});
  var refreshGachaStats = dep('refreshGachaStats', function () {});
  var updateDiscardPileVisual = dep('updateDiscardPileVisual', function () {});
  var openFeedbackModalForTask = dep('openFeedbackModalForTask', function () {});
  var readFeedbackEnergy = dep('readFeedbackEnergy', function () { return '5'; });
  var closeModal = dep('closeModal', function () {});
  var renderFeedbackSuccess = dep('renderFeedbackSuccess', function () {});
  var renderCareModal = dep('renderCareModal', function () {});
  var renderCareRest = dep('renderCareRest', function () {});
  var api = dep('api', function () {
    return Promise.reject(new Error('api 未注入'));
  });
  var toast = dep('toast', function () {});
  var normalizeCardType = dep('normalizeCardType', function () { return 'standard'; });
  var prereqHint = dep('prereqHint', function () { return ''; });
  // 抽卡编排由 Gacha owner 持有；此处只做**晚绑定**注入调用。
  var drawGachaWithCategory = dep('drawGachaWithCategory', function () {});
  // --- G15.3 跳过 / 拒绝：全部经注入适配器，不接触宿主环境 ---
  // 四个适配器都是**必要依赖**：缺失时对应入口 fail closed，绝不发出业务 API。
  // 缺失一律表现为「不是函数」；注入方若提供 isAvailable() 探针（晚绑定场景），
  // 则以探针结果为准。
  var getTaskFeedbackContext = dep('getTaskFeedbackContext', null);
  var promptTaskFeedback = dep('promptTaskFeedback', null);
  var playCardAnim = dep('playCardAnim', null);
  var renderDrawnCardResult = dep('renderDrawnCardResult', null);

  // --- G15.4 弃牌 / 恢复：DOM 与确认能力一律经注入适配器 ---------------
  // 弃牌列表的四个渲染适配器：加载态 / 空态 / 列表 / 错误态。
  // classic 层实现：owner 只负责「取数据 + 判空 + 处理错误」。
  var renderDiscardPileLoading = dep('renderDiscardPileLoading', null);
  var renderDiscardPileEmpty = dep('renderDiscardPileEmpty', null);
  var renderDiscardPileItems = dep('renderDiscardPileItems', null);
  var renderDiscardPileError = dep('renderDiscardPileError', null);
  // 恢复确认适配器（必要依赖）：缺失时 fail closed，绝不 POST。
  var confirmDiscardRestore = dep('confirmDiscardRestore', null);
  // 弃牌提示文案（classic 层 WARM_MESSAGES.discarded 的唯一来源）。
  var getDiscardPileMessage = dep('getDiscardPileMessage', function () {
    return '先放一边，等状态好的时候再试试';
  });

  // 幂等锁：同一 taskId 正在启动计时时，后续调用直接 no-op。
  var _pendingStartTaskId = null;

  // -------------------------------------------------------------------------
  // 反馈 / 关怀业务状态（owner 闭包私有，classic 层不再持有副本）
  // -------------------------------------------------------------------------
  var _feedbackContext = null;      // { taskId, category, finishEarly }
  var _pendingFeedbackSubmit = null; // reentrancy guard: 当前正在 POST 的 taskId
  var feedbackMood = 3;              // 当前心情（1..5）
  var _careContext = null;           // { taskId, category }

  // 与 classic 层 WARM_MESSAGES.unlock 逐字一致的解锁提示文案。
  var UNLOCK_MESSAGE = '恭喜解锁了新任务';

  // 关怀文案与科目标签（逐字保持迁移前的值）。
  var CARE_ENCOURAGES = [
    '太棒了！又完成了一项挑战！',
    '坚持就是胜利，你真棒！',
    '今天的你比昨天更优秀！',
    '小步快跑，大目标在前方等你！',
    '完成就是进步，继续加油！'
  ];

  var CARE_CATEGORY_LABELS = { study: '学习', exercise: '运动', work: '工作', life: '生活', other: '其他' };

  // -------------------------------------------------------------------------
  // 面板 HTML 构建（只产出字符串，绝不接触 DOM）
  // -------------------------------------------------------------------------
  function buildTimerPanelHtml(taskId, planned) {
    return '<div style="text-align:center;margin-bottom:8px">' +
      '<div style="font-size:.78rem;color:var(--text-secondary);margin-bottom:4px">执行中...</div>' +
      '<div class="card-timer-display" style="font-family:var(--font-heading);font-size:1.3rem;color:var(--gold);margin-bottom:6px">00:00</div>' +
      '<div style="font-size:.68rem;color:var(--text-muted)">计划 ' + planned + ' 分</div>' +
      '</div>' +
      '<button class="btn" onclick="pauseInlineTimer(' + taskId + ')" style="width:100%;margin-bottom:6px"><i class="fa-solid fa-pause"></i> 暂停</button>' +
      '<button class="btn pri" onclick="confirmComplete(' + taskId + ')" style="width:100%"><i class="fa-solid fa-check"></i> 确认完成任务</button>';
  }

  function buildStartButtonHtml(taskId) {
    return '<button class="btn pri" onclick="startTask(' + taskId + ')" style="width:100%"><i class="fa-solid fa-play"></i> 开始任务</button>';
  }

  // 任务查找：drawn card → multiDrawResults → allTasks（顺序不变）。
  function findTaskById(numericId) {
    var drawn = getDrawnTask();
    if (drawn && Number(drawn.id) === numericId) return drawn;
    var multi = getMultiDrawResults();
    if (Array.isArray(multi) && multi.length) {
      for (var i = 0; i < multi.length; i += 1) {
        var m = multi[i];
        if (m && Number(m.id) === numericId) return m;
      }
    }
    var tasks = getTasks();
    if (Array.isArray(tasks)) {
      return tasks.find(function (x) { return x.id === numericId; }) || null;
    }
    return null;
  }

  // -------------------------------------------------------------------------
  // startTask
  // -------------------------------------------------------------------------
  async function startTask(taskId) {
    // 只接受正整数 ID；非法输入 toast 后立即返回。
    var numericId = (typeof taskId === 'number') ? taskId : parseInt(taskId, 10);
    if (!isFinite(numericId) || numericId <= 0) {
      toast('任务不存在', 'err');
      return;
    }
    // 同一 ID 正在启动时立即 no-op（幂等锁）。
    if (_pendingStartTaskId === numericId) return;
    _pendingStartTaskId = numericId;
    try {
      var task = findTaskById(numericId);
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

      // 自由卡必须先走接受流程（填写活动 + 理由），绝不允许直接启动计时。
      if (normalizeCardType(task.task_type) === 'free') {
        openFreeCardAcceptForm(numericId);
        return;
      }

      // 计划分钟只接受 1..480 的有限整数，否则使用 30。
      var rawEstimated = Number(task.estimated_time);
      var planned = (isFinite(rawEstimated) && Math.floor(rawEstimated) === rawEstimated
                     && rawEstimated >= 1 && rawEstimated <= 480)
                    ? Math.floor(rawEstimated) : 30;

      // 面板写入交给 classic 适配器；owner 只解释返回状态。
      var renderStatus = renderTaskRightPanel(numericId, buildTimerPanelHtml(numericId, planned));
      if (renderStatus === 'CARD_MISSING') {
        toast('请先抽一张卡牌', 'err');
        return;
      }
      if (renderStatus !== 'RENDERED') {
        // PANEL_MISSING：安全 no-op，不提示、不启动计时。
        return;
      }

      try {
        var owner = await getTimerOwner();
        await owner.startSession({
          taskId: numericId,
          plannedMinutes: planned,
          taskName: task.name
        });
        refreshTimerViews();
        startInlineTimer(numericId);
        toast('计时已开始，加油！', 'suc');
      } catch (e) {
        toast((e && e.message) || '启动计时失败', 'err');
        // 恢复「开始任务」按钮，允许用户重试。
        renderTaskRightPanel(numericId, buildStartButtonHtml(numericId));
      }
    } finally {
      _pendingStartTaskId = null;
    }
  }

  // -------------------------------------------------------------------------
  // confirmComplete
  // -------------------------------------------------------------------------
  async function confirmComplete(taskId) {
    // 先停止计时器；计时失败时**不**完成任务、不清 session。
    var owner = null;
    try {
      owner = await getTimerOwner();
    } catch (e) {
      toast('计时模块加载失败，任务未完成', 'err');
      return;
    }
    var snap = owner.getSnapshot();
    if (snap.session && snap.session.id) {
      // 实际分钟数由 owner 统一计算（暂停时用 pausedElapsedMs）。
      var actualMin = owner.getActualMinutes();
      try {
        await owner.completeSession({
          sessionId: snap.session.id,
          actualMinutes: actualMin,
          result: 'completed'
        });
      } catch (e) {
        // API 失败 → 不重置 dock、不完成任务、不弃牌；保留现有计时状态让用户重试。
        toast((e && e.message) || '停止计时失败，任务未完成', 'err');
        return;
      }
    }
    // API 成功（或无计时器）→ 清理 dock 状态，走任务完成/弃牌流程。
    owner.stopInlineTimer();
    refreshTimerViews();
    await completeWithFeedback(taskId);
  }

  // -------------------------------------------------------------------------
  // completeWithFeedback
  // -------------------------------------------------------------------------
  async function completeWithFeedback(id, opts) {
    opts = opts || {};
    var finishEarly = !!opts.finishEarly;
    var tasks = getTasks();
    var list = Array.isArray(tasks) ? tasks : [];
    var task = list.find(function (x) { return x.id === id; }) || null;
    if (task && !task.is_unlocked) {
      toast(prereqHint(task) || '任务被前置依赖阻塞', 'err');
      return;
    }

    try {
      var r = await api('/api/tasks/' + id + '/complete', { method: 'POST' });
      if (r && r.unlocked_tasks && r.unlocked_tasks.length) {
        toast(UNLOCK_MESSAGE + ': ' + r.unlocked_tasks.join('、'), 'suc');
      }

      // 卡牌飞向弃牌堆（classic 适配器负责查找卡片与动画）。
      await flyDrawnCardToDiscard(id);

      // 先将任务放入弃牌堆，再标记完成。
      await api('/api/tasks/' + id + '/move-to-discard', { method: 'POST' });

      // 完成清理在反馈关闭后再做（由反馈 / 关怀流程接手）。
      loadTasks();
      refreshGachaStats();
      updateDiscardPileVisual();
      // 清空唯一计时状态（owner 持有），并同步两处计时 UI。
      var current = getCurrentTimerOwner();
      if (current) {
        current.clear();
        current.stopInlineTimer();
      }
      refreshTimerViews();

      // 反馈上下文由 owner 持有；DOM 适配器只负责写表单初值。
      openFeedback(id, task ? task.category : null, finishEarly);
    } catch (e) {
      toast((e && e.message) || '完成失败', 'err');
    }
  }

  // -------------------------------------------------------------------------
  // 反馈流程（owner 持有状态与业务编排）
  // -------------------------------------------------------------------------

  // 打开反馈：先存上下文 / 复位心情 / 清 pending 锁，再调用 DOM 适配器。
  function openFeedback(taskId, category, finishEarly) {
    _feedbackContext = {
      taskId: taskId,
      category: category || null,
      finishEarly: !!finishEarly
    };
    feedbackMood = 3;
    _pendingFeedbackSubmit = null;
    openFeedbackModalForTask(taskId, category || null, !!finishEarly);
  }

  // 心情：只更新 owner 状态；DOM 选中态由 classic 适配器负责。
  function setMood(v) {
    var n = parseInt(v, 10);
    feedbackMood = isFinite(n) ? n : 3;
    return feedbackMood;
  }

  // 读取能量：经注入的 DOM 适配器取值，非法值回退 5。
  function readEnergy() {
    var raw = readFeedbackEnergy();
    var energy = parseInt((raw === undefined || raw === null || raw === '') ? '5' : String(raw), 10);
    if (!isFinite(energy) || energy < 1 || energy > 10) energy = 5;
    return energy;
  }

  // 读取心情：owner 状态，非 1..5 的整数回退 3。
  function readMood() {
    var mood = feedbackMood;
    if (!isFinite(mood) || Math.floor(mood) !== mood || mood < 1 || mood > 5) mood = 3;
    return mood;
  }

  // 提交反馈：仅在用户显式「确认」后 POST。
  function submitFeedback() {
    var ctx = _feedbackContext;
    if (!ctx) {
      // 没有上下文：关闭 modal 并直接返回（不发请求）。
      closeModal('feedbackModal');
      return Promise.resolve();
    }
    var taskId = ctx.taskId;
    // reentrancy：同一 taskId 的并发提交直接 no-op。
    if (_pendingFeedbackSubmit === taskId) return Promise.resolve();

    var body = { energy_after: readEnergy(), mood_after: readMood() };
    if (ctx.finishEarly) body.event_type = 'finish_early';

    _pendingFeedbackSubmit = taskId;
    // 不先关闭 modal —— 失败时要停留以供重试。
    return api('/api/tasks/' + taskId + '/feedback', {
      method: 'POST',
      body: JSON.stringify(body)
    }).then(function () {
      closeModal('feedbackModal');
      renderFeedbackSuccess();
      refreshGachaStats();
      transitionToCareModal();
    }).catch(function (e) {
      _pendingFeedbackSubmit = null; // 解锁，允许用户重新点确认
      toast((e && e.message) || '反馈提交失败，请重试', 'err');
      // 模态保持打开，不清空用户输入，不进入关怀流程。
    });
  }

  // 取消反馈：零网络请求，直接过渡到关怀弹窗。
  function cancelFeedback() {
    closeModal('feedbackModal');
    return transitionToCareModal();
  }

  // 反馈 → 关怀 的过渡：捕获上下文、清空反馈状态与 pending 锁。
  function transitionToCareModal() {
    var ctx = _feedbackContext;
    _feedbackContext = null;
    _pendingFeedbackSubmit = null;
    if (!ctx) return Promise.resolve();
    return openCare(ctx.taskId, ctx.category);
  }

  // 打开关怀弹窗：owner 选文案与科目标签，再交给 DOM 适配器渲染。
  function openCare(taskId, category) {
    _careContext = { taskId: taskId, category: category || null };
    var encText = CARE_ENCOURAGES[Math.floor(Math.random() * CARE_ENCOURAGES.length)];
    var catLabel = category ? (CARE_CATEGORY_LABELS[category] || category) : '当前';
    renderCareModal(taskId, category || null, encText, catLabel);
  }

  // 同科目再抽一张（无科目信息时给出提示，但仍然抽卡）。
  function careSameCategory() {
    var cat = _careContext ? _careContext.category : null;
    closeModal('careModal');
    _careContext = null;
    if (!cat) {
      toast('无科目信息，将继续抽卡', 'inf');
    }
    drawGachaWithCategory(cat, null);
  }

  // 换科目再抽一张。
  function careSwitchCategory() {
    var cat = _careContext ? _careContext.category : null;
    closeModal('careModal');
    _careContext = null;
    drawGachaWithCategory(null, cat);
  }

  // 休息一下。
  function careRest() {
    closeModal('careModal');
    _careContext = null;
    renderCareRest();
  }

  // -------------------------------------------------------------------------
  // G15.3 跳过 / 拒绝（Skip / Refuse）
  // -------------------------------------------------------------------------
  // 四条入口的历史语义**逐条保持**（不得互相合并）：
  //   handleSkip  （抽卡结果卡）：resetReplaceChain → 反馈 → POST skip →
  //                动画 → 结果区 → 解锁 Toast → refreshGachaStats → loadTasks
  //   handleRefuse（抽卡结果卡）：resetReplaceChain → 反馈 → POST refuse →
  //                动画 → 结果区 → refreshGachaStats（**不** loadTasks）
  //   taskSkip    （任务列表）  ：反馈 → POST skip → 动画 → 「已跳过」→
  //                解锁 Toast → loadTasks（**不** resetReplaceChain / stats）
  //   taskRefuse  （任务列表）  ：反馈 → POST refuse → 动画 → 「已记录」→
  //                loadTasks（**不** resetReplaceChain / stats）
  //
  // 核心顺序合同：**promptTaskFeedback 的 Promise 未完成前，业务 API 绝不能
  // 发出**。反馈 Promise 的返回值不决定是否继续跳过 / 拒绝（用户取消反馈后
  // 业务仍继续，与迁移前一致）。

  // 反馈上下文（classic 层唯一实现，注入进来；owner 不持有第二份任务数组）。
  function buildFeedbackContext(id, completionStatus) {
    if (typeof getTaskFeedbackContext !== 'function') return null;
    var ctx = getTaskFeedbackContext(id);
    if (!ctx) return null;
    ctx.completionStatus = completionStatus;
    return ctx;
  }

  // 反馈适配器缺失时 fail closed：绝不擅自 POST。
  function feedbackUnavailable() {
    toast('反馈模块未就绪，请稍后重试', 'err');
    return false;
  }

  // 必要适配器可用性：
  //   - 依赖本身必须是函数（未注入时为 null）；
  //   - 注入方若提供 isAvailable() 探针（晚绑定场景），以探针结果为准，
  //     使 owner 能在发出业务 API **之前**识别真实适配器是否存在。
  function adapterAvailable(fn) {
    if (typeof fn !== 'function') return false;
    if (typeof fn.isAvailable === 'function') {
      try {
        return !!fn.isAvailable();
      } catch (e) {
        return false;
      }
    }
    return true;
  }

  // 四个入口**共同**必需的适配器：反馈上下文 / 反馈提示 / 卡片动画。
  function commonAdaptersReady() {
    if (!adapterAvailable(getTaskFeedbackContext) || !adapterAvailable(promptTaskFeedback)) {
      toast('反馈模块未就绪，请稍后重试', 'err');
      return false;
    }
    if (!adapterAvailable(playCardAnim)) {
      toast('动画模块未就绪，请稍后重试', 'err');
      return false;
    }
    return true;
  }

  // 抽卡结果卡入口**额外**必需：结果区渲染（任务列表路径不涉及，不参与预检）。
  function drawnCardAdaptersReady() {
    if (!commonAdaptersReady()) return false;
    if (!adapterAvailable(renderDrawnCardResult)) {
      toast('结果区未就绪，请稍后重试', 'err');
      return false;
    }
    return true;
  }

  // 统一的「先等反馈、再发业务 API」前置段。返回 false 表示不得继续。
  async function awaitFeedbackBeforeAction(id, completionStatus) {
    if (typeof promptTaskFeedback !== 'function') return feedbackUnavailable();
    var ctx = buildFeedbackContext(id, completionStatus);
    if (!ctx) return feedbackUnavailable();
    // 反馈适配器必须返回一个 Promise；缺失 / 非 Promise 一律 fail closed，
    // **绝不**在反馈 Promise 缺失时擅自 POST。
    var pending = promptTaskFeedback('skip', ctx);
    if (!pending || typeof pending.then !== 'function') return feedbackUnavailable();
    await pending;
    return true;
  }

  // 抽卡结果卡：跳过。
  async function handleSkip(id) {
    if (!drawnCardAdaptersReady()) return;
    resetReplaceChain();
    if (!(await awaitFeedbackBeforeAction(id, 'skipped'))) return;
    try {
      var r = await api('/api/tasks/' + id + '/skip', { method: 'POST' });
      await playCardAnim(id, 'is-skipping');
      renderDrawnCardResult('skipped');
      if (r && r.unlocked_tasks && r.unlocked_tasks.length) {
        toast(UNLOCK_MESSAGE + ': ' + r.unlocked_tasks.join('、'), 'suc');
      }
      refreshGachaStats();
      loadTasks();
    } catch (e) {
      toast((e && e.message) || '跳过失败', 'err');
    }
  }

  // 抽卡结果卡：拒绝（历史行为不刷新任务列表）。
  async function handleRefuse(id) {
    if (!drawnCardAdaptersReady()) return;
    resetReplaceChain();
    if (!(await awaitFeedbackBeforeAction(id, 'refused'))) return;
    try {
      await api('/api/tasks/' + id + '/refuse', { method: 'POST' });
      await playCardAnim(id, 'is-refusing');
      renderDrawnCardResult('refused');
      refreshGachaStats();
    } catch (e) {
      toast((e && e.message) || '拒绝失败', 'err');
    }
  }

  // 任务列表：跳过（不结束换卡链，不刷新抽卡统计）。
  async function taskSkip(id) {
    if (!commonAdaptersReady()) return;
    if (!(await awaitFeedbackBeforeAction(id, 'skipped'))) return;
    try {
      var r = await api('/api/tasks/' + id + '/skip', { method: 'POST' });
      await playCardAnim(id, 'is-skipping');
      toast('已跳过', 'suc');
      if (r && r.unlocked_tasks && r.unlocked_tasks.length) {
        toast(UNLOCK_MESSAGE + ': ' + r.unlocked_tasks.join('、'), 'suc');
      }
      loadTasks();
    } catch (e) {
      toast((e && e.message) || '跳过失败', 'err');
    }
  }

  // 任务列表：拒绝（不结束换卡链，不刷新抽卡统计）。
  async function taskRefuse(id) {
    if (!commonAdaptersReady()) return;
    if (!(await awaitFeedbackBeforeAction(id, 'refused'))) return;
    try {
      await api('/api/tasks/' + id + '/refuse', { method: 'POST' });
      await playCardAnim(id, 'is-refusing');
      toast('已记录', 'inf');
      loadTasks();
    } catch (e) {
      toast((e && e.message) || '拒绝失败', 'err');
    }
  }

  // -------------------------------------------------------------------------
  // G15.4 手动弃牌 / 弃牌列表 / 手动恢复
  // -------------------------------------------------------------------------
  // 三条入口的历史语义**逐条保持**：
  //   moveToDiscard(id)    ：POST /api/tasks/{id}/move-to-discard →
  //                         动画 'is-discarding' → toast(discarded,'inf') →
  //                         loadTasks → updateDiscardPileVisual
  //   loadDiscardPileList()：加载态 → GET /api/discard-pile →
  //                         空态 / 列表（渲染委托 classic）→ 错误态 + toast
  //   restoreFromDiscard() ：确认 → POST /api/discard-pile/{id}/restore →
  //                         toast('已恢复任务','suc') → 刷新列表 → loadTasks →
  //                         refreshGachaStats → updateDiscardPileVisual
  //
  // Fail-closed 合同：
  //   - 动画适配器缺失 → 手动弃牌绝不 POST；
  //   - 确认适配器缺失 → 手动恢复绝不 POST；
  //   - 用户取消确认 → 手动恢复绝不 POST、不刷新任何状态。

  // 手动弃牌：动画适配器是必要依赖，缺失时绝不 POST。
  async function moveToDiscard(id) {
    if (!adapterAvailable(playCardAnim)) {
      toast('动画模块未就绪，请稍后重试', 'err');
      return;
    }
    try {
      await api('/api/tasks/' + id + '/move-to-discard', { method: 'POST' });
      await playCardAnim(id, 'is-discarding');
      toast(getDiscardPileMessage(), 'inf');
      loadTasks();
      updateDiscardPileVisual();
    } catch (e) {
      toast((e && e.message) || '操作失败', 'err');
    }
  }

  // 弃牌列表：GET 与业务错误处理归 owner；DOM 渲染全部委托 classic 适配器。
  async function loadDiscardPileList() {
    // 渲染适配器缺失 → 无法呈现加载态，不发起任何请求（fail closed）。
    if (!adapterAvailable(renderDiscardPileLoading)) return;
    // classic 层渲染适配器返回 false 表示容器不存在：同样不发请求。
    if (renderDiscardPileLoading() === false) return;
    try {
      var items = await api('/api/discard-pile');
      if (!items || !items.length) {
        if (adapterAvailable(renderDiscardPileEmpty)) renderDiscardPileEmpty();
        return;
      }
      if (adapterAvailable(renderDiscardPileItems)) renderDiscardPileItems(items);
    } catch (e) {
      if (adapterAvailable(renderDiscardPileError)) renderDiscardPileError();
      toast((e && e.message) || '弃牌堆加载失败', 'err');
    }
  }

  // 手动恢复：确认适配器是必要依赖；用户取消时零网络请求、零刷新。
  async function restoreFromDiscard(id, name) {
    if (!adapterAvailable(confirmDiscardRestore)) {
      toast('恢复确认未就绪，请稍后重试', 'err');
      return;
    }
    var confirmed = confirmDiscardRestore(id, name);
    if (confirmed && typeof confirmed.then === 'function') {
      confirmed = await confirmed;
    }
    if (!confirmed) return;
    try {
      await api('/api/discard-pile/' + id + '/restore', {
        method: 'POST',
        body: JSON.stringify({})
      });
      toast('已恢复任务', 'suc');
      loadDiscardPileList();
      loadTasks();
      refreshGachaStats();
      updateDiscardPileVisual();
    } catch (e) {
      toast((e && e.message) || '恢复失败', 'err');
    }
  }

  // 只读诊断快照（每次返回新对象，不暴露内部可变引用）。
  function getFeedbackContext() {
    if (!_feedbackContext) return null;
    return {
      taskId: _feedbackContext.taskId,
      category: _feedbackContext.category,
      finishEarly: _feedbackContext.finishEarly
    };
  }

  function getCareContext() {
    if (!_careContext) return null;
    return { taskId: _careContext.taskId, category: _careContext.category };
  }

  return {
    startTask: startTask,
    confirmComplete: confirmComplete,
    completeWithFeedback: completeWithFeedback,
    openFeedback: openFeedback,
    setMood: setMood,
    submitFeedback: submitFeedback,
    cancelFeedback: cancelFeedback,
    transitionToCareModal: transitionToCareModal,
    careSameCategory: careSameCategory,
    careSwitchCategory: careSwitchCategory,
    careRest: careRest,
    handleSkip: handleSkip,
    handleRefuse: handleRefuse,
    taskSkip: taskSkip,
    taskRefuse: taskRefuse,
    moveToDiscard: moveToDiscard,
    loadDiscardPileList: loadDiscardPileList,
    restoreFromDiscard: restoreFromDiscard,
    getFeedbackContext: getFeedbackContext,
    getCareContext: getCareContext,
    getMood: function () { return feedbackMood; }
  };
}
