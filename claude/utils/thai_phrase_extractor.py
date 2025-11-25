"""
Thai Phrase Extractor

This utility extracts Thai phrases from OCR results and stores them in the database
for manual review and dictionary management.
"""

import sqlite3
import re
from typing import List, Dict, Tuple
from collections import defaultdict

from app.config import config
from utils.thai_utils import is_thai_text, clean_thai_text


class ThaiPhraseExtractor:
    """Extract and store Thai phrases from OCR results"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self.conn = None

    def connect(self):
        """Connect to database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            return True
        except Exception as e:
            print(f"Error connecting to database: {e}")
            return False

    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def extract_thai_phrases_from_text(self, text: str, context: Dict = None) -> List[Dict]:
        """
        Extract Thai phrases from a single text string

        Args:
            text: Text to analyze
            context: Additional context info (document_id, source_table, etc.)

        Returns:
            List of phrase dictionaries
        """
        if not text or not is_thai_text(text):
            return []

        phrases = []
        text = clean_thai_text(text)

        # Split by common Thai delimiters and punctuation
        delimiters = r'[,\.;:(){}\[\]\"\'—–\n\r\t]+'
        segments = re.split(delimiters, text)

        for i, segment in enumerate(segments):
            segment = segment.strip()

            if len(segment) < 2:  # Skip very short segments
                continue

            if is_thai_text(segment):
                # Count Thai characters vs total characters
                thai_chars = sum(1 for char in segment if ord(char) >= 3584)
                total_chars = len(segment)

                # Only include segments with significant Thai content
                if thai_chars / total_chars > 0.5:
                    word_count = len(segment.split())

                    phrase_data = {
                        'phrase': segment,
                        'word_count': word_count,
                        'thai_char_ratio': thai_chars / total_chars,
                        'position': i,
                        'segment_length': total_chars
                    }

                    # Add context if provided
                    if context:
                        phrase_data.update(context)

                    phrases.append(phrase_data)

        return phrases

    def extract_phrases_from_table_cells(self, table_id: int, document_id: int = None) -> List[Dict]:
        """Extract Thai phrases from all cells in a table"""
        if not self.connect():
            return []

        try:
            cursor = self.conn.cursor()

            # Get all cells from the table
            cursor.execute('''
                SELECT id, row_index, col_index, value, confidence_score
                FROM table_cells
                WHERE extracted_table_id = ?
                AND value IS NOT NULL
                ORDER BY row_index, col_index
            ''', (table_id,))

            cells = cursor.fetchall()
            all_phrases = []

            for cell_id, row_idx, col_idx, value, confidence in cells:
                if value and is_thai_text(value):
                    context = {
                        'source_table': 'table_cells',
                        'source_id': cell_id,
                        'document_id': document_id,
                        'table_id': table_id,
                        'row_index': row_idx,
                        'col_index': col_idx,
                        'confidence_score': confidence,
                        'context': f"Table {table_id}, Row {row_idx}, Col {col_idx}: {value[:50]}..."
                    }

                    phrases = self.extract_thai_phrases_from_text(str(value), context)
                    all_phrases.extend(phrases)

            return all_phrases

        except Exception as e:
            print(f"Error extracting phrases from table cells: {e}")
            return []
        finally:
            self.disconnect()

    def extract_phrases_from_document_text(self, document_id: int, text_blocks: List[str]) -> List[Dict]:
        """Extract Thai phrases from document text blocks"""
        all_phrases = []

        for i, text_block in enumerate(text_blocks):
            if is_thai_text(text_block):
                context = {
                    'source_table': 'processed_document_cache',
                    'source_id': document_id,
                    'document_id': document_id,
                    'block_index': i,
                    'confidence_score': 0.8,  # Default confidence for text blocks
                    'context': f"Document {document_id}, Block {i}: {text_block[:50]}..."
                }

                phrases = self.extract_thai_phrases_from_text(text_block, context)
                all_phrases.extend(phrases)

        return all_phrases

    def store_phrases(self, phrases: List[Dict]) -> int:
        """Store extracted phrases in the database"""
        if not phrases:
            return 0

        if not self.connect():
            return 0

        try:
            cursor = self.conn.cursor()
            stored_count = 0

            for phrase_data in phrases:
                # Prepare data for insertion
                insert_data = {
                    'phrase': phrase_data['phrase'],
                    'source_table': phrase_data.get('source_table', 'unknown'),
                    'source_id': phrase_data.get('source_id', 0),
                    'document_id': phrase_data.get('document_id'),
                    'confidence_score': phrase_data.get('confidence_score'),
                    'context': phrase_data.get('context', ''),
                    'word_count': phrase_data.get('word_count', 0),
                    'status': 'pending'
                }

                # Insert phrase if it doesn't already exist
                cursor.execute('''
                    INSERT OR IGNORE INTO thai_phrases
                    (phrase, source_table, source_id, document_id, confidence_score,
                     context, word_count, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (
                    insert_data['phrase'],
                    insert_data['source_table'],
                    insert_data['source_id'],
                    insert_data['document_id'],
                    insert_data['confidence_score'],
                    insert_data['context'],
                    insert_data['word_count'],
                    insert_data['status']
                ))

                if cursor.rowcount > 0:
                    stored_count += 1

            self.conn.commit()
            return stored_count

        except Exception as e:
            print(f"Error storing phrases: {e}")
            self.conn.rollback()
            return 0
        finally:
            self.disconnect()

    def process_document_phrases(self, document_id: int) -> Dict:
        """Process all Thai phrases for a specific document"""
        if not self.connect():
            return {'error': 'Database connection failed'}

        try:
            cursor = self.conn.cursor()

            # Get text blocks from processed document cache
            cursor.execute('''
                SELECT text_blocks FROM processed_document_cache
                WHERE document_id = ?
            ''', (document_id,))

            result = cursor.fetchone()
            text_blocks = []

            if result and result[0]:
                # Assuming text_blocks is stored as JSON or similar format
                try:
                    import json
                    text_blocks = json.loads(result[0])
                except:
                    # If not JSON, try to split by common delimiters
                    text_blocks = [result[0]]

            # Get all tables for this document
            cursor.execute('''
                SELECT id FROM extracted_tables
                WHERE document_id = ?
            ''', (document_id,))

            table_ids = [row[0] for row in cursor.fetchall()]

            all_phrases = []

            # Extract phrases from text blocks
            if text_blocks:
                phrases_from_text = self.extract_phrases_from_document_text(document_id, text_blocks)
                all_phrases.extend(phrases_from_text)

            # Extract phrases from table cells
            for table_id in table_ids:
                phrases_from_table = self.extract_phrases_from_table_cells(table_id, document_id)
                all_phrases.extend(phrases_from_table)

            # Store all phrases
            stored_count = self.store_phrases(all_phrases)

            return {
                'document_id': document_id,
                'phrases_extracted': len(all_phrases),
                'phrases_stored': stored_count,
                'tables_processed': len(table_ids),
                'text_blocks_processed': len(text_blocks)
            }

        except Exception as e:
            print(f"Error processing document phrases: {e}")
            return {'error': str(e)}
        finally:
            self.disconnect()

    def get_phrase_statistics(self) -> Dict:
        """Get statistics about stored Thai phrases"""
        if not self.connect():
            return {}

        try:
            cursor = self.conn.cursor()

            stats = {}

            # Total phrases
            cursor.execute('SELECT COUNT(*) FROM thai_phrases')
            stats['total_phrases'] = cursor.fetchone()[0]

            # By status
            cursor.execute('SELECT status, COUNT(*) FROM thai_phrases GROUP BY status')
            stats['by_status'] = dict(cursor.fetchall())

            # By source
            cursor.execute('SELECT source_table, COUNT(*) FROM thai_phrases GROUP BY source_table')
            stats['by_source'] = dict(cursor.fetchall())

            # Average word count
            cursor.execute('SELECT AVG(word_count) FROM thai_phrases WHERE word_count > 0')
            avg_words = cursor.fetchone()[0]
            stats['avg_word_count'] = round(avg_words, 2) if avg_words else 0

            # Phrases needing correction
            cursor.execute('SELECT COUNT(*) FROM thai_phrases WHERE needs_correction = TRUE')
            stats['needs_correction'] = cursor.fetchone()[0]

            # Confidence distribution
            cursor.execute('''
                SELECT
                    CASE
                        WHEN confidence_score >= 0.8 THEN 'high'
                        WHEN confidence_score >= 0.6 THEN 'medium'
                        ELSE 'low'
                    END as confidence_level,
                    COUNT(*) as count
                FROM thai_phrases
                WHERE confidence_score IS NOT NULL
                GROUP BY confidence_level
            ''')
            stats['confidence_distribution'] = dict(cursor.fetchall())

            return stats

        except Exception as e:
            print(f"Error getting phrase statistics: {e}")
            return {}
        finally:
            self.disconnect()


def process_all_documents_phrases():
    """Process Thai phrases for all documents in the database"""
    extractor = ThaiPhraseExtractor()

    if not extractor.connect():
        return {'error': 'Database connection failed'}

    try:
        cursor = extractor.conn.cursor()

        # Get all processed documents
        cursor.execute('SELECT id, file_name FROM documents ORDER BY id')
        documents = cursor.fetchall()

        results = []

        for doc_id, file_name in documents:
            print(f"Processing phrases for document {doc_id}: {file_name}")
            result = extractor.process_document_phrases(doc_id)
            result['file_name'] = file_name
            results.append(result)

        # Get final statistics
        final_stats = extractor.get_phrase_statistics()

        return {
            'processed_documents': results,
            'final_statistics': final_stats
        }

    except Exception as e:
        return {'error': str(e)}
    finally:
        extractor.disconnect()


if __name__ == "__main__":
    # Test the phrase extractor
    result = process_all_documents_phrases()

    if 'error' in result:
        print(f"Error: {result['error']}")
    else:
        print("✅ Phrase processing completed")
        print(f"Final statistics: {result['final_statistics']}")