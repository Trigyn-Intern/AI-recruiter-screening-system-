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
    index.ntotal = 5
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

    assert result.shape == (1024,)
    index.reconstruct.assert_called_once_with(4)
    mock_encode.assert_not_called()
    mock_save.assert_not_called()


def test_load_resume_vector_store_reconciles_stale_faiss_rows(mocker):
    index = mocker.Mock()
    index.ntotal = 2
    index.d = 1024
    mocker.patch("backend.faiss.read_index", return_value=index)

    fake_index_path = mocker.Mock()
    fake_index_path.exists.return_value = True
    fake_metadata_path = mocker.Mock()
    fake_metadata_path.exists.return_value = True

    mocker.patch("backend.FAISS_INDEX_PATH", fake_index_path)
    mocker.patch("backend.FAISS_METADATA_PATH", fake_metadata_path)

    mocked_metadata = [
        {"resume_id": "resume-1", "resume_name": "one.pdf", "faiss_row": 0},
        {"resume_id": "resume-2", "resume_name": "two.pdf", "faiss_row": 99},
    ]
    mocker.patch("backend.json.loads", return_value=mocked_metadata)
    mock_write = mocker.patch("backend.write_json_file")

    result_index, result_metadata = __import__("backend").load_resume_vector_store()

    assert result_index is index
    assert result_metadata == [mocked_metadata[0]]
    mock_write.assert_called_once_with(
        __import__("backend").FAISS_METADATA_PATH, [mocked_metadata[0]]
    )
