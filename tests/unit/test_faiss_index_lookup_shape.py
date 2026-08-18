import pytest
import numpy as np
from backend import faiss_index_lookup, EMBEDDING_DIMENSION


def test_faiss_index_lookup_returns_2d_array(mocker):
    """Test that faiss_index_lookup returns 2D array (1, embedding_dim) not 1D."""
    # Mock the FAISS index and metadata
    cached_vector = np.asarray([0.1] * EMBEDDING_DIMENSION, dtype="float32")
    index = mocker.Mock()
    index.ntotal = 5
    index.reconstruct.return_value = cached_vector
    
    metadata = [
        {
            "resume_id": "test-resume-1",
            "resume_name": "test.pdf",
            "faiss_row": 2,
        }
    ]
    
    mocker.patch(
        "backend.load_resume_vector_store",
        return_value=(index, metadata),
    )
    
    # Call faiss_index_lookup
    result = faiss_index_lookup("test-resume-1")
    
    # Verify result is not None
    assert result is not None
    
    # Verify result is 2D array with shape (1, embedding_dim)
    assert result.shape == (1, EMBEDDING_DIMENSION), \
        f"Expected shape (1, {EMBEDDING_DIMENSION}), got {result.shape}"
    
    # Verify it's not 1D
    assert result.ndim == 2, f"Expected ndim=2, got ndim={result.ndim}"
    
    # Verify the embedding values are correct
    np.testing.assert_array_equal(result[0], cached_vector)

