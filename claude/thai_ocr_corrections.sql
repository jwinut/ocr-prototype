
INSERT INTO thai_ocr_corrections
(error_pattern, correction, confidence, frequency, type, description, example, priority, created_at, updated_at)
VALUES (
    'บบ',
    'บ',
    0.95,
    634,
    'character_duplication',
    'Fix duplicated บ character',
    'บริบบษัท → บริษัท',
    'critical',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO thai_ocr_corrections
(error_pattern, correction, confidence, frequency, type, description, example, priority, created_at, updated_at)
VALUES (
    'งบบริษัท',
    'งบบริษัท',
    0.8,
    170,
    'word_segmentation',
    'Financial statement term',
    'งบบริษัท',
    'high',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO thai_ocr_corrections
(error_pattern, correction, confidence, frequency, type, description, example, priority, created_at, updated_at)
VALUES (
    'บจก',
    'บจก.',
    0.85,
    165,
    'abbreviation_punctuation',
    'Add period to company abbreviation',
    'บจก. (บริษัทจำกัด)',
    'high',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO thai_ocr_corrections
(error_pattern, correction, confidence, frequency, type, description, example, priority, created_at, updated_at)
VALUES (
    'กําไร',
    'กำไร',
    0.9,
    149,
    'character_correction',
    'Fix corrupted ำ character',
    'กำไร',
    'high',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO thai_ocr_corrections
(error_pattern, correction, confidence, frequency, type, description, example, priority, created_at, updated_at)
VALUES (
    'สส',
    'ส',
    0.9,
    75,
    'character_duplication',
    'Fix duplicated ส character',
    'สสมบัติ → สมบัติ',
    'high',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO thai_ocr_corrections
(error_pattern, correction, confidence, frequency, type, description, example, priority, created_at, updated_at)
VALUES (
    'จํากั',
    'จำกัด',
    0.9,
    58,
    'character_correction',
    'Fix corrupted ำ character',
    'จำกัด',
    'high',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO thai_ocr_corrections
(error_pattern, correction, confidence, frequency, type, description, example, priority, created_at, updated_at)
VALUES (
    'คํานวณ',
    'คำนวณ',
    0.9,
    0,
    'character_correction',
    'Fix corrupted ำ character',
    'คำนวณ',
    'high',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO thai_ocr_corrections
(error_pattern, correction, confidence, frequency, type, description, example, priority, created_at, updated_at)
VALUES (
    'บ',
    'ป',
    0.7,
    5291,
    'character_confusion',
    'บ/ป character confusion',
    'บริการ → ประการ (when context fits)',
    'medium',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO thai_ocr_corrections
(error_pattern, correction, confidence, frequency, type, description, example, priority, created_at, updated_at)
VALUES (
    'ถ',
    'ด',
    0.75,
    916,
    'character_confusion',
    'ด/ถ character confusion',
    'มูลค่าถ → มูลค่าด',
    'medium',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO thai_ocr_corrections
(error_pattern, correction, confidence, frequency, type, description, example, priority, created_at, updated_at)
VALUES (
    'ปป',
    'ป',
    0.9,
    2,
    'character_duplication',
    'Fix duplicated ป character',
    'ปประเทศ → ประเทศ',
    'medium',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

INSERT INTO thai_ocr_corrections
(error_pattern, correction, confidence, frequency, type, description, example, priority, created_at, updated_at)
VALUES (
    'ว',
    'ถ',
    0.65,
    4793,
    'character_confusion',
    'ว/ถ character confusion',
    'ดำเนินวาน → ดำเนินการ',
    'low',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);