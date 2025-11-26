#!/usr/bin/env python3
"""
Typhoon OCR Test Script for Y67 Documents

Tests Typhoon OCR API on sample PDF files from Y67 folder.
Results are saved in markdown format.

Rate limits: 2 req/s, 20 req/min - script includes delays to respect limits.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Verify API key is loaded
api_key = os.getenv('TYPHOON_OCR_API_KEY')
if not api_key:
    print("ERROR: TYPHOON_OCR_API_KEY not found in environment")
    print(f"Checked .env file at: {env_path}")
    sys.exit(1)

print(f"✓ API key loaded (ending in ...{api_key[-4:]})")

# Import typhoon_ocr after setting env var
from typhoon_ocr import ocr_document


def get_sample_files(y67_path: Path, samples_per_company: int = 2) -> list:
    """
    Get sample PDF files from Y67 folder.
    Selects a few files from each company folder for testing.
    PDFs are nested in year folders (Y58, Y61, Y67, etc.) within company folders.
    """
    sample_files = []

    if not y67_path.exists():
        print(f"ERROR: Y67 folder not found at {y67_path}")
        return sample_files

    # Get all company folders
    company_folders = [f for f in y67_path.iterdir() if f.is_dir()]
    print(f"Found {len(company_folders)} company folders")

    for company_folder in sorted(company_folders):
        # Search recursively for PDFs (they're in year subfolders like Y67/)
        pdf_files = list(company_folder.glob("**/*.pdf"))
        if pdf_files:
            # Prefer Y67 folder if available, otherwise take first N files
            y67_files = [f for f in pdf_files if '/Y67/' in str(f)]
            if y67_files:
                selected = y67_files[:samples_per_company]
            else:
                selected = pdf_files[:samples_per_company]
            sample_files.extend(selected)
            print(f"  {company_folder.name[:40]}...: {len(selected)} files selected")

    return sample_files


def run_ocr_test(pdf_path: Path, output_dir: Path) -> dict:
    """
    Run Typhoon OCR on a single PDF file.
    Saves result to individual markdown file.
    Returns dict with results and timing info.
    """
    result = {
        'file': pdf_path.name,
        'folder': pdf_path.parent.name,
        'company': pdf_path.parent.parent.name,
        'path': str(pdf_path),
        'success': False,
        'text': '',
        'error': '',
        'time_seconds': 0,
        'char_count': 0,
        'output_file': '',
    }

    start_time = time.time()

    try:
        # Run OCR on first page
        markdown_text = ocr_document(
            pdf_or_image_path=str(pdf_path),
            page_num=1
        )

        result['success'] = True
        result['text'] = markdown_text
        result['char_count'] = len(markdown_text) if markdown_text else 0

        # Save to individual markdown file
        if markdown_text:
            # Create output filename from PDF name
            md_filename = pdf_path.stem + "_ocr.md"
            md_path = output_dir / md_filename

            # Write individual markdown file
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(f"# OCR Result: {pdf_path.name}\n\n")
                f.write(f"**Source:** {pdf_path}\n")
                f.write(f"**Company:** {result['company']}\n")
                f.write(f"**Processed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**Model:** typhoon-ocr v1.5\n\n")
                f.write("---\n\n")
                f.write(markdown_text)

            result['output_file'] = str(md_path)

    except Exception as e:
        result['error'] = str(e)
        print(f"  ERROR: {e}")

    result['time_seconds'] = round(time.time() - start_time, 2)
    return result


def generate_markdown_report(results: list, output_path: Path):
    """
    Generate markdown report from OCR results.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Calculate statistics
    total = len(results)
    successful = sum(1 for r in results if r['success'])
    failed = total - successful
    total_chars = sum(r['char_count'] for r in results)
    total_time = sum(r['time_seconds'] for r in results)
    avg_time = total_time / total if total > 0 else 0

    # Group by company folder
    by_company = {}
    for r in results:
        company = r['folder']
        if company not in by_company:
            by_company[company] = []
        by_company[company].append(r)

    # Generate report
    lines = [
        "# Typhoon OCR Test Results",
        "",
        f"**Date:** {timestamp}",
        f"**Model:** typhoon-ocr (v1.5, 2B parameters)",
        f"**Source:** Y67 Thai Financial Documents",
        "",
        "---",
        "",
        "## Summary Statistics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Files Tested | {total} |",
        f"| Successful | {successful} ({100*successful/total:.1f}%) |",
        f"| Failed | {failed} |",
        f"| Total Characters Extracted | {total_chars:,} |",
        f"| Total Processing Time | {total_time:.1f}s |",
        f"| Average Time per File | {avg_time:.2f}s |",
        "",
        "---",
        "",
        "## Results by Company",
        "",
    ]

    for company, company_results in sorted(by_company.items()):
        lines.append(f"### {company}")
        lines.append("")

        for r in company_results:
            status = "✅" if r['success'] else "❌"
            lines.append(f"#### {status} {r['file']}")
            lines.append("")
            lines.append(f"- **Processing Time:** {r['time_seconds']}s")
            lines.append(f"- **Characters Extracted:** {r['char_count']:,}")

            if r['success'] and r['text']:
                # Show preview of extracted text (first 500 chars)
                preview = r['text'][:500]
                if len(r['text']) > 500:
                    preview += "..."
                lines.append("")
                lines.append("**Extracted Text Preview:**")
                lines.append("```")
                lines.append(preview)
                lines.append("```")
            elif r['error']:
                lines.append(f"- **Error:** {r['error']}")

            lines.append("")

    # Add full OCR outputs section
    lines.extend([
        "---",
        "",
        "## Full OCR Outputs",
        "",
        "Complete OCR results for each successfully processed file.",
        "",
    ])

    for r in results:
        if r['success'] and r['text']:
            lines.append(f"### {r['folder']} / {r['file']}")
            lines.append("")
            lines.append("```markdown")
            lines.append(r['text'])
            lines.append("```")
            lines.append("")

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"\n✓ Report saved to: {output_path}")


def main():
    """Main test execution."""
    print("\n" + "="*60)
    print("Typhoon OCR Test - Y67 Thai Financial Documents")
    print("="*60 + "\n")

    # Paths
    base_path = Path(__file__).parent.parent.parent  # ocr-prototype
    y67_path = base_path / "Y67"
    output_dir = base_path / "claude" / "claudedocs" / "typhoon_ocr_results"
    summary_path = output_dir / "_summary.md"

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Y67 Path: {y67_path}")
    print(f"Output Dir: {output_dir}")
    print()

    # Get sample files (2 per company to stay within rate limits)
    sample_files = get_sample_files(y67_path, samples_per_company=2)

    if not sample_files:
        print("ERROR: No sample files found")
        sys.exit(1)

    print(f"\nTotal files to test: {len(sample_files)}")
    print(f"Estimated time: ~{len(sample_files) * 5}s (with rate limiting)")
    print()

    # Run OCR tests with rate limiting
    results = []
    for i, pdf_path in enumerate(sample_files, 1):
        print(f"[{i}/{len(sample_files)}] Processing: {pdf_path.parent.name}/{pdf_path.name}")

        result = run_ocr_test(pdf_path, output_dir)
        results.append(result)

        if result['success']:
            print(f"  ✓ {result['char_count']:,} chars in {result['time_seconds']}s → {Path(result['output_file']).name}")
        else:
            print(f"  ✗ Failed: {result['error'][:50]}...")

        # Rate limiting: wait between requests (2 req/s max, 20 req/min)
        if i < len(sample_files):
            # Wait 3 seconds between requests to be safe with rate limits
            time.sleep(3)

    # Generate summary report
    print("\nGenerating summary report...")
    generate_markdown_report(results, summary_path)

    # Print summary
    successful = sum(1 for r in results if r['success'])
    print(f"\n{'='*60}")
    print(f"Test Complete: {successful}/{len(results)} files processed successfully")
    print(f"Individual MD files saved to: {output_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
