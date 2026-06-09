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

# r"Generate invoice for Autobahn Trucking Corporation of ₹45000 for Legal Due Diligance,Document Verification, and Legal Opinion. "
#     "Address:Autobanh Trucking Corporation Pvt. Ltd	23 & 24,"
#     "Shree Ambika Heritage, Plot No 1, Sector 1, "
#     "Kharghar Navi Mumbai,Mumbai 410210 "

query = (
    r"Generate invoice for Autobahn Trucking Corporation of ₹45000 for Legal Opinion. "
)
formatted_prompt = (
    f"<start_of_turn>user\n{system_instruction}\n\n{query}<end_of_turn>\n"
    f"<start_of_turn>model\n"
)
conversation_history = f"{formatted_prompt}"

while True:
    output = llma(
        prompt=conversation_history,
        max_tokens=5000,
        stop=["<end_of_turn>"],
        echo=False,
    )
    raw_response = output["choices"][0]["text"].strip()
    conversation_history += f"{raw_response} <end_of_turn>\n"
    print("\n" + "=" * 50)
    print("               AGENT OUTPUT")
    print("=" * 50 + "\n")

    try:
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
            print(json.dumps(parsed_json, indent=2))

            print("\n🖌️  Passing data to ReportLab...")
            generate_invoice_pdf(parsed_json)
            break
        else:
            raise json.JSONDecodeError(
                "No proper json format found to decode", raw_response, 0
            )

    except json.JSONDecodeError:
        print("🟡 STATUS: [CLARIFICATION MODE] - Missing Information Detected:\n")
        print("┌────────────────────────────────────────────────────────┐")
        for line in raw_response.splitlines():
            print(f"{line.strip():<52}. |")
        print("└────────────────────────────────────────────────────────┘")

        ans = input("User: ")
        conversation_history += (
            f"<start_of_turn>user\n {ans}<end_of_turn>\n\n<start_of_turn>model\n"
        )
    print("\n" + "=" * 50)
