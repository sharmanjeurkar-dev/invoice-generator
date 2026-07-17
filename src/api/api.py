import asyncio
import os
import re
import sys
import uuid
from typing import List, Optional

import anyio
import asyncpg  # asyncpg used
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from mangum import Mangum
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel
from starlette.background import BackgroundTask

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from intelligence.llm.llma_service import generate_json_for_invoice_from_prompt
from src.document.invoice_storage import (
    download_invoice_pdf,
    upload_invoice_pdf,
)
from src.document.Pdf_generator import generate_invoice_pdf


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
    gst: Optional[float] = 0
    total: float


class PromptRequestModel(BaseModel):
    prompt: str
    user_id: str
    user_name: Optional[str] = "User"


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
    title="Ledger",
    description="Internal microservice for invoice generator",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://ledgerai-smoky.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Email-Status", "Content-Disposition"],
)

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
PDF_SEMAPHORE = asyncio.Semaphore(3)
handler = Mangum(app=app)


@app.post("/api/firms/{firm_id}/users/{target_user_id}/approve")
async def approve_user(firm_id: str, target_user_id: str):
    try:
        if firm_id and target_user_id:
            conn = await asyncpg.connect(DB_URL)
            update = await conn.fetchrow(
                "UPDATE profiles "
                "SET status = 'approved' "
                "WHERE firm_id = $1::uuid AND id = $2::uuid "
                "RETURNING status;",
                (firm_id, target_user_id),
            )

        if update and update["status"] == "approved":
            print(f"✅ User {target_user_id} approved")
            return {"status": "success", "message": "User approved"}
        else:
            print("⚠️ User couldn't be updated (IDs might not match)")
            return {"status": "error", "message": "Could not update user."}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/firms/{firm_id}/team")
async def get_users(firm_id: str):
    try:
        if firm_id:
            print("Opened firm admin dashboard and loading all the users")
            conn = await asyncpg.connect(DB_URL)
            users_pending = await conn.fetch(
                "SELECT id, full_name, email, role, status FROM profiles WHERE firm_id = $1::uuid",
                firm_id,
            )
            await conn.close()
            if users_pending:
                return [dict(row) for row in users_pending]
        return []

    except Exception as e:
        print(f"Error couldnt load users: {e}")
        return []


@app.get("/api/firms/{firm_id}/get-next-invoice-id")
async def get_next_invoice_id(firm_id: str):
    try:
        # asyncpg used
        conn = await asyncpg.connect(DB_URL)
        # asyncpg used
        result = await conn.fetchrow(
            """
            UPDATE firm_settings 
            SET next_invoice_number = next_invoice_number + 1 
            WHERE id = $1::uuid 
            RETURNING next_invoice_number - 1, firm_name;
            """,
            firm_id,
        )

        if result:
            next_val = result[0]
            firm_name = result[1] or "INV"
        else:
            # Fallback if a brand new user hasn't saved their settings yet
            next_val = 1
            firm_name = "Unknown Firm"

        # asyncpg used
        await conn.close()

        words = firm_name.strip().split()
        if len(words) >= 2:
            prefix = (words[0][0] + words[1][0]).upper()
        elif len(words) == 1:
            prefix = words[0][:3].upper()
        else:
            prefix = "INV"

        formatted_number = str(next_val).zfill(3)

        # Injects -INV- between the firm prefix and the number
        return {"invoice_id": f"{prefix}-INV-{formatted_number}"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/firms/{firm_id}/prompt-to-invoice", response_model=None)
async def prompt_to_invoice_generator(firm_id: str, response: PromptRequestModel):
    invoice_id = str(uuid.uuid4())[:8]
    expense_id = str(uuid.uuid4())[:8]
    prompt = str(response.prompt)
    user_id = response.user_id

    client_directory_text = ""
    print(f"🔍 DEBUG: API called with firm_id: {firm_id}")
    try:
        # asyncpg used
        conn = await asyncpg.connect(DB_URL, statement_cache_size=0)

        # asyncpg used
        clients = await conn.fetch(
            """
            SELECT name, address_line1, address_line2, address_line3 
            FROM clients 
            WHERE firm_id = $1::uuid 
            AND (
                $2 ILIKE '%' || name || '%'  -- Checks if the client's name is inside the prompt
                OR name ILIKE '%' || $2 || '%' 
            )
            UNION
            SELECT name, address_line1, address_line2, address_line3 
            FROM clients 
            WHERE firm_id = $1::uuid 
            ORDER BY name 
            LIMIT 50; 
            """,
            firm_id,
            prompt,  # Pass the raw user text directly to PostgreSQL!
        )
        print(f"🔍 DEBUG: Found {len(clients)} clients for this firm.")
        if clients:
            directory_list = []
            for c in clients:
                name = c[0]
                l1 = c[1] if c[1] else ""
                l2 = c[2] if c[2] else ""
                full_addr = f"{l1}, {l2}".strip(", ")

                if full_addr:
                    directory_list.append(f"- {name}: {full_addr}")

            client_directory_text = (
                "\n\n<database_context>\n"
                "KNOWN CLIENT DIRECTORY:\n"
                + "\n".join(directory_list)
                + "\n</database_context>\n"
                "SYSTEM RULE: If the requested client is in the <database_context> above, you MUST extract their exact address for the JSON."
            )

        # asyncpg used
        await conn.close()
    except Exception as e:
        print(f"⚠️ Could not fetch client directory: {e}")
        pass

    email_enforcement = (
        "\n\n<email_extraction_rule>\n"
        "If the user provides an email address anywhere in their request, you MUST extract it and place it in the 'client.email' field of your JSON response. Do not leave it null if an email is present.\n"
        "</email_extraction_rule>"
    )
    financial_enforcement = (
        "\n\n<financial_calculation_rule>\n"
        "By default, set 'gst' to 0.0 and ensure 'total' equals 'subtotal'. ONLY calculate and add GST if the user explicitly asks for it (e.g., 'with GST' or 'add 18% tax').\n"
        "</financial_calculation_rule>"
    )
    enriched_prompt = (
        prompt + client_directory_text + email_enforcement + financial_enforcement
    )
    print("🧠 Sending prompt + client directory to Pass 1...")

    try:
        llm_response = await anyio.to_thread.run_sync(
            generate_json_for_invoice_from_prompt, enriched_prompt
        )
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
            try:
                conn = await asyncpg.connect(DB_URL, statement_cache_size=0)

                # Use fetchrow and RETURNING to see if it actually inserted
                inserted_row = await conn.fetchrow(
                    """
                    INSERT INTO clients 
                    (firm_id, created_by, name, address_line1, address_line2, address_line3) 
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6)
                    ON CONFLICT DO NOTHING
                    RETURNING name;
                    """,
                    firm_id,
                    user_id,
                    client_name,
                    line1,
                    line2,
                    line3,
                )

                if inserted_row:
                    print(f"✅ Successfully learned a new client: {client_name}!")
                else:
                    print(f"🔄 Used existing client profile for: {client_name}")

                await conn.close()
            except Exception as e:
                print(f"⚠️ Failed to auto-save client background task: {e}")

        print("✅ Validating AI output structure...")
        try:
            validating_payload = InvoicePayloadModel(**llm_response["data"])
        except Exception as e:
            print(f"Validation Error: {e}")
            raise HTTPException(status_code=500, detail="Invalid format generated.")

        invoice_dict = validating_payload.model_dump()

        invoice_id = invoice_dict.get("invoice_number", "")
        if (
            not invoice_id
            or invoice_id == "."
            or len(invoice_id) <= 2
            or invoice_id == "PENDING-ID"
        ):
            print("⚠️ AI sent PENDING-ID! Fetching official ID from database...")

            safe_id_data = await get_next_invoice_id(firm_id)

            # If the database errored out, we catch it gracefully
            if "error" in safe_id_data:
                print(f"🚨 DB Error caught in interceptor: {safe_id_data['error']}")
                invoice_id = f"SYS-INV-{str(uuid.uuid4())[:3]}"
            else:
                # Successfully grabs PL-INV-002
                invoice_id = safe_id_data["invoice_id"]

            invoice_dict["invoice_number"] = invoice_id

        inv_name = invoice_dict["client"]["name"]

        safe_inv_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", inv_name.strip())

        # Now it will be Autobahn_Trucking_PL-INV-001.pdf
        output_filename = f"{safe_inv_name}_{invoice_id}.pdf"

        address_data = invoice_dict["client"]["address"]
        for key in ["line1", "line2", "line3"]:
            if address_data.get(key) is None:
                address_data[key] = ""

        print("🖨️  Sending AI data to Playwright engine...")

        try:
            print("🖨️  Fetching Firm Settings and sending data to Playwright engine...")

            # asyncpg used
            conn = await asyncpg.connect(DB_URL, statement_cache_size=0)

            # asyncpg used
            firm_data_record = await conn.fetchrow(
                "SELECT * FROM firm_settings WHERE id = $1::uuid", firm_id
            )

            # asyncpg used
            if not firm_data_record:
                firm_data = {"firm_name": "Unknown Firm"}
            else:
                firm_data = dict(firm_data_record)

            # asyncpg used
            await conn.close()

            async with PDF_SEMAPHORE:
                await anyio.to_thread.run_sync(
                    generate_invoice_pdf,
                    invoice_dict,
                    firm_data,
                    response.user_name,
                    output_filename,
                )
        except Exception as e:
            print(f"PDF Generation error {e}")
            raise HTTPException(status_code=500, detail="Pdf couldnt be generated")

        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
        output_dir = "/tmp" if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else project_root
        file_path = os.path.join(output_dir, output_filename)
        email_status_msg = None

        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=500, detail="PDF was not created successfully"
            )

        invoice_id_for_storage = invoice_dict.get("invoice_number", "INV-UNKNOWN")
        try:
            storage_path = upload_invoice_pdf(
                firm_id, invoice_id_for_storage, file_path
            )
            print(f"☁️  Invoice PDF persisted to storage: {storage_path}")
        except Exception as e:
            # Don't fail the whole request over this — the user still gets
            # their PDF/email today, they just won't be able to "resend"
            # this specific invoice later without regenerating it.
            print(f"⚠️ Failed to upload invoice PDF to storage: {e}")
            storage_path = output_filename

        if invoice_dict["client"].get("email"):
            target_email = invoice_dict["client"]["email"]
            client_name = invoice_dict["client"]["name"]

            # 👇 1. Extract the sender's email from the firm_data you fetched earlier
            sender_email = firm_data.get("email_sender")

            # 👇 THE FIX: explicitly pass the parent environment. Relying on
            # implicit inheritance was likely the actual cause of emails
            # silently using wrong/missing credentials in Lambda — local
            # subprocess spawning and Lambda's execution environment don't
            # always behave identically here.
            server_params = StdioServerParameters(
                command="python",
                args=["src/intelligence/tools/email_mcp_service.py"],
                env=dict(os.environ),
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
                                "sender_email": sender_email,
                            },
                        )
                        # 👇 THE FIX: previously we set email_status_msg
                        # unconditionally right after the call completed,
                        # regardless of what the tool actually reported. The
                        # tool returns an "Error: ..." STRING on failure
                        # rather than raising — so a completed call is NOT
                        # the same as a successful send. Check the content.
                        result_text = "".join(
                            block.text
                            for block in result.content
                            if hasattr(block, "text")
                        )
                        print(f"📧 MCP tool result: {result_text}")

                        if result_text.startswith("Success"):
                            email_status_msg = target_email
                        else:
                            print(f"⚠️ Email send failed: {result_text}")
            except Exception as e:
                print(f"⚠️ MCP Connection Failed: {e}")

        header = {}
        if email_status_msg:
            header["X-Email-Status"] = email_status_msg

        print("💾 Upserting EARNING to PostgreSQL ledger...")
        try:
            # asyncpg used
            conn = await asyncpg.connect(DB_URL, statement_cache_size=0)

            services_list = invoice_dict.get("services", [])
            service_strings = [
                srv.get("details", "Unnamed Service") for srv in services_list
            ]
            detailed_description = "Services: " + ", ".join(service_strings)
            safe_total = invoice_dict.get("total") or 0.0

            invoice_id = invoice_dict.get("invoice_number", "INV-UNKNOWN")

            # asyncpg used
            await conn.execute(
                """
                INSERT INTO firm_financials 
                (firm_id, created_by, transaction_type, amount, party_name, reference_file, description, invoice_id, created_at) 
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, NOW())
                ON CONFLICT (invoice_id) 
                DO UPDATE SET 
                    amount = EXCLUDED.amount,
                    description = EXCLUDED.description,
                    created_by = EXCLUDED.created_by,
                    reference_file = EXCLUDED.reference_file,
                    created_at = CURRENT_TIMESTAMP;
                """,
                firm_id,
                user_id,
                "EARNING",
                safe_total,
                invoice_dict["client"]["name"],
                storage_path,
                detailed_description,
                invoice_id,
            )
            print(f"✅ PostgreSQL record {invoice_id} upserted successfully!")

        except Exception as e:
            print(f"⚠️ Database Error: {e}")

        # asyncpg used
        await conn.close()

        client_email = invoice_dict["client"].get("email")
        if client_email:
            if os.path.exists(file_path):
                os.remove(file_path)
            return {
                "status": "success",
                "message": f"Invoice {invoice_id} successfully finalized and emailed to {client_email}.",
            }
        return FileResponse(
            path=file_path,
            filename=output_filename,
            media_type="application/pdf",
            background=BackgroundTask(os.remove, file_path),
        )

    # --- LOG_EXPENSE MODE ---
    elif action == "log_expense":
        # asyncpg used
        conn = await asyncpg.connect(DB_URL, statement_cache_size=0)

        # asyncpg used
        result = await conn.fetchrow(
            """
            UPDATE firm_settings 
            SET next_expense_number = next_expense_number + 1 
            WHERE id = $1::uuid 
            RETURNING next_expense_number - 1, firm_name;
            """,
            firm_id,
        )

        if result:
            next_val = result[0]
            firm_name = result[1] or "EXP"

            # Generate the prefix
            words = firm_name.strip().split()
            if len(words) >= 2:
                prefix = (words[0][0] + words[1][0]).upper()
            elif len(words) == 1:
                prefix = words[0][:3].upper()
            else:
                prefix = "EXP"

            expense_id = f"{prefix}-EXP-{str(next_val).zfill(3)}"
        else:
            # Fallback just in case something goes wildly wrong
            expense_id = f"EXP-UNKNOWN-{str(uuid.uuid4())[:4]}"

        print("💾 Logging EXPENSE to PostgreSQL...")

        # asyncpg used
        await conn.execute(
            """
                INSERT INTO firm_financials(
                firm_id, created_by, transaction_type, amount, party_name, description, invoice_id, created_at) 
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, NOW())
                """,
            firm_id,
            user_id,
            "EXPENSE",
            float(ai_json.get("amount", 0.0)),
            ai_json.get("vendor_name", "Unknown Vendor"),
            ai_json.get("description", "Firm Expense"),
            expense_id,
        )

        # asyncpg used
        await conn.close()
        return {
            "status": "success",
            "message": f"Successfully logged an expense of ₹{ai_json['amount']} to {ai_json['vendor_name']}.",
        }

    # --- REPORT_GENERATION MODE ---
    elif action == "analyze_financials":
        print("📊 Generating Financial Report...")
        try:
            # asyncpg used
            conn = await asyncpg.connect(DB_URL, statement_cache_size=0)

            # asyncpg used
            time_rows = await conn.fetch(
                """
                SELECT transaction_type, amount, party_name, created_at 
                FROM firm_financials 
                WHERE firm_id = $1::uuid 
                ORDER BY created_at DESC;
                """,
                firm_id,
            )

            # asyncpg used
            client_rows = await conn.fetch(
                """
                SELECT TO_CHAR(created_at, 'Mon YYYY'), COALESCE(party_name, 'Unknown'), SUM(amount) 
                FROM firm_financials 
                WHERE firm_id = $1::uuid AND transaction_type = 'EARNING' 
                GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 50;
            """,
                firm_id,
            )

            # asyncpg used
            expense_rows = await conn.fetch(
                """
                SELECT TO_CHAR(created_at, 'Mon YYYY'), COALESCE(party_name, 'General/Unknown'), SUM(amount) 
                FROM firm_financials 
                WHERE firm_id = $1::uuid AND transaction_type = 'EXPENSE' 
                GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 50;
            """,
                firm_id,
            )

            # asyncpg used
            await conn.close()

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
                "[SYSTEM NOTE: RAW FINANCIAL DATA]\n"
                f"<user_request>\n{prompt}\n</user_request>\n\n"
                "<instruction>\n"
                "Filter the summaries below based on the user's requested timeframe and build the requested charts.\n"
                "</instruction>\n\n"
                f"<financial_data>\n{data_string}\n</financial_data>"
            )

            print("🧠 Sending raw data back to AI for analysis...")
            second_llm_response = await anyio.to_thread.run_sync(
                generate_json_for_invoice_from_prompt, analyst_prompt
            )

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
        # --- UPDATE CLIENT MODE ---
    elif action == "update_client":
        client_name = ai_json.get("client_name")
        new_address = ai_json.get("new_address", {})

        if not client_name:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Client name is missing for the update.",
                }
            )

        line1 = new_address.get("line1", "")
        line2 = new_address.get("line2", "")
        line3 = new_address.get("line3", "")

        print(f"🔄 Attempting to update client: {client_name}")

        try:
            conn = await asyncpg.connect(DB_URL, statement_cache_size=0)

            # ILIKE makes the search case-insensitive (e.g., "sanjay" matches "Sanjay")
            existing_client = await conn.fetchrow(
                "SELECT id FROM clients WHERE firm_id = $1::uuid AND name ILIKE $2",
                firm_id,
                client_name,
            )

            if existing_client:
                await conn.execute(
                    """
                    UPDATE clients 
                    SET address_line1 = $1, address_line2 = $2, address_line3 = $3 
                    WHERE firm_id = $4::uuid AND name ILIKE $5
                    """,
                    line1,
                    line2,
                    line3,
                    firm_id,
                    client_name,
                )
                msg = f"Successfully updated the address for {client_name} in your directory."
            else:
                msg = f"I couldn't find a client named '{client_name}' in your directory to update."

            await conn.close()
            return JSONResponse(content={"status": "success", "message": msg})

        except Exception as e:
            print(f"⚠️ Database Error during client update: {e}")
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Database error while updating the client.",
                }
            )

    # --- RESEND INVOICE MODE ---
    elif action == "resend_invoice":
        invoice_id_to_resend = ai_json.get("invoice_id")
        target_emails = ai_json.get("target_emails") or []

        if not invoice_id_to_resend or not target_emails:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "I need both the invoice ID and at least one recipient email to resend an invoice.",
                }
            )

        print(
            f"🔁 Resend requested for invoice {invoice_id_to_resend} to {target_emails}"
        )

        try:
            # asyncpg used
            conn = await asyncpg.connect(DB_URL, statement_cache_size=0)

            # asyncpg used
            record = await conn.fetchrow(
                """
                SELECT reference_file, party_name
                FROM firm_financials
                WHERE firm_id = $1::uuid AND invoice_id = $2 AND transaction_type = 'EARNING'
                """,
                firm_id,
                invoice_id_to_resend,
            )

            # asyncpg used
            firm_data_record = await conn.fetchrow(
                "SELECT * FROM firm_settings WHERE id = $1::uuid", firm_id
            )
            firm_data = dict(firm_data_record) if firm_data_record else {}

            # asyncpg used
            await conn.close()

            if not record:
                return JSONResponse(
                    content={
                        "status": "error",
                        "message": f"I couldn't find an invoice with ID {invoice_id_to_resend} for this firm.",
                    }
                )

            storage_path = record["reference_file"]
            client_name = record["party_name"] or "Client"
            sender_email = firm_data.get("email_sender")

            if not storage_path:
                return JSONResponse(
                    content={
                        "status": "error",
                        "message": f"Invoice {invoice_id_to_resend} exists but has no stored PDF to resend — it may predate this feature.",
                    }
                )

            output_dir = "/tmp" if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "."
            local_pdf_path = os.path.join(
                output_dir, f"resend_{invoice_id_to_resend}.pdf"
            )

            try:
                download_invoice_pdf(storage_path, local_pdf_path)
            except Exception as e:
                print(f"⚠️ Failed to download invoice from storage: {e}")
                return JSONResponse(
                    content={
                        "status": "error",
                        "message": f"I found the invoice record but couldn't retrieve the stored PDF: {str(e)}",
                    }
                )

            server_params = StdioServerParameters(
                command="python",
                args=["src/intelligence/tools/email_mcp_service.py"],
                env=dict(os.environ),
            )

            sent_to = []
            failed_to = []

            try:
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        # One session, one tool call per recipient — avoids
                        # spinning up a fresh subprocess per email.
                        for recipient in target_emails:
                            try:
                                result = await session.call_tool(
                                    "send_invoice_on_email",
                                    arguments={
                                        "target_email": recipient,
                                        "pdf_file_path": local_pdf_path,
                                        "client_name": client_name,
                                        "sender_email": sender_email,
                                    },
                                )
                                result_text = "".join(
                                    block.text
                                    for block in result.content
                                    if hasattr(block, "text")
                                )
                                print(
                                    f"📧 MCP tool result for {recipient}: {result_text}"
                                )

                                if result_text.startswith("Success"):
                                    sent_to.append(recipient)
                                else:
                                    print(
                                        f"⚠️ Email send failed for {recipient}: {result_text}"
                                    )
                                    failed_to.append(recipient)
                            except Exception as e:
                                print(f"⚠️ Failed to send to {recipient}: {e}")
                                failed_to.append(recipient)
            except Exception as e:
                print(f"⚠️ MCP Connection Failed: {e}")
                return JSONResponse(
                    content={
                        "status": "error",
                        "message": "Failed to connect to the email service.",
                    }
                )
            finally:
                if os.path.exists(local_pdf_path):
                    os.remove(local_pdf_path)

            if sent_to and not failed_to:
                msg = f"Invoice {invoice_id_to_resend} was successfully resent to {', '.join(sent_to)}."
            elif sent_to and failed_to:
                msg = (
                    f"Invoice {invoice_id_to_resend} was sent to {', '.join(sent_to)}, "
                    f"but failed for {', '.join(failed_to)}."
                )
            else:
                msg = f"Failed to resend invoice {invoice_id_to_resend} to anyone."

            return JSONResponse(
                content={"status": "success" if sent_to else "error", "message": msg}
            )

        except Exception as e:
            print(f"⚠️ Database Error during resend: {e}")
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Database error while looking up the invoice to resend.",
                }
            )


@app.get("/api/firms/{firm_id}/settings")
async def get_settings(firm_id: str):
    try:
        # asyncpg used
        conn = await asyncpg.connect(DB_URL, statement_cache_size=0)

        # asyncpg used
        settings = await conn.fetchrow(
            "SELECT * FROM firm_settings WHERE id = $1::uuid", firm_id
        )

        # asyncpg used
        await conn.close()

        if not settings:
            return {}
        # asyncpg used
        return dict(settings)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/firms/{firm_id}/settings")
async def update_settings(firm_id: str, settings: FirmSettings):
    try:
        # asyncpg used
        conn = await asyncpg.connect(DB_URL, statement_cache_size=0)

        # asyncpg used
        await conn.execute(
            """
            INSERT INTO firm_settings 
            (id, firm_name, address_line1, address_line2, email_sender, bank_name, account_number, ifsc_code, logo_url, pan_number, contact_number, contact_email, bank_branch, updated_at) 
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
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
        )

        # asyncpg used
        await conn.close()

        return {
            "status": "success",
            "message": f"Settings for firm {firm_id} updated successfully.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
