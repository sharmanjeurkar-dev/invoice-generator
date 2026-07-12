import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


def generate_json_from_prompt() -> dict:
    system_instruction = """
    You are an expert legal financial AI. Extract the details from the user's prompt
    and format them strictly as a JSON object matching the InvoicePayloadModel schema.
    If you are missing critical information (like a client address and it is not in the directory),
    return a JSON object with {"status": "clarification", "message": "Your question to the user"}.

    IMPORTANT: You must return ONLY valid JSON. Do not include markdown formatting like ```json.
    """

    prompt = input("Enter prompt: ")
    full_prompt = f"{system_instruction}\n\nUSER PROMPT:\n{prompt}"

    try:
        response = client.models.generate_content(
            model="gemma-4-31b-it",  # Your specific model string
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                # 🚨 REMOVED response_mime_type so the Gemma server doesn't crash!
            ),
        )

        raw_content = response.text.strip()

        # 🚨 BROUGHT BACK the markdown stripping since Gemma will likely add it
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]

        parsed_json = json.loads(raw_content.strip())

        if parsed_json.get("status") == "clarification":
            return parsed_json

        return {"status": "success", "data": parsed_json}

    except json.JSONDecodeError:
        print(f"⚠️ Failed to parse JSON from AI: {response.text}")
        return {"status": "error", "message": "AI returned malformed data."}
    except Exception as e:
        print(f"⚠️ Google AI Studio Error: {e}")
        return {"status": "error", "message": "Failed to connect to the AI model."}


print(generate_json_from_prompt())
# import os

# from dotenv import load_dotenv
# from google import genai

# load_dotenv()

# # Connect to Google
# client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# print("🔍 Fetching models available to your API key...\n")

# # List every single model you are allowed to access
# try:
#     for model in client.models.list():
#         print(model.name)
# except Exception as e:
#     print(f"Error fetching models: {e}")
