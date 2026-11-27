// modules/gacha/index.js - 抽卡核心真实 ESM owner（AR03-G14）
//
// AR03-P3-F：**应用级（app-scoped）模块**。
//
// 抽卡 session / 换卡链是 **跨页面的连续概念**：换卡链必须沿用同一个
// session，离开抽卡页才结束。因此本模块 **不实现** 页面级
// `meta` / `mount` / `unmount` 契约 —— 页面切换 **绝不** 让抽卡 session
// 结束、也绝不停止任何抽卡相关的全局能力。
//
// 装配根 static/app.entry.js 在启动时创建唯一 owner 实例并调用
// `init()`；整个应用生命周期内该实例不被销毁。
//
// 本模块内：
//   - createGachaOwner(deps)：持有唯一状态的闭包 owner（energy / pool /
//     canReplace / replace chain / selectedTag / isDrawing +
//     unified event/session 状态）。
//   - initAppScoped()：应用级启动钩子（只做一次性的全局能力接线，
//     **不** 触碰任何页面 DOM 生命周期）。
//
// presentation（renderMultiResults / playCardFlyAnimation）由同目录的
// ./presentation.js 提供，本模块 **静态 import** 复用，绝不重复实现。
// 依赖（api / toast / DOM / 计时快照 / classic task cache setter）全部
// **显式注入**：owner 不通过 window 偷查任何私有依赖。

import { renderMultiResults, playCardFlyAnimation } from './presentation.js';

//: 应用级启动标志：保证 initAppScoped() 的全局接线只做一次。
var _appScopedInitialized = false;

/**
 * 应用级（app-scoped）启动钩子。
 *
 * 语义：**只做一次性全局能力接线**，绝不注册页面级 mount/unmount，
 * 因此页面切换不会影响抽卡 session / 换卡链的连续性。
 */
export function initAppScoped() {
  if (_appScopedInitialized) return;
  _appScopedInitialized = true;
  // Phase 1：委托给旧全局函数（app.js 仍主导）。
  // 这是 **一次性** 的全局接线，不是页面 mount —— 页面切换不会重复触发。
  if (typeof window.refreshGachaStats === 'function') {
    try { window.refreshGachaStats(); } catch (e) { console.error('[gacha] refreshGachaStats', e); }
  }
}

// ===========================================================================
// AR03-G14：抽卡核心 + 行为事件会话 —— 真实 ESM owner
// ===========================================================================
// 唯一状态所有者（闭包内）：
//   energy / pool / canReplace / replacedTaskId / replacedTaskIds /
//   allowRepeatReplaced / currentTaskId / selectedTag / isDrawing
//   + unified gacha event/session（session id / event 序号 / event id /
//     action id / card_shown 去重表 / delivery 统计）
//
// 依赖全部 **显式注入**（不在 owner 内通过 window 偷查私有依赖）：
//   documentRef / api / toast / showModal / closeModal / WARM_MESSAGES
//   renderDrawnCard / refreshGachaStats / updateDiscardPileVisual
//   _timerSnapshot / _timerRunning
//   setCurrentDrawnTask / setMultiDrawResults（写 classic task cache 的窄 setter）
//
// 语义与迁移前的 classic 实现逐行一致：API 路径、方法、payload、事件类型、
// session / event id 语义、card_shown 去重键、delivery 统计、失败提示全部不变。

var UNIFIED_GACHA_EVENT_SOURCE = 'unified_gacha';
var UNIFIED_GACHA_EVENT_SCHEMA_VERSION = 1;

export function createGachaOwner(deps) {
  var documentRef = deps.documentRef;
  var api = deps.api;
  var toast = deps.toast;
  var showModal = deps.showModal;
  var closeModal = deps.closeModal;
  var WARM_MESSAGES = deps.WARM_MESSAGES;
  var renderDrawnCard = deps.renderDrawnCard;
  var refreshGachaStats = deps.refreshGachaStats;
  var updateDiscardPileVisual = deps.updateDiscardPileVisual;
  var timerSnapshot = deps._timerSnapshot;
  var timerRunning = deps._timerRunning;
  var setCurrentDrawnTask = deps.setCurrentDrawnTask;
  var setMultiDrawResults = deps.setMultiDrawResults;

  // ------------------------------------------------------------------
  // 唯一状态
  // ------------------------------------------------------------------
  var state = {
    energy: 'medium',
    pool: 'fragment',
    canReplace: true,
    replacedTaskId: null,
    replacedTaskIds: [],
    allowRepeatReplaced: false,
    currentTaskId: null,
    selectedTag: '',
    isDrawing: false
  };

  // 本轮抽卡 session：新的 draw / multi / care 开启新 session；
  // 同一条连续换卡链 **沿用** 同一个 session；离开抽卡页即结束。
  var _sessionId = null;
  // 事件序号：保证同一页面生命周期内 event_id 互不相同。
  var _eventSeq = 0;
  // card_shown 去重表：session + task + surface + action。
  var _shownKeys = {};
  // 未送达状态（可复用）：成功 / 失败 / 在途计数 + 最近一次错误 + 可重放的载荷。
  var _delivery = {
    sent: 0,
    failed: 0,
    pending: 0,
    lastError: null,
    lastFailed: null
  };

  // ------------------------------------------------------------------
  // 行为事件：id / session / 上报
  // ------------------------------------------------------------------
  function newUnifiedGachaEventId(prefix) {
    _eventSeq += 1;
    return String(prefix || 'evt') + '-' + Date.now().toString(36) +
      '-' + _eventSeq.toString(36) +
      '-' + Math.random().toString(36).slice(2, 10);
  }

  function newUnifiedGachaActionId(kind) {
    return newUnifiedGachaEventId('act-' + (kind || 'draw'));
  }

  function unifiedGachaEventId(actionId, eventType, taskId) {
    var id = String(actionId) + ':' + String(eventType);
    if (taskId !== undefined && taskId !== null) id += ':' + String(taskId);
    return id;
  }

  // 严格取正整数 task id；不是正整数返回 null（绝不伪造 id）。
  function unifiedGachaTaskId(value) {
    var n = (typeof value === 'number') ? value : Number(value);
    if (!isFinite(n) || Math.floor(n) !== n || n <= 0) return null;
    return n;
  }

  function getUnifiedGachaSessionId() {
    if (!_sessionId) beginUnifiedGachaSession();
    return _sessionId;
  }

  function beginUnifiedGachaSession() {
    _eventSeq += 1;
    _sessionId = 'sess-' + Date.now().toString(36) +
      '-' + _eventSeq.toString(36) +
      '-' + Math.random().toString(36).slice(2, 8);
    // 新 session → card_shown 去重表重置。
    _shownKeys = {};
    return _sessionId;
  }

  function endUnifiedGachaSession() {
    _sessionId = null;
  }

  // 卡片 **真正渲染进结果区** 后记录 card_shown。
  function reportUnifiedGachaCardShown(taskId, context, actionId) {
    var tid = unifiedGachaTaskId(taskId);
    if (tid === null) return Promise.resolve({ ok: false, error: 'invalid task_id' });
    var surface = (context && context.surface) ? String(context.surface) : 'default';
    var action = actionId || ('shown-' + tid);
    var key = getUnifiedGachaSessionId() + '#' + tid + '#' + surface + '#' + action;
    if (_shownKeys[key]) {
      return Promise.resolve({ ok: true, duplicate: true, skipped: true });
    }
    _shownKeys[key] = true;
    return sendUnifiedGachaEvent('card_shown', tid, context,
      unifiedGachaEventId(action, 'card_shown', tid));
  }

  // 发送一条统一抽卡行为事件（fire-and-forget：**不 await**）。
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
    _delivery.pending += 1;
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
      _delivery.pending -= 1;
      _delivery.sent += 1;
      _delivery.lastFailed = null;
      return {
        ok: true,
        id: res && res.id,
        status: res && res.status,
        duplicate: !!(res && res.duplicate)
      };
    }).catch(function (e) {
      _delivery.pending -= 1;
      _delivery.failed += 1;
      _delivery.lastError = (e && e.message) ? e.message : '未知错误';
      // 保留未送达载荷（供重试；event_id 不变）。
      _delivery.lastFailed = payload;
      // 可见的失败提示：没送达就说没送达，绝不谎称保存成功。
      toast('行为记录未送达（' + _delivery.lastError + '）', 'err');
      return { ok: false, error: e };
    });
  }

  // 只读诊断快照（每次读取返回新对象，不暴露 owner 内部可变对象）。
  function getDeliverySnapshot() {
    return {
      sent: _delivery.sent,
      failed: _delivery.failed,
      pending: _delivery.pending,
      lastError: _delivery.lastError,
      lastFailed: _delivery.lastFailed
        ? JSON.parse(_delivery.lastFailed.note)
        : null
    };
  }

  // ------------------------------------------------------------------
  // 换卡链
  // ------------------------------------------------------------------
  function resetReplaceChain() {
    state.replacedTaskIds = [];
    state.allowRepeatReplaced = false;
    state.replacedTaskId = null;
  }

  function readAllowRepeatReplaced() {
    var el = documentRef.getElementById('rr_allow_repeat');
    var value = !!(el && el.checked);
    state.allowRepeatReplaced = value;
    return value;
  }

  function showReplaceReason(taskId) {
    state.replacedTaskId = taskId;
    var bar = documentRef.getElementById('replaceReasonBar');
    if (!bar) {
      bar = documentRef.createElement('div');
      bar.id = 'replaceReasonBar';
      bar.className = 'replace-reason';
      // 理由 **没有** 默认选中项：用户必须自己明确选一个。
      // 开关 A 复用本链状态；开关 B 每次新表单默认不勾选（不写入状态）。
      bar.innerHTML =
        '<input type="radio" name="reason" value="low_energy" id="rr_low"><label for="rr_low">精力不足</label>' +
        '<input type="radio" name="reason" value="no_time" id="rr_no"><label for="rr_no">时间不够</label>' +
        '<input type="radio" name="reason" value="similar_done" id="rr_sim"><label for="rr_sim">刚做过类似</label>' +
        '<input type="radio" name="reason" value="other" id="rr_ot"><label for="rr_ot">其他</label>' +
        '<label class="replace-opt" for="rr_allow_repeat"><input type="checkbox" id="rr_allow_repeat"> 允许曾被更换的卡牌再次抽出</label>' +
        '<label class="replace-opt" for="rr_hide_today"><input type="checkbox" id="rr_hide_today"> 我今天内不想再看到这张卡</label>' +
        '<button class="btn pri sm" onclick="doReplace()">确认换牌</button>';
      var card = documentRef.getElementById('gachaResult').querySelector('.task-card.drawn-card');
      if (card) card.appendChild(bar);
    } else {
      bar.style.display = 'flex';
    }
    // 每次打开表单都按链状态同步开关 A，并确保开关 B 未被勾选。
    var allowEl = documentRef.getElementById('rr_allow_repeat');
    if (allowEl) allowEl.checked = !!state.allowRepeatReplaced;
    var hideEl = documentRef.getElementById('rr_hide_today');
    if (hideEl) hideEl.checked = false;
  }

  async function doReplace() {
    var rid = state.replacedTaskId;
    // 理由 **必须显式选择**，绝不静默回落成 other。
    var reasonEl = documentRef.querySelector('#replaceReasonBar input[name="reason"]:checked');
    if (!reasonEl) {
      toast('请先选择换牌理由', 'err');
      return;
    }
    var reason = reasonEl.value;
    var allowRepeat = readAllowRepeatReplaced();
    var hideEl = documentRef.getElementById('rr_hide_today');
    var hideToday = !!(hideEl && hideEl.checked);
    var chainIds = Array.isArray(state.replacedTaskIds) ? state.replacedTaskIds.slice() : [];
    // 同一条连续换卡链沿用同一个 session；本次换牌是一个新的真实动作。
    var actionId = newUnifiedGachaActionId('replace');
    var replacedTaskId = unifiedGachaTaskId(rid);
    try {
      var availableMinutes = getGachaAvailableMinutes();
      var r = await api('/api/gacha/replace', {
        method: 'POST',
        body: JSON.stringify({
          task_id: rid,
          reason: reason,
          pool: state.pool,
          energy: state.energy,
          available_time: availableMinutes,
          preferred_tag: state.selectedTag || null,
          replaced_task_ids: chainIds,
          allow_repeat_replaced: allowRepeat,
          hide_today: hideToday
        })
      });
      if (r.task) {
        if (r.pool) state.pool = r.pool;
        // 只有 **成功** 才把旧卡并入本链；失败时链与当前卡都保持不变。
        if (chainIds.indexOf(rid) === -1) chainIds.push(rid);
        state.replacedTaskIds = chainIds;
        state.currentTaskId = r.task.id;
        // 单抽路径换卡成功后 **仍可** 继续换卡（不永久关闭 canReplace）。
        state.canReplace = true;
        // 写回 classic 的 task cache（startTask / findDrawnTask 的唯一来源）。
        setCurrentDrawnTask(r.task);
        var result = documentRef.getElementById('gachaResult');
        result.innerHTML = '';
        result.appendChild(renderDrawnCard(r.task, 0, state.canReplace));
        // 只有成功才记录 card_replaced。
        var newTaskId = unifiedGachaTaskId(r.task.id);
        if (replacedTaskId !== null) {
          sendUnifiedGachaEvent('card_replaced', replacedTaskId, {
            new_task_id: newTaskId,
            reason: reason,
            allow_repeat_replaced: allowRepeat,
            hide_today: hideToday,
            pool: r.pool || state.pool,
            replaced_task_ids: chainIds.slice()
          }, unifiedGachaEventId(actionId, 'card_replaced', replacedTaskId));
        }
        // 换卡得到的 **新牌** 也是一次真实发牌 → card_drawn（新牌的真实 id）。
        sendUnifiedGachaEvent('card_drawn', newTaskId, {
          source: 'replace',
          pool: r.pool || state.pool,
          energy: state.energy,
          available_time: availableMinutes,
          preferred_tag: state.selectedTag || null
        }, unifiedGachaEventId(actionId, 'card_drawn', newTaskId));
        // 新牌真正渲染进结果区 → 记录新牌的 card_shown。
        reportUnifiedGachaCardShown(r.task.id, {
          source: 'replace',
          surface: 'result',
          pool: r.pool || state.pool
        }, actionId);
        toast('已换牌', 'inf');
      }
    } catch (e) {
      // 失败：保留当前卡、保留表单与开关状态，显示错误并允许重试。
      toast(e.message || '换牌失败', 'err');
    }
  }

  // ------------------------------------------------------------------
  // 可用时间预算
  // ------------------------------------------------------------------
  function getGachaAvailableMinutes() {
    var input = documentRef.getElementById('gachaTimeInput');
    var raw = input ? input.value.trim() : '';
    var minutes = Number(raw);
    if (!/^[0-9]+$/.test(raw) || !Number.isInteger(minutes) || minutes < 1 || minutes > 480) {
      throw new Error('可用时间请输入 1–480 之间的整数分钟');
    }
    return minutes;
  }

  // ------------------------------------------------------------------
  // 初始化：标签选择 + 精力 / 卡池联动
  // ------------------------------------------------------------------
  async function initGachaTagSelect() {
    var sel = documentRef.getElementById('gachaTagSelect');
    if (!sel) return;
    sel.innerHTML = '<option value="">不限</option>';
    try {
      var tags = await api('/api/tags');
      tags.forEach(function (t) {
        var opt = documentRef.createElement('option');
        opt.value = t.name;
        opt.textContent = t.name + ' (' + t.task_count + ')';
        sel.appendChild(opt);
      });
    } catch (e) { /* ignore */ }
  }

  // 一次性绑定标签 / 精力 / 卡池监听（由 app.entry.js 在 owner 创建后调用）。
  function init() {
    var sel = documentRef.getElementById('gachaTagSelect');
    if (sel) {
      sel.addEventListener('change', function () {
        state.selectedTag = this.value;
        var hint = documentRef.getElementById('gachaTagHint');
        if (hint) hint.textContent = this.value ? '🎯 ' + this.value : '';
      });
    }
    documentRef.querySelectorAll('.energy-btn').forEach(function (b) {
      b.addEventListener('click', function () {
        documentRef.querySelectorAll('.energy-btn').forEach(function (x) { x.classList.remove('active'); });
        b.classList.add('active');
        state.energy = b.dataset.e;
      });
    });
    documentRef.querySelectorAll('.pool-btn').forEach(function (b) {
      b.addEventListener('click', function () {
        documentRef.querySelectorAll('.pool-btn').forEach(function (x) { x.classList.remove('active'); });
        b.classList.add('active');
        state.pool = b.dataset.pool;
      });
    });
    initGachaTagSelect();
  }

  // ------------------------------------------------------------------
  // 单抽
  // ------------------------------------------------------------------
  async function drawGacha() {
    if (state.isDrawing) return;
    var btn = documentRef.getElementById('gachaBtn');
    if (btn) btn.disabled = true;
    state.isDrawing = true;
    // 发起新抽卡 → 本链结束。
    resetReplaceChain();
    // 一次新的抽卡 → 开启新的行为事件 session。
    beginUnifiedGachaSession();
    var actionId = newUnifiedGachaActionId('draw');

    var result = documentRef.getElementById('gachaResult');
    var deck = documentRef.getElementById('gachaDeck');
    var flyLayer = documentRef.getElementById('cardFlyLayer');
    var multiResultArea = documentRef.getElementById('gachaMultiResult');
    // 清掉上一次的飞行卡片残留，防止快速二次抽卡时动画叠层（P0-3）
    if (flyLayer) flyLayer.innerHTML = '';
    // 清掉抽卡结果区，避免新旧卡牌同时显示
    if (result) result.innerHTML = '';
    // 切换到单抽时隐藏多抽结果（但不清理计时器或已选任务）
    if (multiResultArea) multiResultArea.classList.add('hidden');
    setMultiDrawResults([]);
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
          pool: state.pool,
          energy: state.energy,
          available_time: availableMinutes,
          preferred_tag: state.selectedTag || null
        })
      });
      if (r.task) {
        if (r.pool) state.pool = r.pool;
        state.canReplace = r.can_replace !== false;
        state.currentTaskId = r.task.id;
        // 写回 classic 的 task cache（startTask / findDrawnTask 的唯一来源）。
        setCurrentDrawnTask(r.task);
        // 服务端返回真实 task 后才记录 card_drawn。
        var drawnTaskId = unifiedGachaTaskId(r.task.id);
        var drawContext = {
          source: 'single_draw',
          pool: r.pool || state.pool,
          energy: state.energy,
          available_time: availableMinutes,
          preferred_tag: state.selectedTag || null
        };
        sendUnifiedGachaEvent('card_drawn', drawnTaskId, drawContext,
          unifiedGachaEventId(actionId, 'card_drawn', drawnTaskId));
        var stage = renderDrawnCard(r.task, 0, state.canReplace);
        result.appendChild(stage);
        // 卡片真正进入结果区后才记录 card_shown。
        reportUnifiedGachaCardShown(drawnTaskId,
          { source: 'single_draw', surface: 'result', pool: drawContext.pool }, actionId);
        // 播放飞行动画
        await playCardFlyAnimation(r.task);
        updateDiscardPileVisual();
      } else {
        result.innerHTML = '<div class="empty-state mt24"><i class="fa-solid fa-box-open"></i><p>' + WARM_MESSAGES.poolEmpty + '</p></div>';
        state.currentTaskId = null;
      }
    } catch (e) {
      toast(e.message || '抽卡失败', 'err');
      state.currentTaskId = null;
    }

    if (deck) deck.classList.remove('is-drawing');
    if (btn) btn.disabled = false;
    state.isDrawing = false;
    refreshGachaStats();
  }

  // ------------------------------------------------------------------
  // 连抽
  // ------------------------------------------------------------------
  async function drawGachaMulti() {
    // 检查共享锁
    if (state.isDrawing) return;

    // 检查计时器状态（唯一 session 来自 ESM timer owner）。
    var _snap = timerSnapshot();
    if (_snap.session && timerRunning()) {
      var taskId = _snap.session.task_id;
      var activeCard = documentRef.querySelector('.task-card.drawn-card[data-task-id="' + taskId + '"]');
      if (activeCard) {
        toast('请先完成当前计时任务', 'inf');
        return;
      }
    }

    var multiBtn = documentRef.getElementById('gachaMultiBtn');
    var singleBtn = documentRef.getElementById('gachaBtn');
    var countSelect = documentRef.getElementById('gachaMultiCount');

    if (multiBtn) multiBtn.disabled = true;
    if (singleBtn) singleBtn.disabled = true;

    state.isDrawing = true;

    var result = documentRef.getElementById('gachaResult');
    var deck = documentRef.getElementById('gachaDeck');

    // 清空单抽结果区（发起新连抽 → 本链结束）
    resetReplaceChain();
    if (result) result.innerHTML = '';
    // 一次新的连抽 → 开启新的行为事件 session。
    beginUnifiedGachaSession();
    var actionId = newUnifiedGachaActionId('multi');

    try {
      var count = parseInt(countSelect ? countSelect.value : '3', 10);
      count = Math.max(2, Math.min(5, count));
      var availableMinutes = getGachaAvailableMinutes();

      var r = await api('/api/gacha/multi-draw', {
        method: 'POST',
        body: JSON.stringify({
          available_time: availableMinutes,
          count: count,
          energy: state.energy,
          preferred_tag: state.selectedTag || null
        })
      });

      if (r.tasks && r.tasks.length > 0) {
        setMultiDrawResults(r.tasks);
        // renderMultiResults 已迁至 ESM presentation owner；必须 await，
        // 确保 DOM 确实渲染完成后才继续上报 card_shown。
        var renderedCount = await renderMultiResults(r, activateMultiCard);
        // 每张 **有效** 卡（真实 task id）各记一次 card_drawn。
        r.tasks.forEach(function (task) {
          var tid = unifiedGachaTaskId(task && task.id);
          if (tid === null) return;  // 没有真实 task id → 不记录
          sendUnifiedGachaEvent('card_drawn', tid, {
            source: 'multi_draw',
            pool: r.pool || state.pool,
            energy: state.energy,
            available_time: availableMinutes,
            preferred_tag: state.selectedTag || null,
            multi_count: count
          }, unifiedGachaEventId(actionId, 'card_drawn', tid));
        });
        // 结果列表 **确实渲染** 出来 → 这些卡已进入结果区 → card_shown。
        if (renderedCount > 0) {
          r.tasks.forEach(function (task) {
            var tid = unifiedGachaTaskId(task && task.id);
            if (tid === null) return;
            reportUnifiedGachaCardShown(tid, {
              source: 'multi_draw',
              surface: 'multi_list',
              pool: r.pool || state.pool
            }, actionId);
          });
        }
        toast('抽到 ' + r.tasks.length + ' 张卡牌', 'suc');
      } else {
        // 空池或404
        var multiResultArea = documentRef.getElementById('gachaMultiResult');
        if (multiResultArea) {
          multiResultArea.classList.add('hidden');
        }
        setMultiDrawResults([]);
        toast('没有合适的任务', 'inf');
      }
    } catch (e) {
      toast(e.message || '连抽失败', 'err');
      // 清空多抽结果
      var multiResultArea = documentRef.getElementById('gachaMultiResult');
      if (multiResultArea) {
        multiResultArea.classList.add('hidden');
      }
      setMultiDrawResults([]);
    } finally {
      if (multiBtn) multiBtn.disabled = false;
      if (singleBtn) singleBtn.disabled = false;
      state.isDrawing = false;
      refreshGachaStats();
    }
  }

  // 激活连抽中的一张卡（不再发任何 POST）。
  function activateMultiCard(task, idx) {
    // 检查是否有计时器正在运行（唯一 session 来自 ESM timer owner）。
    var _snap = timerSnapshot();
    if (_snap.session && timerRunning()) {
      var activeTaskId = _snap.session.task_id;
      if (activeTaskId && activeTaskId !== task.id) {
        var activeCard = documentRef.querySelector('.task-card.drawn-card[data-task-id="' + activeTaskId + '"]');
        if (activeCard) {
          toast('请先完成当前计时任务', 'inf');
          return;
        }
      }
    }

    // 更新选中状态UI + aria-pressed 同步
    var items = documentRef.querySelectorAll('.gacha-multi-item');
    items.forEach(function (item) {
      item.classList.remove('activated');
      if (item.setAttribute) {
        item.setAttribute('aria-pressed', 'false');
      }
    });
    var selectedItem = documentRef.querySelector('.gacha-multi-item[data-task-id="' + task.id + '"]');
    if (selectedItem) {
      selectedItem.classList.add('activated');
      if (selectedItem.setAttribute) {
        selectedItem.setAttribute('aria-pressed', 'true');
      }
      // 保持键盘焦点在选中项上，键盘用户不会丢失位置。
      selectedItem.focus({ preventScroll: true });
    }

    // 清除单抽结果区
    var result = documentRef.getElementById('gachaResult');
    if (result) result.innerHTML = '';

    // 激活卡牌 - 使用现有 renderDrawnCard
    state.currentTaskId = task.id;
    state.canReplace = false; // 多抽激活的卡牌不允许换卡

    // 写回 classic 的 task cache（startTask / findDrawnTask 的唯一来源）。
    setCurrentDrawnTask(task);

    var stage = renderDrawnCard(task, 0, state.canReplace);
    if (result && stage) {
      result.appendChild(stage);
      // 激活的卡真正进入结果区 → card_shown（沿用当前 session）。
      reportUnifiedGachaCardShown(task.id, {
        source: 'multi_draw',
        surface: 'multi_activated',
        pool: state.pool
      });
    }
  }

  // ------------------------------------------------------------------
  // 关怀抽卡（care-draw API 编排）
  // ------------------------------------------------------------------
  async function drawGachaWithCategory(includeCategory, excludeCategory) {
    if (state.isDrawing) return;
    state.isDrawing = true;
    // 发起新抽卡 → 本链结束。
    resetReplaceChain();
    // 一次新的抽卡 → 开启新的行为事件 session。
    beginUnifiedGachaSession();
    var actionId = newUnifiedGachaActionId('care');
    var btn = documentRef.getElementById('gachaBtn');
    if (btn) btn.disabled = true;
    var result = documentRef.getElementById('gachaResult');
    result.innerHTML = '<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>正在抽卡...</p></div>';

    try {
      var availableMinutes = getGachaAvailableMinutes();
      var r = await api('/api/gacha/care-draw', {
        method: 'POST',
        body: JSON.stringify({
          pool: state.pool,
          energy: state.energy,
          available_time: availableMinutes,
          preferred_tag: state.selectedTag || null,
          include_category: includeCategory || null,
          exclude_category: excludeCategory || null
        })
      });
      if (r.task) {
        if (r.pool) state.pool = r.pool;
        state.canReplace = r.can_replace !== false;
        state.currentTaskId = r.task.id;
        // 写回 classic 的 task cache。
        setCurrentDrawnTask(r.task);
        // 服务端返回真实 task 后才记录 card_drawn。
        var careTaskId = unifiedGachaTaskId(r.task.id);
        var careContext = {
          source: 'care_draw',
          pool: r.pool || state.pool,
          energy: state.energy,
          available_time: availableMinutes,
          preferred_tag: state.selectedTag || null,
          include_category: includeCategory || null,
          exclude_category: excludeCategory || null
        };
        sendUnifiedGachaEvent('card_drawn', careTaskId, careContext,
          unifiedGachaEventId(actionId, 'card_drawn', careTaskId));
        // "帮我选"（关怀模态的同科/换口味两条路径走 /api/gacha/care-draw）
        // 成功返回新牌 → 记录 help_me_choose。
        sendUnifiedGachaEvent('help_me_choose', careTaskId, {
          include_category: includeCategory || null,
          exclude_category: excludeCategory || null,
          pool: careContext.pool
        }, unifiedGachaEventId(actionId, 'help_me_choose', careTaskId));
        result.innerHTML = '';
        var stage = renderDrawnCard(r.task, 0, state.canReplace);
        result.appendChild(stage);
        // 卡片真正进入结果区后才记录 card_shown。
        reportUnifiedGachaCardShown(careTaskId,
          { source: 'care_draw', surface: 'result', pool: careContext.pool }, actionId);
        await playCardFlyAnimation(r.task);
        updateDiscardPileVisual();
      } else {
        result.innerHTML = '<div class="empty-state mt24"><i class="fa-solid fa-box-open"></i><p>卡池空了，明天继续！</p></div>';
        state.currentTaskId = null;
      }
    } catch (e) {
      toast(e.message || '抽卡失败', 'err');
      result.innerHTML = '';
      state.currentTaskId = null;
    }

    if (btn) btn.disabled = false;
    state.isDrawing = false;
    refreshGachaStats();
  }

  // 清当前卡（currentTaskId / canReplace）；**不清** classic 的 multiDrawResults
  // （保持迁移前的原语义）。
  function resetCurrentCard() {
    state.currentTaskId = null;
    state.canReplace = false;
  }

  return {
    // 初始化（标签 / 精力 / 卡池监听）
    init: init,
    // 换卡链
    resetReplaceChain: resetReplaceChain,
    readAllowRepeatReplaced: readAllowRepeatReplaced,
    showReplaceReason: showReplaceReason,
    doReplace: doReplace,
    // session / event
    beginUnifiedGachaSession: beginUnifiedGachaSession,
    endUnifiedGachaSession: endUnifiedGachaSession,
    getUnifiedGachaSessionId: getUnifiedGachaSessionId,
    newUnifiedGachaEventId: newUnifiedGachaEventId,
    newUnifiedGachaActionId: newUnifiedGachaActionId,
    unifiedGachaEventId: unifiedGachaEventId,
    unifiedGachaTaskId: unifiedGachaTaskId,
    sendUnifiedGachaEvent: sendUnifiedGachaEvent,
    reportUnifiedGachaCardShown: reportUnifiedGachaCardShown,
    getDeliverySnapshot: getDeliverySnapshot,
    // 抽卡
    getGachaAvailableMinutes: getGachaAvailableMinutes,
    drawGacha: drawGacha,
    drawGachaMulti: drawGachaMulti,
    activateMultiCard: activateMultiCard,
    drawGachaWithCategory: drawGachaWithCategory,
    resetCurrentCard: resetCurrentCard,
    // 只读状态快照（诊断用；不暴露内部可变对象）
    getStateSnapshot: function () {
      return {
        energy: state.energy,
        pool: state.pool,
        canReplace: state.canReplace,
        replacedTaskId: state.replacedTaskId,
        replacedTaskIds: state.replacedTaskIds.slice(),
        allowRepeatReplaced: state.allowRepeatReplaced,
        currentTaskId: state.currentTaskId,
        selectedTag: state.selectedTag,
        isDrawing: state.isDrawing
      };
    }
  };
}

// AR03-P3-F：gacha 是 **应用级** 模块 —— **不** 导出页面级
// meta / mount / unmount 契约。页面切换不得结束抽卡 session / 换卡链。
// 装配根改用 `initAppScoped()`（应用级一次性启动钩子）。
