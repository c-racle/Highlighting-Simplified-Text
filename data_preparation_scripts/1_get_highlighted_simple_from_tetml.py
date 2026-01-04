import os
import xml.etree.ElementTree as ET
from pathlib import Path
import json

# -------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------
INPUT_DIR = "dataset_original_raw/tetml_files"  # directory with .tetml files
OUTPUT_DIR = "dataset_highlighted/tetml_files"# directory to write .md files

# Map font ids (e.g. "F1", "F2") to markdown heading prefixes.
# Keys are matched case-insensitively. Adjust to your fonts.
HEADING_MAP = {
    "F1": "#",   # font id F1 -> H1
    "F2": "##",  # font id F2 -> H2
    "F4": "###" # font id F3 -> H3

}

# -------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------
def font_styles(font_map, font_id, LS_file=True):
    """
    Determine if font should be bold/italic.
    LS_file=True means bold allowed; LS_file=False disables bold.
    """
    font = font_map.get(font_id, {})
    name = font.get("name", "") or ""
    try:
        weight = int(font.get("weight", 400))
    except Exception:
        weight = 400
    try:
        italicangle = float(font.get("italicangle", 0))
    except Exception:
        italicangle = 0.0

    bold = (weight >= 700) or ("bold" in name.lower())
    italic = (abs(italicangle) > 0.01) or ("italic" in name.lower())

    if not LS_file:
        bold = False

    return bold, italic

def style_text(text, bold=False, italic=False):
    """Wrap text in markdown style markers (bold/italic)."""
    if bold and italic:
        return f"***{text}***"
    elif bold:
        return f"**{text}**"
    elif italic:
        return f"*{text}*"
    return text

# -------------------------------------------------------------
# Parsing logic
# -------------------------------------------------------------


def parse_tetml(file_path, LS_file=True):
    """
    Parse a TETML file and return markdown text.
    - LS_file: if False (i.e. AS file), bold formatting is suppressed
               and intra-paragraph line breaks are removed.
    """
    ns = {'tet': 'http://www.pdflib.com/XML/TET3/TET-3.0'}
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Build font map
    font_map = {}
    for font in root.findall('.//tet:Font', ns):
        fid = font.attrib.get('id')
        if fid:
            font_map[fid] = font.attrib

    heading_map_norm = {k.upper(): v for k, v in HEADING_MAP.items()}
    md_paragraphs = []

    for page in root.findall('.//tet:Page', ns):
        for para in page.findall('.//tet:Para', ns):
            para_lines = []
            first_font_id = None
            first_font_seen = False

            for line in para.findall('.//tet:Line', ns):
                words = []
                for word in line.findall('.//tet:Word', ns):
                    text_el = word.find('.//tet:Text', ns)
                    if text_el is None or not text_el.text:
                        continue
                    text = text_el.text.strip()
                    if not text:
                        continue

                    glyph = word.find('.//tet:Glyph', ns)
                    font_id = None
                    if glyph is not None:
                        font_id = glyph.attrib.get('font')

                    if not first_font_seen and font_id:
                        first_font_id = font_id
                        first_font_seen = True

                    if font_id:
                        bold, italic = font_styles(font_map, font_id, LS_file)
                        text = style_text(text, bold, italic)
                    words.append(text)
                if words:
                    para_lines.append(" ".join(words))

            if not para_lines:
                continue

            # ---- DIFFERENT BEHAVIOR HERE ----
            # LS files: keep internal newlines (looks like verses)
            # AS files: merge into a single line
            if LS_file:
                paragraph_text = "\n".join(para_lines).strip()
            else:
                paragraph_text = " ".join(para_lines).strip()

            # Determine heading level
            heading_prefix = None
            if LS_file and first_font_id:
                key = first_font_id.upper()
                if key in heading_map_norm:
                    heading_prefix = heading_map_norm[key]

            if heading_prefix:
                paragraph_text = f"{heading_prefix} {paragraph_text}"

            md_paragraphs.append(paragraph_text)

    return "\n\n".join(md_paragraphs).strip()

# -------------------------------------------------------------
# Main loop
# -------------------------------------------------------------

def main():
    input_path = Path(INPUT_DIR)
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    for tetml_file in input_path.glob("*.tetml"):
        if "AS" in tetml_file.name.upper():
            continue

        print(f"Processing {tetml_file.name} ...")

        LS_file = True
        md_text = parse_tetml(tetml_file, LS_file=LS_file)

        # --- Write Markdown file ---
        md_out = output_path / f"{tetml_file.stem}.md"
        md_out.write_text(md_text, encoding="utf-8")

        # --- Write metadata JSON file ---
        metadata = {
            "source_file": tetml_file.name,
            "base_href": "",
            "html_title": tetml_file.stem,
            "meta_title": ""
        }
        json_out = output_path / f"{tetml_file.stem}.json"
        json_out.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"Written Markdown: {md_out}")
        print(f"Written Metadata: {json_out}")

    print(f"\n✅ Done! Markdown + metadata files written to: {output_path.resolve()}")

# -------------------------------------------------------------
if __name__ == "__main__":
    main()
