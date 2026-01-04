import jsonlines
import argparse
import re
from collections import Counter
import textstat

# --------------------------
# Markdown cleaning
# --------------------------
def clean_markdown(text):
    """Remove Markdown formatting (for SARI/FKGL evaluation)."""
    if text is None:
        return ""

    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)  # images
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)  # links
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)  # bold
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)  # italic
    text = re.sub(r'`([^`]*)`', r'\1', text)  # inline code
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)  # headings
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)  # blockquotes
    text = re.sub(r'^\s*(---|\*\*\*|___)\s*$', '', text, flags=re.MULTILINE)  # horizontal rules
    text = re.sub(r'^\s*([-*+]|\d+\.)\s+', '', text, flags=re.MULTILINE)  # lists
    text = text.replace('\\*', '*').replace('\\_', '_').replace('\\#', '#')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# --------------------------
# Token helpers
# --------------------------
def tokenize(s):
    return s.strip().split()

# --------------------------
# N-gram generation
# --------------------------
def get_ngrams(tokens, n):
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]

# --------------------------
# SARI computation
# --------------------------
def compute_sari_one(src, pred, refs):
    src_tokens = tokenize(src)
    pred_tokens = tokenize(pred)
    refs_tokens = [tokenize(r) for r in refs]

    sari_scores = []

    for n in [1, 2, 3, 4]:
        src_ngrams = set(get_ngrams(src_tokens, n))
        pred_ngrams = set(get_ngrams(pred_tokens, n))
        ref_ngrams = set()
        for r in refs_tokens:
            ref_ngrams |= set(get_ngrams(r, n))

        # KEEP
        keep_in_src_and_pred = pred_ngrams & src_ngrams
        keep_in_src_and_refs = src_ngrams & ref_ngrams
        keep_precision = (len(keep_in_src_and_pred & keep_in_src_and_refs) / len(keep_in_src_and_pred)
                          if keep_in_src_and_pred else 1.0)
        keep_recall = (len(keep_in_src_and_pred & keep_in_src_and_refs) / len(keep_in_src_and_refs)
                       if keep_in_src_and_refs else 1.0)
        keep_f1 = (2 * keep_precision * keep_recall / (keep_precision + keep_recall)
                   if (keep_precision + keep_recall) > 0 else 0)

        # DELETE
        delete_from_src = src_ngrams - pred_ngrams
        delete_from_src_needed = src_ngrams - ref_ngrams
        del_precision = (len(delete_from_src & delete_from_src_needed) / len(delete_from_src)
                         if delete_from_src else 1.0)
        del_recall = (len(delete_from_src & delete_from_src_needed) / len(delete_from_src_needed)
                      if delete_from_src_needed else 1.0)
        del_f1 = (2 * del_precision * del_recall / (del_precision + del_recall)
                  if (del_precision + del_recall) > 0 else 0)

        # ADD
        add_to_pred = pred_ngrams - src_ngrams
        add_needed = ref_ngrams - src_ngrams
        add_precision = (len(add_to_pred & add_needed) / len(add_to_pred) if add_to_pred else 1.0)
        add_recall = (len(add_to_pred & add_needed) / len(add_needed) if add_needed else 1.0)
        add_f1 = (2 * add_precision * add_recall / (add_precision + add_recall)
                  if (add_precision + add_recall) > 0 else 0)

        sari_scores.append((keep_f1 + del_f1 + add_f1) / 3)

    return sum(sari_scores) / 4

# --------------------------
# Markdown span extraction
# --------------------------
def extract_md_spans(text):
    """Extract bold and heading spans as (start, end, type)."""
    spans = []
    # Bold: **text**
    for m in re.finditer(r'\*\*(.+?)\*\*', text):
        spans.append((m.start(), m.end(), 'bold'))
    # Heading: #, ##, ### ...
    for m in re.finditer(r'^(#+)\s*(.+)$', text, flags=re.MULTILINE):
        spans.append((m.start(), m.end(), 'heading'))
    return spans

def span_overlap(span1, span2):
    """Compute character-level overlap ratio (intersection / union)."""
    start1, end1, _ = span1
    start2, end2, _ = span2
    inter = max(0, min(end1, end2) - max(start1, start2))
    union = max(end1, end2) - min(start1, start2)
    return inter / union if union > 0 else 0

def compute_md_f1(pred_spans, ref_spans, threshold=0.5):
    """Compute forgiving F1 score for partial overlaps."""
    tp = 0
    matched_ref = set()
    for p in pred_spans:
        for i, r in enumerate(ref_spans):
            if i in matched_ref:
                continue
            if p[2] == r[2] and span_overlap(p, r) >= threshold:
                tp += 1
                matched_ref.add(i)
                break
    fp = len(pred_spans) - tp
    fn = len(ref_spans) - tp
    precision = tp / (tp + fp) if tp + fp > 0 else 1.0
    recall = tp / (tp + fn) if tp + fn > 0 else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0
    return precision, recall, f1

# --------------------------
# Load JSONL
# --------------------------
def load_jsonl(path, mapping):
    data = {}
    with jsonlines.open(path) as reader:
        for row in reader:
            ex = {}
            for internal, external in mapping.items():
                ex[internal] = row.get(external, "")
            data[row["id"]] = ex
    return data

# --------------------------
# Main
# --------------------------
def process(model_file, ref_file):
    model_data = load_jsonl(model_file, {"src": "input", "pred": "model_output"})
    ref_data = load_jsonl(ref_file, {"ref": "output"})

    sari_scores = []
    fkgl_input = []
    fkgl_pred = []
    fkgl_ref = []
    md_f1_scores = []

    missing = 0

    for _id, m in model_data.items():
        if _id not in ref_data:
            missing += 1
            continue

        src = clean_markdown(m["src"])
        pred = clean_markdown(m["pred"])
        ref = clean_markdown(ref_data[_id]["ref"])

        # --- SARI ---
        sari = compute_sari_one(src, pred, refs=[ref])
        sari_scores.append(sari)

        # --- FKGL ---
        fkgl_input.append(textstat.flesch_kincaid_grade(src))
        fkgl_pred.append(textstat.flesch_kincaid_grade(pred))
        fkgl_ref.append(textstat.flesch_kincaid_grade(ref))

        # --- Markdown F1 ---
        pred_spans = extract_md_spans(m["pred"])
        ref_spans = extract_md_spans(ref_data[_id]["ref"])
        _, _, f1 = compute_md_f1(pred_spans, ref_spans, threshold=0.5)
        md_f1_scores.append(f1)

    if missing:
        print(f"Warning: {missing} examples missing from reference file.")

    print("=== Evaluation Results ===")
    print(f"Average SARI: {sum(sari_scores)/len(sari_scores):.4f}")
    print(f"Average FKGL Input: {sum(fkgl_input)/len(fkgl_input):.2f}")
    print(f"Average FKGL Model Output: {sum(fkgl_pred)/len(fkgl_pred):.2f}")
    print(f"Average FKGL Reference: {sum(fkgl_ref)/len(fkgl_ref):.2f}")
    print(f"Average Markdown F1 (bold + headings): {sum(md_f1_scores)/len(md_f1_scores):.4f}")


if __name__ == "__main__":
    # End2end testset
    print("Evaluating End2end Testset:")
    model_file = "testsets/end2end_testset_output_final.jsonl"
    ref_file = "testsets/end2end_test_final.jsonl"
    process(model_file, ref_file)

    # Pipeline testset
    print("\nEvaluating Pipeline Testset:")
    model_file = "testsets/pipeline_testset_output_final.jsonl"
    ref_file = "testsets/highlighter_test_final.jsonl"
    process(model_file, ref_file)
