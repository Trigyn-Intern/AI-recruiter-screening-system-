"""
Test that build_resume_analysis_context handles chunk_data dicts with NumPy embeddings.

This test verifies that when chunk_data contains NumPy embedding arrays,
only the chunk metadata is extracted for JSON serialization, preventing
"Object of type ndarray is not JSON serializable" errors.
"""

import json
import numpy as np
import pytest
from backend import build_resume_analysis_context


def test_chunk_context_with_embedding_dict():
    """Test that chunk_data dict with embeddings is handled correctly."""
    # Create a chunk_data dict similar to what get_or_create_resume_embeddings_chunked returns
    chunk_data = {
        'embeddings': [
            np.array([[0.1, 0.2, 0.3]], dtype="float32"),
            np.array([[0.4, 0.5, 0.6]], dtype="float32"),
        ],
        'chunks': [
            {
                'chunk_id': 'resume1_chunk_000',
                'resume_id': 'resume1',
                'text': 'Experience in Python development',
                'section': 'Experience',
                'subsection': 'Senior Developer',
            },
            {
                'chunk_id': 'resume1_chunk_001',
                'resume_id': 'resume1',
                'text': 'Experience in React framework',
                'section': 'Experience',
                'subsection': 'Frontend Developer',
            },
        ]
    }

    # This should not raise a JSON serialization error
    context = build_resume_analysis_context(
        resume_text="John Doe\nSoftware Engineer",
        resume_skill_profile=None,
        resume_chunks=chunk_data
    )

    # Verify that chunk metadata is in the context
    assert "RETRIEVED RESUME CHUNKS:" in context
    assert "Experience in Python development" in context
    assert "Experience in React framework" in context

    # Verify that embeddings are NOT in the context (they're not JSON serializable)
    # The context should be a string, not contain raw NumPy arrays
    assert isinstance(context, str)

    # Verify that the JSON serialization succeeded by checking we can parse it back
    context_start = context.find("RETRIEVED RESUME CHUNKS:")
    if context_start != -1:
        # Extract the JSON portion (after the header)
        json_text = context[context_start + len("RETRIEVED RESUME CHUNKS:\n"):].strip()
        # This should not raise an error
        parsed_chunks = json.loads(json_text)
        # Verify it's a list of chunks (not the full dict with embeddings)
        assert isinstance(parsed_chunks, list)
        assert len(parsed_chunks) == 2
        assert parsed_chunks[0]['text'] == 'Experience in Python development'


def test_chunk_context_with_list_of_chunks():
    """Test that existing list-of-chunks format still works."""
    chunks_list = [
        {
            'chunk_id': 'resume2_chunk_000',
            'resume_id': 'resume2',
            'text': 'Skills in data analysis',
            'section': 'Skills',
        },
        {
            'chunk_id': 'resume2_chunk_001',
            'resume_id': 'resume2',
            'text': 'Machine learning experience',
            'section': 'Experience',
        }
    ]

    context = build_resume_analysis_context(
        resume_text="Jane Smith\nData Scientist",
        resume_skill_profile=None,
        resume_chunks=chunks_list
    )

    assert "RETRIEVED RESUME CHUNKS:" in context
    assert "Skills in data analysis" in context
    assert "Machine learning experience" in context


def test_chunk_context_with_none():
    """Test that None chunks are handled correctly."""
    context = build_resume_analysis_context(
        resume_text="Test Resume",
        resume_skill_profile=None,
        resume_chunks=None
    )

    # Should not include chunk context when chunks is None
    assert "RETRIEVED RESUME CHUNKS:" not in context


def test_chunk_context_with_empty_list():
    """Test that empty chunk list is handled correctly."""
    context = build_resume_analysis_context(
        resume_text="Test Resume",
        resume_skill_profile=None,
        resume_chunks=[]
    )

    # Should not include chunk context when chunks is empty
    assert "RETRIEVED RESUME CHUNKS:" not in context


def test_chunk_context_with_dict_without_chunks_key():
    """Test that dict without 'chunks' key is handled gracefully."""
    other_dict = {
        'some_key': 'some_value',
        'another_key': 123
    }

    # This should either work or handle the dict appropriately
    # The current implementation will try to JSON serialize it
    context = build_resume_analysis_context(
        resume_text="Test Resume",
        resume_skill_profile=None,
        resume_chunks=other_dict
    )

    # The dict should be serialized (it doesn't contain NumPy arrays)
    assert isinstance(context, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
