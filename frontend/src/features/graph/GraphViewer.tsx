import { useRef } from 'react'
import Graph from './components/Graph'
import useGraphStore from './store'

export default function GraphViewer() {
  const containerRef = useRef<HTMLDivElement>(null)
  const isFetching = useGraphStore(state => state.isFetching)

  return (
    <div className="w-full h-full bg-[#343541] text-gray-100" ref={containerRef}>
      <div className="w-full h-full">
        <Graph />
      </div>
      {isFetching && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#343541] bg-opacity-80">
          <div className="text-lg text-gray-200">Loading graph...</div>
        </div>
      )}
    </div>
  )
} 