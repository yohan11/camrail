import os
try:
    from markdown_it import MarkdownIt
except ImportError:
    import sys
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "markdown-it-py"])
    from markdown_it import MarkdownIt

md = MarkdownIt("commonmark").enable("table")

# CSS pour avoir un beau rendu "document" propre
css = """
<style>
    body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 30px; color: #222; }
    h1 { color: #8B0000; border-bottom: 2px solid #8B0000; padding-bottom: 10px; }
    h2 { color: #B22222; margin-top: 30px; }
    h3 { color: #CD5C5C; }
    table { width: 100%; border-collapse: collapse; margin: 25px 0; font-size: 14px; }
    th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
    th { background-color: #f8f9fa; font-weight: bold; color: #333; }
    pre { background-color: #f1f3f5; padding: 15px; border-radius: 8px; overflow-x: auto; }
    code { font-family: Consolas, monospace; background-color: #f1f3f5; padding: 2px 5px; border-radius: 3px; font-size: 13px; }
    blockquote { border-left: 4px solid #8B0000; margin-left: 0; padding-left: 15px; color: #555; background-color: #fdfdfd; padding: 10px; }
</style>
"""

docs_dir = r"c:\Users\hp\OneDrive\Desktop\camrail\docs"

for filename in os.listdir(docs_dir):
    if filename.endswith(".md") and filename != "test.md":
        filepath = os.path.join(docs_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        
        html_content = md.render(text)
        
        full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{filename}</title>{css}</head><body>{html_content}</body></html>"
        
        out_path = os.path.join(docs_dir, filename.replace(".md", ".html"))
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        print(f"Généré : {out_path}")

print("Succès !")
