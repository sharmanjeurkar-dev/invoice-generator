import os
import uuid
from typing import List, Optional

import anyio
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel

from src.document.Pdf_generator import generate_invoice_pdf
from tests.test_baseline_inference import generate_json_for_inbvoice_from_prompt


# invoice
class AddressModel(BaseModel):
    line1: str
    line2: Optional[str] = None
    line3: Optional[str] = None


class ClientModel(BaseModel):
    name: str
    address: AddressModel
    email: Optional[str] = None


class ServiceModel(BaseModel):
    category: str = "Legal Professional Fees"
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
    user_id: str  # 👈 Added user_id to accept it from the frontend


# Firm settings
class FirmSettings(BaseModel):
    firm_name: str
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    email_sender: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    logo_url: Optional[str] = None
    pan_number: Optional[str] = None
    contact_number: Optional[str] = None
    contact_email: Optional[str] = None
    bank_branch: Optional[str] = None


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
    expose_headers=["X-Email-Status,Content-Disposition"],
)

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")


@app.get("/api/firms/{firm_id}/get-next-invoice-id")
def get_next_invoice_id(firm_id: str):
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


@app.post("/api/firms/{firm_id}/prompt-to-invoice")
async def prompt_to_invoice_generator(firm_id: str, response: PromptRequestModel):
    invoice_id = str(uuid.uuid4())[:8]
    expense_id = str(uuid.uuid4())[:8]
    prompt = str(response.prompt)
    user_id = response.user_id  # 👈 Extract the user_id securely

    client_directory_text = ""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        # 👈 Added firm_id isolation to the client lookup!
        cursor.execute(
            "SELECT name, address_line1, address_line2 FROM clients WHERE firm_id = %s::uuid LIMIT 50;",
            (firm_id,),
        )
        clients = cursor.fetchall()

        if clients:
            # Format the data into a clean string for the LLM
            directory_list = [f"{c[0]}: {c[1]}, {c[2]}" for c in clients]
            client_directory_text = (
                "\n\n[SYSTEM NOTE: KNOWN CLIENT DIRECTORY]\n"
                + "\n".join(directory_list)
            )

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Could not fetch client directory: {e}")
        pass

    enriched_prompt = prompt + client_directory_text
    print("🧠 Sending prompt + client directory to Pass 1...")

    try:
        llm_response = generate_json_for_inbvoice_from_prompt(enriched_prompt)
    except Exception as e:
        print(f"LLM Error: {e}")
        raise HTTPException(status_code=500, detail="failed to generate Ai response")

    if llm_response["status"] == "clarification":
        print("🟡 AI requested clarification. Sending back to UI.")
        return JSONResponse(
            content={"status": "clarification", "message": llm_response["message"]}
        )

    ai_json = llm_response.get("data", {})
    if ai_json.get("status") == "clarification":
        return JSONResponse(
            content={"status": "clarification", "message": ai_json["message"]}
        )

    action = ai_json.get("action", "draft_invoice")

    # --- DRAFT INVOICE MODE ---
    if action == "draft_invoice":
        client_data = ai_json.get("client", {})
        address = client_data.get("address", {})

        if not address.get("line1"):
            print(
                "🛡️ Python caught a null address hallucination! Forcing clarification."
            )
            return JSONResponse(
                content={
                    "status": "clarification",
                    "message": "I don't have an address on file for this client. Could you please provide their full address?",
                }
            )

        client_name = client_data.get("name")
        line1 = address.get("line1", "")
        line2 = address.get("line2", "")
        line3 = address.get("line3", "")

        if client_name and line1:
            print(f"🔍 Auto-saving client '{client_name}' to directory...")
            try:
                conn = psycopg2.connect(DB_URL)
                cursor = conn.cursor()

                # 👈 Fixed query: Inserts into CLIENTS table instead of financials!
                cursor.execute(
                    """
                    INSERT INTO clients 
                    (firm_id, created_by, name, address_line1, address_line2, address_line3) 
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    (
                        firm_id,
                        user_id,
                        client_name,
                        line1,
                        line2,
                        line3,
                    ),
                )

                if cursor.rowcount > 0:
                    print(f"✅ Successfully learned a new client: {client_name}!")

                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                print(f"⚠️ Failed to auto-save client background task: {e}")

        print("✅ Validating AI output structure...")
        try:
            validating_payload = InvoicePayloadModel(**llm_response["data"])
        except Exception as e:
            print(f"Validation Error: {e}")
            raise HTTPException(status_code=500, detail="Invalid format generated.")

        invoice_dict = validating_payload.model_dump()
        inv_name = invoice_dict["client"]["name"]
        output_filename = f"{inv_name}_Invoice.pdf"
        address_data = invoice_dict["client"]["address"]
        for key in ["line1", "line2", "line3"]:
            if address_data.get(key) is None:
                address_data[key] = ""

        print("🖨️  Sending AI data to Playwright engine...")

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
            raise HTTPException(
                status_code=500, detail="PDF was not created successfully"
            )

        if invoice_dict["client"].get("email"):
            target_email = invoice_dict["client"]["email"]
            client_name = invoice_dict["client"]["name"]
            server_params = StdioServerParameters(
                command="python", args=["src/intelligence/tools/email_mcp_service.py"]
            )

            try:
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(
                            "send_invoice_on_email",
                            arguments={
                                "target_email": target_email,
                                "pdf_file_path": file_path,
                                "client_name": client_name,
                            },
                        )
                        email_status_msg = target_email
            except Exception as e:
                print(f"⚠️ MCP Connection Failed: {e}")

        header = {}
        if email_status_msg:
            header["X-Email-Status"] = email_status_msg

        print("💾 Upserting EARNING to PostgreSQL ledger...")
        try:
            conn = psycopg2.connect(DB_URL)
            cursor = conn.cursor()

            services_list = invoice_dict.get("services", [])
            service_strings = [
                srv.get("details", "Unnamed Service") for srv in services_list
            ]
            detailed_description = "Services: " + ", ".join(service_strings)
            safe_total = invoice_dict.get("total") or 0.0

            invoice_id = invoice_dict.get("invoice_number", "INV-UNKNOWN")

            # 👈 Injected firm_id and created_by into the financial record
            cursor.execute(
                """
                INSERT INTO firm_financials 
                (firm_id, created_by, transaction_type, amount, party_name, reference_file, description, invoice_id, created_at) 
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (invoice_id) 
                DO UPDATE SET 
                    amount = EXCLUDED.amount,
                    description = EXCLUDED.description,
                    reference_file = EXCLUDED.reference_file,
                    created_at = CURRENT_TIMESTAMP;
                """,
                (
                    firm_id,
                    user_id,
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
            return {
                "status": "success",
                "message": f"Invoice {invoice_id} successfully finalized and emailed to {client_email}.",
            }
        return FileResponse(
            path=file_path, filename=output_filename, media_type="application/pdf"
        )

    # --- LOG_EXPENSE MODE ---
    elif action == "log_expense":
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        cursor.execute("SELECT nextval('expense_number_seq');")
        next_val = cursor.fetchone()[0]
        expense_id = f"EXP-{next_val}"

        print("💾 Logging EXPENSE to PostgreSQL...")

        # 👈 Injected firm_id and created_by into the financial record
        cursor.execute(
            """
                INSERT INTO firm_financials(
                firm_id, created_by, transaction_type, amount, party_name, description, invoice_id, created_at) 
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, NOW())
                """,
            (
                firm_id,
                user_id,
                "EXPENSE",
                float(ai_json.get("amount", 0.0)),
                ai_json.get("vendor_name", "Unknown Vendor"),
                ai_json.get("description", "Firm Expense"),
                expense_id,
            ),
        )
        conn.commit()
        conn.close()
        return {
            "status": "success",
            "message": f"Successfully logged an expense of ₹{ai_json['amount']} to {ai_json['vendor_name']}.",
        }

    # --- REPORT_GENERATION MODE ---
    elif action == "analyze_financials":
        print("📊 Generating Financial Report...")
        try:
            conn = psycopg2.connect(DB_URL)
            cursor = conn.cursor()

            # 👈 Locked down to firm_id
            cursor.execute(
                """
                SELECT transaction_type, amount, party_name, created_at 
                FROM firm_financials 
                WHERE firm_id = %s::uuid 
                ORDER BY created_at DESC;
                """,
                (firm_id,),
            )
            time_rows = cursor.fetchall()

            # 👈 Locked down to firm_id
            cursor.execute(
                """
                SELECT TO_CHAR(created_at, 'Mon YYYY'), COALESCE(party_name, 'Unknown'), SUM(amount) 
                FROM firm_financials 
                WHERE firm_id = %s::uuid AND transaction_type = 'EARNING' 
                GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 50;
            """,
                (firm_id,),
            )
            client_rows = cursor.fetchall()

            # 👈 Locked down to firm_id
            cursor.execute(
                """
                SELECT TO_CHAR(created_at, 'Mon YYYY'), COALESCE(party_name, 'General/Unknown'), SUM(amount) 
                FROM firm_financials 
                WHERE firm_id = %s::uuid AND transaction_type = 'EXPENSE' 
                GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 50;
            """,
                (firm_id,),
            )
            expense_rows = cursor.fetchall()

            cursor.close()
            conn.close()

            data_string = (
                "--- OVERALL MONTHLY TRENDS ---\n"
                + " | ".join([f"{r[0]}: {r[2]} ₹{r[1]}" for r in time_rows])
                + "\n\n"
                + "--- EARNINGS BY CLIENT (Per Month) ---\n"
                + " | ".join([f"{r[0]} - {r[1]}: ₹{r[2]}" for r in client_rows])
                + "\n\n"
                + "--- EXPENSES BY CATEGORY (Per Month) ---\n"
                + " | ".join([f"{r[0]} - {r[1]}: ₹{r[2]}" for r in expense_rows])
            )

            analyst_prompt = (
                f"[SYSTEM NOTE: RAW FINANCIAL DATA]\n"
                f"USER'S SPECIFIC REQUEST: {prompt}\n\n"
                f"Here is the pre-aggregated database. Filter these summaries based on the user's requested timeframe and build the requested charts.\n\n"
                f"{data_string}"
            )

            print("🧠 Sending raw data back to AI for analysis...")
            second_llm_response = generate_json_for_inbvoice_from_prompt(analyst_prompt)

            if second_llm_response.get("status") == "clarification":
                return JSONResponse(
                    content={
                        "status": "error",
                        "message": "The AI generated the insights but failed to format the dashboard correctly.",
                    }
                )

            dashboard_json = second_llm_response.get("data", {})
            if "executive_summary" not in dashboard_json:
                dashboard_json["executive_summary"] = (
                    "Here is your requested financial dashboard."
                )

            return JSONResponse(content=dashboard_json)

        except Exception as e:
            print(f"Analyst Loop Error: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to analyze data: {str(e)}"
            )


@app.get("/api/firms/{firm_id}/settings")
async def get_settings(firm_id: str):
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("SELECT * FROM firm_settings WHERE id = %s::uuid", (firm_id,))
        settings = cursor.fetchone()

        cursor.close()
        conn.close()

        if not settings:
            return {}
        return settings

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/firms/{firm_id}/settings")
async def update_settings(firm_id: str, settings: FirmSettings):
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO firm_settings 
            (id, firm_name, address_line1, address_line2, email_sender, bank_name, account_number, ifsc_code, logo_url, pan_number, contact_number, contact_email, bank_branch, updated_at) 
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET 
                firm_name = EXCLUDED.firm_name,
                address_line1 = EXCLUDED.address_line1,
                address_line2 = EXCLUDED.address_line2,
                email_sender = EXCLUDED.email_sender,
                bank_name = EXCLUDED.bank_name,
                account_number = EXCLUDED.account_number,
                ifsc_code = EXCLUDED.ifsc_code,
                logo_url = EXCLUDED.logo_url,
                pan_number = EXCLUDED.pan_number,
                contact_number = EXCLUDED.contact_number,
                contact_email = EXCLUDED.contact_email,
                bank_branch = EXCLUDED.bank_branch,
                updated_at = NOW();
        """,
            (
                firm_id,
                settings.firm_name,
                settings.address_line1,
                settings.address_line2,
                settings.email_sender,
                settings.bank_name,
                settings.account_number,
                settings.ifsc_code,
                settings.logo_url,
                settings.pan_number,
                settings.contact_number,
                settings.contact_email,
                settings.bank_branch,
            ),
        )

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "status": "success",
            "message": f"Settings for firm {firm_id} updated successfully.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
