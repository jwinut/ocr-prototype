#!/usr/bin/env python3
"""
Practical Thai Phrase Corrections

Creates corrections based on actual observed OCR issues from the Thai phrases
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config


def generate_common_corrections():
    """Generate corrections for common OCR errors observed"""

    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    print("🔧 Generating practical Thai phrase corrections...")

    # Common OCR error patterns we observed
    corrections = [
        # Character/spacing issues
        ("สินทรัพย์หมุนเวียนอืน", "สินทรัพย์หมุนเวียนอื่น", "character_fix"),
        ("สินค าคงเหลือ", "สินค้าคงเหลือ", "spacing"),
        ("สุทธิ", "สุทธิ", "character_fix"),
        ("จัดสรร สํารองตามกฎหมาย", "จัดสรร - สํารองตามกฎหมาย", "spacing"),
        ("ผู้ตรวจสอบบัญชี จันทร์เพ็ญ เตชะกําธร 31/05/2568", "ผู้ตรวจสอบบัญชี: จันทร์เพ็ญ เตชะกําธร 31/05/2568", "spacing"),
        ("การปรับปรุงด วยค่าใช จ่ายภาษี เงินได", "การปรับปรุงด้วยค่าใช้จ่ายภาษีเงินได้", "spacing"),
        ("คํานวณงบกระแสเงินสด โดยวิธีทางอ ้อม", "คํานวณงบกระแสเงินสด โดยวิธีทางอ้อม", "character_fix"),
        ("กําไรจากกิจกรรมดําเนินงาน ก่อนการเปลียนแปลงใน สินท", "กําไรจากกิจกรรมดําเนินงานก่อนการเปลี่ยนแปลงในสินทรัพย์", "character_fix"),

        # Missing spaces in long phrases
        ("เงินสดและรายการเทียบเท่าเงินสด", "เงินสดและรายการเทียบเท่าเงินสด", "spacing"),
        ("เงินสดและรายการเทียบเท่าเงินสดเพิมขึน", "เงินสดและรายการเทียบเท่าเงินสดเพิ่มขึน", "spacing"),
        ("เงินสดและรายการเทียบเท่าเงินสดต ้นงวด", "เงินสดและรายการเทียบเท่าเงินสดต้นงวด", "spacing"),
        ("เงินสดและรายการเทียบเท่าเงินสดปลายงวด", "เงินสดและรายการเทียบเท่าเงินสดปลายงวด", "spacing"),

        # Word boundary issues
        ("รวมส่วนของผู้ถือหุ้น", "รวมส่วนของผู้ถือหุ้น", "spacing"),
        ("รวมหนิสินและส่วนของผู้ถือหุ้น", "รวมหนีสินและส่วนของผู้ถือหุ้น", "character_fix"),
        ("รวมรายการอืน - สินทรัพย์หมุนเวียน", "รวมรายการอื่น - สินทรัพย์หมุนเวียน", "character_fix"),
        ("รวมส่วนของบริษัทใหญ่", "รวมส่วนของบริษัทใหญ่", "spacing"),

        # Date formatting
        ("31/05/2568", "31/05/2568", "date_format"),

        # Number formatting
        ("จํานวนหุ ้น - จดทะเบียน", "จำนวนหุ้น - จดทะเบียน", "character_fix"),
        ("จํานวนหุ ้น - ทีออกและเรียกชําระแล ว", "จำนวนหุ้น - ที่ออกและเรียกชำระแล้ว", "character_fix"),
        ("มูลค่าทีตราไว", "มูลค่าที่ตราไว", "character_fix"),

        # Common character OCR errors
        ("ค้ างรับ", "ค่างรับ", "character_fix"),
        ("ค่าใช จ่ายค างจ่าย", "ค่าใช้จ่ายค่างจ่าย", "character_fix"),
        ("ข้อมูลเพิมเติมในส่วนของผู้", "ข้อมูลเพิ่มเติมในส่วนของผู้", "character_fix"),
        ("ถือหุ้น", "ถือหุ้น", "character_fix"),

        # Cleaning up trailing/leading issues
        ("สินทรัพย์...", "สินทรัพย์", "cleanup"),
        ("สุทธิ...", "สุทธิ", "cleanup"),
        ("กําไร...", "กำไร", "cleanup"),
        ("ขาดทุน...", "ขาดทุน", "cleanup"),
    ]

    corrections_added = 0

    for original, correction, correction_type in corrections:
        # Check if correction already exists
        cursor.execute('''
            SELECT id FROM thai_ocr_corrections
            WHERE error_pattern = ? AND correction = ? AND is_active = 1
        ''', (original, correction))

        if not cursor.fetchone():
            # Add new correction
            cursor.execute('''
                INSERT INTO thai_ocr_corrections
                (error_pattern, correction, type, confidence, frequency, description,
                 example, priority, is_active, created_at, updated_at)
                VALUES (?, ?, ?, 0.9, 1, ?, ?, 'high', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (
                original,
                correction,
                correction_type,
                f"Practical correction for {correction_type}",
                f"{original} → {correction}"
            ))

            corrections_added += 1
            print(f"   ✅ Added: {original[:40]}... → {correction[:40]}...")

            # Update phrases that have this exact error
            cursor.execute('''
                UPDATE thai_phrases
                SET correction_suggestion = ?,
                    needs_correction = TRUE,
                    status = 'reviewed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE phrase = ? AND correction_suggestion IS NULL
            ''', (correction, original))

            updated_phrases = cursor.rowcount
            if updated_phrases > 0:
                print(f"      → Updated {updated_phrases} phrase(s)")

    conn.commit()

    print(f"\n🎉 Generated {corrections_added} practical corrections")

    return corrections_added


def mark_phrases_for_review():
    """Mark additional phrases that need manual review"""

    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    print("\n📋 Marking additional phrases for review...")

    # Mark phrases with common issues
    review_criteria = [
        # Very short phrases (likely incomplete)
        "LENGTH(phrase) < 5",
        # Very long phrases (likely concatenated)
        "LENGTH(phrase) > 60",
        # Phrases with confidence score below 0.5
        "confidence_score < 0.5",
        # Phrases with excessive word count
        "word_count > 15",
    ]

    total_marked = 0
    for criterion in review_criteria:
        cursor.execute(f'''
            UPDATE thai_phrases
            SET needs_correction = TRUE,
                status = 'reviewed',
                updated_at = CURRENT_TIMESTAMP
            WHERE {criterion}
            AND needs_correction = FALSE
        ''')

        marked_count = cursor.rowcount
        total_marked += marked_count
        print(f"   ✓ Marked {marked_count} phrases for: {criterion}")

    conn.commit()
    print(f"\n📊 Total phrases marked for review: {total_marked}")

    return total_marked


def update_statistics():
    """Update phrase statistics"""

    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    print("\n📊 Updating phrase statistics...")

    # Get current stats
    cursor.execute('''
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN needs_correction = TRUE THEN 1 END) as needs_correction,
            COUNT(CASE WHEN correction_suggestion IS NOT NULL AND correction_suggestion != '' THEN 1 END) as has_suggestion,
            COUNT(CASE WHEN status = 'corrected' THEN 1 END) as corrected,
            COUNT(CASE WHEN status = 'reviewed' THEN 1 END) as reviewed
        FROM thai_phrases
    ''')

    stats = cursor.fetchone()
    total, needs_correction, has_suggestion, corrected, reviewed = stats

    print(f"📈 Current Phrase Statistics:")
    print(f"   Total phrases: {total:,}")
    print(f"   Need correction: {needs_correction:,}")
    print(f"   Have suggestions: {has_suggestion:,}")
    print(f"   Corrected: {corrected:,}")
    print(f"   Reviewed: {reviewed:,}")

    conn.close()
    return stats


def main():
    """Main execution function"""
    print("🚀 Practical Thai Phrase Correction System")
    print("=" * 50)

    try:
        # Step 1: Generate common corrections
        corrections_added = generate_common_corrections()

        # Step 2: Mark phrases for review
        marked_for_review = mark_phrases_for_review()

        # Step 3: Update statistics
        stats = update_statistics()

        print(f"\n🎯 SUMMARY:")
        print(f"   Corrections added: {corrections_added}")
        print(f"   Phrases marked for review: {marked_for_review}")
        print(f"   Total phrases processed: {stats[0]:,}")

        print(f"\n✅ Practical corrections completed!")
        print(f"\nNext steps:")
        print(f"1. Refresh the Dictionary Management page")
        print(f"2. Review phrases marked as needing correction")
        print(f"3. Accept/reject suggested corrections")
        print(f"4. Add approved corrections to custom dictionary")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()