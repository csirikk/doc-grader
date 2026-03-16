#!/usr/bin/env bash
# Rename .pdf files that are actually Markdown submissions to .md,
# based on the doc_type column in the grader CSVs.
#
# Usage:
#   ./scripts/fix_md.sh          # dry run
#   ./scripts/fix_md.sh --apply  # actually rename

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOCS_DIR="$ROOT_DIR/data/ipp_13_to_24/ipp_docs"
ASSE_DIR="$ROOT_DIR/data/ipp_13_to_24/ipp_assessments"
PYTHON="$ROOT_DIR/.venv/bin/python3"

DRY_RUN=true
if [[ "${1:-}" == "--apply" ]]; then
    DRY_RUN=false
fi

renamed=0
missing=0

for csv in "$ASSE_DIR"/ipp*.csv; do
    variant=$(basename "$csv" .csv)   # 'ipp20-int'
    docs_subdir="$DOCS_DIR/$variant"

    if [[ ! -d "$docs_subdir" ]]; then
        echo "no docs dir for $variant, skipping"
        continue
    fi

    # Extract IDs where doc_type == 'md'
    while IFS= read -r id; do
        [[ -z "$id" ]] && continue
        src="$docs_subdir/${id}.pdf"
        dst="$docs_subdir/${id}.md"

        if [[ -f "$src" ]]; then
            if $DRY_RUN; then
                echo " would rename $variant/${id}.pdf -> .md"
            else
                mv "$src" "$dst"
                echo " renamed $variant/${id}.pdf -> .md"
            fi
            renamed=$((renamed + 1))
        else
            echo " MISSING $variant/${id}.pdf"
            missing=$((missing + 1))
        fi
    done < <("$PYTHON" - "$csv" <<'PYEOF'
import sys, pandas as pd
csv = sys.argv[1]
df = pd.read_csv(csv)
if 'doc_type' in df.columns and 'id' in df.columns:
    for i in df.loc[df['doc_type'] == 'md', 'id'].dropna(): # skip missing
        print(i)
PYEOF
)
done

echo ""
if $DRY_RUN; then
    echo "Dry run done: $renamed files would be renamed, $missing missing."
else
    echo "Done: renamed $renamed files, $missing missing."
fi
