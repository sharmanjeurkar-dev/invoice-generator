import base64
import os
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader

# Import the modern Playwright engine instead of WeasyPrint
from playwright.sync_api import sync_playwright


def generate_invoice_pdf(invoice_data, output_filename="invoice_output.pdf"):
    due_duration = 22
    today = datetime.now()
    due_date = today + timedelta(due_duration)
    today = today.strftime("%d/%m/%Y")
    due_date = due_date.strftime("%d/%m/%Y")
    invoice_data["invoice_number"] = invoice_data.get("invoice_number") or "AUT-001"
    invoice_data["invoice_date"] = invoice_data.get("invoice_date") or today
    invoice_data["due_date"] = invoice_data.get("due_date") or due_date

    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    template_dir = os.path.join(project_root, "templates")

    logo_path = os.path.join(template_dir, "logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode("utf-8")
        invoice_data["logo_data"] = f"data:image/png;base64,{logo_b64}"
    else:
        invoice_data["logo_data"] = ""

    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("invoice.html")

    rendered_html = template.render(**invoice_data)
    output_path = os.path.join(project_root, output_filename)

    print("🌐 Spinning up headless browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        page.set_content(rendered_html)

        page.pdf(
            path=output_path,
            format="A4",
            print_background=True,
            margin={"top": "40px", "right": "40px", "bottom": "40px", "left": "40px"},
        )

        browser.close()

    print(f"📄 Modern CSS PDF generated at: {output_path}")


if __name__ == "__main__":
    test_data = {
        "client": {"name": "Test Client"},
        "services": [{"details": "Test Service", "amount": 1000}],
        "subtotal": 1000,
        "gst": 0.18,
        "total": 1180,
    }
    generate_invoice_pdf(test_data, "playwright_test.pdf")
