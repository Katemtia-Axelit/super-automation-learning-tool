// static/modules/agent-readonly/index.js - AR03-G07 真实生产 ESM owner
//
// 拥有「设置」页 Agent 只读浏览面板（#agentReadonlyModal / #agentReadonlyPanel）
// 的**全部业务实现**与**唯一会话状态**：
//   - 会话状态：agentRoList（Agent 列表快照）/ agentRawSubdir（Raw 当前
//     子目录）/ agentVaultSubject（Vault 当前子目录）
//   - 配置提示：refreshAgentReadonlyHint（CONFIG 表单与本面板共用同一实现）
//   - 模态：openAgentReadonlyModal / closeAgentReadonlyModal
//   - tab 切换：switchAgentTab（agents / raw / vault）
//   - Agent 列表与详情：loadAgentRoList / selectAgentReadonly
//   - 提示词只读查看：GET /api/agent/agents/<id>/prompt
//   - Raw 浏览：GET /api/agent/files/raw + /api/agent/files/raw/content
//   - Vault 浏览：GET /api/agent/files/vault + /api/agent/files/vault/content
//
// 与迁移前 static/app.js 的 AGENT READONLY 段落**逐条语义一致**：空列表
// 文案、失败文案、加载中占位、上级目录导航、当前目录/文件路径提示、
// 提示词标签与「文件缺失」分支全部保持不变。
//
// **只读语义（硬约束）**：本模块只调用 GET 读取型 API，绝不调用
// /api/agent/process、/api/agent/save-note、/api/agent/import-tasks 等
// 写入型 endpoint；绝不直接读写真实 Vault / filesystem。
//
// 依赖注入约定（本模块 **不通过 window 查找任何私有 helper**，也 **不新建
// 独立 API client**，不创建全局 Store 或事件总线）：
//   api(url, opts)   classic 层唯一的 fetch 封装
//   toast(msg,type)  classic 层唯一的提示条
//   showModal(id)    classic 层的模态打开
//   closeModal(id)   classic 层的模态关闭
//   escapeHtml(s)    classic 层的严格转义
//
// 状态**只有一份**：本模块内部持有，classic 层（static/app.js）只保留薄
// facade（dynamic import + 依赖注入），不存在 classic/ESM 双份镜像。

/**
 * 渲染「只读浏览」提示文案（CONFIG 表单提示 + 面板横幅共用）。
 *
 * 与迁移前 app.js 的 refreshAgentReadonlyHint 逐字一致：
 *   - 有 API Key → '只读浏览模式：可查看 Agent 与文件，本页不执行 Agent、不写入 Vault。'
 *   - 无 API Key → '未配置 API Key：只读浏览仍可用；运行 Agent 需在上方填入密钥（本模式不执行）。'
 *
 * 该函数是**唯一实现**：classic 层通过 ESM owner 调用它，不复制第二份逻辑。
 *
 * @param {Object|null} cfg /api/config 的返回体
 */
export function renderAgentReadonlyHint(cfg) {
  var hint = document.getElementById('agentReadonlyHint');
  var banner = document.getElementById('agentReadonlyBanner');
  var hasKey = cfg && (cfg.has_openai_key || cfg.has_claude_key);
  var msg = hasKey
    ? '只读浏览模式：可查看 Agent 与文件，本页不执行 Agent、不写入 Vault。'
    : '未配置 API Key：只读浏览仍可用；运行 Agent 需在上方填入密钥（本模式不执行）。';
  if (hint) hint.textContent = msg;
  if (banner) banner.textContent = msg;
  return msg;
}

/**
 * 创建 Agent 只读浏览模块 owner（唯一状态持有者）。
 *
 * @param {Object} deps classic 层注入的共享帮助函数
 * @returns {Object} owner 暴露全部业务方法
 */
export function createAgentReadonlyOwner(deps) {
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
  var agentRoList = [];
  var agentRawSubdir = '';
  var agentVaultSubject = '';

  // —— 状态新鲜度保护：过期响应不得覆盖较新的用户选择 ——
  var hintGeneration = 0;      // 配置提示请求代际
  var listGeneration = 0;      // Agent 列表请求代际
  var promptGeneration = 0;    // Agent 提示词请求代际
  var rawListGeneration = 0;   // Raw 目录列表请求代际
  var rawContentGeneration = 0; // Raw 正文请求代际
  var vaultListGeneration = 0;   // Vault 目录列表请求代际
  var vaultContentGeneration = 0; // Vault 正文请求代际

  function byId(id) {
    return document.getElementById(id);
  }

  /** 刷新只读提示（CONFIG 表单与 Agent 面板共用同一实现）。 */
  function refreshHint(cfg) {
    return renderAgentReadonlyHint(cfg);
  }

  /** 打开 Agent 只读浏览模态，并加载默认 tab（agents）。 */
  async function openModal() {
    showModal('agentReadonlyModal');
    var myGeneration = ++hintGeneration;
    try {
      var cfg = await api('/api/config');
      if (myGeneration !== hintGeneration) return;
      refreshHint(cfg);
    } catch (e) { /* ignore：配置读取失败不影响只读浏览 */ }
    switchTab('agents');
    loadAgentList();
  }

  /** 关闭 Agent 只读浏览模态。 */
  function closeModal_() {
    closeModal('agentReadonlyModal');
  }

  /** 切换 tab（agents / raw / vault）。 */
  function switchTab(tab) {
    document.querySelectorAll('.agent-ro-tab').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-agent-tab') === tab);
    });
    var tabAgents = byId('agentTabAgents');
    var tabRaw = byId('agentTabRaw');
    var tabVault = byId('agentTabVault');
    if (tabAgents) tabAgents.classList.toggle('hidden', tab !== 'agents');
    if (tabRaw) tabRaw.classList.toggle('hidden', tab !== 'raw');
    if (tabVault) tabVault.classList.toggle('hidden', tab !== 'vault');
    if (tab === 'raw') loadRawList(agentRawSubdir);
    if (tab === 'vault') loadVaultList(agentVaultSubject);
  }

  /** 加载 Agent 列表（真实 GET /api/agent/agents）。 */
  async function loadAgentList() {
    var wrap = byId('agentRoList');
    if (!wrap) return;
    wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
    var myGeneration = ++listGeneration;
    try {
      var list = await api('/api/agent/agents');
      // 过期响应不得覆盖较新的用户操作。
      if (myGeneration !== listGeneration) return;
      agentRoList = list || [];
      if (!agentRoList.length) {
        wrap.innerHTML = '<p style="color:var(--text-muted)">暂无 Agent</p>';
        return;
      }
      wrap.innerHTML = agentRoList.map(function (a) {
        return '<div class="agent-ro-item" data-id="' + escapeHtml(String(a.id)) + '"><i class="fa-solid ' +
          escapeHtml(String(a.icon || 'fa-robot')) + '"></i> ' + escapeHtml(String(a.name)) + '</div>';
      }).join('');
      wrap.querySelectorAll('.agent-ro-item').forEach(function (el) {
        el.addEventListener('click', function () {
          selectAgent(el.getAttribute('data-id'), el);
        });
      });
      selectAgent(agentRoList[0].id, wrap.querySelector('.agent-ro-item'));
    } catch (e) {
      if (myGeneration !== listGeneration) return;
      wrap.innerHTML = '<p style="color:var(--text-muted)">Agent 列表加载失败</p>';
      toast(e.message || 'Agent 列表加载失败', 'err');
    }
  }

  /** 选中某个 Agent：渲染详情 + 只读加载提示词（真实 GET .../prompt）。 */
  async function selectAgent(id, el) {
    document.querySelectorAll('#agentRoList .agent-ro-item').forEach(function (x) {
      x.classList.remove('active');
    });
    if (el) el.classList.add('active');
    var agent = agentRoList.find(function (a) { return a.id === id; });
    var detail = byId('agentRoDetail');
    var ta = byId('agentRoPromptView');
    if (!agent || !detail) return;
    var actions = (agent.action_labels || agent.actions || []).join('；') || '无';
    detail.innerHTML =
      '<p><strong>' + escapeHtml(String(agent.name)) + '</strong>（' + escapeHtml(String(id)) + '）</p>' +
      '<p>' + escapeHtml(String(agent.desc || '')) + '</p>' +
      '<p>输入：' + escapeHtml(String(agent.input_type_label || agent.input_type)) + '</p>' +
      '<p>写操作（本模式禁用）：' + escapeHtml(String(actions)) + '</p>' +
      '<p>提示词文件：' + escapeHtml(String(agent.prompt_file || '-')) + '</p>';
    if (ta) ta.value = '加载中...';
    var myGeneration = ++promptGeneration;
    try {
      var pr = await api('/api/agent/agents/' + encodeURIComponent(id) + '/prompt');
      // 过期响应不得覆盖较新的 Agent 选择。
      if (myGeneration !== promptGeneration) return;
      var label = byId('agentRoPromptLabel');
      if (label) {
        label.textContent = '提示词内容（只读）' +
          (pr.exists ? ' · ' + pr.size + ' 字符' : ' · 文件缺失');
      }
      if (ta) ta.value = pr.exists ? (pr.content || '') : '（提示词文件不存在）';
    } catch (e) {
      if (myGeneration !== promptGeneration) return;
      if (ta) ta.value = '';
      toast(e.message || '提示词加载失败', 'err');
    }
  }

  /** 列出 Raw 目录（真实 GET /api/agent/files/raw）。 */
  async function loadRawList(subdir) {
    agentRawSubdir = subdir || '';
    var wrap = byId('agentRawList');
    var pathEl = byId('agentRawPath');
    if (!wrap) return;
    wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
    if (pathEl) pathEl.textContent = '当前目录：' + (agentRawSubdir || '未分类/');
    var myGeneration = ++rawListGeneration;
    try {
      var q = agentRawSubdir ? '?subdir=' + encodeURIComponent(agentRawSubdir) : '';
      var r = await api('/api/agent/files/raw' + q);
      // 过期响应不得覆盖较新的目录选择。
      if (myGeneration !== rawListGeneration) return;
      var html = '';
      if (agentRawSubdir) {
        html += '<div class="agent-ro-item" data-raw-nav=".."><i class="fa-solid fa-arrow-up"></i> 上级</div>';
      }
      (r.subdirs || []).forEach(function (d) {
        html += '<div class="agent-ro-item" data-raw-dir="' + escapeHtml(String(d.name)) +
          '"><i class="fa-solid fa-folder"></i> ' + escapeHtml(String(d.name)) +
          ' (' + escapeHtml(String(d.file_count)) + ')</div>';
      });
      (r.files || []).forEach(function (f) {
        html += '<div class="agent-ro-item" data-raw-file="' + escapeHtml(String(f.path)) +
          '"><i class="fa-solid fa-file-lines"></i> ' + escapeHtml(String(f.name)) + '</div>';
      });
      if (!html) html = '<p style="color:var(--text-muted);padding:8px">暂无 txt 文件</p>';
      wrap.innerHTML = html;
      wrap.querySelectorAll('[data-raw-nav]').forEach(function (el) {
        el.addEventListener('click', function () {
          loadRawList(parentOf(agentRawSubdir));
        });
      });
      wrap.querySelectorAll('[data-raw-dir]').forEach(function (el) {
        el.addEventListener('click', function () {
          var name = el.getAttribute('data-raw-dir');
          var next = agentRawSubdir ? agentRawSubdir + '/' + name : name;
          loadRawList(next);
        });
      });
      wrap.querySelectorAll('[data-raw-file]').forEach(function (el) {
        el.addEventListener('click', function () {
          loadRawContent(el.getAttribute('data-raw-file'));
        });
      });
    } catch (e) {
      if (myGeneration !== rawListGeneration) return;
      wrap.innerHTML = '<p style="color:var(--text-muted)">Raw 列表加载失败</p>';
      toast(e.message || 'Raw 列表加载失败', 'err');
    }
  }

  /** 读取 Raw 文件内容（真实 GET /api/agent/files/raw/content）。 */
  async function loadRawContent(path) {
    var box = byId('agentRawContent');
    if (!box) return;
    box.textContent = '加载中...';
    var myGeneration = ++rawContentGeneration;
    try {
      var r = await api('/api/agent/files/raw/content?path=' + encodeURIComponent(path));
      if (myGeneration !== rawContentGeneration) return;
      box.textContent = r.content || '';
      var pathEl = byId('agentRawPath');
      if (pathEl) pathEl.textContent = '文件：' + path + '（' + (r.size || 0) + ' 字节）';
    } catch (e) {
      if (myGeneration !== rawContentGeneration) return;
      box.textContent = '加载失败';
      toast(e.message || 'Raw 文件读取失败', 'err');
    }
  }

  /** 列出 Vault 目录（真实 GET /api/agent/files/vault）。 */
  async function loadVaultList(subject) {
    agentVaultSubject = subject || '';
    var wrap = byId('agentVaultList');
    var pathEl = byId('agentVaultPath');
    if (!wrap) return;
    wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
    if (pathEl) pathEl.textContent = '当前目录：' + (agentVaultSubject || 'Vault 根目录');
    var myGeneration = ++vaultListGeneration;
    try {
      var q = agentVaultSubject ? '?subject=' + encodeURIComponent(agentVaultSubject) : '';
      var r = await api('/api/agent/files/vault' + q);
      // 过期响应不得覆盖较新的目录选择。
      if (myGeneration !== vaultListGeneration) return;
      var html = '';
      if (agentVaultSubject) {
        html += '<div class="agent-ro-item" data-vault-nav=".."><i class="fa-solid fa-arrow-up"></i> 上级</div>';
      }
      (r.dirs || []).forEach(function (d) {
        html += '<div class="agent-ro-item" data-vault-dir="' + escapeHtml(String(d.name)) +
          '"><i class="fa-solid fa-folder"></i> ' + escapeHtml(String(d.name)) +
          ' (' + escapeHtml(String(d.file_count)) + ')</div>';
      });
      (r.files || []).forEach(function (f) {
        html += '<div class="agent-ro-item" data-vault-file="' + escapeHtml(String(f.path)) +
          '"><i class="fa-solid fa-file-lines"></i> ' + escapeHtml(String(f.name)) + '</div>';
      });
      if (!html) html = '<p style="color:var(--text-muted);padding:8px">暂无 Markdown 文件</p>';
      wrap.innerHTML = html;
      wrap.querySelectorAll('[data-vault-nav]').forEach(function (el) {
        el.addEventListener('click', function () {
          loadVaultList(parentOf(agentVaultSubject));
        });
      });
      wrap.querySelectorAll('[data-vault-dir]').forEach(function (el) {
        el.addEventListener('click', function () {
          var name = el.getAttribute('data-vault-dir');
          var next = agentVaultSubject ? agentVaultSubject + '/' + name : name;
          loadVaultList(next);
        });
      });
      wrap.querySelectorAll('[data-vault-file]').forEach(function (el) {
        el.addEventListener('click', function () {
          loadVaultContent(el.getAttribute('data-vault-file'));
        });
      });
    } catch (e) {
      if (myGeneration !== vaultListGeneration) return;
      wrap.innerHTML = '<p style="color:var(--text-muted)">Vault 列表加载失败</p>';
      toast(e.message || 'Vault 列表加载失败', 'err');
    }
  }

  /** 读取 Vault 文件内容（真实 GET /api/agent/files/vault/content）。 */
  async function loadVaultContent(path) {
    var box = byId('agentVaultContent');
    if (!box) return;
    box.textContent = '加载中...';
    var myGeneration = ++vaultContentGeneration;
    try {
      var r = await api('/api/agent/files/vault/content?path=' + encodeURIComponent(path));
      if (myGeneration !== vaultContentGeneration) return;
      box.textContent = r.content || '';
      var pathEl = byId('agentVaultPath');
      if (pathEl) pathEl.textContent = '文件：' + path + '（' + (r.size || 0) + ' 字节）';
    } catch (e) {
      if (myGeneration !== vaultContentGeneration) return;
      box.textContent = '加载失败';
      toast(e.message || 'Vault 文件读取失败', 'err');
    }
  }

  /** 由「a/b/c」推出上级目录「a/b」。 */
  function parentOf(p) {
    return p && p.indexOf('/') >= 0 ? p.slice(0, p.lastIndexOf('/')) : '';
  }

  return {
    refreshHint: refreshHint,
    openModal: openModal,
    closeModal: closeModal_,
    switchTab: switchTab,
    loadAgentList: loadAgentList,
    selectAgent: selectAgent,
    loadRawList: loadRawList,
    loadRawContent: loadRawContent,
    loadVaultList: loadVaultList,
    loadVaultContent: loadVaultContent,
    // 只读快照（供诊断 / 测试断言使用，不构成第二份状态源）。
    getState: function () {
      return {
        agentRoList: agentRoList.slice(),
        agentRawSubdir: agentRawSubdir,
        agentVaultSubject: agentVaultSubject
      };
    }
  };
}

export default {
  createAgentReadonlyOwner: createAgentReadonlyOwner,
  renderAgentReadonlyHint: renderAgentReadonlyHint
};
