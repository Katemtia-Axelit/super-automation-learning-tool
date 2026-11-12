// static/modules/knowledge/index.js - AR03-G06 真实生产 ESM owner
//
// 拥有「知识库」页（#page-knowledge）的**全部真实知识浏览业务实现**与
// **唯一会话状态**：
//   - 会话状态：currentNotePath（当前笔记路径）
//   - 缓存状态：分类笔记缓存（noteCache + noteCacheCat）、当前分类
//     （currentCategory）
//   - 分类列表：loadCategories（真实 GET /api/knowledge/categories）
//   - 分类内笔记列表：loadCategoryNotes（真实 GET /api/knowledge/notes）
//   - 笔记正文：loadNote（真实 GET /api/knowledge/note-content/<encoded path>）
//   - 从卡片打开笔记：openNoteFromCard（真实 POST /api/knowledge/open-in-obsidian）
//   - 在 Obsidian 中打开当前笔记：openCurrentInObsidian（同上 endpoint）
//
// 与迁移前 static/app.js 的 KNOWLEDGE 段落**逐条语义一致**：首次加载自动
// 选择首分类 / 首笔记、分类点击切换、笔记点击加载正文、同分类缓存复用、
// 错误 toast 文案、Obsidian 打开反馈全部保持不变。
//
// 依赖注入约定（本模块 **不通过 window 查找任何私有 helper**，也 **不新建
// 独立 API client**，更不直接读取真实 filesystem）：
//   api(url, opts)     classic 层唯一的 fetch 封装
//   toast(msg, type)   classic 层唯一的提示条
//   mdToHtml(md)       classic 层唯一的同步 Markdown 呈现 helper
//                      （依赖页面既有 marked 全局与其 fallback；保持同步
//                        返回语义，不在本模块复制实现）
//   escapeHtml(s)      classic 层的严格转义
//
// 状态**只有一份**：本模块内部持有，classic 层（static/app.js）只保留薄
// facade（dynamic import + 依赖注入），不存在 classic/ESM 双份镜像。

/**
 * 创建知识浏览模块 owner（唯一状态持有者）。
 *
 * @param {Object} deps classic 层注入的共享帮助函数
 * @returns {Object} owner 暴露全部业务方法
 */
export function createKnowledgeOwner(deps) {
  var d = deps || {};
  var api = typeof d.api === 'function' ? d.api : function () {
    return Promise.reject(new Error('api 未注入'));
  };
  var toast = typeof d.toast === 'function' ? d.toast : function () {};
  var mdToHtml = typeof d.mdToHtml === 'function' ? d.mdToHtml : function () { return ''; };
  var escapeHtml = typeof d.escapeHtml === 'function'
    ? d.escapeHtml
    : function (s) { return String(s == null ? '' : s); };

  // —— 唯一会话状态（classic 层不持有镜像）——
  var currentNotePath = '';      // 当前选中的笔记路径
  var currentCategory = '';      // 当前选中的分类名
  var noteCache = {};            // 分类名 -> 已加载的笔记数组
  var noteCacheCat = null;       // 最近一次写入缓存的分类名
  // 当前 #catList 渲染出来的**原始**分类名（顺序与 DOM 一致）。
  // 显示用的 HTML 转义副本只用于 innerHTML，不参与任何精确匹配。
  var renderedCategoryNames = [];

  // —— 状态新鲜度保护：较旧的异步响应不得覆盖用户较新的选择 ——
  var categoriesGeneration = 0;  // 分类列表请求代际
  var notesGeneration = 0;       // 笔记列表请求代际
  var noteGeneration = 0;        // 笔记正文请求代际

  function byId(id) {
    return document.getElementById(id);
  }

  /**
   * 加载分类列表（真实 GET /api/knowledge/categories）。
   *
   * 首次加载时自动选中首个分类，并触发该分类的笔记列表加载。
   */
  async function loadCategories() {
    var myGeneration = ++categoriesGeneration;
    try {
      var cats = await api('/api/knowledge/categories');
      // 过期响应不得覆盖较新的用户操作。
      if (myGeneration !== categoriesGeneration) return;
      var list = byId('catList');
      if (!list) return;
      // 原始分类名单独保留一份：**只有原始名**能与后端返回的 n.category
      // 精确匹配（显示用的转义副本只用于 innerHTML，不会参与匹配）。
      var rawNames = (cats || []).map(function (c) {
        return String(c.name == null ? '' : c.name);
      });
      renderedCategoryNames = rawNames;
      list.innerHTML = (cats || []).map(function (c, idx) {
        var name = escapeHtml(rawNames[idx]);
        return '<div class="cat-item" data-id="' + escapeHtml(String(c.id == null ? '' : c.id)) +
          '" data-name="' + name + '">' + name +
          '<span class="cat-count">' + escapeHtml(String(c.count == null ? '' : c.count)) + '</span></div>';
      }).join('');
      list.querySelectorAll('.cat-item').forEach(function (el, idx) {
        el.addEventListener('click', function () {
          loadCategoryNotes(el.getAttribute('data-id'), rawNames[idx]);
        });
      });
      if (cats && cats.length > 0) {
        loadCategoryNotes(cats[0].id, cats[0].name);
      }
    } catch (e) {
      if (myGeneration !== categoriesGeneration) return;
      toast('加载分类失败', 'err');
    }
  }

  /**
   * 加载某个分类下的笔记列表（真实 GET /api/knowledge/notes）。
   *
   * 同分类复用已加载数据（迁移前的 P3-Bug-D 缓存语义保持不变）；
   * 分类切换后自动加载该分类的首篇笔记。
   */
  async function loadCategoryNotes(catId, catName) {
    currentCategory = catName == null ? '' : String(catName);
    // 高亮当前分类：DOM 里的 data-name 是转义后的副本，必须用**原始名**
    // 比较（renderedCategoryNames 保存原始名，顺序与 DOM 一致；#catList 在
    // #noteList 之前，因此前 N 项就是分类项，与迁移前行为一致）。
    var domItems = document.querySelectorAll('.cat-item');
    domItems.forEach(function (x, idx) {
      var raw = (idx < renderedCategoryNames.length)
        ? renderedCategoryNames[idx]
        : x.getAttribute('data-name');
      x.classList.toggle('active', raw === catName);
    });
    var myGeneration = ++notesGeneration;
    try {
      var notes;
      // 缓存逻辑——同分类复用已加载数据
      if (noteCacheCat === catName && noteCache[catName]) {
        notes = noteCache[catName];
      } else {
        notes = await api('/api/knowledge/notes');
        // 过期响应不得覆盖较新的用户选择。
        if (myGeneration !== notesGeneration) return;
        noteCache[catName] = notes;
        noteCacheCat = catName;
      }
      var filtered = (notes || []).filter(function (n) { return n.category === catName; });
      var list = byId('noteList');
      if (!list) return;
      list.innerHTML = '<div class="cat-item" style="font-size:.8rem;color:var(--text-muted)">' +
        escapeHtml(String(catName == null ? '' : catName)) + ' (' + filtered.length + '篇)</div>';
      filtered.forEach(function (n) {
        var item = document.createElement('div');
        item.className = 'note-item';
        item.textContent = n.name;
        item.addEventListener('click', function () { loadNote(n.path); });
        list.appendChild(item);
      });
      if (filtered.length > 0) loadNote(filtered[0].path);
    } catch (e) {
      if (myGeneration !== notesGeneration) return;
      toast('加载笔记列表失败', 'err');
    }
  }

  /**
   * 加载单篇笔记正文（真实 GET /api/knowledge/note-content/<encoded path>）。
   */
  async function loadNote(path) {
    currentNotePath = path;
    var myGeneration = ++noteGeneration;
    try {
      var r = await api('/api/knowledge/note-content/' + encodeURIComponent(path));
      // 过期响应不得覆盖较新的用户选择。
      if (myGeneration !== noteGeneration) return;
      var title = byId('knowTitle');
      if (title) title.innerHTML = '<i class="fa-solid fa-file-lines"></i> ' + path;
      var content = byId('knowContent');
      if (content) content.innerHTML = mdToHtml((r && r.content) || '');
      var actions = byId('knowActions');
      if (actions) actions.style.display = 'flex';
    } catch (e) {
      if (myGeneration !== noteGeneration) return;
      var content = byId('knowContent');
      if (content) content.innerHTML = '<div class="empty-state"><p>无法加载笔记</p></div>';
      toast(e.message || '加载失败', 'err');
    }
  }

  /**
   * 从任务卡直接打开某篇笔记（真实 POST /api/knowledge/open-in-obsidian）。
   *
   * 注意：该 endpoint 在后端会触发真实的 Obsidian 启动副作用，测试只允许
   * 静态检查其调用合同，禁止在自动化测试中真正调用。
   */
  async function openNoteFromCard(filePath) {
    try {
      await api('/api/knowledge/open-in-obsidian', {
        method: 'POST',
        body: JSON.stringify({ file_path: filePath })
      });
      toast('已在Obsidian中打开', 'suc');
    } catch (e) {
      toast('打开失败: ' + (e.message || e), 'err');
    }
  }

  /**
   * 在 Obsidian 中打开当前选中的笔记（真实 POST
   * /api/knowledge/open-in-obsidian）。
   *
   * 注意：同上，后端有真实副作用，测试禁止真正调用。
   */
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

  return {
    loadCategories: loadCategories,
    loadCategoryNotes: loadCategoryNotes,
    loadNote: loadNote,
    openNoteFromCard: openNoteFromCard,
    openCurrentInObsidian: openCurrentInObsidian,
    // 只读快照（供诊断 / 测试断言使用，不构成第二份状态源）。
    getState: function () {
      return {
        currentNotePath: currentNotePath,
        currentCategory: currentCategory,
        cachedCategories: Object.keys(noteCache),
        noteCacheCat: noteCacheCat
      };
    }
  };
}

export default { createKnowledgeOwner: createKnowledgeOwner };
