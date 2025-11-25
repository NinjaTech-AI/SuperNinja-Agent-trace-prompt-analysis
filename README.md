# Agent Trace & Prompt Analysis

This repo contains a small pipeline to download agent trace logs from S3, decompress them,
summarise their agent configuration, and analyse prompt/token usage.

The scripts are intentionally simple and focused on CLI usage.

## Environment

- Python 3.10.11 (tested with pyenv on macOS)
- macOS
- pyenv (optional but recommended)

You can adapt the instructions below to your own OS if needed.

## Installation

1. Clone this repo

2. (Optional) Select Python with pyenv
pyenv local 3.10.11

3. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate         
          
4. Install dependencies
pip install -r requirements.txt

## Script Order
