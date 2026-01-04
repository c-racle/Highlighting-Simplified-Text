import os
import re
import shutil


def remove_markdown_formatting(text: str) -> str:
    """
    Removes Markdown formatting like **bold**, *italic*, headings, links, images,
    inline code, blockquotes, lists, etc., leaving just plain text.
    """
    # Remove code blocks
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Remove inline code
    text = re.sub(r"`[^`]*`", "", text)
    # Remove images
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    # Remove links but keep the link text
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Remove headings (e.g. ### Heading)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    # Remove bold and italics
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
    # Remove blockquotes
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
    # Remove list markers (-, *, +, numbers)
    #text = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", text, flags=re.MULTILINE)
    # Collapse multiple blank lines
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()

def process_files(src_dir, dst_dir):
    # Make sure the destination directory exists
    os.makedirs(dst_dir, exist_ok=True)

    # Process files containing "LS" in the filename
    for filename in os.listdir(src_dir):
        src_path = os.path.join(src_dir, filename)
        dst_path = os.path.join(dst_dir, filename)

        if not os.path.isfile(src_path):
            continue  # skip directories or non-files

        if "LS" in filename and filename.endswith(".md"):


            # Read the file
            with open(src_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Clean formatting
            cleaned = remove_markdown_formatting(content)

            # Write cleaned content to destination
            with open(dst_path, "w", encoding="utf-8") as f:
                f.write(cleaned)

            # copy metadata JSON if it exists
            json_src = os.path.splitext(src_path)[0] + ".json"
            json_dst = os.path.splitext(dst_path)[0] + ".json"
            if os.path.exists(json_src):
                shutil.copy2(json_src, json_dst)

            print(f"Processed: {filename}")

        #elif "AS" in filename and filename.endswith(".md"):
            # Copy AS files directly
            #shutil.copy2(src_path, dst_path)
            #print(f"Copied AS file: {filename}")

if __name__ == "__main__":

    # Define directories
    src_dir_test = "dataset_highlighted/tetml_files"
    dst_dir_test = "dataset_simple/tetml_files"
    process_files(src_dir_test, dst_dir_test)

    src_dir_train = "dataset_highlighted/html_files"
    dst_dir_train = "dataset_simple/html_files"
    process_files(src_dir_train, dst_dir_train)


