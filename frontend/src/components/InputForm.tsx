'use client';

import React, { useState } from 'react';

type Location = {
  latitude: number;
  longitude: number;
};

type InputFormProps = {
  onSubmit: (
    mood: string, 
    freeTime: number, 
    location: Location,
    transportation: string,
    companion: string,
    budget: string
  ) => void;
};

export default function InputForm({ onSubmit }: InputFormProps) {
  const [mood, setMood] = useState('');
  const [freeTime, setFreeTime] = useState<number>(120);
  const [transportation, setTransportation] = useState('walk_transit');
  const [companion, setCompanion] = useState('solo');
  const [budget, setBudget] = useState('normal');
  const [isLoadingLocation, setIsLoadingLocation] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!mood.trim()) {
      setErrorMsg('お客さん、気分だけでも教えてもらえませんか？');
      return;
    }

    setIsLoadingLocation(true);
    setErrorMsg('');

    if (!navigator.geolocation) {
      setErrorMsg('お使いのブラウザでは現在地が取得できないようです。');
      setIsLoadingLocation(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setIsLoadingLocation(false);
        onSubmit(mood, freeTime, {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        }, transportation, companion, budget);
      },
      (error) => {
        setIsLoadingLocation(false);
        setErrorMsg('現在地の取得に失敗しました。GPSの設定を確認してくださいね。');
      }
    );
  };

  return (
    <div className="glass-panel animate-fade-in" style={{ padding: '2rem', maxWidth: '500px', width: '100%', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.5rem', marginBottom: '0.5rem', color: 'var(--taxi-yellow)' }}>
          「お客さん、お疲れ様です。<br/>今日はどちらまで？」
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          今の気分や条件を教えてください。<br/>
          あなたにピッタリのツアープランをご案内しますよ。
        </p>
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', color: '#cbd5e1' }}>
            今の気分や、やりたいことは？
          </label>
          <input
            type="text"
            className="taxi-input"
            placeholder="例: 静かなところでコーヒーが飲みたい、自然を感じたい"
            value={mood}
            onChange={(e) => setMood(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', gap: '1rem' }}>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', color: '#cbd5e1' }}>
              空き時間 (分)
            </label>
            <input
              type="number"
              className="taxi-input"
              min="30"
              step="30"
              value={freeTime}
              onChange={(e) => setFreeTime(Number(e.target.value))}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', color: '#cbd5e1' }}>
              交通手段
            </label>
            <select className="taxi-input" value={transportation} onChange={(e) => setTransportation(e.target.value)}>
              <option value="walk_transit">徒歩 / 電車・バス</option>
              <option value="driving">車（タクシー）</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1rem' }}>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', color: '#cbd5e1' }}>
              同伴者
            </label>
            <select className="taxi-input" value={companion} onChange={(e) => setCompanion(e.target.value)}>
              <option value="solo">一人</option>
              <option value="date">デート</option>
              <option value="friends">友達</option>
              <option value="family">家族</option>
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', color: '#cbd5e1' }}>
              予算感
            </label>
            <select className="taxi-input" value={budget} onChange={(e) => setBudget(e.target.value)}>
              <option value="save">節約（安く済ませる）</option>
              <option value="normal">普通</option>
              <option value="splurge">贅沢（お金をかける）</option>
            </select>
          </div>
        </div>

        {errorMsg && (
          <div style={{ color: '#ef4444', fontSize: '0.85rem', textAlign: 'center', backgroundColor: 'rgba(239, 68, 68, 0.1)', padding: '8px', borderRadius: '4px' }}>
            {errorMsg}
          </div>
        )}

        <button 
          type="submit" 
          className="taxi-btn"
          disabled={isLoadingLocation}
          style={{ marginTop: '1rem', width: '100%' }}
        >
          {isLoadingLocation ? 'ルートを検索中...' : '行き先をお任せする'}
        </button>
      </form>
    </div>
  );
}
