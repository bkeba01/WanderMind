'use client'

import { useState, useCallback, useEffect } from 'react'
import ChatWindow from '@/components/ChatWindow'
import SpotCard from '@/components/SpotCard'
import MapEmbed from '@/components/MapEmbed'
import JourneyPanel from '@/components/JourneyPanel'
import RouteTimeline from '@/components/RouteTimeline'
import { buildNavUrl, type LatLng } from '@/lib/geo'
import type { Message, Spot, RouteInfo, SetupStep } from '@/types/chat'

const INITIAL_MESSAGE: Message = {
  id: 'init-0',
  role: 'ai',
  content: 'いらっしゃい。\n今日はどんな気分ですかい？',
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}
function userMsg(content: string): Message { return { id: makeId(), role: 'user', content } }
function aiMsg(content: string): Message   { return { id: makeId(), role: 'ai',   content } }

function getLocation(): Promise<GeolocationCoordinates> {
  return new Promise((resolve, reject) =>
    navigator.geolocation.getCurrentPosition(p => resolve(p.coords), reject)
  )
}

// ── 確定ルートパネル（右カラム・done フェーズ） ────────────────

function RouteSummaryPanel({ routeInfo, userCoords, transportation }: {
  routeInfo: RouteInfo
  userCoords: LatLng | null
  transportation: 'walking' | 'driving'
}) {
  const totalStay = routeInfo.spots.reduce((sum, s) => sum + (s.estimated_stay_minutes ?? 0), 0)
  const spotLocations = routeInfo.spots.map(s => s.location)

  return (
    <div style={{
      borderRadius: 20,
      overflow: 'hidden',
      background: 'rgba(15,20,35,0.95)',
      border: '1px solid rgba(250,204,21,0.18)',
      boxShadow: '0 12px 48px rgba(0,0,0,0.6)',
      animation: 'fadeIn 0.4s ease forwards',
    }}>
      <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid rgba(250,204,21,0.12)', background: 'rgba(250,204,21,0.04)' }}>
        <div style={{ color: '#facc15', fontWeight: 700, fontSize: '0.9rem', marginBottom: 4 }}>
          🗺️ 確定ルート（{routeInfo.spots.length}スポット）
        </div>
        <div style={{ color: '#94a3b8', fontSize: '0.78rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <span>🚶 移動合計 {routeInfo.total_travel_minutes}分</span>
          {totalStay > 0 && <span>⏱ 滞在合計 約{totalStay}分</span>}
          {totalStay > 0 && <span style={{ color: '#facc15' }}>合計 約{routeInfo.total_travel_minutes + totalStay}分</span>}
        </div>
      </div>

      {/* 全行程マップ（現在地 → 各スポット） */}
      <div style={{ borderBottom: '1px solid rgba(250,204,21,0.12)' }}>
        <MapEmbed origin={userCoords} spots={spotLocations} transportation={transportation} height={220} />
      </div>

      <div style={{ padding: '1.25rem 1.5rem' }}>
        <RouteTimeline
          stops={routeInfo.spots}
          userCoords={userCoords}
          legMinutes={routeInfo.travel_times}
          transportation={transportation}
        />
      </div>

      {/* Google Mapsナビ */}
      {routeInfo.spots.length > 0 && (
        <div style={{ padding: '0 1.5rem 1.25rem' }}>
          <a
            href={buildNavUrl(userCoords, spotLocations, transportation)}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'block', textAlign: 'center',
              padding: '0.7rem', borderRadius: 12,
              background: 'rgba(250,204,21,0.12)',
              border: '1px solid rgba(250,204,21,0.35)',
              color: '#facc15', fontWeight: 700, fontSize: '0.88rem',
              textDecoration: 'none',
            }}
          >
            🧭 Google Mapsでナビを開く ↗
          </a>
        </div>
      )}
    </div>
  )
}

// ── 右カラム プレースホルダー ────────────────────────────────────

function DetailPlaceholder() {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      color: '#475569', textAlign: 'center', padding: '2rem',
    }}>
      <div style={{ fontSize: '5rem', marginBottom: '1.25rem', opacity: 0.3 }}>☕</div>
      <p style={{ fontSize: '0.9rem', lineHeight: 1.8, color: '#475569' }}>
        マスターがあなたにぴったりの<br />場所を探しています...
      </p>
    </div>
  )
}

// ── スポット探索中のスケルトン ──────────────────────────────────

function SpotSkeleton() {
  const bar = (w: string, h = 12) => (
    <div style={{
      width: w, height: h, borderRadius: 6,
      background: 'rgba(255,255,255,0.06)',
      animation: 'skeletonPulse 1.4s ease-in-out infinite',
    }} />
  )
  return (
    <div style={{
      borderRadius: 20, overflow: 'hidden',
      background: 'rgba(15,20,35,0.95)',
      border: '1px solid rgba(255,255,255,0.08)',
    }}>
      <div style={{
        height: 200,
        background: 'rgba(255,255,255,0.04)',
        animation: 'skeletonPulse 1.4s ease-in-out infinite',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '0.85rem', color: '#64748b',
      }}>
        ☕ マスターが良いところを思い出しています…
      </div>
      <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
        {bar('60%', 18)}
        {bar('90%')}
        {bar('75%')}
      </div>
    </div>
  )
}

// ── メインページ ─────────────────────────────────────────────────

export default function Home() {
  const [messages, setMessages]       = useState<Message[]>([INITIAL_MESSAGE])
  const [setupStep, setSetupStep]     = useState<SetupStep>('mood')
  const [threadId, setThreadId]       = useState<string | null>(null)
  const [likedSpots, setLikedSpots]   = useState<Spot[]>([])
  const [routeInfo, setRouteInfo]     = useState<RouteInfo | null>(null)
  const [chatPhase, setChatPhase]     = useState<'collecting' | 'done'>('collecting')
  const [isLoading, setIsLoading]     = useState(false)
  const [currentSpot, setCurrentSpot] = useState<Spot | null>(null)
  const [selectedSpot, setSelectedSpot] = useState<Spot | null>(null)
  const [spotMessage, setSpotMessage] = useState<string>('')
  const [transportation, setTransportation] = useState<'walking' | 'driving'>('walking')
  const [userCoords, setUserCoords] = useState<LatLng | null>(null)
  const [quickReplies, setQuickReplies] = useState<string[]>([])

  const [pendingMood, setPendingMood] = useState('')
  const [pendingTime, setPendingTime] = useState(0)

  const push = useCallback((...msgs: Message[]) => {
    setMessages(prev => [...prev, ...msgs])
  }, [])

  // ── セッション復元（リロード後も会話を継続） ────────────────
  useEffect(() => {
    const tid = localStorage.getItem('wander_thread_id')
    if (!tid) return

    ;(async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/chat/${tid}`)
        if (!res.ok) throw new Error('セッションが見つかりません')
        const json = await res.json()

        setThreadId(tid)
        setMessages(
          (json.messages as { role: 'ai' | 'user'; content: string }[])
            .map(m => ({ id: makeId(), role: m.role, content: m.content }))
        )
        setLikedSpots(json.liked_spots ?? [])
        setRouteInfo(json.route_info ?? null)
        setChatPhase(json.phase === 'done' ? 'done' : 'collecting')
        setQuickReplies(json.quick_replies ?? [])
        setTransportation(json.transportation === 'driving' ? 'driving' : 'walking')
        if (json.current_suggestion) {
          setCurrentSpot(json.current_suggestion)
          const lastAi = [...json.messages].reverse().find(
            (m: { role: string }) => m.role === 'ai'
          )
          setSpotMessage(lastAi?.content ?? '')
        }
        const coords = localStorage.getItem('wander_coords')
        if (coords) setUserCoords(JSON.parse(coords))
        setSetupStep('chatting')
      } catch {
        localStorage.removeItem('wander_thread_id')
        localStorage.removeItem('wander_coords')
      }
    })()
  }, [])

  // ── 新しく相談し直す ─────────────────────────────────────────
  const handleReset = useCallback(() => {
    localStorage.removeItem('wander_thread_id')
    localStorage.removeItem('wander_coords')
    setMessages([INITIAL_MESSAGE])
    setSetupStep('mood')
    setThreadId(null)
    setLikedSpots([])
    setRouteInfo(null)
    setChatPhase('collecting')
    setCurrentSpot(null)
    setSelectedSpot(null)
    setSpotMessage('')
    setQuickReplies([])
    setPendingMood('')
    setPendingTime(0)
  }, [])

  const applyResponse = useCallback((json: {
    thread_id?: string
    message: string
    phase: string
    liked_spots: Spot[]
    route_info?: RouteInfo | null
    current_suggestion?: Spot | null
    quick_replies?: string[]
  }) => {
    setLikedSpots(json.liked_spots ?? [])
    setRouteInfo(json.route_info ?? null)
    setChatPhase(json.phase === 'done' ? 'done' : 'collecting')
    setQuickReplies(json.quick_replies ?? [])
    push(aiMsg(json.message))
    if (json.current_suggestion) {
      setCurrentSpot(json.current_suggestion)
      setSpotMessage(json.message)
      setSelectedSpot(null) // 新しい提案が来たら手動選択を解除して提案を表示
    }
  }, [push])

  // STEP 1: 気分
  const handleMoodSelect = useCallback((mood: string) => {
    setPendingMood(mood)
    push(userMsg(mood), aiMsg('いいですね。\nちなみに、今日はどのくらい時間がありますか？'))
    setSetupStep('time')
  }, [push])

  // STEP 2: 時間
  const handleTimeSelect = useCallback((minutes: number) => {
    const label = minutes < 60 ? `${minutes}分` : minutes < 120 ? '1時間' : minutes < 240 ? '2時間' : '半日'
    setPendingTime(minutes)
    push(userMsg(`${label}くらい`), aiMsg('了解です。\nどうやって移動しますか？'))
    setSetupStep('transport')
  }, [push])

  // STEP 3: 交通手段 → セッション開始
  const handleTransportSelect = useCallback(async (transport: string) => {
    const mode = transport === 'driving' ? 'driving' : 'walking'
    setTransportation(mode)
    const transportLabel = mode === 'driving' ? '車で' : '徒歩で'
    push(userMsg(transportLabel))
    setIsLoading(true)
    setSetupStep('chatting')

    try {
      const coords = await getLocation()
      setUserCoords({ latitude: coords.latitude, longitude: coords.longitude })
      const res = await fetch(`${API_URL}/api/v1/chat/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: `${pendingMood}。空き時間は${pendingTime}分くらい。`,
          latitude: coords.latitude,
          longitude: coords.longitude,
          transportation: transport,
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      const json = await res.json()
      setThreadId(json.thread_id)
      // リロード復元用に保存
      localStorage.setItem('wander_thread_id', json.thread_id)
      localStorage.setItem('wander_coords', JSON.stringify({ latitude: coords.latitude, longitude: coords.longitude }))
      applyResponse(json)
    } catch (err) {
      console.error(err)
      push(aiMsg('すいません、うまく繋がらなかったみたいで...\nもう一度話しかけてもらえますか？'))
      setSetupStep('transport')
    } finally {
      setIsLoading(false)
    }
  }, [pendingMood, pendingTime, push, applyResponse])

  // 会話中のメッセージ送信
  // isQuickReply: ボタン由来なら true（バックエンドで固定分類）、自由入力なら false（LLMが意図解析）
  const handleSend = useCallback(async (text: string, isQuickReply = false) => {
    if (setupStep === 'mood') { handleMoodSelect(text); return }
    if (!threadId || isLoading) return

    push(userMsg(text))
    setIsLoading(true)

    try {
      const res = await fetch(`${API_URL}/api/v1/chat/${threadId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, is_quick_reply: isQuickReply }),
      })
      if (!res.ok) throw new Error(await res.text())
      applyResponse(await res.json())
    } catch (err) {
      console.error(err)
      push(aiMsg('ちょっとトラブルがあったようで... もう一度言ってもらえますか？'))
    } finally {
      setIsLoading(false)
    }
  }, [setupStep, threadId, isLoading, push, handleMoodSelect, applyResponse])

  // タイムラインのスポットをクリックして詳細表示を切り替える
  const handleSelectSpot = useCallback((spot: Spot) => {
    setSelectedSpot(spot)
  }, [])

  // 承認済みスポットの取り消し（❌）
  const handleRemoveSpot = useCallback(async (spot: Spot) => {
    if (!threadId || isLoading) return
    try {
      const res = await fetch(
        `${API_URL}/api/v1/chat/${threadId}/spots/${spot.place_id}`,
        { method: 'DELETE' },
      )
      if (!res.ok) throw new Error(await res.text())
      const json = await res.json()
      setLikedSpots(json.liked_spots ?? [])
      setSelectedSpot(prev => (prev?.place_id === spot.place_id ? null : prev))
      push(aiMsg(`了解、「${spot.name}」は無しにしておくよ。`))
    } catch (err) {
      console.error(err)
      push(aiMsg('すまんね、うまく外せなかったみたいだ...'))
    }
  }, [threadId, isLoading, push])

  // 表示するスポット: 手動選択があればそれを優先、なければ提案中のスポット
  const displayedSpot = selectedSpot ?? currentSpot

  // ── レンダリング ────────────────────────────────────────────────

  return (
    <main className="wander-layout">

      {/* 左カラム: チャット */}
      <div className="wander-chat-col">
        <ChatWindow
          messages={messages}
          setupStep={setupStep}
          likedSpots={likedSpots}
          routeInfo={routeInfo}
          chatPhase={chatPhase}
          isLoading={isLoading}
          dynamicReplies={quickReplies}
          onMoodSelect={handleMoodSelect}
          onTimeSelect={handleTimeSelect}
          onTransportSelect={handleTransportSelect}
          onSend={handleSend}
          onReset={handleReset}
        />
      </div>

      {/* 右カラム: スポット詳細 / 確定ルート */}
      <div className="wander-detail-col">
        <div style={{ width: '100%', maxWidth: 520 }}>
          {chatPhase === 'done' && routeInfo ? (
            <RouteSummaryPanel routeInfo={routeInfo} userCoords={userCoords} transportation={transportation} />
          ) : isLoading && setupStep === 'chatting' ? (
            <SpotSkeleton />
          ) : displayedSpot ? (
            <>
              <JourneyPanel
                userCoords={userCoords}
                likedSpots={likedSpots}
                suggestion={currentSpot}
                transportation={transportation}
                activeId={displayedSpot.place_id}
                onSelect={handleSelectSpot}
                onRemove={handleRemoveSpot}
              />
              <div style={{ marginTop: '1rem' }}>
                <SpotCard
                  spot={displayedSpot}
                  masterMessage={displayedSpot.place_id === currentSpot?.place_id ? spotMessage : undefined}
                  transportation={transportation}
                  userCoords={userCoords}
                />
              </div>
            </>
          ) : (
            <DetailPlaceholder />
          )}
        </div>
      </div>

    </main>
  )
}
