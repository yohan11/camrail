from markdown_pdf import MarkdownPdf, Section
import os

pdf = MarkdownPdf(toc_level=2)
source_file = r"C:\Users\hp\.gemini\antigravity-ide\brain\8a040c38-0c56-437c-b97f-b690c0c40f43\guide_deploiement.md"
target_file = r"C:\Users\hp\OneDrive\Desktop\camrail\Documentation RailMind Lite\Guide_Deploiement.pdf"

with open(source_file, "r", encoding="utf-8") as f:
    content = f.read()

# Add content
pdf.add_section(Section(content))

# Save
pdf.save(target_file)
print("PDF generated at", target_file)
