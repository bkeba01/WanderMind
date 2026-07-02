'use client'

import type { Spot } from '@/types/chat'
import { haversineKm, formatDistance, type LatLng } from '@/lib/geo'

type RouteTimelineProps = {
  stops: Spot[]
  userCoords: LatLng | null
  /** legMinutes[i] = 前の地点 → stops[i] の移動時間（分）。無い区間は直線距離を表示 */
  legMinutes?: number[]
  transportation: 'walking' | 'driving'
  activeId?: string | null
  /** まだ確定していない「提案中」スポットのplace_id（紫でハイライト） */
  suggestionId?: string | null
  onSelect?: (spot: Spot) => void
}

const NODE_COL = 30

function LegChip({ label }: { label: string }) {
  return (
    <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
      <div style={{ width: NODE_COL, display: 'flex', justifyContent: 'center', flexShrink: 0 }}>
        <div style={{ width: 2, height: 26, background: 'linear-gradient(to bottom, rgba(56,189,248,0.5), rgba(56,189,248,0.15))' }} />
      </div>
      <span style={{ fontSize: '0.73rem', color: '#38bdf8', fontWeight: 600 }}>{label}</span>
    </div>
  )
}

/** 現在地 → スポット1 → スポット2... を縦のタイムラインで表示する */
export default function RouteTimeline({
  stops,
  userCoords,
  legMinutes,
  transportation,
  activeId = null,
  suggestionId = null,
  onSelect,
}: RouteTimelineProps) {
  const travelIcon = transportation === 'driving' ? '🚗' : '🚶'

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>

      {/* 現在地ノード */}
      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
        <div style={{ width: NODE_COL, display: 'flex', justifyContent: 'center', flexShrink: 0 }}>
          <div style={{
            width: 12, height: 12, borderRadius: '50%',
            background: '#38bdf8',
            boxShadow: '0 0 10px rgba(56,189,248,0.8), 0 0 20px rgba(56,189,248,0.35)',
          }} />
        </div>
        <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#38bdf8', letterSpacing: '0.04em' }}>
          現在地
        </span>
      </div>

      {stops.map((spot, i) => {
        const isSuggestion = spot.place_id === suggestionId
        const isActive = spot.place_id === activeId
        const prev: LatLng | null = i === 0 ? userCoords : stops[i - 1].location

        // 区間ラベル: 実測の移動時間があれば優先、なければ直線距離
        const minutes = legMinutes?.[i]
        const legLabel = minutes != null
          ? `${travelIcon} 約${minutes}分`
          : prev
            ? `${travelIcon} 約${formatDistance(haversineKm(prev, spot.location))}`
            : `${travelIcon} 移動`

        const row = (
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start', width: '100%' }}>
            {/* ノード（番号 or 提案中マーク） */}
            <div style={{ width: NODE_COL, display: 'flex', justifyContent: 'center', flexShrink: 0 }}>
              <div style={{
                width: 26, height: 26, borderRadius: '50%',
                background: isSuggestion ? 'linear-gradient(135deg, #c084fc, #818cf8)' : '#facc15',
                color: isSuggestion ? '#fff' : '#000',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.72rem', fontWeight: 700,
                animation: isSuggestion ? 'suggestPulse 1.8s ease infinite' : undefined,
              }}>
                {isSuggestion ? '？' : i + 1}
              </div>
            </div>
            {/* スポット情報 */}
            <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                <span style={{
                  fontWeight: 700, fontSize: '0.9rem',
                  color: isSuggestion ? '#c084fc' : isActive ? '#facc15' : '#e2e8f0',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {spot.name}
                </span>
                {isSuggestion && (
                  <span style={{
                    fontSize: '0.62rem', fontWeight: 700, flexShrink: 0,
                    color: '#c084fc', border: '1px solid rgba(192,132,252,0.45)',
                    borderRadius: 8, padding: '1px 7px',
                  }}>
                    提案中
                  </span>
                )}
              </div>
              <div style={{
                color: '#64748b', fontSize: '0.73rem', marginTop: 2,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {spot.address}
                {spot.estimated_stay_minutes ? ` ・ 滞在目安${spot.estimated_stay_minutes}分` : ''}
              </div>
            </div>
          </div>
        )

        return (
          <div key={spot.place_id}>
            <LegChip label={legLabel} />
            {onSelect ? (
              <button
                onClick={() => onSelect(spot)}
                style={{
                  display: 'block', width: '100%',
                  padding: '0.45rem 0.4rem', margin: '0 -0.4rem',
                  borderRadius: 12,
                  border: `1px solid ${isActive ? 'rgba(250,204,21,0.35)' : 'transparent'}`,
                  background: isActive ? 'rgba(250,204,21,0.06)' : 'transparent',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                {row}
              </button>
            ) : (
              <div style={{ padding: '0.45rem 0' }}>{row}</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
