from llama_cpp import Llama

llma = Llama(
    model_path="./models/gemma-2-9b-it-Q8_0.gguf",
    n_gpu_layers=-1,
    verbose=False,
)
output = llma(
    prompt="<start_of_turn>user\nGenerate invoice in json format for Autobahn Trucking Coorporation of ₹45000 for Legal Due Diligance, Document Verification, and Legal Opinion, Merut(UP)<end_of_turn>\n<start_of_turn>model\n",
    max_tokens=800,
    stop=["<end_of_user>"],
    echo=True,
)
print(output)
