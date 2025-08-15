import { create } from 'zustand'
import { DirectedGraph } from 'graphology'

interface GraphState {
  // Graph data
  rawGraph: any | null
  sigmaGraph: DirectedGraph | null
  sigmaInstance: any | null
  
  // UI state
  selectedNode: string | null
  focusedNode: string | null
  moveToSelectedNode: boolean
  isFetching: boolean
  graphIsEmpty: boolean
  
  // Actions
  setRawGraph: (rawGraph: any | null) => void
  setSigmaGraph: (sigmaGraph: DirectedGraph | null) => void
  setSigmaInstance: (sigmaInstance: any | null) => void
  setSelectedNode: (nodeId: string | null, moveToNode?: boolean) => void
  setFocusedNode: (nodeId: string | null) => void
  setMoveToSelectedNode: (move: boolean) => void
  setIsFetching: (isFetching: boolean) => void
  setGraphIsEmpty: (isEmpty: boolean) => void
  reset: () => void
}

const useGraphStore = create<GraphState>((set) => ({
  // Initial state
  rawGraph: null,
  sigmaGraph: null,
  sigmaInstance: null,
  selectedNode: null,
  focusedNode: null,
  moveToSelectedNode: false,
  isFetching: false,
  graphIsEmpty: false,

  // Actions
  setRawGraph: (rawGraph) => set({ rawGraph }),
  setSigmaGraph: (sigmaGraph) => set({ sigmaGraph }),
  setSigmaInstance: (sigmaInstance) => set({ sigmaInstance }),
  setSelectedNode: (nodeId, moveToNode = false) => set({ 
    selectedNode: nodeId,
    moveToSelectedNode: moveToNode
  }),
  setFocusedNode: (nodeId) => set({ focusedNode: nodeId }),
  setMoveToSelectedNode: (move) => set({ moveToSelectedNode: move }),
  setIsFetching: (isFetching) => set({ isFetching }),
  setGraphIsEmpty: (isEmpty) => set({ graphIsEmpty: isEmpty }),
  reset: () => set({
    rawGraph: null,
    sigmaGraph: null,
    sigmaInstance: null,
    selectedNode: null,
    focusedNode: null,
    moveToSelectedNode: false,
    isFetching: false,
    graphIsEmpty: false
  })
}))

export default useGraphStore 