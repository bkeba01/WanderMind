'use client'

import type { Spot } from '@/types/chat'
import MapEmbed from '@/components/MapEmbed'
import { haversineKm, formatDistance, buildPlaceUrl, type LatLng } from '@/lib/geo'

const PRICE_LABELS: Record<number, string> = {
  0: '無料',
  1: '¥',
  2: '¥¥',
  3: '¥¥¥',
  4: '¥¥¥¥',
}

function guessTypeEmoji(name: string): string {
  const n = name
  if (n.includes('カフェ') || n.includes('cafe') || n.includes('喫茶') || n.includes('コーヒー')) return '☕'
  if (n.includes('公園') || n.includes('park') || n.includes('庭園') || n.includes('緑')) return '🌿'
  if (n.includes('美術館') || n.includes('博物館') || n.includes('ミュージアム')) return '🎨'
  if (n.includes('レストラン') || n.includes('食堂') || n.includes('料理') || n.includes('ダイニング')) return '🍽️'
  if (n.includes('バー') || n.includes('居酒屋') || n.includes('酒')) return '🍺'
  if (n.includes('ショッピング') || n.includes('モール') || n.includes('百貨店')) return '🛍️'
  if (n.includes('映画') || n.includes('シネマ')) return '🎬'
  if (n.includes('温泉') || n.includes('スパ') || n.includes('銭湯')) return '♨️'
  return '📍'
}

type SpotCardProps = {
  spot: Spot
  masterMessage?: string
  transportation?: 'walking' | 'driving'
  userCoords?: LatLng | null
}

export default function SpotCard({ spot, masterMessage, transportation = 'walking', userCoords = null }: SpotCardProps) {
  const rating = typeof spot.rating === 'number' ? spot.rating : null
  const typeEmoji = guessTypeEmoji(spot.name)
  const travelIcon = transportation === 'driving' ? '🚗' : '🚶'
  const travelLabel = transportation === 'driving' ? '車で' : '徒歩で'
  const distance = userCoords ? formatDistance(haversineKm(userCoords, spot.location)) : null

  return (
    <div style={{
      borderRadius: 20,
      overflow: 'hidden',
      background: 'rgba(15, 20, 35, 0.95)',
      border: '1px solid rgba(255,255,255,0.08)',
      boxShadow: '0 12px 48px rgba(0,0,0,0.6)',
      animation: 'fadeIn 0.4s ease forwards',
    }}>

      {/* ── ヒーロー写真 ── */}
      <div style={{ position: 'relative', height: 240, background: 'rgba(20,28,48,1)', overflow: 'hidden' }}>
        {spot.photo_url ? (
          <img
            src={spot.photo_url}
            alt={spot.name}
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
            onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
        ) : (
          <div style={{
            width: '100%', height: '100%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '6rem', opacity: 0.18,
          }}>
            {typeEmoji}
          </div>
        )}
        {/* 下からのグラデーションオーバーレイ */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(to top, rgba(15,20,35,1) 0%, rgba(15,20,35,0.45) 55%, transparent 100%)',
        }} />
        {/* 店名 + 評価バッジ */}
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '0 1.25rem 1.1rem' }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: '0.5rem' }}>
            <h2 style={{ fontWeight: 700, fontSize: '1.25rem', color: '#fff', lineHeight: 1.25, margin: 0, flex: 1 }}>
              {spot.name}
            </h2>
            {rating && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 4,
                background: 'rgba(250,204,21,0.14)',
                border: '1px solid rgba(250,204,21,0.35)',
                borderRadius: 20, padding: '4px 10px', flexShrink: 0,
              }}>
                <span style={{ color: '#facc15', fontSize: '0.78rem' }}>★</span>
                <span style={{ color: '#facc15', fontWeight: 700, fontSize: '0.85rem' }}>{rating.toFixed(1)}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── 基本情報 ── */}
      <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.4rem', fontSize: '0.84rem', color: '#94a3b8' }}>
            <span style={{ flexShrink: 0 }}>📍</span>
            <span>{spot.address}</span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', fontSize: '0.83rem', marginTop: '0.2rem' }}>
            {spot.travel_time_minutes != null && (
              <span style={{ color: '#38bdf8', fontWeight: 600 }}>
                {travelIcon} {travelLabel}約{spot.travel_time_minutes}分
              </span>
            )}
            {distance && (
              <span style={{ color: '#a5b4fc' }}>
                📏 現在地から{distance}
              </span>
            )}
            {spot.estimated_stay_minutes && (
              <span style={{ color: '#94a3b8' }}>
                ⏱ 滞在目安 {spot.estimated_stay_minutes}分
              </span>
            )}
            {spot.price_level != null && PRICE_LABELS[spot.price_level] && (
              <span style={{ color: '#facc15', fontWeight: 600 }}>
                {PRICE_LABELS[spot.price_level]}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── 地図（現在地からの経路） ── */}
      <div style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', position: 'relative' }}>
        <MapEmbed origin={userCoords ?? null} spots={[spot.location]} transportation={transportation} height={180} />
        <a
          href={buildPlaceUrl(spot.location, spot.place_id)}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            position: 'absolute', right: 10, bottom: 10,
            fontSize: '0.72rem', fontWeight: 600,
            color: '#e2e8f0', textDecoration: 'none',
            background: 'rgba(15,20,35,0.9)',
            border: '1px solid rgba(255,255,255,0.15)',
            borderRadius: 16, padding: '4px 10px',
          }}
        >
          Google Mapsで開く ↗
        </a>
      </div>

      {/* ── マスターより ── */}
      {masterMessage && (
        <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <div style={{
            fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.08em',
            color: '#c084fc', marginBottom: '0.5rem', textTransform: 'uppercase',
          }}>
            ☕ マスターより
          </div>
          <div style={{
            fontSize: '0.88rem', color: '#e2e8f0', lineHeight: 1.7,
            padding: '0.75rem 1rem',
            background: 'rgba(192,132,252,0.06)',
            border: '1px solid rgba(192,132,252,0.12)',
            borderRadius: 12,
          }}>
            {masterMessage}
          </div>
        </div>
      )}

      {/* ── お客様の声 ── */}
      {spot.review_snippets && spot.review_snippets.length > 0 && (
        <div style={{ padding: '1rem 1.25rem' }}>
          <div style={{
            fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.08em',
            color: '#94a3b8', marginBottom: '0.55rem', textTransform: 'uppercase',
          }}>
            💬 お客様の声
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
            {spot.review_snippets.slice(0, 2).map((review, i) => (
              <div key={i} style={{
                display: 'flex', gap: '0.45rem',
                fontSize: '0.82rem', color: '#94a3b8', lineHeight: 1.6,
              }}>
                <span style={{ color: '#facc15', flexShrink: 0, fontSize: '0.75rem' }}>⭐</span>
                <span>「{review}」</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
