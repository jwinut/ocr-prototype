"""
Thai OCR Post-Processing Module

Enhances OCR output for Thai financial documents by:
1. Fixing character spacing issues (vowels/tone marks separated from base characters)
2. Correcting common Thai OCR errors using spell checking
3. Converting parenthesized numbers to negative values (accounting format)
4. Normalizing Thai text formatting
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass

# Try to import PyThaiNLP for advanced spell correction
try:
    from pythainlp.spell import correct as pythainlp_correct
    from pythainlp.tokenize import word_tokenize
    from pythainlp.util import normalize as pythainlp_normalize
    PYTHAINLP_AVAILABLE = True
except ImportError:
    PYTHAINLP_AVAILABLE = False


@dataclass
class PostProcessResult:
    """Result from post-processing Thai OCR text."""
    original: str
    corrected: str
    corrections_made: int
    negative_numbers_converted: int


# Thai vowel and tone mark patterns that may get separated during OCR
# These should be attached to the preceding consonant
THAI_UPPER_VOWELS = '\u0e31\u0e34\u0e35\u0e36\u0e37\u0e38\u0e39\u0e47\u0e4c\u0e4d'  # ั ิ ี ึ ื ุ ู ็ ์ ํ
THAI_TONE_MARKS = '\u0e48\u0e49\u0e4a\u0e4b'  # ่ ้ ๊ ๋
THAI_TRAILING_VOWELS = '\u0e32\u0e33'  # า ำ (follow consonant, often separated by OCR)
THAI_COMBINING_MARKS = THAI_UPPER_VOWELS + THAI_TONE_MARKS
THAI_ALL_ATTACHABLE = THAI_COMBINING_MARKS + THAI_TRAILING_VOWELS

# Common OCR errors in Thai financial documents
# Maps incorrect text to correct text
COMMON_OCR_CORRECTIONS = {
    # Missing tone marks and vowels
    'ลูกหนีการค า': 'ลูกหนี้การค้า',
    'หนีสิน': 'หนี้สิน',
    'ทีดิน': 'ที่ดิน',
    'เงินให กู ยืม': 'เงินให้กู้ยืม',
    'เงินให้กู ยืม': 'เงินให้กู้ยืม',
    'เจ าหนี': 'เจ้าหนี้',
    'เจ้าหนี': 'เจ้าหนี้',
    'ค าใช จ าย': 'ค่าใช้จ่าย',
    'ค่าใช้จ่าย': 'ค่าใช้จ่าย',
    'กําไร': 'กำไร',
    'กาไร': 'กำไร',
    'ราคาตามบัญชี': 'ราคาตามบัญชี',
    'เงินปันผล': 'เงินปันผล',
    'รายได ': 'รายได้',
    'รายได': 'รายได้',
    'ค าเสื่อม': 'ค่าเสื่อม',
    'สินทรัพย ': 'สินทรัพย์',
    'สินทรัพย': 'สินทรัพย์',
    'หลักทรัพย ': 'หลักทรัพย์',
    'หลักทรัพย': 'หลักทรัพย์',

    # Common financial terms
    'บริษัท': 'บริษัท',
    'จํากัด': 'จำกัด',
    'มหาชน': 'มหาชน',
    'ทุนจดทะเบียน': 'ทุนจดทะเบียน',
    'งบการเงิน': 'งบการเงิน',
    'งบดุล': 'งบดุล',
    'งบกาไรขาดทุน': 'งบกำไรขาดทุน',
    'งบกระแสเงินสด': 'งบกระแสเงินสด',

    # Common spacing issues
    'ส่ วน': 'ส่วน',
    'บั ญชี': 'บัญชี',
    'รว ม': 'รวม',
    'ทั้ งหมด': 'ทั้งหมด',

    # Additional financial terms with spacing/missing marks
    # (Include both with-space and without-space versions)
    'สินค า': 'สินค้า',
    'สินคา': 'สินค้า',  # After spacing fix
    'สินค าคงเหลือ': 'สินค้าคงเหลือ',
    'สินคาคงเหลือ': 'สินค้าคงเหลือ',  # After spacing fix
    'ระยะยาว': 'ระยะยาว',  # Preserve correct term
    'เงินให กู ยืม': 'เงินให้กู้ยืม',
    'เงินให กูยืม': 'เงินให้กู้ยืม',  # After partial spacing fix
    'เงินให กู ยืมระยะยาว': 'เงินให้กู้ยืมระยะยาว',
    'เงินให กูยืมระยะยาว': 'เงินให้กู้ยืมระยะยาว',  # After partial spacing fix
    'เงินกู ยืม': 'เงินกู้ยืม',
    'เงินกูยืม': 'เงินกู้ยืม',  # After spacing fix
    'เงินกู ยืมระยะยาว': 'เงินกู้ยืมระยะยาว',
    'เงินกูยืมระยะยาว': 'เงินกู้ยืมระยะยาว',  # After spacing fix
    'เงินกู ยืมระยะสั้น': 'เงินกู้ยืมระยะสั้น',
    'เงินกูยืมระยะสั้น': 'เงินกู้ยืมระยะสั้น',  # After spacing fix
    'ค าใช จ าย': 'ค่าใช้จ่าย',
    'คาใช จาย': 'ค่าใช้จ่าย',  # After spacing fix
    'คาใชจาย': 'ค่าใช้จ่าย',  # After full spacing fix
    'ค าเสื่อมราคา': 'ค่าเสื่อมราคา',
    'คาเสื่อมราคา': 'ค่าเสื่อมราคา',  # After spacing fix
    'ที ดิน': 'ที่ดิน',
    'ลูกหนีการค า': 'ลูกหนี้การค้า',
    'ลูกหนีการคา': 'ลูกหนี้การค้า',  # After spacing fix
    'เจ าหนี': 'เจ้าหนี้',
    'เจาหนี': 'เจ้าหนี้',  # After spacing fix
    'เจ ้าหนีการค า': 'เจ้าหนี้การค้า',
    'เจ้าหนีการคา': 'เจ้าหนี้การค้า',  # After spacing fix (still missing ้ on ค)
    'เจ้าหนีการค า': 'เจ้าหนี้การค้า',  # Partial spacing fix
    'อาคาร': 'อาคาร',
    'อุปกรณ ': 'อุปกรณ์',
    'อุปกรณ': 'อุปกรณ์',  # After spacing fix

    # PyThaiNLP overcorrections to fix (specific financial terms)
    'ลูกหนี้หอการค้า': 'ลูกหนี้การค้า',
    'ระยะทาง': 'ระยะยาว',  # Common PyThaiNLP overcorrection in financial context

    # NEW: Terms from Cash Flow statement analysis (Nov 2024)
    # Interest and financial terms
    'ดอกเบียจ่าย': 'ดอกเบี้ยจ่าย',
    'ดอกเบีย': 'ดอกเบี้ย',

    # Tax terms
    'ภาษีเงินได': 'ภาษีเงินได้',
    'ภาษี เงินได': 'ภาษีเงินได้',
    'เงินได': 'เงินได้',

    # "Other" terms (อื่น with wrong character)
    'อืน': 'อื่น',
    'อืนๆ': 'อื่นๆ',
    'รายการอืนๆ': 'รายการอื่นๆ',
    'สินทรัพย์หมุนเวียนอืน': 'สินทรัพย์หมุนเวียนอื่น',
    'สินทรัพย์ไม่หมุนเวียนอืน': 'สินทรัพย์ไม่หมุนเวียนอื่น',
    'หนีสินหมุนเวียนอืน': 'หนี้สินหมุนเวียนอื่น',
    'หนีสินไม่หมุนเวียนอืน': 'หนี้สินไม่หมุนเวียนอื่น',
    'เจ าหนีอืน': 'เจ้าหนี้อื่น',
    'เจาหนีอืน': 'เจ้าหนี้อื่น',
    'เงินกู ยืมระยะยาวอืน': 'เงินกู้ยืมระยะยาวอื่น',
    'เงินกูยืมระยะยาวอืน': 'เงินกู้ยืมระยะยาวอื่น',
    'ระยะยาวอืน': 'ระยะยาวอื่น',

    # Increase/Decrease terms
    'เพิมขึน': 'เพิ่มขึ้น',
    'เพิม': 'เพิ่ม',
    'ลดลง': 'ลดลง',

    # Short-term (ระยะสั้น)
    'ระยะสัน': 'ระยะสั้น',
    'ระยะสั น': 'ระยะสั้น',

    # Calculation terms
    'คํานวณ': 'คำนวณ',
    'คานวณ': 'คำนวณ',

    # Accrued expenses
    'ค างจ่าย': 'ค้างจ่าย',
    'คางจ่าย': 'ค้างจ่าย',
    'ค่าใช จ่ายค างจ่าย': 'ค่าใช้จ่ายค้างจ่าย',
    'ค่าใชจ่ายคางจ่าย': 'ค่าใช้จ่ายค้างจ่าย',

    # Accrued revenue
    'ค้ างรับ': 'ค้างรับ',
    'คางรับ': 'ค้างรับ',
    'รายได้ ค้ างรับ': 'รายได้ค้างรับ',
    'รายได้คางรับ': 'รายได้ค้างรับ',

    # Prepaid expenses
    'จ่ายล่วงหน้า': 'จ่ายล่วงหน้า',
    'ค่าใช จ่ายจ่ายล่วงหน้า': 'ค่าใช้จ่ายจ่ายล่วงหน้า',

    # Beginning/End of period
    'ต ้นงวด': 'ต้นงวด',
    'ตนงวด': 'ต้นงวด',
    'ปลายงวด': 'ปลายงวด',

    # Cash flow specific
    'ได ้มาจาก': 'ได้มาจาก',
    'ไดมาจาก': 'ได้มาจาก',
    'ใช ้ไป': 'ใช้ไป',
    'ใชไป': 'ใช้ไป',
    'ใช ้ไป ใน': 'ใช้ไปใน',

    # Investment terms
    'เงินลงทุนระยะยาว': 'เงินลงทุนระยะยาว',
    'เงินลงทุน ระยะยาวอืน': 'เงินลงทุนระยะยาวอื่น',

    # Indirect method
    'วิธีทางอ ้อม': 'วิธีทางอ้อม',
    'วิธีทางออม': 'วิธีทางอ้อม',

    # Company name patterns
    'จํากั ด': 'จำกัด',
    'จากัด': 'จำกัด',

    # Adjustments
    'การปรับปรุงด วย': 'การปรับปรุงด้วย',
    'การปรับปรุงดวย': 'การปรับปรุงด้วย',

    # Bank overdraft
    'เงินเบิกเกินบัญชี': 'เงินเบิกเกินบัญชี',

    # Changes in assets
    'การเปลียนแปลง': 'การเปลี่ยนแปลง',
    'เปลียนแปลง': 'เปลี่ยนแปลง',

    # Net profit/loss
    'กําไร': 'กำไร',
    'ขาดทุน': 'ขาดทุน',

    # Equivalent (เทียบเท่า)
    'เทียบเท่า': 'เทียบเท่า',

    # NEW: Income Statement (งบกำไรขาดทุน) terms - Nov 2024
    # Income/Revenue terms
    'รายได้ อืน': 'รายได้อื่น',
    'รายได้อืน': 'รายได้อื่น',  # After spacing fix

    # Cost of goods sold (ต้นทุนสินค้าที่ขาย)
    'ต้ นทุนสินค าทีขาย': 'ต้นทุนสินค้าที่ขาย',
    'ต้นทุนสินค าทีขาย': 'ต้นทุนสินค้าที่ขาย',  # After partial spacing fix
    'ต้นทุนสินคาทีขาย': 'ต้นทุนสินค้าที่ขาย',  # After more spacing fix
    'ต้นทุนสินคาทีขาย': 'ต้นทุนสินค้าที่ขาย',
    'ทีขาย': 'ที่ขาย',
    'สินค าทีขาย': 'สินค้าที่ขาย',
    'สินคาทีขาย': 'สินค้าที่ขาย',

    # Expenses (ค่าใช้จ่าย variations)
    'ค่าใช จ่ายในการขาย': 'ค่าใช้จ่ายในการขาย',
    'ค่าใชจ่ายในการขาย': 'ค่าใช้จ่ายในการขาย',  # After spacing fix
    'ค่าใช จ่ายในการบริหาร': 'ค่าใช้จ่ายในการบริหาร',
    'ค่าใชจ่ายในการบริหาร': 'ค่าใช้จ่ายในการบริหาร',  # After spacing fix
    'ค่าใช จ่าย': 'ค่าใช้จ่าย',
    'ค่าใชจ่าย': 'ค่าใช้จ่าย',

    # Cost of finance (ต้นทุนทางการเงิน)
    'ต้ นทุนทางการเงิน': 'ต้นทุนทางการเงิน',
    'ตนทุนทางการเงิน': 'ต้นทุนทางการเงิน',  # After spacing fix
    'ต้ นทุน': 'ต้นทุน',
    'ตนทุน': 'ต้นทุน',

    # Corporate income tax (ภาษีเงินได้นิติบุคคล)
    'ภาษีเงินได นิติบุคคล': 'ภาษีเงินได้นิติบุคคล',
    'ภาษีเงินไดนิติบุคคล': 'ภาษีเงินได้นิติบุคคล',  # After spacing fix
    'เงินได นิติบุคคล': 'เงินได้นิติบุคคล',
    'เงินไดนิติบุคคล': 'เงินได้นิติบุคคล',

    # Profit/Loss before tax phrases
    'กําไร ( ขาดทุน )': 'กำไร (ขาดทุน)',
    'กําไร (ขาดทุน)': 'กำไร (ขาดทุน)',
    'กําไรขาดทุน': 'กำไรขาดทุน',
    'งบกําไรขาดทุน': 'งบกำไรขาดทุน',

    # Net profit/loss (สุทธิ)
    'กําไร ( ขาดทุน ) สุทธิ': 'กำไร (ขาดทุน) สุทธิ',
    'กําไรสุทธิ': 'กำไรสุทธิ',
    'ขาดทุนสุทธิ': 'ขาดทุนสุทธิ',

    # Auditor terms
    'ผู้ตรวจสอบบัญชี': 'ผู้ตรวจสอบบัญชี',
    'ผู ้ตรวจสอบบัญชี': 'ผู้ตรวจสอบบัญชี',

    # Statement detail (งบละเอียด)
    'งบละเอียด': 'งบละเอียด',
    '( งบละเอียด )': '(งบละเอียด)',
    'งบบริษัท': 'งบบริษัท',
}


def fix_spacing_issues(text: str) -> str:
    """
    Fix character spacing issues where vowels/tone marks are separated from base consonants.

    Examples:
        "อ ้อม" → "อ้อม"
        "เงิ นสด" → "เงินสด"
        "สินค า" → "สินค้า" (trailing vowel)

    Args:
        text: Text with potential spacing issues

    Returns:
        Text with fixed spacing
    """
    if not text:
        return text

    # Pattern 1: space followed by combining mark OR trailing vowel (า, ำ)
    # e.g., "อ ้อม" → "อ้อม", "สินค า" → "สินคา"
    pattern = r'(\S)\s+([' + THAI_ALL_ATTACHABLE + r'])'

    # Keep replacing until no more matches (handles multiple marks)
    prev_text = None
    while prev_text != text:
        prev_text = text
        text = re.sub(pattern, r'\1\2', text)

    # Pattern 2: combining mark followed by space then consonant
    # e.g., "ก ็ น" should become "ก็น"
    pattern2 = r'([' + THAI_COMBINING_MARKS + r'])\s+(\S)'
    text = re.sub(pattern2, r'\1\2', text)

    return text


def remove_duplicate_marks(text: str) -> str:
    """
    Remove duplicate Thai combining marks (vowels/tone marks).

    This fixes issues like "เจ้าหนี้้" → "เจ้าหนี้"

    Args:
        text: Text with potential duplicate marks

    Returns:
        Text with duplicate marks removed
    """
    if not text:
        return text

    # Remove duplicate combining marks (same mark repeated)
    for mark in THAI_COMBINING_MARKS:
        text = re.sub(mark + '+', mark, text)

    return text


def apply_common_corrections(text: str) -> Tuple[str, int]:
    """
    Apply dictionary of common OCR corrections.

    Applies longer patterns first to avoid partial matches
    breaking longer matches (e.g., 'เจ้าหนี' should not prevent
    'เจ้าหนีการคา' from being corrected properly).

    Args:
        text: Text to correct

    Returns:
        Tuple of (corrected text, number of corrections made)
    """
    corrections = 0

    # Sort by length descending so longer patterns are applied first
    sorted_corrections = sorted(
        COMMON_OCR_CORRECTIONS.items(),
        key=lambda x: len(x[0]),
        reverse=True
    )

    for wrong, correct in sorted_corrections:
        if wrong in text:
            count = text.count(wrong)
            text = text.replace(wrong, correct)
            corrections += count

    return text, corrections


def convert_parentheses_to_negative(text: str) -> Tuple[str, int]:
    """
    Convert numbers in parentheses to negative values (accounting format).

    Examples:
        "(1,234,567.89)" → "-1,234,567.89"
        "(123)" → "-123"
        "(1,234)" → "-1,234"

    Args:
        text: Text containing numbers in parentheses

    Returns:
        Tuple of (converted text, number of conversions)
    """
    if not text:
        return text, 0

    # Pattern for numbers in parentheses (with optional comma separators and decimals)
    pattern = r'\(\s*([0-9,]+\.?[0-9]*)\s*\)'

    # Count matches before replacing
    matches = re.findall(pattern, text)
    count = len(matches)

    # Replace parentheses with negative sign
    text = re.sub(pattern, r'-\1', text)

    return text, count


def normalize_thai_text(text: str) -> str:
    """
    Normalize Thai text using PyThaiNLP if available.

    This handles:
    - NIKHAHIT/SARA AM normalization
    - Duplicate characters
    - Thai character level normalization

    Args:
        text: Thai text to normalize

    Returns:
        Normalized text
    """
    if not text:
        return text

    if PYTHAINLP_AVAILABLE:
        try:
            return pythainlp_normalize(text)
        except Exception:
            pass

    # Basic normalization without PyThaiNLP
    # Fix common character issues
    text = text.replace('\u0e33', '\u0e4d\u0e32')  # Normalize SARA AM
    return text


def correct_thai_spelling(text: str, use_pythainlp: bool = True) -> Tuple[str, int]:
    """
    Correct Thai spelling using PyThaiNLP spell checker.

    Note: This is more aggressive and may change correct words.
    Use with caution on financial documents where precision is important.

    Args:
        text: Thai text to correct
        use_pythainlp: Whether to use PyThaiNLP (if available)

    Returns:
        Tuple of (corrected text, estimated corrections)
    """
    if not text or not use_pythainlp or not PYTHAINLP_AVAILABLE:
        return text, 0

    try:
        # Tokenize the text
        words = word_tokenize(text, engine='newmm')

        corrections = 0
        corrected_words = []

        for word in words:
            # Skip non-Thai words, numbers, punctuation
            if not re.search(r'[\u0e00-\u0e7f]', word):
                corrected_words.append(word)
                continue

            # Skip very short words (often particles, won't correct well)
            if len(word) <= 1:
                corrected_words.append(word)
                continue

            # Try to correct
            try:
                corrected = pythainlp_correct(word)
                if corrected and corrected != word:
                    corrected_words.append(corrected)
                    corrections += 1
                else:
                    corrected_words.append(word)
            except Exception:
                corrected_words.append(word)

        return ''.join(corrected_words), corrections

    except Exception:
        return text, 0


def postprocess_thai_ocr(
    text: str,
    fix_spacing: bool = True,
    apply_corrections: bool = True,
    convert_negatives: bool = True,
    normalize: bool = True,
    spell_check: bool = True  # Enabled by default when PyThaiNLP is available
) -> PostProcessResult:
    """
    Main function to post-process Thai OCR output.

    Args:
        text: Raw OCR text
        fix_spacing: Fix character spacing issues
        apply_corrections: Apply common OCR corrections dictionary
        convert_negatives: Convert (xxx) to -xxx
        normalize: Normalize Thai text
        spell_check: Use PyThaiNLP spell checker (more aggressive)

    Returns:
        PostProcessResult with original, corrected text, and stats
    """
    if not text:
        return PostProcessResult(
            original=text or '',
            corrected='',
            corrections_made=0,
            negative_numbers_converted=0
        )

    original = text
    total_corrections = 0
    negative_conversions = 0

    # Step 1: Fix spacing issues first
    if fix_spacing:
        text = fix_spacing_issues(text)

    # Step 2: Normalize Thai text
    if normalize:
        text = normalize_thai_text(text)

    # Step 3: PyThaiNLP spell check (runs early so our dictionary can override)
    if spell_check and PYTHAINLP_AVAILABLE:
        text, corrections = correct_thai_spelling(text)
        total_corrections += corrections

    # Step 4: Apply common corrections dictionary (runs AFTER PyThaiNLP to override any mistakes)
    if apply_corrections:
        text, corrections = apply_common_corrections(text)
        total_corrections += corrections

    # Step 5: Convert parentheses to negative numbers
    if convert_negatives:
        text, negative_conversions = convert_parentheses_to_negative(text)

    # Step 6: Final cleanup - remove duplicate tone marks
    text = remove_duplicate_marks(text)

    return PostProcessResult(
        original=original,
        corrected=text,
        corrections_made=total_corrections,
        negative_numbers_converted=negative_conversions
    )


def postprocess_markdown(markdown: str) -> str:
    """
    Post-process markdown output from OCR.

    Applies all corrections while preserving markdown structure.
    Uses PyThaiNLP spell checking when available.

    Args:
        markdown: Markdown text from OCR

    Returns:
        Corrected markdown
    """
    result = postprocess_thai_ocr(
        markdown,
        fix_spacing=True,
        apply_corrections=True,
        convert_negatives=True,
        normalize=True,
        spell_check=True  # Use PyThaiNLP when available
    )
    return result.corrected


def add_correction(wrong: str, correct: str) -> None:
    """
    Add a new correction to the common corrections dictionary.

    This allows users to add domain-specific corrections at runtime.

    Args:
        wrong: Incorrect text pattern
        correct: Correct replacement
    """
    COMMON_OCR_CORRECTIONS[wrong] = correct


def get_pythainlp_status() -> dict:
    """
    Get status of PyThaiNLP integration.

    Returns:
        Dict with availability status and version info
    """
    status = {
        'available': PYTHAINLP_AVAILABLE,
        'version': None,
        'spell_check_enabled': PYTHAINLP_AVAILABLE,
    }

    if PYTHAINLP_AVAILABLE:
        try:
            import pythainlp
            status['version'] = pythainlp.__version__
        except Exception:
            pass

    return status
