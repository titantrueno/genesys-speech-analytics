import { ArrowLeft, MessageSquareText, Phone, ScanSearch } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams, type Location } from 'react-router'
import { ApiError } from '../api/client'
import { useConversation } from '../api/conversations'
import { useAuth } from '../auth/useAuth'
import { LoadingScreen } from '../layout/LoadingScreen'
import { formatDuration } from '../lib/format'
import { AnalysisPanel } from './AnalysisPanel'
import { ChatTranscript } from './ChatTranscript'
import { CHANNEL_LABELS } from './labels'

const dateTime = new Intl.DateTimeFormat('es-ES', { dateStyle: 'long', timeStyle: 'short' })

const BACK_LABELS: Record<string, string> = {
  '/conversaciones': 'Volver al listado',
  '/explorador': 'Volver al explorador',
  '/busqueda': 'Volver a la búsqueda',
}

// Orígenes con parámetros en la ruta (FE004: la tabla de resultados de una ejecución de flujo).
const BACK_PATTERNS: Array<[RegExp, string]> = [[/^\/flujos\/[^/]+\/ejecuciones\/[^/]+$/, 'Volver a la ejecución']]

function backLabel(pathname: string): string | undefined {
  return BACK_LABELS[pathname] ?? BACK_PATTERNS.find(([pattern]) => pattern.test(pathname))?.[1]
}

function BackLink() {
  const location = useLocation()
  const from = (location.state as { from?: Pick<Location, 'pathname' | 'search'> } | null)?.from
  const label = from ? backLabel(from.pathname) : undefined
  const to = from && label ? `${from.pathname}${from.search}` : '/conversaciones'
  return (
    <Link to={to} className="inline-flex items-center gap-1 text-sm text-brand-700 hover:underline">
      <ArrowLeft className="size-4" aria-hidden />{label ?? BACK_LABELS['/conversaciones']}
    </Link>
  )
}

/** Turno de `?turn=N` (enlace desde la búsqueda); `null` si no es un índice válido de la conversación. */
function parseTurn(value: string | null, turnCount: number | undefined): number | null {
  if (value === null || turnCount === undefined || !/^\d+$/.test(value)) return null
  const turn = Number(value)
  return turn < turnCount ? turn : null
}

export function ConversationDetailPage() {
  const { conversationId = '' } = useParams()
  const { data: conversation, error, isLoading } = useConversation(conversationId)
  const { can } = useAuth()
  const [params] = useSearchParams()
  const turnElements = useRef(new Map<number, HTMLLIElement>())
  const chatRef = useRef<HTMLDivElement>(null)
  const urlTurn = parseTurn(params.get('turn'), conversation?.turns.length)
  const [chosenTurn, setChosenTurn] = useState<number | null>(null)
  const activeTurn = chosenTurn ?? urlTurn

  const registerTurn = useCallback((index: number, element: HTMLLIElement | null) => {
    if (element) turnElements.current.set(index, element)
    else turnElements.current.delete(index)
  }, [])

  const scrollToTurn = useCallback((index: number) => {
    const element = turnElements.current.get(index)
    const container = chatRef.current
    if (element && container) {
      container.scrollTo({ top: element.offsetTop - container.clientHeight / 2 + element.offsetHeight / 2, behavior: 'smooth' })
    }
  }, [])

  const selectTurn = useCallback((index: number) => {
    scrollToTurn(index)
    setChosenTurn(index)
  }, [scrollToTurn])

  useEffect(() => {
    if (urlTurn !== null) scrollToTurn(urlTurn)
  }, [urlTurn, scrollToTurn])

  if (isLoading) return <LoadingScreen />
  if (error || !conversation) {
    const notFound = error instanceof ApiError && error.status === 404
    return (
      <div className="space-y-3">
        <BackLink />
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {notFound ? 'Conversación no encontrada.' : 'No se ha podido cargar la conversación.'}
        </p>
      </div>
    )
  }

  const ChannelIcon = conversation.channel === 'voz' ? Phone : MessageSquareText
  return (
    <div className="space-y-4">
      <BackLink />
      <section aria-label="Resumen de la conversación" className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Conversación {conversation.id}</h1>
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500">
              <span className="inline-flex items-center gap-1.5 font-medium text-slate-700">
                <ChannelIcon className="size-4" aria-hidden />
                <span>{CHANNEL_LABELS[conversation.channel]}</span>
                {conversation.channel === 'voz' && <span className="font-normal text-slate-500">(transcripción)</span>}
              </span>
              <span>{dateTime.format(new Date(conversation.started_at))}</span>
              <span>{conversation.queue}</span>
              <span>{conversation.agent}</span>
              <span>{formatDuration(conversation.duration_s)}</span>
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {can('search:use') && (
              <Link to={`/busqueda?similar=${conversation.id}`}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50">
                <ScanSearch className="size-4" aria-hidden />Buscar conversaciones similares
              </Link>
            )}
            <span className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white">{conversation.main_topic_label}</span>
          </div>
        </div>
        <p className="mt-4 text-sm leading-relaxed text-slate-700"><span className="font-medium text-slate-900">Summary. </span>{conversation.analysis.summary}</p>
      </section>
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div ref={chatRef} data-testid="chat-scroll"
          className="relative max-h-[calc(100vh-17rem)] min-h-96 overflow-y-auto rounded-xl border border-slate-200 bg-[#efeae2]">
          <ChatTranscript conversation={conversation} activeTurn={activeTurn} registerTurn={registerTurn} />
        </div>
        <AnalysisPanel conversation={conversation} activeTurn={activeTurn} onSelectTurn={selectTurn} />
      </div>
    </div>
  )
}
