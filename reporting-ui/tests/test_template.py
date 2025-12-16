# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for report detail template rendering."""

import os
from pathlib import Path


def test_report_detail_template_structure():
    """Test that the report detail template has the correct structure for citations."""
    # Read the template file directly
    template_path = Path(__file__).parent.parent / "templates" / "report_detail.html"
    
    with open(template_path, 'r') as f:
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
    assert 'copyToClipboard' in template_content
    
    # Verify "no citations" message exists
    assert 'No citations available' in template_content


def test_template_css_includes_citation_styles():
    """Test that template includes CSS for citation display."""
    template_path = Path(__file__).parent.parent / "templates" / "report_detail.html"
    
    with open(template_path, 'r') as f:
        template_content = f.read()
    
    # Verify CSS classes for citations
    assert '.citation-card' in template_content
    assert '.citation-text' in template_content
    assert '.citation-header' in template_content
    assert '.citation-number' in template_content
    assert '.citation-id-badge' in template_content
    assert '.citation-metadata' in template_content

