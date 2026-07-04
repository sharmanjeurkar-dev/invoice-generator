import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Pentacles Email Service")

load_dotenv()


@mcp.tool()
def send_invoice_on_email(
    target_email: str, pdf_file_path: str, client_name: str
) -> str:
    sender_email = os.getenv("SENDER_EMAIL")
    app_password = os.getenv("APP_PASSWORD")

    if not os.path.exists(pdf_file_path):
        return "ERROR FILE NOT FOUND"

    try:
        msg = EmailMessage()
        msg["Subject"] = f"Your legal invoice from Pentacle legal firm: {client_name}"
        msg["From"] = sender_email
        msg["To"] = target_email
        msg.set_content(
            f"Hello {client_name},\n\nPlease find your generated invoice attached.\n\nBest,\nPentacles Legal"
        )

        with open(pdf_file_path, "rb") as f:
            pdf_data = f.read()
            pdf_name = os.path.basename(pdf_file_path)
            msg.add_attachment(
                pdf_data, maintype="application", subtype="pdf", filename=pdf_name
            )
            print(f"📧 [MCP Server] Executing SMTP transfer to {target_email}...")

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(user=sender_email, password=app_password)
                smtp.send_message(msg)
            return f"Success: Email delivered to {target_email}"
    except Exception as e:
        return f"Error: Failed to send email - {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
