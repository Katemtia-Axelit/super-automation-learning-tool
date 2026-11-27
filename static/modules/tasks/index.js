// static/modules/tasks/index.js - AR03-P3-B 任务域 ESM 业务 owner
//
// 「有哪些任务」的 **唯一权威**。闭包私有持有：
//   - allTasks（任务数组）
//   - allTags（标签数组）
//   - selectedTagFilter（当前标签筛选）
//   - 渲染防重入锁（_renderLock / _renderPending）与渲染代际（generation）
//   - presentation 模块的 import promise
//
// 职责边界（与 Timer Owner 的分工，见计划 §3.2 B-2）：
//   - **Tasks Owner** = 数据权威：任务列表、标签、筛选、网格渲染、
//     批量标签提示、依赖关系图弹窗。
//   - **Timer Owner** = 计时面板 DOM 权威：任务下拉框（#timerTaskSelect）
//     由 Timer Owner 渲染，本 owner **只** 通过注入的 getTasks() 提供数据。
//     本模块 **不得** 出现任何下拉框渲染代码。
//
// 依赖注入（owner 内 **不** 偷查 window）：
//   api / toast / escapeHtml / documentRef
//   prereqHint / buildTaskCardHtml
//   onTasksChanged（任务数据变化后的下游通知，例如下拉框刷新）
//
// 语义保护（与迁移前 static/app.js 逐条一致，**不改产品行为**）：
//   - loadTasks：GET /api/tasks?unlocked_only=false；失败
//     toast('加载任务失败: ' + msg, 'err')；
//   - loadTags：GET /api/tags；标签徽章 HTML 结构、当前筛选高亮、
//     「清除」徽章；
//   - filterByTag(id)：置筛选 → 重载标签 → 重绘网格；
//   - renderTasks：**防重入 + 代际防过期**（最新过滤/标签/任务数据获胜，
//     多次请求只产生一次真实绘制）；
//   - openBatchTags / openDepGraph：文案与 DOM 结构逐字保持。

import { renderTaskGrid } from './presentation.js';

var meta = {
  name: 'tasks',
  version: '1.0.0-p3b',
  deps: ['timer']
};

/**
 * 创建任务域 owner 实例。
 * @param {Object} deps 注入依赖（见文件头说明）
 */
export function createTasksOwner(deps) {
  var d = deps || {};

  var api = typeof d.api === 'function' ? d.api : null;
  var toast = typeof d.toast === 'function' ? d.toast : function () {};
  var escapeHtml = typeof d.escapeHtml === 'function'
    ? d.escapeHtml
    : function (s) { return String(s == null ? '' : s); };
  var documentRef = d.documentRef || (typeof document !== 'undefined' ? document : null);
  var prereqHint = typeof d.prereqHint === 'function' ? d.prereqHint : function () { return ''; };
  var buildTaskCardHtml = typeof d.buildTaskCardHtml === 'function'
    ? d.buildTaskCardHtml
    : function () { return ''; };
  var onTasksChanged = typeof d.onTasksChanged === 'function'
    ? d.onTasksChanged
    : function () {};

  // ---- 唯一可变状态（闭包私有）------------------------------------------
  var allTasks = [];
  var allTags = [];
  var selectedTagFilter = null;
  var renderLock = false;
  var renderPending = false;
  var renderGeneration = 0;

  function requireApi() {
    if (!api) throw new Error('任务 owner 缺少 api 依赖');
    return api;
  }

  // ---- 只读访问器（供其它 owner 注入）----------------------------------
  /**
   * 当前任务数组（**权威**，不是副本）。
   * @returns {Array}
   */
  function getTasks() {
    return allTasks;
  }

  /**
   * 当前标签数组（**权威**）。
   * @returns {Array}
   */
  function getTags() {
    return allTags;
  }

  /**
   * 当前标签筛选（null = 不过滤）。
   * @returns {*}
   */
  function getSelectedTagFilter() {
    return selectedTagFilter;
  }

  /**
   * 按 id 找任务（在权威数组内查找）。
   * @param {number|string} taskId
   * @returns {Object|null}
   */
  function findTaskById(taskId) {
    var numericId = (typeof taskId === 'number') ? taskId : parseInt(taskId, 10);
    if (!isFinite(numericId) || numericId <= 0) return null;
    for (var i = 0; i < allTasks.length; i += 1) {
      if (allTasks[i] && Number(allTasks[i].id) === numericId) return allTasks[i];
    }
    return null;
  }

  // ---- 窄 setter（计划 §3.2 B-3）--------------------------------------
  /**
   * **窄**写入入口：直接设置权威任务数组。
   *
   * 存在的唯一理由：权威数据必须 **只有一份**，而外部（合成测试台 /
   * 装配根）需要一种方式把已知的任务集合 **注入** 这份权威数据 ——
   * 而不是绕开它另建一份副本（那会产生第二状态源）。
   *
   * 因此本 setter **替换** 权威数组（而不是追加），并触发下游通知
   * （下拉框刷新）。它 **不是** 业务 API 的替代品：真实数据仍只经
   * ``loadTasks()`` 从服务端取得。
   *
   * @param {Array} list
   * @returns {Array} 设置后的权威数组
   */
  function setTasks(list) {
    allTasks = Array.isArray(list) ? list : [];
    onTasksChanged();
    return allTasks;
  }

  /**
   * **窄**写入入口：设置权威标签数组。
   * @param {Array} list
   * @returns {Array}
   */
  function setTags(list) {
    allTags = Array.isArray(list) ? list : [];
    return allTags;
  }

  // ---- 加载 -------------------------------------------------------------
  /**
   * 加载任务列表并重绘网格。
   * @returns {Promise<Array>} 加载到的任务数组（失败时为原数组）
   */
  async function loadTasks() {
    try {
      allTasks = await requireApi()('/api/tasks?unlocked_only=false');
      await renderTasks();
      onTasksChanged();
    } catch (e) {
      toast('加载任务失败: ' + (e.message || ''), 'err');
    }
    return allTasks;
  }

  /**
   * 加载标签并重绘标签栏。
   */
  async function loadTags() {
    try {
      allTags = await requireApi()('/api/tags');
      renderTagBar();
    } catch (e) { /* ignore */ }
    return allTags;
  }

  /**
   * 渲染标签栏（当前筛选高亮 + 「清除」徽章）。
   */
  function renderTagBar() {
    if (!documentRef) return;
    var bar = documentRef.getElementById('tagsBar');
    if (!bar) return;
    bar.innerHTML = allTags.map(function (t) {
      return '<span class="badge ' + (selectedTagFilter === t.id ? 'bg-gold' : 'bg-blue') +
        '" onclick="filterByTag(' + escapeHtml(String(t.id)) + ')">' + escapeHtml(t.name) +
        ' (' + escapeHtml(String(t.task_count)) + ')</span>';
    }).join('');
    if (selectedTagFilter) {
      bar.innerHTML += '<span class="badge bg-red" onclick="filterByTag(null)">清除</span>';
    }
  }

  /**
   * 按标签筛选：置筛选 → 重载标签 → 重绘网格。
   * @param {number|string|null} id null = 清除筛选
   */
  async function filterByTag(id) {
    selectedTagFilter = id;
    await loadTags();
    await renderTasks();
  }

  // ---- 渲染（防重入 + 代际防过期）--------------------------------------
  /**
   * 重绘任务网格。
   *
   * 防重入语义（**必须完整保留**）：
   *   - 正在渲染时再来一次请求 → 记 pending，本次渲染结束后补渲染一次；
   *   - 每次请求领一个代际号；旧一代到达时 **不再写 DOM**，
   *     由最新一代负责 → 「最新过滤/标签/任务数据获胜」；
   *   - 多次请求只产生一次真实绘制（无事件洪水）。
   *
   * @returns {Promise<boolean>} 是否真的写了一屏
   */
  async function renderTasks() {
    var generation = ++renderGeneration;
    if (renderLock) { renderPending = true; return false; }
    renderLock = true;
    var rendered = false;
    try {
      if (generation === renderGeneration) {
        rendered = !!renderTaskGrid({
          getTasks: getTasks,
          getTags: getTags,
          getSelectedTagFilter: getSelectedTagFilter,
          prereqHint: prereqHint,
          buildTaskCardHtml: buildTaskCardHtml,
          escapeHtml: escapeHtml
        });
      }
    } catch (e) {
      console.error('[tasks] renderTasks', e);
    } finally {
      renderLock = false;
    }
    if (renderPending) {
      renderPending = false;
      await renderTasks();
    }
    return rendered;
  }

  // ---- 批量标签 / 依赖图 ------------------------------------------------
  /**
   * 批量标签提示（文案逐字保持）。
   */
  async function openBatchTags() {
    toast('选择任务后点击编辑，在标签栏中添加标签即可', 'inf');
  }

  /**
   * 打开依赖关系图弹窗。
   */
  async function openDepGraph() {
    try {
      var r = await requireApi()('/api/dependencies');
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
      var m = documentRef.createElement('div');
      m.className = 'modal-overlay';
      m.innerHTML = '<div class="modal" style="max-width:800px"><h2>依赖关系图</h2>' + view +
        '<div class="modal-actions"><button class="btn" id="depGraphClose">关闭</button></div></div>';
      documentRef.body.appendChild(m);
      m.querySelector('#depGraphClose').addEventListener('click', function () { m.remove(); });
      m.addEventListener('click', function (ev) { if (ev.target === m) m.remove(); });
    } catch (e) {
      toast(e.message || '加载失败', 'err');
    }
  }

  return {
    // --- 数据权威 ---
    getTasks: getTasks,
    getTags: getTags,
    getSelectedTagFilter: getSelectedTagFilter,
    findTaskById: findTaskById,
    // --- 窄 setter（唯一权威数据的注入入口，不产生第二份副本）---
    setTasks: setTasks,
    setTags: setTags,
    // --- 窄 setter（唯一权威数据的注入入口，不产生第二份副本）---
    setTasks: setTasks,
    setTags: setTags,
    // --- 加载 / 渲染 ---
    loadTasks: loadTasks,
    loadTags: loadTags,
    renderTasks: renderTasks,
    renderTagBar: renderTagBar,
    filterByTag: filterByTag,
    // --- 弹窗 ---
    openBatchTags: openBatchTags,
    openDepGraph: openDepGraph
  };
}

// ---------------------------------------------------------------------------
// registry Feature 契约（meta / mount / unmount）
// ---------------------------------------------------------------------------
//
// 本模块是 **页面级** Feature：任务页可见时 mount，���开时 unmount。
// unmount 只释放 **本模块自己的** 监听 / 待补渲染标记，
// **绝不** 清空权威数据（任务数据在下次 load 时刷新）。

var _mounted = false;

function mount(rootEl, ctx) {
  if (_mounted) return;
  _mounted = true;
  var owner = (typeof window !== 'undefined' && window.__tasksOwner) ? window.__tasksOwner : null;
  if (owner) {
    try {
      owner.loadTags();
      owner.loadTasks();
    } catch (e) { console.error('[tasks] mount', e); }
  }
  var bus = (typeof window !== 'undefined' && window.SAL && window.SAL.core && window.SAL.core.eventBus) || null;
  if (bus) bus.emit('module:mounted', { name: meta.name });
}

function unmount(rootEl) {
  if (!_mounted) return;
  _mounted = false;
  var bus = (typeof window !== 'undefined' && window.SAL && window.SAL.core && window.SAL.core.eventBus) || null;
  if (bus) bus.emit('module:unmounted', { name: meta.name });
}

export { meta, mount, unmount };
export default { meta: meta, mount: mount, unmount: unmount };
