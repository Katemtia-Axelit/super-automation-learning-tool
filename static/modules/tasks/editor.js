// static/modules/tasks/editor.js - AR03-G13 真实生产 ESM owner
//
// 拥有「任务编辑器」模态框（#taskModal）的**全部业务实现**与**唯一状态**：
//   - owner 闭包私有状态：
//       originalCardType —— 原始卡类型（显示侧归一后的值）；
//       tagLists['tf']   —— 当前标签数组；
//       depSelected      —— 当前依赖选择数组；
//   - 对外方法（既有同步入口名，src/index.html 的 inline handler 不变）：
//       openTaskEdit(id) / buildDepList(selectedIds) / addTagChip('tf') /
//       saveTask() / deleteCurrentTask()；
//   - 内部私有：
//       setCardTypeSelect / getCardTypeSelect /
//       loadNoteOptionsForTaskModal / toggleExistingTag / addTagChipEl /
//       removeTagChip / readSelectedPrereqs / validatePrereqsLocal。
//
// 与迁移前 static/app.js 的编辑器段落**逐条语义一致**：
//   - openTaskEdit 同步完成 showModal('taskModal')、字段初始化/回填、
//     标签与依赖列表渲染；返回值保持 undefined；知识笔记选项加载仍是
//     fire-and-forget（**不** await 后才显示表单）；
//   - 新建任务：原始卡类型为 null、下拉默认 'standard'、POST **必须**
//     显式包含一个合法 task_type；
//   - 编辑旧卡：normal / other / NULL / 未知值经 normalizeCardType 显示为
//     'standard'，并把该**显示值**记为原始卡类型；用户**未实际改型**时
//     PUT **省略** task_type（绝不把用户历史旧值静默改写为 standard）；
//     用户**确实改型**时才写入新的合法值；
//   - 表单默认值、字段映射、任务名称校验、前置依赖自依赖校验、标签 chip
//     行为、知识笔记选项 GET /api/knowledge/notes（最多 200 项）、保存后的
//     closeModal → toast → loadTasks → loadTags 次序与错误提示全部保持；
//   - buildDepList 仍排除当前任务、按搜索过滤、最多显示 50 项、保留
//     「(已完成)」标记与 HTML 转义；window._depSelected 仍可被 HTML 的
//     inline input handler 读取；
//   - deleteCurrentTask 仍**委托**既有 deleteTask(id) 并立即 closeModal，
//     不复制任务卡删除 API 与 dependents 确认逻辑。
//
// 依赖注入约定（本模块 **不新建独立 API client**，不创建全局 Store、事件
// 总线、缓存、重试层，也不持有第二份 allTasks / allTags）：
//   windowRef / documentRef / api / toast / showModal / closeModal /
//   escapeHtml / normalizeCardType / getTasks / getTags / loadTasks /
//   loadTags / deleteTask
//
// 业务实现**只有这一份**：classic 层（static/app.js）不再持有任务编辑器
// 的影子实现；normalizeCardType、任务数据加载、任务卡渲染与 deleteTask
// 仍由 classic 层持有，本模块**注入调用**。
//
// 兼容性说明：owner 创建时为 window._depSelected 与
// window._tfOriginalCardType 安装可配置 getter/setter，读写**转发**到
// owner 闭包状态（不另存镜像状态）。window._tfTags 已被 owner 闭包状态
// 取代，本仓库无其它模块使用它，因此不再保留该全局。

export function createTaskEditorOwner(deps) {
  var d = deps || {};

  var windowRef = d.windowRef || null;
  var documentRef = d.documentRef || (windowRef ? windowRef.document : null);
  var api = typeof d.api === 'function' ? d.api : function () {
    return Promise.reject(new Error('api 未注入'));
  };
  var toast = typeof d.toast === 'function' ? d.toast : function () {};
  var showModal = typeof d.showModal === 'function' ? d.showModal : function () {};
  var closeModal = typeof d.closeModal === 'function' ? d.closeModal : function () {};
  var escapeHtml = typeof d.escapeHtml === 'function' ? d.escapeHtml : function (s) {
    return String(s == null ? '' : s);
  };
  var normalizeCardType = typeof d.normalizeCardType === 'function'
    ? d.normalizeCardType
    : function () { return 'standard'; };
  var getTasks = typeof d.getTasks === 'function' ? d.getTasks : function () { return []; };
  var getTags = typeof d.getTags === 'function' ? d.getTags : function () { return []; };
  var loadTasks = typeof d.loadTasks === 'function' ? d.loadTasks : function () {};
  var loadTags = typeof d.loadTags === 'function' ? d.loadTags : function () {};
  var deleteTask = typeof d.deleteTask === 'function' ? d.deleteTask : function () {};

  // ---- owner 闭包私有状态（classic 层不再持有副本）----
  var originalCardType = null; // 原始卡类型（显示侧归一后的值）
  var tagLists = {}; // 当前标签数组（按 prefix；'tf' = 任务模态框）
  var depSelected = []; // 当前依赖选择数组

  function tagList(prefix) {
    if (!tagLists[prefix]) tagLists[prefix] = [];
    return tagLists[prefix];
  }

  /** 任务模态框当前的标签数组。 */
  function currentTags() {
    return tagList('tf');
  }

  function byId(id) {
    return documentRef.getElementById(id);
  }

  // ------------------------------------------------------------------
  // 卡类型下拉
  // ------------------------------------------------------------------

  // 把卡类型下拉设为一个合法值。只接受四种正式值；任何其它输入
  // （历史值 / 攻击性字符串）一律回落到 'standard'，因此下拉的 value
  // 永远不可能是被注入的任意字符串。
  function setCardTypeSelect(value) {
    var sel = byId('tfCardType');
    if (!sel) return 'standard';
    var v = normalizeCardType(value);
    sel.value = v;
    return v;
  }

  // 读取当前下拉里的卡类型。**始终**返回四种正式值之一：
  // 即使 DOM 被外部篡改成任意字符串，也会归一回 'standard'。
  function getCardTypeSelect() {
    var sel = byId('tfCardType');
    if (!sel) return 'standard';
    return normalizeCardType(sel.value);
  }

  // ------------------------------------------------------------------
  // 依赖 / 标签
  // ------------------------------------------------------------------

  function readSelectedPrereqs() {
    var boxes = documentRef.querySelectorAll('#tfDepList input[type=checkbox]:checked');
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

  function buildDepList(selectedIds) {
    selectedIds = selectedIds || [];
    var searchEl = byId('tfDepSearch');
    var search = (searchEl ? searchEl.value : '').toLowerCase();
    var currentId = parseInt(byId('tfId').value, 10) || 0;
    var tasks = getTasks().filter(function (t) {
      if (!t.id || t.id === currentId) return false;
      if (search && t.name.toLowerCase().indexOf(search) < 0) return false;
      return true;
    }).slice(0, 50);
    var listEl = byId('tfDepList');
    listEl.innerHTML = tasks.map(function (t) {
      var checked = selectedIds.indexOf(t.id) >= 0 ? ' checked' : '';
      var done = t.completed ? ' (已完成)' : '';
      return '<label class="note-item" style="display:flex;align-items:center;gap:8px;cursor:pointer">' +
        '<input type="checkbox" class="dep-cb" value="' + t.id + '"' + checked + ' style="width:auto"> ' +
        escapeHtml(t.name) + done + ' <span class="note-meta">ID:' + t.id + '</span></label>';
    }).join('');
    listEl.querySelectorAll('.dep-cb').forEach(function (cb) {
      cb.addEventListener('change', function () { depSelected = readSelectedPrereqs(); });
    });
    depSelected = selectedIds.slice();
  }

  function toggleExistingTag(name) {
    var list = currentTags();
    var idx = list.indexOf(name);
    if (idx >= 0) list.splice(idx, 1);
    else list.push(name);
    byId('tfTagChips').innerHTML = '';
    list.forEach(function (x) { addTagChipEl('tf', x); });
  }

  function addTagChip(prefix) {
    var inp = byId(prefix + 'TagInput');
    var tagName = inp.value.trim();
    if (!tagName) return;
    inp.value = '';
    var list = tagList(prefix);
    if (list.indexOf(tagName) < 0) {
      list.push(tagName);
      addTagChipEl(prefix, tagName);
    }
  }

  function addTagChipEl(prefix, tagName) {
    var chips = byId(prefix + 'TagChips');
    var chip = documentRef.createElement('span');
    chip.className = 'tag-chip';
    chip.innerHTML = tagName + '<span class="remove" data-prefix="' + prefix + '" data-name="' +
      tagName.replace(/"/g, '&quot;') + '">&times;</span>';
    chip.querySelector('.remove').addEventListener('click', function () {
      removeTagChip(this.getAttribute('data-prefix'), this.getAttribute('data-name'));
    });
    chips.appendChild(chip);
  }

  function removeTagChip(prefix, tagName) {
    var list = tagList(prefix);
    tagLists[prefix] = list.filter(function (x) { return x !== tagName; });
    byId(prefix + 'TagChips').innerHTML = '';
    tagLists[prefix].forEach(function (x) { addTagChipEl(prefix, x); });
  }

  // ------------------------------------------------------------------
  // 知识笔记选项（fire-and-forget）
  // ------------------------------------------------------------------

  async function loadNoteOptionsForTaskModal() {
    var sel = byId('tfLinkedNote');
    if (!sel || sel.options.length > 1) return;
    try {
      var notes = await api('/api/knowledge/notes');
      notes.slice(0, 200).forEach(function (n) {
        var opt = documentRef.createElement('option');
        opt.value = n.path || '';
        opt.textContent = (n.category || '') + ' / ' + (n.name || n.path || '');
        sel.appendChild(opt);
      });
    } catch (e) { /* ignore */ }
  }

  // ------------------------------------------------------------------
  // 对外入口
  // ------------------------------------------------------------------

  function openTaskEdit(id) {
    showModal('taskModal');
    byId('tfId').value = '';
    byId('taskModalTitle').textContent = '新建任务';
    byId('taskDelBtn').style.display = 'none';
    loadNoteOptionsForTaskModal();
    byId('tfExistingTags').innerHTML = getTags().map(function (t) {
      return '<span class="badge bg-blue tag-pick" data-tag="' + escapeHtml(t.name) + '">' + escapeHtml(t.name) + '</span>';
    }).join('');
    documentRef.querySelectorAll('#tfExistingTags .tag-pick').forEach(function (el) {
      el.addEventListener('click', function () { toggleExistingTag(el.getAttribute('data-tag')); });
    });
    buildDepList([]);
    // 新建任务：卡类型默认「标准卡」。这是**展示侧默认值**，
    // saveTask 时会显式提交一个合法 task_type。
    originalCardType = null;
    setCardTypeSelect('standard');
    if (id) {
      var t = getTasks().find(function (x) { return x.id === id; });
      if (t) {
        byId('tfId').value = t.id;
        byId('taskModalTitle').textContent = '编辑: ' + t.name;
        byId('taskDelBtn').style.display = 'inline-flex';
        byId('tfName').value = t.name || '';
        byId('tfCat').value = t.category || 'study';
        byId('tfPri').value = t.priority || 5;
        byId('tfTime').value = t.estimated_time || 30;
        byId('tfDdl').value = t.deadline || '';
        byId('tfRes').value = t.resistance || 'medium';
        byId('tfEnergy').value = t.energy_required || 'medium';
        byId('tfRepeat').value = t.repeat_type || 'none';
        byId('tfProfile').value = t.task_profile || 'deadline_flexible';
        byId('tfDesc').value = t.description || '';
        // 编辑旧卡：下拉显示**归一后**的卡类型（历史 normal/other/NULL →
        // 显示为「标准卡」），并记住这个归一值供 saveTask 判断「用户是否
        // 真的改型」。归一只影响显示，**绝不**改写用户旧数据。
        originalCardType = normalizeCardType(t.task_type);
        setCardTypeSelect(originalCardType);
        buildDepList(t.prerequisite_ids || []);
        byId('tfTagChips').innerHTML = '';
        var list = currentTags();
        list.length = 0;
        (t.tags || []).forEach(function (x) {
          list.push(x);
          addTagChipEl('tf', x);
        });
        return;
      }
    }
    ['tfName', 'tfDesc', 'tfDdl'].forEach(function (x) { byId(x).value = ''; });
    byId('tfCat').value = 'study';
    byId('tfPri').value = '5';
    byId('tfTime').value = '30';
    byId('tfRes').value = 'medium';
    byId('tfEnergy').value = 'medium';
    byId('tfRepeat').value = 'none';
    byId('tfProfile').value = 'deadline_flexible';
    byId('tfLinkedNote').value = '';
    byId('tfTagChips').innerHTML = '';
    currentTags().length = 0;
    buildDepList([]);
  }

  async function saveTask() {
    var id = byId('tfId').value;
    var name = byId('tfName').value.trim();
    if (!name) { toast('请填写任务名称', 'err'); return; }
    var prereqIds = readSelectedPrereqs();
    var localErr = validatePrereqsLocal(id, prereqIds);
    if (localErr) { toast(localErr, 'err'); return; }
    var data = {
      name: name,
      category: byId('tfCat').value,
      priority: parseInt(byId('tfPri').value, 10),
      estimated_time: parseInt(byId('tfTime').value, 10),
      deadline: byId('tfDdl').value || null,
      resistance: byId('tfRes').value,
      energy_required: byId('tfEnergy').value,
      repeat_type: byId('tfRepeat').value,
      task_profile: byId('tfProfile').value,
      description: byId('tfDesc').value,
      tags: currentTags().slice(),
      prerequisite_ids: prereqIds
    };
    var linkedNote = byId('tfLinkedNote').value;
    if (linkedNote) data.linked_note_path = linkedNote;
    // ---- 卡类型（M02-S01-G02-W03）--------------------------------
    // 新建：始终提交一个**合法**的 task_type（默认标准卡）。
    // 编辑旧卡：
    //   * 用户**没有**改类型 → **省略** PUT 的 task_type 字段。
    //     （旧卡原值可能是 normal/other/NULL；因为显示侧归一成了
    //      'standard'，如果照抄归一值提交，就等于把用户的历史旧数据
    //      静默改写成 standard —— 这是产品事故，必须避免。）
    //   * 用户**确实**改成了别的类型 → 才提交 task_type。
    var selectedCardType = getCardTypeSelect();
    if (!id) {
      data.task_type = selectedCardType;
    } else if (typeof originalCardType === 'string' &&
               selectedCardType !== originalCardType) {
      // 只有在「原值已知」且「用户确实改型」时才提交。
      data.task_type = selectedCardType;
    }
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
      // 后端 400（例如 task_type 非法）通过现有 toast 告知用户。
      toast(e.message || '保存失败', 'err');
    }
  }

  function deleteCurrentTask() {
    var id = byId('tfId').value;
    if (id) { deleteTask(id); closeModal('taskModal'); }
  }

  // ------------------------------------------------------------------
  // 兼容既有 HTML / characterization harness 的全局访问器
  // ------------------------------------------------------------------

  if (windowRef) {
    Object.defineProperty(windowRef, '_depSelected', {
      configurable: true,
      enumerable: true,
      get: function () { return depSelected.slice(); },
      set: function (v) {
        depSelected = Array.isArray(v) ? v.slice() : [];
      }
    });
    Object.defineProperty(windowRef, '_tfOriginalCardType', {
      configurable: true,
      enumerable: true,
      get: function () { return originalCardType; },
      set: function (v) {
        originalCardType = (typeof v === 'string') ? v : null;
      }
    });
  }

  return {
    openTaskEdit: openTaskEdit,
    buildDepList: buildDepList,
    addTagChip: addTagChip,
    saveTask: saveTask,
    deleteCurrentTask: deleteCurrentTask,
    // 只读状态句柄（调试 / 测试用；不暴露可变引用）
    getState: function () {
      return {
        originalCardType: originalCardType,
        tags: currentTags().slice(),
        depSelected: depSelected.slice()
      };
    }
  };
}

export default { createTaskEditorOwner: createTaskEditorOwner };
