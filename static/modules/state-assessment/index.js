// static/modules/state-assessment/index.js - AR03-G09 真实生产 ESM owner
//
// 拥有「日程」页「今日状态评估」面板（#stateAssessmentPanel）与模态
// （#stateAssessmentModal）的**全部业务实现**与**唯一业务状态**：
//   - 业务状态：assessmentQuestions（题目快照）/ assessmentAnswers（当前答案）
//   - 展示常量：TONE_LABELS（基调中文名）
//   - 评分展示：formatAssessmentScore
//   - 面板：loadPanel / loadSummary / loadHistory
//   - 模态：openModal / closeModal / renderAssessmentForm / save
//
// 与迁移前 static/app.js 的「STATE ASSESSMENT」段落**逐条语义一致**：
//   - 初始评分默认 3；滑块 min=1 / max=5 / step=1；
//   - input 事件更新答案并同步「当前: N」数值；
//   - 题目文本只执行原有的 `<` → `&lt;` 转义；
//   - 今日已完成时恢复原 answers；否则全部落到默认 3；
//   - 历史固定取 days=7，且最多展示 7 条；
//   - GET / POST 失败时的 loading 占位、错误占位、toast 文案、
//     modal 关闭 / 保留行为全部保持不变；
//   - 保存成功后仍关闭 modal、显示成功 toast 并刷新 summary / history。
//
// 依赖注入约定（本模块 **不通过 window 查找任何私有 helper**，也 **不新建
// 独立 API client**，不创建全局 Store 或事件总线）：
//   api(url, opts)   classic 层唯一的 fetch 封装
//   toast(msg,type)  classic 层唯一的提示条
//   showModal(id)    classic 层的模态打开
//   closeModal(id)   classic 层的模态关闭
//
// 状态**只有一份**：本模块内部持有，classic 层（static/app.js）只保留薄
// facade（dynamic import + 依赖注入），不存在 classic/ESM 双份镜像。

/**
 * 创建「今日状态评估」模块 owner（唯一状态持有者）。
 *
 * @param {Object} deps classic 层注入的共享帮助函数
 * @returns {Object} owner 暴露全部业务方法
 */
export function createStateAssessmentOwner(deps) {
  var d = deps || {};
  var api = typeof d.api === 'function' ? d.api : function () {
    return Promise.reject(new Error('api 未注入'));
  };
  var toast = typeof d.toast === 'function' ? d.toast : function () {};
  var showModal = typeof d.showModal === 'function' ? d.showModal : function () {};
  var closeModal = typeof d.closeModal === 'function' ? d.closeModal : function () {};

  // —— 唯一业务状态（classic 层不持有镜像）——
  var assessmentQuestions = [];
  var assessmentAnswers = {};

  // —— 展示常量（唯一实现）——
  var TONE_LABELS = { high: '高能量', normal: '正常', low: '低能量', rest: '休息' };

  function byId(id) {
    return document.getElementById(id);
  }

  /** 评分展示格式化（唯一实现）。 */
  function formatAssessmentScore(v) {
    if (v == null || v === '') return '-';
    return String(v);
  }

  /** 加载「今日状态评估」面板：先 summary，再 history。 */
  async function loadPanel() {
    await loadSummary();
    await loadHistory();
  }

  /** 渲染今日状态摘要 + 按钮文案。 */
  async function loadSummary() {
    var wrap = byId('stateAssessmentSummary');
    var btn = byId('stateAssessmentOpenBtn');
    if (!wrap) return;
    wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">加载中...</p>';
    try {
      var r = await api('/api/state/assessment');
      if (r.completed) {
        var tone = TONE_LABELS[r.daily_tone] || r.daily_tone || '-';
        wrap.innerHTML =
          '<div class="state-scores">' +
          '<div class="state-score"><div class="num">' + formatAssessmentScore(r.energy_score) + '</div><div class="lbl">精力</div></div>' +
          '<div class="state-score"><div class="num">' + formatAssessmentScore(r.focus_score) + '</div><div class="lbl">专注</div></div>' +
          '<div class="state-score"><div class="num">' + formatAssessmentScore(r.mood_score) + '</div><div class="lbl">情绪</div></div>' +
          '<div class="state-score"><div class="num" style="font-size:1rem">' + tone + '</div><div class="lbl">基调</div></div>' +
          '</div>';
        if (btn) btn.innerHTML = '<i class="fa-solid fa-pen"></i> 修改评估';
      } else {
        wrap.innerHTML = '<div class="empty-state" style="padding:12px"><p>今日还没有评估</p></div>';
        if (btn) btn.innerHTML = '<i class="fa-solid fa-pen"></i> 填写评估';
      }
    } catch (e) {
      wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">状态评估加载失败</p>';
      toast(e.message || '状态评估加载失败', 'err');
    }
  }

  /** 渲染近 7 日评估历史（最多 7 条）。 */
  async function loadHistory() {
    var wrap = byId('stateAssessmentHistory');
    if (!wrap) return;
    try {
      var rows = await api('/api/state/assessment/history?days=7');
      if (!rows || !rows.length) {
        wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">暂无历史记录</p>';
        return;
      }
      var html = '<table class="energy-table"><thead><tr><th>日期</th><th>精力</th><th>专注</th><th>情绪</th><th>基调</th></tr></thead><tbody>';
      rows.slice(0, 7).forEach(function (r) {
        html += '<tr><td>' + r.date + '</td><td>' + formatAssessmentScore(r.energy_score) +
          '</td><td>' + formatAssessmentScore(r.focus_score) +
          '</td><td>' + formatAssessmentScore(r.mood_score) +
          '</td><td>' + (TONE_LABELS[r.daily_tone] || r.daily_tone || '-') + '</td></tr>';
      });
      html += '</tbody></table>';
      wrap.innerHTML = html;
    } catch (e) {
      wrap.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">历史记录加载失败</p>';
    }
  }

  /** 打开评估模态并加载题目与答案。 */
  async function openModal() {
    var form = byId('stateAssessmentForm');
    if (!form) return;
    form.innerHTML = '<p style="color:var(--text-muted)">加载中...</p>';
    showModal('stateAssessmentModal');
    try {
      var r = await api('/api/state/assessment');
      var qResp = await api('/api/state/questions');
      assessmentQuestions = r.questions || qResp.questions || [];
      assessmentAnswers = {};
      if (r.completed && r.answers) {
        assessmentAnswers = Object.assign({}, r.answers);
      }
      renderForm();
    } catch (e) {
      form.innerHTML = '<p style="color:var(--text-muted)">加载失败</p>';
      toast(e.message || '评估表单加载失败', 'err');
    }
  }

  /** 渲染问题表单（滑块 + 当前数值）。 */
  function renderForm() {
    var form = byId('stateAssessmentForm');
    if (!form || !assessmentQuestions.length) {
      if (form) form.innerHTML = '<p style="color:var(--text-muted)">暂无评估问题</p>';
      return;
    }
    form.innerHTML = assessmentQuestions.map(function (q) {
      var val = assessmentAnswers[q.id] != null ? assessmentAnswers[q.id] : 3;
      assessmentAnswers[q.id] = val;
      return '<div class="assess-q" data-qid="' + q.id + '">' +
        '<label>' + String(q.q).replace(/</g, '&lt;') + '</label>' +
        '<input type="range" min="1" max="5" step="1" value="' + val + '" class="assess-range" data-qid="' + q.id + '">' +
        '<div class="assess-q-val">当前: <span class="assess-val-num">' + val + '</span></div></div>';
    }).join('');
    form.querySelectorAll('.assess-range').forEach(function (inp) {
      inp.addEventListener('input', function () {
        var qid = inp.getAttribute('data-qid');
        var v = parseInt(inp.value, 10);
        assessmentAnswers[qid] = v;
        var row = inp.closest('.assess-q');
        if (row) {
          var span = row.querySelector('.assess-val-num');
          if (span) span.textContent = String(v);
        }
      });
    });
  }

  /** 保存今日评估（POST /api/state/assessment）。 */
  async function save() {
    if (!assessmentQuestions.length) {
      toast('暂无评估问题', 'err');
      return;
    }
    var answers = {};
    assessmentQuestions.forEach(function (q) {
      answers[q.id] = assessmentAnswers[q.id] != null ? assessmentAnswers[q.id] : 3;
    });
    try {
      await api('/api/state/assessment', {
        method: 'POST',
        body: JSON.stringify({ answers: answers })
      });
      closeModal('stateAssessmentModal');
      toast('评估已保存', 'suc');
      loadPanel();
    } catch (e) {
      toast(e.message || '保存失败', 'err');
    }
  }

  /** 关闭评估模态。 */
  function closeModal_() {
    closeModal('stateAssessmentModal');
  }

  return {
    loadPanel: loadPanel,
    loadSummary: loadSummary,
    loadHistory: loadHistory,
    openModal: openModal,
    closeModal: closeModal_,
    renderForm: renderForm,
    save: save,
    // 只读快照（供诊断 / 测试断言使用，不构成第二份状态源）。
    getState: function () {
      return {
        assessmentQuestions: assessmentQuestions.slice(),
        assessmentAnswers: Object.assign({}, assessmentAnswers)
      };
    }
  };
}

export default {
  createStateAssessmentOwner: createStateAssessmentOwner
};
