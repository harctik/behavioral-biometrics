import os
import re
import asyncio
from playwright.async_api import async_playwright

svg_dir = r"d:\Behavior-Based-Authentication-main\studvisor_diagrams"
output_pdf = os.path.join(svg_dir, "studvisor_chapter3_diagrams.pdf")

svg_files = [
    "fig_3_1_use_case.svg",
    "fig_3_2_er_diagram.svg",
    "fig_3_3_dfd_l0.svg",
    "fig_3_4_dfd_l1.svg",
    "fig_3_5_dfd_l2.svg",
    "fig_3_6_sfd_request_lifecycle.svg",
]

async def render_pdf():
    print("Reading SVGs for unified PDF...")
    svg_contents = []
    for filename in svg_files:
        filepath = os.path.join(svg_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                content = re.sub(r'<\?xml[^>]*\?>', '', content)
                svg_contents.append(content.strip())
                print(f"  Loaded {filename}")
        else:
            print(f"  Warning: {filename} not found!")

    # Build print-friendly HTML
    html_content = """<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Studvisor Diagrams Print</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
        <style>
            @page {
                size: A4 landscape;
                margin: 0;
            }
            body {
                margin: 0;
                padding: 0;
                background-color: #FFFFFF;
            }
            .page {
                width: 297mm;
                height: 210mm;
                page-break-after: always;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
            }
            .page svg {
                width: 100%;
                height: 100%;
            }
        </style>
    </head>
    <body>
    """

    for svg in svg_contents:
        html_content += f'<div class="page">{svg}</div>\n'

    html_content += """
    </body>
    </html>
    """

    temp_html = os.path.join(svg_dir, "print_temp.html")
    with open(temp_html, "w", encoding="utf-8") as f_temp:
        f_temp.write(html_content)

    print("Launching Playwright for PDF export...")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        url = f"file:///{temp_html.replace(os.sep, '/')}"
        
        try:
            await page.goto(url, wait_until="load", timeout=20000)
            # Wait for 2 seconds for Google Fonts to download/render
            await page.wait_for_timeout(2000)
            
            print(f"Printing unified PDF to {output_pdf}...")
            await page.pdf(path=output_pdf, format="A4", landscape=True, print_background=True, timeout=20000)
            print("PDF printed successfully!")
        except Exception as e:
            print(f"Error printing PDF: {e}")
            try:
                print("Attempting fallback PDF print...")
                await page.pdf(path=output_pdf, format="A4", landscape=True, print_background=True, timeout=10000)
                print("Fallback PDF printed successfully!")
            except Exception as err:
                print(f"Critical PDF failure: {err}")
        
        await browser.close()
        
    # Cleanup temp html
    if os.path.exists(temp_html):
        os.remove(temp_html)
        print("Cleaned up temporary HTML file.")

if __name__ == "__main__":
    asyncio.run(render_pdf())
