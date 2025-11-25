#!/usr/bin/env python3
"""
Thai Phrase Analysis and Correction System

This script systematically analyzes Thai phrases from OCR results and:
1. Identifies phrases needing corrections
2. Generates corrections for common OCR errors
3. Updates the dictionary with suggested corrections
"""

import sqlite3
import re
import sys
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config
from utils.thai_utils import is_thai_text, clean_thai_text


class ThaiPhraseAnalyzer:
    """Analyze Thai phrases and generate corrections"""

    def __init__(self):
        self.conn = sqlite3.connect(config.DATABASE_PATH)
        self.cursor = self.conn.cursor()

        # Common OCR error patterns in Thai
        self.correction_patterns = {
            # Character confusion patterns (examples - would need more comprehensive mapping)
            # r'ค': 'ฮ',  # ค vs ฮ confusion
            # r'ต': 'ถ',  # ต vs ถ confusion
            # r'ป': 'ผ',  # ป vs ผ confusion

            # Missing spaces between words
            r'([ก-ฮ]{3,})([ก-ฮ]{3,})': r'\1 \2',  # Add space between long combined words

            # Common OCR artifacts
            r'[\u200B-\u200D\ufeff]': '',  # Remove zero-width characters
            r'\s+': ' ',  # Normalize whitespace
            r'^\s+|\s+$': '',  # Trim leading/trailing spaces

            # Number formatting issues
            r'([0-9])\s+([0-9])': r'\1\2',  # Combine separated numbers

            # Date format corrections
            r'(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})': r'\1/\2/\3',  # Normalize date format
        }

        # Financial terms that commonly appear in these documents
        self.financial_terms = [
            'สินทรัพย์', 'สินทรัพย์หมุนเวียน', 'สินทรัพย์ไม่หมุนเวียน',
            'เงินสด', 'ลูกหนี', 'เจ้าหนี', 'หนีสิน', 'งบดุล', 'งบแสดง',
            'กำไร', 'ขาดทุน', 'สะสม', 'บริษัท', 'ผู้ถือหุ้น', 'ทุน',
            'ภาษีเงินได้', 'ค่าใช้จ่าย', 'รายได้', 'รายจ่าย',
            'ที่ดิน', 'อาคาร', 'อุปกรณ์', 'เงินลงทุนระยะยาว',
            'เงินให้กู้ยืม', 'ดอกเบี้ยจ่าย', 'งบบริษัท', 'ผู้ตรวจสอบบัญชี'
        ]

    def analyze_phrase_quality(self):
        """Analyze all phrases and identify quality issues"""

        print("🔍 Analyzing Thai phrase quality...")

        # Get all phrases
        self.cursor.execute('''
            SELECT id, phrase, confidence_score, word_count, status, needs_correction
            FROM thai_phrases
            ORDER BY id
        ''')

        phrases = self.cursor.fetchall()

        quality_issues = []
        corrections_needed = []

        for phrase_id, phrase, confidence, word_count, status, needs_correction in phrases:
            issues = []

            if not phrase or not is_thai_text(phrase.strip()):
                issues.append("empty_or_invalid")
                continue

            # Check for common OCR errors
            phrase_analysis = self.analyze_single_phrase(phrase)

            if phrase_analysis['has_issues']:
                issues.extend(phrase_analysis['issue_types'])
                corrections_needed.append({
                    'id': phrase_id,
                    'original': phrase,
                    'issues': issues,
                    'suggested_correction': phrase_analysis['suggested_correction'],
                    'issue_types': phrase_analysis['issue_types'],
                    'confidence': confidence
                })

        print(f"📊 Analysis complete:")
        print(f"   Total phrases analyzed: {len(phrases)}")
        print(f"   Phrases needing corrections: {len(corrections_needed)}")

        return corrections_needed

    def analyze_single_phrase(self, phrase):
        """Analyze a single phrase for OCR issues"""

        original_phrase = phrase
        cleaned_phrase = clean_thai_text(phrase)
        suggested_correction = phrase
        issue_types = []
        has_issues = False

        # Check for empty or too short phrases
        if len(cleaned_phrase.strip()) < 2:
            return {
                'has_issues': True,
                'issue_types': ['too_short'],
                'suggested_correction': phrase,
                'confidence': 0.1
            }

        # Apply correction patterns
        for pattern, replacement in self.correction_patterns.items():
            if re.search(pattern, phrase):
                suggested_correction = re.sub(pattern, replacement, phrase)
                if pattern.startswith(r'([\u200B-\u200D\ufeff]'):
                    issue_types.append('zero_width_chars')
                elif pattern.startswith(r'\s+'):
                    issue_types.append('whitespace_issues')
                elif pattern.startswith(r'([ก-ฮ]{2,})'):
                    issue_types.append('missing_spaces')
                elif pattern.startswith(r'([0-9])'):
                    issue_types.append('number_formatting')
                else:
                    issue_types.append('character_confusion')
                has_issues = True

        # Check for financial term matching
        found_financial_terms = []
        for term in self.financial_terms:
            if term in suggested_correction:
                found_financial_terms.append(term)

        # If phrase contains no recognizable financial terms, flag it
        if not found_financial_terms and len(cleaned_phrase) > 5:
            issue_types.append('unrecognized_content')
            has_issues = True

        # Check for repeated characters (common OCR artifact)
        if re.search(r'(.)\1{2,}', suggested_correction):
            suggested_correction = re.sub(r'(.)\1{2,}', r'\1\1', suggested_correction)
            issue_types.append('repeated_characters')
            has_issues = True

        # Normalize final result
        suggested_correction = ' '.join(suggested_correction.split())

        return {
            'has_issues': has_issues,
            'issue_types': issue_types,
            'suggested_correction': suggested_correction if suggested_correction != original_phrase else None,
            'financial_terms': found_financial_terms
        }

    def generate_corrections_batch(self, corrections_needed):
        """Generate corrections for phrases that need them"""

        print("🔧 Generating corrections for problematic phrases...")

        corrections_generated = 0

        for correction_data in corrections_needed:
            phrase_id = correction_data['id']
            suggested_correction = correction_data['suggested_correction']
            issue_types = correction_data['issue_types']

            if suggested_correction and suggested_correction != correction_data['original']:
                # Check if this correction already exists in dictionary
                self.cursor.execute('''
                    SELECT id FROM thai_ocr_corrections
                    WHERE error_pattern = ? AND correction = ? AND is_active = 1
                ''', (correction_data['original'], suggested_correction))

                if not self.cursor.fetchone():
                    # Add to corrections table
                    correction_type = self.determine_correction_type(issue_types)

                    self.cursor.execute('''
                        INSERT INTO thai_ocr_corrections
                        (error_pattern, correction, type, confidence, frequency, description,
                         example, priority, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, 0.9, 0, ?, ?, 'high', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (
                        correction_data['original'],
                        suggested_correction,
                        correction_type,
                        f"Auto-generated correction for: {', '.join(issue_types)}",
                        f"{correction_data['original']} → {suggested_correction}"
                    ))

                    corrections_generated += 1
                    print(f"   ✅ Added correction: {correction_data['original'][:30]}... → {suggested_correction[:30]}...")

                # Update phrase record
                self.cursor.execute('''
                    UPDATE thai_phrases
                    SET needs_correction = TRUE,
                        correction_suggestion = ?,
                        status = 'reviewed',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (suggested_correction, phrase_id))

        self.conn.commit()
        print(f"🎉 Generated {corrections_generated} new corrections")

        return corrections_generated

    def determine_correction_type(self, issue_types):
        """Determine the type of correction based on issues"""

        if 'character_confusion' in issue_types:
            return 'character_fix'
        elif 'missing_spaces' in issue_types:
            return 'spacing'
        elif 'zero_width_chars' in issue_types or 'whitespace_issues' in issue_types:
            return 'spacing'
        elif 'number_formatting' in issue_types:
            return 'other'
        elif 'repeated_characters' in issue_types:
            return 'character_fix'
        else:
            return 'other'

    def update_phrases_status(self):
        """Update phrase status based on corrections"""

        print("📋 Updating phrase statuses...")

        # Mark phrases as corrected if they have corrections
        self.cursor.execute('''
            UPDATE thai_phrases
            SET status = 'corrected',
                needs_correction = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE correction_suggestion IS NOT NULL
            AND correction_suggestion != ''
        ''')

        corrected_count = self.cursor.rowcount

        # Mark high-quality phrases as reviewed
        self.cursor.execute('''
            UPDATE thai_phrases
            SET status = 'reviewed',
                needs_correction = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE confidence_score >= 0.9
            AND word_count >= 3
            AND word_count <= 10
            AND status = 'pending'
        ''')

        reviewed_count = self.cursor.rowcount

        self.conn.commit()

        print(f"   ✅ Marked {corrected_count} phrases as corrected")
        print(f"   ✅ Marked {reviewed_count} high-quality phrases as reviewed")

    def generate_quality_report(self, corrections_needed):
        """Generate a comprehensive quality report"""

        print("\n📊 PHRASE QUALITY ANALYSIS REPORT")
        print("=" * 50)

        # Issue type distribution
        issue_counts = defaultdict(int)
        for correction in corrections_needed:
            for issue_type in correction['issue_types']:
                issue_counts[issue_type] += 1

        print(f"📈 Issue Type Distribution:")
        for issue_type, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"   {issue_type}: {count}")

        print(f"\n📋 Summary:")
        print(f"   Total problematic phrases: {len(corrections_needed)}")
        print(f"   Average phrase confidence: {sum(c['confidence'] for c in corrections_needed) / len(corrections_needed):.3f}" if corrections_needed else "N/A")

        # Sample corrections
        print(f"\n💡 Sample Corrections:")
        for i, correction in enumerate(corrections_needed[:10]):
            print(f"   {i+1}. {correction['original'][:40]}... → {correction['suggested_correction'][:40]}...")

        print(f"\n📝 Financial Terms Found:")
        financial_terms_found = set()
        for correction in corrections_needed:
            analysis = self.analyze_single_phrase(correction['original'])
            financial_terms_found.update(analysis.get('financial_terms', []))

        for term in sorted(financial_terms_found):
            print(f"   ✓ {term}")

    def run_analysis(self):
        """Run the complete analysis and correction process"""

        print("🚀 Starting Thai Phrase Analysis and Correction System")
        print("=" * 60)

        try:
            # Step 1: Analyze phrase quality
            corrections_needed = self.analyze_phrase_quality()

            # Step 2: Generate corrections
            corrections_generated = self.generate_corrections_batch(corrections_needed)

            # Step 3: Update phrase statuses
            self.update_phrases_status()

            # Step 4: Generate report
            self.generate_quality_report(corrections_needed)

            # Final statistics
            self.cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN needs_correction = TRUE THEN 1 END) as needs_correction,
                    COUNT(CASE WHEN status = 'corrected' THEN 1 END) as corrected,
                    COUNT(CASE WHEN status = 'reviewed' THEN 1 END) as reviewed
                FROM thai_phrases
            ''')

            stats = self.cursor.fetchone()
            total, needs_correction, corrected, reviewed = stats

            print(f"\n🎯 FINAL RESULTS:")
            print(f"   Total phrases: {total:,}")
            print(f"   Phrases needing correction: {needs_correction:,}")
            print(f"   Phrases corrected: {corrected:,}")
            print(f"   Phrases reviewed: {reviewed:,}")
            print(f"   Corrections generated: {corrections_generated:,}")

            print(f"\n✅ Analysis complete! The Dictionary Management page now has:")
            print(f"   - Identified phrases needing manual review")
            print(f"   - Auto-generated corrections for common OCR errors")
            print(f"   - Updated status flags for workflow management")

            return True

        except Exception as e:
            print(f"❌ Error during analysis: {e}")
            return False

        finally:
            self.conn.close()


def main():
    """Main execution function"""
    analyzer = ThaiPhraseAnalyzer()
    success = analyzer.run_analysis()

    if success:
        print(f"\n🎉 Thai phrase analysis completed successfully!")
        print(f"\nNext steps:")
        print(f"1. Refresh the Dictionary Management page to see updated statuses")
        print(f"2. Review phrases marked as needing correction")
        print(f"3. Accept or modify the suggested corrections")
        print(f"4. Add approved corrections to the custom dictionary")
    else:
        print(f"\n❌ Analysis failed. Please check the error messages above.")


if __name__ == "__main__":
    main()