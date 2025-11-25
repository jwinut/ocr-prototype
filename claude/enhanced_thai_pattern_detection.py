#!/usr/bin/env python3
"""
Enhanced Thai OCR Pattern Detection - Targeted Error Identification

This script specifically identifies common Thai OCR errors that were missed
in the initial analysis, based on real-world examples from financial documents.
"""

import sqlite3
import re
from datetime import datetime
from collections import Counter, defaultdict
from typing import Dict, List, Set
from utils.thai_utils import is_thai_text, clean_thai_text


class EnhancedThaiPatternDetector:
    """Enhanced detection for specific Thai OCR errors"""

    def __init__(self, db_path: str = "data/prototype.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

        # Enhanced error patterns based on real examples
        self.specific_errors = {
            # Character corruption (ำ character issues)
            'งบปี': 'งบปี',  # Should be งบปี (proper spacing)
            'งบบริษัท': 'งบบริษัท',  # Company financial statements

            # Name/title corruption
            'จันทร์เพ็ญ': 'จันทร์เพ็ญ',  # Thai name corruption
            'เตชะกําธร': 'เตชะกําธร',  # Thai name corruption

            # Company type formatting
            'จํากัด': 'จำกัด',  # Missing/ corrupted ำ character
            'จํากัด': 'จำกัด',  # Character duplication/corruption

            # Common financial terms
            'งบกําไร': 'งบกำไร',  # Income statement heading
            'งบสรุป': 'งบสรุป',  # Financial statements
            'ขาดทุน': 'ขาดทุน',  # Net loss

            # Character spacing issues
            'สุทธิ': 'สุทธิ',  # Thai spacing

            # Mixed Thai-English formatting
            'COMPANY.,LTD.': 'COMPANY LTD',  # English punctuation

            # Specific name corrections
            'จํานวนปี': 'จำนวนปี',  # Number of years
        }

        # Pattern-based corrections using regex
        self.pattern_corrections = [
            # Fix ำ character corruption
            (r'จํากั', 'จำกัด'),
            (r'คํานวณ', 'คำนวณ'),
            (r'กําไร', 'กำไร'),
            (r'งบบริษัท', 'งบบริษัท'),
            (r'งบปี', 'งบปี'),
            (r'จํานวนปี', 'จำนวนปี'),

            # Fix spacing around Thai words
            (r'บริษัท\s+จํากัด', 'บริษัทจำกัด'),
            (r'บริษัท\s+(\w)', r'บริษัท \1'),

            # Fix name formatting
            (r'จันทร์เพ็ญ\s+เตชะกําธร', 'จันทร์เพ็ญ เตชะกําธร'),

            # Financial statement formatting
            (r'งบกําไรขาดทุน\s*\(([^)]+)\)', r'งบกำไรขาดทุน (\1)'),
            (r'งบสรุป\s*:\s*งบบริษัท', 'งบสรุป: งบบริษัท'),

            # Thai period formatting
            (r'([0-9,]+)\.([0-9]{2})\s+บาท', r'\1.\2 บาท'),

            # Mixed punctuation
            (r'LTD\.', 'LTD'),
            (r'COMPANY,\s*LTD\.', 'COMPANY LTD'),
        ]

        # Common Thai business terms that should be recognized as correct
        self.valid_terms = {
            'บริษัท', 'จำกัด', 'มหาชน', 'ห้างหุ้นส่วน', 'สามัญ',
            'งบการเงิน', 'งบดุล', 'งบกำไร', 'งบสรุป', 'งบแสดง',
            'รายได้', 'รายจ่าย', 'กำไร', 'ขาดทุน', 'ทุน', 'สินทรัพย์',
            'หนี้', 'สุทธิ', 'ดอกเบี้ย', 'ภาษี', 'บาท',
            'ผู้ตรวจสอบบัญชี', 'กรรมการ', 'ประธาน', 'จดทะเบียน',
            'สำนักงานใหญ่', 'ที่อยู่', 'โทรศัพท์', 'อีเมล', 'เว็บไซต์',
        }

    def connect(self) -> bool:
        """Connect to database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            return True
        except Exception as e:
            print(f"Error connecting to database: {e}")
            return False

    def extract_sample_texts(self, limit: int = 100) -> List[str]:
        """Extract sample texts for manual verification"""
        if not self.cursor:
            return []

        texts = []

        try:
            # Get sample table content
            self.cursor.execute("""
                SELECT value FROM table_cells
                WHERE value IS NOT NULL AND LENGTH(value) > 10
                ORDER BY RANDOM()
                LIMIT ?
            """, (limit,))

            for row in self.cursor.fetchall():
                if is_thai_text(row[0]):
                    texts.append(row[0])

            # Get sample document content
            self.cursor.execute("""
                SELECT file_path, document_type FROM documents
                WHERE file_path LIKE '%.pdf'
                ORDER BY RANDOM()
                LIMIT 20
            """)

            for row in self.cursor.fetchall():
                texts.append(f"Document: {row[0]} ({row[1]})")

        except Exception as e:
            print(f"Error extracting samples: {e}")

        return texts

    def find_specific_errors(self, texts: List[str]) -> Dict:
        """Find specific Thai OCR errors based on enhanced patterns"""
        error_analysis = {
            'total_texts': len(texts),
            'errors_found': defaultdict(int),
            'error_examples': defaultdict(list),
            'corrections_needed': []
        }

        for text in texts:
            cleaned_text = clean_thai_text(text)

            # Check each specific error pattern
            for error, correction in self.specific_errors.items():
                if error in cleaned_text:
                    error_analysis['errors_found'][error] += 1

                    # Store example (first occurrence only)
                    if len(error_analysis['error_examples'][error]) < 3:
                        error_analysis['error_examples'][error].append(text)

                    # Add to corrections list if not already added
                    existing = [c['error_pattern'] for c in error_analysis['corrections_needed']]
                    if error not in existing:
                        error_analysis['corrections_needed'].append({
                            'error_pattern': error,
                            'correction': correction,
                            'frequency': error_analysis['errors_found'][error],
                            'type': 'specific_corruption',
                            'confidence': 0.95,
                            'description': f"Specific OCR error: {error} → {correction}",
                            'example': f"Found: {error}, Correct: {correction}"
                        })

            # Apply pattern-based corrections
            for pattern, replacement in self.pattern_corrections:
                if re.search(pattern, cleaned_text):
                    matches = re.findall(pattern, cleaned_text)
                    if matches:
                        error_key = f"Pattern: {pattern[:20]}..."
                        error_analysis['errors_found'][error_key] += len(matches)

                        if len(error_analysis['error_examples'][error_key]) < 3:
                            error_analysis['error_examples'][error_key].append(text)

                        # Add to corrections if not already present
                        existing = [c['error_pattern'] for c in error_analysis['corrections_needed']]
                        if pattern not in existing:
                            error_analysis['corrections_needed'].append({
                                'error_pattern': pattern,
                                'correction': replacement,
                                'frequency': len(matches),
                                'type': 'pattern_based',
                                'confidence': 0.85,
                                'description': f"Regex pattern: {pattern} → {replacement}",
                                'example': f"Example: {matches[0]} → {replacement}"
                            })

        return error_analysis

    def analyze_current_corrections(self) -> Dict:
        """Analyze current corrections to see what errors they address"""
        if not self.cursor:
            return {}

        try:
            self.cursor.execute("""
                SELECT error_pattern, correction, frequency, type, description
                FROM thai_ocr_corrections
                WHERE is_active = 1
                ORDER BY frequency DESC
            """)

            current_corrections = {}
            for row in self.cursor.fetchall():
                current_corrections[row['error_pattern']] = dict(row)

            return current_corrections

        except Exception as e:
            print(f"Error analyzing current corrections: {e}")
            return {}

    def generate_enhanced_corrections(self, new_errors: List[Dict],
                                       current_corrections: Dict) -> List[Dict]:
        """Generate enhanced corrections combining new findings with existing"""
        enhanced_corrections = []

        # Add high-priority new corrections
        for error in new_errors:
            # Skip if already exists with same correction
            existing_key = f"{error['error_pattern']}->{error['correction']}"
            if existing_key in [f"{c['error_pattern']}->{c['correction']}" for c in enhanced_corrections]:
                continue

            # Prioritize by frequency and confidence
            if error['frequency'] >= 5 or error['confidence'] >= 0.90:
                enhanced_corrections.append(error)

        # Keep existing corrections that are still valuable
        for pattern, correction in current_corrections.items():
            if correction['frequency'] >= 10:  # Keep well-established corrections
                enhanced_corrections.append({
                    'error_pattern': pattern,
                    'correction': correction['correction'],
                    'frequency': correction['frequency'],
                    'type': correction['type'],
                    'confidence': 0.85,
                    'description': correction['description'],
                    'example': f"Existing: {pattern} → {correction['correction']}",
                    'priority': 'maintained'
                })

        # Sort by frequency and confidence
        enhanced_corrections.sort(
            key=lambda x: (x['frequency'], x['confidence']),
            reverse=True
        )

        return enhanced_corrections

    def create_error_examples_report(self, error_analysis: Dict) -> str:
        """Create detailed error examples report"""
        report_lines = []
        report_lines.append("# Thai OCR Error Examples Report")
        report_lines.append("=" * 50)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Total texts analyzed: {error_analysis['total_texts']}")
        report_lines.append(f"Error types found: {len(error_analysis['errors_found'])}")
        report_lines.append("")

        report_lines.append("## Error Examples by Type")
        report_lines.append("")

        for error_type, examples in error_analysis['error_examples'].items():
            count = error_analysis['errors_found'][error_type]
            report_lines.append(f"### {error_type} (Found {count} times)")
            report_lines.append("")

            for i, example in enumerate(examples[:2], 1):  # Show up to 2 examples
                # Clean up the example for readability
                if len(example) > 200:
                    example = example[:200] + "..."

                report_lines.append(f"Example {i}:")
                report_lines.append(f"```")
                report_lines.append(example)
                report_lines.append("```")
                report_lines.append("")

        return '\n'.join(report_lines)

    def run_enhanced_analysis(self):
        """Run the enhanced pattern detection"""
        print("🔍 Running Enhanced Thai OCR Pattern Detection...")
        print("=" * 60)

        if not self.connect():
            return

        # Get sample texts
        texts = self.extract_sample_texts(limit=200)
        print(f"📝 Analyzing {len(texts)} sample texts...")

        # Find specific errors
        error_analysis = self.find_specific_errors(texts)
        print(f"❓ Found {len(error_analysis['errors_found'])} error types")
        print(f"💡 Generated {len(error_analysis['corrections_needed'])} correction candidates")

        # Analyze current corrections
        current_corrections = self.analyze_current_corrections()
        print(f"📚 Current corrections in database: {len(current_corrections)}")

        # Generate enhanced corrections
        enhanced_corrections = self.generate_enhanced_corrections(
            error_analysis['corrections_needed'],
            current_corrections
        )
        print(f"🎯 Enhanced corrections generated: {len(enhanced_corrections)}")

        # Create examples report
        examples_report = self.create_error_examples_report(error_analysis)
        with open('thai_ocr_error_examples.md', 'w', encoding='utf-8') as f:
            f.write(examples_report)
        print("💾 Error examples saved to thai_ocr_error_examples.md")

        # Display top findings
        print("\n🎯 Top New Error Patterns Found:")
        for i, error in enumerate(error_analysis['corrections_needed'][:10], 1):
            print(f"   {i}. {error['error_pattern']} → {error['correction']} "
                  f"(freq: {error['frequency']}, conf: {error['confidence']:.2f})")

        print(f"\n📊 Error Type Summary:")
        for error_type, count in sorted(error_analysis['errors_found'].items(),
                                     key=lambda x: x[1], reverse=True):
            print(f"   {error_type}: {count} occurrences")

        # Close connection
        self.conn.close()

        return error_analysis, enhanced_corrections


def main():
    """Main execution function"""
    detector = EnhancedThaiPatternDetector()
    error_analysis, enhanced_corrections = detector.run_enhanced_analysis()

    print("\n✅ Enhanced pattern detection complete!")


if __name__ == "__main__":
    main()