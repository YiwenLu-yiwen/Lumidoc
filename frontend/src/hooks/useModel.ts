import { useState, useEffect } from 'react';
import { ModelInfo, getAvailableModels } from '@/api/modelService';

export interface ModelState {
  selectedModel: ModelInfo | null;
  availableModels: ModelInfo[];
  loading: boolean;
  error: string | null;
}

export function useModel() {
  const [state, setState] = useState<ModelState>({
    selectedModel: null,
    availableModels: [],
    loading: true,
    error: null
  });

  // 加载模型列表
  const loadModels = async () => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const response = await getAvailableModels();
      const availableModels = response.models;
      
      // 如果没有选中模型，自动选择第一个可用的模型
      let selectedModel = state.selectedModel;
      if (!selectedModel && availableModels.length > 0) {
        // 优先选择可用的思考模型
        const thinkingModel = availableModels.find(m => m.isAvailable && m.type === 'thinking');
        const anyAvailableModel = availableModels.find(m => m.isAvailable);
        selectedModel = thinkingModel || anyAvailableModel || null;
      }
      
      setState(prev => ({
        ...prev,
        availableModels,
        selectedModel,
        loading: false
      }));
    } catch (error) {
      console.error('加载模型列表失败:', error);
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : '加载模型失败',
        loading: false
      }));
    }
  };

  // 选择模型
  const selectModel = (model: ModelInfo) => {
    setState(prev => ({
      ...prev,
      selectedModel: model
    }));
    
    // 保存到 localStorage
    localStorage.setItem('stp_selected_model', JSON.stringify(model));
  };

  // 获取模型类型统计
  const getModelStats = () => {
    const available = state.availableModels.filter(m => m.isAvailable);
    const thinking = available.filter(m => m.type === 'thinking');
    const fast = available.filter(m => m.type === 'fast');
    
    return {
      total: state.availableModels.length,
      available: available.length,
      thinking: thinking.length,
      fast: fast.length,
      unavailable: state.availableModels.length - available.length
    };
  };

  // 根据类型获取模型
  const getModelsByType = (type: 'thinking' | 'fast') => {
    return state.availableModels.filter(m => m.type === type);
  };

  // 获取可用模型
  const getAvailableModelsByType = (type?: 'thinking' | 'fast') => {
    const available = state.availableModels.filter(m => m.isAvailable);
    if (type) {
      return available.filter(m => m.type === type);
    }
    return available;
  };

  // 检查模型是否为思考模型
  const isThinkingModel = (model?: ModelInfo | null) => {
    return model?.type === 'thinking';
  };

  // 初始化
  useEffect(() => {
    // 尝试从 localStorage 恢复选中的模型
    const savedModel = localStorage.getItem('stp_selected_model');
    if (savedModel) {
      try {
        const model = JSON.parse(savedModel) as ModelInfo;
        setState(prev => ({ ...prev, selectedModel: model }));
      } catch (error) {
        console.error('恢复选中模型失败:', error);
      }
    }

    loadModels();
  }, []);

  return {
    ...state,
    loadModels,
    selectModel,
    getModelStats,
    getModelsByType,
    getAvailableModelsByType,
    isThinkingModel
  };
}