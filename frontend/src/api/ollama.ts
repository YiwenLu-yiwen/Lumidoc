import { apiClient } from './client';

// Ollama 模型信息接口
export interface OllamaModel {
  name: string;
  size?: number;
  digest?: string;
  modified?: string;
  details?: any;
}

// 模型下载状态接口
export interface ModelPullStatus {
  status: 'started' | 'downloading' | 'completed' | 'error' | 'not_found';
  percentage: number;
  message: string;
  total?: number;
  completed?: number;
}

// 模型下载请求接口
export interface ModelPullRequest {
  name: string;
  insecure?: boolean;
}

export class OllamaApi {
  /**
   * 获取已安装的 Ollama 模型列表
   */
  static async getInstalledModels(): Promise<{ models: OllamaModel[], total: number }> {
    try {
      const response = await apiClient.get('/api/v1/llm/ollama/models');
      return response.data;
    } catch (error) {
      console.error('获取已安装模型列表失败:', error);
      throw error;
    }
  }

  /**
   * 获取增强的模型列表（包含 Ollama 模型识别）
   */
  static async getAvailableModels(): Promise<{ models: any[], total: number }> {
    try {
      const response = await apiClient.get('/api/v1/llm/models');
      return response.data;
    } catch (error) {
      console.error('获取可用模型列表失败:', error);
      throw error;
    }
  }

  /**
   * 下载模型
   */
  static async pullModel(request: ModelPullRequest): Promise<{ status: string, message: string, model: string }> {
    try {
      const response = await apiClient.post('/api/v1/llm/ollama/pull', request);
      return response.data;
    } catch (error) {
      console.error('下载模型失败:', error);
      throw error;
    }
  }

  /**
   * 获取模型下载状态
   */
  static async getPullStatus(modelName: string): Promise<ModelPullStatus> {
    try {
      const response = await apiClient.get(`/api/v1/llm/ollama/pull/${encodeURIComponent(modelName)}/status`);
      return response.data;
    } catch (error) {
      console.error('获取下载状态失败:', error);
      throw error;
    }
  }

  /**
   * 检查 Ollama 服务状态
   */
  static async checkOllamaStatus(): Promise<boolean> {
    try {
      await this.getInstalledModels();
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * 格式化文件大小
   */
  static formatFileSize(bytes?: number): string {
    if (!bytes) return '未知';
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    
    return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
  }

  /**
   * 智能检测模型类型（思考模型或快速模型）
   * 基于模型架构、参数规模、官方定位等多维度分析
   */
  static detectModelType(modelName: string): 'thinking' | 'fast' {
    const lowerName = modelName.toLowerCase();
    
    // 1. 明确的推理/思考模型
    const explicitThinkingModels = [
      'deepseek-r1',     // DeepSeek 推理模型
      'o1',              // OpenAI o1 系列
      'o3',              // OpenAI o3 系列  
      'reasoning',       // 明确标注推理
      'think',           // 明确标注思考
      'cot',             // Chain of Thought
      'chain-of-thought',
      'step-by-step',
      'reflection',
      'analysis'
    ];
    
    for (const keyword of explicitThinkingModels) {
      if (lowerName.includes(keyword)) {
        return 'thinking';
      }
    }
    
    // 2. 基于模型系列和参数规模的智能判断
    const modelAnalysis = this.analyzeModelCharacteristics(lowerName);
    
    // 3. 大语言模型系列分析
    if (modelAnalysis.isLargeParameterModel) {
      return 'thinking';
    }
    
    // 4. 专业模型判断
    if (modelAnalysis.isProfessionalModel) {
      return 'thinking';
    }
    
    // 5. 默认为快速模型
    return 'fast';
  }
  
  /**
   * 分析模型特征
   */
  private static analyzeModelCharacteristics(modelName: string) {
    const analysis = {
      isLargeParameterModel: false,
      isProfessionalModel: false,
      modelFamily: '',
      parameterSize: 0
    };
    
    // 参数规模提取和分析
    const parameterPatterns = [
      { pattern: /(\d+)b/i, multiplier: 1 },
      { pattern: /(\d+)\.(\d+)b/i, multiplier: 1 }
    ];
    
    for (const { pattern, multiplier } of parameterPatterns) {
      const match = modelName.match(pattern);
      if (match) {
        const size = parseFloat(match[1] + (match[2] ? '.' + match[2] : ''));
        analysis.parameterSize = size * multiplier;
        break;
      }
    }
    
    // 模型系列分析
    if (modelName.includes('qwen')) {
      analysis.modelFamily = 'qwen';
      // Qwen 系列：14B+ 为思考模型，小于14B为快速模型
      analysis.isLargeParameterModel = analysis.parameterSize >= 14;
    } else if (modelName.includes('llama')) {
      analysis.modelFamily = 'llama';
      // Llama 系列：13B+ 为思考模型
      analysis.isLargeParameterModel = analysis.parameterSize >= 13;
    } else if (modelName.includes('mistral') || modelName.includes('mixtral')) {
      analysis.modelFamily = 'mistral';
      // Mistral 系列：7B+ 通常为思考模型（架构优化）
      analysis.isLargeParameterModel = analysis.parameterSize >= 7;
    } else if (modelName.includes('gemma')) {
      analysis.modelFamily = 'gemma';
      // Gemma 系列：9B+ 为思考模型
      analysis.isLargeParameterModel = analysis.parameterSize >= 9;
    } else if (modelName.includes('claude')) {
      analysis.modelFamily = 'claude';
      // Claude 系列默认为思考模型
      analysis.isProfessionalModel = true;
    } else if (modelName.includes('gpt')) {
      analysis.modelFamily = 'gpt';
      // GPT 系列默认为思考模型
      analysis.isProfessionalModel = true;
    }
    
    // 专业/代码模型判断
    const professionalKeywords = [
      'codestral',       // 代码专用
      'codeqwen',        // 代码专用
      'wizard',          // 专业模型
      'nous',            // 专业调优
      'solar',           // 专业模型
      'yi-34b',          // 大参数专业模型
    ];
    
    for (const keyword of professionalKeywords) {
      if (modelName.includes(keyword)) {
        analysis.isProfessionalModel = true;
        break;
      }
    }
    
    return analysis;
  }

  /**
   * 检查是否是 embedding 模型
   */
  static isEmbeddingModel(modelName: string): boolean {
    const lowerName = modelName.toLowerCase();
    const embeddingKeywords = [
      'embed', 'embedding', 'nomic-embed', 
      'bge-', 'e5-', 'sentence-transformer',
      'all-minilm', 'text-embedding'
    ];
    
    return embeddingKeywords.some(keyword => lowerName.includes(keyword));
  }

  /**
   * 获取热门模型推荐
   */
  static getPopularModels(language: string = 'zh-CN'): Array<{name: string, description: string, type: 'thinking' | 'fast', size: string}> {
    const models = [
      {
        name: 'llama3.2:latest',
        description: {
          'zh-CN': 'Meta 最新的 Llama 3.2 模型，性能优秀',
          'en-US': 'Meta\'s latest Llama 3.2 model with excellent performance'
        },
        type: 'fast' as const,
        size: '2.0GB'
      },
      {
        name: 'qwen2.5:14b',
        description: {
          'zh-CN': '阿里通义千问 2.5，中文能力强',
          'en-US': 'Alibaba Qwen 2.5 with strong Chinese language capabilities'
        },
        type: 'thinking' as const,
        size: '8.2GB'
      },
      {
        name: 'deepseek-r1:8b',
        description: {
          'zh-CN': 'DeepSeek 推理模型，逻辑思维强',
          'en-US': 'DeepSeek reasoning model with strong logical thinking'
        },
        type: 'thinking' as const,
        size: '4.9GB'
      },
      {
        name: 'codestral:latest',
        description: {
          'zh-CN': 'Mistral 代码专用模型',
          'en-US': 'Mistral specialized code model'
        },
        type: 'fast' as const,
        size: '12GB'
      },
      {
        name: 'gemma2:9b',
        description: {
          'zh-CN': 'Google Gemma 2，轻量高效',
          'en-US': 'Google Gemma 2, lightweight and efficient'
        },
        type: 'fast' as const,
        size: '5.4GB'
      },
      {
        name: 'llama3.1:8b',
        description: {
          'zh-CN': 'Meta Llama 3.1 8B 版本',
          'en-US': 'Meta Llama 3.1 8B version'
        },
        type: 'fast' as const,
        size: '4.7GB'
      }
    ];
    
    return models.map(model => ({
      ...model,
      description: model.description[language as keyof typeof model.description] || model.description['zh-CN']
    }));
  }
}