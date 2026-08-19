import { apiClient } from './client';

export interface ModelInfo {
  id: string;
  name: string;
  displayName: string;
  provider: 'deepseek' | 'openai' | 'azure' | 'ollama' | 'local';
  type: 'thinking' | 'fast';
  description?: string;
  contextLength?: number;
  isAvailable: boolean;
}

export interface ModelResponse {
  models: ModelInfo[];
  total: number;
}

interface RawModel {
  id: string;
  name?: string;
  display_name?: string;
  provider?: ModelInfo['provider'];
  description?: string;
  context_length?: number;
  max_tokens?: number;
  available?: boolean;
}

/**
 * 根据模型名称自动识别模型类型
 * @param modelName 模型名称
 * @returns 'thinking' | 'fast'
 */
export function detectModelType(modelName: string): 'thinking' | 'fast' {
  const lowerName = modelName.toLowerCase();
  
  // 思考模型关键词
  const thinkingKeywords = [
    'thinking', 'think', 'reason', 'reasoning', 'step', 'cot', 'chain-of-thought',
    'o1', 'o2', 'deepthink', 'reflect', 'analysis', 'slow', 'careful'
  ];
  
  // 快速模型关键词
  const fastKeywords = [
    'fast', 'quick', 'turbo', 'instant', 'speed', 'light', 'rapid',
    'gpt-3.5', 'claude-instant', 'haiku', 'flash'
  ];
  
  // 检查思考模型关键词
  for (const keyword of thinkingKeywords) {
    if (lowerName.includes(keyword)) {
      return 'thinking';
    }
  }
  
  // 检查快速模型关键词
  for (const keyword of fastKeywords) {
    if (lowerName.includes(keyword)) {
      return 'fast';
    }
  }
  
  // 默认情况下，根据模型名称长度和复杂度判断
  // 通常更复杂的模型名称或包含版本号较高的倾向于是思考模型
  if (lowerName.includes('4') || lowerName.includes('large') || lowerName.includes('max')) {
    return 'thinking';
  }
  
  // 默认为快速模型
  return 'fast';
}

/**
 * 获取可用的模型列表
 */
export async function getAvailableModels(): Promise<ModelResponse> {
  try {
    const response = await apiClient.get('/api/v1/llm/models');
    const rawModels = (response.data.models || []) as RawModel[];
    
    // 处理模型数据并自动识别类型
    const models: ModelInfo[] = rawModels.map((model) => {
      const modelType = detectModelType(model.name || model.id);
      
      return {
        id: model.id,
        name: model.name || model.id,
        displayName: model.display_name || model.name || model.id,
        provider: model.provider || 'local',
        type: modelType,
        description: model.description,
        contextLength: model.context_length || model.max_tokens,
        isAvailable: model.available !== false
      };
    });
    
    return {
      models,
      total: models.length
    };
  } catch (error) {
    console.error('获取模型列表失败:', error);
    throw new Error('获取模型列表失败，请检查LLM服务是否可用');
  }
}

/**
 * 检查模型是否可用
 * @param modelId 模型ID
 */
export async function checkModelAvailability(modelId: string): Promise<boolean> {
  try {
    const response = await apiClient.get(`/api/v1/llm/models/${modelId}/status`);
    return response.data.available === true;
  } catch (error) {
    console.error(`检查模型 ${modelId} 可用性失败:`, error);
    return false;
  }
}

/**
 * 获取模型详细信息
 * @param modelId 模型ID
 */
export async function getModelInfo(modelId: string): Promise<ModelInfo | null> {
  try {
    const response = await apiClient.get(`/api/v1/llm/models/${modelId}`);
    const model = response.data;
    
    return {
      id: model.id,
      name: model.name || model.id,
      displayName: model.display_name || model.name || model.id,
      provider: model.provider || 'local',
      type: detectModelType(model.name || model.id),
      description: model.description,
      contextLength: model.context_length || model.max_tokens,
      isAvailable: model.available !== false
    };
  } catch (error) {
    console.error(`获取模型 ${modelId} 信息失败:`, error);
    return null;
  }
}
