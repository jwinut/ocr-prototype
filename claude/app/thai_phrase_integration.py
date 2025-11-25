
# Thai Phrase Integration for Main App

def extract_phrases_after_processing(document_id: int) -> dict:
    """Extract phrases after document processing is complete"""
    try:
        from utils.thai_phrase_extractor import ThaiPhraseExtractor
        extractor = ThaiPhraseExtractor()
        return extractor.process_document_phrases(document_id)
    except Exception as e:
        return {'error': str(e)}

def get_phrase_count_for_dashboard():
    """Get phrase statistics for dashboard display"""
    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM thai_phrases')
        total = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM thai_phrases WHERE needs_correction = TRUE')
        needs_review = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM thai_phrases WHERE status = "pending"')
        pending = cursor.fetchone()[0]

        conn.close()

        return {
            'total_phrases': total,
            'needs_review': needs_review,
            'pending_review': pending,
            'review_rate': (total - pending) / total if total > 0 else 0
        }
    except Exception as e:
        return {'error': str(e)}
