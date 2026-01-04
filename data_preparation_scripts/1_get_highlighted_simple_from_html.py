from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag
import re
import json


# stupid to first do it for all and then remove it for half, but could not figure out another way
def remove_headings(markdown_text):
    """
    Converts all Markdown headings into normal text.

    Parameters:
        markdown_text (str): The original Markdown text.

    Returns:
        str: The Markdown text with headings converted to normal text.
    """
    # Regex to match headings (from # to ######) and capture the text
    heading_pattern = re.compile(r'^(#{1,6})\s*(.*)$', re.MULTILINE)

    # Replace headings with just their text
    return heading_pattern.sub(r'\2', markdown_text)


def clean_markdown(markdown_text):
    """
    Converts all Markdown headings to normal text and removes bold formatting.

    Parameters:
        markdown_text (str): The original Markdown text.

    Returns:
        str: Cleaned Markdown text with headings converted and bold removed.
    """
    # Remove headings: match lines starting with 1-6 # followed by space
    heading_pattern = re.compile(r'^(#{1,6})\s*(.*)$', re.MULTILINE)
    text_without_headings = heading_pattern.sub(r'\2', markdown_text)

    # Remove bold formatting (**text** or __text__)
    bold_pattern = re.compile(r'(\*\*|__)(.*?)\1')
    clean_text = bold_pattern.sub(r'\2', text_without_headings)

    return clean_text


def inline_to_markdown(node, replace_br_with_space=False):
    """Recursively convert inline nodes to markdown text."""
    if isinstance(node, NavigableString):
        return node.string.replace("\r", "").replace("\n", " ")
    if not isinstance(node, Tag):
        return ""

    name = node.name.lower()

    if name in ("strong", "b"):
        inner = "".join(inline_to_markdown(c, replace_br_with_space) for c in node.children).strip()
        return f"**{inner}**" if inner else ""
    if name in ("em", "i"):
        inner = "".join(inline_to_markdown(c, replace_br_with_space) for c in node.children).strip()
        return f"*{inner}*" if inner else ""
    if name == "a":
        href = node.get("href", "").strip()
        text = "".join(inline_to_markdown(c, replace_br_with_space) for c in node.children).strip()
        if href:
            return f"[{text}]({href})" if text else href
        return text
    if name == "code":
        text = "".join(inline_to_markdown(c, replace_br_with_space) for c in node.children).strip()
        return f"`{text}`" if text else ""
    if name == "br":
        return " " if replace_br_with_space else "  \n"  # <-- key change
    # For other tags, concatenate children (this preserves inline spans, <span>, etc.)
    return "".join(inline_to_markdown(c, replace_br_with_space) for c in node.children)

def process_list(tag, indent=0):
    """
    Convert a <ul> or <ol> to markdown lines, keeping nested lists.
    indent = number of leading "  " levels
    """
    lines = []
    is_ordered = (tag.name.lower() == "ol")
    # Only iterate top-level li children (recursive=False) to preserve structure
    lis = [li for li in tag.find_all("li", recursive=False)]
    for idx, li in enumerate(lis, start=1):
        # Build the text for the non-list children inside li
        parts = []
        for child in li.contents:
            if isinstance(child, Tag) and child.name in ("ul", "ol"):
                # nested list; handled after the current line
                continue
            parts.append(inline_to_markdown(child))
        content_text = " ".join(p.strip() for p in parts if p and p.strip()).strip()
        prefix = ("  " * indent)
        if is_ordered:
            prefix += f"{idx}. "
        else:
            prefix += "- "
        lines.append(prefix + content_text)
        # Now handle nested lists directly under this li
        for child in li.find_all(["ul", "ol"], recursive=False):
            lines.extend(process_list(child, indent=indent+1))
    return lines

def should_include_p(p_tag):
    # include only <p> with no class attribute
    #return p_tag.name == "p" and not p_tag.has_attr("class")
    # include <p> with no class or class="MsoNormal"
    return p_tag.name == "p" and (not p_tag.has_attr("class") or p_tag.get("class") == ["MsoNormal"])

def walk_and_extract(node, out_lines, use_headings=True):
    """
    Walk a node's children in document order and append markdown lines for:
    - headings h1..h6
    - p without class
    - ul/ol lists (with nested handling)
    For any other tag, we descend into children to find allowed nodes (so nested headings/lists/p are found).
    """
    for child in node.children:
        if isinstance(child, NavigableString):
            # plain strings directly under content_div are usually whitespace/newlines; skip
            continue
        if not isinstance(child, Tag):
            continue

        name = child.name.lower()


        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):# and use_headings:
            level = int(name[1])
            #text = inline_to_markdown(child).strip()
            text = inline_to_markdown(child, replace_br_with_space=True).strip()
            out_lines.append(f'{"#"*level} {text}' if text else f'{"#"*level}')
            out_lines.append("")  # blank line after heading

        elif name == "p" and should_include_p(child):
            text = inline_to_markdown(child).strip()
            if text:
                out_lines.append(text)
                out_lines.append("")  # paragraph separation

        elif name in ("ul", "ol"):
            list_lines = process_list(child, indent=0)
            if list_lines:
                out_lines.extend(list_lines)
                out_lines.append("")  # blank line after list

        else:
            # descend into children to locate nested headings/p/lists
            walk_and_extract(child, out_lines)


def process_files(input_dir, output_dir):
    for html_path in sorted(input_dir.glob("*.html")):
        # Skip non-LS files
        if "LS" not in html_path.name:
            continue

        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")

        # --- Metadata ---
        base_href = ""
        base_tag = soup.find("base")
        if base_tag and base_tag.has_attr("href"):
            base_href = base_tag["href"].strip()

        title_text = ""
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)

        meta_title = ""
        meta_tag = soup.find("meta", attrs={"name": "title"})
        if meta_tag and meta_tag.has_attr("content"):
            meta_title = meta_tag["content"].strip()

        print(f"Processing: {html_path.name}")

        # --- Find the main content containers ---
        content_div = (
            soup.find("div", id="content")
            or soup.find("div", id="main")
            or soup.find("div", class_="magazin-reader source-default")
            or soup.find("div", class_="main-container")
            or soup.find("main", id="main")
            or soup.find("div", class_="main_wrapper")
            or soup.find("div", id="inhalt")
            or soup.find("main", class_="main")
            or soup.find("main")
            or soup.find("div", class_="main")
            or soup.find("ul", class_="slides")  # 5392 LS
        )

        # collect also flexslider blocks
        content_divs = []
        flexslider_divs = soup.find_all("div", class_="flexslider flexslider-inpage")

        if content_div:
            content_divs.append(content_div)
            if content_div.get("id") == "main" or content_div.name == "main":
                content_divs.extend(flexslider_divs)
        else:
            all_wrappers = soup.find_all("div", class_="wpb_wrapper")
            top_level_wrappers = [
                w for w in all_wrappers
                if w.find_parent("div", class_="wpb_wrapper") is None
            ]
            if not top_level_wrappers:
                top_level_wrappers = all_wrappers
            content_divs.extend(top_level_wrappers)

        md_lines = []
        first = True

        for div in content_divs:
            if not div.get_text(strip=True):
                continue

            if not first:
                md_lines.append("")

            # --- Special handling for flexslider blocks ---

            # --- Special handling for flexslider blocks ---
            # --- Robust handling for flexslider blocks ---
            # This works for many variants: titles may be in specific field divs,
            # in headings, or in elements with 'titel'/'title'/'headline' in the class name.
            # Captions are taken from <p> tags; if none exist we fall back to text nodes.
            if "flexslider" in (div.get("class") or []) or (
                div.name == "ul" and "slides" in (div.get("class") or [])
            ):
                slides = div.find_all("li")
                for slide in slides:
                    # --- find title element (many fallbacks) ---
                    title_el = None
                    # Prefer elements whose class name contains 'titel'/'title'/'headline'
                    for cand in slide.find_all(True):
                        classes = cand.get("class") or []
                        cls_str = " ".join(classes).lower()
                        if any(k in cls_str for k in ("titel", "title", "headline")):
                            title_el = cand
                            break
                    # fallback to any heading tag inside the slide
                    if title_el is None:
                        title_el = slide.find(["h1", "h2", "h3", "h4", "h5", "h6"])
                    # fallback: sometimes title is the first strong/b element
                    if title_el is None:
                        title_el = slide.find(["strong", "b"])
                    # final fallback: first non-empty direct child string
                    title_text = ""
                    if title_el is not None:
                        title_text = inline_to_markdown(title_el, replace_br_with_space=True).strip()
                    else:
                        # look for a short text near the top of the slide
                        for child in slide.contents:
                            if isinstance(child, NavigableString):
                                t = child.strip()
                                if t:
                                    title_text = t.splitlines()[0].strip()
                                    break
                            elif isinstance(child, Tag):
                                txt = child.get_text(" ", strip=True)
                                if txt:
                                    title_text = txt.splitlines()[0].strip()
                                    break

                    # --- collect paragraph lines ---
                    paragraph_lines = []
                    # prefer explicit <p> tags
                    for p in slide.find_all("p"):
                        pt = inline_to_markdown(p).strip()
                        if pt:
                            paragraph_lines.append(pt)
                    # fallback: collect textual content excluding the title element
                    if not paragraph_lines:
                        texts = []
                        for descendant in slide.descendants:
                            # skip the title element's descendants (we've already extracted it)
                            if title_el is not None and (isinstance(descendant, Tag) and descendant is title_el):
                                continue
                            if isinstance(descendant, NavigableString):
                                t = descendant.strip()
                                if t:
                                    texts.append(t)
                        if texts:
                            # join into one paragraph (split intelligently if there are multiple sentences)
                            paragraph_lines = [" ".join(texts).strip()]

                    # --- write out as a bullet + indented paragraphs (Markdown line breaks) ---
                    if title_text or paragraph_lines:
                        # if title_text is empty but we have paragraphs, use first paragraph as bullet text
                        bullet_title = title_text if title_text else (paragraph_lines[0] if paragraph_lines else "")
                        md_lines.append(f"- {bullet_title}")
                        # if we used the first paragraph as title, avoid duplicating it
                        start_idx = 0 if title_text else (1 if paragraph_lines else 0)
                        for p_line in paragraph_lines[start_idx:]:
                            # append two spaces at end to make a markdown line break
                            md_lines.append(f"{p_line}  ")
                        md_lines.append("")  # blank line after each slide item

            else:
                # default path
                walk_and_extract(div, md_lines, use_headings=True)

            first = False

        # Remove trailing empty lines
        while md_lines and md_lines[-1].strip() == "":
            md_lines.pop()


        # --- Write Markdown file (text only, no front matter) ---
        body = "\n".join(md_lines) + ("\n" if md_lines else "")
        out_md_path = output_dir / f"{html_path.stem}.md"
        out_md_path.write_text(body, encoding="utf-8")

        # --- Write metadata JSON file ---
        metadata = {
            "source_file": html_path.name,
            "base_href": base_href,
            "html_title": title_text,
            "meta_title": meta_title
        }
        out_meta_path = output_dir / f"{html_path.stem}.json"
        out_meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"Written Markdown: {out_md_path}")
        print(f"Written Metadata: {out_meta_path}")


if __name__ == "__main__":
    # Input and output directories
    input_dir = Path("dataset_original_raw/html_files")
    output_dir = Path("dataset_highlighted/html_files")

    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    process_files(input_dir, output_dir)