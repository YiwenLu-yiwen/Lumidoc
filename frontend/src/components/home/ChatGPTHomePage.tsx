import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  MessageSquare, 
  Sparkles, 
  Brain, 
  ArrowRight,
  LogIn,
  Globe,
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
import { useTheme } from '@/context/ThemeContext';
import { useLanguage } from '@/context/LanguageContext';
import { supportedLanguages } from '@/utils/language';

interface FeatureCard {
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  benefits: string[];
}


export function ChatGPTHomePage() {
  const [hoveredFeature, setHoveredFeature] = useState<number | null>(null);
  const { user } = useAuth();
  const navigate = useNavigate();
  const { isDarkMode } = useTheme();
  
  const { t, currentLanguage, setLanguage } = useLanguage();

  // 动画演示状态管理
  const [animationStep, setAnimationStep] = useState(0);
  const [questionText, setQuestionText] = useState('');
  const [answerText, setAnswerText] = useState('');
  const [showThinking, setShowThinking] = useState(false);
  const [thinkingCollapsed, setThinkingCollapsed] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const demoRef = useRef<HTMLDivElement>(null);
  const animationStartedRef = useRef(false);
  const animationTimersRef = useRef<Set<number>>(new Set());
  const startAnimationRef = useRef<() => void>(() => {});

  // 完整的问题和答案文本（使用翻译）
  const fullQuestion = t('demoQuestion');
  const fullAnswer = t('demoAnswer');

  // 打字动画效果
  const typeText = useCallback((text: string, callback: (currentText: string) => void, onComplete?: () => void) => {
    let currentIndex = 0;
    const typingInterval = window.setInterval(() => {
      if (currentIndex <= text.length) {
        callback(text.slice(0, currentIndex));
        currentIndex++;
      } else {
        clearInterval(typingInterval);
        animationTimersRef.current.delete(typingInterval);
        onComplete?.();
      }
    }, 120); // 每120ms打一个字符
    animationTimersRef.current.add(typingInterval);
    return typingInterval;
  }, []);

  const scheduleAnimationStep = useCallback((callback: () => void, delay: number) => {
    const timer = window.setTimeout(() => {
      animationTimersRef.current.delete(timer);
      callback();
    }, delay);
    animationTimersRef.current.add(timer);
  }, []);

  // 启动动画序列
  const startAnimation = useCallback(() => {
    if (animationStartedRef.current) return;
    animationStartedRef.current = true;
    
    // 重置状态
    setAnimationStep(0);
    setQuestionText('');
    setAnswerText('');
    setShowThinking(false);
    setThinkingCollapsed(false);
    setIsTyping(true);

    // 步骤1: 用户问题打字动画
    scheduleAnimationStep(() => {
      typeText(fullQuestion, setQuestionText, () => {
        setIsTyping(false);
        setAnimationStep(1);
        
        // 步骤2: 显示思考过程
        scheduleAnimationStep(() => {
          setShowThinking(true);
          setAnimationStep(2);
          
          // 步骤3: 开始回答并折叠思考
          scheduleAnimationStep(() => {
            setThinkingCollapsed(true);
            setAnimationStep(3);
            setIsTyping(true);
            
            // 步骤4: AI回答打字动画
            scheduleAnimationStep(() => {
              typeText(fullAnswer, setAnswerText, () => {
                setIsTyping(false);
                setAnimationStep(4);
                
                // 5秒后重新开始动画
                scheduleAnimationStep(() => {
                  animationStartedRef.current = false;
                  startAnimationRef.current();
                }, 5000);
              });
            }, 500);
          }, 3000); // 思考3秒
        }, 1000);
      });
    }, 1000);
  }, [fullAnswer, fullQuestion, scheduleAnimationStep, typeText]);
  startAnimationRef.current = startAnimation;

  useEffect(() => () => {
    animationTimersRef.current.forEach(timer => window.clearTimeout(timer));
    animationTimersRef.current.clear();
    animationStartedRef.current = false;
  }, []);

  // 监听滚动，当演示区域进入视野时开始动画
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry.isIntersecting) {
          startAnimation();
        }
      },
      {
        threshold: 0.3,
        rootMargin: '0px 0px -100px 0px'
      }
    );

    const demoElement = demoRef.current;
    if (demoElement) {
      observer.observe(demoElement);
    }

    return () => {
      if (demoElement) {
        observer.unobserve(demoElement);
      }
    };
  }, [startAnimation]);

  // 核心特性展示（使用翻译）
  const coreFeatures: FeatureCard[] = [
    {
      title: t('multiModelSupport'),
      description: t('multiModelDescription'),
      icon: Brain,
      color: 'from-purple-500 to-pink-500',
      benefits: [
        t('mainstreamModels'),
        t('intelligentModelRecognition'),
        t('autoModelRecommendation'),
        t('unifiedAPIInterface')
      ]
    },
    {
      title: t('smartProjectManagement'),
      description: t('smartProjectDescription'),
      icon: Users,
      color: 'from-blue-500 to-cyan-500',
      benefits: [
        t('multiProjectManagement'),
        t('teamCollaboration'),
        t('projectProgress'),
        t('documentVersionControl')
      ]
    },
    {
      title: t('intelligentDocumentProcessing'),
      description: t('intelligentDocumentDescription'),
      icon: FileSearch,
      color: 'from-green-500 to-emerald-500',
      benefits: [
        t('multiFormatSupport'),
        t('highAccuracyOCR'),
        t('aiSummaryExtraction'),
        t('batchProcessing')
      ]
    },
    {
      title: t('graphRAGTechnology'),
      description: t('graphRAGDescription'),
      icon: Network,
      color: 'from-orange-500 to-red-500',
      benefits: [
        t('neo4jGraphStorage'),
        t('entityRelationRecognition'),
        t('multiHopReasoning'),
        t('visualKnowledgeGraph')
      ]
    }
  ];

  // 竞争优势对比表格数据
  const comparisonData = [
    {
      feature: t('responseSpeed'),
      traditional: false,
      traditionalText: t('cloudDeploymentLatency'),
      lumidoc: true,
      lumidocText: t('localDeploymentFast'),
      icon: Clock
    },
    {
      feature: t('dataSecurity'),
      traditional: false,
      traditionalText: t('dataUploadRisk'),
      lumidoc: true,
      lumidocText: t('dataStaysPrivate'),
      icon: Shield
    },
    {
      feature: t('knowledgeManagement'),
      traditional: false,
      traditionalText: t('vectorSearchLimited'),
      lumidoc: true,
      lumidocText: t('graphRAGRelations'),
      icon: Database
    },
    {
      feature: t('deploymentFlexibility'),
      traditional: false,
      traditionalText: t('monolithicArchitecture'),
      lumidoc: true,
      lumidocText: t('microservicesFlexible'),
      icon: Server
    },
    {
      feature: t('multiModelSupport'),
      traditional: false,
      traditionalText: t('singleModelLimited'),
      lumidoc: true,
      lumidocText: t('multiModelCollaboration'),
      icon: Brain
    },
    {
      feature: t('documentProcessing'),
      traditional: false,
      traditionalText: t('basicOCRLimited'),
      lumidoc: true,
      lumidocText: t('smartOCRAccurate'),
      icon: FileSearch
    },
    {
      feature: t('projectManagement'),
      traditional: false,
      traditionalText: t('simpleFileManagement'),
      lumidoc: true,
      lumidocText: t('multiTenantCollaboration'),
      icon: Users
    },
    {
      feature: t('systemArchitecture'),
      traditional: false,
      traditionalText: t('traditionalMonolith'),
      lumidoc: true,
      lumidocText: t('modernMicroservices'),
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
          <div className="flex min-h-16 flex-wrap items-center justify-between gap-3 py-3 sm:flex-nowrap sm:py-0">
            {/* 左侧：Logo和品牌 */}
            <div className="flex items-center space-x-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                isDarkMode ? 'bg-gradient-to-r from-blue-600 to-purple-600' : 'bg-gradient-to-r from-blue-500 to-purple-500'
              }`}>
                <MessageSquare className="w-6 h-6 text-white" />
              </div>
              <h1 className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-lg font-bold text-transparent sm:text-2xl">
                Lumidoc<span className="hidden lg:inline"> Intelligence</span>
              </h1>
            </div>

            {/* 右侧：语言选择和账号入口 */}
            <div className="ml-auto flex items-center space-x-2 sm:space-x-4">
              <div className="relative">
                <Globe aria-hidden="true" className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2" />
                <select
                  aria-label={t('language')}
                  value={currentLanguage}
                  onChange={event => setLanguage(event.target.value)}
                  className={`h-10 rounded-md border py-2 pl-8 pr-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    isDarkMode ? 'border-gray-600 bg-[#171717] text-gray-100' : 'border-gray-300 bg-white text-gray-900'
                  }`}
                >
                  {supportedLanguages.map(language => (
                    <option key={language.code} value={language.code}>{language.name}</option>
                  ))}
                </select>
              </div>
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
                    {t('login')}
                  </Button>
                  <Button
                    onClick={() => handleAuthNavigation('register')}
                    className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0"
                  >
                    {t('register')}
                  </Button>
                </>
              ) : (
                <Button
                  onClick={handleStartChat}
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0"
                >
                  {t('enterApp')}
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
                  {t('enterpriseDocumentPlatform')}
                </span>
              </h1>
              <p className={`text-xl max-w-3xl mx-auto ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                {t('platformDescription')}
              </p>
            </div>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <Button
                onClick={handleStartChat}
                size="lg"
                className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0 px-8 py-3 text-lg"
              >
                <Sparkles className="w-5 h-5 mr-2" />
                {t('tryNow')}
              </Button>
              <Button
                variant="outline"
                size="lg"
                onClick={() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })}
                className={`px-8 py-3 text-lg border-blue-600 text-blue-600 hover:bg-blue-600 hover:text-white transition-colors ${
                  isDarkMode ? 'border-blue-500 text-blue-400 hover:bg-blue-500 hover:text-white' : ''
                }`}
              >
                {t('learnMore')}
                <ChevronDown className="w-5 h-5 ml-2" />
              </Button>
            </div>
          </div>
        </section>

        {/* 核心特性展示 */}
        <section id="features" className="py-20">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">{t('coreFunctionalities')}</h2>
            <p className={`text-xl max-w-2xl mx-auto ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
              {t('comprehensiveSolution')}
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
                        {t('hoverForDetails')}
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
            <h2 className="text-4xl font-bold mb-4">{t('intelligentQACore')}</h2>
            <p className={`text-xl max-w-3xl mx-auto ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
              {t('qaExperienceDescription')}
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
                    <h3 className="text-xl font-semibold">{t('intelligentThinkingMode')}</h3>
                  </div>
                  <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-4`}>
                    {t('thinkingModeDescription')}
                  </p>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>{t('deepComplexAnalysis')}</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>{t('showThinkingProcess')}</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>{t('fastSimpleQueries')}</span>
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
                    <h3 className="text-xl font-semibold">{t('graphRAGEnhancement')}</h3>
                  </div>
                  <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-4`}>
                    {t('graphRAGDescription')}
                  </p>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>{t('entityRelationRecognition')}</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>{t('multiHopLogicalReasoning')}</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>{t('contextualAnalysis')}</span>
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
                    <h3 className="text-xl font-semibold">{t('documentUnderstanding')}</h3>
                  </div>
                  <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} mb-4`}>
                    {t('documentUnderstandingDescription')}
                  </p>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>{t('multiFormatSupport')}</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>{t('keyInfoExtraction')}</span>
                    </div>
                    <div className="flex items-center">
                      <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                      <span>{t('semanticAnalysis')}</span>
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
                  <span>{t('qaDemoTitle')}</span>
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
                              {thinkingCollapsed ? t('aiThinkingComplete') : t('aiDeepThinking')}
                            </span>
                            {thinkingCollapsed && (
                              <span className="text-xs text-gray-500 ml-2">({t('clickToExpand')})</span>
                            )}
                          </div>
                          {!thinkingCollapsed && (
                            <div className="space-y-2 text-xs">
                              <div className={`${isDarkMode ? 'text-gray-300' : 'text-gray-700'} opacity-80`}>
                                • {t('analyzingMedicalAI')}...
                              </div>
                              <div className={`${isDarkMode ? 'text-gray-300' : 'text-gray-700'} opacity-60`}>
                                • {t('evaluatingDiagnosticFactors')}...
                              </div>
                              <div className={`${isDarkMode ? 'text-gray-300' : 'text-gray-700'} opacity-40`}>
                                • {t('integratingResearchData')}...
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
                      {t('continueDiscussion')}...
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
            <h2 className="text-4xl font-bold mb-4">{t('whyChooseLumidoc')}</h2>
            <div className="max-w-4xl mx-auto mb-12">
              <h3 className="text-2xl font-bold mb-4">
                <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  {t('eightCoreAdvantages')}
                </span>
              </h3>
              <p className={`text-lg ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                {t('comprehensiveAdvantages')}
              </p>
            </div>
          </div>

          <div className={`overflow-x-auto rounded-2xl border ${
            isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
          } shadow-2xl`}>
            {/* 表格头 */}
            <div className={`grid min-w-[760px] grid-cols-4 ${
              isDarkMode ? 'bg-gray-900' : 'bg-gray-50'
            } border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
              <div className="p-6 text-center">
                <h3 className="text-lg font-semibold">{t('features')}</h3>
              </div>
              <div className="border-l border-border p-6 text-center">
                <h3 className="text-lg font-semibold text-red-600">{t('traditional')}</h3>
              </div>
              <div className="border-l border-border p-6 text-center">
                <h3 className="text-lg font-semibold text-green-600">{t('lumidocIntelligence')}</h3>
              </div>
              <div className="border-l border-border p-6 text-center">
                <h3 className="text-lg font-semibold">{t('advantageComparison')}</h3>
              </div>
            </div>

            {/* 表格内容 */}
            <div className="min-w-[760px] divide-y divide-border">
              {comparisonData.map((item, index) => {
                const Icon = item.icon;
                return (
                  <div 
                    key={index} 
                    className={`grid grid-cols-4 transition-colors duration-200 ${
                      isDarkMode ? 'hover:bg-gray-700/50' : 'hover:bg-gray-50'
                    }`}
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

                    {/* Lumidoc方案 */}
                    <div className={`p-6 border-l flex items-center ${
                      isDarkMode ? 'border-gray-700' : 'border-gray-200'
                    }`}>
                      <div className="flex items-center space-x-3">
                        <div className="flex-shrink-0">
                          <Check className="w-6 h-6 text-green-500" />
                        </div>
                        <span className={`text-sm font-medium ${isDarkMode ? 'text-gray-200' : 'text-gray-800'}`}>
                          {item.lumidocText}
                        </span>
                      </div>
                    </div>

                    {/* 优势指示 */}
                    <div className={`p-6 border-l flex items-center justify-center ${
                      isDarkMode ? 'border-gray-700' : 'border-gray-200'
                    }`}>
                      <div className="flex items-center space-x-2">
                        <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                        <span className="text-sm font-medium text-green-600">{t('leading')}</span>
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
                  {t('openNewEra')}
                </span>
              </h2>
              <p className={`text-xl max-w-2xl mx-auto ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                {t('experienceLumidoc')}
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
                <Button
                  onClick={handleStartChat}
                  size="lg"
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white border-0 px-8 py-3 text-lg"
                >
                  <ArrowRight className="w-5 h-5 mr-2" />
                  {t('startNow')}
                </Button>
                <div className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                  {t('localDeploymentSecure')}
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
              © {new Date().getFullYear()} {t('copyrightNotice')}
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
