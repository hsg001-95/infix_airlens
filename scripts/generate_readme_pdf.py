import json
import re
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
README_PATH = ROOT_DIR / "README.md"
OUTPUT_HTML = ROOT_DIR / "docs" / "readme_rendered.html"
OUTPUT_PDF = ROOT_DIR / "docs" / "Infix_AirLens_README.pdf"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Infix AirLens | Enterprise Intelligence Platform</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown-light.min.css">
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/mermaid.min.js"></script>
<style>
    @page {
        size: A4;
        margin: 13mm 13mm 13mm 13mm;
    }
    body {
        background-color: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        color: #1e293b;
        margin: 0;
        padding: 0;
    }
    .markdown-body {
        box-sizing: border-box;
        min-width: 200px;
        max-width: 100%;
        margin: 0 auto;
        padding: 4px;
        font-size: 12.2px;
        line-height: 1.5;
    }
    .markdown-body h1 {
        border-bottom: 2px solid #0284c7;
        padding-bottom: 6px;
        color: #0f172a;
        font-size: 23px;
        margin-top: 4px;
        margin-bottom: 12px;
    }
    .markdown-body h2 {
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 5px;
        margin-top: 18px;
        margin-bottom: 10px;
        color: #0f172a;
        font-size: 16.5px;
        page-break-after: avoid;
    }
    .markdown-body h3 {
        color: #1e293b;
        font-size: 14px;
        margin-top: 14px;
        margin-bottom: 6px;
        page-break-after: avoid;
    }
    .markdown-body table {
        width: 100%;
        border-collapse: collapse;
        margin: 10px 0;
        font-size: 11px;
        page-break-inside: avoid;
    }
    .markdown-body th, .markdown-body td {
        padding: 5px 8px;
        border: 1px solid #cbd5e1;
    }
    .markdown-body th {
        background-color: #f1f5f9;
        font-weight: 600;
        color: #0f172a;
    }
    .markdown-body pre {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        font-size: 10.5px;
        padding: 10px;
        page-break-inside: avoid;
    }
    .markdown-body code {
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    }
    .mermaid {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 10px;
        margin: 12px 0;
        text-align: center;
        page-break-inside: avoid;
    }
    .mermaid svg {
        max-width: 95% !important;
        height: auto !important;
    }
    hr {
        height: 1px;
        background-color: #e2e8f0;
        border: none;
        margin: 14px 0;
    }
</style>
</head>
<body class="markdown-body">
<div id="content"></div>

<script>
    mermaid.initialize({
        startOnLoad: false,
        theme: 'neutral',
        flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' }
    });

    const rawMd = `__ESCAPED_MD__`;
    const mermaidDiagrams = __MERMAID_JSON__;

    document.getElementById('content').innerHTML = marked.parse(rawMd);

    // Inject protected mermaid blocks
    mermaidDiagrams.forEach((code, idx) => {
        const placeholder = document.getElementById(`mermaid-placeholder-${idx}`);
        if (placeholder) {
            const div = document.createElement('div');
            div.className = 'mermaid';
            div.textContent = code;
            placeholder.replaceWith(div);
        }
    });

    async function initMermaid() {
        try {
            await mermaid.run({
                nodes: document.querySelectorAll('.mermaid')
            });
        } catch (e) {
            console.error('Mermaid render error:', e);
        }
    }
    initMermaid();
</script>
</body>
</html>
"""

def build_pdf():
    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    with open(README_PATH, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Extract mermaid diagram to protect it from marked parser
    mermaid_blocks = []
    def save_mermaid(match):
        idx = len(mermaid_blocks)
        mermaid_blocks.append(match.group(1).strip())
        return f'<div id="mermaid-placeholder-{idx}"></div>'

    md_content = re.sub(r'```mermaid\s*\n(.*?)\n```', save_mermaid, md_content, flags=re.DOTALL)

    # Clean math notation for crisp typography
    md_content = md_content.replace(r"$\rightarrow$", "→").replace(r"\rightarrow", "→")
    md_content = md_content.replace(r"\text{Hotspot Index}", "Hotspot Index")
    md_content = md_content.replace(r"\text{Mean AQI}", "Mean AQI")
    md_content = md_content.replace(r"\text{P95 AQI}", "P95 AQI")
    md_content = md_content.replace(r"\text{Poor+ Share}", "Poor+ Share")
    md_content = md_content.replace(r"\left(", "(").replace(r"\right)", ")")
    md_content = md_content.replace(r"\times", "×")
    md_content = md_content.replace(r"\frac{100}{450}", "(100 / 450)")

    # Escape backticks and backslashes for JS string template
    escaped_md = md_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    html_content = HTML_TEMPLATE.replace("__ESCAPED_MD__", escaped_md).replace("__MERMAID_JSON__", json.dumps(mermaid_blocks))

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Generated HTML preview at: {OUTPUT_HTML}")

    chrome_cmd = [
        "google-chrome",
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=6000",
        f"--print-to-pdf={OUTPUT_PDF}",
        "--no-pdf-header-footer",
        str(OUTPUT_HTML.resolve()),
    ]

    print("Running headless Chrome to render PDF...")
    result = subprocess.run(chrome_cmd, capture_output=True, text=True)
    if result.returncode == 0 and OUTPUT_PDF.exists():
        size_kb = OUTPUT_PDF.stat().st_size / 1024
        print(f"Successfully generated PDF: {OUTPUT_PDF} ({size_kb:.1f} KB)")
    else:
        print(f"Return code: {result.returncode}, stderr: {result.stderr}, stdout: {result.stdout}")

if __name__ == "__main__":
    build_pdf()
