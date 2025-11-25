#!/usr/bin/env python3
"""
Additional Thai OCR Corrections - Tone Marks and Financial Terms

Based on additional user feedback, this script adds corrections for
Thai financial terms with missing tone marks and spacing issues.
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict


class AdditionalThaiCorrectionGenerator:
    """Generate additional corrections for Thai financial term OCR errors"""

    def __init__(self, db_path: str = "data/prototype.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

        # Additional corrections based on user feedback about financial terms
        self.additional_corrections = [
            # Financial term tone mark errors
            {
                'error_pattern': 'ภาษีเงินได',
                'correction': 'ภาษีเงินได้',
                'confidence': 0.95,
                'frequency': 4,  # Found in database
                'type': 'tone_mark_error',
                'description': 'Add missing tone mark to income tax term',
                'example': 'ภาษีเงินได → ภาษีเงินได้ (income tax)',
                'priority': 'critical',
                'user_example': True
            },
            {
                'error_pattern': 'ดอกเบียจ่าย',
                'correction': 'ดอกเบี้ยจ่าย',
                'confidence': 0.95,
                'frequency': 4,  # Found in database
                'type': 'tone_mark_error',
                'description': 'Add missing tone mark to interest expense term',
                'example': 'ดอกเบียจ่าย → ดอกเบี้ยจ่าย (interest expense)',
                'priority': 'critical',
                'user_example': True
            },

            # Common financial term variations
            {
                'error_pattern': 'รวมรายได',
                'correction': 'รวมรายได้',
                'confidence': 0.90,
                'frequency': 0,  # Pattern-based correction
                'type': 'tone_mark_error',
                'description': 'Add missing tone mark to total income term',
                'example': 'รวมรายได → รวมรายได้ (total income)',
                'priority': 'high',
                'user_example': True
            },

            # Spacing issues in financial terms
            {
                'error_pattern': 'ค่าใช จ่าย',
                'correction': 'ค่าใช้จ่าย',
                'confidence': 0.95,
                'frequency': 2,  # Found in database
                'type': 'spacing_error',
                'description': 'Fix spacing in expense term',
                'example': 'ค่าใช จ่าย → ค่าใช้จ่าย (expenses)',
                'priority': 'high',
                'user_example': True
            },
            {
                'error_pattern': 'รายได้ ค้ างรับ',
                'correction': 'รายได้ค้างรับ',
                'confidence': 0.95,
                'frequency': 1,  # Found in database
                'type': 'spacing_error',
                'description': 'Fix spacing in accrued revenue term',
                'example': 'รายได้ ค้ างรับ → รายได้ค้างรับ (accrued revenue)',
                'priority': 'high',
                'user_example': True
            },

            # Character corruption in financial terms
            {
                'error_pattern': 'การปรับปรุงด',
                'correction': 'การปรับปรุงด้วย',
                'confidence': 0.90,
                'frequency': 4,  # Found in database
                'type': 'character_corruption',
                'description': 'Fix corruption in adjustment term',
                'example': 'การปรับปรุงดอกเบียจ่าย → การปรับปรุงด้วยดอกเบี้ยจ่าย',
                'priority': 'medium',
                'user_example': True
            },
            {
                'error_pattern': 'ค างจ่าย',
                'correction': 'ค้างจ่าย',
                'confidence': 0.90,
                'frequency': 1,  # Found in database
                'type': 'character_corruption',
                'description': 'Fix corruption in accrued expense term',
                'example': 'ค างจ่าย → ค้างจ่าย (accrued expense)',
                'priority': 'high',
                'user_example': True
            },

            # Additional common Thai financial term errors
            {
                'error_pattern': 'สินทรัพย์',
                'correction': 'สินทรัพย์',
                'confidence': 0.85,
                'frequency': 0,  # Should already be correct
                'type': 'character_validation',
                'description': 'Validate assets term spelling',
                'example': 'สินทรัพย์ (assets)',
                'priority': 'medium',
                'user_example': False
            },

            # Income related corrections
            {
                'error_pattern': 'เงินได',
                'correction': 'เงินได้',
                'confidence': 0.80,
                'frequency': 0,  # Pattern-based
                'type': 'tone_mark_error',
                'description': 'Add missing tone mark to income term',
                'example': 'เงินได → เงินได้ (income)',
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

    def add_additional_corrections(self) -> Dict:
        """Add additional corrections to database"""
        if not self.connect():
            return {}

        existing_corrections = self.check_existing_corrections()
        results = {
            'added': [],
            'skipped': [],
            'updated': []
        }

        try:
            for correction in self.additional_corrections:
                key = f"{correction['error_pattern']}->{correction['correction']}"

                if key in existing_corrections:
                    # Update existing correction with user feedback
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

    def test_financial_corrections(self) -> Dict:
        """Test corrections on financial document examples"""
        example_texts = [
            "การปรับปรุงด วยค่าใช จ่ายภาษี เงินได",
            "ดอกเบียจ่ายค างจ่าย",
            "รายได้ ค้ างรับและรวมรายได",
            "ค่าใช จ่ายจ่ายล่วงหน้า"
        ]

        test_results = {
            'examples_tested': len(example_texts),
            'corrections_applied': [],
            'before_after': []
        }

        for i, text in enumerate(example_texts, 1):
            corrected_text = text
            applied_corrections = []

            for correction in self.additional_corrections:
                if correction['error_pattern'] in corrected_text:
                    corrected_text = corrected_text.replace(
                        correction['error_pattern'],
                        correction['correction']
                    )
                    applied_corrections.append(correction['error_pattern'])

            if applied_corrections:
                test_results['corrections_applied'].extend(applied_corrections)
                test_results['before_after'].append({
                    'example': i,
                    'original': text,
                    'corrected': corrected_text,
                    'corrections': applied_corrections
                })

        return test_results

    def run_additional_corrections(self):
        """Main execution function"""
        print("💰 Running Additional Thai Financial Term Corrections...")
        print("=" * 65)

        if not self.connect():
            return

        print("📝 Adding financial term corrections based on user feedback...")

        # Add corrections to database
        results = self.add_additional_corrections()

        # Test corrections on financial examples
        print("\n🧪 Testing corrections on financial document examples...")
        test_results = self.test_financial_corrections()

        print(f"✅ Examples tested: {test_results['examples_tested']}")
        print(f"✅ Total corrections applied: {len(set(test_results['corrections_applied']))}")

        # Show before/after examples
        print("\n📋 Correction Examples:")
        for example in test_results['before_after']:
            print(f"\nExample {example['example']}:")
            print(f"   Before: {example['original']}")
            print(f"   After:  {example['corrected']}")
            print(f"   Fixes:  {', '.join(example['corrections'])}")

        # Display summary
        print(f"\n📊 Summary:")
        print(f"   Additional corrections: {len(self.additional_corrections)}")
        print(f"   New corrections added: {len(results['added'])}")
        print(f"   Existing corrections updated: {len(results['updated'])}")

        # Show financial term corrections specifically
        financial_corrections = [c for c in self.additional_corrections
                               if c['type'] in ['tone_mark_error', 'spacing_error'] and c.get('user_example')]

        print(f"\n💵 Financial Term Corrections (User-Identified):")
        for i, correction in enumerate(financial_corrections, 1):
            print(f"   {i}. {correction['error_pattern']} → {correction['correction']}")
            print(f"      Type: {correction['type']}, Priority: {correction['priority']}")

        # Close connection
        self.conn.close()

        print("\n✅ Additional financial term corrections complete!")
        print("These corrections address Thai financial terminology with missing tone marks.")


def main():
    """Main execution function"""
    generator = AdditionalThaiCorrectionGenerator()
    generator.run_additional_corrections()


if __name__ == "__main__":
    main()