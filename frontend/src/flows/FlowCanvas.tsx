import {
  Background, Controls, MiniMap, ReactFlow, useReactFlow,
  type Connection, type FinalConnectionState, type IsValidConnection, type OnEdgesChange, type OnNodesChange, type XYPosition,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useState, type DragEvent, type ReactNode } from 'react'
import type { CanvasEdge, CanvasNode } from './graph'
import { FlowNodeCard } from './nodes'
import type { NodeType } from './types'

export const NODE_DRAG_TYPE = 'application/x-insight-node'
const NODE_TYPES = { sampling: FlowNodeCard, prompt: FlowNodeCard, output: FlowNodeCard }
const DELETE_KEYS = ['Delete', 'Backspace']
const NODE_KINDS: NodeType[] = ['sampling', 'prompt', 'output']

interface Props {
  nodes: CanvasNode[]
  edges: CanvasEdge[]
  editable: boolean
  label: string
  onNodesChange?: OnNodesChange<CanvasNode>
  onEdgesChange?: OnEdgesChange<CanvasEdge>
  /** Conexión propuesta, válida o no: el editor aplica las reglas y avisa del motivo si la rechaza. */
  onConnectAttempt?: (source: string, target: string) => void
  isValidConnection?: (source: string, target: string) => boolean
  onDropNode?: (type: NodeType, position: XYPosition) => void
  children?: ReactNode
}

/** Nodo bajo el puntero al soltar una conexión, aunque no tenga conector de entrada (p. ej. un Sampling). */
function nodeAt(event: MouseEvent | TouchEvent): string | null {
  const point = 'changedTouches' in event ? event.changedTouches[0] : event
  const element = point && document.elementFromPoint?.(point.clientX, point.clientY)
  return element?.closest<HTMLElement>('.react-flow__node')?.dataset.id ?? null
}

export function FlowCanvas({
  nodes, edges, editable, label, onNodesChange, onEdgesChange, onConnectAttempt, isValidConnection, onDropNode, children,
}: Props) {
  const { screenToFlowPosition } = useReactFlow()
  // Encuadrar solo al abrir un flujo con nodos: en un lienzo vacío, `fitView` se dispararía con el primer nodo
  // que se suelta y cambiaría el zoom a mitad del diseño.
  const [fitOnOpen] = useState(nodes.length > 0)

  const validate: IsValidConnection<CanvasEdge> = (c) => !!isValidConnection?.(c.source, c.target)

  function onConnectEnd(event: MouseEvent | TouchEvent, state: FinalConnectionState) {
    if (state.isValid || !state.fromNode || !state.fromHandle) return
    const other = state.toNode?.id ?? nodeAt(event)
    if (!other) return
    const fromSource = state.fromHandle.type === 'source'
    onConnectAttempt?.(fromSource ? state.fromNode.id : other, fromSource ? other : state.fromNode.id)
  }

  function onDrop(event: DragEvent) {
    const type = event.dataTransfer.getData(NODE_DRAG_TYPE) as NodeType
    if (!editable || !NODE_KINDS.includes(type)) return
    event.preventDefault()
    onDropNode?.(type, screenToFlowPosition({ x: event.clientX, y: event.clientY }))
  }

  return (
    <div className="insight-flow h-full w-full" aria-label={label} role="region"
      onDragOver={(event) => {
        if (!editable) return
        event.preventDefault()
        event.dataTransfer.dropEffect = 'move'
      }}
      onDrop={onDrop}>
      <ReactFlow<CanvasNode, CanvasEdge>
        nodes={nodes} edges={edges} nodeTypes={NODE_TYPES}
        onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        onConnect={(c: Connection) => onConnectAttempt?.(c.source, c.target)}
        onConnectEnd={onConnectEnd}
        isValidConnection={validate}
        nodesDraggable={editable} nodesConnectable={editable} elementsSelectable
        deleteKeyCode={editable ? DELETE_KEYS : null}
        snapToGrid snapGrid={[15, 15]} fitView={fitOnOpen} fitViewOptions={{ maxZoom: 1.1 }} minZoom={0.2}
      >
        <Background gap={15} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable ariaLabel="Minimapa del flujo" />
        {children}
      </ReactFlow>
    </div>
  )
}
