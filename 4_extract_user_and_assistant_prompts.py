import json
import csv
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

MAX_THREADS = 24


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract user/assistant prompts from chat_completion JSON files"
    )

    parser.add_argument(
        "--json-root",
        type=str,
        required=True,
        help="Root directory containing decompressed JSON chat files"
    )

    parser.add_argument(
        "--output-csv",
        type=str,
        required=True,
        help="Output CSV path for saving extracted prompts"
    )

    return parser.parse_args()


def normalize_content(content):
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, str):
                if item.strip():
                    parts.append(item.strip())
                continue

            if isinstance(item, dict):
                t = item.get("type")

                if t == "text":
                    text_val = item.get("text")
                    if isinstance(text_val, str) and text_val.strip():
                        parts.append(text_val.strip())
                    continue

                continue

        if parts:
            return "\n".join(parts).strip()

        return None

    return None


def extract_prompts_from_file(file_path: Path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to load {file_path}: {e}")
        return []

    request_obj = data.get("request", {})
    messages = request_obj.get("messages", [])

    results = []

    for msg in messages:
        try:
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue

            raw_content = msg.get("content", "")
            text = normalize_content(raw_content)
            if text:
                results.append((str(file_path), text, role))
        except Exception as e:
            print(f"[WARN] Error parsing message in {file_path}: {e}")
            continue

    return results


def main():
    args = parse_args()

    json_root = Path(args.json_root)
    output_csv = args.output_csv

    json_files = list(json_root.rglob("*_chat_completion.json"))
    print(f"Found {len(json_files)} chat_completion JSON files under {json_root}")

    all_rows = []

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(extract_prompts_from_file, fp): fp for fp in json_files}

        for i, fut in enumerate(as_completed(futures), start=1):
            file_results = fut.result()
            all_rows.extend(file_results)

            if i % 200 == 0:
                print(
                    f"Processed {i}/{len(json_files)} files, "
                    f"collected {len(all_rows)} prompts so far"
                )

    print(f"Finished. Total prompts collected: {len(all_rows)}")

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_path", "prompt", "role"])
        writer.writerows(all_rows)

    print(f"Saved all prompts to {output_csv}")


if __name__ == "__main__":
    main()
