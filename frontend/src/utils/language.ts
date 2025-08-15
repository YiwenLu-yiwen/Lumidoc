interface Language {
  code: string;
  name: string;
  flag: string;
}

// 支持的语言
export const supportedLanguages: Language[] = [
  { code: 'zh-CN', name: '中文', flag: '🇨🇳' },
  { code: 'en-US', name: 'English', flag: '🇺🇸' },
  { code: 'ja-JP', name: '日本語', flag: '🇯🇵' },
  { code: 'ko-KR', name: '한국어', flag: '🇰🇷' },
  { code: 'fr-FR', name: 'Français', flag: '🇫🇷' },
  { code: 'de-DE', name: 'Deutsch', flag: '🇩🇪' },
  { code: 'es-ES', name: 'Español', flag: '🇪🇸' },
];

// 浏览器语言到支持语言的映射
const languageMap: { [key: string]: string } = {
  'zh': 'zh-CN',
  'zh-CN': 'zh-CN',
  'zh-TW': 'zh-CN',
  'zh-HK': 'zh-CN',
  'en': 'en-US',
  'en-US': 'en-US',
  'en-GB': 'en-US',
  'ja': 'ja-JP',
  'ja-JP': 'ja-JP',
  'ko': 'ko-KR',
  'ko-KR': 'ko-KR',
  'fr': 'fr-FR',
  'fr-FR': 'fr-FR',
  'de': 'de-DE',
  'de-DE': 'de-DE',
  'es': 'es-ES',
  'es-ES': 'es-ES',
};

// 自动检测浏览器语言
export function detectBrowserLanguage(): string {
  // 优先从 localStorage 获取用户设置的语言
  const savedLanguage = localStorage.getItem('stp_language');
  if (savedLanguage && supportedLanguages.some(lang => lang.code === savedLanguage)) {
    return savedLanguage;
  }

  // 检测浏览器语言
  const browserLanguages = [
    navigator.language,
    ...(navigator.languages || [])
  ];

  for (const browserLang of browserLanguages) {
    // 直接匹配
    if (languageMap[browserLang]) {
      return languageMap[browserLang];
    }
    
    // 匹配语言前缀（如 'zh-CN' -> 'zh'）
    const langPrefix = browserLang.split('-')[0];
    if (languageMap[langPrefix]) {
      return languageMap[langPrefix];
    }
  }

  // 默认返回中文
  return 'zh-CN';
}

// 根据时间自动判断主题
export function detectAutoTheme(): 'light' | 'dark' {
  const hour = new Date().getHours();
  // 6:00-18:00 为白天，使用浅色主题
  // 18:00-6:00 为夜晚，使用深色主题
  return hour >= 6 && hour < 18 ? 'light' : 'dark';
}

// 保存语言设置
export function saveLanguage(languageCode: string) {
  localStorage.setItem('stp_language', languageCode);
}

// 多语言文本
export const translations = {
  'zh-CN': {
    newChat: '新建聊天',
    searchChats: '搜索聊天记录...',
    chat: '聊天',
    projects: '项目',
    rag: '知识图谱',
    settings: '设置',
    lightMode: '浅色模式',
    darkMode: '深色模式',
    autoMode: '自动模式',
    language: '语言',
    thinkingModel: '思考模型',
    fastModel: '快速模型',
    starred: '已收藏',
    archive: '归档',
    manageAccount: '点击管理账号',
    user: '用户',
    login: '登录',
    email: '邮箱',
    password: '密码',
    loginButton: '登录',
    register: '注册',
    forgotPassword: '忘记密码？',
    thinking: '思考中...',
    admin: '管理员',
    projectManagement: '项目管理',
    userManagement: '用户管理',
    inviteUser: '邀请用户',
    modelList: '模型列表',
    localModels: '本地模型',
    // Dashboard 专用翻译
    intelligentWorkbench: '智能工作台',
    aiDocumentPlatform: '一站式AI文档处理和分析平台',
    newProject: '新建项目',
    uploadDocument: '上传文档',
    deepReasoning: '深度推理和复杂分析',
    instantResponse: '即时响应和轻量任务',
    documentProcessing: '文档处理',
    ocrRecognition: 'OCR识别和智能分析',
    knowledgeGraph: '知识图谱',
    neo4jStorage: 'Neo4j图数据库存储',
    available: '可用',
    offline: '离线',
    online: '在线',
    loading: '加载中',
    responseTime: '响应时间',
    processingSuccess: '处理成功率',
    entityRelations: '实体关系',
    localModelManagement: '本地模型管理',
    modelAutoDownload: '管理本地模型，自动下载和更新',
    refresh: '刷新',
    downloadModel: '下载模型',
    installedModels: '已安装模型',
    popularModels: '热门模型推荐',
    type: '类型',
    size: '大小',
    modifiedTime: '修改时间',
    download: '下载',
    cancel: '取消',
    projectOverview: '项目概览',
    monitorProgress: '监控所有项目的进度和状态',
    newCreate: '新建',
    lastActivity: '最后活动',
    progress: '进度',
    view: '查看',
    recentDocuments: '最近文档',
    viewLatestDocs: '查看最新处理的文档',
    viewAllDocs: '查看所有文档',
    quickActions: '快速操作',
    commonFeatures: '常用功能快捷入口',
    newConversation: '新建对话',
    dataAnalysis: '数据分析',
    systemStatus: '系统状态',
    realTimeMonitoring: '实时监控系统资源',
    cpuUsage: 'CPU使用率',
    memoryUsage: '内存使用',
    gpuLoad: 'GPU负载',
    networkLatency: '网络延迟',
    enterModelName: '输入模型名称',
    downloadStarted: '开始下载...',
    downloadCompleted: '下载完成',
    cannotConnect: '无法连接到 Ollama 服务',
    noModelsInstalled: '暂无已安装的模型'
  },
  'en-US': {
    newChat: 'New Chat',
    searchChats: 'Search chat history...',
    chat: 'Chat',
    projects: 'Projects',
    rag: 'Knowledge Graph',
    settings: 'Settings',
    lightMode: 'Light Mode',
    darkMode: 'Dark Mode',
    autoMode: 'Auto Mode',
    language: 'Language',
    thinkingModel: 'Thinking Model',
    fastModel: 'Fast Model',
    starred: 'Starred',
    archive: 'Archive',
    manageAccount: 'Click to manage account',
    user: 'User',
    login: 'Login',
    email: 'Email',
    password: 'Password',
    loginButton: 'Login',
    register: 'Register',
    forgotPassword: 'Forgot Password?',
    thinking: 'Thinking...',
    admin: 'Admin',
    projectManagement: 'Project Management',
    userManagement: 'User Management',
    inviteUser: 'Invite User',
    modelList: 'Model List',
    localModels: 'Local Models',
    // Dashboard specific translations
    intelligentWorkbench: 'Intelligent Workbench',
    aiDocumentPlatform: 'One-stop AI document processing and analysis platform',
    newProject: 'New Project',
    uploadDocument: 'Upload Document',
    deepReasoning: 'Deep reasoning and complex analysis',
    instantResponse: 'Instant response and lightweight tasks',
    documentProcessing: 'Document Processing',
    ocrRecognition: 'OCR recognition and intelligent analysis',
    knowledgeGraph: 'Knowledge Graph',
    neo4jStorage: 'Neo4j graph database storage',
    available: 'Available',
    offline: 'Offline',
    online: 'Online',
    loading: 'Loading',
    responseTime: 'Response time',
    processingSuccess: 'Processing success rate',
    entityRelations: 'Entity relations',
    localModelManagement: 'Local Model Management',
    modelAutoDownload: 'Manage local models, auto download and update',
    refresh: 'Refresh',
    downloadModel: 'Download Model',
    installedModels: 'Installed Models',
    popularModels: 'Popular Model Recommendations',
    type: 'Type',
    size: 'Size',
    modifiedTime: 'Modified Time',
    download: 'Download',
    cancel: 'Cancel',
    projectOverview: 'Project Overview',
    monitorProgress: 'Monitor progress and status of all projects',
    newCreate: 'New',
    lastActivity: 'Last activity',
    progress: 'Progress',
    view: 'View',
    recentDocuments: 'Recent Documents',
    viewLatestDocs: 'View latest processed documents',
    viewAllDocs: 'View All Documents',
    quickActions: 'Quick Actions',
    commonFeatures: 'Common feature shortcuts',
    newConversation: 'New Conversation',
    dataAnalysis: 'Data Analysis',
    systemStatus: 'System Status',
    realTimeMonitoring: 'Real-time system resource monitoring',
    cpuUsage: 'CPU Usage',
    memoryUsage: 'Memory Usage',
    gpuLoad: 'GPU Load',
    networkLatency: 'Network Latency',
    enterModelName: 'Enter model name',
    downloadStarted: 'Download started...',
    downloadCompleted: 'Download completed',
    cannotConnect: 'Cannot connect to Ollama service',
    noModelsInstalled: 'No models installed'
  }
};

// 获取翻译文本
export function getTranslation(languageCode: string, key: keyof typeof translations['zh-CN']): string {
  const lang = translations[languageCode as keyof typeof translations] || translations['zh-CN'];
  return lang[key] || translations['zh-CN'][key];
}