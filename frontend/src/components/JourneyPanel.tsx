'use client'

import type { Spot } from '@/types/chat'
import MapEmbed from '@/components/MapEmbed'
import RouteTimeline from '@/components/RouteTimeline'
import { buildNavUrl, type LatLng } from '@/lib/geo'

type JourneyPanelProps = {
  userCoords: LatLng | null
  likedSpots: Spot[]
  /** マスターが提案中のスポット（まだ経由確定ではない） */
  suggestion: Spot | null
  transportation: 'walking' | 'driving'
  activeId?: string | null
  onSelect?: (spot: Spot) => void
}

/** 会話中の右パネル: 現在地→経由スポット→提案中スポットのルート全体を地図＋タイムラインで表示 */
export default function JourneyPanel({
  userCoords,
  likedSpots,
  suggestion,
  transportation,
  activeId,
  onSelect,
}: JourneyPanelProps) {
  const isSuggestionNew =
    suggestion != null && !likedSpots.some(s => s.place_id === suggestion.place_id)
  const chain = isSuggestionNew && suggestion ? [...likedSpots, suggestion] : likedSpots

  if (chain.length === 0) return null

  return (
    <div style={{
      borderRadius: 20,
      overflow: 'hidden',
      background: 'rgba(15,20,35,0.95)',
      border: '1px solid rgba(255,255,255,0.08)',
      boxShadow: '0 12px 48px rgba(0,0,0,0.6)',
      animation: 'fadeIn 0.4s ease forwards',
    }}>

      {/* ── ヘッダー ── */}
      <div style={{
        padding: '1rem 1.25rem',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem',
      }}>
        <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#e2e8f0' }}>
          🧭 今日のルート
        </span>
        <span style={{ display: 'flex', gap: '0.4rem' }}>
          <span style={{
            fontSize: '0.7rem', fontWeight: 700, color: '#facc15',
            background: 'rgba(250,204,21,0.1)', border: '1px solid rgba(250,204,21,0.3)',
            borderRadius: 12, padding: '3px 10px',
          }}>
            経由 {likedSpots.length}ヶ所
          </span>
          {isSuggestionNew && (
            <span style={{
              fontSize: '0.7rem', fontWeight: 700, color: '#c084fc',
              background: 'rgba(192,132,252,0.1)', border: '1px solid rgba(192,132,252,0.3)',
              borderRadius: 12, padding: '3px 10px',
            }}>
              ＋提案中
            </span>
          )}
        </span>
      </div>

      {/* ── ルート地図（現在地 → 経由地 → 提案中） ── */}
      <MapEmbed
        origin={userCoords}
        spots={chain.map(s => s.location)}
        transportation={transportation}
        height={210}
      />

      {/* ── タイムライン ── */}
      <div style={{ padding: '1rem 1.25rem', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        <RouteTimeline
          stops={chain}
          userCoords={userCoords}
          transportation={transportation}
          activeId={activeId}
          suggestionId={isSuggestionNew && suggestion ? suggestion.place_id : null}
          onSelect={onSelect}
        />
      </div>

      {/* ── Google Mapsで経由ルートを開く ── */}
      <div style={{ padding: '0 1.25rem 1.1rem' }}>
        <a
          href={buildNavUrl(userCoords, chain.map(s => s.location), transportation)}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'block', textAlign: 'center',
            padding: '0.6rem', borderRadius: 12,
            background: 'rgba(56,189,248,0.08)',
            border: '1px solid rgba(56,189,248,0.3)',
            color: '#38bdf8', fontWeight: 700, fontSize: '0.82rem',
            textDecoration: 'none',
          }}
        >
          🗺️ Google Mapsで経由ルートを開く ↗
        </a>
      </div>
    </div>
  )
}
