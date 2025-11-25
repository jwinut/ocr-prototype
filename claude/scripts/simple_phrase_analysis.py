#!/usr/bin/env python3
"""
Simple Thai Phrase Analysis and Correction System

Analyzes Thai phrases from OCR results and identifies common issues
"""

import sqlite3
import re
import sys
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config


def is_thai_text(text):
    """Simple check if text contains Thai characters"""
    if not text:
        return False
    # Check for Thai character range
    return any(ord(char) >= 3584 and ord(char) <= 3711 for char in text)


def clean_thai_text(text):
    """Clean Thai text by removing artifacts"""
    if not text:
        return ""

    # Remove common OCR artifacts
    text = re.sub(r'[\u200B-\u200D\ufeff]', '', text)  # Zero-width chars
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    text = text.strip()  # Trim

    return text


class ThaiPhraseAnalyzer:
    """Simple Thai phrase analyzer"""

    def __init__(self):
        self.conn = sqlite3.connect(config.DATABASE_PATH)
        self.cursor = self.conn.cursor()

        # Financial terms commonly found in financial statements
        self.financial_terms = [
            'สินทรัพย์', 'สินทรัพย์หมุนเวียน', 'สินทรัพย์ไม่หมุนเวียน',
            'เงินสด', 'ลูกหนี', 'เจ้าหนี', 'หนีสิน', 'งบดุล', 'งบแสดง',
            'กำไร', 'ขาดทุน', 'สะสม', 'บริษัท', 'ผู้ถือหุ้น', 'ทุน',
            'ภาษีเงินได้', 'ค่าใช้จ่าย', 'รายได้', 'รายจ่าย',
            'ที่ดิน', 'อาคาร', 'อุปกรณ์', 'เงินลงทุนระยะยาว',
            'เงินให้กู้ยืม', 'ดอกเบี้ยจ่าย', 'งบบริษัท', 'ผู้ตรวจสอบบัญชี',
            'รวม', 'สุทธิ', 'ทุนจดทะเบียน', 'หุ้นสามัญ',
            'ค่าใช้จ่ายค่าง่าย', 'เงินเบิกเกินบัญชี', 'ส่วนของผู้ถือหุ้น',
            'การปรับปรุง', 'ทุนที่ออก', 'มูลค่า', 'จัดสรร'
        ]

    def analyze_phrases(self):
        """Analyze all Thai phrases and identify issues"""

        print("🔍 Analyzing Thai phrases...")

        # Get all phrases
        self.cursor.execute('''
            SELECT id, phrase, confidence_score, word_count, status, needs_correction
            FROM thai_phrases
            ORDER BY id
            LIMIT 1000  -- Process first 1000 for testing
        ''')

        phrases = self.cursor.fetchall()

        quality_issues = []
        phrase_analysis = []

        for phrase_id, phrase, confidence, word_count, status, needs_correction in phrases:
            if not phrase or not is_thai_text(phrase.strip()):
                continue

            # Analyze single phrase
            analysis = self.analyze_single_phrase(phrase)

            if analysis['has_issues']:
                quality_issues.append({
                    'id': phrase_id,
                    'original': phrase,
                    'confidence': confidence,
                    'issues': analysis['issues'],
                    'suggestion': analysis['suggestion']
                })

            phrase_analysis.append(analysis)

        print(f"📊 Analysis complete:")
        print(f"   Phrases analyzed: {len(phrases)}")
        print(f"   Phrases with issues: {len(quality_issues)}")

        return quality_issues, phrase_analysis

    def analyze_single_phrase(self, phrase):
        """Analyze a single phrase for issues"""

        issues = []
        has_issues = False
        suggestion = phrase

        # Check for basic issues
        original = phrase

        # 1. Zero-width characters
        if re.search(r'[\u200B-\u200D\ufeff]', phrase):
            issues.append("zero_width_chars")
            suggestion = re.sub(r'[\u200B-\u200D\ufeff]', '', suggestion)
            has_issues = True

        # 2. Excessive whitespace
        if re.search(r'\s{3,}', phrase):
            issues.append("excessive_whitespace")
            suggestion = re.sub(r'\s+', ' ', suggestion)
            has_issues = True

        # 3. Missing spaces in long phrases
        if len(phrase) > 15 and ' ' not in phrase:
            # Try to identify potential word breaks
            cleaned = suggestion
            # Look for financial terms and add appropriate spacing
            for term in self.financial_terms:
                if term in cleaned:
                    # Term is present, might need spacing around it
                    pass
            issues.append("potential_missing_spaces")
            has_issues = True

        # 4. Check for repeated characters (OCR artifact)
        if re.search(r'(.)\1{3,}', phrase):
            issues.append("repeated_characters")
            suggestion = re.sub(r'(.)\1{3,}', r'\1', suggestion)
            has_issues = True

        # 5. Clean final suggestion
        suggestion = clean_thai_text(suggestion)

        # 6. Check if it contains known financial terms
        found_terms = []
        for term in self.financial_terms:
            if term in suggestion:
                found_terms.append(term)

        # 7. Flag phrases with no recognizable content
        if len(suggestion) > 10 and not found_terms:
            issues.append("unrecognized_content")
            has_issues = True

        return {
            'has_issues': has_issues,
            'issues': issues,
            'suggestion': suggestion if suggestion != original else None,
            'found_terms': found_terms,
            'length': len(suggestion)
        }

    def update_database_corrections(self, quality_issues):
        """Update database with correction suggestions"""

        print("🔧 Updating database with corrections...")

        updated_count = 0

        for issue in quality_issues:
            phrase_id = issue['id']
            suggestion = issue['suggestion']

            if suggestion and suggestion != issue['original']:
                # Update phrase record
                self.cursor.execute('''
                    UPDATE thai_phrases
                    SET needs_correction = TRUE,
                        correction_suggestion = ?,
                        status = 'reviewed',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (suggestion, phrase_id))

                updated_count += 1

                # Add to corrections dictionary if not exists
                self.cursor.execute('''
                    SELECT id FROM thai_ocr_corrections
                    WHERE error_pattern = ? AND correction = ? AND is_active = 1
                ''', (issue['original'], suggestion))

                if not self.cursor.fetchone():
                    self.cursor.execute('''
                        INSERT INTO thai_ocr_corrections
                        (error_pattern, correction, type, confidence, frequency, description,
                         example, priority, is_active, created_at, updated_at)
                        VALUES (?, ?, 'other', 0.8, 0, ?, ?, 'medium', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (
                        issue['original'],
                        suggestion,
                        f"Auto-correction for: {', '.join(issue['issues'])}",
                        f"{issue['original']} → {suggestion}"
                    ))

        self.conn.commit()
        print(f"✅ Updated {updated_count} phrases with correction suggestions")
        return updated_count

    def generate_report(self, quality_issues, phrase_analysis):
        """Generate analysis report"""

        print("\n📊 THAI PHRASE ANALYSIS REPORT")
        print("=" * 40)

        # Issue distribution
        issue_counts = defaultdict(int)
        for issue in quality_issues:
            for issue_type in issue['issues']:
                issue_counts[issue_type] += 1

        print("📈 Issue Distribution:")
        for issue_type, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"   {issue_type}: {count}")

        # Sample corrections
        print(f"\n💡 Sample Corrections Needed:")
        for i, issue in enumerate(quality_issues[:10]):
            print(f"   {i+1}. {issue['original'][:50]}...")
            if issue['suggestion']:
                print(f"      → {issue['suggestion'][:50]}...")
            else:
                print(f"      → [No suggestion]")
            print(f"      Issues: {', '.join(issue['issues'])}")
            print()

        # Financial terms found
        all_found_terms = set()
        for analysis in phrase_analysis:
            all_found_terms.update(analysis.get('found_terms', []))

        print(f"📋 Financial Terms Found ({len(all_found_terms)}):")
        for term in sorted(all_found_terms):
            print(f"   ✓ {term}")

        # Statistics
        confidences = [issue['confidence'] for issue in quality_issues if issue['confidence'] is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        print(f"\n📈 Statistics:")
        print(f"   Phrases needing correction: {len(quality_issues)}")
        print(f"   Average confidence: {avg_confidence:.3f}")

    def mark_high_quality_phrases(self):
        """Mark high-quality phrases as reviewed"""

        print("📋 Marking high-quality phrases...")

        # Mark phrases with high confidence and reasonable length
        self.cursor.execute('''
            UPDATE thai_phrases
            SET status = 'reviewed',
                needs_correction = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE confidence_score >= 0.8
            AND LENGTH(phrase) >= 3
            AND LENGTH(phrase) <= 50
            AND status = 'pending'
        ''')

        marked_count = self.cursor.rowcount
        self.conn.commit()

        print(f"✅ Marked {marked_count} high-quality phrases as reviewed")
        return marked_count

    def run_analysis(self):
        """Run complete analysis"""

        print("🚀 Starting Thai Phrase Analysis")
        print("=" * 35)

        try:
            # Step 1: Analyze phrases
            quality_issues, phrase_analysis = self.analyze_phrases()

            # Step 2: Generate report
            self.generate_report(quality_issues, phrase_analysis)

            # Step 3: Update database
            updated_count = self.update_database_corrections(quality_issues)

            # Step 4: Mark high-quality phrases
            marked_count = self.mark_high_quality_phrases()

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
            print(f"   Phrases updated with suggestions: {updated_count}")
            print(f"   High-quality phrases marked: {marked_count}")

            return True

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            self.conn.close()


def main():
    """Main execution"""
    analyzer = ThaiPhraseAnalyzer()
    success = analyzer.run_analysis()

    if success:
        print(f"\n🎉 Analysis completed!")
        print(f"\nNext steps:")
        print(f"1. Refresh the Dictionary Management page")
        print(f"2. Review phrases marked as needing correction")
        print(f"3. Accept or modify the suggested corrections")
        print(f"4. Add corrections to custom dictionary")


if __name__ == "__main__":
    main()