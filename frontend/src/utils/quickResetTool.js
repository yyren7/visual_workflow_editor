// 快速重置工具 - 可以在浏览器控制台中直接运行
window.quickResetStuckFlow = async function(flowId) {
  const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
  const token = localStorage.getItem('access_token');
  
  if (!flowId) {
    // 尝试从当前页面URL获取flowId
    const urlParams = new URLSearchParams(window.location.search);
    flowId = urlParams.get('flowId') || window.location.pathname.split('/').pop();
  }
  
  if (!flowId) {
    console.error('无法获取flowId，请手动提供：quickResetStuckFlow("your-flow-id")');
    return;
  }
  
  console.log(`🔄 正在重置卡住的流程: ${flowId}`);
  
  try {
    // 1. 首先尝试状态回退
    console.log('1️⃣ 尝试状态回退...');
    const rollbackResponse = await fetch(`${API_BASE_URL}/sas/${flowId}/rollback-to-previous`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (rollbackResponse.ok) {
      const result = await rollbackResponse.json();
      console.log('✅ 状态回退成功:', result.message);
      setTimeout(() => window.location.reload(), 1000);
      return;
    }
    
    // 2. 如果回退失败，尝试重置卡住状态
    console.log('2️⃣ 尝试重置卡住状态...');
    const resetResponse = await fetch(`${API_BASE_URL}/sas/${flowId}/reset-stuck-state`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (resetResponse.ok) {
      const result = await resetResponse.json();
      console.log('✅ 重置卡住状态成功:', result.message);
      setTimeout(() => window.location.reload(), 1000);
      return;
    }
    
    // 3. 最后尝试强制重置
    console.log('3️⃣ 尝试强制重置...');
    const forceResetResponse = await fetch(`${API_BASE_URL}/sas/${flowId}/force-reset-state`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (forceResetResponse.ok) {
      const result = await forceResetResponse.json();
      console.log('✅ 强制重置成功:', result.message);
      setTimeout(() => window.location.reload(), 1000);
      return;
    }
    
    console.error('❌ 所有重置方法都失败了');
    console.log('🔄 建议刷新页面或联系技术支持');
    
  } catch (error) {
    console.error('❌ 重置过程中发生错误:', error);
    console.log('🔄 建议刷新页面或联系技术支持');
  }
};

// 自动检测并提供快速重置选项
window.checkAndOfferQuickReset = function() {
  // 检查Redux store中的状态
  const store = window.__REDUX_STORE__ || window.store;
  if (store) {
    const state = store.getState();
    const agentState = state.flow?.agentState;
    
    if (agentState && agentState.dialog_state === 'initial') {
      const hasGeneratedTasks = agentState.sas_step1_generated_tasks && agentState.sas_step1_generated_tasks.length > 0;
      if (hasGeneratedTasks && !agentState.clarification_question) {
        console.log('🚨 检测到卡住状态！');
        console.log('💡 运行以下命令来快速重置:');
        console.log('quickResetStuckFlow()');
        return true;
      }
    }
  }
  return false;
};

console.log('🛠️ 快速重置工具已加载！');
console.log('💡 使用方法:');
console.log('  - 自动检测: checkAndOfferQuickReset()');
console.log('  - 立即重置: quickResetStuckFlow()');
console.log('  - 指定流程: quickResetStuckFlow("flow-id")'); 