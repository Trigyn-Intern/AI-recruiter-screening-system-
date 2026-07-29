import numpy as np

from backend import calculate_match_score, get_or_create_resume_embedding

def test_match_score_range():
    resume = "Python Machine Learning AI"
    jd = "Python AI developer"

    score = calculate_match_score(resume, jd)

    assert isinstance(score, float)
    assert 0 <= score <= 100


def test_get_or_create_resume_embedding_uses_cached_faiss_row(mocker):
    cached_vector = np.asarray([0.1] * 1024, dtype="float32")
    index = mocker.Mock()
    index.reconstruct.return_value = cached_vector
    mocker.patch(
        "backend.load_resume_vector_store",
        return_value=(
            index,
            [
                {
                    "resume_id": "resume-1",
                    "resume_name": "resume.pdf",
                    "faiss_row": 4,
                }
            ],
        ),
    )
    mock_encode = mocker.patch("backend.encode_text_embedding")
    mock_save = mocker.patch("backend.save_resume_vector_store")

    result = get_or_create_resume_embedding(
        "resume-1",
        "resume.pdf",
        "resume text",
    )

    assert result.shape == (1, 1024)
    index.reconstruct.assert_called_once_with(4)
    mock_encode.assert_not_called()
    mock_save.assert_called_once()
