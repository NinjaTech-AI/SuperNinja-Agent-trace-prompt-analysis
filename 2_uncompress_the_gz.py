import gzip
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Decompress all .gz files inside directory recursively")

    parser.add_argument("--download-root", type=str, required=True,
                        help="Root directory that contains downloaded .gz files")
    parser.add_argument("--max-threads", type=int, default=20,
                        help="Maximum number of parallel decompression workers")

    return parser.parse_args()


def decompress_one_gz(gz_path: Path):
    json_path = gz_path.with_suffix("")

    if json_path.exists():
        return True

    try:
        with gzip.open(gz_path, 'rb') as f_in:
            with open(json_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return True

    except Exception:
        return False


def main():
    args = parse_args()

    download_root = Path(args.download_root)
    max_threads = args.max_threads

    gz_files = list(download_root.rglob("*.gz"))
    print(f"Found {len(gz_files)} gz files.")

    success = 0
    failed_files = []

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = {
            executor.submit(decompress_one_gz, gz_path): gz_path
            for gz_path in gz_files
        }

        for future in as_completed(futures):
            gz_file = futures[future]
            ok = future.result()

            if ok:
                success += 1
            else:
                failed_files.append(gz_file)

    print("\n==============================")
    print("        DECOMPRESS SUMMARY")
    print("============================")
    print(f"Number of successful unzip: {success}")
    print(f"Number of failure: {len(failed_files)}")

    if failed_files:
        print("\nFailed files:")
        for f in failed_files:
            print(f)


if __name__ == "__main__":
    main()
