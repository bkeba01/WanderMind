import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

tour_plan_schema = {
    "type": "OBJECT",
    "properties": {
        "plan_title": {"type": "STRING", "description": "お出かけツアープランのタイトル"},
        "expected_emotion": {"type": "STRING", "description": "このプランを終えたあとにユーザーが得られる感情"},
        "stops": {
            "type": "ARRAY",
            "description": "巡るスポットの順序リスト（最大3件まで）",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "selected_place_id": {"type": "STRING", "description": "提示した候補リストの中から選んだスポットのplace_id"},
                    "activity_proposal": {"type": "STRING", "description": "この場所で何をして過ごすかの具体的な提案"}
                },
                "required": ["selected_place_id", "activity_proposal"]
            }
        }
    },
    "required": ["plan_title", "expected_emotion", "stops"]
}

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents="こんにちは。テストです",
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=tour_plan_schema,
        temperature=0.2
    ),
)
print(response.text)
