from app import calculate_match_score

def test_match_score_range():
    resume = "Python Machine Learning AI"
    jd = "Python AI developer"

    score = calculate_match_score(resume, jd)

    assert isinstance(score, float)
    assert 0 <= score <= 100