# WanderMind

「今の気分」と「空き時間」を伝えるだけで、AIのマスター（コンシェルジュ）との会話を通じて、
現在地周辺のお出かけプランを提案してくれるWebアプリです。

チャットでスポットに「いいね / 違う」と反応していくと、気に入った場所だけを巡る
ルート（移動時間・滞在目安つき）が完成します。

## 画面構成

| 左カラム | 右カラム |
|---|---|
| マスターとのチャット（気分・時間・移動手段の選択 → スポットへの反応） | 提案中スポットの詳細カード（写真・評価・現在地からの経路地図・距離）、いいねした経由候補リスト、確定後は全行程マップ＋Google Mapsナビリンク |

## 技術スタック

- **フロントエンド**: Next.js 16 / React 19 / TypeScript（`frontend/`）
- **バックエンド**: FastAPI + LangGraph（会話ステートマシン） / Gemini 2.5 Flash（`backend/`）
- **外部API**:
  - Google Places API (New) — スポット検索・写真・レビュー
  - Google Routes API — 移動時間の計算
  - Open-Meteo — 現在地の天気（APIキー不要）

## ディレクトリ構成

```
WanderMind/
├── .env.example        # 環境変数のテンプレート（コピーして .env を作る）
├── .venv/              # Python仮想環境（ルート直下に作成）
├── main.py             # 初期のCLIプロトタイプ（現在は未使用）
├── backend/
│   ├── main.py         # FastAPIエントリーポイント（チャットAPI）
│   ├── schemas.py      # Pydanticスキーマ
│   ├── services.py     # 外部API呼び出し（天気・Places・Routes）
│   └── graph/          # LangGraphによる会話フロー
│       ├── state.py    #   会話の状態定義
│       ├── nodes.py    #   各ノード（気分分析・スポット提案・ルート計画など）
│       └── builder.py  #   グラフの組み立て
└── frontend/
    └── src/
        ├── app/page.tsx           # メインページ（2カラムレイアウト）
        ├── components/            # ChatWindow, SpotCard, MapEmbed など
        ├── lib/geo.ts             # 距離計算・Google Maps URL生成
        └── types/chat.ts          # 型定義
```

## セットアップ

### 前提

- **Python 3.10以上**（`X | Y` 型構文を使っているため。3.9では起動できません）
- Node.js 18以上
- APIキー: Gemini APIキー / Google Cloud APIキー（Places API (New) と Routes API を有効化）

### 1. 環境変数

```bash
cp .env.example .env
```

`.env` を開いて2つのキーを設定します。

```
GEMINI_API_KEY=（Google AI StudioのAPIキー）
GOOGLE_MAPS_API_KEY=（Google CloudのAPIキー）
```

### 2. バックエンド

```bash
# リポジトリのルートで仮想環境を作成
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# ⚠️ 必ず backend/ ディレクトリから起動すること
cd backend
uvicorn main:app --reload
```

→ http://localhost:8000 で起動（APIドキュメント: http://localhost:8000/docs ）

> **注意**: ルートディレクトリから `uvicorn main:app` を実行すると、
> ルートにある旧プロトタイプの `main.py` を読み込んでしまい
> `Attribute "app" not found` エラーになります。

### 3. フロントエンド

```bash
cd frontend
npm install
npm run dev
```

→ http://localhost:3000 で起動。
バックエンドのURLを変えたい場合は環境変数 `NEXT_PUBLIC_API_URL` を設定します（デフォルト: `http://localhost:8000`）。

ブラウザの**位置情報の許可**が必要です（現在地周辺のスポット検索に使用）。

## 使い方（会話の流れ）

1. 気分を選ぶ（例: 🌿 リフレッシュしたい）
2. 空き時間を選ぶ（30分〜半日）
3. 移動手段を選ぶ（🚶 徒歩 / 🚗 車）
4. マスターがスポットを1件ずつ提案してくるので反応する
   - 「👍 いいね」→ 経由候補に追加して次の提案へ
   - 「👎 違う」→ 別のスポットを提案
   - 「もっと静かな場所がいい」→ 気分を汲み直して再提案
5. 「✅ それでいこう」→ いいねしたスポットを巡るルートが確定し、
   全行程マップとGoogle Mapsナビリンクが表示される

## APIエンドポイント

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/api/v1/health` | ヘルスチェック |
| POST | `/api/v1/chat/session` | 会話セッション開始（気分・現在地・移動手段を送信） |
| POST | `/api/v1/chat/{thread_id}` | 会話の継続（ユーザーの反応を送信） |
| POST | `/api/v1/plans/generate` | 一括プラン生成（旧API） |
| POST | `/api/v1/plans/refine` | プランの再生成（旧API） |

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| `TypeError: unsupported operand type(s) for \|` | Pythonが3.9以下。3.10以上で `.venv` を作り直す |
| `Error loading ASGI app. Attribute "app" not found` | ルートから起動している。`cd backend` してから `uvicorn main:app --reload` |
| `API Keys are not configured correctly` | `.env` がルートにない、またはキーが未設定 |
| スポットが見つからない | ブラウザの位置情報許可を確認。Google CloudでPlaces API (New)が有効か確認 |
