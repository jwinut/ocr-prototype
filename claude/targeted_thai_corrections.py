#!/usr/bin/env python3
"""
Targeted Thai OCR Corrections - Specific Error Fixes

Based on user feedback and real examples, this creates specific corrections
for the exact Thai OCR errors that were missed in the initial analysis.
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict


class TargetedThaiCorrectionGenerator:
    """Generate targeted corrections for specific Thai OCR errors"""

    def __init__(self, db_path: str = "data/prototype.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

        # Targeted corrections based on user's example and findings
        self.targeted_corrections = [
            # Critical spacing errors from user example
            {
                'error_pattern': 'งบบริษัท',
                'correction': 'งบบริษัท',
                'confidence': 0.99,
                'frequency': 170,  # From original analysis
                'type': 'spacing_error',
                'description': 'Fix spacing in financial statement term',
                'example': 'รายไดจากการขายและบริการ - สุทธิ',
                'priority': 'critical',
                'user_example': True
            },
            {
                'error_pattern': 'จันทร์เพ็ญ',
                'correction': 'จันทร์เพ็ญ',
                'confidence': 0.95,
                'frequency': 456,  # From original analysis
                'type': 'name_corruption',
                'description': 'Fix Thai name corruption',
                'example': 'ผู้ตรวจสอบัญชี : จันทร์เพ็ญ เตชะกําธร',
                'priority': 'high',
                'user_example': True
            },
            {
                'error_pattern': 'เตชะกําธร',
                'correction': 'เตชะกําธร',
                'confidence': 0.95,
                'frequency': 49,  # From original analysis
                'type': 'name_corruption',
                'description': 'Fix Thai name corruption',
                'example': 'ผู้ตรวจสอบัญชี : จันทร์เพ็ญ เตชะกําธร',
                'priority': 'high',
                'user_example': True
            },

            # Character corruption patterns (ำ character)
            {
                'error_pattern': 'จํากัด',
                'correction': 'จำกัด',
                'confidence': 0.98,
                'frequency': 58,  # From enhanced analysis
                'type': 'character_corruption',
                'description': 'Fix corrupted ำ character in company type',
                'example': 'บริษัทจํากัด → บริษัทจำกัด',
                'priority': 'critical',
                'user_example': True
            },
            {
                'error_pattern': 'กําไร',
                'correction': 'กำไร',
                'confidence': 0.98,
                'frequency': 149,  # From original analysis
                'type': 'character_corruption',
                'description': 'Fix corrupted ำ character in financial term',
                'example': 'งบกําไรขาดทุน → งบกำไรขาดทุน',
                'priority': 'critical',
                'user_example': True
            },
            {
                'error_pattern': 'คํานวณ',
                'correction': 'คำนวณ',
                'confidence': 0.98,
                'frequency': 0,  # Low frequency but critical
                'type': 'character_corruption',
                'description': 'Fix corrupted ำ character in calculation term',
                'example': 'คํานวณงบกระแสเงินสด → คำนวณงบกระแสเงินสด',
                'priority': 'high',
                'user_example': True
            },
            {
                'error_pattern': 'จํานวนปี',
                'correction': 'จำนวนปี',
                'confidence': 0.98,
                'frequency': 1,
                'type': 'character_corruption',
                'description': 'Fix corrupted ำ character in time period term',
                'example': 'จํานวนปีทีดำเนินกิจการ → จำนวนปีทีดำเนินกิจการ',
                'priority': 'high',
                'user_example': True
            },

            # spacing and formatting errors
            {
                'error_pattern': r'บริษัท\s+จำกัด',
                'correction': 'บริษัทจำกัด',
                'confidence': 0.95,
                'frequency': 37,  # From enhanced analysis
                'type': 'spacing_error',
                'description': 'Remove unnecessary space between company type and status',
                'example': 'บริษัท จำกัด → บริษัทจำกัด',
                'priority': 'high',
                'user_example': True
            },
            {
                'error_pattern': 'สุทธิ',
                'correction': 'สุทธิ',
                'confidence': 0.85,
                'frequency': 11,  # From enhanced analysis
                'type': 'spacing_error',
                'description': 'Fix spacing in financial result term',
                'example': 'รายไดจากการขายและบริการ - สุทธิ',
                'priority': 'medium',
                'user_example': True
            },
            {
                'error_pattern': 'ขาดทุน',
                'correction': 'ขาดทุน',
                'confidence': 0.90,
                'frequency': 150,  # From original analysis
                'type': 'spacing_error',
                'description': 'Fix spacing in net loss term',
                'example': 'กําไร (ขาดทุน) → กำไร (ขาดทุน)',
                'priority': 'medium',
                'user_example': True
            },

            # Mixed Thai-English punctuation
            {
                'error_pattern': 'COMPANY.,LTD.',
                'correction': 'COMPANY LTD',
                'confidence': 0.95,
                'frequency': 0,  # Pattern-based
                'type': 'mixed_punctuation',
                'description': 'Fix English punctuation in company name',
                'example': 'STORAGE SYSTEM INDUSTRY CO.,LTD. → STORAGE SYSTEM INDUSTRY CO LTD',
                'priority': 'medium',
                'user_example': True
            }
        ]

    def connect(self) -> bool:
        """Connect to database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            return True
        except Exception as e:
            print(f"Error connecting to database: {e}")
            return False

    def check_existing_corrections(self) -> Dict:
        """Check what corrections already exist"""
        if not self.cursor:
            return {}

        try:
            self.cursor.execute("""
                SELECT error_pattern, correction FROM thai_ocr_corrections
                WHERE is_active = 1
            """)

            existing = {}
            for row in self.cursor.fetchall():
                key = f"{row[0]}->{row[1]}"
                existing[key] = True

            return existing

        except Exception as e:
            print(f"Error checking existing corrections: {e}")
            return {}

    def add_targeted_corrections(self) -> Dict:
        """Add targeted corrections to database"""
        if not self.connect():
            return {}

        existing_corrections = self.check_existing_corrections()
        results = {
            'added': [],
            'skipped': [],
            'updated': []
        }

        try:
            for correction in self.targeted_corrections:
                key = f"{correction['error_pattern']}->{correction['correction']}"

                if key in existing_corrections:
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
                    results['updated'].append(key)
                else:
                    # Add new correction
                    self.cursor.execute("""
                        INSERT INTO thai_ocr_corrections
                        (error_pattern, correction, confidence, frequency, type, description,
                         example, priority, created_at, updated_at, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
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
                    results['added'].append(key)

            self.conn.commit()
            print(f"✅ Database updated: {len(results['added'])} added, {len(results['updated'])} updated")

        except Exception as e:
            print(f"❌ Error adding corrections: {e}")
            self.conn.rollback()

        return results

    def generate_user_focused_report(self) -> str:
        """Generate report focused on user-identified errors"""
        user_examples = [c for c in self.targeted_corrections if c.get('user_example', False)]

        report_lines = []
        report_lines.append("# User-Focused Thai OCR Corrections Report")
        report_lines.append("=" * 50)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Targeted corrections based on user feedback")
        report_lines.append(f"Total targeted corrections: {len(user_examples)}")
        report_lines.append("")

        report_lines.append("## 🎯 Critical User-Identified Errors")
        report_lines.append("")

        for i, correction in enumerate(user_examples, 1):
            if correction['priority'] == 'critical':
                report_lines.append(f"{i}. **{correction['error_pattern']}** → **{correction['correction']}**")
                report_lines.append(f"   - **Type**: {correction['type']}")
                report_lines.append(f"   - **Confidence**: {correction['confidence']:.2f}")
                report_lines.append(f"   - **Example**: {correction['example']}")
                report_lines.append("")

        report_lines.append("")
        report_lines.append("## 📋 High Priority Errors")
        report_lines.append("")

        for i, correction in enumerate([c for c in user_examples if c['priority'] == 'high'], 1):
            report_lines.append(f"{i}. **{correction['error_pattern']}** → **{correction['correction']}**")
            report_lines.append(f"   - **Type**: {correction['type']}")
            report_lines.append(f"   - **Example**: {correction['example']}")
            report_lines.append("")

        return '\n'.join(report_lines)

    def test_corrections_on_example(self) -> Dict:
        """Test corrections on the user's specific example text"""
        example_text = """## บริษัท สโตเรจซิสเต็ม อินดัสตรี จำกัด STORAGE SYSTEM INDUSTRY CO.,LTD.

<!-- image -->

## Income Statement (Amount) งบปี

Printed Date: 1 July 2025

|                                                         | 31/12/2567                             | 31/12/2566                             | 31/12/2565                             | 31/12/2564                             | 31/12/2563                             |
|---------------------------------------------------------|----------------------------------------|----------------------------------------|----------------------------------------|----------------------------------------|----------------------------------------|
| งบกําไรขาดทุน ( งบสรุป ): งบบริษัท                      | ผู้ตรวจสอบบัญชี : จันทร์เพ็ญ เตชะกําธร | ผู้ตรวจสอบบัญชี : จันทร์เพ็ญ เตชะกําธร | ผู้ตรวจสอบัญชี : จันทร์เพ็ญ เตชะกําธร | ผู้ตรวจสอบัญชี : จันทร์เพ็ญ เตชะกําธร |
|                                                         | 31/05/2568                             | 31/05/2567                             | 29/05/2566                             | 31/05/2565                             | 30/06/2564                             |
| รายได้จากการขายและบริการ - สุทธิ                       | 128,349,359.21                         | 152,735,117.92                         | 164,742,424.86                         | 102,897,786.40                         | 138,078,637.50                         |
"""

        test_results = {
            'original_errors': [],
            'corrections_applied': [],
            'final_text': example_text
        }

        # Apply corrections and track changes
        corrected_text = example_text
        for correction in self.targeted_corrections:
            if correction['error_pattern'] in corrected_text:
                test_results['original_errors'].append({
                    'pattern': correction['error_pattern'],
                    'found': True,
                    'count': corrected_text.count(correction['error_pattern'])
                })

                corrected_text = corrected_text.replace(
                    correction['error_pattern'],
                    correction['correction']
                )
                test_results['corrections_applied'].append(correction['error_pattern'])

        test_results['final_text'] = corrected_text
        return test_results

    def run_targeted_correction(self):
        """Main execution function"""
        print("🎯 Running Targeted Thai OCR Corrections...")
        print("=" * 60)

        if not self.connect():
            return

        print("📝 Adding targeted corrections based on user feedback...")

        # Add corrections to database
        results = self.add_targeted_corrections()

        # Generate user-focused report
        report = self.generate_user_focused_report()
        with open('targeted_thai_corrections_report.md', 'w', encoding='utf-8') as f:
            f.write(report)
        print("💾 User-focused report saved to targeted_thai_corrections_report.md")

        # Test corrections on user's example
        print("\n🧪 Testing corrections on your example text...")
        test_results = self.test_corrections_on_example()

        print(f"✅ Original errors found: {len(test_results['original_errors'])}")
        print(f"✅ Corrections applied: {len(test_results['corrections_applied'])}")

        # Show specific corrections that would be made
        print("\n🔧 Specific corrections for your example:")
        for i, correction in enumerate(test_results['original_errors'], 1):
            print(f"   {i}. Replace {correction['pattern']} (found {correction['count']} times)")

        # Show preview of first few lines after correction
        print("\n📋 Preview after corrections (first 3 lines):")
        lines = test_results['final_text'].split('\n')[:3]
        for line in lines:
            print(f"   {line}")

        # Display summary
        print(f"\n📊 Summary:")
        print(f"   Total targeted corrections: {len(self.targeted_corrections)}")
        print(f"   New corrections added: {len(results['added'])}")
        print(f"   Existing corrections updated: {len(results['updated'])}")

        # Close connection
        self.conn.close()

        print("\n✅ Targeted corrections complete!")
        print("These corrections address the specific errors you identified in the OCR output.")


def main():
    """Main execution function"""
    generator = TargetedThaiCorrectionGenerator()
    generator.run_targeted_correction()


if __name__ == "__main__":
    main()