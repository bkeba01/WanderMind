export type Spot = {
  place_id: string
  name: string
  address: string
  rating: number | string
  location: { latitude: number; longitude: number }
  photo_url?: string | null
  price_level?: number | null
  editorial_summary?: string | null
  review_snippets?: string[]
  estimated_stay_minutes?: number
  travel_time_minutes?: number | null
  open_now?: boolean | null
  opening_hours_today?: string | null
}

export type RouteInfo = {
  total_travel_minutes: number
  spots: Spot[]
  travel_times: number[]
}

export type Message = {
  id: string
  role: 'ai' | 'user'
  content: string
}

/** フロントエンドのセットアップステップ（バックエンド接続前） */
export type SetupStep = 'mood' | 'time' | 'transport' | 'chatting'

export type MoodOption = {
  emoji: string
  label: string
  value: string
}

export type QuickReply = {
  label: string
  value: string
}
