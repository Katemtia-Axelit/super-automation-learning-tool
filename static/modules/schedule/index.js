// static/modules/schedule/index.js - AR03-G12 真实生产 ESM owner
//
// 拥有「日程」页的**全部日程业务实现**与**唯一业务状态**：
//   - 状态：schedDate / slots / weeklyData / dailyData（owner 闭包私有）；
//   - 日期切换：shiftDate
//   - 日程网格：renderSchedule
//   - 日程格编辑：editSlot（owner 内部私有）
//   - 活动管理器：openActivityMgr / closeActivityMgr / loadActivityList
//     （loadActivityList 为 owner 内部私有）/ addActivity / deleteActivity
//     （deleteActivity 为 owner 内部私有）
//
// 与迁移前 static/app.js 的 SCHEDULE 段落**逐条语义一致**：
//   - schedDate 初值仍是 new Date()；日期字符串仍是
//     schedDate.toISOString().slice(0, 10)（UTC 日期，不改成 local date，
//     不改时区语义）；
//   - renderSchedule 的真实请求顺序仍是
//     GET /api/schedule/slots → GET /api/schedule/weekly →
//     GET /api/schedule/daily?date=<当前日期>；
//   - 星期索引仍是 (getDay() === 0 ? 6 : getDay() - 1).toString()；
//     dailyData 命中 slot_id 时优先 daily activity，否则回退 weekly activity；
//   - 网格仍写入 #schedGrid；空结果仍显示「暂无日程时段」；
//     每个 .sched-slot 点击后仍调用 editSlot；
//   - editSlot 仍使用原生 prompt('活动名称:', 当前值)，取消不发请求；
//     确认后 POST /api/schedule/daily，payload 精确为
//     { date, slot_id, activity }；成功后刷新 renderSchedule 并
//     toast('已保存','suc')；异常 toast(e.message || '保存失败','err')；
//   - openActivityMgr 仍先 showModal('activityMgrModal') 再触发
//     loadActivityList；loadActivityList 仍请求 GET /api/schedule/activities，
//     加载中 / 空态 / 失败文案与既有行为一致，HTML 转义方式保持原样
//     （不顺手改业务 / 安全策略）；
//   - addActivity 仍读取 activityNewName / activityNewType /
//     activityNewDuration；空名称 toast('请输入活动名称','err')；
//     payload 精确为 { name, type, duration_minutes }，type 默认 custom，
//     duration 使用 parseInt(value,10) || 30；成功后 toast('活动已添加','suc')、
//     清空名称并刷新列表；异常文案保持不变；
//   - deleteActivity 仍先 confirm('确定删除活动「' + name + '」？')，取消不发
//     请求；确认后 DELETE /api/schedule/activities/:id；成功
//     toast('已删除','suc') 并刷新列表；失败 toast(e.message || '删除失败','err')；
//   - closeActivityMgr 仍只关闭 activityMgrModal。
//
// 依赖注入约定（本模块 **不新建独立 API client**，不创建全局 Store、事件总线、
// 缓存或重试层）：
//   api(url, opts)         classic 层唯一的 fetch 封装
//   toast(msg, type)       classic 层唯一的提示条
//   showModal(id)          classic 层唯一的弹窗显示 helper
//   closeModal(id)         classic 层唯一的弹窗关闭 helper
//
// 业务实现**只有这一份**：classic 层（static/app.js）只保留薄 facade
// （memoized dynamic import + 依赖注入），不存在 classic/ESM 双份镜像。

/**
 * 创建「日程」模块 owner（唯一业务实现与状态持有者）。
 *
 * @param {Object} deps classic 层注入的共享帮助函数
 * @returns {Object} owner 暴露 classic 页面需要的入口
 */
export function createScheduleOwner(deps) {
  var d = deps || {};
  var api = typeof d.api === 'function' ? d.api : function () {
    return Promise.reject(new Error('api 未注入'));
  };
  var toast = typeof d.toast === 'function' ? d.toast : function () {};
  var showModal = typeof d.showModal === 'function' ? d.showModal : function () {};
  var closeModal = typeof d.closeModal === 'function' ? d.closeModal : function () {};

  // ---- owner 闭包私有状态（classic 层不再持有副本）----
  var schedDate = new Date();
  var slots = [];
  var weeklyData = {};
  var dailyData = [];

  function byId(id) {
    return document.getElementById(id);
  }

  /** 当前 UTC 日期字符串（YYYY-MM-DD），语义与迁移前完全一致。 */
  function currentDateStr() {
    return schedDate.toISOString().slice(0, 10);
  }

  /**
   * 切换日程日期（前一天 / 后一天）并重新渲染。
   * @param {number} d 偏移天数
   */
  function shiftDate(d) {
    schedDate.setDate(schedDate.getDate() + d);
    return renderSchedule();
  }

  /**
   * 渲染日程网格。真实请求顺序固定：
   *   GET /api/schedule/slots → GET /api/schedule/weekly →
   *   GET /api/schedule/daily?date=<当前日期>
   */
  async function renderSchedule() {
    var ds = currentDateStr();
    var dateEl = byId('schedDate');
    if (dateEl) dateEl.textContent = ds;
    try {
      slots = await api('/api/schedule/slots');
      weeklyData = await api('/api/schedule/weekly');
      dailyData = await api('/api/schedule/daily?date=' + ds);
    } catch (e) {
      toast('日程加载失败（可能数据库表未就绪）', 'err');
      slots = slots || [];
    }
    var dow = schedDate.getDay();
    var wd = weeklyData[(dow === 0 ? 6 : dow - 1).toString()] || {};
    var html = '';
    slots.forEach(function (s) {
      var daily = dailyData.find(function (d) { return d.slot_id === s.slot_id; });
      var activity = daily ? daily.activity : (wd[s.slot_id] ? wd[s.slot_id].activity : '');
      html += '<div class="sched-time"><div>' + s.start_time + '</div><div style="font-size:.65rem">' + s.end_time + '</div></div>';
      html += '<div class="sched-slot" data-slot="' + s.slot_id + '">' +
        '<input class="slot-act full-width" value="' + (activity || '').replace(/"/g, '&quot;') + '" placeholder="点击编辑..." readonly></div>';
    });
    var grid = byId('schedGrid');
    if (!grid) return;
    grid.innerHTML = html || '<div class="empty-state"><p>暂无日程时段</p></div>';
    grid.querySelectorAll('.sched-slot').forEach(function (el) {
      el.addEventListener('click', function () { editSlot(el.getAttribute('data-slot'), el); });
    });
  }

  /**
   * 编辑某个日程格的活动名称（原生 prompt；取消不发请求）。
   * owner 内部私有：仅由 renderSchedule 生成的 .sched-slot 点击触发。
   */
  async function editSlot(slotId, el) {
    var act = prompt('活动名称:', el.querySelector('.slot-act').value || '');
    if (act === null) return;
    try {
      await api('/api/schedule/daily', {
        method: 'POST',
        body: JSON.stringify({
          date: currentDateStr(),
          slot_id: slotId,
          activity: act
        })
      });
      renderSchedule();
      toast('已保存', 'suc');
    } catch (e) {
      toast(e.message || '保存失败', 'err');
    }
  }

  /** 打开活动管理器：先显示弹窗，再加载活动列表。 */
  async function openActivityMgr() {
    showModal('activityMgrModal');
    loadActivityList();
  }

  /** 关闭活动管理器（只关闭 activityMgrModal）。 */
  function closeActivityMgr() {
    closeModal('activityMgrModal');
  }

  /**
   * 加载活动列表（真实 GET /api/schedule/activities）。
   * owner 内部私有：仅由 openActivityMgr / addActivity / deleteActivity 调用。
   */
  async function loadActivityList() {
    var wrap = byId('activityList');
    if (!wrap) return;
    wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
    try {
      var items = await api('/api/schedule/activities');
      if (!items || !items.length) {
        wrap.innerHTML = '<div class="empty-state" style="padding:16px"><p>暂无活动</p></div>';
        return;
      }
      wrap.innerHTML = items.map(function (a) {
        var type = a.type || 'custom';
        var dur = a.duration_minutes != null ? a.duration_minutes : 30;
        return '<div class="activity-row" data-id="' + a.id + '">' +
          '<div><strong>' + String(a.name).replace(/</g, '&lt;') + '</strong>' +
          '<span style="color:var(--text-muted);font-size:.8rem;margin-left:8px">' + type + ' · ' + dur + '分</span></div>' +
          '<button type="button" class="btn danger sm activity-del-btn" data-id="' + a.id + '" data-name="' +
          String(a.name).replace(/"/g, '&quot;') + '"><i class="fa-solid fa-trash"></i></button></div>';
      }).join('');
      wrap.querySelectorAll('.activity-del-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
          deleteActivity(parseInt(btn.getAttribute('data-id'), 10), btn.getAttribute('data-name'));
        });
      });
    } catch (e) {
      wrap.innerHTML = '<p style="color:var(--text-muted)">活动列表加载失败</p>';
      toast(e.message || '活动列表加载失败', 'err');
    }
  }

  /** 添加活动（真实 POST /api/schedule/activities）。 */
  async function addActivity() {
    var nameEl = byId('activityNewName');
    if (!nameEl) return;
    var name = nameEl.value.trim();
    if (!name) {
      toast('请输入活动名称', 'err');
      return;
    }
    var body = {
      name: name,
      type: (byId('activityNewType').value || 'custom').trim() || 'custom',
      duration_minutes: parseInt(byId('activityNewDuration').value, 10) || 30
    };
    try {
      await api('/api/schedule/activities', { method: 'POST', body: JSON.stringify(body) });
      toast('活动已添加', 'suc');
      nameEl.value = '';
      loadActivityList();
    } catch (e) {
      toast(e.message || '添加失败', 'err');
    }
  }

  /**
   * 删除活动（真实 DELETE /api/schedule/activities/:id）。
   * owner 内部私有：仅由列表里的删除按钮触发。
   */
  function deleteActivity(id, name) {
    if (!confirm('确定删除活动「' + name + '」？')) return;
    api('/api/schedule/activities/' + id, { method: 'DELETE' }).then(function () {
      toast('已删除', 'suc');
      loadActivityList();
    }).catch(function (e) {
      toast(e.message || '删除失败', 'err');
    });
  }

  return {
    renderSchedule: renderSchedule,
    shiftDate: shiftDate,
    openActivityMgr: openActivityMgr,
    closeActivityMgr: closeActivityMgr,
    addActivity: addActivity
  };
}

export default {
  createScheduleOwner: createScheduleOwner
};
