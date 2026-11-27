// core/constants.js - 共享常量（Phase 1 收紧版）
// 避免 modules/* 直接 import 魔术数字；旧 app.js 全局变量不变。
(function () {
  const PAGES = ['gacha', 'tasks', 'schedule', 'knowledge', 'config'];
  const POOL_IDS = ['fragment', 'tomato', 'deep'];
  const POOL_LABELS = {
    fragment: '碎片卡池',
    tomato: '番茄卡池',
    deep: '深度卡池',
  };
  const ENERGY_LEVELS = ['low', 'medium', 'high'];
  window.SAL = window.SAL || {};
  window.SAL.core = window.SAL.core || {};
  window.SAL.core.constants = {
    PAGES: PAGES,
    POOL_IDS: POOL_IDS,
    POOL_LABELS: POOL_LABELS,
    ENERGY_LEVELS: ENERGY_LEVELS,
  };
})();
