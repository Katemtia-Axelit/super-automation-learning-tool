// static/modules/prompts/index.js - AR03-G05 真实生产 ESM owner
//
// 拥有「设置」页提示词文件浏览器（#promptPanel）的**全部业务实现**与
// **唯一会话状态**：
//   - 会话状态：promptFiles / promptCurrentContent / promptOriginalContent /
//     promptSelectedName / promptEditMode / 待保存内容（pendingSave）
//   - 列表：loadPromptList（真实 GET /api/prompts，安全 HTML 转义）
//   - 正文：loadPromptContent（真实 GET /api/prompts/<name>）
//   - 编辑：setPromptEditMode / enterPromptEdit / cancelPromptEdit
//   - 差异：computePromptDiff / previewPromptDiff / cancelPromptDiffModal
//   - 保存：confirmPromptSave（真实 PUT /api/prompts/<name>）
//   - 备份：refreshPromptBackupStatus（GET /api/prompts/<name>/backup/latest）
//   - 恢复：restorePromptLatest（POST /api/prompts/<name>/restore-latest）
//   - 复制：copyPromptContent（剪贴板 + execCommand fallback）
//
// 与迁移前 static/app.js 的 PROMPTS 段落**逐条语义一致**（空列表、失败、
// 取消、备份状态、编辑期间禁止切换、剪贴板 fallback、恢复失败的处理全部
// 保持不变）。
//
// 依赖注入约定（本模块 **不通过 window 查找任何私有 helper**，也 **不新建
// 独立 API client**，更不直接读取真实 filesystem）：
//   api(url, opts)   classic 层唯一的 fetch 封装
//   toast(msg,type)  classic 层唯一的提示条
//   showModal(id)    classic 层的模态打开
//   closeModal(id)   classic 层的模态关闭
//   escapeHtml(s)    classic 层的严格转义
//
// 状态**只有一份**：本模块内部持有，classic 层（static/app.js）只保留薄
// facade（dynamic import + 依赖注入），不存在 classic/ESM 双份镜像。

/**
 * 计算两段文本的逐行差异。
 *
 * 与迁移前 app.js 的 computePromptDiff 逐行一致：新增 / 删除 / 修改三型，
 * 最多返回前 80 行差异明细。
 *
 * @param {string} oldText
 * @param {string} newText
 * @returns {{added:number,removed:number,changed:number,lines:Array}}
 */
export function computePromptDiff(oldText, newText) {
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

/**
 * 创建提示词模块 owner（唯一状态持有者）。
 *
 * @param {Object} deps classic 层注入的共享帮助函数
 * @returns {Object} owner 暴露全部业务方法
 */
export function createPromptsOwner(deps) {
  var d = deps || {};
  var api = typeof d.api === 'function' ? d.api : function () {
    return Promise.reject(new Error('api 未注入'));
  };
  var toast = typeof d.toast === 'function' ? d.toast : function () {};
  var showModal = typeof d.showModal === 'function' ? d.showModal : function () {};
  var closeModal = typeof d.closeModal === 'function' ? d.closeModal : function () {};
  var escapeHtml = typeof d.escapeHtml === 'function'
    ? d.escapeHtml
    : function (s) { return String(s == null ? '' : s); };

  // —— 唯一会话状态（classic 层不持有镜像）——
  var promptFiles = [];
  var promptCurrentContent = '';
  var promptOriginalContent = '';
  var promptSelectedName = '';
  var promptEditMode = false;
  var pendingSave;

  // —— 状态新鲜度保护：过期回调不得覆盖较新的用户选择 ——
  var listGeneration = 0;     // 列表请求代际
  var contentGeneration = 0;   // 正文请求代际
  var backupGeneration = 0;    // 备份状态代际

  function byId(id) {
    return document.getElementById(id);
  }

  /** 切换只读 / 编辑模式（按钮组、提示文案、textarea readOnly、复制按钮）。 */
  function setPromptEditMode(on) {
    promptEditMode = !!on;
    var ta = byId('promptContentView');
    var readBtns = byId('promptReadBtns');
    var editBtns = byId('promptEditBtns');
    var hint = byId('promptModeHint');
    if (ta) ta.readOnly = !promptEditMode;
    if (readBtns) readBtns.classList.toggle('hidden', promptEditMode);
    if (editBtns) editBtns.classList.toggle('hidden', !promptEditMode);
    if (hint) {
      hint.textContent = promptEditMode
        ? '编辑模式：修改后请预览差异并确认保存（保存前自动备份）'
        : '默认只读；进入编辑模式后可预览差异并保存（保存前自动备份）';
    }
    var copyBtn = byId('promptCopyBtn');
    if (copyBtn) copyBtn.style.display = promptEditMode ? 'none' : '';
    var editBtn = byId('promptEditBtn');
    if (editBtn) editBtn.style.display = promptEditMode ? 'none' : '';
  }

  /** 刷新「恢复最近备份」按钮的可见性（真实备份状态）。 */
  async function refreshPromptBackupStatus() {
    var btn = byId('promptRestoreBtn');
    if (!btn || !promptSelectedName || promptEditMode) {
      if (btn) btn.style.display = 'none';
      return;
    }
    var myGeneration = ++backupGeneration;
    var wantedName = promptSelectedName;
    try {
      var r = await api('/api/prompts/' + encodeURIComponent(wantedName) + '/backup/latest');
      // 过期响应不得覆盖较新的用户选择。
      if (myGeneration !== backupGeneration) return;
      if (promptSelectedName !== wantedName) return;
      btn.style.display = r && r.exists ? '' : 'none';
    } catch (e) {
      if (myGeneration !== backupGeneration) return;
      btn.style.display = 'none';
    }
  }

  /** 加载提示词文件列表（真实 GET /api/prompts）。 */
  async function loadPromptList() {
    var list = byId('promptFileList');
    if (!list) return;
    if (promptEditMode) {
      toast('请先退出编辑模式', 'err');
      return;
    }
    list.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
    var myGeneration = ++listGeneration;
    try {
      var files = await api('/api/prompts');
      // 过期响应不得覆盖较新的用户操作。
      if (myGeneration !== listGeneration) return;
      promptFiles = files || [];
      if (!promptFiles.length) {
        list.innerHTML = '<div class="empty-state" style="padding:12px"><p>暂无提示词文件</p></div>';
        var ta = byId('promptContentView');
        if (ta) ta.value = '';
        var label = byId('promptCurrentLabel');
        if (label) label.textContent = '选择文件查看内容';
        promptCurrentContent = '';
        promptOriginalContent = '';
        promptSelectedName = '';
        contentGeneration++;   // 作废仍在途的正文请求
        return;
      }
      var html = promptFiles.map(function (f, idx) {
        var safe = escapeHtml(String(f.name));
        return '<div class="prompt-file-item" data-idx="' + idx + '">' + safe + '</div>';
      }).join('');
      list.innerHTML = html;
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
      if (myGeneration !== listGeneration) return;
      list.innerHTML = '<div class="empty-state" style="padding:12px"><p>提示词列表加载失败</p></div>';
      toast('提示词列表加载失败', 'err');
    }
  }

  /** 加载单个提示词文件内容（真实 GET /api/prompts/<name>）。 */
  async function loadPromptContent(name, el) {
    if (!name || promptEditMode) return;
    document.querySelectorAll('.prompt-file-item').forEach(function (x) {
      x.classList.remove('active');
    });
    if (el) el.classList.add('active');
    var myGeneration = ++contentGeneration;
    try {
      var r = await api('/api/prompts/' + encodeURIComponent(name));
      // 过期回调不得覆盖较新的用户选择。
      if (myGeneration !== contentGeneration) return;
      promptSelectedName = name;
      promptCurrentContent = (r && r.content) || '';
      promptOriginalContent = promptCurrentContent;
      var ta = byId('promptContentView');
      if (ta) ta.value = promptCurrentContent;
      var label = byId('promptCurrentLabel');
      if (label) label.textContent = name;
      refreshPromptBackupStatus();
    } catch (e) {
      if (myGeneration !== contentGeneration) return;
      toast(e.message || '加载提示词失败', 'err');
    }
  }

  /** 进入编辑模式。 */
  function enterPromptEdit() {
    if (!promptSelectedName) {
      toast('请先选择提示词文件', 'err');
      return;
    }
    promptOriginalContent = promptCurrentContent;
    setPromptEditMode(true);
    var restoreBtn = byId('promptRestoreBtn');
    if (restoreBtn) restoreBtn.style.display = 'none';
  }

  /** 取消编辑（脏内容需要用户确认放弃）。 */
  function cancelPromptEdit() {
    var ta = byId('promptContentView');
    var dirty = ta && ta.value !== promptOriginalContent;
    if (dirty && !confirm('内容已修改，确定放弃编辑？')) return;
    if (ta) ta.value = promptOriginalContent;
    promptCurrentContent = promptOriginalContent;
    setPromptEditMode(false);
    refreshPromptBackupStatus();
  }

  /** 预览修改差异（真实 DOM 渲染 + 打开差异模态）。 */
  function previewPromptDiff() {
    if (!promptSelectedName) return;
    var ta = byId('promptContentView');
    var newContent = ta ? ta.value : '';
    if (newContent === promptOriginalContent) {
      toast('内容未变化', 'inf');
      return;
    }
    var diff = computePromptDiff(promptOriginalContent, newContent);
    var summary = byId('promptDiffSummary');
    if (summary) {
      summary.innerHTML =
        '原内容 ' + promptOriginalContent.length + ' 字符 → 新内容 ' + newContent.length + ' 字符<br>' +
        '新增行 ' + diff.added + ' · 删除行 ' + diff.removed + ' · 修改行 ' + diff.changed;
    }
    var html = '';
    diff.lines.forEach(function (ln) {
      if (ln.type === 'add') html += '<div class="diff-line-add">+ ' + escapeHtml(ln.text) + '</div>';
      else if (ln.type === 'rem') html += '<div class="diff-line-rem">- ' + escapeHtml(ln.text) + '</div>';
      else html += '<div class="diff-line-chg">~ ' + escapeHtml(ln.old) + ' → ' + escapeHtml(ln.new) + '</div>';
    });
    if (!diff.lines.length) html = '<div style="color:var(--text-muted)">（无逐行差异，可能仅末尾换行不同）</div>';
    var lines = byId('promptDiffLines');
    if (lines) lines.innerHTML = html;
    pendingSave = newContent;
    showModal('promptDiffModal');
  }

  /** 关闭差异模态并丢弃待保存内容（取消语义）。 */
  function cancelPromptDiffModal() {
    closeModal('promptDiffModal');
    pendingSave = undefined;
  }

  /** 确认保存（真实 PUT /api/prompts/<name>，后端先自动备份）。 */
  async function confirmPromptSave() {
    if (!promptSelectedName || pendingSave === undefined) return;
    var content = pendingSave;
    try {
      await api('/api/prompts/' + encodeURIComponent(promptSelectedName), {
        method: 'PUT',
        body: JSON.stringify({ content: content })
      });
      closeModal('promptDiffModal');
      promptCurrentContent = content;
      promptOriginalContent = content;
      var ta = byId('promptContentView');
      if (ta) ta.value = content;
      setPromptEditMode(false);
      toast('保存成功', 'suc');
      refreshPromptBackupStatus();
      pendingSave = undefined;
    } catch (e) {
      toast(e.message || '保存失败，原文件未破坏（已先备份）', 'err');
    }
  }

  /** 恢复最近一次备份（真实 POST restore-latest，随后重新读取正文）。 */
  async function restorePromptLatest() {
    if (!promptSelectedName || promptEditMode) return;
    if (!confirm('确定恢复最近一次备份？当前文件会先自动备份。')) return;
    try {
      await api('/api/prompts/' + encodeURIComponent(promptSelectedName) + '/restore-latest', {
        method: 'POST',
        body: JSON.stringify({})
      });
      var r = await api('/api/prompts/' + encodeURIComponent(promptSelectedName));
      promptCurrentContent = (r && r.content) || '';
      promptOriginalContent = promptCurrentContent;
      var ta = byId('promptContentView');
      if (ta) ta.value = promptCurrentContent;
      toast('已恢复最近备份', 'suc');
      refreshPromptBackupStatus();
    } catch (e) {
      toast(e.message || '恢复失败', 'err');
    }
  }

  /** 复制当前提示词内容到剪贴板（含 execCommand fallback）。 */
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
      var ta = byId('promptContentView');
      if (!ta) return;
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

  return {
    setPromptEditMode: setPromptEditMode,
    computePromptDiff: computePromptDiff,
    refreshPromptBackupStatus: refreshPromptBackupStatus,
    loadPromptList: loadPromptList,
    loadPromptContent: loadPromptContent,
    enterPromptEdit: enterPromptEdit,
    cancelPromptEdit: cancelPromptEdit,
    previewPromptDiff: previewPromptDiff,
    cancelPromptDiffModal: cancelPromptDiffModal,
    confirmPromptSave: confirmPromptSave,
    restorePromptLatest: restorePromptLatest,
    copyPromptContent: copyPromptContent,
    // 只读快照（供诊断 / 测试断言使用，不构成第二份状态源）。
    getState: function () {
      return {
        files: promptFiles.slice(),
        currentContent: promptCurrentContent,
        originalContent: promptOriginalContent,
        selectedName: promptSelectedName,
        editMode: promptEditMode,
        hasPendingSave: pendingSave !== undefined
      };
    }
  };
}

export default { createPromptsOwner: createPromptsOwner, computePromptDiff: computePromptDiff };
