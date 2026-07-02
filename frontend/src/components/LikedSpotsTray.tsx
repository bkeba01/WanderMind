'use client'

import type { Spot } from '@/types/chat'
import { haversineKm, formatDistance, type LatLng } from '@/lib/geo'

type LikedSpotsTrayProps = {
  spots: Spot[]
  currentPlaceId?: string | null
  userCoords: LatLng | null
  onSelect: (spot: Spot) => void
}

/** いいねした経由候補スポットの一覧。クリックで詳細カードを切り替える */
export default function LikedSpotsTray({ spots, currentPlaceId, userCoords, onSelect }: LikedSpotsTrayProps) {
  if (spots.length === 0) return null

  return (
    <div style={{
      marginTop: '1rem',
      borderRadius: 16,
      background: 'rgba(15,20,35,0.95)',
      border: '1px solid rgba(250,204,21,0.15)',
      padding: '1rem 1.25rem',
      animation: 'fadeIn 0.4s ease forwards',
    }}>
      <div style={{
        fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.08em',
        color: '#facc15', marginBottom: '0.6rem', textTransform: 'uppercase',
      }}>
        🧳 経由候補（{spots.length}件）
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        {spots.map((spot, i) => {
          const active = spot.place_id === currentPlaceId
          const dist = userCoords ? formatDistance(haversineKm(userCoords, spot.location)) : null
          return (
            <button
              key={spot.place_id}
              onClick={() => onSelect(spot)}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.6rem',
                padding: '0.5rem 0.65rem',
                borderRadius: 10,
                border: `1px solid ${active ? 'rgba(250,204,21,0.4)' : 'rgba(255,255,255,0.06)'}`,
                background: active ? 'rgba(250,204,21,0.08)' : 'rgba(255,255,255,0.02)',
                cursor: 'pointer',
                transition: 'all 0.15s',
                width: '100%',
              }}
            >
              <span style={{
                width: 22, height: 22, borderRadius: '50%',
                background: active ? '#facc15' : 'rgba(255,255,255,0.1)',
                color: active ? '#000' : '#94a3b8',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.7rem', fontWeight: 700, flexShrink: 0,
              }}>
                {i + 1}
              </span>
              <span style={{
                flex: 1, textAlign: 'left',
                fontSize: '0.85rem', fontWeight: 600,
                color: active ? '#facc15' : '#e2e8f0',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {spot.name}
              </span>
              {dist && (
                <span style={{ fontSize: '0.75rem', color: '#38bdf8', flexShrink: 0 }}>
                  📍 {dist}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
