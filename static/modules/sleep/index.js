// static/modules/sleep/index.js - AR03-G10 真实生产 ESM owner
//
// 拥有「日程」页「睡眠追踪」面板（#sleepPanel）与「近 7 日能量」表
// （#weeklyEnergyTable）的**全部业务实现**：
//   - 日期工具：todayDateStr（UTC 日期字符串）
//   - 校验：validateBedTime（HH:MM 格式与小时/分钟边界 + 原有中文提示）
//   - 面板：loadSleepPanel
//   - 今日入睡记录：loadSleepInfo（真实 GET /api/state/sleep）
//   - 保存睡眠记录：saveSleep（真实 POST /api/state/sleep）
//   - 近七日能量表：loadWeeklyEnergyTable（真实 GET /api/state/weekly-energy）
//
// 与迁移前 static/app.js 的 SLEEP TRACKING 段落**逐条语义一致**：
//   - todayDateStr 继续使用 new Date().toISOString().slice(0, 10)（UTC 日期，
//     不改成 local date，不改时区行为）；
//   - validateBedTime 的空值 / HH:MM 格式 / 小时 0-23 / 分钟 0-59 边界与
//     「请输入入睡时间」「入睡时间格式应为 HH:MM」「入睡时间无效」提示全部保留；
//   - GET /api/state/sleep 后只取 date === today 的那条记录，原样更新
//     #sleepBedTimeDisplay / #sleepStreakDisplay / #sleepBedTimeInput；
//   - POST /api/state/sleep 的 method / body 字段 / status='on_time' 不变；
//     成功后 toast、更新显示并触发 loadWeeklyEnergyTable，失败时保留原错误提示；
//   - GET /api/state/weekly-energy 后仍按 cutoff = 当前 UTC 日期减 6 天过滤；
//     空列表、无近七日数据、表格列顺序、原有占位文案与错误 toast 全部保留。
//
// 依赖注入约定（本模块 **不通过 window 查找任何私有 helper**，也 **不新建
// 独立 API client**，不创建全局 Store、事件总线、缓存或重试层）：
//   api(url, opts)   classic 层唯一的 fetch 封装
//   toast(msg,type)  classic 层唯一的提示条
//
// 业务实现**只有这一份**：classic 层（static/app.js）只保留薄 facade
// （dynamic import + 依赖注入），不存在 classic/ESM 双份镜像。

/**
 * 创建「睡眠追踪 + 近七日能量表」模块 owner（唯一业务实现持有者）。
 *
 * @param {Object} deps classic 层注入的共享帮助函数
 * @returns {Object} owner 暴露全部业务方法
 */
export function createSleepOwner(deps) {
  var d = deps || {};
  var api = typeof d.api === 'function' ? d.api : function () {
    return Promise.reject(new Error('api 未注入'));
  };
  var toast = typeof d.toast === 'function' ? d.toast : function () {};

  function byId(id) {
    return document.getElementById(id);
  }

  /** 今天的 UTC 日期字符串（YYYY-MM-DD）。 */
  function todayDateStr() {
    return new Date().toISOString().slice(0, 10);
  }

  /**
   * 校验入睡时间；返回 null 表示合法，否则返回中文错误提示。
   */
  function validateBedTime(val) {
    if (!val || !String(val).trim()) return '请输入入睡时间';
    if (!/^\d{2}:\d{2}$/.test(val)) return '入睡时间格式应为 HH:MM';
    var parts = val.split(':');
    var h = parseInt(parts[0], 10);
    var m = parseInt(parts[1], 10);
    if (isNaN(h) || isNaN(m) || h < 0 || h > 23 || m < 0 || m > 59) return '入睡时间无效';
    return null;
  }

  /** 加载睡眠面板：今日入睡记录 + 近七日能量表。 */
  async function loadSleepPanel() {
    await loadSleepInfo();
    await loadWeeklyEnergyTable();
  }

  /** 加载今日入睡时间与连续早睡天数（真实 GET /api/state/sleep）。 */
  async function loadSleepInfo() {
    var disp = byId('sleepBedTimeDisplay');
    if (!disp) return;
    try {
      var rows = await api('/api/state/sleep');
      var today = todayDateStr();
      var row = null;
      if (Array.isArray(rows)) {
        row = rows.find(function (r) { return r.date === today; });
      }
      var bed = row && row.bed_time ? row.bed_time : '';
      var streak = row && row.sleep_early_streak != null ? row.sleep_early_streak : 0;
      disp.textContent = bed || '--';
      byId('sleepStreakDisplay').textContent = String(streak);
      var inp = byId('sleepBedTimeInput');
      if (inp) inp.value = bed ? bed.slice(0, 5) : '';
    } catch (e) {
      toast('睡眠信息加载失败', 'err');
    }
  }

  /** 保存入睡时间（真实 POST /api/state/sleep）。 */
  async function saveSleep() {
    var inp = byId('sleepBedTimeInput');
    if (!inp) return;
    var val = inp.value;
    var errMsg = validateBedTime(val);
    if (errMsg) {
      toast(errMsg, 'err');
      return;
    }
    try {
      var r = await api('/api/state/sleep', {
        method: 'POST',
        body: JSON.stringify({ bed_time: val, status: 'on_time' })
      });
      toast('睡眠记录已保存', 'suc');
      byId('sleepBedTimeDisplay').textContent = r.bed_time || val;
      byId('sleepStreakDisplay').textContent = String(
        r.sleep_early_streak != null ? r.sleep_early_streak : 0
      );
      loadWeeklyEnergyTable();
    } catch (e) {
      toast(e.message || '保存失败', 'err');
    }
  }

  /** 渲染近七日能量表（真实 GET /api/state/weekly-energy）。 */
  async function loadWeeklyEnergyTable() {
    var wrap = byId('weeklyEnergyTable');
    if (!wrap) return;
    try {
      var rows = await api('/api/state/weekly-energy');
      if (!Array.isArray(rows) || !rows.length) {
        wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">暂无能量记录</p>';
        return;
      }
      var cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - 6);
      var cutoffStr = cutoff.toISOString().slice(0, 10);
      var filtered = rows.filter(function (r) { return r.date >= cutoffStr; });
      if (!filtered.length) {
        wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">暂无能量记录</p>';
        return;
      }
      var html = '<table class="energy-table"><thead><tr><th>日期</th><th>早</th><th>午</th><th>晚</th><th>基调</th></tr></thead><tbody>';
      filtered.forEach(function (r) {
        html += '<tr><td>' + r.date + '</td><td>' + (r.energy_morning != null ? r.energy_morning : '-') +
          '</td><td>' + (r.energy_afternoon != null ? r.energy_afternoon : '-') +
          '</td><td>' + (r.energy_evening != null ? r.energy_evening : '-') +
          '</td><td>' + (r.daily_tone || '-') + '</td></tr>';
      });
      html += '</tbody></table>';
      wrap.innerHTML = html;
    } catch (e) {
      wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">能量数据加载失败</p>';
      toast('能量数据加载失败', 'err');
    }
  }

  return {
    loadPanel: loadSleepPanel,
    loadSleepInfo: loadSleepInfo,
    saveSleep: saveSleep,
    loadWeeklyEnergyTable: loadWeeklyEnergyTable,
    todayDateStr: todayDateStr,
    validateBedTime: validateBedTime
  };
}

export default {
  createSleepOwner: createSleepOwner
};
