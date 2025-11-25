#!/usr/bin/env python3
"""
Analyze Thai OCR Results - Find bad patterns and improve dictionary

This script connects to the OCR database and analyzes Thai text patterns
to identify common OCR errors and suggest dictionary corrections.
"""

import sqlite3
import re
from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple, Optional
from utils.thai_utils import is_thai_text, clean_thai_text
import unicodedata


class ThaiOCRPatternAnalyzer:
    """Analyze Thai OCR results to identify common error patterns"""

    def __init__(self, db_path: str = "data/prototype.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

        # Thai character categories
        self.thai_consonants = "กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ"
        self.thai_vowels = "ะาิีึืุูเแโใไๅๆฯ"
        self.thai_tones = "่้๊๋"
        self.thai_digits = "๐๑๒๓๔๕๖๗๘๙"
        self.thai_punctuation = "ๆฯ"

        # Common OCR confusion patterns (based on visual similarity)
        self.confusion_patterns = {
            # Similar looking characters
            'บ': ['ป', 'ผ'],  # บ vs ป/ผ
            'ป': ['บ', 'ผ'],  # ป vs บ/ผ
            'ผ': ['บ', 'ป'],  # ผ vs บ/ป
            'ด': ['ถ'],      # ด vs ถ
            'ถ': ['ด'],      # ถ vs ด
            'ค': ['ข'],      # ค vs ข
            'ข': ['ค'],      # ข vs ค
            'ว': ['ถ'],      # ว vs ถ
            'ส': ['ษ'],      # ส vs ษ
            'อ': ['ป', 'บ'], # อ vs ป/บ

            # Consonant clusters that get confused
            'รร': ['ลน', 'ลร'],  # รร vs other combinations

            # Missing/extra characters
            'ำ': ['าม'],       # ำ vs าม
            'ต': ['ถ'],         # ต vs ถ
            'น': ['ร', 'ล'],     # น vs ร/ล
        }

        # Known valid Thai words (small dictionary for validation)
        # This would be expanded with a proper dictionary
        self.known_words = {
            'บริษัท', 'จำกัด', 'มหาชน', 'ห้าง', 'หุ้น', 'ส่วน', 'สามัญ',
            'เงิน', 'ทุน', 'จดทะเบียน', 'นิติ', 'บุคคล', 'กรุงเทพ', 'มหานคร',
            'ประเทศ', 'ไทย', 'การ', 'ค้า', 'ส่งออก', 'นำเข้า', 'อุตสาหกรรม',
            'ผลิต', 'บริการ', 'ลูกค้า', 'สินค้า', 'วัตถุดิบ', 'โรงงาน', 'สำนักงาน',
            'ที่อยู่', 'โทร', 'โทรศัพท์', 'อีเมล', 'เว็บไซต์', 'ติดต่อ'
        }

    def connect(self) -> bool:
        """Connect to database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Enable dict-like access
            self.cursor = self.conn.cursor()
            return True
        except Exception as e:
            print(f"Error connecting to database: {e}")
            return False

    def get_tables(self) -> List[str]:
        """Get list of tables in database"""
        if not self.cursor:
            return []

        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return [row[0] for row in self.cursor.fetchall()]

    def analyze_table_structure(self, table_name: str) -> Dict:
        """Analyze table structure and identify text columns"""
        if not self.cursor:
            return {}

        self.cursor.execute(f"PRAGMA table_info({table_name})")
        columns = self.cursor.fetchall()

        text_columns = []
        for col in columns:
            col_name = col[1]
            col_type = col[2].upper()
            if any(t in col_type for t in ['TEXT', 'CHAR', 'VARCHAR']):
                text_columns.append(col_name)

        return {
            'table': table_name,
            'columns': columns,
            'text_columns': text_columns
        }

    def extract_thai_text_from_table(self, table_name: str, limit: int = 1000) -> List[str]:
        """Extract Thai text from all text columns in a table"""
        if not self.cursor:
            return []

        structure = self.analyze_table_structure(table_name)
        if not structure['text_columns']:
            return []

        thai_texts = []

        try:
            # Query with limit to avoid memory issues
            cols = ', '.join(structure['text_columns'])
            query = f"SELECT {cols} FROM {table_name} LIMIT {limit}"
            self.cursor.execute(query)
            rows = self.cursor.fetchall()

            for row in rows:
                for col_name in structure['text_columns']:
                    text = row[col_name]
                    if text and is_thai_text(str(text)):
                        thai_texts.append(str(text))

        except Exception as e:
            print(f"Error extracting from {table_name}: {e}")

        return thai_texts

    def analyze_thai_patterns(self, texts: List[str]) -> Dict:
        """Analyze Thai text patterns to identify potential errors"""
        if not texts:
            return {}

        analysis = {
            'total_texts': len(texts),
            'character_frequency': Counter(),
            'word_frequency': Counter(),
            'suspicious_patterns': defaultdict(int),
            'unknown_words': defaultdict(int),
            'character_sequences': defaultdict(int),
            'potential_errors': []
        }

        # Character frequency analysis
        for text in texts:
            cleaned_text = clean_thai_text(text)
            for char in cleaned_text:
                if char in self.thai_consonants or char in self.thai_vowels or char in self.thai_tones:
                    analysis['character_frequency'][char] += 1

        # Extract Thai words/patterns
        for text in texts:
            cleaned_text = clean_thai_text(text)

            # Find Thai-like sequences
            thai_sequences = re.findall(r'[\u0E00-\u0E7F]+', cleaned_text)

            for sequence in thai_sequences:
                if len(sequence) >= 2:  # Only consider sequences with 2+ chars
                    analysis['character_sequences'][sequence] += 1

                    # Check if it's a known word
                    if sequence not in self.known_words:
                        analysis['unknown_words'][sequence] += 1

        # Identify suspicious patterns based on character frequency
        total_thai_chars = sum(count for char, count in analysis['character_frequency'].items()
                              if char in self.thai_consonants)

        if total_thai_chars > 0:
            for char, count in analysis['character_frequency'].items():
                if char in self.thai_consonants:
                    frequency = count / total_thai_chars
                    # Very high frequency might indicate OCR errors (e.g., บ being overused)
                    if frequency > 0.15:  # More than 15% of all consonants
                        analysis['suspicious_patterns'][f'High frequency: {char}'] = count

        # Check for common OCR error patterns
        for text in texts:
            cleaned_text = clean_thai_text(text)

            # Check for repeated characters (common OCR error)
            for char in self.thai_consonants:
                pattern = f"{char}{char}{char}"  # Triple same character
                if pattern in cleaned_text:
                    analysis['suspicious_patterns'][f'Repeated: {char*3}'] += cleaned_text.count(pattern)

            # Check for impossible consonant clusters
            invalid_clusters = [
                'บบ', 'ปป', 'ผผ', 'ถถ', 'ดด', 'วว', 'สส', 'ษษ'
            ]
            for cluster in invalid_clusters:
                if cluster in cleaned_text:
                    analysis['suspicious_patterns'][f'Invalid cluster: {cluster}'] += cleaned_text.count(cluster)

        return analysis

    def suggest_corrections(self, analysis: Dict) -> List[Dict]:
        """Suggest corrections based on pattern analysis"""
        suggestions = []

        # High frequency character corrections
        for pattern, count in analysis['suspicious_patterns'].items():
            if 'High frequency:' in pattern:
                char = pattern.split(': ')[1]
                if char in self.confusion_patterns:
                    for alternative in self.confusion_patterns[char]:
                        suggestions.append({
                            'type': 'high_frequency',
                            'pattern': char,
                            'correction': alternative,
                            'count': count,
                            'confidence': min(count / 100, 0.9),  # Confidence based on frequency
                            'example': f"Replace frequent {char} with {alternative}"
                        })

        # Unknown word corrections (most common first)
        for word, count in sorted(analysis['unknown_words'].items(), key=lambda x: x[1], reverse=True)[:20]:
            if count >= 3:  # Only consider words that appear at least 3 times
                # Check if it's a simple OCR error
                suggestions.append({
                    'type': 'unknown_word',
                    'pattern': word,
                    'correction': 'NEEDS_REVIEW',
                    'count': count,
                    'confidence': 0.5,
                    'example': f"Review word: {word} (appears {count} times)"
                })

        return suggestions

    def generate_dictionary_updates(self, suggestions: List[Dict]) -> List[Dict]:
        """Generate dictionary update entries from suggestions"""
        updates = []

        for suggestion in suggestions:
            if suggestion['confidence'] > 0.6:  # Only high-confidence suggestions
                updates.append({
                    'error_pattern': suggestion['pattern'],
                    'correction': suggestion['correction'],
                    'frequency': suggestion['count'],
                    'confidence': suggestion['confidence'],
                    'type': suggestion['type'],
                    'needs_review': suggestion['confidence'] < 0.8,
                    'example': suggestion['example']
                })

        return updates

    def run_full_analysis(self) -> Dict:
        """Run complete analysis of Thai OCR patterns"""
        if not self.connect():
            return {'error': 'Failed to connect to database'}

        print("🔍 Analyzing Thai OCR patterns...")

        # Get all tables
        tables = self.get_tables()
        print(f"📊 Found tables: {tables}")

        # Extract all Thai text
        all_thai_texts = []
        for table in tables:
            print(f"📋 Analyzing table: {table}")
            texts = self.extract_thai_text_from_table(table)
            all_thai_texts.extend(texts)
            print(f"   Found {len(texts)} Thai text entries")

        print(f"📝 Total Thai text entries: {len(all_thai_texts)}")

        # Analyze patterns
        analysis = self.analyze_thai_patterns(all_thai_texts)
        print(f"🔢 Analyzed {analysis['total_texts']} texts")
        print(f"📝 Found {len(analysis['character_sequences'])} unique Thai sequences")
        print(f"❓ Found {len(analysis['unknown_words'])} unknown word patterns")

        # Generate suggestions
        suggestions = self.suggest_corrections(analysis)
        print(f"💡 Generated {len(suggestions)} correction suggestions")

        # Generate dictionary updates
        updates = self.generate_dictionary_updates(suggestions)
        print(f"📚 Identified {len(updates)} potential dictionary updates")

        # Close connection
        self.conn.close()

        return {
            'analysis': analysis,
            'suggestions': suggestions,
            'dictionary_updates': updates,
            'total_texts_processed': len(all_thai_texts)
        }

    def save_results(self, results: Dict, filename: str = "thai_ocr_analysis.json"):
        """Save analysis results to JSON file"""
        import json

        # Convert defaultdict to regular dict for JSON serialization
        def convert_defaultdicts(obj):
            if isinstance(obj, defaultdict):
                return dict(obj)
            elif isinstance(obj, Counter):
                return dict(obj)
            return obj

        # Convert all defaultdicts and Counters
        results_serializable = {}
        for key, value in results.items():
            results_serializable[key] = convert_defaultdicts(value)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results_serializable, f, ensure_ascii=False, indent=2)

        print(f"💾 Results saved to {filename}")


def main():
    """Main execution function"""
    analyzer = ThaiOCRPatternAnalyzer()

    print("🚀 Starting Thai OCR Pattern Analysis")
    print("=" * 50)

    # Run full analysis
    results = analyzer.run_full_analysis()

    if 'error' in results:
        print(f"❌ Analysis failed: {results['error']}")
        return

    # Display top results
    print("\n🎯 Top Unknown Words:")
    unknown_words = results['analysis']['unknown_words']
    for word, count in sorted(unknown_words.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"   {word}: {count}")

    print("\n⚠️  Suspicious Patterns:")
    for pattern, count in results['analysis']['suspicious_patterns'].items():
        print(f"   {pattern}: {count}")

    print("\n💡 Top Correction Suggestions:")
    for suggestion in results['suggestions'][:10]:
        print(f"   {suggestion['pattern']} → {suggestion['correction']} (confidence: {suggestion['confidence']:.2f})")

    # Save results
    analyzer.save_results(results)

    print("\n✅ Analysis complete!")
    print(f"📊 Processed {results['total_texts_processed']} Thai text entries")
    print(f"💡 Found {len(results['dictionary_updates'])} potential dictionary improvements")


if __name__ == "__main__":
    main()