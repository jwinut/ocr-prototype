"""
Custom Dictionary Management Page

This page allows users to:
1. Review Thai phrases extracted from OCR results
2. Identify incorrect phrases and suggest corrections
3. Add new corrections to the custom dictionary
4. Manage the Thai OCR correction workflow
"""

import streamlit as st
import pandas as pd
import sqlite3
import re
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config
from utils.thai_utils import is_thai_text, clean_thai_text

# Page configuration
st.set_page_config(
    page_title="Dictionary Management",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database connection
def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(config.DATABASE_PATH)

# Cache Thai phrases data
@st.cache_data(ttl=300)
def load_thai_phrases(status_filter=None, needs_review_only=False, search_term=None):
    """Load Thai phrases from database with optional filters"""
    conn = get_db_connection()

    query = '''
        SELECT tp.id, tp.phrase, tp.word_count, tp.confidence_score,
               tp.status, tp.needs_correction, tp.correction_suggestion,
               tp.created_at, tp.context, d.file_name, c.name_th as company_name
        FROM thai_phrases tp
        LEFT JOIN documents d ON tp.document_id = d.id
        LEFT JOIN fiscal_years fy ON d.fiscal_year_id = fy.id
        LEFT JOIN companies c ON fy.company_id = c.id
        WHERE 1=1
    '''

    params = []

    if status_filter and status_filter != "all":
        query += " AND tp.status = ?"
        params.append(status_filter)

    if needs_review_only:
        query += " AND tp.needs_correction = TRUE"

    if search_term:
        query += " AND (tp.phrase LIKE ? OR tp.context LIKE ?)"
        params.extend([f"%{search_term}%", f"%{search_term}%"])

    query += " ORDER BY tp.created_at DESC"

    try:
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Error loading Thai phrases: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# Cache aggregated Thai phrases data
@st.cache_data(ttl=600)
def load_aggregated_thai_phrases(needs_review_only=False, search_term=None, min_group_size=1):
    """Load aggregated Thai phrases with deduplication across documents"""
    conn = get_db_connection()

    try:
        # Get all phrases with their document information
        query = '''
            SELECT
                tp.id,
                tp.phrase,
                tp.word_count,
                tp.confidence_score,
                tp.status,
                tp.needs_correction,
                tp.correction_suggestion,
                tp.context,
                tp.created_at,
                tp.updated_at,
                d.id as document_id,
                d.file_name,
                c.name_th as company_name,
                c.name_en as company_name_en
            FROM thai_phrases tp
            LEFT JOIN documents d ON tp.document_id = d.id
            LEFT JOIN fiscal_years fy ON d.fiscal_year_id = fy.id
            LEFT JOIN companies c ON fy.company_id = c.id
            ORDER BY tp.phrase, tp.confidence_score
        '''

        df = pd.read_sql_query(query, conn)

        if df.empty:
            return pd.DataFrame()

        # Get dictionary corrections for reference
        corrections_query = '''
            SELECT error_pattern, correction, type
            FROM thai_ocr_corrections
            WHERE is_active = 1
        '''
        corrections_df = pd.read_sql_query(corrections_query, conn)
        correction_map = dict(zip(corrections_df['error_pattern'],
                                  zip(corrections_df['correction'], corrections_df['type'])))

        # Group phrases by their text content
        aggregated_data = []

        for phrase_text, group in df.groupby('phrase'):
            # Apply filters
            if search_term and search_term.lower() not in phrase_text.lower():
                continue

            if needs_review_only and not group['needs_correction'].any():
                continue

            # Count unique documents
            group_size = len(group)
            if group_size < min_group_size:
                continue

            # Find the best representative phrase from the group
            # Handle NaN values in confidence_score properly
            valid_confidence = group['confidence_score'].dropna()
            if not valid_confidence.empty:
                # Use the row with highest confidence score
                best_idx = valid_confidence.idxmax()
                best_row = group.loc[best_idx]
            else:
                # All confidence scores are NaN, use the first row
                best_row = group.iloc[0]

            # Collect all document sources and companies
            source_documents = '; '.join(sorted(group['file_name'].dropna().unique()))
            companies = set()
            for company in group['company_name'].dropna():
                companies.add(company)
            for company in group['company_name_en'].dropna():
                companies.add(company)
            unique_companies = '; '.join(sorted(companies))

            # Determine if any instance needs correction
            any_needs_correction = group['needs_correction'].any()
            any_has_suggestion = group['correction_suggestion'].notna().any()

            # Try to find dictionary correction
            dict_correction = correction_map.get(phrase_text)

            # Determine final correction and source
            if dict_correction:
                final_correction = dict_correction[0]
                correction_source = f"dictionary_{dict_correction[1]}"
            elif any_has_suggestion:
                final_correction = best_row['correction_suggestion']
                correction_source = 'phrase_suggestion'
            elif any_needs_correction:
                final_correction = None
                correction_source = 'needs_manual_review'
            else:
                final_correction = None
                correction_source = 'no_correction_needed'

            # Create aggregated entry
            aggregated_entry = {
                'phrase_text': phrase_text,
                'group_size': group_size,
                'confidence_score': best_row['confidence_score'],
                'word_count': best_row['word_count'],
                'status': best_row['status'],
                'needs_correction': any_needs_correction,
                'correction_suggestion': best_row['correction_suggestion'],
                'final_correction': final_correction,
                'correction_source': correction_source,
                'source_documents': source_documents,
                'unique_companies': unique_companies,
                'total_instances': group_size,
                'best_phrase_id': best_row['id'],
                'best_file_name': best_row['file_name'],
                'context': best_row['context'],
                'created_at': best_row['created_at'],
                'updated_at': best_row['updated_at']
            }

            # Add priority classification
            if any_needs_correction:
                if group_size >= 3:
                    priority = 'HIGH_MULTI_FILE'
                elif pd.notna(best_row['confidence_score']) and best_row['confidence_score'] < 0.5:
                    priority = 'HIGH_LOW_CONFIDENCE'
                elif group_size >= 2:
                    priority = 'MEDIUM_MULTI_FILE'
                else:
                    priority = 'STANDARD'
            else:
                priority = None

            aggregated_entry['priority'] = priority
            aggregated_data.append(aggregated_entry)

        # Convert to DataFrame
        aggregated_df = pd.DataFrame(aggregated_data)

        # Sort by priority and group size
        if not aggregated_df.empty and aggregated_df['priority'].notna().any():
            priority_order = {'HIGH_MULTI_FILE': 1, 'HIGH_LOW_CONFIDENCE': 2, 'MEDIUM_MULTI_FILE': 3, 'STANDARD': 4}
            aggregated_df['priority_rank'] = aggregated_df['priority'].map(lambda x: priority_order.get(x, 5) if pd.notna(x) else 5)
            # Handle NaN values in confidence_score for sorting
            aggregated_df['confidence_score_filled'] = aggregated_df['confidence_score'].fillna(0.0)
            aggregated_df = aggregated_df.sort_values(['priority_rank', 'group_size', 'confidence_score_filled'],
                                                   ascending=[True, False, True])
            aggregated_df = aggregated_df.drop(['priority_rank', 'confidence_score_filled'], axis=1)
        else:
            # Handle NaN values in confidence_score for sorting
            aggregated_df['confidence_score_filled'] = aggregated_df['confidence_score'].fillna(0.0)
            aggregated_df = aggregated_df.sort_values(['group_size', 'confidence_score_filled'], ascending=[False, True])
            aggregated_df = aggregated_df.drop('confidence_score_filled', axis=1)

        return aggregated_df

    except Exception as e:
        st.error(f"Error loading aggregated phrases: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# Cache existing corrections
@st.cache_data(ttl=600)
def load_existing_corrections():
    """Load existing Thai OCR corrections"""
    conn = get_db_connection()

    try:
        df = pd.read_sql_query('''
            SELECT error_pattern, correction, frequency, type, priority, confidence
            FROM thai_ocr_corrections
            WHERE is_active = 1
            ORDER BY priority, frequency DESC
        ''', conn)
        return df
    except Exception as e:
        st.error(f"Error loading corrections: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def update_phrase_status(phrase_id, status, needs_correction=False, correction_suggestion="", notes=""):
    """Update phrase status and correction info"""
    conn = get_db_connection()

    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE thai_phrases
            SET status = ?, needs_correction = ?, correction_suggestion = ?,
                notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, needs_correction, correction_suggestion, notes, phrase_id))

        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        st.error(f"Error updating phrase: {e}")
        return False
    finally:
        conn.close()

def add_correction_to_dictionary(error_pattern, correction, correction_type, confidence=0.9):
    """Add a new correction to the Thai OCR corrections dictionary"""
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        # Check if correction already exists
        cursor.execute('''
            SELECT id FROM thai_ocr_corrections
            WHERE error_pattern = ? AND correction = ? AND is_active = 1
        ''', (error_pattern, correction))

        if cursor.fetchone():
            st.warning("This correction already exists in the dictionary")
            return False

        # Add new correction
        cursor.execute('''
            INSERT INTO thai_ocr_corrections
            (error_pattern, correction, confidence, frequency, type, description,
             example, priority, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 0, ?, ?, ?, 'high', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (
            error_pattern,
            correction,
            confidence,
            correction_type,
            f"Manual correction for {correction_type}",
            f"{error_pattern} → {correction}",
            correction_type
        ))

        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error adding correction: {e}")
        return False
    finally:
        conn.close()

def get_phrase_statistics():
    """Get statistics about Thai phrases"""
    conn = get_db_connection()

    try:
        stats = {}

        # Total phrases
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM thai_phrases")
        stats['total'] = cursor.fetchone()[0]

        # By status
        cursor.execute("SELECT status, COUNT(*) FROM thai_phrases GROUP BY status")
        stats['by_status'] = dict(cursor.fetchall())

        # Needs correction
        cursor.execute("SELECT COUNT(*) FROM thai_phrases WHERE needs_correction = TRUE")
        stats['needs_correction'] = cursor.fetchone()[0]

        # Average confidence
        cursor.execute("SELECT AVG(confidence_score) FROM thai_phrases WHERE confidence_score IS NOT NULL")
        avg_conf = cursor.fetchone()[0]
        stats['avg_confidence'] = round(avg_conf, 3) if avg_conf else 0

        # Aggregated statistics
        cursor.execute('''
            SELECT COUNT(DISTINCT phrase) as unique_phrases,
                   COUNT(*) as total_instances
            FROM thai_phrases
        ''')
        agg_result = cursor.fetchone()
        stats['unique_phrases'] = agg_result[0] if agg_result else 0
        stats['total_instances'] = agg_result[1] if agg_result else 0

        # Reduction percentage
        if stats['total_instances'] > 0:
            stats['reduction_percentage'] = ((stats['total_instances'] - stats['unique_phrases']) / stats['total_instances']) * 100
        else:
            stats['reduction_percentage'] = 0

        return stats
    except Exception as e:
        st.error(f"Error getting statistics: {e}")
        return {}
    finally:
        conn.close()

def apply_correction_to_group(phrase_text, correction, correction_type="manual"):
    """Apply a correction to all instances of a phrase group"""
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        # Update all instances of this phrase
        cursor.execute('''
            UPDATE thai_phrases
            SET needs_correction = TRUE,
                correction_suggestion = ?,
                status = 'reviewed',
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE phrase = ?
        ''', (correction, f"Group correction applied: {correction_type}", phrase_text))

        conn.commit()
        return cursor.rowcount > 0

    except Exception as e:
        st.error(f"Error applying group correction: {e}")
        return False
    finally:
        conn.close()

def main():
    """Main dictionary management page"""

    st.title("📖 Custom Dictionary Management")
    st.markdown("Review and manage Thai phrases extracted from OCR results")

    # Sidebar for filters and actions
    with st.sidebar:
        st.header("🔍 Filters & Options")

        # Search
        search_term = st.text_input("Search phrases:", placeholder="Enter Thai text...")

        # Status filter
        status_filter = st.selectbox(
            "Status Filter:",
            options=["all", "pending", "reviewed", "corrected"],
            format_func=lambda x: x.title()
        )

        # Needs review only
        needs_review_only = st.checkbox("Show only phrases needing correction", value=False)

        # Refresh button
        if st.button("🔄 Refresh Data"):
            # Clear cache
            load_thai_phrases.clear()
            load_aggregated_thai_phrases.clear()
            load_existing_corrections.clear()
            st.rerun()

        st.markdown("---")

        # Statistics
        st.header("📊 Statistics")
        stats = get_phrase_statistics()

        if stats:
            st.metric("Total Phrases", stats['total'])
            st.metric("Unique Phrases", stats['unique_phrases'])
            st.metric("Need Review", stats['needs_correction'])
            st.metric("Avg Confidence", f"{stats['avg_confidence']:.3f}")
            st.metric("Reduction", f"{stats['reduction_percentage']:.1f}%")

    # Main content area
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔗 Aggregated Review", "📝 Individual Phrases", "➕ Add Correction", "📚 Dictionary", "📈 Analytics"])

    with tab1:
        st.header("🔗 Aggregated Phrase Review")
        st.markdown("""
        **This view shows DEDUPLICATED phrases** - identical phrases across all documents are grouped together.

        For example, if the phrase "เจ ้าหนีการค า" appears in 73 different places, it shows as ONE group with size 73.
        Use this view to efficiently review and correct phrases that appear multiple times.
        """)

        # Aggregation filters
        col1, col2, col3 = st.columns(3)

        with col1:
            agg_needs_review_only = st.checkbox("Show only flagged phrases", value=False)
            st.caption("Filter to phrases with needs_correction flag set")

        with col2:
            min_group_size = st.selectbox(
                "Minimum group size:",
                options=[1, 2, 3, 5, 10],
                index=0,
                help="Minimum number of times a phrase must appear to be shown"
            )

        with col3:
            agg_search_term = st.text_input(
                "Search aggregated phrases:",
                placeholder="Search phrase text...",
                help="Search within phrase text"
            )

        # Load aggregated phrases
        st.markdown("---")
        aggregated_df = load_aggregated_thai_phrases(agg_needs_review_only, agg_search_term, min_group_size)

        if aggregated_df.empty:
            st.info("No aggregated phrases found matching your criteria.")
            st.info("💡 Try adjusting filters: uncheck 'Show only flagged phrases' or reduce minimum group size")
        else:
            # Summary statistics for aggregation
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Unique Groups", len(aggregated_df))
            with col2:
                total_instances = aggregated_df['group_size'].sum()
                st.metric("Total Instances", total_instances)
            with col3:
                reduction = ((total_instances - len(aggregated_df)) / total_instances) * 100
                st.metric("Review Reduction", f"{reduction:.1f}%")
            with col4:
                needs_correction = aggregated_df['needs_correction'].sum()
                st.metric("Need Correction", needs_correction)

            st.markdown("---")

            # Priority filter for aggregated view
            if 'priority' in aggregated_df.columns and aggregated_df['priority'].notna().any():
                priority_filter = st.selectbox(
                    "Filter by priority:",
                    options=["all", "HIGH_MULTI_FILE", "HIGH_LOW_CONFIDENCE", "MEDIUM_MULTI_FILE", "STANDARD"],
                    format_func=lambda x: x.replace('_', ' ').title() if x != "all" else "All"
                )

                if priority_filter != "all":
                    filtered_df = aggregated_df[aggregated_df['priority'] == priority_filter]
                else:
                    filtered_df = aggregated_df
            else:
                filtered_df = aggregated_df

            # Pagination for aggregated view
            items_per_page_agg = 50
            total_items_agg = len(filtered_df)
            total_pages_agg = (total_items_agg + items_per_page_agg - 1) // items_per_page_agg

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if total_pages_agg > 1:
                    current_page_agg = st.selectbox(
                        "Page",
                        options=list(range(1, total_pages_agg + 1)),
                        key="agg_page_select",
                        format_func=lambda x: f"Page {x} of {total_pages_agg}"
                    )
                else:
                    current_page_agg = 1

            start_idx_agg = (current_page_agg - 1) * items_per_page_agg
            end_idx_agg = min(start_idx_agg + items_per_page_agg, total_items_agg)

            st.info(f"Showing **{start_idx_agg + 1}-{end_idx_agg}** of **{total_items_agg}** aggregated phrase groups")

            # Display aggregated phrases with pagination
            page_df = filtered_df.iloc[start_idx_agg:end_idx_agg]
            for idx, row in page_df.iterrows():
                # Priority indicator
                priority_emoji = ""
                priority_color = "secondary"
                if row.get('priority') == 'HIGH_MULTI_FILE':
                    priority_emoji = "🔴"
                    priority_color = "error"
                elif row.get('priority') == 'HIGH_LOW_CONFIDENCE':
                    priority_emoji = "🟡"
                    priority_color = "warning"
                elif row.get('priority') == 'MEDIUM_MULTI_FILE':
                    priority_emoji = "🟠"
                    priority_color = "warning"
                elif row.get('priority') == 'STANDARD':
                    priority_emoji = "⚪"

                with st.expander(f"{priority_emoji} **{row['phrase_text'][:60]}{'...' if len(row['phrase_text']) > 60 else ''}** ({row['group_size']} instances)"):
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        # Phrase details
                        st.write(f"**Phrase:** `{row['phrase_text']}`")
                        st.write(f"**Group Size:** {row['group_size']} instances across {len(row['source_documents'].split('; '))} documents")
                        st.write(f"**Confidence:** {row['confidence_score']:.3f}" if pd.notna(row['confidence_score']) else "**Confidence:** N/A")
                        st.write(f"**Status:** {row['status']}")

                        # Dictionary correction status
                        if row.get('final_correction'):
                            st.success(f"**✅ Dictionary Correction:** {row['final_correction']}")
                            st.caption(f"Source: {row['correction_source']}")

                        # Source information
                        if row['source_documents']:
                            st.write(f"**Documents:** {row['source_documents']}")
                        if row['unique_companies']:
                            st.write(f"**Companies:** {row['unique_companies']}")
                        if row['context']:
                            st.write(f"**Context:** {row['context']}")

                        # Priority and correction info
                        if row.get('priority'):
                            st.info(f"**Priority:** {row['priority'].replace('_', ' ').title()}")

                    with col2:
                        # Quick actions
                        if row['needs_correction']:
                            st.error("🚨 Needs Review")
                        else:
                            st.success("✅ OK")

                        # Apply dictionary correction to group
                        if row.get('final_correction'):
                            if st.button("🔄 Apply to Group", key=f"apply_{row['best_phrase_id']}", help="Apply dictionary correction to all instances"):
                                if apply_correction_to_group(row['phrase_text'], row['final_correction'], 'dictionary'):
                                    st.success(f"Applied correction to {row['group_size']} instances")
                                    load_aggregated_thai_phrases.clear()
                                    st.rerun()
                                else:
                                    st.error("Failed to apply correction")

                        # Suggest correction for group
                        if st.button("💡 Suggest Correction", key=f"suggest_agg_{row['best_phrase_id']}", help="Add correction suggestion to all instances"):
                            st.session_state[f'show_correction_{row["best_phrase_id"]}'] = True

                    # Correction suggestion interface
                    if st.session_state.get(f'show_correction_{row["best_phrase_id"]}'):
                        st.markdown("### 💡 Suggest Group Correction")
                        col1, col2, col3 = st.columns([2, 1, 1])

                        with col1:
                            group_correction = st.text_input(
                                "Correction:",
                                value=row['correction_suggestion'] or "",
                                key=f"group_correction_{row['best_phrase_id']}"
                            )

                        with col2:
                            group_correction_type = st.selectbox(
                                "Type:",
                                options=["character_fix", "spacing", "tone_mark", "word_segmentation", "other"],
                                key=f"group_type_{row['best_phrase_id']}"
                            )

                        with col3:
                            if st.button("💾 Apply to Group", key=f"save_group_{row['best_phrase_id']}"):
                                if group_correction:
                                    if apply_correction_to_group(row['phrase_text'], group_correction, group_correction_type):
                                        st.success(f"Applied correction to {row['group_size']} instances")
                                        st.session_state[f'show_correction_{row["best_phrase_id"]}'] = False
                                        load_aggregated_thai_phrases.clear()
                                        st.rerun()
                                    else:
                                        st.error("Failed to apply group correction")
                                else:
                                    st.error("Please enter a correction")

                        if st.button("❌ Cancel", key=f"cancel_group_{row['best_phrase_id']}"):
                            st.session_state[f'show_correction_{row["best_phrase_id"]}'] = False
                            st.rerun()

    with tab2:
        st.header("📝 Individual Phrase Review")
        st.markdown("""
        ⚠️ **This view shows INDIVIDUAL phrases** - each row is a separate occurrence.
        The same phrase may appear multiple times if it exists in different documents.

        **For efficient review, use the "🔗 Aggregated Review" tab instead**, which groups identical phrases together.
        """)

        # Load phrases
        phrases_df = load_thai_phrases(status_filter, needs_review_only, search_term)

        if phrases_df.empty:
            st.info("No Thai phrases found matching your criteria.")
            return

        st.info(f"Found **{len(phrases_df)}** individual phrases")

        # Pagination setup
        PAGE_SIZE = 100
        total_pages = (len(phrases_df) + PAGE_SIZE - 1) // PAGE_SIZE

        # Initialize page number in session state if not exists
        if 'individual_page' not in st.session_state:
            st.session_state.individual_page = 1

        # Page navigation
        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            if st.button("⬅️ Previous", disabled=st.session_state.individual_page <= 1):
                st.session_state.individual_page -= 1
                st.rerun()

        with col2:
            st.write(f"Page **{st.session_state.individual_page}** of **{total_pages}**")
            page_input = st.number_input(
                "Go to page:",
                min_value=1,
                max_value=total_pages,
                value=st.session_state.individual_page,
                key="page_input"
            )
            if page_input != st.session_state.individual_page:
                st.session_state.individual_page = page_input
                st.rerun()

        with col3:
            if st.button("Next ➡️", disabled=st.session_state.individual_page >= total_pages):
                st.session_state.individual_page += 1
                st.rerun()

        # Get current page data
        start_idx = (st.session_state.individual_page - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        current_page_df = phrases_df.iloc[start_idx:end_idx]

        # Phrase display and review
        for idx, row in current_page_df.iterrows():
            with st.expander(f"📄 Phrase {row['phrase'][:50]}... (ID: {row['id']})"):
                col1, col2 = st.columns([3, 1])

                with col1:
                    # Phrase details
                    st.write(f"**Phrase:** `{row['phrase']}`")
                    st.write(f"**Word Count:** {row['word_count']}")
                    st.write(f"**Status:** {row['status']}")

                    if row['confidence_score']:
                        st.write(f"**Confidence:** {row['confidence_score']:.3f}")

                    if row['context']:
                        st.write(f"**Context:** {row['context']}")

                    if row['file_name']:
                        st.write(f"**Document:** {row['file_name']}")

                    if row['company_name']:
                        st.write(f"**Company:** {row['company_name']}")

                with col2:
                    # Review actions
                    if row['needs_correction']:
                        st.error("🚨 Needs Correction")
                    else:
                        st.success("✅ OK")

                    # Mark for correction
                    if st.button("🔧 Mark for Correction", key=f"correct_{row['id']}"):
                        update_phrase_status(
                            row['id'],
                            "reviewed",
                            needs_correction=True
                        )
                        st.rerun()

                    # Mark as correct
                    if st.button("✅ Mark as Correct", key=f"correct_ok_{row['id']}"):
                        update_phrase_status(
                            row['id'],
                            "corrected",
                            needs_correction=False
                        )
                        st.rerun()

                # Correction suggestion
                if row['needs_correction']:
                    st.markdown("**💡 Suggest Correction:**")
                    col1, col2, col3 = st.columns([2, 1, 1])

                    with col1:
                        correction_text = st.text_input(
                            "Correction:",
                            value=row['correction_suggestion'] or "",
                            key=f"suggestion_{row['id']}"
                        )

                    with col2:
                        correction_type = st.selectbox(
                            "Type:",
                            options=["character_fix", "spacing", "tone_mark", "word_segmentation", "other"],
                            key=f"type_{row['id']}"
                        )

                    with col3:
                        if st.button("💾 Save", key=f"save_{row['id']}"):
                            if correction_text:
                                update_phrase_status(
                                    row['id'],
                                    "reviewed",
                                    needs_correction=True,
                                    correction_suggestion=correction_text,
                                    notes=f"Correction type: {correction_type}"
                                )
                                st.success("Correction suggestion saved!")
                                st.rerun()

    with tab2:
        st.header("➕ Add Manual Correction")

        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("### 🔧 New Correction")

            error_pattern = st.text_input(
                "Error Pattern (OCR output):",
                placeholder="e.g., จํากัด",
                help="Enter the incorrect Thai text as it appears in OCR output"
            )

            correction = st.text_input(
                "Correct Pattern:",
                placeholder="e.g., จำกัด",
                help="Enter the correct Thai text"
            )

            correction_type = st.selectbox(
                "Correction Type:",
                options=["character_fix", "spacing", "tone_mark", "word_segmentation", "abbreviation", "other"]
            )

            confidence = st.slider(
                "Confidence:",
                min_value=0.0,
                max_value=1.0,
                value=0.9,
                step=0.05,
                help="How confident are you in this correction?"
            )

            if st.button("➕ Add Correction", type="primary"):
                if error_pattern and correction:
                    if add_correction_to_dictionary(error_pattern, correction, correction_type, confidence):
                        st.success(f"✅ Added correction: {error_pattern} → {correction}")
                        load_existing_corrections.clear()
                        st.rerun()
                else:
                    st.error("Please enter both error pattern and correction")

        with col2:
            st.markdown("### 📋 Recent Manual Corrections")

            # Show recent corrections added manually
            conn = get_db_connection()
            recent_corrections = pd.read_sql_query('''
                SELECT error_pattern, correction, type, created_at
                FROM thai_ocr_corrections
                WHERE is_active = 1
                ORDER BY created_at DESC
                LIMIT 10
            ''', conn)
            conn.close()

            if not recent_corrections.empty:
                for _, row in recent_corrections.iterrows():
                    st.write(f"**{row['error_pattern']}** → **{row['correction']}**")
                    st.caption(f"Type: {row['type']} | {row['created_at']}")
                    st.markdown("---")
            else:
                st.info("No manual corrections added yet")

    with tab3:
        st.header("📚 Current Dictionary")

        # Load existing corrections
        corrections_df = load_existing_corrections()

        if not corrections_df.empty:
            # Summary by type
            st.markdown("### 📊 Dictionary Summary")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Corrections", len(corrections_df))

            with col2:
                critical_count = len(corrections_df[corrections_df['priority'] == 'critical'])
                st.metric("Critical", critical_count)

            with col3:
                high_count = len(corrections_df[corrections_df['priority'] == 'high'])
                st.metric("High Priority", high_count)

            with col4:
                avg_confidence = corrections_df['confidence'].mean()
                st.metric("Avg Confidence", f"{avg_confidence:.3f}")

            st.markdown("---")

            # Type distribution
            st.markdown("### 📈 Distribution by Type")
            type_counts = corrections_df['type'].value_counts()
            st.bar_chart(type_counts)

            st.markdown("---")

            # Corrections table
            st.markdown("### 📋 All Corrections")

            # Filter options
            filter_col1, filter_col2 = st.columns(2)
            with filter_col1:
                priority_filter = st.selectbox(
                    "Filter by Priority:",
                    options=["all", "critical", "high", "medium", "low"]
                )

            with filter_col2:
                type_filter = st.selectbox(
                    "Filter by Type:",
                    options=["all"] + list(corrections_df['type'].unique())
                )

            # Apply filters
            filtered_df = corrections_df.copy()
            if priority_filter != "all":
                filtered_df = filtered_df[filtered_df['priority'] == priority_filter]

            if type_filter != "all":
                filtered_df = filtered_df[filtered_df['type'] == type_filter]

            st.dataframe(
                filtered_df[[
                    'error_pattern', 'correction', 'frequency', 'type',
                    'priority', 'confidence'
                ]].rename(columns={
                    'error_pattern': 'Error Pattern',
                    'correction': 'Correction',
                    'frequency': 'Frequency',
                    'type': 'Type',
                    'priority': 'Priority',
                    'confidence': 'Confidence'
                }),
                width='stretch'
            )
        else:
            st.info("No corrections found in the dictionary")

    with tab4:
        st.header("📈 Phrase Analytics")

        # Phrase statistics
        st.markdown("### 📊 Phrase Statistics")

        # Load all phrases for analytics
        all_phrases = load_thai_phrases()

        if not all_phrases.empty:
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total Phrases", len(all_phrases))

            with col2:
                avg_word_count = all_phrases['word_count'].mean()
                st.metric("Avg Word Count", f"{avg_word_count:.1f}")

            with col3:
                needs_review = all_phrases['needs_correction'].sum()
                st.metric("Need Review", needs_review)

            st.markdown("---")

            # Status distribution
            st.markdown("### 📈 Status Distribution")
            status_counts = all_phrases['status'].value_counts()
            st.bar_chart(status_counts)

            st.markdown("---")

            # Word count distribution
            st.markdown("### 📏 Word Count Distribution")
            word_count_dist = all_phrases['word_count'].value_counts().sort_index()
            st.bar_chart(word_count_dist)

            st.markdown("---")

            # Confidence distribution
            st.markdown("### 🎯 Confidence Distribution")
            confidence_counts = all_phrases['confidence_score'].dropna()

            if not confidence_counts.empty:
                hist_bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
                confidence_hist = pd.cut(confidence_counts, bins=hist_bins, include_lowest=True).value_counts().sort_index()
                st.bar_chart(confidence_hist)
        else:
            st.info("No phrase data available for analytics")

if __name__ == "__main__":
    main()