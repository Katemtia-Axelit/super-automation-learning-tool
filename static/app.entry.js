// static/app.entry.js - Phase 1 收紧版薄入口（type=module）
//
// 设计：
// - 这是"未来模块化"入口；Phase 1 仅做以下事：
//   1) 注册 nav 事件委托（统一走 event-bus page:change，监听者挂载/卸载）
//   2) 打印一次 module 加载报告到 console（验证 core + shared 完整）
//   3) 不动旧 app.js 的任何全局函数 → 36/36 E2E 必然不破
// - 旧 app.js 仍主导 UI；modules/* 在 Phase 3 真正接管
//
// 不依赖 import 旧 app.js（避免循环）。index.html 顺序：
//   <script src="core/event-bus.js">  ← 全局 SAL.core.eventBus
//   <script src="core/api.js">        ← SAL.core.api
//   <script src="core/ui.js">         ← SAL.core.ui.{toast,showModal,closeModal,escapeHtml}
//   <script src="core/theme.js">      ← SAL.core.theme
//   <script src="core/router.js">     ← SAL.core.router
//   <script src="app.js">             ← 旧 IIFE 全部全局函数
//   <script type="module" src="app.entry.js">  ← 本文件（薄入口）
//
// AR03-G13：静态 import「任务编辑器」ESM owner，并在**模块入口执行阶段**
// （classic app.js 已先执行、用户交互尚未开始）创建唯一 owner，**同步**绑定
// 既有同步入口名 window.openTaskEdit / window.buildDepList /
// window.addTagChip / window.saveTask / window.deleteCurrentTask。
// 刻意**不**使用动态 import：src/index.html 的 inline handler
// （openTaskEdit() / buildDepList(window._depSelected||[]) /
//   addTagChip('tf') / saveTask() / deleteCurrentTask()）必须立即可用。

import { createTaskEditorOwner } from './modules/tasks/editor.js';

const bus = (window.SAL && window.SAL.core && window.SAL.core.eventBus) || null;
const router = (window.SAL && window.SAL.core && window.SAL.core.router) || null;

// ---------------------------------------------------------------------------
// 任务编辑器 owner（AR03-G13）
// ---------------------------------------------------------------------------
// 依赖全部从 classic 层**读取并注入**（不新建 API client / Store / 事件总线）：
//   api / toast / showModal / closeModal / escapeHtml / normalizeCardType
//   —— classic 层唯一实现；
//   allTasks / allTags —— classic 层唯一数据来源（用 getter 注入，**不复制**
//     数组作为长期状态）；
//   loadTasks / loadTags / deleteTask —— classic 层唯一既有行为，owner 只
//     调用，不迁移、不复制。
function createEditorOwnerFromClassic() {
  return createTaskEditorOwner({
    windowRef: window,
    documentRef: document,
    api: window.api,
    toast: window.toast,
    showModal: window.showModal,
    closeModal: window.closeModal,
    escapeHtml: window.escapeHtml,
    normalizeCardType: window.normalizeCardType,
    getTasks: function () { return window.allTasks || []; },
    getTags: function () { return window.allTags || []; },
    loadTasks: window.loadTasks,
    loadTags: window.loadTags,
    deleteTask: window.deleteTask
  });
}

const taskEditorOwner = createEditorOwnerFromClassic();

// 同步绑定既有入口名（src/index.html 的 inline handler 依赖这些全局）。
window.openTaskEdit = function (id) { return taskEditorOwner.openTaskEdit(id); };
window.buildDepList = function (selectedIds) { return taskEditorOwner.buildDepList(selectedIds); };
window.addTagChip = function (prefix) { return taskEditorOwner.addTagChip(prefix); };
window.saveTask = function () { return taskEditorOwner.saveTask(); };
window.deleteCurrentTask = function () { return taskEditorOwner.deleteCurrentTask(); };

function reportBoot() {
  const lines = [];
  lines.push('[app.entry] Phase 1 thin bootstrap');
  lines.push('  SAL.core.eventBus: ' + (bus ? 'OK' : 'MISSING'));
  lines.push('  SAL.core.api: ' + ((window.SAL && window.SAL.core && window.SAL.core.api) ? 'OK' : 'MISSING'));
  lines.push('  SAL.core.ui: ' + ((window.SAL && window.SAL.core && window.SAL.core.ui) ? 'OK' : 'MISSING'));
  lines.push('  SAL.core.theme: ' + ((window.SAL && window.SAL.core && window.SAL.core.theme) ? 'OK' : 'MISSING'));
  lines.push('  SAL.core.router: ' + (router ? 'OK' : 'MISSING'));
  lines.push('  SAL.core.state: ' + ((window.SAL && window.SAL.core && window.SAL.core.state) ? 'OK' : 'MISSING'));
  lines.push('  SAL.core.constants: ' + ((window.SAL && window.SAL.core && window.SAL.core.constants) ? 'OK' : 'MISSING'));
  lines.push('  SAL.core.ui.{modal,toast,theme,sandbox}: ' +
    ((window.SAL && window.SAL.core && window.SAL.core.ui &&
      window.SAL.core.ui.modal && window.SAL.core.ui.toast &&
      window.SAL.core.ui.theme && window.SAL.core.ui.sandbox)
      ? 'OK' : 'MISSING'));
  lines.push('  SAL.shared.{timer,xss,formatters}: ' +
    ((window.SAL && window.SAL.shared && window.SAL.shared.timer &&
      window.SAL.shared.xss && window.SAL.shared.formatters)
      ? 'OK' : 'MISSING'));
  // eslint-disable-next-line no-console
  console.log(lines.join('\n'));
}

function wireNav() {
  // nav 按钮统一通过 event-bus 广播 page:change；modules/* 可挂载/卸载
  const navs = document.querySelectorAll('.nav-btn[data-page]');
  navs.forEach(function (btn) {
    // 避免与旧 onclick=showPage(...) 冲突：用 addEventListener，不替换 onclick
    btn.addEventListener('click', function () {
      const page = btn.getAttribute('data-page');
      if (bus) bus.emit('page:change', { page: page });
    });
  });
  // 暴露 page:change 监听者给 modules 自行决定 mount/unmount
  if (bus) {
    bus.on('page:change', function (p) {
      // Phase 1 noop（modules/* 仍由旧 app.js 主动调用）；
      // Phase 3 接入时这里 dispatch to active module
      // eslint-disable-next-line no-console
      console.debug('[app.entry] page:change', p);
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function () {
    reportBoot();
    wireNav();
  });
} else {
  reportBoot();
  wireNav();
}
