'use client'

import { buildDirectionsEmbedUrl, type LatLng } from '@/lib/geo'

type MapEmbedProps = {
  origin: LatLng | null
  spots: LatLng[]
  transportation: 'walking' | 'driving'
  height?: number
}

/** 現在地→スポットの経路を埋め込み地図で表示する */
export default function MapEmbed({ origin, spots, transportation, height = 200 }: MapEmbedProps) {
  const src = buildDirectionsEmbedUrl(origin, spots, transportation)
  return (
    <div style={{ height, overflow: 'hidden', background: 'rgba(20,28,48,1)' }}>
      <iframe
        src={src}
        width="100%"
        height="100%"
        style={{ border: 0 }}
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
      />
    </div>
  )
}
