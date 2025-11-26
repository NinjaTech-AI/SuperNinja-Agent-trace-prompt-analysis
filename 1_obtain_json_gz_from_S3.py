import argparse
import csv
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore.exceptions import ClientError
from tqdm import tqdm

csv.field_size_limit(sys.maxsize)



def parse_args():
    parser = argparse.ArgumentParser(description="Download latest .gz trace files from S3 based on ID list in CSV")

    parser.add_argument("--csv-path", type=str, required=True, default=None,
                        help="Path to CSV file containing IDs")
    parser.add_argument("--id-column", type=str, default="id",
                        help="Column name in CSV that contains IDs")
    parser.add_argument("--download-root", type=str, required=True, default=None,
                        help="Local root directory to store downloaded files")
    parser.add_argument("--bucket-name", type=str, default="ninja-task-trace-beta",
                        help="S3 bucket name")
    parser.add_argument("--region-name", type=str, default="us-west-2",
                        help="AWS region of the S3 bucket")
    parser.add_argument("--max-threads", type=int, default=30,
                        help="Maximum number of parallel download threads")

    return parser.parse_args()


def load_ids_from_csv(csv_path, id_column):
    ids = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            id_value = row[id_column].strip()
            if id_value:
                ids.append(id_value)
    return ids


def find_latest_gz_for_id(s3_client, bucket, prefix):
    paginator = s3_client.get_paginator("list_objects_v2")
    latest_obj = None

    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            contents = page.get("Contents", [])
            for obj in contents:
                key = obj["Key"]
                if key.endswith(".gz"):
                    if latest_obj is None or obj["LastModified"] > latest_obj["LastModified"]:
                        latest_obj = obj

    except ClientError:
        return None

    return latest_obj


def download_one_id(id_value, bucket, region, download_root):
    session = boto3.Session()
    s3 = session.client("s3", region_name=region)

    prefix = id_value
    latest_obj = find_latest_gz_for_id(s3, bucket, prefix)

    if latest_obj is None:
        return (id_value, False)

    key = latest_obj["Key"]
    filename = os.path.basename(key)
    local_dir = Path(download_root) / id_value
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / filename

    if local_path.exists():
        return (id_value, True)

    try:
        s3.download_file(bucket, key, str(local_path))
        return (id_value, True)
    except:
        return (id_value, False)


def main():
    args = parse_args()

    download_root = Path(args.download_root)
    download_root.mkdir(parents=True, exist_ok=True)

    ids = load_ids_from_csv(args.csv_path, args.id_column)
    print(f"Loaded {len(ids)} ids.")

    success_ids = []
    missing_ids = []

    with ThreadPoolExecutor(max_workers=args.max_threads) as executor:
        futures = {
            executor.submit(download_one_id, id_value, args.bucket_name, args.region_name, download_root): id_value
            for id_value in ids
        }

        for future in tqdm(as_completed(futures), total=len(futures), desc="Downloading"):
            id_value = futures[future]
            ok = future.result()

            if ok[1]:
                success_ids.append(id_value)
            else:
                missing_ids.append(id_value)

    print("\n============================")
    print("          SUMMARY")
    print("================================")
    print(f"Number of Successful Downloads: {len(success_ids)}")
    print(f"Number of Invalid IDs: {len(missing_ids)}")

    if missing_ids:
        output_file = download_root.parent / "missing_ids.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            for mid in missing_ids:
                f.write(mid + "\n")

        print(f"\nInvalid IDs saved to:")
        print(output_file)


if __name__ == "__main__":
    main()
