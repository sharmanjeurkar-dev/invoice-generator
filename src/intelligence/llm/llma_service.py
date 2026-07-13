import json
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

# 1. Load environment variables
load_dotenv()

# 2. Configure the NVIDIA NIM SDK
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1", api_key=os.getenv("NVIDIA_API_KEY")
)

# 3. Dynamic path routing (Safe for Local Mac and Production Docker)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
sys.path.insert(0, project_root)

system_promt_file_path = os.path.join(project_root, "config", "system_prompt.txt")

with open(system_promt_file_path, "r", encoding="utf-8") as f:
    system_instruction = f.read().strip()


def generate_json_for_invoice_from_prompt(query: str) -> dict:
    print("\n--- SENDING PROMPT TO NVIDIA NIM (meta/llama-3.1-8b-instruct) ---")

    max_retries = 3
    raw_content = ""

    # Exponential Backoff Loop for Rate Limits
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="meta/llama-3.1-8b-instruct",
                messages=[
                    {
                        "role": "system",
                        "content": f"{system_instruction}\n\nIMPORTANT: Return ONLY valid JSON. No conversational text. No markdown blocks.",
                    },
                    {
                        "role": "user",
                        # Only send the user's query here, not the system prompt again!
                        "content": f"USER PROMPT:\n{query}",
                    },
                ],
                temperature=0.1,
                max_tokens=2048,
            )

            raw_content = response.choices[0].message.content.strip()
            break  # Success! Break out of the retry loop

        except Exception as e:
            print(f"⚠️ Unexpected Error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                return {
                    "status": "error",
                    "message": "An unexpected error occurred after multiple retries.",
                }
            time.sleep(2**attempt)

    print(f"\n--- RAW AI RESPONSE ---\n{raw_content}\n-----------------------\n")

    # Safe Markdown Stripper
    if raw_content.startswith("```json"):
        raw_content = raw_content[7:]
    if raw_content.endswith("```"):
        raw_content = raw_content[:-3]

    # Find the first '{' and the last '}' to safely extract JSON
    start_idx = raw_content.find("{")
    end_idx = raw_content.rfind("}")

    if start_idx != -1 and end_idx != -1:
        cleaned_response = raw_content[start_idx : end_idx + 1]

        try:
            parsed_json = json.loads(cleaned_response, strict=False)

            # Catch clarifications
            if parsed_json.get("status") == "clarification":
                return parsed_json

            print("\n" + "=" * 50)
            print("               AGENT OUTPUT")
            print("=" * 50 + "\n")
            print("🟢 STATUS: [GENERATION MODE] - Final JSON Generated Successfully:\n")

            return {"status": "success", "data": parsed_json}

        except json.JSONDecodeError:
            print(f"⚠️ Failed to parse JSON from AI: {cleaned_response}")
            return {"status": "error", "message": "AI returned malformed data."}
    else:
        return {"status": "clarification", "message": raw_content}


# Alias function
def generate_json_from_prompt(query: str) -> dict:
    return generate_json_for_invoice_from_prompt(query)


def text_to_json(text: str, key: str = "Prompt"):
    return json.dumps([key, text], separators=(",", ":"))
