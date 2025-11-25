# Thai Financial Document OCR - GUI Application

## Overview

Complete Streamlit web application for processing Thai financial PDFs with OCR capabilities. Built by DEV-3 (GAMMA) as part of the distributed development team.

## Features

### 1. Dashboard (`app/main.py`)
- System overview with statistics
- Quick action buttons
- Company list with document counts
- Recent activity feed
- Real-time metrics: Total Companies, Total Documents, Processed count, Progress %

### 2. Browse Documents (`pages/1_📁_Browse.py`)
- Advanced filtering:
  - Filter by company (dropdown)
  - Filter by fiscal year (dropdown)
  - Filter by document type (multiselect)
- File selection with checkboxes
- Bulk selection (Select All)
- Document details view (expandable)
- Selected files tracking
- Direct navigation to processing

### 3. Process Documents (`pages/2_⚙️_Process.py`)
- Selected files summary with metrics
- Real-time processing with progress bar
- Live status updates for current file
- Detailed processing logs with timestamps
- Cancel functionality
- Processing statistics after completion
- Success/failure tracking

### 4. View Results (`pages/3_📊_Results.py`)
- Document selector for processed files
- Multiple view formats:
  - **Tables Tab**: Interactive DataFrames with export
  - **Text Tab**: Full extracted text content
  - **Markdown Tab**: Formatted preview with raw view
  - **JSON Tab**: Complete structured data
- Individual and batch export options
- Export formats: CSV, TXT, MD, JSON

### 5. Upload Documents (`pages/4_⬆️_Upload.py`)
- Multi-file PDF upload
- File validation:
  - PDF format check
  - Size limit (50MB per file)
- File preview and organization
- Target folder selection (company, year, type)
- Upload progress tracking
- "Process After Upload" option
- Upload history

## Project Structure

```
claude/
├── .streamlit/
│   └── config.toml          # Streamlit configuration
├── app/
│   ├── __init__.py          # Package initialization
│   ├── main.py              # Dashboard entry point
│   └── pages/
│       ├── 1_📁_Browse.py   # File browser
│       ├── 2_⚙️_Process.py  # Processing view
│       ├── 3_📊_Results.py  # Results viewer
│       └── 4_⬆️_Upload.py   # Upload interface
└── GUI_README.md            # This file
```

## Installation & Setup

### Prerequisites
```bash
pip install streamlit pandas
```

### Running the Application

From the `/Users/nut/ocr-prototype/claude` directory:

```bash
streamlit run app/main.py
```

The application will open in your browser at `http://localhost:8501`

## Session State Management

The application uses Streamlit session state for:
- `selected_files`: List of document IDs selected for processing
- `processing_status`: Current processing state (None, "running", "completed", "cancelled")
- `processed_documents`: List of successfully processed documents
- `processing_logs`: Processing log entries
- `current_file_idx`: Index of currently processing file
- `uploaded_files`: History of uploaded files
- `filter_*`: Current filter values in browse page

## Thai Language Support

All pages properly handle Thai text (UTF-8 encoding):
- Company names in Thai
- Document types in Thai
- Text extraction with Thai characters
- CSV exports with UTF-8-BOM for Excel compatibility

## Mock Data Structure

Currently uses mock data that will be replaced with actual database integration:

```python
MOCK_COMPANIES = [
    {
        "code": "10002819",
        "name": "บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด",
        "count": 40
    },
    # ... 10 more companies
]

MOCK_DOCUMENTS = [
    {
        "id": "10002819_2023_งบการเงิน",
        "filename": "10002819_2023_งบการเงิน.pdf",
        "company_code": "10002819",
        "company_name": "บริษัท โฮชุง อินดัสเตรียล (ประเทศไทย) จำกัด",
        "year": 2023,
        "type": "งบการเงิน",
        "size": "2.5 MB",
        "status": "pending",
        "path": "/Y67/10002819/2023/งบการเงิน.pdf"
    },
    # ... many more documents
]
```

## Integration Points (Ready for Other Devs)

The GUI is designed with placeholder imports for integration:

```python
# These will be implemented by other devs
# from app.database import DatabaseManager  # DEV-1
# from processing.scanner import scan_directory  # DEV-2
# from processing.ocr import DocumentProcessor  # DEV-4
```

When other components are ready:
1. Remove mock data generators
2. Uncomment integration imports
3. Replace mock function calls with actual API calls
4. Update session state management as needed

## UI/UX Features

### Design System
- Primary color: #1E88E5 (Blue)
- Clean, professional layout
- Responsive columns
- Thai-friendly fonts
- Wide layout for data tables

### User Experience
- Clear navigation between pages
- Loading states with spinners
- Success/error messages with appropriate styling
- Progress indicators for long operations
- Expandable sections for details
- Tooltips for guidance

### Accessibility
- Proper button labels
- Clear visual hierarchy
- Status indicators with icons
- Descriptive error messages
- Keyboard navigation support

## Key Components

### File Selection
```python
# In Browse page
if st.checkbox("", value=is_selected, key=f"check_{doc['id']}"):
    if doc['id'] not in st.session_state.selected_files:
        st.session_state.selected_files.append(doc['id'])
```

### Progress Tracking
```python
# In Process page
progress = st.session_state.current_file_idx / len(st.session_state.selected_files)
st.progress(progress)
```

### Results Display
```python
# In Results page
tab1, tab2, tab3, tab4 = st.tabs(["📊 Tables", "📝 Text", "📋 Markdown", "🔧 JSON"])
with tab1:
    st.dataframe(table['data'], use_container_width=True)
```

### File Upload
```python
# In Upload page
uploaded_files = st.file_uploader(
    "Choose PDF files to upload",
    type=['pdf'],
    accept_multiple_files=True
)
```

## Error Handling

All pages include:
- Input validation
- File type checking
- Size limit enforcement
- Graceful error messages
- Empty state handling
- Session state initialization

## Performance Considerations

- Display limits for large lists (50 documents at once)
- Pagination indicators when needed
- Progress bars for long operations
- Efficient session state updates
- Lazy loading of results

## Testing Workflow

To test the complete workflow:

1. **Start**: Launch app, view dashboard
2. **Browse**: Go to Browse page, apply filters, select documents
3. **Process**: Navigate to Process page, start processing
4. **Results**: View processed results in multiple formats
5. **Upload**: Upload new documents, optionally process immediately

## Future Enhancements

When integrating with actual backend:
- Real-time progress updates via WebSocket
- Database-backed document listing
- Actual OCR processing integration
- User authentication
- Batch export as ZIP files
- Search functionality
- Advanced filtering options
- Document comparison
- Historical processing data
- Performance analytics dashboard

## Configuration

### Streamlit Config (`.streamlit/config.toml`)
- Theme colors and fonts
- Server settings (max upload 200MB)
- CORS and XSRF protection
- Usage statistics disabled for privacy

### Environment Variables (Future)
When backend is integrated:
```bash
DATABASE_URL=sqlite:///documents.db
UPLOAD_FOLDER=/Y67
MAX_UPLOAD_SIZE=50MB
PROCESSING_WORKERS=4
```

## Troubleshooting

### Common Issues

1. **Thai text not displaying**: Ensure UTF-8 encoding is set
2. **Upload fails**: Check file size and format
3. **Processing hangs**: Check mock data generation in process page
4. **Session state lost**: Streamlit reruns reset state, use session_state properly

### Debug Mode

To see session state:
```python
# Add to any page for debugging
st.sidebar.write("Session State:", st.session_state)
```

## Development Notes

- All pages are standalone and can run independently
- Session state is the communication layer between pages
- Mock data simulates realistic Thai financial documents
- Processing is simulated with sleep() calls
- Ready for backend integration with minimal changes

## Contact

Built by DEV-3 (GAMMA) - GUI/Frontend Specialist
Part of the Thai Financial Document OCR Prototype team
