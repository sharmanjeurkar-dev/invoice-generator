import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY"),
    timeout=30.0,
    max_retries=1,
)


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
    key = os.getenv("NVIDIA_API_KEY")
    print("Key loaded:", bool(key), key[:8] if key else None)
    try:
        print("Sending request to NVIDIA...")
        response = client.chat.completions.create(
            model="meta/llama-3.1-8b-instruct",  # The correct NVIDIA path
            messages=[
                {
                    "role": "system",
                    "content": f"{system_instruction}\n\nIMPORTANT: Return ONLY valid JSON. No markdown blocks.",
                },
                {"role": "user", "content": full_prompt},
            ],
            temperature=0.1,
            max_tokens=2048,
        )

        raw_content = response.choices[0].message.content.strip()
        print("Got response.")
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
        print(f"⚠️ Failed to parse JSON from AI: {raw_content}")
        return {"status": "error", "message": "AI returned malformed data."}
    except Exception as e:
        print(f"⚠️ NVIDIA API ERROR: {e}")
        return {"status": "error", "message": "Failed to connect to the AI model."}


print(generate_json_from_prompt())
