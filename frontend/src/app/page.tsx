'use client';

import { useState } from 'react';
import InputForm from '@/components/InputForm';
import LoadingOverlay from '@/components/LoadingOverlay';
import PlanResult from '@/components/PlanResult';

export default function Home() {
  const [appState, setAppState] = useState<'input' | 'loading' | 'result'>('input');
  const [planData, setPlanData] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState('');
  
  // Refine用のステート
  const [originalRequest, setOriginalRequest] = useState<any>(null);
  const [isLoadingRefine, setIsLoadingRefine] = useState(false);

  const handleGeneratePlan = async (
    mood: string, 
    freeTime: number, 
    location: { latitude: number; longitude: number },
    transportation: string,
    companion: string,
    budget: string
  ) => {
    setAppState('loading');
    setErrorMsg('');
    
    const reqPayload = {
      mood,
      free_time_minutes: freeTime,
      location,
      transportation,
      companion,
      budget
    };
    setOriginalRequest(reqPayload);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const res = await fetch(`${apiUrl}/api/v1/plans/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(reqPayload),
      });

      if (!res.ok) {
        const errText = await res.text();
        console.error("Backend Error Response:", errText);
        throw new Error(`バックエンド通信エラー: ${errText}`);
      }

      const json = await res.json();
      if (json.status === 'success') {
        setPlanData(json.data);
        setAppState('result');
      } else {
        throw new Error('予期せぬエラー');
      }
    } catch (error) {
      console.error(error);
      setErrorMsg('すいませんお客さん、行き先が見つかりませんでした... もう一度教えてもらえませんか？');
      setAppState('input');
    }
  };

  const handleRefinePlan = async (feedback: string) => {
    if (!originalRequest || !planData) return;
    
    setIsLoadingRefine(true);
    setErrorMsg('');

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const res = await fetch(`${apiUrl}/api/v1/plans/refine`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          original_request: originalRequest,
          feedback_text: feedback,
          previous_plan_data: planData
        }),
      });

      if (!res.ok) {
        const errText = await res.text();
        console.error("Backend Error Response:", errText);
        throw new Error(`バックエンド通信エラー: ${errText}`);
      }

      const json = await res.json();
      if (json.status === 'success') {
        setPlanData(json.data);
      } else {
        throw new Error('予期せぬエラー');
      }
    } catch (error) {
      console.error(error);
      alert('別のルートが見つかりませんでした。条件を変えて最初からやり直してみてください。');
    } finally {
      setIsLoadingRefine(false);
    }
  };

  const handleReset = () => {
    setPlanData(null);
    setOriginalRequest(null);
    setAppState('input');
  };

  return (
    <main style={{ 
      minHeight: '100vh', 
      display: 'flex', 
      flexDirection: 'column',
      justifyContent: 'center',
      padding: '2rem 1rem'
    }}>
      
      {/* エラーメッセージ（トップレベル） */}
      {errorMsg && appState === 'input' && (
        <div style={{ maxWidth: '500px', margin: '0 auto 1rem', padding: '1rem', backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5', borderRadius: '8px', textAlign: 'center' }}>
          {errorMsg}
        </div>
      )}

      {/* 画面切り替え */}
      {appState === 'input' && (
        <InputForm onSubmit={handleGeneratePlan} />
      )}

      {appState === 'loading' && (
        <LoadingOverlay />
      )}

      {appState === 'result' && planData && (
        <PlanResult 
          data={planData} 
          onReset={handleReset} 
          onRefine={handleRefinePlan}
          isLoadingRefine={isLoadingRefine}
        />
      )}

    </main>
  );
}
