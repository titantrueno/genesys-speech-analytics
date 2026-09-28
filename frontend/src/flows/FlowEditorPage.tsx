import { ReactFlowProvider, addEdge, applyEdgeChanges, applyNodeChanges, useReactFlow, type EdgeChange, type NodeChange, type XYPosition } from '@xyflow/react'
import { AlertCircle, ArrowLeft, CheckCircle2, History, Play, Save, ShieldCheck, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useBlocker, useNavigate, useParams } from 'react-router'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { useDebouncedValue } from '../explorer/hooks'
import { LoadingScreen } from '../layout/LoadingScreen'
import { useFlow, useFlowCatalog, useSaveGraph, useStartRun, useValidation } from './api'
import { CatalogContext, useCatalog } from './catalog'
import { FlowCanvas, NODE_DRAG_TYPE } from './FlowCanvas'
import {
  freePosition, fromCanvas, newNode, remapEdges, remapNodes, sameJson, toCanvasEdges, toCanvasNodes, type CanvasEdge, type CanvasNode,
} from './graph'
import { NodePanel } from './panels/NodePanel'
import { useNodeNames } from './panels/nodeNames'
import { connectionRejection, NODE_LABELS } from './rules'
import type { Flow, Issue, NodeType } from './types'

const button = 'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50'
const secondary = `${button} border border-slate-300 bg-white text-slate-700 hover:bg-slate-50`
const PALETTE: Array<{ type: NodeType; description: string }> = [
  { type: 'sampling', description: 'Toma una muestra de conversaciones' },
  { type: 'prompt', description: 'Aplica un prompt a cada conversación' },
  { type: 'output', description: 'Produce una tabla, una métrica o un informe' },
]

function Palette({ onAdd }: { onAdd: (type: NodeType) => void }) {
  return (
    <aside aria-label="Paleta de nodos" className="w-44 shrink-0 space-y-2">
      <h2 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">Nodos</h2>
      <p className="text-xs text-slate-500">Arrástralos al lienzo o púlsalos para añadirlos.</p>
      {PALETTE.map(({ type, description }) => (
        <button key={type} type="button" draggable aria-label={`Añadir ${NODE_LABELS[type]}`}
          onDragStart={(event) => {
            event.dataTransfer.setData(NODE_DRAG_TYPE, type)
            event.dataTransfer.effectAllowed = 'move'
          }}
          onClick={() => onAdd(type)}
          className="block w-full cursor-grab rounded-lg border border-slate-200 bg-white p-2.5 text-left shadow-sm hover:border-brand-500 active:cursor-grabbing">
          <span className="block text-sm font-semibold text-slate-800">{NODE_LABELS[type]}</span>
          <span className="block text-xs text-slate-500">{description}</span>
        </button>
      ))}
    </aside>
  )
}

function ValidationPanel({ issues, loading, nodes, onSelect, onClose }: {
  issues: Issue[] | undefined; loading: boolean; nodes: CanvasNode[]; onSelect: (id: string) => void; onClose: () => void
}) {
  const names = useNodeNames(nodes)
  return (
    <section aria-label="Validación" className="rounded-xl border border-slate-200 bg-white p-3">
      <header className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">Validación</h2>
        <button type="button" onClick={onClose} aria-label="Cerrar validación" className="rounded p-1 text-slate-400 hover:bg-slate-100">
          <X className="size-4" aria-hidden />
        </button>
      </header>
      {!issues && loading && <p role="status" className="text-sm text-slate-500">Validando…</p>}
      {issues && issues.length === 0 && (
        <p className="inline-flex items-center gap-1.5 text-sm text-[var(--status-good-text)]">
          <CheckCircle2 className="size-4" aria-hidden />El flujo es válido.
        </p>
      )}
      {issues && issues.length > 0 && (
        <ul aria-label="Errores de validación" className={`space-y-1 ${loading ? 'opacity-60' : ''}`}>
          {issues.map((issue, i) => {
            // «Prompt 2»: tipo y número, sin el resumen, para distinguir nodos del mismo tipo.
            const name = issue.node_id ? names.get(issue.node_id)?.split(' · ')[0] : undefined
            return (
              <li key={`${issue.code}-${issue.node_id}-${i}`} className="flex items-start gap-1.5 text-sm text-red-800">
                <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
                {name && issue.node_id ? (
                  <button type="button" onClick={() => onSelect(issue.node_id!)} className="text-left hover:underline">
                    <span className="font-medium">{name}:</span> {issue.message}
                  </button>
                ) : <span>{issue.message}</span>}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function UnsavedChangesDialog({ onLeave, onStay }: { onLeave: () => void; onStay: () => void }) {
  return (
    <div role="alertdialog" aria-labelledby="unsaved-title" aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30">
      <div className="w-96 space-y-3 rounded-xl bg-white p-5 shadow-xl">
        <h2 id="unsaved-title" className="text-base font-semibold text-slate-900">Hay cambios sin guardar</h2>
        <p className="text-sm text-slate-600">Si sales ahora, perderás los cambios del flujo.</p>
        <div className="flex justify-end gap-2">
          <button type="button" className={secondary} onClick={onStay} autoFocus>Seguir editando</button>
          <button type="button" className={`${button} bg-red-600 text-white hover:bg-red-700`} onClick={onLeave}>Salir sin guardar</button>
        </div>
      </div>
    </div>
  )
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && Array.isArray(error.detail) && error.detail.length) {
    const first = error.detail[0] as { message?: string }
    return `${fallback} ${first.message ?? ''}`.trim()
  }
  return error instanceof ApiError && typeof error.detail === 'string' ? `${fallback} ${error.detail}` : fallback
}

function Editor({ flow }: { flow: Flow }) {
  const catalog = useCatalog()
  const { can } = useAuth()
  const editable = can('flows:edit')
  const navigate = useNavigate()
  const { screenToFlowPosition, fitView } = useReactFlow()
  const canvasRef = useRef<HTMLDivElement>(null)
  const [nodes, setNodes] = useState<CanvasNode[]>(() => toCanvasNodes(flow.graph))
  const [edges, setEdges] = useState<CanvasEdge[]>(() => toCanvasEdges(flow.graph))
  const [saved, setSaved] = useState(flow.graph)
  const [validating, setValidating] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const graph = useMemo(() => fromCanvas(nodes, edges), [nodes, edges])
  const dirty = !sameJson(graph, saved)
  const save = useSaveGraph(flow.id)
  const start = useStartRun(flow.id)
  const validation = useValidation(useDebouncedValue(graph, 400), validating)
  const issues = validating ? validation.data?.issues : undefined

  const issuesByNode = useMemo(() => {
    const map = new Map<string, Issue[]>()
    for (const issue of issues ?? []) {
      if (issue.node_id) map.set(issue.node_id, [...(map.get(issue.node_id) ?? []), issue])
    }
    return map
  }, [issues])
  const shownNodes = useMemo(
    () => nodes.map((n) => (issuesByNode.has(n.id) ? { ...n, data: { ...n.data, issues: issuesByNode.get(n.id) } } : n)),
    [nodes, issuesByNode],
  )

  // Tras guardar y lanzar una ejecución se navega antes de que React vuelva a pintar con el estado guardado:
  // esa salida es intencionada y no debe pedir confirmación.
  const leavingToRun = useRef(false)
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    dirty && !leavingToRun.current && currentLocation.pathname !== nextLocation.pathname)
  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  const onNodesChange = useCallback((changes: NodeChange<CanvasNode>[]) => setNodes((current) => applyNodeChanges(changes, current)), [])
  const onEdgesChange = useCallback((changes: EdgeChange<CanvasEdge>[]) => setEdges((current) => applyEdgeChanges(changes, current)), [])

  const types = useMemo(() => new Map(nodes.map((n) => [n.id, n.type])), [nodes])
  const connect = (source: string, target: string) => {
    const rejection = connectionRejection(types, graph.edges, source, target)
    if (rejection) {
      setNotice(`No se puede conectar: ${rejection.message}`)
      return
    }
    setNotice(null)
    setEdges((current) => addEdge({ id: `${source}>${target}`, source, target }, current))
  }

  function addNode(type: NodeType, position?: XYPosition) {
    let at = position
    if (!at) {
      const rect = canvasRef.current?.getBoundingClientRect()
      // Desde el cuarto izquierdo del lienzo visible, en el primer hueco libre.
      const origin = screenToFlowPosition({ x: (rect?.left ?? 0) + (rect?.width ?? 0) / 4, y: (rect?.top ?? 0) + (rect?.height ?? 0) / 3 })
      at = freePosition(origin, nodes)
    }
    const node = { ...newNode(type, at, catalog.default_model), selected: true }
    setNodes((current) => [...current.map((n) => (n.selected ? { ...n, selected: false } : n)), node])
  }

  const selected = nodes.filter((n) => n.selected)
  const current = selected.length === 1 ? selected[0] : undefined

  function updateConfig(id: string, config: CanvasNode['data']['config']) {
    setNodes((all) => all.map((n) => (n.id === id ? { ...n, data: { ...n.data, config } } : n)))
  }

  function deleteNode(id: string) {
    setNodes((all) => all.filter((n) => n.id !== id))
    setEdges((all) => all.filter((e) => e.source !== id && e.target !== id))
  }

  function selectNode(id: string) {
    setNodes((current) => current.map((n) => ({ ...n, selected: n.id === id })))
    fitView({ nodes: [{ id }], duration: 300, maxZoom: 1.1 })
  }

  async function persist(): Promise<boolean> {
    try {
      const result = await save.mutateAsync(graph)
      setNodes((current) => remapNodes(current, result.id_map))
      setEdges((current) => remapEdges(current, result.id_map))
      setSaved(result.graph)
      return true
    } catch {
      return false
    }
  }

  async function run() {
    if (dirty && !(await persist())) return
    start.mutate(undefined, {
      onSuccess: (created) => {
        leavingToRun.current = true
        navigate(`/flujos/${flow.id}/ejecuciones/${created.id}`)
      },
      onError: (error) => {
        if (error instanceof ApiError && error.status === 422) setValidating(true)
      },
    })
  }

  const runError = start.error instanceof ApiError
    ? start.error.status === 422 ? 'El flujo tiene errores: corrígelos antes de ejecutarlo.'
      : start.error.status === 409 ? 'Ya hay una ejecución en curso de este flujo.' : 'No se ha podido ejecutar el flujo.'
    : start.error ? 'No se ha podido ejecutar el flujo.' : null

  return (
    <div className="flex h-[calc(100vh-3rem)] min-h-[560px] flex-col gap-3">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <Link to="/flujos" className="inline-flex items-center gap-1 text-sm text-brand-700 hover:underline">
            <ArrowLeft className="size-4" aria-hidden />Volver a flujos
          </Link>
          <h1 className="truncate text-2xl font-semibold text-slate-900">{flow.name}</h1>
          <p role="status" className="text-xs text-slate-500">
            {!editable ? 'Solo lectura' : save.isPending ? 'Guardando…' : dirty ? 'Cambios sin guardar' : 'Guardado'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link to={`/flujos/${flow.id}/ejecuciones`} className={secondary}><History className="size-4" aria-hidden />Historial</Link>
          <button type="button" className={secondary} onClick={() => setValidating(true)}>
            <ShieldCheck className="size-4" aria-hidden />Validar
          </button>
          {editable && (
            <>
              <button type="button" className={secondary} disabled={!dirty || save.isPending} onClick={() => void persist()}>
                <Save className="size-4" aria-hidden />Guardar
              </button>
              <button type="button" className={`${button} bg-brand-600 text-white hover:bg-brand-700`}
                disabled={save.isPending || start.isPending} onClick={() => void run()}>
                <Play className="size-4" aria-hidden />Ejecutar
              </button>
            </>
          )}
        </div>
      </header>
      {save.isError && <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{errorMessage(save.error, 'No se ha podido guardar el flujo.')}</p>}
      {runError && <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{runError}</p>}
      {notice && (
        <p role="alert" className="flex items-center justify-between rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {notice}
          <button type="button" aria-label="Cerrar aviso" onClick={() => setNotice(null)} className="rounded p-0.5 hover:bg-amber-100">
            <X className="size-4" aria-hidden />
          </button>
        </p>
      )}
      <div className="flex min-h-0 flex-1 gap-3">
        {editable && <Palette onAdd={(type) => addNode(type)} />}
        <div ref={canvasRef} className="min-w-0 flex-1 overflow-hidden rounded-xl border border-slate-200 bg-white">
          <FlowCanvas nodes={shownNodes} edges={edges} editable={editable} label="Lienzo del flujo"
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onConnectAttempt={connect}
            isValidConnection={(source, target) => !connectionRejection(types, graph.edges, source, target)}
            onDropNode={addNode} />
        </div>
        {(validating || current) && (
          <div className="w-96 shrink-0 space-y-3 overflow-y-auto pb-2">
            {validating && (
              <ValidationPanel issues={issues} loading={validation.isFetching} nodes={nodes} onSelect={selectNode}
                onClose={() => setValidating(false)} />
            )}
            {current && (
              <NodePanel key={current.id} node={current} nodes={nodes} edges={edges} editable={editable}
                onChange={(config) => updateConfig(current.id, config)}
                onDelete={() => deleteNode(current.id)}
                onConnect={connect}
                onDisconnect={(edgeId) => setEdges((all) => all.filter((e) => e.id !== edgeId))}
                onClose={() => setNodes((all) => all.map((n) => (n.selected ? { ...n, selected: false } : n)))} />
            )}
          </div>
        )}
      </div>
      {blocker.state === 'blocked' && <UnsavedChangesDialog onLeave={() => blocker.proceed()} onStay={() => blocker.reset()} />}
    </div>
  )
}

export function FlowEditorPage() {
  const { flowId = '' } = useParams()
  const flow = useFlow(flowId)
  const catalog = useFlowCatalog()
  if (flow.isError || catalog.isError) {
    const notFound = flow.error instanceof ApiError && flow.error.status === 404
    return (
      <div className="space-y-3">
        <Link to="/flujos" className="inline-flex items-center gap-1 text-sm text-brand-700 hover:underline">
          <ArrowLeft className="size-4" aria-hidden />Volver a flujos
        </Link>
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {notFound ? 'Flujo no encontrado.' : 'No se ha podido cargar el flujo.'}
        </p>
      </div>
    )
  }
  if (!flow.data || !catalog.data) return <LoadingScreen />
  return (
    <CatalogContext.Provider value={catalog.data}>
      <ReactFlowProvider>
        <Editor key={flow.data.id} flow={flow.data} />
      </ReactFlowProvider>
    </CatalogContext.Provider>
  )
}
