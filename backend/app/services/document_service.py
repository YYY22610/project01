"""Document generation service using python-docx."""
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


def generate_docx(file_path: str, title: str, content: str):
    """Generate a formatted .docx file from title and content.

    Content is plain text with line breaks. Lines starting with # are treated as headings.
    Lines starting with - are treated as bullet points.
    """
    doc = Document()

    # Set default font
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Microsoft YaHei"
    font.size = Pt(11)

    # Title
    heading = doc.add_heading(title, level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Parse and add content
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("### "):
            doc.add_heading(line[4:], level=3)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        elif line.startswith("- "):
            p = doc.add_paragraph(line[2:], style="List Bullet")
        elif line.startswith(tuple("0123456789")) and ". " in line:
            idx = line.index(". ")
            p = doc.add_paragraph(line[idx + 2:], style="List Number")
        else:
            doc.add_paragraph(line)

    doc.save(file_path)
