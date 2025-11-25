#!/usr/bin/env python3
"""
Thai Phrases Export with Corrections

Exports all Thai phrases with their correction status and suggested corrections
to facilitate manual review and correction workflow.
"""

import sqlite3
import sys
import csv
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config


def export_phrases_with_corrections():
    """Export all Thai phrases with correction information to CSV"""

    conn = sqlite3.connect(config.DATABASE_PATH)

    try:
        print("📊 Exporting Thai phrases with corrections...")

        # Get all phrases with their correction information
        query = '''
            SELECT
                tp.id,
                tp.phrase,
                tp.word_count,
                tp.confidence_score,
                tp.status,
                tp.needs_correction,
                tp.correction_suggestion,
                tp.context,
                tp.created_at,
                tp.updated_at,
                d.file_name,
                c.name_th as company_name,
                c.name_en as company_name_en
            FROM thai_phrases tp
            LEFT JOIN documents d ON tp.document_id = d.id
            LEFT JOIN fiscal_years fy ON d.fiscal_year_id = fy.id
            LEFT JOIN companies c ON fy.company_id = c.id
            ORDER BY
                CASE WHEN tp.needs_correction = 1 THEN 1 ELSE 2 END,
                tp.confidence_score ASC,
                tp.id
        '''

        cursor = conn.cursor()
        cursor.execute(query)
        phrases = cursor.fetchall()

        # Get dictionary corrections for reference
        corrections_query = '''
            SELECT
                error_pattern,
                correction,
                type,
                priority,
                confidence,
                frequency,
                created_at
            FROM thai_ocr_corrections
            WHERE is_active = 1
            ORDER BY priority, frequency DESC
        '''

        cursor.execute(corrections_query)
        corrections = cursor.fetchall()

        print(f"📈 Found {len(phrases)} total phrases")

        # Count phrases needing correction
        needs_correction_count = sum(1 for phrase in phrases if phrase[5])  # needs_correction is index 5
        print(f"🔧 {needs_correction_count} phrases marked for correction")
        print(f"📚 {len(corrections)} dictionary corrections available")

        # Create a dictionary mapping for fast lookups
        correction_map = {correction[0]: correction for correction in corrections}

        # Create comprehensive export data
        export_data = []
        needs_review_data = []

        for phrase in phrases:
            (phrase_id, phrase_text, word_count, confidence_score, status, needs_correction,
             correction_suggestion, context, created_at, updated_at, file_name,
             company_name, company_name_en) = phrase

            # Try to find exact match in dictionary corrections
            dict_correction = correction_map.get(phrase_text)

            # Determine final correction and source
            if dict_correction:
                final_correction = dict_correction[1]  # correction text
                correction_source = f"dictionary_{dict_correction[2]}"  # type
            elif correction_suggestion:
                final_correction = correction_suggestion
                correction_source = 'phrase_suggestion'
            elif needs_correction:
                final_correction = None
                correction_source = 'needs_manual_review'
            else:
                final_correction = None
                correction_source = 'no_correction_needed'

            export_row = {
                'phrase_id': phrase_id,
                'original_phrase': phrase_text,
                'word_count': word_count,
                'confidence_score': confidence_score,
                'status': status,
                'needs_correction': needs_correction,
                'correction_suggestion': correction_suggestion,
                'final_correction': final_correction,
                'correction_source': correction_source,
                'context': context,
                'company_name': company_name,
                'company_name_en': company_name_en,
                'file_name': file_name,
                'created_at': created_at,
                'updated_at': updated_at
            }

            export_data.append(export_row)

            # Also add to review-only list if it needs correction
            if needs_correction:
                needs_review_data.append(export_row)

        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export all phrases
        csv_filename = f"data/exports/thai_phrases_corrections_{timestamp}.csv"
        csv_path = Path(config.PROJECT_ROOT) / csv_filename
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = list(export_data[0].keys()) if export_data else []

        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in export_data:
                writer.writerow(row)

        print(f"✅ Complete CSV exported to: {csv_path}")

        # Export only phrases needing correction
        review_filename = f"data/exports/thai_phrases_needs_review_{timestamp}.csv"
        review_path = Path(config.PROJECT_ROOT) / review_filename

        with open(review_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in needs_review_data:
                writer.writerow(row)

        print(f"📝 Review-only CSV exported to: {review_path}")

        # Export dictionary corrections reference
        dict_filename = f"data/exports/dictionary_corrections_{timestamp}.csv"
        dict_path = Path(config.PROJECT_ROOT) / dict_filename

        dict_fieldnames = ['error_pattern', 'correction', 'type', 'priority', 'confidence', 'frequency', 'created_at']

        with open(dict_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=dict_fieldnames)
            writer.writeheader()
            for correction in corrections:
                writer.writerow({
                    'error_pattern': correction[0],
                    'correction': correction[1],
                    'type': correction[2],
                    'priority': correction[3],
                    'confidence': correction[4],
                    'frequency': correction[5],
                    'created_at': correction[6]
                })

        print(f"📚 Dictionary corrections exported to: {dict_path}")

        return csv_path, review_path, dict_path

    except Exception as e:
        print(f"❌ Error during export: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

    finally:
        conn.close()


def main():
    """Main execution function"""
    print("🚀 Thai Phrases Export with Corrections")
    print("=" * 50)

    try:
        # Export comprehensive data
        export_path, review_path, dict_path = export_phrases_with_corrections()

        # Print summary
        print(f"\n📊 EXPORT SUMMARY:")
        print(f"   Complete phrases export: {export_path.name if export_path else 'Failed'}")
        print(f"   Review-only export: {review_path.name if review_path else 'Failed'}")
        print(f"   Dictionary corrections: {dict_path.name if dict_path else 'Failed'}")

        print(f"\n🎯 NEXT STEPS:")
        print(f"1. Open the review-only CSV for focused correction work")
        print(f"2. Review phrases marked as 'needs_manual_review'")
        print(f"3. Use the dictionary corrections reference for patterns")
        print(f"4. Update corrections in the Dictionary Management page")
        print(f"5. Re-run export to track progress")

        return export_path, review_path, dict_path

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


if __name__ == "__main__":
    main()