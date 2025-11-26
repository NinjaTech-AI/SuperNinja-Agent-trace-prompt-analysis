import re
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import tiktoken
from tqdm import tqdm
import argparse

def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze token usage and tool calls from prompts CSV"
    )

    parser.add_argument(
        "--csv-path",
        type=str,
        required=True,
        help="Path to CSV file (with columns: file_path, prompt, role)"
    )

    return parser.parse_args()


# Tokenizer
def build_tokenizer():
    return tiktoken.encoding_for_model("gpt-4o-mini")


def count_tokens(text, enc):
    if not isinstance(text, str):
        return 0
    return len(enc.encode(text))


# Tool-call parsing
TOOL_RESULT_PATTERN = re.compile(
    r"<tool_result>(.*?)</tool_result>",
    re.DOTALL,
)

INNER_TAG_PATTERN = re.compile(
    r"<([a-zA-Z0-9\-_]+)>"
)


def analyze_tool_calls(prompt, enc):
    """Return (total_tool_tokens, first_tool_type) for a single prompt."""
    if not isinstance(prompt, str):
        return 0, None

    total_tool_tokens = 0
    tool_type = None

    matches = TOOL_RESULT_PATTERN.findall(prompt)

    for m in matches:
        inner = m.strip()

        # Skip <str-replace>
        if inner.startswith("<str-replace>"):
            continue

        tag_match = INNER_TAG_PATTERN.search(inner)
        if not tag_match:
            continue

        tag = tag_match.group(1)

        num_tokens = len(enc.encode(inner))
        total_tool_tokens += num_tokens

        if tool_type is None:
            tool_type = tag

    return total_tool_tokens, tool_type


def add_token_columns(df, enc):
    """Add num_token, num_token_from_toolcall, tool_type columns with progress bar."""
    df["num_token"] = df["prompt"].apply(lambda x: count_tokens(x, enc))
    df["num_token_from_toolcall"] = 0
    df["tool_type"] = None

    print("\nAnalyzing tool calls...")
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Processing prompts"):
        tok, tool = analyze_tool_calls(row["prompt"], enc)
        df.at[idx, "num_token_from_toolcall"] = tok
        df.at[idx, "tool_type"] = tool

    return df


def overall_stats(df):
    print("====================================================")
    print("Overall statistics: User vs Assistant")
    print("======================================================\n")

    num_cols = ["num_token", "num_token_from_toolcall"]

    for role in ["user", "assistant"]:
        sub = df.loc[df["role"] == role, num_cols]

        print(f"---- [{role.upper()} Prompt] description ----")
        print(sub.describe().round(2))

        print("\n---- Percentiles ----")
        print(
            sub.quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).round(2)
        )
        print("\n\n")

    total_token = df["num_token"].sum()
    tool_token = df["num_token_from_toolcall"].sum()
    pct_tool = tool_token / total_token * 100 if total_token > 0 else 0.0

    print("------------------------------------------------------")
    print("Overall percentage of tokens from tool calls:")
    print(f"Total number of tokens                      = {total_token:,}")
    print(f"Total number of tokens from tool calls      = {tool_token:,}")
    print(f"Percentage of tokens from tool calls        = {pct_tool:.2f}%")
    print("----------------------------------------------------\n")


def tool_type_stats(df):
    tool_df = df[df["tool_type"].notna()].copy()

    print("======================================================")
    print("Statistics about tool-call type")
    print("====================================================")

    TOP_N = 10

    tool_type_counts = tool_df["tool_type"].value_counts()
    tool_type_pct = tool_type_counts / tool_type_counts.sum() * 100
    tool_type_pct_top = tool_type_pct.head(TOP_N).round(2)

    print(f"\n---- Tool-call type proportion (Top {TOP_N}) -----")
    print(tool_type_pct_top.to_frame("percent (%)"))

    avg_token_by_type = (
        tool_df.groupby("tool_type")["num_token_from_toolcall"]
        .mean()
        .sort_values(ascending=False)
    )

    print("\n----- Average tokens generated from each time of various tool-call -----")
    print(avg_token_by_type.to_frame("avg_num_tokens_generated"))

    # Plot: tool type percentage
    plt.figure(figsize=(16, 6))
    sns.barplot(x=tool_type_pct.index, y=tool_type_pct.values)
    plt.title("Tool type percentage (%)", fontsize=14)
    plt.ylabel("Percent (%)")
    plt.xlabel("Tool type")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()

    # Plot: average tokens per tool type
    plt.figure(figsize=(16, 6))
    sns.barplot(x=avg_token_by_type.index, y=avg_token_by_type.values)
    plt.title("Average tokens generated from each time of various tool-call", fontsize=14)
    plt.ylabel("Average tokens")
    plt.xlabel("Tool type")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()


def analyze_by_file_path(df):
    print("\n=====================================================")
    print("Analysis below is grouped by id/chat")
    print("====================================================\n")

    group = df.groupby("file_path")

    # Tool-call percentage per file_path
    file_tool_pct = (
        group["num_token_from_toolcall"].sum()
        / group["num_token"].sum()
        * 100
    )
    file_tool_pct_df = file_tool_pct.to_frame("tool_call_token_pct")
    file_tool_pct_df = file_tool_pct_df.sort_values(
        "tool_call_token_pct", ascending=False
    )

    # Distribution of tool-call percentage across dialogs
    plt.figure(figsize=(16, 6))
    sns.histplot(file_tool_pct_df["tool_call_token_pct"], bins=30, kde=True)
    plt.title("The distribution of the percentage of tokens from tool-calls out of the total token count", fontsize=14)
    plt.xlabel("Tool-call percentage (%)")
    plt.tight_layout()
    plt.show()

    # Bucketed percentage ranges
    bins = [0, 20, 40, 60, 80, 100]
    labels = ["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"]

    file_tool_pct_df["range_bin"] = pd.cut(
        file_tool_pct_df["tool_call_token_pct"],
        bins=bins,
        labels=labels,
        right=True,
    )

    range_counts = (
        file_tool_pct_df["range_bin"]
        .value_counts()
        .sort_index()
    )

    print("=====================================================")
    print("The percentage occupied by the tokens from tool-call of each complete chat(bucketed)") 
    print("====================================================")
    print(range_counts.to_frame("num_of_chats"))

    # Dominant tool type per file_path
    tool_type_by_file = (
        df[df["tool_type"].notna()]
        .groupby(["file_path", "tool_type"])["num_token_from_toolcall"]
        .sum()
    )

    dominant_tool_type = tool_type_by_file.groupby("file_path").idxmax()

    dominant_tool_type_df = pd.DataFrame(
        {
            "file_path": [fp for fp, _ in dominant_tool_type],
            "dominant_tool_type": [tp for _, tp in dominant_tool_type],
        }
    ).set_index("file_path")

    freq_dominant = dominant_tool_type_df["dominant_tool_type"].value_counts()

    plt.figure(figsize=(16, 6))
    sns.barplot(x=freq_dominant.index, y=freq_dominant.values)
    plt.title("Frequency of dominant tool-call types", fontsize=14)
    plt.ylabel("Number of chats")
    plt.xlabel("Tool-call type")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()

    print("\n====================================================")
    print("Dominant tool-call type per chat (counts)")
    print("=====================================================")
    print(freq_dominant.to_frame("num_of_chats"))


def main():
    args = parse_args()
    csv_path = args.csv_path

    df = pd.read_csv(csv_path)
    enc = build_tokenizer()

    df = add_token_columns(df, enc)

    overall_stats(df)
    tool_type_stats(df)
    analyze_by_file_path(df)


if __name__ == "__main__":
    main()
