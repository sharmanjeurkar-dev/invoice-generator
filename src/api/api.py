import os
import uuid
from typing import List, Optional

import anyio
import psycopg2
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel

from src.document.Pdf_generator import generate_invoice_pdf
from tests.test_baseline_inference import generate_json_for_inbvoice_from_prompt


class AddressModel(BaseModel):
    line1: Optional[str] = ""
    line2: Optional[str] = ""
    line3: Optional[str] = ""


class ClientModel(BaseModel):
    name: str
    address: AddressModel
    email: Optional[str] = None


class ServiceModel(BaseModel):
    category: str = "Legal Professional Fees"  # Typo fixed
    details: str
    qty: int = 1
    amount: float


class InvoicePayloadModel(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    client: ClientModel
    services: List[ServiceModel]
    subtotal: float
    gst: Optional[float] = None
    total: float


class PromptRequestModel(BaseModel):
    prompt: str


app = FastAPI(
    title="Pentacles Legal firm",
    description="Internal microservice for invoice generator",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Email-Status"],
)

load_dotenv()


@app.get("/api/get-next-invoice-id")
def get_next_invoice_id():
    try:
        db_url = os.getenv("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # This securely pulls the next atomic number from Postgres
        cursor.execute("SELECT nextval('invoice_number_seq');")
        next_val = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        # Formats it as INV-1000, INV-1001, etc.
        return {"invoice_id": f"INV-{next_val}"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/prompt-to-invoice")
async def prompt_to_invoice_generator(response: PromptRequestModel):
    invoice_id = str(uuid.uuid4())[:8]
    prompt = str(response.prompt)
    print(f"📥 Received text prompt: {prompt}")
    try:
        llm_response = generate_json_for_inbvoice_from_prompt(prompt)
    except Exception as e:
        print(f"LLM Error: {e}")
        raise HTTPException(status_code=500, detail="failed to generate Ai response")

    if llm_response["status"] == "clarification":
        print("🟡 AI requested clarification. Sending back to UI.")
        return JSONResponse(
            content={"status": "clarification", "message": llm_response["message"]}
        )

    print("✅ Validating AI output structure...")
    try:
        validating_payload = InvoicePayloadModel(**llm_response["data"])
    except Exception as e:
        print(f"Validation Error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Invalid format generated. Validation returned negative results.",
        )

    invoice_dict = validating_payload.model_dump()
    inv_name = invoice_dict["client"]["name"]
    output_filename = f"{inv_name}_Invoice.pdf"
    address_data = invoice_dict["client"]["address"]
    for key in ["line1", "line2", "line3"]:
        if address_data.get(key) is None:
            address_data[key] = ""
    print("🖨️  Sending AI data to Playwright engine background thread...")

    try:
        await anyio.to_thread.run_sync(
            generate_invoice_pdf, invoice_dict, output_filename
        )
    except Exception as e:
        print(f"PDF Generation error {e}")
        raise HTTPException(status_code=500, detail="Pdf couldnt be generated")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    file_path = os.path.join(project_root, output_filename)

    email_status_msg = None

    if not os.path.exists(file_path):
        raise HTTPException(status_code=500, detail="PDF was not created successfully")

    if invoice_dict["client"].get("email"):
        target_email = invoice_dict["client"]["email"]
        client_name = invoice_dict["client"]["name"]
        print(f"🔌 Initializing MCP Connection for {target_email}...")

        server_params = StdioServerParameters(
            command="python", args=["src/intelligence/tools/email_mcp_service.py"]
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    print("🛠️  Triggering 'send_invoice_email' tool...")
                    result = await session.call_tool(
                        "send_invoice_on_email",
                        arguments={
                            "target_email": target_email,
                            "pdf_file_path": file_path,
                            "client_name": client_name,
                        },
                    )
                    print(f"📬 MCP Server Response: {result.content[0].text}")
                    email_status_msg = target_email
        except Exception as e:
            print(f"⚠️ MCP Connection Failed: {e}")

    print(f"📤 Returning {output_filename} to the client.")
    header = {}
    if email_status_msg:
        header["X-Email-Status"] = email_status_msg

    print("💾 Upserting EARNING to PostgreSQL ledger...")
    try:
        db_url = os.getenv("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        services_list = invoice_dict.get("services", [])
        service_strings = [
            srv.get("details", "Unnamed Service") for srv in services_list
        ]
        detailed_description = "Services: " + ", ".join(service_strings)
        safe_total = invoice_dict.get("total") or 0.0

        # Pull the ID generated by the AI in the JSON
        invoice_id = invoice_dict.get("invoice_number", "INV-UNKNOWN")

        # Use ON CONFLICT on the invoice_id to prevent duplicates
        cursor.execute(
            """
            INSERT INTO firm_financials 
            (transaction_type, amount, party_name, reference_file, description, invoice_id) 
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (invoice_id) 
            DO UPDATE SET 
                amount = EXCLUDED.amount,
                description = EXCLUDED.description,
                reference_file = EXCLUDED.reference_file,
                created_at = CURRENT_TIMESTAMP;
            """,
            (
                "EARNING",
                safe_total,
                invoice_dict["client"]["name"],
                output_filename,
                detailed_description,
                invoice_id,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ PostgreSQL record {invoice_id} upserted successfully!")
    except Exception as e:
        print(f"⚠️ Database Error: {e}")
    client_email = invoice_dict["client"].get("email")
    if client_email:
        print(f"📧 Email was sent to {client_email}. Returning success message.")
        return {
            "status": "success",
            "message": f"Invoice {invoice_id} successfully finalized and emailed to {client_email}.",
        }
    return FileResponse(
        path=file_path, filename=output_filename, media_type="application/pdf"
    )
