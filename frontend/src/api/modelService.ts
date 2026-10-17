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
  supportsThinking?: boolean;
  isDefault?: boolean;
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
  supports_thinking?: boolean;
  is_default?: boolean;
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
      const modelType = model.supports_thinking ? 'thinking' : 'fast';
      
      return {
        id: model.id,
        name: model.name || model.id,
        displayName: model.display_name || model.name || model.id,
        provider: model.provider || 'local',
        type: modelType,
        description: model.description,
        contextLength: model.context_length || model.max_tokens,
        supportsThinking: model.supports_thinking === true,
        isDefault: model.is_default === true,
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
      type: model.supports_thinking ? 'thinking' : 'fast',
      description: model.description,
      contextLength: model.context_length || model.max_tokens,
      supportsThinking: model.supports_thinking === true,
        isDefault: model.is_default === true,
        isAvailable: model.available !== false
    };
  } catch (error) {
    console.error(`获取模型 ${modelId} 信息失败:`, error);
    return null;
  }
}
