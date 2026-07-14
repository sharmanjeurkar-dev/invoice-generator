import os
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader

# Import the modern Playwright engine instead of WeasyPrint
from playwright.sync_api import sync_playwright


def generate_invoice_pdf(
    invoice_dict: dict,
    firm_dict: dict,
    user_name: str,
    output_filename="invoice_output.pdf",
):

    due_duration = 22
    today = datetime.now()
    due_date = today + timedelta(due_duration)

    invoice_dict["invoice_number"] = invoice_dict.get("invoice_number") or "INV-UNKNOWN"
    invoice_dict["invoice_date"] = invoice_dict.get("invoice_date") or today.strftime(
        "%d/%m/%Y"
    )
    invoice_dict["due_date"] = invoice_dict.get("due_date") or due_date.strftime(
        "%d/%m/%Y"
    )

    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))

    # Keeping your existing template directory structure
    template_dir = os.path.join(project_root, "templates")
    env = Environment(loader=FileSystemLoader(template_dir))

    # Load your dynamic HTML file (ensure the filename matches what is in your templates folder)
    template = env.get_template("invoice.html")

    rendered_html = template.render(
        invoice=invoice_dict, firm=firm_dict, user_name=user_name
    )

    output_path = os.path.join(project_root, output_filename)

    print("🌐 Spinning up headless browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--no-sandbox", "--disable-dev-shm-usage", "--single-process"]
        )
        page = browser.new_page()

        # Playwright renders the injected HTML string
        page.set_content(rendered_html, wait_until="networkidle")

        page.pdf(
            path=output_path,
            format="A4",
            print_background=True,
            margin={"top": "40px", "right": "40px", "bottom": "40px", "left": "40px"},
        )

        browser.close()

    print(f"📄 Modern CSS PDF generated at: {output_path}")


if __name__ == "__main__":
    # A quick mock test to ensure it runs locally if executed directly
    test_invoice = {
        "client": {"name": "Test Client"},
        "services": [{"details": "Test Service", "amount": 1000, "qty": 1}],
        "subtotal": 1000,
        "gst": 180,
        "total": 1180,
    }
    test_firm = {
        "firm_name": "Test Firm LLC",
        "logo_url": "https://via.placeholder.com/150",
        "bank_name": "Test Bank",
        "account_number": "123456789",
    }
    generate_invoice_pdf(test_invoice, test_firm, "playwright_test.pdf")
