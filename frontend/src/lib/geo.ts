export type LatLng = { latitude: number; longitude: number }

/** 2点間の直線距離 (km) */
export function haversineKm(a: LatLng, b: LatLng): number {
  const R = 6371
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(b.latitude - a.latitude)
  const dLng = toRad(b.longitude - a.longitude)
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.latitude)) * Math.cos(toRad(b.latitude)) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

/** 1km未満はm表示、それ以上はkm表示 */
export function formatDistance(km: number): string {
  return km < 1 ? `${Math.round((km * 1000) / 10) * 10}m` : `${km.toFixed(1)}km`
}

const fmt = (p: LatLng) => `${p.latitude},${p.longitude}`

/** 埋め込み地図URL（現在地からの経路表示。現在地がなければスポット中心表示） */
export function buildDirectionsEmbedUrl(
  origin: LatLng | null,
  spots: LatLng[],
  transportation: 'walking' | 'driving',
): string {
  if (!origin || spots.length === 0) {
    const center = spots[0] ?? origin
    return `https://maps.google.com/maps?q=${center ? fmt(center) : ''}&hl=ja&z=15&output=embed`
  }
  const daddr = spots.map(fmt).join('+to:')
  const dirflg = transportation === 'driving' ? 'd' : 'w'
  return `https://maps.google.com/maps?saddr=${fmt(origin)}&daddr=${daddr}&dirflg=${dirflg}&hl=ja&output=embed`
}

/** Google Mapsアプリ/サイトでナビを開くURL */
export function buildNavUrl(
  origin: LatLng | null,
  spots: LatLng[],
  transportation: 'walking' | 'driving',
): string {
  const destination = spots[spots.length - 1]
  const params = new URLSearchParams({
    api: '1',
    destination: fmt(destination),
    travelmode: transportation,
  })
  if (origin) params.set('origin', fmt(origin))
  const waypoints = spots.slice(0, -1).map(fmt).join('|')
  if (waypoints) params.set('waypoints', waypoints)
  return `https://www.google.com/maps/dir/?${params.toString()}`
}

/** 単一スポットをGoogle Mapsで開くURL */
export function buildPlaceUrl(location: LatLng, placeId?: string): string {
  const params = new URLSearchParams({ api: '1', query: fmt(location) })
  if (placeId) params.set('query_place_id', placeId)
  return `https://www.google.com/maps/search/?${params.toString()}`
}
