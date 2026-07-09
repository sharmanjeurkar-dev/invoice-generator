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


# invice
class AddressModel(BaseModel):
    line1: str
    line2: Optional[str] = None
    line3: Optional[str] = None


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

    client_directory_text = ""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        # Adjust 'clients' and the column names based on your actual Supabase table!
        cursor.execute(
            "SELECT name, address_line1, address_line2 FROM clients LIMIT 50;"
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
        print(f"⚠️ Could not fetch client directory (Table might not exist yet): {e}")
        pass  # Fail silently so the app doesn't crash if the table is empty

    # Glue the directory to the user's prompt!
    enriched_prompt = prompt + client_directory_text
    print("🧠 Sending prompt + client directory to Pass 1...")
    llm_response = generate_json_for_inbvoice_from_prompt(enriched_prompt)

    action = llm_response.get("action")

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
    ai_json = llm_response.get("data", {})
    if ai_json.get("status") == "clarification":
        print("🟡 AI requested clarification (JSON). Sending back to UI.")
        return JSONResponse(
            content={"status": "clarification", "message": ai_json["message"]}
        )
    action = ai_json.get("action", "draft_invoice")
    # DRAFT mode
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

        client_data = ai_json.get("client", {})
        client_name = client_data.get("name")
        address = client_data.get("address", {})
        line1 = address.get("line1", "")
        line2 = address.get("line2", "")
        line3 = address.get("line3", "")

        if client_name and line1:
            print(f"🔍 Checking if client '{client_name}' is in the directory...")
            try:
                conn = psycopg2.connect(DB_URL)
                cursor = conn.cursor()

                # Using PostgreSQL 'ON CONFLICT DO NOTHING' to safely ignore duplicates
                cursor.execute(
                    """
                    INSERT INTO clients (name, address_line1, address_line2,address_line3) 
                    VALUES (%s, %s, %s, %s) 
                    ON CONFLICT (name) DO NOTHING;
                """,
                    (client_name, line1, line2, line3),
                )

                # If a new row was inserted, rowcount will be 1
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
            raise HTTPException(
                status_code=500, detail="PDF was not created successfully"
            )

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
            conn = psycopg2.connect(DB_URL)
            cursor = conn.cursor()

            services_list = invoice_dict.get("services", [])
            service_strings = [
                srv.get("details", "Unnamed Service") for srv in services_list
            ]
            detailed_description = "Services: " + ", ".join(service_strings)
            safe_total = invoice_dict.get("total") or 0.0

            invoice_id = invoice_dict.get("invoice_number", "INV-UNKNOWN")

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

    # LOG_EXPENSE Mode
    elif action == "log_expense":
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        cursor.execute("SELECT nextval('expense_number_seq');")
        next_val = cursor.fetchone()[0]
        expense_id = f"EXP-{next_val}"
        print(f"🏷️ Generated sequential ID: {expense_id}")

        print("💾 Logging EXPENSE to PostgreSQL...")
        cursor.execute(
            """
                INSERT INTO firm_financials(
                transaction_type, amount, party_name, description,invoice_id) 
                VALUES (%s, %s, %s, %s, %s)
                """,
            (
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

    # REPORT_GENERATION Mode
    elif action == "analyze_financials":
        print("📊 Generating Financial Report...")
        try:
            conn = psycopg2.connect(DB_URL)
            cursor = conn.cursor()

            timeframe = ai_json.get("timeframe", "all")

            cursor.execute("""
                SELECT TO_CHAR(created_at, 'Mon YYYY'), transaction_type, SUM(amount) 
                FROM firm_financials 
                GROUP BY 1, 2 ORDER BY MIN(created_at) DESC;
            """)
            time_rows = cursor.fetchall()

            cursor.execute("""
                SELECT TO_CHAR(created_at, 'Mon YYYY'), COALESCE(party_name, 'Unknown'), SUM(amount) 
                FROM firm_financials 
                WHERE transaction_type = 'EARNING' 
                GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 50;
            """)
            client_rows = cursor.fetchall()

            cursor.execute("""
                SELECT TO_CHAR(created_at, 'Mon YYYY'), COALESCE(party_name, 'General/Unknown'), SUM(amount) 
                FROM firm_financials 
                WHERE transaction_type = 'EXPENSE' 
                GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 50;
            """)
            expense_rows = cursor.fetchall()
            cursor.close()
            conn.close()

            data_string = (
                "--- OVERALL MONTHLY TRENDS ---\n"
                + " | ".join([f"{r[0]}: {r[1]} ₹{r[2]}" for r in time_rows])
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
                print("⚠️ AI failed to format the dashboard JSON correctly.")
                return JSONResponse(
                    content={
                        "status": "error",
                        "message": "The AI generated the insights but failed to format the dashboard correctly. Please try asking for fewer charts at a time.",
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

        # Inject the dynamic firm_id into the UPSERT statement
        cursor.execute(
            """
            INSERT INTO firm_settings 
            (id, firm_name, address_line1, address_line2, email_sender, bank_name, account_number, ifsc_code, logo_url, updated_at) 
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET 
                firm_name = EXCLUDED.firm_name,
                address_line1 = EXCLUDED.address_line1,
                address_line2 = EXCLUDED.address_line2,
                email_sender = EXCLUDED.email_sender,
                bank_name = EXCLUDED.bank_name,
                account_number = EXCLUDED.account_number,
                ifsc_code = EXCLUDED.ifsc_code,
                logo_url = EXCLUDED.logo_url,
                updated_at = NOW();
        """,
            (
                firm_id,  # <--- Dynamic ID inserted here
                settings.firm_name,
                settings.address_line1,
                settings.address_line2,
                settings.email_sender,
                settings.bank_name,
                settings.account_number,
                settings.ifsc_code,
                settings.logo_url,
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
