#!/usr/bin/env python3
"""
Convert a Markdown file to a formatted Google Doc.

Uses Inter font, native Google Docs tables, no horizontal rule dividers.
Supports: headings (h1-h3), bold, italic, code (as bold), bullet lists,
numbered lists, and native tables with bold headers.

Requires: gws CLI (`npm install -g @googleworkspace/cli`) with auth configured.

Usage:
    python3 md_to_gdoc.py report.md --title "My Report"
    python3 md_to_gdoc.py report.md  # title inferred from first H1
    python3 md_to_gdoc.py report.md --update DOC_ID  # update existing doc
"""

import os
import sys
import re
import json
import subprocess
import argparse

FONT = "Inter"


def _gws(*args, input_json=None):
    """Run a gws CLI command and return parsed JSON output."""
    cmd = ["gws"] + list(args)
    kwargs = {"capture_output": True, "text": True}
    if input_json is not None:
        cmd.extend(["--json", json.dumps(input_json)])
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"gws error: {result.stderr}", file=sys.stderr)
        raise RuntimeError(f"gws command failed: {' '.join(cmd)}")
    if result.stdout.strip():
        return json.loads(result.stdout)
    return {}


def _gws_batch_update(doc_id, requests):
    """Execute a batchUpdate via gws CLI."""
    return _gws(
        "docs", "documents", "batchUpdate",
        "--params", json.dumps({"documentId": doc_id}),
        input_json={"requests": requests},
    )


def _gws_get_doc(doc_id):
    """Get a document via gws CLI."""
    return _gws(
        "docs", "documents", "get",
        "--params", json.dumps({"documentId": doc_id}),
    )


def parse_inline(text: str) -> list[dict]:
    """Parse inline markdown (bold, italic, code) into runs."""
    runs = []
    pattern = r'(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|([^*`]+))'
    for match in re.finditer(pattern, text):
        if match.group(2):
            runs.append({"text": match.group(2), "bold": True, "italic": False})
        elif match.group(3):
            runs.append({"text": match.group(3), "bold": False, "italic": True})
        elif match.group(4):
            runs.append({"text": match.group(4), "bold": True, "italic": False})
        elif match.group(5):
            runs.append({"text": match.group(5), "bold": False, "italic": False})
    return runs


def parse_markdown_to_blocks(md_text: str) -> list[dict]:
    """Parse markdown into block dicts. Skips horizontal rules and code blocks."""
    blocks = []
    lines = md_text.split('\n')
    i = 0
    in_code_block = False

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            i += 1
            continue
        if in_code_block:
            i += 1
            continue

        # Skip horizontal rules
        if re.match(r'^---+\s*$', line):
            i += 1
            continue

        # Heading
        m = re.match(r'^(#{1,3})\s+(.+)$', line)
        if m:
            blocks.append({
                "type": "heading",
                "level": len(m.group(1)),
                "runs": parse_inline(m.group(2)),
            })
            i += 1
            continue

        # Table
        if line.strip().startswith('|') and i + 1 < len(lines) and '---' in lines[i + 1]:
            headers = [c.strip() for c in line.strip().strip('|').split('|')]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                rows.append(row)
                i += 1
            blocks.append({"type": "table", "headers": headers, "rows": rows})
            continue

        # Bullet list
        m = re.match(r'^[\s]*[-*]\s+(.+)$', line)
        if m:
            blocks.append({"type": "bullet", "runs": parse_inline(m.group(1))})
            i += 1
            continue

        # Numbered list
        m = re.match(r'^[\s]*\d+\.\s+(.+)$', line)
        if m:
            blocks.append({"type": "numbered", "runs": parse_inline(m.group(1))})
            i += 1
            continue

        # Paragraph
        stripped = line.strip()
        if stripped:
            blocks.append({"type": "paragraph", "runs": parse_inline(stripped)})
        i += 1

    return blocks


def text_blocks_to_parts(blocks: list[dict]) -> list[tuple]:
    """Convert non-table blocks into (text, style_dict) tuples."""
    parts = []
    for block in blocks:
        btype = block["type"]
        heading = block.get("level") if btype == "heading" else None
        is_bullet = btype == "bullet"
        is_numbered = btype == "numbered"

        for run in block["runs"]:
            parts.append((run["text"], {
                "heading": heading, "bullet": is_bullet, "numbered": is_numbered,
                "bold": run["bold"], "italic": run["italic"],
            }))
        parts.append(("\n", {
            "heading": heading, "bullet": is_bullet, "numbered": is_numbered,
            "bold": False, "italic": False,
        }))
    return parts


def build_text_requests(text_parts: list[tuple], start_index: int) -> tuple[list[dict], int]:
    """Build insert + formatting requests. Applies Inter font + bold/italic together."""
    if not text_parts:
        return [], 0

    full_text = "".join(t for t, _ in text_parts)
    if not full_text:
        return [], 0

    requests = [{"insertText": {"location": {"index": start_index}, "text": full_text}}]

    idx = start_index
    for text, style in text_parts:
        end_idx = idx + len(text)

        if text.strip():
            # Apply Inter font + bold/italic in ONE request per run
            ts = {"weightedFontFamily": {"fontFamily": FONT}}
            fields = ["weightedFontFamily"]
            if style["bold"]:
                ts["bold"] = True
                fields.append("bold")
            if style["italic"]:
                ts["italic"] = True
                fields.append("italic")
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": idx, "endIndex": end_idx},
                    "textStyle": ts,
                    "fields": ",".join(fields),
                }
            })

        # Paragraph-level styles
        if text.endswith("\n"):
            text_before = full_text[:idx - start_index]
            last_nl = text_before.rfind('\n')
            para_start = start_index + last_nl + 1 if last_nl >= 0 else start_index

            if style["heading"]:
                hmap = {1: "HEADING_1", 2: "HEADING_2", 3: "HEADING_3"}
                space_above = {1: 24, 2: 18, 3: 12}.get(style["heading"], 12)
                requests.append({
                    "updateParagraphStyle": {
                        "range": {"startIndex": para_start, "endIndex": end_idx},
                        "paragraphStyle": {
                            "namedStyleType": hmap.get(style["heading"], "HEADING_3"),
                            "spaceAbove": {"magnitude": space_above, "unit": "PT"},
                        },
                        "fields": "namedStyleType,spaceAbove",
                    }
                })
            else:
                # Body text / bullets / numbered — add paragraph spacing
                space_above = 3 if (style["bullet"] or style["numbered"]) else 8
                requests.append({
                    "updateParagraphStyle": {
                        "range": {"startIndex": para_start, "endIndex": end_idx},
                        "paragraphStyle": {
                            "spaceAbove": {"magnitude": space_above, "unit": "PT"},
                        },
                        "fields": "spaceAbove",
                    }
                })

            if style["bullet"]:
                requests.append({
                    "createParagraphBullets": {
                        "range": {"startIndex": para_start, "endIndex": end_idx},
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                    }
                })
            if style["numbered"]:
                requests.append({
                    "createParagraphBullets": {
                        "range": {"startIndex": para_start, "endIndex": end_idx},
                        "bulletPreset": "NUMBERED_DECIMAL_NESTED",
                    }
                })

        idx = end_idx

    return requests, len(full_text)


def find_table_element(doc_state, at_or_after):
    """Find the first table element at or after the given index."""
    for el in doc_state['body']['content']:
        if 'table' in el and el.get('startIndex', 0) >= at_or_after:
            return el
    return None


def insert_native_table(doc_id, headers, rows, insert_index):
    """
    Insert a native Google Docs table, fill cells, apply Inter + bold headers.
    Returns the new end index.
    """
    num_cols = len(headers)
    if num_cols == 0:
        return insert_index

    norm_rows = [(row + [""] * num_cols)[:num_cols] for row in rows]
    num_rows = len(norm_rows) + 1

    # 1) Insert empty table
    _gws_batch_update(doc_id, [{"insertTable": {
        "location": {"index": insert_index},
        "rows": num_rows,
        "columns": num_cols,
    }}])

    # 2) Read doc to get cell indices
    doc_state = _gws_get_doc(doc_id)
    table_el = find_table_element(doc_state, insert_index)
    if not table_el:
        print(f"Warning: table not found at index {insert_index}")
        return insert_index

    # 3) Collect cells: (original_start, text, is_header)
    cells = []
    for r_idx, trow in enumerate(table_el['table']['tableRows']):
        for c_idx, tcell in enumerate(trow['tableCells']):
            cell_start = tcell['content'][0]['startIndex']
            if r_idx == 0:
                text = headers[c_idx] if c_idx < num_cols else ""
            else:
                text = norm_rows[r_idx - 1][c_idx]
            cells.append((cell_start, text, r_idx == 0))

    # 4) Build ONE batch: fill (reversed) + Inter font + bold headers
    all_reqs = []

    # Fill in reverse order
    for cs, txt, _ in reversed(cells):
        if txt:
            all_reqs.append({"insertText": {"location": {"index": cs}, "text": txt}})

    # After fills complete, calculate final cell positions.
    cumulative_offset = 0
    for j, (cs, txt, is_header) in enumerate(cells):
        if txt:
            final_start = cs + cumulative_offset
            ts = {"weightedFontFamily": {"fontFamily": FONT}}
            fields = ["weightedFontFamily"]
            if is_header:
                ts["bold"] = True
                fields.append("bold")
            all_reqs.append({
                "updateTextStyle": {
                    "range": {"startIndex": final_start, "endIndex": final_start + len(txt)},
                    "textStyle": ts,
                    "fields": ",".join(fields),
                }
            })
        cumulative_offset += len(txt)

    if all_reqs:
        _gws_batch_update(doc_id, all_reqs)

    total_text_added = sum(len(txt) for _, txt, _ in cells)
    return table_el['endIndex'] + total_text_added


def create_gdoc_from_markdown(md_path: str, title: str = None, update_doc_id: str = None) -> str:
    with open(md_path, 'r') as f:
        md_text = f.read()

    if not title:
        m = re.search(r'^#\s+(.+)$', md_text, re.MULTILINE)
        title = m.group(1) if m else os.path.basename(md_path)

    if update_doc_id:
        doc_id = update_doc_id
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        print(f"Updating Google Doc: {title} ({doc_url})")

        # Get current doc length and delete existing content
        doc = _gws_get_doc(doc_id)
        end_index = doc['body']['content'][-1]['endIndex']
        if end_index > 2:
            _gws_batch_update(doc_id, [{
                'deleteContentRange': {
                    'range': {'startIndex': 1, 'endIndex': end_index - 1}
                }
            }])
    else:
        print(f"Creating Google Doc: {title}")
        doc = _gws("docs", "documents", "create", input_json={"title": title})
        doc_id = doc["documentId"]
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        print(f"Doc created: {doc_url}")

    blocks = parse_markdown_to_blocks(md_text)

    # Group blocks into segments: contiguous text vs tables
    segments = []
    text_buf = []
    for block in blocks:
        if block["type"] == "table":
            if text_buf:
                segments.append({"type": "text", "blocks": text_buf})
                text_buf = []
            segments.append(block)
        else:
            text_buf.append(block)
    if text_buf:
        segments.append({"type": "text", "blocks": text_buf})

    current_index = 1

    for seg_num, segment in enumerate(segments):
        if segment.get("type") == "text":
            parts = text_blocks_to_parts(segment["blocks"])
            reqs, length = build_text_requests(parts, current_index)
            if reqs:
                for i in range(0, len(reqs), 450):
                    _gws_batch_update(doc_id, reqs[i:i + 450])
                current_index += length
            print(f"  [{seg_num + 1}/{len(segments)}] text ({length} chars)")

        elif segment.get("type") == "table":
            end_idx = insert_native_table(
                doc_id,
                segment["headers"], segment["rows"],
                current_index,
            )
            current_index = end_idx
            r = len(segment["rows"])
            c = len(segment["headers"])
            print(f"  [{seg_num + 1}/{len(segments)}] table {r + 1}x{c}")

    table_count = sum(1 for s in segments if s.get("type") == "table")
    print(f"Done: {len(blocks)} blocks, {table_count} native tables")
    print(f"Google Doc URL: {doc_url}")
    return doc_url


def main():
    parser = argparse.ArgumentParser(description="Convert Markdown to Google Doc")
    parser.add_argument("md_file", help="Path to the markdown file")
    parser.add_argument("--title", help="Document title (default: from first H1)")
    parser.add_argument("--update", metavar="DOC_ID", help="Update existing doc instead of creating new")
    args = parser.parse_args()

    url = create_gdoc_from_markdown(args.md_file, args.title, args.update)
    print(f"\nDone: {url}")


if __name__ == "__main__":
    main()
