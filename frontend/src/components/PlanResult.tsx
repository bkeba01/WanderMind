'use client';

import React, { useState } from 'react';

type TourStop = {
  destination: {
    place_id: string;
    name: string;
    address: string;
    rating: number | string;
    location: {
      latitude: number;
      longitude: number;
    };
  };
  activity_proposal: string;
  travel_time_to_next: number | null;
};

type PlanData = {
  plan_title: string;
  expected_emotion: string;
  stops: TourStop[];
  weather: {
    condition: string;
    temperature: number;
  };
};

type PlanResultProps = {
  data: PlanData;
  onReset: () => void;
  onRefine: (feedback: string) => void;
  isLoadingRefine: boolean;
};

export default function PlanResult({ data, onReset, onRefine, isLoadingRefine }: PlanResultProps) {
  const { plan_title, expected_emotion, stops, weather } = data;
  const [feedback, setFeedback] = useState('');

  const handleFeedbackSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!feedback.trim()) return;
    onRefine(feedback);
  };

  return (
    <div className="glass-panel animate-fade-in" style={{ padding: '2rem', maxWidth: '700px', width: '100%', margin: '0 auto' }}>
      
      {/* 運転手のセリフ風ヘッダー */}
      <div style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '1.5rem', marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.5rem', color: 'var(--taxi-yellow)', marginBottom: '0.5rem' }}>
          「お客さん、こんなルートはいかがですか？」
        </h2>
        <p style={{ color: 'var(--text-muted)' }}>
          外は{weather.condition}（{weather.temperature}℃）みたいですね。<br/>
          テーマは『{plan_title}』です。
        </p>
      </div>

      {/* タイムライン表示 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0rem', position: 'relative' }}>
        {stops.map((stop, index) => {
          const mapUrl = `https://maps.google.com/maps?q=${stop.destination.location.latitude},${stop.destination.location.longitude}&hl=ja&z=15&output=embed`;
          
          return (
            <div key={index} style={{ display: 'flex', gap: '1.5rem', paddingBottom: stop.travel_time_to_next ? '1.5rem' : '0' }}>
              
              {/* 左側：タイムラインの線と点 */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '40px' }}>
                <div style={{ width: '20px', height: '20px', borderRadius: '50%', backgroundColor: 'var(--neon-blue)', zIndex: 2 }}></div>
                {stop.travel_time_to_next !== null && (
                  <div style={{ flex: 1, width: '2px', backgroundColor: 'rgba(255,255,255,0.2)', margin: '8px 0' }}></div>
                )}
              </div>

              {/* 右側：コンテンツ */}
              <div style={{ flex: 1, paddingBottom: '2rem' }}>
                <h3 style={{ fontSize: '1.2rem', color: 'var(--neon-blue)', marginBottom: '0.3rem' }}>
                  {index + 1}. {stop.destination.name}
                </h3>
                <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.8rem' }}>
                  📍 {stop.destination.address} (⭐ {stop.destination.rating})
                </p>
                
                <div style={{ backgroundColor: 'rgba(0,0,0,0.3)', padding: '1rem', borderRadius: '8px', borderLeft: '4px solid var(--neon-purple)', marginBottom: '1rem' }}>
                  <p style={{ color: '#e2e8f0', lineHeight: 1.6, fontSize: '0.95rem' }}>
                    {stop.activity_proposal}
                  </p>
                </div>

                <div style={{ borderRadius: '8px', overflow: 'hidden', height: '150px', border: '1px solid rgba(255,255,255,0.1)' }}>
                  <iframe 
                    src={mapUrl}
                    width="100%" 
                    height="100%" 
                    style={{ border: 0 }} 
                    allowFullScreen={false} 
                    loading="lazy" 
                    referrerPolicy="no-referrer-when-downgrade"
                  />
                </div>

                {stop.travel_time_to_next !== null && (
                  <div style={{ marginTop: '1.5rem', color: 'var(--taxi-yellow)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span>⬇️</span>
                    <span>次の目的地まで 約 {stop.travel_time_to_next} 分</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 得られる感情 */}
      <div style={{ marginTop: '1rem', padding: '1rem', borderTop: '1px solid rgba(255,255,255,0.1)', fontSize: '0.9rem', color: 'var(--taxi-yellow)', textAlign: 'center' }}>
        💡 この旅が終わる頃には、{expected_emotion}
      </div>

      {/* フィードバック入力欄 */}
      <div style={{ marginTop: '2rem', backgroundColor: 'rgba(255,255,255,0.05)', padding: '1.5rem', borderRadius: '8px' }}>
        <h4 style={{ marginBottom: '1rem', fontSize: '1rem', color: '#f8fafc' }}>
          「何かご要望はありますか？（もっと歩きたくない、カフェを変えて、など）」
        </h4>
        <form onSubmit={handleFeedbackSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            className="taxi-input"
            style={{ flex: 1 }}
            placeholder="例: もう少し静かな場所がいいな"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            disabled={isLoadingRefine}
          />
          <button type="submit" className="taxi-btn" disabled={isLoadingRefine || !feedback.trim()}>
            {isLoadingRefine ? '再検索中...' : '別のルートを頼む'}
          </button>
        </form>
      </div>

      {/* リセットボタン */}
      <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
        <button onClick={onReset} className="taxi-btn" style={{ width: '100%', background: 'transparent', border: '1px solid var(--text-muted)', color: 'var(--text-muted)' }} disabled={isLoadingRefine}>
          最初から入力し直す（降りる）
        </button>
      </div>

    </div>
  );
}
