// static/modules/gacha/presentation.js - AR03-G01 真实生产 ESM owner
//
// 拥有抽卡 presentation 域两个真正有副作用的 DOM 更新：
// - refreshGachaStats(api): GET /api/gacha/statistics -> #statDraws/#statRate/#statRejects
// - updateDiscardPileVisual(api): GET /api/discard-pile -> #discardPileStack/#discardPileEmpty
// 语义与旧 static/app.js 实现逐行一致（地址/格式/舍入/静默/上限5/class/CSS var/zIndex/empty）。
// 旧 app.js 仅保留最薄 classic facade，经 dynamic import 注入 api 后委托到此。

export async function refreshGachaStats(api) {
  try {
    var r = await api('/api/gacha/statistics');
    var se = document.getElementById('statDraws');
    var sr = document.getElementById('statRate');
    var srej = document.getElementById('statRejects');
    if (se) se.textContent = r.total_draws || 0;
    if (sr) sr.textContent = r.acceptance_rate != null ? (Math.round(r.acceptance_rate) + '%') : '--';
    if (srej) srej.textContent = r.rejections || 0;
  } catch (e) { /* 统计失败不阻塞 */ }
}

export async function updateDiscardPileVisual(api) {
  try {
    var items = await api('/api/discard-pile');
    var stack = document.getElementById('discardPileStack');
    var empty = document.getElementById('discardPileEmpty');
    if (!stack) return;
    // 移除所有视觉卡
    stack.querySelectorAll('.discard-pile-visual-card').forEach(function (el) { el.remove(); });
    // 显示空状态或堆叠卡
    if (empty) empty.style.display = items && items.length > 0 ? 'none' : 'flex';
    if (items && items.length > 0) {
      var show = Math.min(items.length, 5);
      for (var i = 0; i < show; i++) {
        var card = document.createElement('div');
        card.className = 'discard-pile-visual-card discard-pile-card';
        card.style.setProperty('--di', i);
        card.style.zIndex = i;
        stack.appendChild(card);
      }
    }
  } catch (e) { /* ignore */ }
}
