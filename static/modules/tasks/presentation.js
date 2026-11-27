// static/modules/tasks/presentation.js - AR03-G03 真实生产 ESM owner
//
// 拥有「任务」页 #taskGrid 的真实筛选 + DOM 绘制：
//   - 搜索（#taskSearch）与筛选（#taskFilter: unlocked/all/daily/weekly/urgent）
//   - 标签筛选（selectedTagFilter + allTags 命中）
//   - 空态、按状态分组的徽章（已完成 / 弃牌堆 / 阻塞）
//   - 前置依赖阻塞提示（prereqHint）
//   - 任务卡操作按钮（编辑 / 完成 / 跳过 / 拒绝 / 弃牌 / 删除）
//   - 8000 字符批量拼接后一次性写入 #taskGrid
//
// 语义与迁移前 static/app.js 里的 renderTasks() 逐条一致；旧 app.js 现在只
// 保留最薄 classic facade（唯一共享 import promise + 旧 _renderLock /
// _renderPending 语义），**不再有任何第二份实现**。
//
// 依赖注入约定（本模块 **不通过 window 查找任何私有 helper**）：
//   getTasks()                    -> classic 层维护的 allTasks（唯一任务数组来源）
//   getTags()                     -> classic 层维护的 allTags
//   getSelectedTagFilter()        -> classic 层维护的 selectedTagFilter
//   prereqHint(task)              -> classic 层的前置阻塞提示
//   buildTaskCardHtml(task, opts) -> classic 层的任务卡 HTML
//   escapeHtml(s)                 -> classic 层的严格转义
//
// 本模块 **不持有** 任何任务数组 / 标签数组 / 用户可见状态：所有筛选条件都在
// 真正写 DOM 的那一刻从注入的 getter 读取，因此渲染出来的永远是最新状态。

/**
 * 按「搜索词 + 筛选器 + 标签」筛选任务。
 *
 * 与迁移前 app.js renderTasks() 内的筛选链完全一致（顺序、判定式、边界
 * 行为都不变）。纯函数：不读 DOM、不写 DOM。
 *
 * @param {Array} allTasks classic 层注入的真实任务数组
 * @param {Object} options
 *   - allTags: Array        classic 层注入的标签数组
 *   - selectedTagFilter: any classic 层注入的当前标签筛选（null = 不过滤）
 *   - search: string        当前搜索词（大小写不敏感）
 *   - filter: string        unlocked | all | daily | weekly | urgent
 * @returns {Array} 命中的任务数组
 */
export function selectTasks(allTasks, options) {
  var opts = options || {};
  var allTags = opts.allTags || [];
  var selectedTagFilter = opts.selectedTagFilter;
  var search = String(opts.search == null ? '' : opts.search).toLowerCase();
  var filter = opts.filter;

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
  return tasks;
}

/**
 * 真实渲染任务网格（唯一 DOM 写入点）。
 *
 * @param {Object} deps 注入的 classic 层依赖（见文件头约定）
 * @returns {boolean} 是否真的写了一屏
 */
export function renderTaskGrid(deps) {
  var d = deps || {};
  var getTasks = typeof d.getTasks === 'function' ? d.getTasks : function () { return []; };
  var getTags = typeof d.getTags === 'function' ? d.getTags : function () { return []; };
  var getSelectedTagFilter = typeof d.getSelectedTagFilter === 'function'
    ? d.getSelectedTagFilter
    : function () { return null; };
  var prereqHint = typeof d.prereqHint === 'function' ? d.prereqHint : function () { return ''; };
  var buildTaskCardHtml = typeof d.buildTaskCardHtml === 'function'
    ? d.buildTaskCardHtml
    : function () { return ''; };
  var escapeHtml = typeof d.escapeHtml === 'function'
    ? d.escapeHtml
    : function (s) { return String(s == null ? '' : s); };

  // —— 数据与筛选条件：在写 DOM 的这一刻读取，保证渲染的永远是最新状态 ——
  var allTasks = getTasks();
  if (!allTasks) return false;
  var allTags = getTags() || [];

  var searchEl = document.getElementById('taskSearch');
  var filterEl = document.getElementById('taskFilter');
  var search = searchEl ? String(searchEl.value || '').toLowerCase() : '';
  var filter = filterEl ? String(filterEl.value || '') : '';

  var tasks = selectTasks(allTasks, {
    allTags: allTags,
    selectedTagFilter: getSelectedTagFilter(),
    search: search,
    filter: filter
  });

  var grid = document.getElementById('taskGrid');
  if (!grid) return false;

  if (tasks.length === 0) {
    grid.innerHTML = '<div class="empty-state"><i class="fa-solid fa-inbox"></i><p>没有匹配的任务</p></div>';
    return true;
  }

  var html = '', batch = '';
  for (var i = 0; i < tasks.length; i++) {
    var t = tasks[i];
    var statusIcons = [];
    if (t.completed) statusIcons.push('<span class="badge bg-green">已完成</span>');
    if (t.in_discard_pile) statusIcons.push('<span class="badge bg-red">弃牌堆</span>');
    if (!t.is_unlocked) statusIcons.push('<span class="badge bg-purple">阻塞</span>');
    var hint = prereqHint(t);
    var blockedNote = hint
      ? '<div class="card-meta mt8" style="color:var(--purple)">' + escapeHtml(hint) + '</div>'
      : '';
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
  return true;
}
