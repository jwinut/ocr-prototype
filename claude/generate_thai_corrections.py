#!/usr/bin/env python3
"""
Generate Thai OCR Corrections - Create dictionary improvements

Based on the OCR analysis, this script generates corrections for common Thai OCR errors.
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List


class ThaiCorrectionGenerator:
    """Generate Thai OCR correction dictionary entries"""

    def __init__(self, db_path: str = "data/prototype.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

        # Load analysis results
        with open('thai_ocr_analysis.json', 'r', encoding='utf-8') as f:
            self.analysis = json.load(f)

    def connect(self) -> bool:
        """Connect to database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            return True
        except Exception as e:
            print(f"Error connecting to database: {e}")
            return False

    def generate_corrections(self) -> List[Dict]:
        """Generate correction entries based on analysis"""
        corrections = []

        # High-priority character duplication corrections
        suspicious_patterns = self.analysis['analysis']['suspicious_patterns']

        # Most critical: บบ duplication (appears 634 times)
        corrections.append({
            'error_pattern': 'บบ',
            'correction': 'บ',
            'confidence': 0.95,
            'frequency': 634,
            'type': 'character_duplication',
            'description': 'Fix duplicated บ character',
            'example': 'บริบบษัท → บริษัท',
            'priority': 'critical'
        })

        # Other duplications
        if 'Invalid cluster: สส' in suspicious_patterns:
            corrections.append({
                'error_pattern': 'สส',
                'correction': 'ส',
                'confidence': 0.90,
                'frequency': suspicious_patterns['Invalid cluster: สส'],
                'type': 'character_duplication',
                'description': 'Fix duplicated ส character',
                'example': 'สสมบัติ → สมบัติ',
                'priority': 'high'
            })

        if 'Invalid cluster: ปป' in suspicious_patterns:
            corrections.append({
                'error_pattern': 'ปป',
                'correction': 'ป',
                'confidence': 0.90,
                'frequency': suspicious_patterns['Invalid cluster: ปป'],
                'type': 'character_duplication',
                'description': 'Fix duplicated ป character',
                'example': 'ปประเทศ → ประเทศ',
                'priority': 'medium'
            })

        # OCR character confusion patterns
        # Based on visual similarity and common OCR errors
        confusion_corrections = [
            {
                'error_pattern': 'ถ',
                'correction': 'ด',
                'confidence': 0.75,
                'frequency': 916,  # from character_frequency
                'type': 'character_confusion',
                'description': 'ด/ถ character confusion',
                'example': 'มูลค่าถ → มูลค่าด',
                'priority': 'medium'
            },
            {
                'error_pattern': 'บ',
                'correction': 'ป',
                'confidence': 0.70,
                'frequency': 5291,  # high frequency suggests overuse
                'type': 'character_confusion',
                'description': 'บ/ป character confusion',
                'example': 'บริการ → ประการ (when context fits)',
                'priority': 'medium'
            },
            {
                'error_pattern': 'ว',
                'correction': 'ถ',
                'confidence': 0.65,
                'frequency': 4793,
                'type': 'character_confusion',
                'description': 'ว/ถ character confusion',
                'example': 'ดำเนินวาน → ดำเนินการ',
                'priority': 'low'
            }
        ]

        corrections.extend(confusion_corrections)

        # Common spacing/segmentation errors
        unknown_words = self.analysis['analysis']['unknown_words']

        # Fix common word segmentation issues
        segmentation_corrections = [
            {
                'error_pattern': 'งบบริษัท',
                'correction': 'งบบริษัท',
                'confidence': 0.80,
                'frequency': unknown_words.get('งบบริษัท', 0),
                'type': 'word_segmentation',
                'description': 'Financial statement term',
                'example': 'งบบริษัท',
                'priority': 'high'
            },
            {
                'error_pattern': 'บจก',
                'correction': 'บจก.',
                'confidence': 0.85,
                'frequency': unknown_words.get('บจก', 0),
                'type': 'abbreviation_punctuation',
                'description': 'Add period to company abbreviation',
                'example': 'บจก. (บริษัทจำกัด)',
                'priority': 'high'
            },
            {
                'error_pattern': 'จํากั',
                'correction': 'จำกัด',
                'confidence': 0.90,
                'frequency': unknown_words.get('จํากั', 0),
                'type': 'character_correction',
                'description': 'Fix corrupted ำ character',
                'example': 'จำกัด',
                'priority': 'high'
            },
            {
                'error_pattern': 'กําไร',
                'correction': 'กำไร',
                'confidence': 0.90,
                'frequency': unknown_words.get('กําไร', 0),
                'type': 'character_correction',
                'description': 'Fix corrupted ำ character',
                'example': 'กำไร',
                'priority': 'high'
            },
            {
                'error_pattern': 'คํานวณ',
                'correction': 'คำนวณ',
                'confidence': 0.90,
                'frequency': unknown_words.get('คํานวณ', 0),
                'type': 'character_correction',
                'description': 'Fix corrupted ำ character',
                'example': 'คำนวณ',
                'priority': 'high'
            }
        ]

        corrections.extend(segmentation_corrections)

        # Sort by priority and frequency
        priority_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        corrections.sort(key=lambda x: (priority_order.get(x['priority'], 0), x['frequency']), reverse=True)

        return corrections

    def save_corrections_to_json(self, corrections: List[Dict], filename: str = "thai_ocr_corrections.json"):
        """Save corrections to JSON file"""
        corrections_data = {
            'generated_at': datetime.now().isoformat(),
            'analysis_summary': {
                'total_texts_analyzed': self.analysis['total_texts_processed'],
                'thai_sequences_found': len(self.analysis['analysis']['character_sequences']),
                'suspicious_patterns_found': len(self.analysis['analysis']['suspicious_patterns']),
                'unknown_words_found': len(self.analysis['analysis']['unknown_words'])
            },
            'corrections': corrections,
            'statistics': {
                'total_corrections': len(corrections),
                'critical_corrections': len([c for c in corrections if c['priority'] == 'critical']),
                'high_priority_corrections': len([c for c in corrections if c['priority'] == 'high']),
                'corrections_by_type': {}
            }
        }

        # Count corrections by type
        for correction in corrections:
            corr_type = correction['type']
            corrections_data['statistics']['corrections_by_type'][corr_type] = \
                corrections_data['statistics']['corrections_by_type'].get(corr_type, 0) + 1

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(corrections_data, f, ensure_ascii=False, indent=2)

        print(f"💾 Corrections saved to {filename}")

    def generate_sql_inserts(self, corrections: List[Dict]) -> str:
        """Generate SQL INSERT statements for corrections"""
        sql_statements = []

        for correction in corrections:
            # Escape single quotes in JSON
            example = correction['example'].replace("'", "''")
            description = correction['description'].replace("'", "''")

            sql = f"""
INSERT INTO thai_ocr_corrections
(error_pattern, correction, confidence, frequency, type, description, example, priority, created_at, updated_at)
VALUES (
    '{correction['error_pattern']}',
    '{correction['correction']}',
    {correction['confidence']},
    {correction['frequency']},
    '{correction['type']}',
    '{description}',
    '{example}',
    '{correction['priority']}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);"""
            sql_statements.append(sql)

        return '\n'.join(sql_statements)

    def create_corrections_table(self):
        """Create table for storing corrections if it doesn't exist"""
        create_table_sql = """
CREATE TABLE IF NOT EXISTS thai_ocr_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    error_pattern TEXT NOT NULL,
    correction TEXT NOT NULL,
    confidence REAL NOT NULL,
    frequency INTEGER NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    example TEXT,
    priority TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(error_pattern, correction)
);"""

        self.cursor.execute(create_table_sql)
        self.conn.commit()
        print("✓ Thai OCR corrections table created/verified")

    def save_corrections_to_db(self, corrections: List[Dict]):
        """Save corrections to database"""
        try:
            self.create_corrections_table()

            inserted_count = 0
            updated_count = 0

            for correction in corrections:
                # Check if correction already exists
                self.cursor.execute("""
                    SELECT id FROM thai_ocr_corrections
                    WHERE error_pattern = ? AND correction = ?
                """, (correction['error_pattern'], correction['correction']))

                if self.cursor.fetchone():
                    # Update existing correction
                    self.cursor.execute("""
                        UPDATE thai_ocr_corrections
                        SET confidence = ?, frequency = ?, type = ?, description = ?,
                            example = ?, priority = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE error_pattern = ? AND correction = ?
                    """, (
                        correction['confidence'],
                        correction['frequency'],
                        correction['type'],
                        correction['description'],
                        correction['example'],
                        correction['priority'],
                        correction['error_pattern'],
                        correction['correction']
                    ))
                    updated_count += 1
                else:
                    # Insert new correction
                    self.cursor.execute("""
                        INSERT INTO thai_ocr_corrections
                        (error_pattern, correction, confidence, frequency, type, description,
                         example, priority, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (
                        correction['error_pattern'],
                        correction['correction'],
                        correction['confidence'],
                        correction['frequency'],
                        correction['type'],
                        correction['description'],
                        correction['example'],
                        correction['priority']
                    ))
                    inserted_count += 1

            self.conn.commit()
            print(f"✓ Saved corrections to database")
            print(f"   New entries: {inserted_count}")
            print(f"   Updated entries: {updated_count}")

        except Exception as e:
            print(f"❌ Error saving corrections to database: {e}")
            self.conn.rollback()

    def generate_report(self, corrections: List[Dict]) -> str:
        """Generate a human-readable report"""
        report_lines = []
        report_lines.append("# Thai OCR Correction Report")
        report_lines.append("=" * 50)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Total corrections generated: {len(corrections)}")
        report_lines.append("")

        # Summary by priority
        priority_counts = {}
        type_counts = {}
        for correction in corrections:
            priority = correction['priority']
            corr_type = correction['type']
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            type_counts[corr_type] = type_counts.get(corr_type, 0) + 1

        report_lines.append("## Summary by Priority")
        for priority in ['critical', 'high', 'medium', 'low']:
            count = priority_counts.get(priority, 0)
            if count > 0:
                report_lines.append(f"- {priority.capitalize()}: {count} corrections")

        report_lines.append("")
        report_lines.append("## Summary by Type")
        for corr_type, count in sorted(type_counts.items()):
            report_lines.append(f"- {corr_type}: {count} corrections")

        report_lines.append("")
        report_lines.append("## Top 10 Corrections by Frequency")

        # Sort corrections by frequency (descending)
        sorted_corrections = sorted(corrections, key=lambda x: x['frequency'], reverse=True)

        for i, correction in enumerate(sorted_corrections[:10], 1):
            report_lines.append(f"{i}. **{correction['error_pattern']}** → **{correction['correction']}**")
            report_lines.append(f"   - Frequency: {correction['frequency']}")
            report_lines.append(f"   - Confidence: {correction['confidence']:.2f}")
            report_lines.append(f"   - Type: {correction['type']}")
            report_lines.append(f"   - Priority: {correction['priority']}")
            report_lines.append(f"   - Example: {correction['example']}")
            report_lines.append("")

        return '\n'.join(report_lines)

    def run(self):
        """Main execution function"""
        print("🔧 Generating Thai OCR corrections...")
        print("=" * 50)

        if not self.connect():
            return

        # Generate corrections
        corrections = self.generate_corrections()
        print(f"✓ Generated {len(corrections)} corrections")

        # Save to JSON
        self.save_corrections_to_json(corrections)

        # Save to database
        self.save_corrections_to_db(corrections)

        # Generate SQL inserts
        sql_inserts = self.generate_sql_inserts(corrections)
        with open('thai_ocr_corrections.sql', 'w', encoding='utf-8') as f:
            f.write(sql_inserts)
        print("💾 SQL insert statements saved to thai_ocr_corrections.sql")

        # Generate report
        report = self.generate_report(corrections)
        with open('thai_ocr_corrections_report.md', 'w', encoding='utf-8') as f:
            f.write(report)
        print("💾 Report saved to thai_ocr_corrections_report.md")

        # Display summary
        print("\n📊 Correction Summary:")
        priority_counts = {}
        for correction in corrections:
            priority = correction['priority']
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        for priority in ['critical', 'high', 'medium', 'low']:
            count = priority_counts.get(priority, 0)
            if count > 0:
                print(f"   {priority.capitalize()}: {count} corrections")

        print(f"\n🎯 Top 3 critical corrections:")
        critical_corrections = [c for c in corrections if c['priority'] == 'critical'][:3]
        for i, correction in enumerate(critical_corrections, 1):
            print(f"   {i}. {correction['error_pattern']} → {correction['correction']} "
                  f"(frequency: {correction['frequency']})")

        # Close connection
        self.conn.close()

        print("\n✅ Correction generation complete!")


def main():
    """Main execution function"""
    generator = ThaiCorrectionGenerator()
    generator.run()


if __name__ == "__main__":
    main()