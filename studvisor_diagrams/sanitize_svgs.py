import os
import re

svg_dir = r"d:\Behavior-Based-Authentication-main\studvisor_diagrams"
svg_files = [
    "fig_3_1_use_case.svg",
    "fig_3_2_er_diagram.svg",
    "fig_3_3_dfd_l0.svg",
    "fig_3_4_dfd_l1.svg",
    "fig_3_5_dfd_l2.svg",
    "fig_3_6_sfd_request_lifecycle.svg",
]

for filename in svg_files:
    filepath = os.path.join(svg_dir, filename)
    if os.path.exists(filepath):
        print(f"Sanitizing {filename}...")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if already using CDATA
        if "<style type=\"text/css\"><![CDATA[" not in content:
            # Let's search for <style type="text/css">...</style> and wrap inside CDATA
            # and replace &amp; with &
            
            def replace_style(match):
                style_body = match.group(1)
                # Replace escaped &amp; with actual &
                style_body = style_body.replace("&amp;", "&")
                # Strip existing CDATA if somehow partially present
                style_body = style_body.replace("<![CDATA[", "").replace("]]>", "")
                return f'<style type="text/css"><![CDATA[{style_body}]]></style>'
            
            new_content = re.sub(r'<style type="text/css">(.*?)</style>', replace_style, content, flags=re.DOTALL)
            
            with open(filepath, "w", encoding="utf-8") as f_out:
                f_out.write(new_content)
            print(f"  Successfully sanitized {filename} (wrapped in CDATA).")
        else:
            print(f"  {filename} is already wrapped in CDATA.")
    else:
        print(f"  Warning: {filename} not found!")

print("All SVGs sanitized successfully!")
