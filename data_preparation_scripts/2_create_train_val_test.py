import os
import shutil
import random
import re

# --------------------------
# CONFIGURATION
# --------------------------
DATASETS = {
    "original": "dataset_original",
    "simple": "dataset_simple",
    "highlighted": "dataset_highlighted"
}

TRAIN_RATIO = 0.8
VAL_RATIO = 0.1
TEST_RATIO = 0.1
SEED = 42

# --------------------------
# SETUP
# --------------------------
random.seed(SEED)

# Regex patterns to extract IDs
AS_PATTERN = re.compile(r"(\d+)_AS\.md$")
LS_PATTERN = re.compile(r"(\d+)_LS\.md$")

# --------------------------
# COLLECT FILE IDS
# --------------------------
def get_ids_from_folder(base_path, pattern, recursive=False):
    ids = set()
    if recursive:
        for root, dirs, files in os.walk(base_path):
            for f in files:
                m = pattern.match(f)
                if m:
                    ids.add(m.group(1))
    else:
        for f in os.listdir(base_path):
            m = pattern.match(f)
            if m:
                ids.add(m.group(1))
    return ids

ids_original = get_ids_from_folder(DATASETS["original"], AS_PATTERN, recursive=False)
ids_simple = get_ids_from_folder(DATASETS["simple"], LS_PATTERN, recursive=True)
ids_highlighted = get_ids_from_folder(DATASETS["highlighted"], LS_PATTERN, recursive=True)

# Only keep IDs present in all three
common_ids = sorted(list(ids_original & ids_simple & ids_highlighted))
print(f"Found {len(common_ids)} fully aligned triples.")

# Shuffle and split
random.shuffle(common_ids)
n_total = len(common_ids)
n_train = int(n_total * TRAIN_RATIO)
n_val = int(n_total * VAL_RATIO)

train_ids = common_ids[:n_train]
val_ids = common_ids[n_train:n_train + n_val]
test_ids = common_ids[n_train + n_val:]

print(f"Train: {len(train_ids)} | Val: {len(val_ids)} | Test: {len(test_ids)}")

# --------------------------
# CREATE SPLIT FOLDERS
# --------------------------
for ds_name, ds_path in DATASETS.items():
    for split in ["train", "val", "test"]:
        split_dir = os.path.join(ds_path, split)
        os.makedirs(split_dir, exist_ok=True)

# --------------------------
# COPY FILES BY ID (merge LS .md + .json into split folders)
# --------------------------
def copy_by_ids(id_list, split_name):
    for id_ in id_list:
        orig_file = f"{id_}_AS.md"
        ls_file = f"{id_}_LS.md"
        for ds_name, ds_path in DATASETS.items():
            # Determine target file
            target_file = orig_file if ds_name == "original" else ls_file

            # Determine search method
            recursive = ds_name != "original"

            src_path = None
            if recursive:
                for root, dirs, files in os.walk(ds_path):
                    if target_file in files:
                        src_path = os.path.join(root, target_file)
                        break
            else:
                if os.path.exists(os.path.join(ds_path, target_file)):
                    src_path = os.path.join(ds_path, target_file)

            if src_path:
                dest_dir = os.path.join(ds_path, split_name)
                shutil.copy2(src_path, dest_dir)

                # If LS file, also copy the corresponding .json
                if ds_name != "original":
                    json_file = os.path.splitext(target_file)[0] + ".json"
                    json_src_path = os.path.join(os.path.dirname(src_path), json_file)
                    if os.path.exists(json_src_path):
                        shutil.copy2(json_src_path, dest_dir)
            else:
                print(f"⚠️ Missing file {target_file} in {ds_path}")

copy_by_ids(train_ids, "train")
copy_by_ids(val_ids, "val")
copy_by_ids(test_ids, "test")

print("✅ All datasets split successfully!")

# --------------------------
# VERIFY ALIGNMENT
# --------------------------
def verify_alignment():
    print("\n🔍 Verifying alignment across datasets...")
    all_ok = True
    for split in ["train", "val", "test"]:
        split_ids = {}
        for ds_name, ds_path in DATASETS.items():
            split_dir = os.path.join(ds_path, split)
            files = [f for f in os.listdir(split_dir) if f.endswith(".md")]
            # extract IDs for each dataset
            pattern = AS_PATTERN if ds_name == "original" else LS_PATTERN
            split_ids[ds_name] = set()
            for f in files:
                m = pattern.match(f)
                if m:
                    split_ids[ds_name].add(m.group(1))

        common = set.intersection(*split_ids.values())
        for ds_name, ids in split_ids.items():
            missing = common.symmetric_difference(ids)
            if missing:
                all_ok = False
                print(f"⚠️ Mismatch in {ds_name}/{split}: {sorted(list(missing))[:5]}{'...' if len(missing) > 5 else ''}")

        print(f"{split.upper()}: {len(common)} aligned triples")

    if all_ok:
        print("\n✅ All splits are perfectly aligned!")
    else:
        print("\n⚠️ Some misalignments detected — check warnings above.")

verify_alignment()
