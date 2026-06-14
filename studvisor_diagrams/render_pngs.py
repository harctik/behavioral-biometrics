import os
import asyncio
from playwright.async_api import async_playwright

svg_dir = r"d:\Behavior-Based-Authentication-main\studvisor_diagrams"
output_dir = os.path.join(svg_dir, "high_res_pngs")
os.makedirs(output_dir, exist_ok=True)

svg_files = {
    "Figure_3_1_Use_Case": "fig_3_1_use_case.svg",
    "Figure_3_2_ER_Diagram": "fig_3_2_er_diagram.svg",
    "Figure_3_3_DFD_Level_0": "fig_3_3_dfd_l0.svg",
    "Figure_3_4_DFD_Level_1": "fig_3_4_dfd_l1.svg",
    "Figure_3_5_DFD_Level_2": "fig_3_5_dfd_l2.svg",
    "Figure_3_6_SFD_Request_Lifecycle": "fig_3_6_sfd_request_lifecycle.svg",
}

async def render_svgs():
    print("Launching Playwright Chromium...")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # Set viewport to A4 Landscape at 300 DPI: 3508 x 2480
        page = await browser.new_page(viewport={"width": 3508, "height": 2480})
        
        for name, filename in svg_files.items():
            svg_path = os.path.join(svg_dir, filename)
            if os.path.exists(svg_path):
                print(f"Rendering {filename} to {name}.png...")
                url = f"file:///{svg_path.replace(os.sep, '/')}"
                
                try:
                    await page.goto(url, wait_until="load", timeout=15000)
                    # Wait for 1.5 seconds for Google Fonts to download/render
                    await page.wait_for_timeout(1500)
                    
                    png_path = os.path.join(output_dir, f"{name}.png")
                    # Set screenshot timeout to 15 seconds
                    await page.screenshot(path=png_path, full_page=True, type="png", timeout=15000)
                    print(f"  Saved {png_path}")
                except Exception as e:
                    print(f"  Error rendering {filename}: {e}")
                    # Attempt simple fallback screenshot
                    try:
                        print(f"  Attempting fallback screenshot for {filename}...")
                        png_path = os.path.join(output_dir, f"{name}.png")
                        await page.screenshot(path=png_path, full_page=False, type="png", timeout=5000)
                        print(f"  Saved fallback {png_path}")
                    except Exception as fallback_err:
                        print(f"  Critical fallback failure for {filename}: {fallback_err}")
            else:
                print(f"  Warning: {filename} not found!")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(render_svgs())
