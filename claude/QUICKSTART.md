# Quick Start Guide - Thai OCR Streamlit App

## Prerequisites
```bash
pip install streamlit pandas
```

## Launch Application
```bash
cd /Users/nut/ocr-prototype/claude
streamlit run app/main.py
```

## First Time Setup
1. Application will open in browser at `http://localhost:8501`
2. You'll see the dashboard with 11 Thai companies
3. Current status shows 0 processed documents (all mock data)

## User Flow

### Flow 1: Browse and Process
1. **Dashboard** → Click "📁 Browse Documents"
2. **Browse Page**:
   - Use filters (Company/Year/Type)
   - Select documents with checkboxes
   - Click "Process Selected →"
3. **Process Page**:
   - Click "▶️ Start Processing"
   - Watch real-time progress
   - View logs in expander
4. **Results Page** (auto-navigate or click "View Results →"):
   - Select document from dropdown
   - View in 4 tabs (Tables/Text/Markdown/JSON)
   - Export using download buttons

### Flow 2: Upload New Files
1. **Dashboard** → Click "⬆️ Upload"
2. **Upload Page**:
   - Drag-drop PDF files or click to browse
   - Select company, year, type
   - Check "Process after upload" (optional)
   - Click "🚀 Upload Files"
3. Auto-navigate to Process page if option checked

## Testing the Interface

### Test Browse Filters
```
1. Go to Browse page
2. Select company: "10002819 - บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด"
3. Select year: "2023"
4. Select type: "งบการเงิน"
5. See filtered results
6. Click "Clear Filters" to reset
```

### Test Processing
```
1. Browse page → Select 3-5 documents
2. Click "Process Selected"
3. Click "▶️ Start Processing"
4. Watch progress bar (simulates ~2 seconds per doc)
5. Check logs for processing steps
6. View statistics when complete
```

### Test Results Viewer
```
1. After processing, go to Results page
2. Select a document from dropdown
3. Check each tab:
   - Tables: View DataFrames, export CSV
   - Text: View extracted text, export TXT
   - Markdown: View formatted output, export MD
   - JSON: View structured data, export JSON
4. Try "Export All Tables" batch option
```

### Test File Upload
```
1. Go to Upload page
2. Click file uploader (any PDF will work for demo)
3. Select organization metadata
4. Click "🚀 Upload Files"
5. Watch progress bar
6. Check recent uploads section
```

## Current Limitations (Mock Data)
- All data is simulated/mock
- No actual OCR processing
- No real file system operations
- No database persistence
- Processing just sleeps to simulate work

## Mock Data Details
- **11 Companies**: Thai financial companies with codes 10002819-10002849
- **4 Years**: 2020-2024 fiscal years
- **3 Doc Types**: งบการเงิน, รายงานประจำปี, รายงานคณะกรรมการ
- **Total Docs**: 132 mock documents

## Session State (Persistent During Session)
- Selected files persist when navigating between pages
- Processed documents accumulate during session
- Upload history maintained
- Processing logs stored

## Keyboard Shortcuts
- `R` - Rerun/refresh current page
- `C` - Clear cache
- Navigation via sidebar menu

## Troubleshooting

### Port Already in Use
```bash
streamlit run app/main.py --server.port 8502
```

### Thai Characters Not Displaying
- Ensure terminal/browser supports UTF-8
- Check system fonts include Thai support
- Try different browser (Chrome recommended)

### File Upload Not Working
- Check file is actually PDF
- Verify file size < 50MB
- Clear browser cache and retry

## File Locations
```
app/main.py                    # Dashboard
app/pages/1_📁_Browse.py       # Document browser
app/pages/2_⚙️_Process.py      # Processing view
app/pages/3_📊_Results.py      # Results viewer
app/pages/4_⬆️_Upload.py       # File upload
.streamlit/config.toml         # Configuration
```

## Configuration Changes

### Change Theme Color
Edit `.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#FF5722"  # Orange instead of blue
```

### Increase Upload Limit
Edit `.streamlit/config.toml`:
```toml
[server]
maxUploadSize = 500  # Increase to 500MB
```

### Change Default Port
```bash
streamlit run app/main.py --server.port 8080
```

## Development Mode
```bash
# Auto-reload on file changes (default in Streamlit)
streamlit run app/main.py

# Access from other devices on network
streamlit run app/main.py --server.address 0.0.0.0
```

## Next Integration Steps
1. Replace mock_get_company_summary() with DatabaseManager
2. Replace process_document() with DocumentProcessor
3. Connect upload to actual file system
4. Wire up results to database queries

## Support
- Streamlit docs: https://docs.streamlit.io
- Thai encoding issues: Use UTF-8-sig for Excel compatibility
- Session state guide: https://docs.streamlit.io/library/api-reference/session-state
