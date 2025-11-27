from pathlib import Path
import pandas as pd
import argparse


ID_COL = "id"
AGENT_TYPE_COL = "agent_type"
MODE_COL = "agent_execution_mode"


def parse_args():
    parser = argparse.ArgumentParser(description="Match IDs on disk with CSV and show distributions")

    parser.add_argument("--data-root", type=str, required=True,
                        help="Root directory that contains ID folders or JSON files")
    parser.add_argument("--csv-path", type=str, required=True,
                        help="Path to CSV file containing ID and metadata fields")

    return parser.parse_args()


def collect_ids_from_data_root(data_root: Path):
    ids = set()

    for child in data_root.iterdir():
        if child.is_dir():
            ids.add(child.name)
        elif child.is_file():
            ids.add(child.stem)

    return ids


def main():
    args = parse_args()

    data_root = Path(args.data_root)
    csv_path = Path(args.csv_path)

    if not data_root.exists():
        raise FileNotFoundError(f"DATA_ROOT does not exist: {data_root}")

    ids_on_disk = collect_ids_from_data_root(data_root)
    print(f"Found {len(ids_on_disk)} IDs in local data directory.")

    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from CSV. Columns: {list(df.columns)}")

    for col in [ID_COL, AGENT_TYPE_COL, MODE_COL]:
        if col not in df.columns:
            raise KeyError(f"Column '{col}' not found in CSV. available columns: {list(df.columns)}")

    df_sub = df[df[ID_COL].isin(ids_on_disk)].copy()
    print(f"Matched {len(df_sub)} rows between local data and CSV IDs.")

    print("\n===== Distribution: agent type =====")
    print(df_sub[AGENT_TYPE_COL].value_counts(dropna=False))

    print("\n===== Distribution: agent_execution_mode =====")
    print(df_sub[MODE_COL].value_counts(dropna=False))

    # This is the joint distribution
    print("\n===== Joint Distribution: agent type × agent_execution_mode =====")
    ctab = pd.crosstab(df_sub[AGENT_TYPE_COL], df_sub[MODE_COL], dropna=False)
    print(ctab)


if __name__ == "__main__":
    main()
