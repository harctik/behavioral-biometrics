import os
import re

svg_dir = r"d:\Behavior-Based-Authentication-main\studvisor_diagrams"
output_html = os.path.join(svg_dir, "index.html")

print("Reading SVG files...")
svg_files = {
    "fig_3_1": "fig_3_1_use_case.svg",
    "fig_3_2": "fig_3_2_er_diagram.svg",
    "fig_3_3": "fig_3_3_dfd_l0.svg",
    "fig_3_4": "fig_3_4_dfd_l1.svg",
    "fig_3_5": "fig_3_5_dfd_l2.svg",
    "fig_3_6": "fig_3_6_sfd_request_lifecycle.svg",
}

svg_contents = {}
for key, filename in svg_files.items():
    filepath = os.path.join(svg_dir, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            # Strip XML declaration if present
            content = re.sub(r'<\?xml[^>]*\?>', '', content)
            svg_contents[key] = content.strip()
            print(f"  Loaded {filename}")
    else:
        # Fallback if first file is in upper case or located elsewhere
        print(f"  Warning: {filename} not found!")

html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Studvisor Platform - Chapter 3 A4 Diagram Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0F172A;
            --bg-secondary: #1E293B;
            --bg-tertiary: #334155;
            --accent-teal: #0D9488;
            --accent-blue: #0284C7;
            --text-primary: #F8FAFC;
            --text-secondary: #94A3B8;
            --glass-bg: rgba(30, 41, 59, 0.7);
            --glass-border: rgba(255, 255, 255, 0.08);
            --shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        /* Glassmorphism Header */
        header {
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--glass-border);
            padding: 20px 40px;
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: var(--shadow);
        }

        .header-logo {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-icon {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, var(--accent-teal), var(--accent-blue));
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 18px;
            color: white;
            box-shadow: 0 0 15px rgba(13, 148, 136, 0.4);
        }

        .header-title h1 {
            font-weight: 800;
            font-size: 20px;
            letter-spacing: 0.5px;
            background: linear-gradient(to right, #F8FAFC, #94A3B8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .header-title p {
            font-size: 11px;
            color: var(--text-secondary);
            font-weight: 400;
            margin-top: 2px;
        }

        .actions-btn {
            background: linear-gradient(135deg, var(--accent-teal), var(--accent-blue));
            color: white;
            border: none;
            padding: 10px 18px;
            font-size: 13px;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(2, 132, 199, 0.25);
            display: flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
        }

        .actions-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(2, 132, 199, 0.35);
            filter: brightness(1.1);
        }

        /* Main Workspace Layout */
        .workspace {
            display: flex;
            flex: 1;
            height: calc(100vh - 78px);
            overflow: hidden;
        }

        /* Sidebar Navigation */
        .sidebar {
            width: 320px;
            background: rgba(15, 23, 42, 0.85);
            border-right: 1px solid var(--glass-border);
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            overflow-y: auto;
        }

        .section-title {
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 700;
            color: var(--text-secondary);
            letter-spacing: 1.5px;
            margin-bottom: 8px;
        }

        .nav-list {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .nav-item {
            background: var(--bg-secondary);
            border: 1px solid var(--glass-border);
            border-radius: 10px;
            padding: 12px 16px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .nav-item:hover {
            background: var(--bg-tertiary);
            border-color: rgba(255, 255, 255, 0.15);
            transform: translateX(4px);
        }

        .nav-item.active {
            background: linear-gradient(135deg, rgba(13, 148, 136, 0.15), rgba(2, 132, 199, 0.15));
            border-color: var(--accent-blue);
            box-shadow: inset 0 0 10px rgba(2, 132, 199, 0.05);
        }

        .nav-item-num {
            font-family: 'Fira Code', monospace;
            font-size: 11px;
            font-weight: 600;
            color: var(--accent-teal);
        }

        .nav-item.active .nav-item-num {
            color: #38BDF8;
        }

        .nav-item-name {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-primary);
        }

        /* Canvas Container */
        .canvas-area {
            flex: 1;
            background: #080D1A;
            padding: 30px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            overflow: hidden;
            position: relative;
        }

        .canvas-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .canvas-details h2 {
            font-size: 20px;
            font-weight: 800;
        }

        .canvas-details p {
            font-size: 12.5px;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        .canvas-actions {
            display: flex;
            gap: 10px;
        }

        .control-btn {
            background: var(--bg-secondary);
            border: 1px solid var(--glass-border);
            color: var(--text-primary);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .control-btn:hover {
            background: var(--bg-tertiary);
            border-color: rgba(255, 255, 255, 0.2);
        }

        .control-btn svg {
            width: 14px;
            height: 14px;
            fill: currentColor;
        }

        /* A4 Viewer Window */
        .viewer-card {
            flex: 1;
            background: #FFFFFF;
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid var(--glass-border);
            position: relative;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
            /* Preserve A4 aspect ratio 1.414 */
            aspect-ratio: 1.414;
            max-height: calc(100% - 60px);
        }

        .viewer-card.portrait {
            aspect-ratio: 0.707;
        }

        .svg-container {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            transform-origin: center center;
            transition: transform 0.1s ease;
        }

        .svg-container svg {
            width: 100%;
            height: 100%;
            max-width: 100%;
            max-height: 100%;
        }

        /* Right Panel: Documentation */
        .doc-panel {
            width: 360px;
            background: rgba(15, 23, 42, 0.85);
            border-left: 1px solid var(--glass-border);
            padding: 30px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .doc-section h3 {
            font-size: 15px;
            font-weight: 700;
            color: var(--text-primary);
            border-left: 3px solid var(--accent-teal);
            padding-left: 10px;
            margin-bottom: 12px;
        }

        .doc-section p {
            font-size: 12.5px;
            color: var(--text-secondary);
            line-height: 1.6;
        }

        .bullet-list {
            margin-top: 10px;
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .bullet-list li {
            font-size: 12px;
            color: var(--text-secondary);
            position: relative;
            padding-left: 15px;
            line-height: 1.5;
        }

        .bullet-list li::before {
            content: "•";
            color: var(--accent-teal);
            font-weight: bold;
            position: absolute;
            left: 0;
            top: 0;
        }

        /* Hide elements dynamically */
        .diagram-content {
            display: none;
            width: 100%;
            height: 100%;
        }

        .diagram-content.active {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .doc-content {
            display: none;
            flex-direction: column;
            gap: 20px;
        }

        .doc-content.active {
            display: flex;
        }
    </style>
</head>
<body>

    <header>
        <div class="header-logo">
            <div class="logo-icon">S</div>
            <div class="header-title">
                <h1>STUDVISOR DIAGRAM CENTER</h1>
                <p>Chapter 3 (System Design) Redesigned High-Resolution A4 Diagrams</p>
            </div>
        </div>
        <div class="header-actions">
            <a class="actions-btn" href="./chapter3_diagrams.md" target="_blank">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 4px;"><path d="M15 3h6v6M10 14L21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>
                Open Markdown Document
            </a>
        </div>
    </header>

    <div class="workspace">
        <!-- Sidebar Navigation -->
        <aside class="sidebar">
            <div class="section-title">Chapter 3 Diagrams</div>
            <ul class="nav-list">
                <li class="nav-item active" onclick="switchDiagram('fig_3_1')">
                    <span class="nav-item-num">FIGURE 3.1</span>
                    <span class="nav-item-name">Use-Case Diagram</span>
                </li>
                <li class="nav-item" onclick="switchDiagram('fig_3_2')">
                    <span class="nav-item-num">FIGURE 3.2</span>
                    <span class="nav-item-name">Entity-Relationship Diagram</span>
                </li>
                <li class="nav-item" onclick="switchDiagram('fig_3_3')">
                    <span class="nav-item-num">FIGURE 3.3</span>
                    <span class="nav-item-name">DFD Level 0 (Context)</span>
                </li>
                <li class="nav-item" onclick="switchDiagram('fig_3_4')">
                    <span class="nav-item-num">FIGURE 3.4</span>
                    <span class="nav-item-name">DFD Level 1 (Major Flows)</span>
                </li>
                <li class="nav-item" onclick="switchDiagram('fig_3_5')">
                    <span class="nav-item-num">FIGURE 3.5</span>
                    <span class="nav-item-name">DFD Level 2 (AI Tutor)</span>
                </li>
                <li class="nav-item" onclick="switchDiagram('fig_3_6')">
                    <span class="nav-item-num">FIGURE 3.6</span>
                    <span class="nav-item-name">System Flow Diagram (SFD)</span>
                </li>
            </ul>
        </aside>

        <!-- Canvas Area -->
        <main class="canvas-area">
            <div class="canvas-header">
                <div class="canvas-details">
                    <h2 id="active-title">FIGURE 3.1: USE-CASE DIAGRAM</h2>
                    <p id="active-subtitle">Studvisor Platform Boundary - Primary Actors &amp; Interactions</p>
                </div>
                <div class="canvas-actions">
                    <button class="control-btn" onclick="zoomIn()">
                        <svg viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>Zoom In
                    </button>
                    <button class="control-btn" onclick="zoomOut()">
                        <svg viewBox="0 0 24 24"><path d="M19 13H5v-2h14v2z"/></svg>Zoom Out
                    </button>
                    <button class="control-btn" onclick="resetZoom()">Reset</button>
                    <button class="control-btn" onclick="downloadSVG()">
                        <svg viewBox="0 0 24 24"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM17 13l-5 5-5-5h3V9h4v4h3z"/></svg>Download Vector (SVG)
                    </button>
                </div>
            </div>

            <!-- Viewer Card -->
            <div class="viewer-card" id="viewer">
                <div class="svg-container" id="svg-zoom-container">
                    <!-- Embedded SVGs -->
                    <div class="diagram-content active" id="diag_fig_3_1">
                        __FIG_3_1__
                    </div>
                    <div class="diagram-content" id="diag_fig_3_2">
                        __FIG_3_2__
                    </div>
                    <div class="diagram-content" id="diag_fig_3_3">
                        __FIG_3_3__
                    </div>
                    <div class="diagram-content" id="diag_fig_3_4">
                        __FIG_3_4__
                    </div>
                    <div class="diagram-content" id="diag_fig_3_5">
                        __FIG_3_5__
                    </div>
                    <div class="diagram-content" id="diag_fig_3_6">
                        __FIG_3_6__
                    </div>
                </div>
            </div>
        </main>

        <!-- Right Doc Panel -->
        <section class="doc-panel">
            <!-- DOC FOR FIG 3.1 -->
            <div class="doc-content active" id="doc_fig_3_1">
                <div class="doc-section">
                    <h3>Use-Case Architecture</h3>
                    <p>The Use-Case Diagram structures the core platform interfaces across three actors:</p>
                    <ul class="bullet-list">
                        <li><strong>Student (Primary)</strong>: Interacts with the AI Tutor, monitors academic profiles, and participates in anonymous wall merit-gathering.</li>
                        <li><strong>Faculty Member</strong>: Coordinates grades, takes daily classroom attendance registers, and accesses at-risk analytics dashboards.</li>
                        <li><strong>System Administrator</strong>: Inspects append-only system logs, manages master databases, and oversees safety rules.</li>
                    </ul>
                </div>
            </div>

            <!-- DOC FOR FIG 3.2 -->
            <div class="doc-content" id="doc_fig_3_2">
                <div class="doc-section">
                    <h3>Normalized Schema</h3>
                    <p>The ERD charts the fully normalized relational schema:</p>
                    <ul class="bullet-list">
                        <li><strong>Identity Separation</strong>: Users map polymorphic profiles to Students and Faculty respectively.</li>
                        <li><strong>Relational Integrity</strong>: 1:N relations connect Students to Marks, Attendance logs, and Merit ledgers.</li>
                        <li><strong>Timetabling Conflicts</strong>: Timetable slots integrate composite FK constraints (faculty, subject, room, group).</li>
                        <li><strong>Anonymity</strong>: Rotating daily HMAC salts protect poster identifies on the campus wall.</li>
                    </ul>
                </div>
            </div>

            <!-- DOC FOR FIG 3.3 -->
            <div class="doc-content" id="doc_fig_3_3">
                <div class="doc-section">
                    <h3>Level 0 Context Flow</h3>
                    <p>The DFD L0 maps high-level boundaries and communications:</p>
                    <ul class="bullet-list">
                        <li><strong>Student Input</strong>: Authentication, text queries, leave forms, Wall postings.</li>
                        <li><strong>Faculty Input</strong>: Marks, attendances, timetable updates.</li>
                        <li><strong>Admin Controls</strong>: Security settings and AI system configurations.</li>
                        <li><strong>AI Provider Pipeline</strong>: Transmits clean vector prompt vectors, returning completions.</li>
                    </ul>
                </div>
            </div>

            <!-- DOC FOR FIG 3.4 -->
            <div class="doc-content" id="doc_fig_3_4">
                <div class="doc-section">
                    <h3>Level 1 Major Flows</h3>
                    <p>Decomposes application logic into seven autonomous backend processes:</p>
                    <ul class="bullet-list">
                        <li><strong>P1 - P3</strong>: Manage JWT authentication cycles, CRUD academic data entries, and orchestrate AI chat loops.</li>
                        <li><strong>P4 - P6</strong>: Compute predictive risk scores, direct anonymous wall classifications, and compute gamified rewards.</li>
                        <li><strong>P7</strong>: Intercepts all write paths, writing JSON diff blocks to compliance stores.</li>
                    </ul>
                </div>
            </div>

            <!-- DOC FOR FIG 3.5 -->
            <div class="doc-content" id="doc_fig_3_5">
                <div class="doc-section">
                    <h3>Level 2 AI Pipeline</h3>
                    <p>Details the core operations inside process P3 (AI Tutor Interaction):</p>
                    <ul class="bullet-list">
                        <li><strong>P3.1 - P3.2</strong>: Authorizes tokens, loads session cache, and gathers academic marks to prepend to prompts.</li>
                        <li><strong>P3.3</strong>: Embeds query vectors, searching FAISS indexes for related knowledge files.</li>
                        <li><strong>P3.4 - P3.5</strong>: Scrubs PII identifiers using regex filters, streaming completions via SSE pipelines.</li>
                    </ul>
                </div>
            </div>

            <!-- DOC FOR FIG 3.6 -->
            <div class="doc-content" id="doc_fig_3_6">
                <div class="doc-section">
                    <h3>System Flow Swimlanes</h3>
                    <p>Follows a single database-mutating transaction through four conceptual lanes:</p>
                    <ul class="bullet-list">
                        <li><strong>Client Ingress</strong>: Handles SlowAPI middleware checks (&lt; 200 requests/minute limit).</li>
                        <li><strong>Auth Guarding</strong>: Extracts authorization headers, decoding roles via JWT security decoders.</li>
                        <li><strong>Database Scoping</strong>: Programmatically appends WHERE filters, shielding records from peer horizontal hacking.</li>
                        <li><strong>Transactions &amp; Auditing</strong>: Commits write-operations, logging changes append-only via AuditLogMiddleware.</li>
                    </ul>
                </div>
            </div>
        </section>
    </div>

    <script>
        let currentScale = 1;
        let activeKey = "fig_3_1";

        const metadata = {
            fig_3_1: {
                title: "FIGURE 3.1: USE-CASE DIAGRAM",
                subtitle: "Studvisor Platform Boundary - Primary Actors & Interactions",
                filename: "fig_3_1_use_case.svg"
            },
            fig_3_2: {
                title: "FIGURE 3.2: ENTITY-RELATIONSHIP DIAGRAM",
                subtitle: "Normalized relational schema - entities, types and constraints",
                filename: "fig_3_2_er_diagram.svg"
            },
            fig_3_3: {
                title: "FIGURE 3.3: DFD LEVEL 0 (CONTEXT DIAGRAM)",
                subtitle: "High-level input/output flow parameters between external entities",
                filename: "fig_3_3_dfd_l0.svg"
            },
            fig_3_4: {
                title: "FIGURE 3.4: DFD LEVEL 1 (MAJOR FLOWS)",
                subtitle: "Architecture process layers, database storage and interactions",
                filename: "fig_3_4_dfd_l1.svg"
            },
            fig_3_5: {
                title: "FIGURE 3.5: DFD LEVEL 2 (AI TUTOR PROCESS)",
                subtitle: "Context injection, FAISS Vector retrieval, and PII redaction pipeline",
                filename: "fig_3_5_dfd_l2.svg"
            },
            fig_3_6: {
                title: "FIGURE 3.6: SYSTEM FLOW DIAGRAM (SFD)",
                subtitle: "Swimlane request lifecycle trace: TLS, JWT verification, Scoping, and Audit",
                filename: "fig_3_6_sfd_request_lifecycle.svg"
            }
        };

        function switchDiagram(key) {
            activeKey = key;
            currentScale = 1;
            
            // Update Active Navigation Item
            document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
            const clickedIndex = Object.keys(metadata).indexOf(key);
            document.querySelectorAll('.nav-list .nav-item')[clickedIndex].classList.add('active');
            
            // Update Headers
            document.getElementById('active-title').innerText = metadata[key].title;
            document.getElementById('active-subtitle').innerText = metadata[key].subtitle;
            
            // Switch SVGs
            document.querySelectorAll('.diagram-content').forEach(el => el.classList.remove('active'));
            document.getElementById(`diag_${key}`).classList.add('active');
            
            // Switch Docs
            document.querySelectorAll('.doc-content').forEach(el => el.classList.remove('active'));
            document.getElementById(`doc_${key}`).classList.add('active');
            
            // Reset Zoom
            resetZoom();
        }

        function zoomIn() {
            if (currentScale < 3) {
                currentScale += 0.15;
                applyZoom();
            }
        }

        function zoomOut() {
            if (currentScale > 0.5) {
                currentScale -= 0.15;
                applyZoom();
            }
        }

        function resetZoom() {
            currentScale = 1;
            applyZoom();
        }

        function applyZoom() {
            const container = document.getElementById('svg-zoom-container');
            container.style.transform = `scale(${currentScale})`;
        }

        function downloadSVG() {
            const svgContent = document.getElementById(`diag_${activeKey}`).innerHTML;
            const blob = new Blob([svgContent], {type: "image/svg+xml;charset=utf-8"});
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = metadata[activeKey].filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        }
    </script>
</body>
</html>
"""

# Format HTML template using direct string replacement (safe from single braces)
formatted_html = html_template
formatted_html = formatted_html.replace("__FIG_3_1__", svg_contents.get("fig_3_1", "<!-- Missing Fig 3.1 -->"))
formatted_html = formatted_html.replace("__FIG_3_2__", svg_contents.get("fig_3_2", "<!-- Missing Fig 3.2 -->"))
formatted_html = formatted_html.replace("__FIG_3_3__", svg_contents.get("fig_3_3", "<!-- Missing Fig 3.3 -->"))
formatted_html = formatted_html.replace("__FIG_3_4__", svg_contents.get("fig_3_4", "<!-- Missing Fig 3.4 -->"))
formatted_html = formatted_html.replace("__FIG_3_5__", svg_contents.get("fig_3_5", "<!-- Missing Fig 3.5 -->"))
formatted_html = formatted_html.replace("__FIG_3_6__", svg_contents.get("fig_3_6", "<!-- Missing Fig 3.6 -->"))

print(f"Writing {output_html}...")
with open(output_html, "w", encoding="utf-8") as f_out:
    f_out.write(formatted_html)

print("Dashboard compilation complete!")
