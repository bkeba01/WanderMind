'use client'

import { useEffect, useRef, useState } from 'react'
import type { Message, Spot, RouteInfo, SetupStep, MoodOption, QuickReply } from '@/types/chat'

// ── 選択肢の定義 ────────────────────────────────────────────

const MOOD_OPTIONS: MoodOption[] = [
  { emoji: '🌿', label: 'リフレッシュしたい', value: 'リフレッシュしたい、自然を感じたい' },
  { emoji: '🎉', label: 'はしゃぎたい', value: 'はしゃぎたい、テンションを上げたい' },
  { emoji: '☕', label: 'のんびりしたい', value: 'のんびりゆっくり過ごしたい' },
  { emoji: '✨', label: '刺激がほしい', value: '刺激的な体験がしたい、ワクワクしたい' },
  { emoji: '🍽️', label: '美味しいもの食べたい', value: 'おいしいものが食べたい、グルメがしたい' },
  { emoji: '🎨', label: '文化・芸術を楽しみたい', value: '文化的なものや芸術に触れたい' },
]

const TIME_OPTIONS = [
  { label: '30分', value: 30 },
  { label: '1時間', value: 60 },
  { label: '2時間', value: 120 },
  { label: '半日', value: 240 },
]

const TRANSPORT_OPTIONS = [
  { emoji: '🚶', label: '徒歩', value: 'walking' },
  { emoji: '🚗', label: '車', value: 'driving' },
]

const CHAT_QUICK_REPLIES: QuickReply[] = [
  { label: '👍 いいね！', value: 'いいね' },
  { label: '👎 違う', value: '違う' },
  { label: '🔥 もっとはしゃぎたい', value: 'もっとはしゃぎたい' },
  { label: '🌿 静かな場所がいい', value: '静かな場所がいい' },
  { label: '✅ それでいこう！', value: 'それでいこう' },
]

// ── サブコンポーネント ────────────────────────────────────────

function MessageBubble({ msg }: { msg: Message }) {
  const isAI = msg.role === 'ai'
  return (
    <div style={{ display: 'flex', justifyContent: isAI ? 'flex-start' : 'flex-end', alignItems: 'flex-end', gap: '0.5rem' }}>
      {isAI && (
        <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'rgba(192,132,252,0.2)', border: '1px solid rgba(192,132,252,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem', flexShrink: 0 }}>
          ☕
        </div>
      )}
      <div style={{
        maxWidth: '72%',
        padding: '0.7rem 1rem',
        borderRadius: isAI ? '4px 18px 18px 18px' : '18px 4px 18px 18px',
        background: isAI ? 'rgba(17,24,39,0.85)' : 'rgba(250,204,21,0.12)',
        border: `1px solid ${isAI ? 'rgba(255,255,255,0.07)' : 'rgba(250,204,21,0.25)'}`,
        color: isAI ? 'var(--text-color)' : 'var(--taxi-yellow)',
        fontSize: '0.9rem',
        lineHeight: 1.65,
        whiteSpace: 'pre-wrap',
      }}>
        {msg.content}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: '0.5rem' }}>
      <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'rgba(192,132,252,0.2)', border: '1px solid rgba(192,132,252,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem', flexShrink: 0 }}>
        ☕
      </div>
      <div style={{ padding: '0.7rem 1rem', borderRadius: '4px 18px 18px 18px', background: 'rgba(17,24,39,0.85)', border: '1px solid rgba(255,255,255,0.07)', display: 'flex', gap: 5, alignItems: 'center' }}>
        {[0, 1, 2].map(i => (
          <span key={i} className="typing-dot" style={{ animationDelay: `${i * 0.2}s` }} />
        ))}
      </div>
    </div>
  )
}

function RouteCard({ routeInfo }: { routeInfo: RouteInfo }) {
  return (
    <div style={{ background: 'rgba(250,204,21,0.06)', border: '1px solid rgba(250,204,21,0.25)', borderRadius: 14, padding: '1rem', marginLeft: 44 }}>
      <div style={{ color: 'var(--taxi-yellow)', fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.75rem' }}>
        🗺️ 確定ルート（移動 {routeInfo.total_travel_minutes}分）
      </div>
      {routeInfo.spots.map((spot, i) => (
        <div key={spot.place_id} style={{ display: 'flex', alignItems: 'flex-start', marginBottom: i < routeInfo.spots.length - 1 ? '0.6rem' : 0 }}>
          <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'var(--taxi-yellow)', color: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.72rem', fontWeight: 700, flexShrink: 0, marginRight: '0.65rem', marginTop: 2 }}>
            {i + 1}
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>{spot.name}</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{spot.address}</div>
            {i < routeInfo.travel_times.length && (
              <div style={{ color: 'var(--neon-blue)', fontSize: '0.76rem', marginTop: 2 }}>
                ↓ 次まで約{routeInfo.travel_times[i]}分
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── メインコンポーネント ──────────────────────────────────────

type ChatWindowProps = {
  messages: Message[]
  setupStep: SetupStep
  likedSpots: Spot[]
  routeInfo: RouteInfo | null
  chatPhase: 'collecting' | 'done'
  isLoading: boolean
  onMoodSelect: (mood: string) => void
  onTimeSelect: (minutes: number) => void
  onTransportSelect: (transport: string) => void
  onSend: (text: string) => void
}

export default function ChatWindow({
  messages,
  setupStep,
  likedSpots,
  routeInfo,
  chatPhase,
  isLoading,
  onMoodSelect,
  onTimeSelect,
  onTransportSelect,
  onSend,
}: ChatWindowProps) {
  const [textInput, setTextInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSendText = () => {
    const trimmed = textInput.trim()
    if (!trimmed || isLoading) return
    onSend(trimmed)
    setTextInput('')
  }

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* ── ヘッダー ── */}
      <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: '0.6rem', flexShrink: 0 }}>
        <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'rgba(192,132,252,0.15)', border: '1px solid rgba(192,132,252,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.3rem' }}>
          ☕
        </div>
        <div>
          <div style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--neon-purple)' }}>WanderMind</div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            {chatPhase === 'done'
              ? '✓ ルート確定'
              : setupStep === 'chatting'
              ? `${likedSpots.length}件お気に入り中`
              : 'マスターと相談中...'}
          </div>
        </div>
      </div>

      {/* ── メッセージエリア ── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 0.75rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
        {isLoading && <TypingIndicator />}
        {routeInfo && chatPhase === 'done' && <RouteCard routeInfo={routeInfo} />}
        <div ref={bottomRef} />
      </div>

      {/* ── アクションエリア ── */}
      <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', padding: '0.75rem', flexShrink: 0, background: 'rgba(11,15,25,0.95)', backdropFilter: 'blur(12px)' }}>

        {/* 気分選択 */}
        {setupStep === 'mood' && !isLoading && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem', marginBottom: '0.6rem' }}>
            {MOOD_OPTIONS.map(opt => (
              <button key={opt.value} onClick={() => onMoodSelect(opt.value)}
                style={{ padding: '0.65rem 0.5rem', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, background: 'rgba(255,255,255,0.03)', color: 'var(--text-color)', cursor: 'pointer', textAlign: 'left', fontSize: '0.85rem', transition: 'all 0.15s' }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--neon-purple)'; (e.currentTarget as HTMLButtonElement).style.background = 'rgba(192,132,252,0.08)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.1)'; (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.03)' }}
              >
                <span style={{ marginRight: '0.35rem' }}>{opt.emoji}</span>{opt.label}
              </button>
            ))}
          </div>
        )}

        {/* 時間選択 */}
        {setupStep === 'time' && !isLoading && (
          <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.6rem' }}>
            {TIME_OPTIONS.map(opt => (
              <button key={opt.value} onClick={() => onTimeSelect(opt.value)}
                style={{ flex: 1, padding: '0.6rem 0', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, background: 'rgba(255,255,255,0.03)', color: 'var(--text-color)', cursor: 'pointer', fontSize: '0.85rem', transition: 'all 0.15s' }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--taxi-yellow)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--taxi-yellow)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.1)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-color)' }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}

        {/* 交通手段選択 */}
        {setupStep === 'transport' && !isLoading && (
          <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.6rem' }}>
            {TRANSPORT_OPTIONS.map(opt => (
              <button key={opt.value} onClick={() => onTransportSelect(opt.value)}
                style={{ flex: 1, padding: '0.65rem', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, background: 'rgba(255,255,255,0.03)', color: 'var(--text-color)', cursor: 'pointer', fontSize: '0.88rem', transition: 'all 0.15s' }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--neon-blue)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--neon-blue)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.1)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-color)' }}
              >
                {opt.emoji} {opt.label}
              </button>
            ))}
          </div>
        )}

        {/* 会話中のクイックリプライ */}
        {setupStep === 'chatting' && chatPhase !== 'done' && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginBottom: '0.6rem' }}>
            {CHAT_QUICK_REPLIES.map(qr => (
              <button key={qr.value} onClick={() => onSend(qr.value)} disabled={isLoading}
                style={{ padding: '0.35rem 0.75rem', borderRadius: 20, border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.04)', color: 'var(--text-color)', fontSize: '0.8rem', cursor: 'pointer', opacity: isLoading ? 0.4 : 1, transition: 'all 0.15s' }}
                onMouseEnter={e => { if (!isLoading) (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--taxi-yellow)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.12)' }}
              >
                {qr.label}
              </button>
            ))}
          </div>
        )}

        {/* テキスト入力（セットアップ中も補助として常時表示、終了後は非表示） */}
        {chatPhase !== 'done' && (
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              className="taxi-input"
              placeholder={setupStep === 'mood' ? '気分を自分の言葉で...' : 'または自由に入力...'}
              value={textInput}
              onChange={e => setTextInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleSendText() }}
              disabled={isLoading}
              style={{ fontSize: '0.85rem', padding: '10px 12px' }}
            />
            <button className="taxi-btn" onClick={handleSendText} disabled={isLoading || !textInput.trim()}
              style={{ padding: '10px 16px', flexShrink: 0, fontSize: '0.85rem' }}>
              送信
            </button>
          </div>
        )}

        {chatPhase === 'done' && (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem', padding: '0.5rem' }}>
            ルートが確定しました。いい時間になりますよ ☕
          </div>
        )}
      </div>
    </div>
  )
}
