// static/modules/config/index.js - AR03-G11 真实生产 ESM owner
//
// 拥有「设置」页「系统配置」表单的**全部业务实现**：
//   - loadConfigForm：真实 GET /api/config，回填端口 / 笔记目录 / Vault 路径 /
//     API Base / 模型，并刷新 Agent 只读提示；
//   - saveConfigForm：真实 POST /api/config/save，提交
//     { port, notes_directory, vault_path, openai_api_key, api_base, model }。
//
// 与迁移前 static/app.js 的 CONFIG 段落**逐条语义一致**：
//   - GET 后的默认值不变：port || 5000、notes_directory || ''、
//     vault_path || ''、api_base || 'https://api.openai.com/v1'、
//     model || 'gpt-4o-mini'；
//   - GET **不读取、不回填** cfgApiKey（API Key 永不从服务端回显）；
//   - 加载顺序不变：先回填各字段，再 await refreshAgentReadonlyHint(r)；
//   - 加载异常 → toast('加载配置失败', 'err')；
//   - 保存时 port 使用 parseInt(value, 10) || 5000，其余字段取原始字符串；
//   - 保存成功（r.success 为真）→ toast('已保存，重启服务器后生效', 'suc')；
//     否则 → toast('保存失败: ' + (r.error || ''), 'err')；
//   - 保存异常 → toast(e.message || '保存失败', 'err')；
//   - 读取表单值的部分在 try 之外（与迁移前一致：字段缺失时行为不变）。
//
// **API Key 回填语义（硬约束）**：本模块**永不**从 /api/config 的返回体读取或
// 写回 cfgApiKey；cfgApiKey 只由用户在表单里手工输入，再随保存请求提交。
//
// 依赖注入约定（本模块 **不通过 window 查找任何私有 helper**，也 **不新建
// 独立 API client**，不创建全局 Store、事件总线、缓存或重试层）：
//   api(url, opts)                     classic 层唯一的 fetch 封装
//   toast(msg, type)                   classic 层唯一的提示条
//   refreshAgentReadonlyHint(cfg)      Agent 只读 owner 的既有 facade
//                                       （唯一实现在 static/modules/agent-readonly/
//                                       index.js；本模块**只调用**，不复制实现）
//
// 业务实现**只有这一份**：classic 层（static/app.js）只保留薄 facade
// （dynamic import + 依赖注入），不存在 classic/ESM 双份镜像。

/**
 * 创建「系统配置表单」模块 owner（唯一业务实现持有者）。
 *
 * @param {Object} deps classic 层注入的共享帮助函数
 * @returns {Object} owner 暴露全部业务方法
 */
export function createConfigOwner(deps) {
  var d = deps || {};
  var api = typeof d.api === 'function' ? d.api : function () {
    return Promise.reject(new Error('api 未注入'));
  };
  var toast = typeof d.toast === 'function' ? d.toast : function () {};
  var refreshAgentReadonlyHint = typeof d.refreshAgentReadonlyHint === 'function'
    ? d.refreshAgentReadonlyHint
    : function () {};

  function byId(id) {
    return document.getElementById(id);
  }

  /** 读取输入框当前值（与迁移前 app.js 一致：元素缺失时抛错）。 */
  function fieldValue(id) {
    return byId(id).value;
  }

  /**
   * 加载配置表单（真实 GET /api/config）。
   *
   * 语义与迁移前一致：
   *   - GET **不读取、不回填** cfgApiKey；
   *   - 先回填字段，再刷新 Agent 只读提示；
   *   - 任何异常 → toast('加载配置失败', 'err')。
   */
  async function loadConfigForm() {
    try {
      var r = await api('/api/config');
      byId('cfgPort').value = r.port || 5000;
      byId('cfgNotesDir').value = r.notes_directory || '';
      byId('cfgVaultPath').value = r.vault_path || '';
      byId('cfgApiBase').value = r.api_base || 'https://api.openai.com/v1';
      byId('cfgModel').value = r.model || 'gpt-4o-mini';
      // Agent 只读提示的唯一实现在 ESM owner 里（CONFIG 表单提示 + 面板横幅共用）。
      await refreshAgentReadonlyHint(r);
    } catch (e) {
      toast('加载配置失败', 'err');
    }
  }

  /**
   * 保存配置表单（真实 POST /api/config/save）。
   *
   * 语义与迁移前一致：
   *   - 读取表单值在 try 之外；
   *   - port 使用 parseInt(value, 10) || 5000；
   *   - payload 字段精确为 6 个，不多不少；
   *   - 成功 / 失败 / 异常的 toast 文案保持原样。
   */
  async function saveConfigForm() {
    var data = {
      port: parseInt(fieldValue('cfgPort'), 10) || 5000,
      notes_directory: fieldValue('cfgNotesDir'),
      vault_path: fieldValue('cfgVaultPath'),
      openai_api_key: fieldValue('cfgApiKey'),
      api_base: fieldValue('cfgApiBase'),
      model: fieldValue('cfgModel')
    };
    try {
      var r = await api('/api/config/save', {
        method: 'POST',
        body: JSON.stringify(data)
      });
      if (r.success) toast('已保存，重启服务器后生效', 'suc');
      else toast('保存失败: ' + (r.error || ''), 'err');
    } catch (e) {
      toast(e.message || '保存失败', 'err');
    }
  }

  return {
    loadConfigForm: loadConfigForm,
    saveConfigForm: saveConfigForm
  };
}

export default {
  createConfigOwner: createConfigOwner
};
