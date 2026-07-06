import json
import os
import sys

from llama_cpp import Llama

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, project_root)
from src.document.Pdf_generator import generate_invoice_pdf

llma = Llama(
    model_path="./models/gemma-2-9b-it-Q5_K_M.gguf",
    n_ctx=8192,
    n_batch=2048,
    flash_attn=True,  # efficient memory and attention management
    n_gpu_layers=-1,
    verbose=False,
)
conversation_history = ""

system_promt_file_path = (
    f"/Users/sharmanjeurkar/Projects/invoice-agent/config/system_prompt.txt"
)
with open(system_promt_file_path, "r", encoding="utf-8") as f:
    system_instruction = f.read().strip()


def generate_json_for_inbvoice_from_prompt(query: str) -> dict:
    formatted_prompt = (
        f"<start_of_turn>user\n{system_instruction}\n\n{query}<end_of_turn>\n"
        f"<start_of_turn>model\n"
    )
    conversation_history = f"{formatted_prompt}"

    output = llma(
        prompt=conversation_history,
        max_tokens=5000,
        stop=["<end_of_turn>"],
        echo=False,
    )
    raw_response = output["choices"][0]["text"].strip()
    print(f"\n--- RAW AI RESPONSE ---\n{raw_response}\n-----------------------\n")
    if "```json" in raw_response:
        raw_response = raw_response.split("```json")[1]
    if "```" in raw_response:
        raw_response = raw_response.split("```")[0]
    conversation_history += f"{raw_response} <end_of_turn>\n"
    print("\n" + "=" * 50)
    print("               AGENT OUTPUT")
    print("=" * 50 + "\n")

    # Find the first '{' and the last '}' in the text
    start_idx = raw_response.find("{")
    end_idx = raw_response.rfind("}")

    if start_idx != -1 and end_idx != -1:
        # Extract ONLY the JSON part
        cleaned_response = raw_response[start_idx : end_idx + 1]
        parsed_json = json.loads(cleaned_response, strict=False)
        print(
            "🟢 STATUS: [GENERATION MODE] - Final Invoice JSON Generated Successfully:\n"
        )
        return {"status": "success", "data": parsed_json}
    else:
        return {"status": "clarification", "message": raw_response}


print("\n" + "=" * 50)


def text_to_json(text: str, key: str = "Prompt"):
    return json.dumps([key, text], separators=(",", ":"))


# prompt: Generate invoice for Ram of ₹30000 for Legal Opinion and for Document Verifaction ₹20000. Address:  23 and 24 Shree ambika heritage, Plot no 1, Sector 1, Khargar, Navi Mumbai, Mumbai 4102101
