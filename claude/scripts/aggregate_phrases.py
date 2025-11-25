#!/usr/bin/env python3
"""
Thai Phrase Aggregation and Deduplication

Aggregates duplicate phrases across similar financial template documents
to reduce the review workload while preserving context and source information.
"""

import sqlite3
import sys
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config


def aggregate_duplicate_phrases():
    """Aggregate duplicate phrases across documents to reduce review workload"""

    conn = sqlite3.connect(config.DATABASE_PATH)

    try:
        print("🔄 Aggregating duplicate phrases from financial templates...")

        # Get all phrases with their document information
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
                d.id as document_id,
                d.file_name,
                c.name_th as company_name,
                c.name_en as company_name_en
            FROM thai_phrases tp
            LEFT JOIN documents d ON tp.document_id = d.id
            LEFT JOIN fiscal_years fy ON d.fiscal_year_id = fy.id
            LEFT JOIN companies c ON fy.company_id = c.id
            ORDER BY tp.phrase, tp.confidence_score
        '''

        cursor = conn.cursor()
        cursor.execute(query)
        phrases = cursor.fetchall()

        print(f"📈 Found {len(phrases)} total phrases before deduplication")

        # Get dictionary corrections for reference
        corrections_query = '''
            SELECT error_pattern, correction, type
            FROM thai_ocr_corrections
            WHERE is_active = 1
        '''
        cursor.execute(corrections_query)
        corrections = cursor.fetchall()
        correction_map = {correction[0]: correction for correction in corrections}

        # Group phrases by their text content
        phrase_groups = defaultdict(list)

        for phrase in phrases:
            (phrase_id, phrase_text, word_count, confidence_score, status, needs_correction,
             correction_suggestion, context, created_at, updated_at, document_id, file_name,
             company_name, company_name_en) = phrase

            phrase_groups[phrase_text].append({
                'phrase_id': phrase_id,
                'confidence_score': confidence_score,
                'word_count': word_count,
                'status': status,
                'needs_correction': needs_correction,
                'correction_suggestion': correction_suggestion,
                'context': context,
                'document_id': document_id,
                'file_name': file_name,
                'company_name': company_name,
                'company_name_en': company_name_en,
                'created_at': created_at,
                'updated_at': updated_at
            })

        print(f"🔄 Grouped into {len(phrase_groups)} unique phrase groups")

        # Analyze phrase distribution
        group_sizes = [len(group) for group in phrase_groups.values()]
        size_distribution = Counter(group_sizes)

        print(f"📊 Phrase duplication analysis:")
        for size, count in sorted(size_distribution.items()):
            print(f"   {size} occurrences: {count} unique phrases ({size * count} total instances)")

        total_duplicates = sum((size - 1) * count for size, count in size_distribution.items() if size > 1)
        print(f"🔢 Total duplicate instances: {total_duplicates}")

        # Create aggregated dataset
        aggregated_data = []
        review_reduction_stats = {
            'original_phrases': len(phrases),
            'unique_phrases': len(phrase_groups),
            'reduced_by': len(phrases) - len(phrase_groups),
            'reduction_percentage': ((len(phrases) - len(phrase_groups)) / len(phrases)) * 100
        }

        for phrase_text, group in phrase_groups.items():
            # Find the best representative phrase from the group
            # Prioritize: 1) Highest confidence, 2) Has correction suggestion, 3) Most recent

            def get_priority_score(x):
                score = 0
                score += (x['confidence_score'] or 0) * 1000
                score += 100 if x['correction_suggestion'] else 0
                # Use string representation for dates to avoid comparison issues
                score += 10 if x['updated_at'] and x['updated_at'] != '' else 0
                score += 5 if x['created_at'] and x['created_at'] != '' else 0
                return score

            best_phrase = max(group, key=get_priority_score)

            # Collect all document sources
            source_documents = []
            companies = set()

            for instance in group:
                if instance['file_name']:
                    source_documents.append(instance['file_name'])
                if instance['company_name']:
                    companies.add(instance['company_name'])
                if instance['company_name_en']:
                    companies.add(instance['company_name_en'])

            # Determine if any instance in the group needs correction
            any_needs_correction = any(instance['needs_correction'] for instance in group)
            any_has_suggestion = any(instance['correction_suggestion'] for instance in group)

            # Try to find dictionary correction
            dict_correction = correction_map.get(phrase_text)

            # Determine final correction and source
            if dict_correction:
                final_correction = dict_correction[1]
                correction_source = f"dictionary_{dict_correction[2]}"
            elif any_has_suggestion:
                # Use suggestion from the best instance
                final_correction = best_phrase['correction_suggestion']
                correction_source = 'phrase_suggestion'
            elif any_needs_correction:
                final_correction = None
                correction_source = 'needs_manual_review'
            else:
                final_correction = None
                correction_source = 'no_correction_needed'

            # Create aggregated entry
            aggregated_entry = {
                'phrase_text': phrase_text,
                'group_size': len(group),
                'confidence_score': best_phrase['confidence_score'],
                'word_count': best_phrase['word_count'],
                'status': best_phrase['status'],
                'needs_correction': any_needs_correction,
                'correction_suggestion': best_phrase['correction_suggestion'],
                'final_correction': final_correction,
                'correction_source': correction_source,
                'source_documents': '; '.join(sorted(set(source_documents))),
                'unique_companies': '; '.join(sorted(companies)),
                'total_instances': len(group),
                'best_phrase_id': best_phrase['phrase_id'],
                'best_file_name': best_phrase['file_name'],
                'context': best_phrase['context'],
                'created_at': best_phrase['created_at'],
                'updated_at': best_phrase['updated_at']
            }

            aggregated_data.append(aggregated_entry)

        # Sort aggregated data
        # Priority: needs_correction (True first), confidence_score (low first), group_size (high first)
        aggregated_data.sort(key=lambda x: (
            not x['needs_correction'],  # False sorts before True, so we invert
            x['confidence_score'] or 999,
            -x['group_size']  # Higher groups first
        ))

        return aggregated_data, review_reduction_stats

    except Exception as e:
        print(f"❌ Error during aggregation: {e}")
        import traceback
        traceback.print_exc()
        return None, None

    finally:
        conn.close()


def export_aggregated_phrases(aggregated_data, review_reduction_stats):
    """Export aggregated phrases to CSV files"""

    if not aggregated_data:
        print("❌ No data to export")
        return None, None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create exports directory
    exports_dir = Path(config.PROJECT_ROOT) / "data" / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    # Export all aggregated phrases (without priority field for main export)
    all_filename = f"thai_phrases_aggregated_{timestamp}.csv"
    all_path = exports_dir / all_filename

    fieldnames = [
        'phrase_text', 'group_size', 'confidence_score', 'word_count', 'status',
        'needs_correction', 'correction_suggestion', 'final_correction', 'correction_source',
        'source_documents', 'unique_companies', 'total_instances', 'best_phrase_id',
        'best_file_name', 'context', 'created_at', 'updated_at'
    ]

    # Remove priority field from data for main export
    clean_aggregated_data = [{k: v for k, v in row.items() if k != 'priority'} for row in aggregated_data]

    with open(all_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in clean_aggregated_data:
            writer.writerow(row)

    print(f"✅ Aggregated phrases exported to: {all_path}")

    # Export only phrases needing correction (much smaller file!)
    needs_correction_data = [{k: v for k, v in row.items() if k != 'priority'} for row in aggregated_data if row['needs_correction']]

    review_filename = f"thai_phrases_aggregated_needs_review_{timestamp}.csv"
    review_path = exports_dir / review_filename

    with open(review_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in needs_correction_data:
            writer.writerow(row)

    print(f"📝 Review-only aggregated export: {review_path}")

    # Create summary statistics file
    summary_filename = f"aggregation_summary_{timestamp}.csv"
    summary_path = exports_dir / summary_filename

    summary_data = [
        {'metric': 'Original phrases', 'value': review_reduction_stats['original_phrases']},
        {'metric': 'Unique phrases after aggregation', 'value': len(aggregated_data)},
        {'metric': 'Reduction in phrases', 'value': review_reduction_stats['reduced_by']},
        {'metric': 'Reduction percentage', 'value': f"{review_reduction_stats['reduction_percentage']:.1f}%"},
        {'metric': 'Unique phrases needing correction', 'value': len(needs_correction_data)},
        {
            'metric': 'Average group size for corrected phrases',
            'value': f"{sum(row['group_size'] for row in needs_correction_data) / len(needs_correction_data):.1f}" if needs_correction_data else 0
        }
    ]

    with open(summary_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['metric', 'value'])
        writer.writeheader()
        for row in summary_data:
            writer.writerow(row)

    print(f"📊 Summary statistics exported to: {summary_path}")

    return all_path, review_path


def create_high_priority_review_file(aggregated_data):
    """Create a prioritized review file focusing on the most important corrections"""

    # Filter to high-priority cases:
    # 1. Phrases that appear in multiple files AND need correction
    # 2. Low confidence phrases that need correction
    high_priority = []

    for row in aggregated_data:
        if row['needs_correction']:
            # Priority 1: Multi-file phrases needing correction
            if row['group_size'] >= 3:
                priority = 'HIGH_MULTI_FILE'
            # Priority 2: Low confidence phrases
            elif row['confidence_score'] and row['confidence_score'] < 0.5:
                priority = 'HIGH_LOW_CONFIDENCE'
            # Priority 3: Medium confidence, 2+ files
            elif row['group_size'] >= 2:
                priority = 'MEDIUM_MULTI_FILE'
            else:
                priority = 'STANDARD'

            row['priority'] = priority
            high_priority.append(row)

    # Sort by priority and group size
    priority_order = {'HIGH_MULTI_FILE': 1, 'HIGH_LOW_CONFIDENCE': 2, 'MEDIUM_MULTI_FILE': 3, 'STANDARD': 4}
    high_priority.sort(key=lambda x: (
        priority_order.get(x['priority'], 5),
        -x['group_size'],
        x['confidence_score'] or 999
    ))

    return high_priority


def main():
    """Main execution function"""
    print("🚀 Thai Phrase Aggregation and Deduplication")
    print("=" * 60)

    try:
        # Aggregate phrases
        aggregated_data, reduction_stats = aggregate_duplicate_phrases()

        if not aggregated_data:
            print("❌ Failed to aggregate phrases")
            return

        # Create high-priority review list
        high_priority_data = create_high_priority_review_file(aggregated_data)

        print(f"\n📈 AGGREGATION RESULTS:")
        print(f"   Original phrases: {reduction_stats['original_phrases']:,}")
        print(f"   Unique phrases: {reduction_stats['unique_phrases']:,}")
        print(f"   Reduction: {reduction_stats['reduced_by']:,} ({reduction_stats['reduction_percentage']:.1f}%)")
        print(f"   Phrases needing correction: {len([r for r in aggregated_data if r['needs_correction']]):,}")
        print(f"   High-priority cases: {len(high_priority_data):,}")

        # Export aggregated data
        all_path, review_path = export_aggregated_phrases(aggregated_data, reduction_stats)

        # Export high-priority review file
        if high_priority_data:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            priority_filename = f"thai_phrases_priority_review_{timestamp}.csv"
            priority_path = Path(config.PROJECT_ROOT) / "data" / "exports" / priority_filename

            fieldnames = [
                'phrase_text', 'group_size', 'confidence_score', 'priority', 'final_correction',
                'correction_source', 'source_documents', 'unique_companies', 'total_instances',
                'best_file_name', 'context'
            ]

            with open(priority_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in high_priority_data:
                    writer.writerow({k: row[k] for k in fieldnames})

            print(f"⚡ High-priority review file: {priority_filename}")

        print(f"\n🎯 RECOMMENDED WORKFLOW:")
        print(f"1. Start with: thai_phrases_priority_review_{timestamp}.csv (high-priority cases)")
        print(f"2. Then review: thai_phrases_aggregated_needs_review_{timestamp}.csv (all needs review)")
        print(f"3. Reference: thai_phrases_aggregated_{timestamp}.csv (complete dataset)")
        print(f"4. Track progress by updating corrections in the Dictionary Management page")

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()