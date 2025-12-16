# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for report detail template rendering."""

from pathlib import Path


def test_report_detail_template_structure():
    """Test that the report detail template has the correct structure for citations."""
    # Read the template file directly
    template_path = Path(__file__).parent.parent / "templates" / "report_detail.html"
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # Verify citations section exists
    assert 'class="citations-section"' in template_content
    assert 'Citations (' in template_content
    
    # Verify citation card structure exists
    assert 'citation-card' in template_content
    assert 'citation-text' in template_content
    assert 'citation-metadata' in template_content
    
    # Verify quote field is used
    assert 'citation.quote' in template_content
    
    # Verify fallback for no quote
    assert 'No text snippet available' in template_content
    
    # Verify message_id and chunk_id are displayed
    assert 'citation.message_id' in template_content
    assert 'citation.chunk_id' in template_content
    
    # Verify copy buttons exist
    assert 'copyToClipboard' in template_content or 'citation-copy-btn' in template_content
    
    # Verify "no citations" message exists
    assert 'No citations available' in template_content


def test_template_css_includes_citation_styles():
    """Test that template includes CSS for citation display."""
    template_path = Path(__file__).parent.parent / "templates" / "report_detail.html"
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # Verify CSS classes for citations
    assert '.citation-card' in template_content
    assert '.citation-text' in template_content
    assert '.citation-header' in template_content
    assert '.citation-number' in template_content
    assert '.citation-id-badge' in template_content
    assert '.citation-metadata' in template_content
    # Verify word-wrap CSS
    assert 'overflow-wrap: break-word' in template_content
    assert 'word-break: break-word' in template_content


def test_template_has_citation_data_bindings():
    """Test template has proper citation data bindings."""
    template_path = Path(__file__).parent.parent / "templates" / "report_detail.html"
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # Verify citation data bindings exist in template
    assert '{% for citation in report.citations %}' in template_content
    assert 'citation.quote' in template_content
    assert 'citation.message_id' in template_content
    assert 'citation.chunk_id' in template_content
    assert 'data-copy-text="{{ citation.message_id }}"' in template_content
    assert 'data-copy-text="{{ citation.chunk_id }}"' in template_content


def test_template_has_empty_quote_fallback():
    """Test template has fallback for empty quotes."""
    template_path = Path(__file__).parent.parent / "templates" / "report_detail.html"
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # Verify fallback structure exists
    assert '{% if citation.quote %}' in template_content
    assert '{% else %}' in template_content
    assert 'No text snippet available' in template_content
    assert 'citation-text no-quote' in template_content


def test_template_uses_data_attributes_not_inline_onclick():
    """Test template uses data attributes instead of inline onclick for safety."""
    template_path = Path(__file__).parent.parent / "templates" / "report_detail.html"
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # Verify data-copy-text attributes are used (safer than onclick)
    assert 'data-copy-text=' in template_content
    assert 'citation-copy-btn' in template_content
    # Verify no direct onclick handlers with citation IDs (which could have XSS issues)
    assert 'onclick="copyToClipboard(\'{{ citation.' not in template_content


def test_template_has_accessibility_attributes():
    """Test that copy buttons have accessibility attributes."""
    template_path = Path(__file__).parent.parent / "templates" / "report_detail.html"
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # Verify aria-label and title attributes
    assert 'aria-label="Copy message ID"' in template_content
    assert 'aria-label="Copy chunk ID"' in template_content
    assert 'title="Copy message ID"' in template_content
    assert 'title="Copy chunk ID"' in template_content
    # Verify event listener script for citation copy buttons
    assert '.citation-copy-btn' in template_content
    assert 'addEventListener' in template_content
