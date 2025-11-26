import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions, TableFormerMode
    from docling.datamodel.base_models import InputFormat
except ImportError:
    print("Docling not installed")
    sys.exit(1)

def test_docling(file_path):
    print(f"Testing Docling on: {file_path}")
    
    # Configure options similar to app
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
        table_structure_options={"mode": TableFormerMode.ACCURATE}
    )
    
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    
    try:
        result = converter.convert(file_path)
        doc = result.document
        
        text = doc.export_to_text()
        md = doc.export_to_markdown()
        
        print(f"Text Length: {len(text)}")
        print(f"Markdown Length: {len(md)}")
        
        if len(text) > 0:
            print(f"Text Preview: {text[:100]}...")
        else:
            print("Text is EMPTY")
            
        if len(md) > 0:
            print(f"Markdown Preview: {md[:100]}...")
        else:
            print("Markdown is EMPTY")
            
        print(f"Tables: {len(doc.tables)}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Use the file path found in previous step
    file_path = "/Users/nut/ocr-prototype/Y67/10000588 บริษัท สโตเรจซิสเต็ม อินดัสตรี จำกัด/Y67/บริษัท สโตเรจซิสเต็ม อินดัสตรี จำกัด_BS67.pdf"
    test_docling(file_path)
