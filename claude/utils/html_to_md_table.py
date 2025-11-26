"""
HTML Table to Markdown Table Converter

Converts HTML tables in OCR output to markdown table format.
Note: Merged cells (colspan/rowspan) will be flattened.
"""

import re
from html.parser import HTMLParser
from typing import List, Optional


class HTMLTableParser(HTMLParser):
    """Parse HTML table into rows and cells."""

    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = ""
        self.in_table = False
        self.in_row = False
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
            self.current_table = []
        elif tag == 'tr':
            self.in_row = True
            self.current_row = []
        elif tag in ('td', 'th'):
            self.in_cell = True
            self.current_cell = ""
        elif tag == 'br' and self.in_cell:
            self.current_cell += " "

    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
            if self.current_table:
                self.tables.append(self.current_table)
            self.current_table = []
        elif tag == 'tr':
            self.in_row = False
            if self.current_row:
                self.current_table.append(self.current_row)
            self.current_row = []
        elif tag in ('td', 'th'):
            self.in_cell = False
            # Clean up cell content
            cell = self.current_cell.strip()
            cell = re.sub(r'\s+', ' ', cell)  # Normalize whitespace
            self.current_row.append(cell)
            self.current_cell = ""

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data


def html_table_to_markdown(html_table: str) -> str:
    """
    Convert a single HTML table to markdown format.

    Args:
        html_table: HTML table string

    Returns:
        Markdown table string
    """
    parser = HTMLTableParser()
    parser.feed(html_table)

    if not parser.tables:
        return html_table  # Return original if parsing failed

    table = parser.tables[0]
    if not table:
        return ""

    # Find max columns
    max_cols = max(len(row) for row in table)

    # Normalize rows to same column count
    normalized = []
    for row in table:
        while len(row) < max_cols:
            row.append("")
        normalized.append(row)

    if not normalized:
        return ""

    # Build markdown table
    lines = []

    # Header row
    header = normalized[0]
    lines.append("| " + " | ".join(header) + " |")

    # Separator
    lines.append("| " + " | ".join(["---"] * max_cols) + " |")

    # Data rows
    for row in normalized[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def convert_tables_in_text(text: str) -> str:
    """
    Find all HTML tables in text and convert them to markdown.

    Args:
        text: Text containing HTML tables

    Returns:
        Text with HTML tables converted to markdown
    """
    # Pattern to match HTML tables
    table_pattern = re.compile(r'<table>.*?</table>', re.DOTALL | re.IGNORECASE)

    def replace_table(match):
        html_table = match.group(0)
        md_table = html_table_to_markdown(html_table)
        return "\n\n" + md_table + "\n\n"

    return table_pattern.sub(replace_table, text)


def convert_ocr_file(input_path: str, output_path: Optional[str] = None) -> str:
    """
    Convert HTML tables in an OCR result file to markdown tables.

    Args:
        input_path: Path to input markdown file with HTML tables
        output_path: Path for output file (optional, defaults to _mdtable.md suffix)

    Returns:
        Path to output file
    """
    from pathlib import Path

    input_file = Path(input_path)

    if output_path is None:
        output_path = input_file.parent / (input_file.stem + "_mdtable.md")

    # Read input
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Convert tables
    converted = convert_tables_in_text(content)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(converted)

    return str(output_path)


# Example usage
if __name__ == "__main__":
    # Test with sample HTML table
    sample = """
    Some text before.

    <table><tr><td>Header 1</td><td>Header 2</td></tr><tr><td>Data 1</td><td>Data 2</td></tr></table>

    Some text after.
    """

    result = convert_tables_in_text(sample)
    print("Converted output:")
    print(result)
