import { useEffect, useRef, useState } from 'react'
import { Network, Node, Edge, Options } from 'vis-network'
import { useParams } from 'react-router-dom'
import { fetchGraphData, getNodeNeighbors, searchNodes } from '../api'
import 'vis-network/styles/vis-network.css'
import { Button } from '../../../components/ui/button'
import { toast } from 'sonner'

// Define color mapping for different node types with muted colors
const nodeColors = {
  default: '#6B7280',        // 中灰色
  entity: '#64748B',         // 石板灰
  organization: '#475569',   // 深石板灰
  person: '#52525B',         // 锌灰
  location: '#57534E',       // 暖灰
  event: '#525252',          // 真灰
  concept: '#4B5563',        // 冷灰
  product: '#4A5568',        // 蓝灰
  technology: '#374151',     // 深灰
  document: '#6B7280',       // 中灰色
  chunk: '#4B5563',          // 中灰色
  embedding: '#374151',      // 浅灰色
  query: '#1F2937',          // 深色
  source: '#9CA3AF',         // 亮灰色
  target: '#D1D5DB',         // 浅色
  intermediate: '#6B7280',   // 中灰色
  text: '#9CA3AF',           // 亮灰色
  code: '#6B7280',           // 中灰色
  image: '#4B5563',          // 深灰色
  audio: '#374151',          // 浅灰色
  video: '#1F2937',          // 深色
  data: '#9CA3AF',           // 亮灰色
  model: '#6B7280',          // 中灰色
  api: '#4B5563',            // 深灰色
  Entity: '#64748B'          // 石板灰，用于实体节点
}

// Define color mapping for different relationship types with bright colors for visibility
const relationshipColors = {
  default: '#FBBF24',        // 明亮黄色
  'relates_to': '#34D399',   // 翠绿色
  'contains': '#60A5FA',     // 亮蓝色
  'member_of': '#F87171',    // 珊瑚红
  'located_in': '#A78BFA',   // 紫色
  'part_of': '#FB7185',      // 粉红色
  'similar_to': '#10B981',   // 绿色
  'depends_on': '#F59E0B',   // 橙色
  'created_by': '#EF4444',   // 红色
  'associated_with': '#8B5CF6', // 紫色
  'interacts_with': '#06B6D4',  // 青色
  'influences': '#84CC16',      // lime绿
  'supports': '#F97316',        // 橙色
  'conflicts_with': '#DC2626',  // 深红色
  'derives_from': '#7C3AED',    // 紫色
  'leads_to': '#059669',        // 深绿色
  'causes': '#DB2777',          // 粉色
  'enables': '#0D9488',         // 蓝绿色
  'restricts': '#B91C1C',       // 深红色
  '运动活动与场地关系': '#00FF00', // 鲜绿色，专门为我们的关系类型
  '运动活动': '#FF6B6B',
  '活动地点': '#4ECDC4',
  '产品关系': '#45B7D1',
  '商业关系': '#96CEB4',
  '组织关系': '#FFEAA7'
}

const getNodeColor = (node: NodeData) => {
  // 首先尝试通过type获取颜色
  if (node.type && nodeColors[node.type as keyof typeof nodeColors]) {
    return {
      background: nodeColors[node.type as keyof typeof nodeColors],
      border: '#374151',  // 深色边框
      highlight: {
        background: nodeColors[node.type as keyof typeof nodeColors],
        border: '#1F2937'  // 高亮时的边框颜色
      },
      hover: {
        background: nodeColors[node.type as keyof typeof nodeColors],
        border: '#1F2937'  // 悬停时的边框颜色
      }
    }
  }
  
  // 如果没有type，尝试使用role或category
  if (node.role && nodeColors[node.role as keyof typeof nodeColors]) {
    return {
      background: nodeColors[node.role as keyof typeof nodeColors],
      border: '#374151',
      highlight: {
        background: nodeColors[node.role as keyof typeof nodeColors],
        border: '#1F2937'
      },
      hover: {
        background: nodeColors[node.role as keyof typeof nodeColors],
        border: '#1F2937'
      }
    }
  }
  
  // 默认颜色
  return {
    background: nodeColors.default,
    border: '#374151',
    highlight: {
      background: nodeColors.default,
      border: '#1F2937'
    },
    hover: {
      background: nodeColors.default,
      border: '#1F2937'
    }
  }
}

const getRelationshipColor = (edge: EdgeData) => {
  // 首先尝试通过label完全匹配
  if (edge.label && relationshipColors[edge.label as keyof typeof relationshipColors]) {
    return relationshipColors[edge.label as keyof typeof relationshipColors]
  }
  
  // 如果label包含描述信息，尝试部分匹配
  if (edge.label) {
    const label = edge.label.toString()
    for (const [colorKey, color] of Object.entries(relationshipColors)) {
      if (label.includes(colorKey)) {
        return color
      }
    }
  }
  
  // 尝试通过type获取颜色
  if (edge.type && relationshipColors[edge.type as keyof typeof relationshipColors]) {
    return relationshipColors[edge.type as keyof typeof relationshipColors]
  }
  
  // 默认颜色
  return relationshipColors.default
}

// Define the shape of our node data from the API
interface NodeData {
  id: string
  label?: string
  type?: string
  role?: string
  description?: string
  properties?: Record<string, unknown>
}

// Define the shape of our edge data from the API
interface EdgeData {
  source: string
  target: string
  label?: string
  type?: string
}

interface CustomNode extends Node {
  type?: string
  description?: string
  properties?: Record<string, unknown>
  file_path?: string
  degree?: number
}

interface NodeDetails {
  id: string
  label: string
  type?: string
  description?: string
  properties?: Record<string, unknown>
  relationships?: Array<{
    type: string
    node: string
  }>
}

type GraphViewData = { nodes: NodeData[]; edges: EdgeData[] }

export default function Graph() {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<Network | null>(null)
  const graphNodesRef = useRef<CustomNode[]>([])
  const renderGraphRef = useRef<(data: GraphViewData) => void>(() => {})
  const { projectId } = useParams()
  const [selectedNode, setSelectedNode] = useState<NodeDetails | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [loading, setLoading] = useState(false)

  // 初始加载图谱数据
  useEffect(() => {
    async function loadGraph() {
      if (!projectId || !containerRef.current) return

      try {
        setLoading(true)
        console.log(`[Graph] 开始加载项目 ${projectId} 的图谱数据`)
        
        const data = await fetchGraphData(projectId)
        console.log('[Graph] 收到图谱数据:', data)
        
        // 确保数据格式正确
        const safeData = {
          nodes: Array.isArray(data?.nodes) ? data.nodes : [],
          edges: Array.isArray(data?.edges) ? data.edges : []
        }
        
        renderGraphRef.current(safeData)
        
        // 显示加载结果
        if (safeData.nodes.length === 0) {
          toast('当前项目暂无图谱数据', { 
            description: '请先上传文档并处理后再查看图谱' 
          })
        } else {
          console.log(`[Graph] 成功加载 ${safeData.nodes.length} 个节点和 ${safeData.edges.length} 条边`)
        }
      } catch (error) {
        console.error('[Graph] 加载图谱数据失败:', error)
        // 提供空数据以确保界面正常工作
        const emptyData = { nodes: [], edges: [] }
        renderGraphRef.current(emptyData)
        
        // 显示友好的错误提示
        toast('图谱数据加载失败', { 
          description: '请检查网络连接或稍后重试' 
        })
      } finally {
        setLoading(false)
      }
    }

    loadGraph()
  }, [projectId])

  // 渲染图谱
  const renderGraph = (data: GraphViewData) => {
    if (!containerRef.current) return

    // 处理空数据情况
    if (!data || !data.nodes || !data.edges) {
      console.warn('[Graph] 收到空数据，使用默认空数据结构')
      data = { nodes: [], edges: [] }
    }

    // 确保数组是有效的
    if (!Array.isArray(data.nodes)) {
      console.warn('[Graph] nodes不是数组，重置为空数组')
      data.nodes = []
    }
    if (!Array.isArray(data.edges)) {
      console.warn('[Graph] edges不是数组，重置为空数组') 
      data.edges = []
    }

    // Transform data for vis-network
    const nodes = (data.nodes as NodeData[]).map((node, index) => {
      // 安全地处理可能为空的节点数据
      if (!node || typeof node !== 'object') {
        console.warn(`[Graph] 跳过无效节点 #${index}:`, node)
        return null
      }

      // 确保节点有有效的ID
      const nodeId = node.id || `node_${index}`
      const nodeLabel = node.label || node.id || `Node ${index}`
      
      const customNode: CustomNode = {
        id: nodeId,
        label: nodeLabel,
        type: node.type || 'default',
        description: node.description || '',
        properties: node.properties || {},
        color: getNodeColor(node),
        size: 40,
        physics: true,
        font: {
          color: '#E5E7EB',  // 浅灰色文字
          size: 14,
          face: 'Inter, system-ui, -apple-system, sans-serif',
          bold: 'bold' as const
        }
      }
      return customNode
    }).filter(node => node !== null) as CustomNode[]
    graphNodesRef.current = nodes

    // 边的样式设置
    const edges = (data.edges as EdgeData[]).map((edge, index) => {
      // 安全地处理可能为空的边数据
      if (!edge || typeof edge !== 'object') {
        console.warn(`[Graph] 跳过无效边 #${index}:`, edge)
        return null
      }

      // 确保边有有效的source和target
      if (!edge.source || !edge.target) {
        console.warn(`[Graph] 跳过无效边（缺少source或target） #${index}:`, edge)
        return null
      }

      const relationshipColor = getRelationshipColor(edge)
      return {
        from: edge.source,
        to: edge.target,
        title: edge.label || '',
        label: edge.label || '',
        color: {
          color: relationshipColor,
          highlight: '#FFFFFF',  // 高亮时为白色
          hover: '#FFFF00'       // 悬停时为黄色
        },
        arrows: {
          to: {
            enabled: true,
            scaleFactor: 0.8,
            color: relationshipColor
          }
        },
        width: 4,
        smooth: {
          enabled: true,
          type: 'continuous',
          roundness: 0.3
        },
        font: {
          color: '#FFFFFF',
          size: 14,
          face: 'Inter, system-ui, -apple-system, sans-serif',
          background: 'rgba(0,0,0,0.7)',
          strokeWidth: 2,
          strokeColor: '#000000'
        }
      }
    }).filter(edge => edge !== null) as Edge[]

    // vis-network配置选项
    const options: Options = {
      nodes: {
        shape: 'dot',
        borderWidth: 2,
        shadow: true,
        scaling: {
          min: 20,
          max: 30
        }
      },
      physics: {
        enabled: true,
        barnesHut: {
          gravitationalConstant: -1000,
          centralGravity: 0.01,
          springLength: 200,
          springConstant: 0.02,
          damping: 0.09,
          avoidOverlap: 1
        },
        stabilization: {
          enabled: true,
          iterations: 1000,
          updateInterval: 50
        }
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        zoomView: true,
        dragView: true,
        dragNodes: true,
        zoomSpeed: 1,
        navigationButtons: false,  // 禁用导航按钮
        keyboard: true,
        hideEdgesOnDrag: false,
        hideEdgesOnZoom: false
      },
      edges: {
        width: 4,
        shadow: true,
        color: {
          color: '#FBBF24',     // 默认明亮黄色
          highlight: '#FFFFFF', // 高亮白色
          hover: '#FFFF00'      // 悬停黄色
        },
        smooth: {
          enabled: true,
          type: 'continuous',
          roundness: 0.3
        },
        font: {
          size: 14,
          color: '#FFFFFF',
          background: 'rgba(0,0,0,0.8)',
          strokeWidth: 2,
          strokeColor: '#000000',
          face: 'Inter, system-ui, -apple-system, sans-serif'
        }
      }
    }

    // Create network
    try {
      if (networkRef.current) {
        networkRef.current.destroy()
        networkRef.current = null
      }
      
      console.log(`[Graph] 创建网络：${nodes.length}个节点，${edges.length}条边`)
      
      networkRef.current = new Network(
        containerRef.current,
        { nodes, edges },
        options
      )
    } catch (error) {
      console.error('[Graph] 创建网络失败:', error)
      toast.error('图谱渲染失败')
      return
    }

    // Handle node selection
    networkRef.current.on('click', (params) => {
      try {
        if (params.nodes && params.nodes.length > 0) {
          const nodeId = String(params.nodes[0])
          const node = nodes.find(n => n.id === nodeId)
          if (node) {
            console.log('[Graph] 选中节点:', node)
            // 获取与该节点相关的边
            const nodeRelationships = edges
              .filter(edge => edge && (edge.from === nodeId || edge.to === nodeId))
              .map(edge => {
                const connectedNodeId = edge.from === nodeId ? edge.to : edge.from
                const connectedNode = nodes.find(n => n.id === connectedNodeId)
                return {
                  type: String(edge.title || edge.label || '关联'),
                  node: connectedNode?.label || String(connectedNodeId)
                }
              })
              .filter(rel => rel.node) // 过滤掉空的关系

            setSelectedNode({
              id: nodeId,
              label: String(node.label || nodeId),
              type: node.type || 'default',
              description: node.description || '',
              properties: node.properties || {},
              relationships: nodeRelationships
            })
          }
        } else {
          setSelectedNode(null)
        }
      } catch (error) {
        console.error('[Graph] 节点选择处理失败:', error)
        // 不显示错误提示，避免干扰用户体验
      }
    })

    // Handle double click to explore neighbors
    networkRef.current.on('doubleClick', async (params) => {
      try {
        if (params.nodes && params.nodes.length > 0 && projectId) {
          const nodeId = String(params.nodes[0])
          const node = nodes.find(n => n.id === nodeId)
          const nodeLabel = node?.label || nodeId
          
          console.log(`[Graph] 双击节点获取邻居: ${nodeLabel} (${nodeId})`)
          
          setLoading(true)
          const neighborsData = await getNodeNeighbors(projectId, nodeId, 1)
          
          if (neighborsData && (neighborsData.nodes.length > 0 || neighborsData.edges.length > 0)) {
            renderGraph(neighborsData)
            toast.success(`显示节点 ${nodeLabel} 的邻居`)
          } else {
            toast('该节点暂无邻居节点', { description: '可能是孤立节点或数据未加载完成' })
          }
        }
      } catch (error) {
        console.error('[Graph] 获取邻居节点失败:', error)
        toast.error('获取邻居节点失败', { description: '请稍后重试或检查网络连接' })
      } finally {
        setLoading(false)
      }
    })
  }
  renderGraphRef.current = renderGraph


  // 搜索节点
  const searchNodesLocal = (term: string) => {
    try {
      if (!networkRef.current || !term) {
        networkRef.current?.unselectAll()
        return
      }

      const matches = new Set<string>()
      const normalizedTerm = term.toLowerCase()

      graphNodesRef.current.forEach((node) => {
        const label = String(node.label || '').toLowerCase()
        const type = String(node.type || '').toLowerCase()
        const description = String(node.description || '').toLowerCase()

        if (label.includes(normalizedTerm) ||
            type.includes(normalizedTerm) ||
            description.includes(normalizedTerm)) {
          matches.add(String(node.id))
        }
      })

      networkRef.current.selectNodes(Array.from(matches), false)
      console.log(`[Graph] 本地搜索"${term}"找到 ${matches.size} 个匹配节点`)
    } catch (error) {
      console.error('[Graph] 本地搜索失败:', error)
      networkRef.current?.unselectAll()
    }
  }

  // 远程搜索节点
  const searchNodesRemote = async (term: string) => {
    if (!projectId || !term) {
      networkRef.current?.unselectAll()
      return
    }

    try {
      console.log(`[Graph] 开始远程搜索: "${term}"`)
      const searchResult = await searchNodes(projectId, term)
      
      if (searchResult && searchResult.nodes) {
        renderGraph(searchResult)
        
        // 高亮搜索结果
        const matches = new Set(searchResult.nodes.map(node => node.id).filter(id => id))
        networkRef.current?.selectNodes(Array.from(matches), false)
        
        if (searchResult.nodes.length > 0) {
          toast.success(`找到 ${searchResult.nodes.length} 个相关节点`)
        } else {
          toast('未找到匹配的节点', { description: '请尝试其他搜索关键词' })
        }
      } else {
        toast('搜索返回空结果', { description: '请尝试其他搜索关键词' })
      }
    } catch (error) {
      console.error('[Graph] 远程搜索失败:', error)
      toast.error('搜索失败', { description: '请检查网络连接或稍后重试' })
    }
  }

  // 监听搜索词变化
  useEffect(() => {
    searchNodesLocal(searchTerm)
  }, [searchTerm])

  return (
    <div className="flex flex-col h-full">
      {/* 搜索框 */}
      <div className="mb-4 flex gap-2">
        <input
          type="text"
          placeholder="搜索节点..."
          className="p-2 flex-1 bg-gray-700 text-white rounded-lg"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <Button 
          onClick={() => searchNodesRemote(searchTerm)}
          variant="outline"
          disabled={!searchTerm || loading}
        >
          远程搜索
        </Button>
        <Button 
          onClick={() => {
            setSearchTerm('')
            networkRef.current?.unselectAll()
            if (projectId) {
              fetchGraphData(projectId).then(data => {
                renderGraph(data)
              }).catch(() => {
                // 忽略错误，避免重复提示
              })
            }
          }}
          variant="outline"
        >
          清除搜索
        </Button>
      </div>

      <div className="flex flex-col lg:flex-row gap-4 h-full">
        {/* 图谱容器 */}
        <div className="flex-grow h-[500px] lg:h-full bg-gray-900 rounded-lg shadow-lg overflow-hidden relative">
          {loading && (
            <div className="absolute inset-0 bg-gray-900 bg-opacity-75 flex items-center justify-center z-10">
              <div className="text-white text-lg">加载图谱数据中...</div>
            </div>
          )}
          <div ref={containerRef} className="w-full h-full" />
        </div>

        {/* 节点详情面板 */}
        {selectedNode && (
          <div className="w-full lg:w-1/3 bg-gray-800 p-4 rounded-lg shadow-lg overflow-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-bold text-gray-200">{selectedNode.label}</h3>
              <Button
                onClick={async () => {
                  if (!projectId || !selectedNode) return
                  try {
                    setLoading(true)
                    console.log(`[Graph] 按钮点击获取邻居: ${selectedNode.label} (${selectedNode.id})`)
                    
                    const neighborsData = await getNodeNeighbors(projectId, selectedNode.id, 1)
                    
                    if (neighborsData && (neighborsData.nodes.length > 0 || neighborsData.edges.length > 0)) {
                      renderGraph(neighborsData)
                      toast.success(`显示节点 ${selectedNode.label} 的邻居`)
                    } else {
                      toast('该节点暂无邻居节点', { 
                        description: '可能是孤立节点或数据未加载完成' 
                      })
                    }
                  } catch (error) {
                    console.error('[Graph] 按钮获取邻居节点失败:', error)
                    toast.error('获取邻居节点失败', { 
                      description: '请稍后重试或检查网络连接' 
                    })
                  } finally {
                    setLoading(false)
                  }
                }}
                variant="outline"
                size="sm"
                disabled={loading || !selectedNode}
              >
                {loading ? '加载中...' : '查看邻居'}
              </Button>
            </div>
            
            {selectedNode.type && (
              <div className="mb-2">
                <span className="text-gray-400">类型: </span>
                <span className="px-2 py-1 bg-blue-600 text-white rounded-md text-sm">
                  {selectedNode.type}
                </span>
              </div>
            )}
            
            <div className="mb-2">
              <span className="text-gray-400">ID: </span>
              <span className="text-gray-200 font-mono text-sm">{selectedNode.id}</span>
            </div>
            
            {selectedNode.description && (
              <div className="mb-2">
                <span className="text-gray-400">描述: </span>
                <span className="text-gray-200">{selectedNode.description}</span>
              </div>
            )}
            
            {/* 属性列表 */}
            {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
              <>
                <h4 className="font-semibold text-gray-300 mt-4 mb-2">属性</h4>
                <div className="bg-gray-700 p-2 rounded-md">
                  {Object.entries(selectedNode.properties)
                    .filter(([key]) => !['id', 'type', 'label', 'description'].includes(key))
                    .map(([key, value]) => (
                      <div key={key} className="mb-1">
                        <span className="text-gray-400">{key}: </span>
                        <span className="text-gray-200">
                          {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                        </span>
                      </div>
                    ))}
                </div>
              </>
            )}
            
            {/* 关系列表 */}
            {selectedNode.relationships && selectedNode.relationships.length > 0 && (
              <>
                <h4 className="font-semibold text-gray-300 mt-4 mb-2">
                  关系 ({selectedNode.relationships.length})
                </h4>
                <div className="bg-gray-700 p-2 rounded-md max-h-64 overflow-y-auto">
                  {selectedNode.relationships.map((rel, index) => (
                    <div key={index} className="mb-2 p-2 bg-gray-600 rounded-md">
                      <div className="flex justify-between items-center">
                        <span className="text-blue-400 font-medium">{rel.type || '关联'}</span>
                        <span className="text-xs text-gray-400">#{index + 1}</span>
                      </div>
                      <div className="text-gray-200 mt-1">{rel.node}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
            
            {/* 操作说明 */}
            <div className="mt-4 p-2 bg-gray-700 rounded-md">
              <h4 className="font-semibold text-gray-300 mb-2">操作说明</h4>
              <div className="text-xs text-gray-400">
                <div>• 单击节点查看详情</div>
                <div>• 双击节点查看邻居</div>
                <div>• 拖拽节点调整位置</div>
                <div>• 滚轮缩放图谱</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
