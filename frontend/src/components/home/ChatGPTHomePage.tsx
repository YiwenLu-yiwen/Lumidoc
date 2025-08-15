import React, { useState, useEffect, useRef } from 'react';
import { 
  MessageSquare, 
  Sparkles, 
  Brain, 
  ArrowRight,
  LogIn,
  ChevronDown,
  Shield,
  Network,
  Database,
  FileSearch,
  Clock,
  CheckCircle,
  Users,
  Server,
  Layers,
  Check,
  X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { detectAutoTheme } from '@/utils/language';

interface FeatureCard {
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  benefits: string[];
}


export function ChatGPTHomePage() {
  const [themeMode] = useState<'light' | 'dark' | 'auto'>('auto');
  const [hoveredFeature, setHoveredFeature] = useState<number | null>(null);
  const { user } = useAuth();
  const navigate = useNavigate();

  // 计算实际主题
  const actualTheme = themeMode === 'auto' ? detectAutoTheme() : themeMode;
  const isDarkMode = actualTheme === 'dark';

  // 动画演示状态管理
  const [animationStep, setAnimationStep] = useState(0);
  const [questionText, setQuestionText] = useState('');
  const [answerText, setAnswerText] = useState('');
  const [showThinking, setShowThinking] = useState(false);
  const [thinkingCollapsed, setThinkingCollapsed] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [animationStarted, setAnimationStarted] = useState(false);
  const demoRef = useRef<HTMLDivElement>(null);

  // 完整的问题和答案文本
  const fullQuestion = "请分析一下人工智能在医疗领域的应用前景，特别是在诊断准确性方面的优势。";
  const fullAnswer = `**人工智能在医疗诊断领域展现出巨大潜力：**

**🎯 诊断准确性优势：**
• 影像识别准确率可达95%以上，超越人类医生平均水平
• 减少主观判断误差，提供标准化诊断依据
• 24/7不间断工作，避免疲劳导致的判断失误

**🚀 应用前景：**
• 早期癌症筛查：提高检出率，降低漏诊风险
• 罕见病诊断：基于大数据快速识别罕见症状
• 个性化治疗：结合基因信息制定精准方案

**💡 基于Graph RAG分析：**通过知识图谱关联了医疗AI、诊断技术、临床应用等多个领域的信息，提供了全面的分析视角。`;

  // 打字动画效果
  const typeText = (text: string, callback: (currentText: string) => void, onComplete?: () => void) => {
    let currentIndex = 0;
    const typingInterval = setInterval(() => {
      if (currentIndex <= text.length) {
        callback(text.slice(0, currentIndex));
        currentIndex++;
      } else {
        clearInterval(typingInterval);
        onComplete?.();
      }
    }, 120); // 每120ms打一个字符
    return typingInterval;
  };

  // 启动动画序列
  const startAnimation = () => {
    if (animationStarted) return;
    setAnimationStarted(true);
    
    // 重置状态
    setAnimationStep(0);
    setQuestionText('');
    setAnswerText('');
    setShowThinking(false);
    setThinkingCollapsed(false);
    setIsTyping(true);

    // 步骤1: 用户问题打字动画
    setTimeout(() => {
      typeText(fullQuestion, setQuestionText, () => {
        setIsTyping(false);
        setAnimationStep(1);
        
        // 步骤2: 显示思考过程
        setTimeout(() => {
          setShowThinking(true);
          setAnimationStep(2);
          
          // 步骤3: 开始回答并折叠思考
          setTimeout(() => {
            setThinkingCollapsed(true);
            setAnimationStep(3);
            setIsTyping(true);
            
            // 步骤4: AI回答打字动画
            setTimeout(() => {
              typeText(fullAnswer, setAnswerText, () => {
                setIsTyping(false);
                setAnimationStep(4);
                
                // 5秒后重新开始动画
                setTimeout(() => {
                  setAnimationStarted(false);
                  startAnimation();
                }, 5000);
              });
            }, 500);
          }, 3000); // 思考3秒
        }, 1000);
      });
    }, 1000);
  };

  // 监听滚动，当演示区域进入视野时开始动画
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry.isIntersecting && !animationStarted) {
          startAnimation();
        }
      },
      {
        threshold: 0.3,
        rootMargin: '0px 0px -100px 0px'
      }
    );

    if (demoRef.current) {
      observer.observe(demoRef.current);
    }

    return () => {
      if (demoRef.current) {
        observer.unobserve(demoRef.current);
      }
    };
  }, [animationStarted]);

  // 核心特性展示
  const coreFeatures: FeatureCard[] = [
    {
      title: '多模型支持',
      description: '支持思考模型和快速模型，智能切换适应不同场景',
      icon: Brain,
      color: 'from-purple-500 to-pink-500',
      benefits: [
        'DeepSeek、OpenAI、Claude等主流模型',
        '智能识别思考型vs快速型模型',
        '根据任务复杂度自动推荐模型',
        '统一API接口，无缝切换'
      ]
    },
    {
      title: '智能项目管理',
      description: '多租户项目管理，协作共享，权限控制',
      icon: Users,
      color: 'from-blue-500 to-cyan-500',
      benefits: [
        '多项目并行管理',
        '团队协作与权限控制',
        '项目进度可视化',
        '文档版本管理'
      ]
    },
    {
      title: '智能文档处理',
      description: '自动上传、OCR识别、智能总结，支持多种格式',
      icon: FileSearch,
      color: 'from-green-500 to-emerald-500',
      benefits: [
        'PDF、Word、Excel等格式支持',
        '高精度OCR文字识别',
        'AI智能摘要和关键信息提取',
        '批量处理，提升效率'
      ]
    },
    {
      title: 'Graph RAG技术',
      description: '基于知识图谱的检索增强生成，超越传统RAG',
      icon: Network,
      color: 'from-orange-500 to-red-500',
      benefits: [
        'Neo4j图数据库存储关系',
        '实体关系自动识别',
        '多跳推理能力',
        '可视化知识图谱'
      ]
    }
  ];

  // 竞争优势对比表格数据
  const comparisonData = [
    {
      feature: '响应速度',
      traditional: false,
      traditionalText: '云端部署，延迟100-500ms',
      stp: true,
      stpText: '本地部署，响应<50ms',
      icon: Clock
    },
    {
      feature: '数据安全',
      traditional: false,
      traditionalText: '数据上传云端，存在泄漏风险',
      stp: true,
      stpText: '数据不出企业，完全私有化',
      icon: Shield
    },
    {
      feature: '知识管理',
      traditional: false,
      traditionalText: '向量检索，只能匹配相似内容',
      stp: true,
      stpText: 'Graph RAG，理解实体关系',
      icon: Database
    },
    {
      feature: '部署灵活性',
      traditional: false,
      traditionalText: '单体架构，难以扩展定制',
      stp: true,
      stpText: '微服务架构，灵活组合部署',
      icon: Server
    },
    {
      feature: '多模型支持',
      traditional: false,
      traditionalText: '单一模型，功能局限',
      stp: true,
      stpText: '多模型协作，智能切换',
      icon: Brain
    },
    {
      feature: '文档处理',
      traditional: false,
      traditionalText: '基础OCR，准确率有限',
      stp: true,
      stpText: '高精度OCR + AI智能摘要',
      icon: FileSearch
    },
    {
      feature: '项目管理',
      traditional: false,
      traditionalText: '简单文件管理',
      stp: true,
      stpText: '多租户协作，权限控制',
      icon: Users
    },
    {
      feature: '系统架构',
      traditional: false,
      traditionalText: '传统单体应用',
      stp: true,
      stpText: '现代微服务架构',
      icon: Layers
    }
  ];

  // 处理鼠标悬停
  const handleFeatureHover = (index: number) => {
    setHoveredFeature(index);
  };

  const handleFeatureLeave = () => {
    setHoveredFeature(null);
  };

  // 跳转到认证页面
  const handleAuthNavigation = (mode: 'login' | 'register') => {
    navigate(`/auth?mode=${mode}`);
  };

  // 跳转到应用
  const handleStartChat = () => {
    if (user) {
      navigate('/app');
    } else {
      handleAuthNavigation('login');
    }
  };

  return (
    <div className={`min-h-screen transition-colors duration-300 ${
      isDarkMode ? 'bg-[#212121] text-gray-100' : 'bg-white text-gray-900'
    }`}>
      {/* 顶部导航栏 */}
      <header className={`border-b transition-colors duration-300 ${
        isDarkMode ? 'border-gray-800 bg-[#171717]' : 'border-gray-200 bg-white'
      }`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* 左侧：Logo和品牌 */}
            <div className="flex items-center space-x-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                isDarkMode ? 'bg-gradient-to-r from-blue-600 to-purple-600' : 'bg-gradient-to-r from-blue-500 to-purple-500'
              }`}>
                <MessageSquare className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                Lumidoc Intelligence
              </h1>
            </div>

            {/* 右侧：登录注册按钮 */}
            <div className="flex items-center space-x-4">
              {!user ? (
                <>
                  <Button
                    variant="ghost"
                    onClick={() => handleAuthNavigation('login')}
                    className={`transition-colors ${
                      isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                    }`}
                  >
                    <LogIn className="w-4 h-4 mr-2" />
                    登录
                  </Button>
                  <Button
                    onClick={() => handleAuthNavigation('register')}
                    className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0"
                  >
                    注册
                  </Button>
                </>
              ) : (
                <Button
                  onClick={handleStartChat}
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0"
                >
                  进入应用
                </Button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* 主要内容区域 */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Hero 区域 */}
        <section className="py-20 text-center">
          <div className="space-y-8">
            <div className="space-y-4">
              <h1 className="text-5xl lg:text-6xl font-bold">
                <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  企业级智能文档处理平台
                </span>
              </h1>
              <p className={`text-xl max-w-3xl mx-auto ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                基于Graph RAG技术，支持多模型协作，纯本地部署，为企业提供安全、高效、智能的文档处理解决方案
              </p>
            </div>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <Button
                onClick={handleStartChat}
                size="lg"
                className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0 px-8 py-3 text-lg"
              >
                <Sparkles className="w-5 h-5 mr-2" />
                立即体验
              </Button>
              <Button
                variant="outline"
                size="lg"
                onClick={() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })}
                className={`px-8 py-3 text-lg border-blue-600 text-blue-600 hover:bg-blue-600 hover:text-white transition-colors ${
                  isDarkMode ? 'border-blue-500 text-blue-400 hover:bg-blue-500 hover:text-white' : ''
                }`}
              >
                了解更多
                <ChevronDown className="w-5 h-5 ml-2" />
              </Button>
            </div>
          </div>
        </section>

        {/* 核心特性展示 */}
        <section id="features" className="py-20">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">核心功能特性</h2>
            <p className={`text-xl max-w-2xl mx-auto ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
              集成最新AI技术，为企业文档处理提供全方位智能化解决方案
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {coreFeatures.map((feature, index) => {
              const Icon = feature.icon;
              const isHovered = index === hoveredFeature;
              return (
                <div
                  key={index}
                  className={`relative p-6 rounded-2xl border transition-all duration-300 cursor-pointer ${
                    isHovered 
                      ? `scale-105 ${isDarkMode ? 'bg-gray-800 border-blue-500 shadow-2xl shadow-blue-500/20' : 'bg-white border-blue-400 shadow-2xl shadow-blue-400/20'}`
                      : `${isDarkMode ? 'bg-gray-800 border-gray-700 hover:border-gray-600' : 'bg-white border-gray-200 hover:border-gray-300'} hover:scale-102`
                  }`}
                  onMouseEnter={() => handleFeatureHover(index)}
                  onMouseLeave={handleFeatureLeave}
                >
                  {/* 特性图标 */}
                  <div className={`inline-flex p-3 rounded-xl bg-gradient-to-r ${feature.color} mb-4 transition-all duration-300 ${
                    isHovered ? 'scale-110' : ''
                  }`}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  
                  {/* 特性内容 */}
                  <div className="space-y-3">
                    <h3 className={`text-xl font-semibold transition-colors duration-300 ${
                      isHovered ? 'text-blue-600 dark:text-blue-400' : ''
                    }`}>
                      {feature.title}
                    </h3>
                    <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                      {feature.description}
                    </p>
                    
                    {/* 展开的优势列表 */}
                    <div className={`space-y-2 transition-all duration-300 ${
                      isHovered ? 'opacity-100 max-h-64' : 'opacity-0 max-h-0 overflow-hidden'
                    }`}>
                      {feature.benefits.map((benefit, idx) => (
                        <div 
                          key={idx} 
                          className={`flex items-center text-sm transition-all duration-300 ${
                            isHovered ? 'translate-x-0 opacity-100' : 'translate-x-2 opacity-0'
                          }`}
                          style={{ transitionDelay: `${idx * 50}ms` }}
                        >
                          <CheckCircle className="w-4 h-4 text-green-500 mr-2 flex-shrink-0" />
                          <span className={isDarkMode ? 'text-gray-300' : 'text-gray-700'}>{benefit}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  {/* 悬停指示器 */}
                  {isHovered && (
                    <div className="absolute -top-1 -right-1">
                      <div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse"></div>
                    </div>
                  )}
                  
                  {/* 悬停提示 */}
                  {!isHovered && (
                    <div className="absolute bottom-4 right-4 opacity-50">
                      <div className={`text-xs px-2 py-1 rounded ${
                        isDarkMode ? 'bg-gray-700 text-gray-400' : 'bg-gray-100 text-gray-500'
                      }`}>
                        悬停查看详情
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* 智能问答演示 */}
        <section className="py-20" ref={demoRef}>
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">智能问答核心功能</h2>
            <p className={`text-xl max-w-3xl mx-auto ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
              基于Graph RAG技术，结合多模型协作，为您提供精准、智能的问答体验
            </p>
          </div>

          <div className="grid lg:grid-cols-2 gap-12 items-start">
            {/* 左侧：功能特点 */}
            <div className="space-y-8">
              <div className="space-y-6">
                <div className={`p-6 rounded-2xl border ${
                  isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                } hover:shadow-xl transition-all duration-300`}>
                  <div className="flex items-center mb-4">
                    <div className="inline-flex p-3 rounded-xl bg-gradient-to-r from-blue-500 to-purple-500 mr-4">
                      <Brain className="w-6 h-6 text-white" />
                    </div>
                    <h3 className="text-xl font-semibold">智能思考模式</h3>
                  </div>
                  <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-4`}>
                    支持深度思考和快速响应两种模式，根据问题复杂度智能选择
                  </p>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>深度分析复杂问题</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>展示完整思考过程</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>快速响应简单查询</span>
                    </div>
                  </div>
                </div>

                <div className={`p-6 rounded-2xl border ${
                  isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                } hover:shadow-xl transition-all duration-300`}>
                  <div className="flex items-center mb-4">
                    <div className="inline-flex p-3 rounded-xl bg-gradient-to-r from-orange-500 to-red-500 mr-4">
                      <Network className="w-6 h-6 text-white" />
                    </div>
                    <h3 className="text-xl font-semibold">Graph RAG 增强</h3>
                  </div>
                  <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-4`}>
                    超越传统RAG，基于知识图谱的多跳推理，理解复杂关系
                  </p>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>实体关系自动识别</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>多跳逻辑推理</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>上下文关联分析</span>
                    </div>
                  </div>
                </div>

                <div className={`p-6 rounded-2xl border ${
                  isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                } hover:shadow-xl transition-all duration-300`}>
                  <div className="flex items-center mb-4">
                    <div className="inline-flex p-3 rounded-xl bg-gradient-to-r from-green-500 to-emerald-500 mr-4">
                      <FileSearch className="w-6 h-6 text-white" />
                    </div>
                    <h3 className="text-xl font-semibold">文档理解</h3>
                  </div>
                  <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-4`}>
                    深度理解文档内容，提供基于文档的精准问答
                  </p>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>多格式文档支持</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>关键信息提取</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>语义理解分析</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 右侧：动画问答演示 */}
            <div className={`rounded-2xl border ${
              isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
            } shadow-2xl overflow-hidden`}>
              {/* 演示窗口标题栏 */}
              <div className={`px-6 py-4 border-b flex items-center justify-between ${
                isDarkMode ? 'border-gray-700 bg-gray-900' : 'border-gray-200 bg-gray-50'
              }`}>
                <div className="flex items-center space-x-3">
                  <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                  <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                  <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                </div>
                <div className="text-sm font-medium flex items-center space-x-2">
                  <MessageSquare className="w-4 h-4" />
                  <span>Lumidoc Intelligence 问答演示</span>
                </div>
              </div>

              {/* 动画问答内容 */}
              <div className="p-6 space-y-6 min-h-[500px]">
                {/* 用户问题 - 带打字动画 */}
                {animationStep >= 0 && (
                  <div className="flex justify-end">
                    <div className="max-w-[85%] p-4 rounded-2xl bg-gradient-to-r from-blue-600 to-purple-600 text-white">
                      <p className="text-sm font-medium">
                        {questionText}
                        {animationStep === 0 && isTyping && (
                          <span className="inline-block w-2 h-5 bg-white ml-1 animate-pulse"></span>
                        )}
                      </p>
                    </div>
                  </div>
                )}

                {/* AI 思考和回答 */}
                {animationStep >= 1 && (
                  <div className="flex justify-start">
                    <div className="max-w-[90%] space-y-3">
                      {/* 思考过程 - 可折叠 */}
                      {showThinking && (
                        <div className={`transition-all duration-500 overflow-hidden ${
                          thinkingCollapsed ? 'max-h-16 opacity-60' : 'max-h-96 opacity-100'
                        } p-4 rounded-2xl border-2 border-dashed ${
                          isDarkMode 
                            ? 'bg-purple-900/20 border-purple-500/30' 
                            : 'bg-purple-50 border-purple-200'
                        }`}>
                          <div className="flex items-center space-x-2 mb-3">
                            <Brain className={`w-4 h-4 text-purple-500 ${
                              !thinkingCollapsed ? 'animate-pulse' : ''
                            }`} />
                            <span className="text-sm font-medium text-purple-600 dark:text-purple-400">
                              {thinkingCollapsed ? 'AI 思考完成' : 'AI 深度思考中...'}
                            </span>
                            {thinkingCollapsed && (
                              <span className="text-xs text-gray-500 ml-2">(点击展开)</span>
                            )}
                          </div>
                          {!thinkingCollapsed && (
                            <div className="space-y-2 text-xs">
                              <div className={`${isDarkMode ? 'text-gray-300' : 'text-gray-700'} opacity-80`}>
                                • 分析医疗AI的技术发展现状...
                              </div>
                              <div className={`${isDarkMode ? 'text-gray-300' : 'text-gray-700'} opacity-60`}>
                                • 评估诊断准确性提升的关键因素...
                              </div>
                              <div className={`${isDarkMode ? 'text-gray-300' : 'text-gray-700'} opacity-40`}>
                                • 整合相关研究数据和案例...
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {/* AI回答 - 带打字动画 */}
                      {animationStep >= 3 && (
                        <div className={`p-4 rounded-2xl ${
                          isDarkMode ? 'bg-gray-700' : 'bg-gray-100'
                        }`}>
                          <div className="flex items-center space-x-2 mb-3">
                            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                            <span className="text-sm font-medium text-green-600 dark:text-green-400">
                              Lumidoc Intelligence
                            </span>
                          </div>
                          <div className={`text-sm leading-relaxed ${
                            isDarkMode ? 'text-gray-200' : 'text-gray-800'
                          }`}>
                            <div className="whitespace-pre-line">
                              {answerText}
                              {animationStep === 3 && isTyping && (
                                <span className={`inline-block w-2 h-4 ml-1 animate-pulse ${
                                  isDarkMode ? 'bg-gray-200' : 'bg-gray-800'
                                }`}></span>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 完成提示 */}
                {animationStep >= 4 && (
                  <div className="text-center pt-4">
                    <div className={`inline-flex items-center px-4 py-2 rounded-full text-xs ${
                      isDarkMode ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-600'
                    }`}>
                      <div className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></div>
                      可以继续提问或深入讨论...
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* 竞争优势对比表格 */}
        <section className="py-20">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">为什么选择 Lumidoc Intelligence？</h2>
            <div className="max-w-4xl mx-auto mb-12">
              <h3 className="text-2xl font-bold mb-4">
                <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  8项核心功能全面领先
                </span>
              </h3>
              <p className={`text-lg ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                基于Graph RAG技术和微服务架构，Lumidoc Intelligence在响应速度、数据安全、知识管理等关键指标上全面超越传统方案
              </p>
            </div>
          </div>

          <div className={`overflow-hidden rounded-2xl border ${
            isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
          } shadow-2xl`}>
            {/* 表格头 */}
            <div className={`grid grid-cols-4 ${
              isDarkMode ? 'bg-gray-900' : 'bg-gray-50'
            } border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
              <div className="p-6 text-center">
                <h3 className="text-lg font-semibold">功能特性</h3>
              </div>
              <div className="p-6 text-center border-l ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}">
                <h3 className="text-lg font-semibold text-red-600">传统方案</h3>
              </div>
              <div className="p-6 text-center border-l ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}">
                <h3 className="text-lg font-semibold text-green-600">Lumidoc Intelligence</h3>
              </div>
              <div className="p-6 text-center border-l ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}">
                <h3 className="text-lg font-semibold">优势对比</h3>
              </div>
            </div>

            {/* 表格内容 */}
            <div className="divide-y ${isDarkMode ? 'divide-gray-700' : 'divide-gray-200'}">
              {comparisonData.map((item, index) => {
                const Icon = item.icon;
                return (
                  <div 
                    key={index} 
                    className={`grid grid-cols-4 hover:${
                      isDarkMode ? 'bg-gray-750' : 'bg-gray-50'
                    } transition-colors duration-200`}
                  >
                    {/* 功能特性 */}
                    <div className="p-6 flex items-center">
                      <div className="inline-flex p-2 rounded-lg bg-gradient-to-r from-blue-500 to-purple-500 mr-4">
                        <Icon className="w-5 h-5 text-white" />
                      </div>
                      <span className="font-medium">{item.feature}</span>
                    </div>

                    {/* 传统方案 */}
                    <div className={`p-6 border-l flex items-center ${
                      isDarkMode ? 'border-gray-700' : 'border-gray-200'
                    }`}>
                      <div className="flex items-center space-x-3">
                        <div className="flex-shrink-0">
                          <X className="w-6 h-6 text-red-500" />
                        </div>
                        <span className={`text-sm ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                          {item.traditionalText}
                        </span>
                      </div>
                    </div>

                    {/* STP方案 */}
                    <div className={`p-6 border-l flex items-center ${
                      isDarkMode ? 'border-gray-700' : 'border-gray-200'
                    }`}>
                      <div className="flex items-center space-x-3">
                        <div className="flex-shrink-0">
                          <Check className="w-6 h-6 text-green-500" />
                        </div>
                        <span className={`text-sm font-medium ${isDarkMode ? 'text-gray-200' : 'text-gray-800'}`}>
                          {item.stpText}
                        </span>
                      </div>
                    </div>

                    {/* 优势指示 */}
                    <div className={`p-6 border-l flex items-center justify-center ${
                      isDarkMode ? 'border-gray-700' : 'border-gray-200'
                    }`}>
                      <div className="flex items-center space-x-2">
                        <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                        <span className="text-sm font-medium text-green-600">领先</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

          </div>
        </section>


        {/* CTA 区域 */}
        <section className="py-20 text-center">
          <div className={`p-12 rounded-3xl ${
            isDarkMode ? 'bg-gradient-to-r from-gray-800 to-gray-700' : 'bg-gradient-to-r from-blue-50 to-purple-50'
          } border ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
            <div className="space-y-6">
              <h2 className="text-4xl font-bold">
                <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  开启智能文档处理新时代
                </span>
              </h2>
              <p className={`text-xl max-w-2xl mx-auto ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                立即体验 Lumidoc Intelligence，感受 Graph RAG 和多模型协作带来的智能化升级
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
                <Button
                  onClick={handleStartChat}
                  size="lg"
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0 px-8 py-3 text-lg"
                >
                  <ArrowRight className="w-5 h-5 mr-2" />
                  立即开始
                </Button>
                <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                  本地部署 • 数据安全 • 企业级
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* 页脚 */}
      <footer className={`border-t ${isDarkMode ? 'border-gray-800 bg-[#171717]' : 'border-gray-200 bg-white'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="text-center">
            <div className="flex justify-center items-center space-x-3 mb-4">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 flex items-center justify-center">
                <MessageSquare className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                Lumidoc Intelligence
              </span>
            </div>
            <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
              © 2024 Lumidoc Intelligence. 企业级智能文档处理平台，专注于Graph RAG技术创新。
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}