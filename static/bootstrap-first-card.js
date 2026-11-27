// static/bootstrap-first-card.js
// 正式产品 P0：第一次启动引导卡 (LT_BOOTSTRAP_FIRST_CARD_20261021_A)
//
// 目的
// ----
// 当用户尚未拥有一份"经本人明确批准"的初始策略时，正式用户界面上
// **唯一** 可操作的卡是「与 Agent 讨论复盘并更改配置」，固定 25 分钟。
// 初始化阶段绝不允许换卡 / 拒绝 / 暂停 / 跳过 / 自由抽卡 / 继续其他任务。
//
// 强制覆盖视图
// ------------
// 本脚本在 <head> 中、app.js 之前加载：
//   1. 立即给 <html> 打上 pending 标记 + 注入样式：body 下除覆盖层外的
//      所有元素（含 header / main / 弹窗）一律 display:none，
//      因此在状态判定完成前，页面上不存在任何可执行的替代按钮。
//   2. 状态判定期间拦截一切"会改变服务端状态"的写请求
//      （/api/gacha/*、/api/timer/*、/api/tasks 的非 GET），
//      保证引导卡不参与正常抽卡 / 完成率 / 拒绝率建模。
//   3. 判定结果：
//        initialized === true  → 移除覆盖层与 pending 标记，恢复正常页面。
//        initialized === false → 展示引导卡（唯一入口按钮「开始任务」）。
//        无法访问 status API    → fail closed：仍然停在覆盖层，绝不误入
//                                正常抽卡；仅提供「重新检测状态」。
//
// 状态持久化
// ----------
// 引导流程状态只保存在 localStorage（非行为分析存储），用于刷新恢复：
//   sal.bootstrap.v1 = { stage: 'intro' | 'prompt', startedAt, elapsed }
//
// 本文件不写入任何用户数据库、配置文件或 notes；不实现策略发布。

(function () {
  'use strict';

  var STORAGE_KEY = 'sal.bootstrap.v1';
  var PROMPT_URL = '/static/bootstrap-steward-prompt.txt';
  var STATUS_URL = '/api/agent-policy/status';
  var FIXED_MINUTES = 25;
  var PENDING_CLASS = 'sal-bootstrap-pending';

  var state = {
    initialized: false,
    stage: 'intro',
    startedAt: 0,
    elapsed: 0,
    promptText: '',
    tickHandle: null,
    locked: true
  };

  // ---------------------------------------------------------------- utils

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function storeState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        stage: state.stage,
        startedAt: state.startedAt,
        elapsed: state.elapsed
      }));
    } catch (e) { /* localStorage 不可用时降级为内存态 */ }
  }

  function loadState() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') return null;
      return parsed;
    } catch (e) {
      return null;
    }
  }

  function clearState() {
    try { localStorage.removeItem(STORAGE_KEY); } catch (e) { /* noop */ }
  }

  function formatClock(totalSeconds) {
    var seconds = Math.max(0, Math.floor(totalSeconds));
    var m = Math.floor(seconds / 60);
    var s = seconds % 60;
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }

  // ----------------------------------------------------------- 样式注入

  var STYLE_ID = 'sal-bootstrap-style';

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = [
      'html.' + PENDING_CLASS + ' body > *:not(#salBootstrapOverlay){display:none !important;}',
      '#salBootstrapOverlay{position:fixed;inset:0;z-index:2147483000;',
      '  display:flex;align-items:center;justify-content:center;padding:24px;',
      '  background:var(--bg-deep,#0a0e1a);color:var(--text-primary,#f0e8da);',
      '  font-family:var(--font-body,serif);overflow-y:auto;}',
      '#salBootstrapOverlay[hidden]{display:none !important;}',
      '#salBootstrapOverlay [hidden]{display:none !important;}',
      '.sal-bootstrap-card{width:100%;max-width:720px;background:var(--bg-card,rgba(26,32,56,0.95));',
      '  border:1px solid var(--border,rgba(255,255,255,0.06));border-radius:16px;padding:28px;',
      '  box-shadow:0 10px 40px rgba(0,0,0,0.45);}',
      '.sal-bootstrap-card h2{font-family:var(--font-heading,serif);font-size:1.2rem;margin:0 0 6px;}',
      '.sal-bootstrap-meta{font-size:0.85rem;color:var(--text-muted,#6b6480);margin-bottom:16px;}',
      '.sal-bootstrap-timer{font-family:var(--font-heading,serif);font-size:2.4rem;color:var(--gold,#f0c040);',
      '  margin:8px 0 4px;}',
      '.sal-bootstrap-note{font-size:0.85rem;color:var(--text-secondary,#a8a0b8);line-height:1.7;margin:8px 0;}',
      '.sal-bootstrap-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px;}',
      '.sal-bootstrap-btn{background:var(--bg-tertiary,#222a48);color:var(--text-primary,#f0e8da);',
      '  border:1px solid var(--border,rgba(255,255,255,0.06));border-radius:10px;padding:9px 18px;',
      '  cursor:pointer;font-family:var(--font-body,serif);font-size:0.95rem;}',
      '.sal-bootstrap-btn.pri{background:linear-gradient(135deg,#c99f2e,#f0c040);color:#0a0e1a;border:0;font-weight:700;}',
      '.sal-bootstrap-btn:hover{border-color:var(--gold,#f0c040);}',
      '.sal-bootstrap-prompt{width:100%;min-height:220px;margin-top:12px;background:var(--bg-secondary,#1a2038);',
      '  color:var(--text-primary,#f0e8da);border:1px solid var(--border,rgba(255,255,255,0.06));',
      '  border-radius:10px;padding:12px;font-family:Consolas,monospace;font-size:0.82rem;',
      '  white-space:pre-wrap;overflow:auto;}',
      '.sal-bootstrap-status{font-size:0.9rem;margin-top:10px;color:var(--gold,#f0c040);}',
      '.sal-bootstrap-recheck{margin-top:16px;padding-top:14px;',
      '  border-top:1px solid var(--border,rgba(255,255,255,0.08));}',
      '.sal-bootstrap-recheck[hidden]{display:none !important;}',
      '.sal-bootstrap-btn.link{background:transparent;color:var(--text-secondary,#a8a0b8);',
      '  text-decoration:underline;border-style:dashed;}',
      '.sal-bootstrap-btn[aria-busy="true"]{opacity:0.6;cursor:progress;}',
      '.sal-bootstrap-list{margin:10px 0 0 18px;font-size:0.88rem;color:var(--text-secondary,#a8a0b8);line-height:1.8;}'
    ].join('');
    document.head.appendChild(style);
  }

  // --------------------------------------------------------- 覆盖层构建

  var overlay = null;
  var refs = {};

  function buildOverlay() {
    if (overlay) return overlay;
    overlay = el('div');
    overlay.id = 'salBootstrapOverlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', '初始化引导卡');
    overlay.hidden = true;

    var card = el('div', 'sal-bootstrap-card');
    card.id = 'salBootstrapCard';

    refs.title = el('h2', null, '与 Agent 讨论复盘并更改配置');
    refs.meta = el('div', 'sal-bootstrap-meta',
      '初始化引导卡 · 固定 25 分钟 · 这不是普通任务卡，不参与抽卡 / 完成率 / 拒绝率统计');
    refs.timer = el('div', 'sal-bootstrap-timer', formatClock(FIXED_MINUTES * 60));
    refs.timer.id = 'salBootstrapTimer';
    refs.timerNote = el('div', 'sal-bootstrap-note',
      '引导卡计时到 0 也不会自动解锁。只有当策略经你明确批准并生效后，才会回到正常抽卡页面。');
    refs.intro = el('div', 'sal-bootstrap-note',
      '点击「开始任务」后会展示一份可复制的 ChatGPT 管家提示词。把它粘贴进你已有的管家对话；' +
      '如果没有，就新开一个干净的 ChatGPT 对话再粘贴。对话会询问你的日常习惯与目标，' +
      '并生成一份初始策略提案，等你明确批准后才会生效。');

    refs.startBtn = el('button', 'sal-bootstrap-btn pri', '开始任务');
    refs.startBtn.id = 'salBootstrapStartBtn';
    refs.startBtn.type = 'button';

    var introActions = el('div', 'sal-bootstrap-actions');
    introActions.appendChild(refs.startBtn);

    // --- 第二阶段（提示词） ---
    refs.promptWrap = el('div');
    refs.promptWrap.hidden = true;
    refs.promptTitle = el('div', 'sal-bootstrap-note',
      '第一步：复制下面这份完整提示词 → 打开 ChatGPT → 粘贴到你的管家对话里。');
    refs.promptBox = el('textarea', 'sal-bootstrap-prompt');
    refs.promptBox.id = 'salBootstrapPromptText';
    refs.promptBox.readOnly = true;
    refs.promptBox.setAttribute('aria-label', 'ChatGPT 管家提示词');

    refs.copyBtn = el('button', 'sal-bootstrap-btn pri', '复制提示词');
    refs.copyBtn.id = 'salBootstrapCopyBtn';
    refs.copyBtn.type = 'button';

    refs.chatLink = el('a', 'sal-bootstrap-btn', '打开 ChatGPT');
    refs.chatLink.id = 'salBootstrapChatLink';
    refs.chatLink.href = 'https://chatgpt.com/';
    refs.chatLink.target = '_blank';
    refs.chatLink.rel = 'noopener noreferrer';

    refs.copyStatus = el('div', 'sal-bootstrap-status');
    refs.copyStatus.id = 'salBootstrapCopyStatus';

    refs.guide = el('ul', 'sal-bootstrap-list');
    refs.guide.appendChild(el('li', null, '如果你已经有管家对话，直接在那个对话里粘贴。'));
    refs.guide.appendChild(el('li', null, '如果没有，就新开一个干净的 ChatGPT 对话再粘贴，不要混用别的任务上下文。'));
    refs.guide.appendChild(el('li', null, '回答管家关于日常习惯与目标的提问，然后审阅它给出的初始策略提案。'));
    refs.guide.appendChild(el('li', null, '明确批准之后，策略才会被写回；在此之前页面会一直停在这张引导卡上。'));

    // --- 批准并发布之后的「重新检测配置」入口 ---
    //
    // 这一步**只是只读复查**：
    //   - 不发送任何 POST，不写策略文件，不记录任何"用户同意"；
    //   - 按钮文案刻意不写成"批准并发布"，避免误导成"点一下就算批准"；
    //   - 唯一的动作就是复用既有的 checkStatus()（GET /api/agent-policy/status）。
    // 用户真正批准与受控发布仍只发生在 ChatGPT 管家对话 +
    // scripts/agent_policy_publisher.py，网页无法代替。
    refs.recheckWrap = el('div', 'sal-bootstrap-recheck');
    refs.recheckWrap.id = 'salBootstrapRecheckWrap';
    refs.recheckBtn = el('button', 'sal-bootstrap-btn link', '已经在管家中批准并完成发布？检查配置');
    refs.recheckBtn.id = 'salBootstrapRecheckBtn';
    refs.recheckBtn.type = 'button';
    refs.recheckBtn.setAttribute(
      'aria-label',
      '重新检测是否已有生效的已批准策略（只读取状态，不会批准或发布任何配置）',
    );
    refs.recheckBtn.title = '只读取当前策略状态：若你已在管家中批准并通过受控发布工具保存，这里会返回正常抽卡页面。';
    refs.recheckNote = el('div', 'sal-bootstrap-note');
    refs.recheckNote.id = 'salBootstrapRecheckNote';
    refs.recheckNote.setAttribute('role', 'status');
    refs.recheckNote.hidden = true;
    refs.recheckWrap.appendChild(refs.recheckBtn);
    refs.recheckWrap.appendChild(refs.recheckNote);

    var promptActions = el('div', 'sal-bootstrap-actions');
    promptActions.appendChild(refs.copyBtn);
    promptActions.appendChild(refs.chatLink);

    refs.promptWrap.appendChild(refs.promptTitle);
    refs.promptWrap.appendChild(refs.promptBox);
    refs.promptWrap.appendChild(promptActions);
    refs.promptWrap.appendChild(refs.copyStatus);
    refs.promptWrap.appendChild(refs.guide);
    refs.promptWrap.appendChild(refs.recheckWrap);

    // --- fail closed 状态 ---
    refs.errorWrap = el('div');
    refs.errorWrap.hidden = true;
    refs.errorText = el('div', 'sal-bootstrap-note');
    refs.errorText.id = 'salBootstrapErrorText';
    refs.retryBtn = el('button', 'sal-bootstrap-btn', '重新检测状态');
    refs.retryBtn.id = 'salBootstrapRetryBtn';
    refs.retryBtn.type = 'button';
    var errorActions = el('div', 'sal-bootstrap-actions');
    errorActions.appendChild(refs.retryBtn);
    refs.errorWrap.appendChild(refs.errorText);
    refs.errorWrap.appendChild(errorActions);

    card.appendChild(refs.title);
    card.appendChild(refs.meta);
    card.appendChild(refs.timer);
    card.appendChild(refs.timerNote);
    card.appendChild(refs.intro);
    card.appendChild(introActions);
    card.appendChild(refs.promptWrap);
    card.appendChild(refs.errorWrap);

    overlay.appendChild(card);
    document.body.appendChild(overlay);

    refs.startBtn.addEventListener('click', onStartClick);
    refs.copyBtn.addEventListener('click', onCopyClick);
    refs.recheckBtn.addEventListener('click', onRecheckClick);
    refs.retryBtn.addEventListener('click', function () { checkStatus(); });

    return overlay;
  }

  function showIntro() {
    state.stage = 'intro';
    storeState();
    refs.promptWrap.hidden = true;
    refs.errorWrap.hidden = true;
    refs.startBtn.parentNode.hidden = false;
    refs.intro.hidden = false;
    refs.timer.hidden = false;
    overlay.hidden = false;
  }

  function showPromptStage() {
    state.stage = 'prompt';
    storeState();
    refs.startBtn.parentNode.hidden = true;
    refs.intro.hidden = true;
    refs.timer.hidden = false;
    refs.promptWrap.hidden = false;
    refs.errorWrap.hidden = true;
    overlay.hidden = false;
    fetchPrompt();
  }

  function showFailClosed(message) {
    overlay.hidden = false;
    refs.errorWrap.hidden = false;
    refs.errorText.textContent = message;
    refs.startBtn.parentNode.hidden = true;
    refs.promptWrap.hidden = true;
  }

  // ------------------------------------------------------- 重新检测配置
  //
  // 只读复查流程（契约：点击仅调用既有 checkStatus()）：
  //   1. 防重入：检测期间按钮 aria-busy 且被 disable，重复点击不再发请求。
  //   2. 尚未发布 → 保留原提示词阶段、已填写内容与计时，只显示一句可见说明。
  //   3. 已生效   → 沿用 releaseLock()，移除覆盖层进入正常抽卡。
  //   4. 状态 API 失败 → 沿用既有 fail closed 与「重新检测状态」，不跳过引导。
  var recheckInFlight = false;

  var RECHECK_PENDING_NOTE =
    '尚未检测到已生效配置，请先在管家中明确批准并通过受控发布工具保存。';

  function setRecheckBusy(busy) {
    recheckInFlight = !!busy;
    if (!refs.recheckBtn) return;
    refs.recheckBtn.disabled = !!busy;
    if (busy) refs.recheckBtn.setAttribute('aria-busy', 'true');
    else refs.recheckBtn.removeAttribute('aria-busy');
  }

  function showRecheckNote(text) {
    if (!refs.recheckNote) return;
    if (!text) {
      refs.recheckNote.textContent = '';
      refs.recheckNote.hidden = true;
      return;
    }
    refs.recheckNote.textContent = text;
    refs.recheckNote.hidden = false;
  }

  function onRecheckClick() {
    // 顺序即语义：先确认仍在引导层（未解锁），再谈点击。
    if (state.locked === false) return;
    if (recheckInFlight) return;                 // 防连续重复点击
    if (refs.recheckWrap && refs.recheckWrap.hidden) return;
    setRecheckBusy(true);
    showRecheckNote('');
    try {
      checkStatus().then(function () {
        // checkStatus() 已决定下一步（releaseLock / 保持阶段 / fail closed）。
        // 未解锁 = 合法已批准策略尚未生效：给出可见说明，阶段与计时保持不变。
        if (state.locked !== false && refs.recheckNote) {
          showRecheckNote(RECHECK_PENDING_NOTE);
        }
      }, function () {
        if (state.locked !== false) showRecheckNote(RECHECK_PENDING_NOTE);
      }).then(function () {
        // releaseLock() 会清空 refs；此时不再触碰任何节点。
        if (state.locked !== false) setRecheckBusy(false);
      });
    } catch (e) {
      setRecheckBusy(false);
      showRecheckNote(RECHECK_PENDING_NOTE);
    }
  }

  // ------------------------------------------------------------ 计时器

  function elapsedSeconds() {
    if (state.stage !== 'prompt' || !state.startedAt) return 0;
    return Math.max(0, (Date.now() - state.startedAt) / 1000);
  }

  function tick() {
    var remaining = FIXED_MINUTES * 60 - elapsedSeconds();
    refs.timer.textContent = formatClock(remaining);
    // 到 0 也不解锁：只是把显示归零，并保持覆盖层。
  }

  function startTicking() {
    if (state.tickHandle) return;
    tick();
    state.tickHandle = window.setInterval(tick, 1000);
  }

  function stopTicking() {
    if (!state.tickHandle) return;
    window.clearInterval(state.tickHandle);
    state.tickHandle = null;
  }

  // ------------------------------------------------------------ 提示词

  function fetchPrompt() {
    if (state.promptText) {
      refs.promptBox.value = state.promptText;
      return;
    }
    fetch(PROMPT_URL, { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error('prompt fetch failed');
      return r.text();
    }).then(function (text) {
      state.promptText = text;
      refs.promptBox.value = text;
    }).catch(function () {
      refs.promptBox.value = '（提示词加载失败，请刷新页面重试，或直接查看 /static/bootstrap-steward-prompt.txt）';
    });
  }

  function onStartClick() {
    // 引导卡的唯一入口：进入提示词阶段。此后不再有停止 / 暂停 / 拒绝 /
    // 换卡 / 跳过等任何出口。
    state.stage = 'prompt';
    state.startedAt = state.startedAt || Date.now();
    state.elapsed = 0;
    showPromptStage();
    startTicking();
  }

  function onCopyClick() {
    var text = state.promptText || refs.promptBox.value || '';
    var done = function () {
      refs.copyStatus.textContent = '已复制提示词，可以粘贴到 ChatGPT 管家对话了。';
      refs.copyBtn.setAttribute('data-last-copied', text);
      window.SAL_BOOTSTRAP_LAST_COPIED = text;
    };
    var fallback = function () {
      try {
        refs.promptBox.focus();
        refs.promptBox.select();
        var ok = document.execCommand('copy');
        if (!ok) throw new Error('execCommand failed');
        done();
      } catch (e) {
        refs.copyStatus.textContent = '自动复制失败，请手动全选上面的提示词文本进行复制。';
      }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(fallback);
    } else {
      fallback();
    }
  }

  // -------------------------------------------------------- 状态判定

  function applyPendingLock() {
    document.documentElement.classList.add(PENDING_CLASS);
    state.locked = true;
  }

  function releaseLock() {
    document.documentElement.classList.remove(PENDING_CLASS);
    state.locked = false;
    state.initialized = true;
    stopTicking();
    if (overlay) overlay.hidden = true;
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
    overlay = null;
    refs = {};
    clearState();
  }

  function checkStatus() {
    return fetch(STATUS_URL, { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error('status http ' + r.status);
      return r.json();
    }).then(function (body) {
      if (body && body.initialized === true) {
        releaseLock();
        return;
      }
      applyPendingLock();
      buildOverlay();
      var saved = loadState();
      // 停留在提示词阶段的两种来源都要保住：localStorage 恢复，或本次
      // 会话内已经进入过提示词阶段（例如刚点过「检查配置」，此时
      // localStorage 不可用也不该把用户踢回第一阶段、清掉计时）。
      if ((saved && saved.stage === 'prompt') || state.stage === 'prompt') {
        state.stage = 'prompt';
        state.startedAt = (saved && saved.startedAt) || state.startedAt || 0;
        state.elapsed = (saved && saved.elapsed) || state.elapsed || 0;
        showPromptStage();
        startTicking();
      } else {
        showIntro();
      }
    }).catch(function () {
      // Fail closed：拿不到状态就绝不放行普通抽卡。
      applyPendingLock();
      buildOverlay();
      showFailClosed(
        '无法获取策略状态（连接失败），为安全起见暂不开放抽卡。请确认后端服务已启动后重试。'
      );
    });
  }

  // -------------------------------------------------------- 写请求封锁

  var BLOCKED_PREFIXES = ['/api/gacha', '/api/timer', '/api/tasks'];

  function shouldBlock(url, method) {
    if (state.locked === false) return false;
    if (!method || method.toUpperCase() === 'GET') return false;
    if (!url) return false;
    var path = String(url).replace(/^https?:\/\/[^/]+/, '');
    for (var i = 0; i < BLOCKED_PREFIXES.length; i++) {
      if (path.indexOf(BLOCKED_PREFIXES[i]) === 0) return true;
    }
    return false;
  }

  function installFetchGuard() {
    if (!window.fetch || window.fetch.__salBootstrapGuard) return;
    var original = window.fetch;
    var guarded = function (input, init) {
      var url = (typeof input === 'string') ? input : (input && input.url) || '';
      var method = (init && init.method) || (input && input.method) || 'GET';
      if (shouldBlock(url, method)) {
        return Promise.reject(new Error('bootstrap-locked: 初始化完成前不可抽卡或开始计时'));
      }
      return original.apply(this, arguments);
    };
    guarded.__salBootstrapGuard = true;
    window.fetch = guarded;
  }

  // -------------------------------------------------- 交互层兜底封锁

  function installInteractionGuard() {
    if (window.__salBootstrapInteractionGuard) return;
    window.__salBootstrapInteractionGuard = true;
    document.addEventListener('click', function (ev) {
      if (state.locked === false) return;
      var target = ev.target;
      if (overlay && (target === overlay || overlay.contains(target))) return;
      // 覆盖层之外的一切点击都被吞掉。
      ev.preventDefault();
      ev.stopImmediatePropagation();
    }, true);
  }

  // -------------------------------------------------------- 启动

  // fetch / 交互守卫必须在脚本求值时立刻安装（脚本位于 <head>），
  // 否则 app.js 启动加载期间可能漏过一次写请求。
  function installGuardsEarly() {
    injectStyle();
    applyPendingLock();
    installFetchGuard();
    installInteractionGuard();
  }

  function boot() {
    installGuardsEarly();
    applyPendingLock();
    buildOverlay();
    overlay.hidden = true;
    checkStatus();
  }

  installGuardsEarly();

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // 暴露给隔离测试用的只读句柄（不含任何敏感数据）。
  window.SAL_BOOTSTRAP = {
    state: function () {
      return {
        locked: state.locked,
        initialized: state.initialized,
        stage: state.stage,
        promptLength: state.promptText.length,
        rechecking: recheckInFlight
      };
    },
    storageKey: STORAGE_KEY
  };
})();
