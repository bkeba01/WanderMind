'use client'

import { useState, useCallback } from 'react'
import ChatWindow from '@/components/ChatWindow'
import SpotCard from '@/components/SpotCard'
import MapEmbed from '@/components/MapEmbed'
import LikedSpotsTray from '@/components/LikedSpotsTray'
import { haversineKm, formatDistance, buildNavUrl, type LatLng } from '@/lib/geo'
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

      <div style={{ padding: '1.25rem 1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {routeInfo.spots.map((spot, i) => {
          const dist = userCoords ? formatDistance(haversineKm(userCoords, spot.location)) : null
          return (
            <div key={spot.place_id}>
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%',
                  background: '#facc15', color: '#000',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '0.75rem', fontWeight: 700, flexShrink: 0, marginTop: 2,
                }}>
                  {i + 1}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem', color: '#e2e8f0' }}>{spot.name}</div>
                  <div style={{ color: '#94a3b8', fontSize: '0.78rem', marginTop: 2 }}>{spot.address}</div>
                  <div style={{ display: 'flex', gap: '0.8rem', flexWrap: 'wrap', marginTop: 3 }}>
                    {spot.estimated_stay_minutes && (
                      <span style={{ color: '#64748b', fontSize: '0.75rem' }}>
                        ⏱ 滞在目安 {spot.estimated_stay_minutes}分
                      </span>
                    )}
                    {dist && (
                      <span style={{ color: '#a5b4fc', fontSize: '0.75rem' }}>
                        📏 現在地から{dist}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              {i < routeInfo.travel_times.length && (
                <div style={{ marginLeft: 14, marginTop: '0.4rem', marginBottom: '0.1rem', color: '#38bdf8', fontSize: '0.76rem', paddingLeft: '0.5rem', borderLeft: '2px solid rgba(56,189,248,0.25)' }}>
                  ↓ 次まで約 {routeInfo.travel_times[i]}分
                </div>
              )}
            </div>
          )
        })}
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
  const [spotMessage, setSpotMessage] = useState<string>('')
  const [transportation, setTransportation] = useState<'walking' | 'driving'>('walking')
  const [userCoords, setUserCoords] = useState<LatLng | null>(null)

  const [pendingMood, setPendingMood] = useState('')
  const [pendingTime, setPendingTime] = useState(0)

  const push = useCallback((...msgs: Message[]) => {
    setMessages(prev => [...prev, ...msgs])
  }, [])

  const applyResponse = useCallback((json: {
    thread_id?: string
    message: string
    phase: string
    liked_spots: Spot[]
    route_info?: RouteInfo | null
    current_suggestion?: Spot | null
  }) => {
    setLikedSpots(json.liked_spots ?? [])
    setRouteInfo(json.route_info ?? null)
    setChatPhase(json.phase === 'done' ? 'done' : 'collecting')
    push(aiMsg(json.message))
    if (json.current_suggestion) {
      setCurrentSpot(json.current_suggestion)
      setSpotMessage(json.message)
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
  const handleSend = useCallback(async (text: string) => {
    if (setupStep === 'mood') { handleMoodSelect(text); return }
    if (!threadId || isLoading) return

    push(userMsg(text))
    setIsLoading(true)

    try {
      const res = await fetch(`${API_URL}/api/v1/chat/${threadId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
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

  // 経由候補リストからスポットを選んで詳細表示を切り替える
  const handleSelectLikedSpot = useCallback((spot: Spot) => {
    setCurrentSpot(spot)
    setSpotMessage('')
  }, [])

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
          onMoodSelect={handleMoodSelect}
          onTimeSelect={handleTimeSelect}
          onTransportSelect={handleTransportSelect}
          onSend={handleSend}
        />
      </div>

      {/* 右カラム: スポット詳細 / 確定ルート */}
      <div className="wander-detail-col">
        <div style={{ width: '100%', maxWidth: 520 }}>
          {chatPhase === 'done' && routeInfo ? (
            <RouteSummaryPanel routeInfo={routeInfo} userCoords={userCoords} transportation={transportation} />
          ) : currentSpot ? (
            <>
              <SpotCard spot={currentSpot} masterMessage={spotMessage} transportation={transportation} userCoords={userCoords} />
              <LikedSpotsTray
                spots={likedSpots}
                currentPlaceId={currentSpot.place_id}
                userCoords={userCoords}
                onSelect={handleSelectLikedSpot}
              />
            </>
          ) : (
            <DetailPlaceholder />
          )}
        </div>
      </div>

    </main>
  )
}
