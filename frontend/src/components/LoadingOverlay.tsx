import React, { useEffect, useState } from 'react';

export default function LoadingOverlay() {
  const [messageIndex, setMessageIndex] = useState(0);
  
  const messages = [
    "ナビを設定中... 少しお待ちくださいね。",
    "周辺の通りを検索中... 安全運転で行きますよ。",
    "お客さんの気分に合う場所... ここなんて良さそうです。",
    "ルート確定... まもなくご案内します。"
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % messages.length);
    }, 3000); // 3秒ごとにメッセージ変更
    return () => clearInterval(interval);
  }, [messages.length]);

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(11, 15, 25, 0.85)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
    }} className="animate-fade-in">
      <div 
        className="neon-pulse"
        style={{
          width: '60px',
          height: '60px',
          borderRadius: '50%',
          border: '4px solid var(--taxi-yellow)',
          borderTopColor: 'transparent',
          animation: 'spin 1s linear infinite, neonPulse 2s infinite ease-in-out',
          marginBottom: '2rem'
        }}
      />
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}} />
      <h3 style={{ 
        color: '#fff', 
        fontSize: '1.2rem', 
        fontWeight: 500,
        textAlign: 'center',
        padding: '0 20px',
        transition: 'opacity 0.5s ease'
      }}>
        {messages[messageIndex]}
      </h3>
    </div>
  );
}
