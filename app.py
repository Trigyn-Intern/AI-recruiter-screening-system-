import streamlit as st
import PyPDF2
import pandas as pd
import json
import ollama

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from docx import Document

# ==================================================
# LOAD EMBEDDING MODEL
# ==================================================

@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")


model = load_model()


# ==================================================
# EXTRACT PDF TEXT
# ==================================================

def extract_pdf_text(pdf_file):

    text = ""

    reader = PyPDF2.PdfReader(pdf_file)

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text

def extract_docx_text(docx_file):
    document = Document(docx_file)
    text = ""
    for paragraph in document.paragraphs:
        text += paragraph.text + "\n"
    return text

def extract_text(file):

    if file.name.endswith(".pdf"):

        return extract_pdf_text(file)

    elif file.name.endswith(".docx"):

        return extract_docx_text(file)

    else:

        return ""
# ==================================================
# MATCH SCORE
# ==================================================

def calculate_match_score(resume_text, job_text):

    resume_embedding = model.encode([resume_text])

    job_embedding = model.encode([job_text])

    similarity = cosine_similarity(
        resume_embedding,
        job_embedding
    )

    score = float(similarity[0][0]) * 100

    return round(score, 2)


# ==================================================
# JD ANALYSIS
# ==================================================

def analyze_job_description(job_text):

    prompt = f"""
You are an HR Recruitment Expert.

Read the Job Description carefully.

Extract:

1. Years of Experience Required
2. Primary Skills
3. Secondary Skills
4. Educational Qualifications

Return ONLY valid JSON.

Format:

{{
    "experience": "",
    "primary_skills": "",
    "secondary_skills": "",
    "education": ""
}}

JOB DESCRIPTION:

{job_text}
"""

    try:

        response = ollama.chat(
            model="llama3.2",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        result = response["message"]["content"]

        start = result.find("{")
        end = result.rfind("}") + 1

        json_text = result[start:end]

        return json.loads(json_text)

    except Exception:

        return {
            "experience": "Not Found",
            "primary_skills": "Not Found",
            "secondary_skills": "Not Found",
            "education": "Not Found"
        }


# ==================================================
# SKILL GAP ANALYSIS
# ==================================================

def analyze_skill_gap(resume_text, job_text):

    prompt = f"""
You are an ATS and Recruitment Expert.

Compare the RESUME and JOB DESCRIPTION.

Identify:

1. Resume Skills
2. Job Description Skills
3. Missing Skills

Return ONLY valid JSON.

Format:

{{
    "resume_skills": [],
    "jd_skills": [],
    "missing_skills": []
}}

RESUME:

{resume_text}

JOB DESCRIPTION:

{job_text}
"""

    try:

        response = ollama.chat(
            model="llama3.2",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        result = response["message"]["content"]

        start = result.find("{")
        end = result.rfind("}") + 1

        json_text = result[start:end]

        return json.loads(json_text)

    except Exception:

        return {
            "resume_skills": [],
            "jd_skills": [],
            "missing_skills": []
        }
# ==================================================
# PROCESS SINGLE RESUME
# ==================================================

def process_resume(resume_file, job_description):

    resume_text = extract_text(resume_file)

    score = calculate_match_score(
        resume_text,
        job_description
    )


    return {
        "Resume Name": resume_file.name,
        "Match Score (%)": score,
    }


# ==================================================
# PAGE CONFIG
# ==================================================

st.set_page_config(
    page_title="AI Recruiter Screening System",
    page_icon="📄",
    layout="wide"
)


# ==================================================
# UI
# ==================================================

st.title("📄 AI Recruiter Screening System")

st.write(
    "Upload multiple resumes and compare them against a Job Description using AI."
)

st.divider()


resumes = st.file_uploader(
    "Upload Resumes (PDF/DOCX)",
    type=["pdf", "docx"],
    accept_multiple_files=True
)

job_description = st.text_area(
    "Paste Job Description",
    height=250
)


# ==================================================
# MAIN LOGIC
# ==================================================

if resumes and job_description.strip():

    # ==============================================
    # JD ANALYSIS
    # ==============================================

    st.subheader(
        "🧠 Job Description Analysis"
    )

    with st.spinner(
        "Analyzing Job Description..."
    ):

        jd_info = analyze_job_description(
            job_description
        )

    jd_df = pd.DataFrame(
        {
            "Years of Experience": [
                jd_info.get(
                    "experience",
                    "Not Found"
                )
            ],

            "Primary Skills": [
                jd_info.get(
                    "primary_skills",
                    "Not Found"
                )
            ],

            "Secondary Skills": [
                jd_info.get(
                    "secondary_skills",
                    "Not Found"
                )
            ],

            "Educational Qualifications": [
                jd_info.get(
                    "education",
                    "Not Found"
                )
            ]
        }
    )

    st.table(jd_df)

    st.divider()

    # ==============================================
    # CANDIDATE RANKING
    # ==============================================

    st.subheader(
        "🏆 Candidate Ranking Dashboard"
    )

    results = []
    good_fit = []
    moderate_fit = []
    bad_fit = []

    progress_bar = st.progress(0)

    total_resumes = len(resumes)

    for index, resume in enumerate(resumes):

        result = process_resume(
            resume,
            job_description
        )

        results.append(result)
        score = result["Match Score (%)"]

        if score >= 70:

            good_fit.append(
                result["Resume Name"]
            )

        elif score >= 50:

            moderate_fit.append(
                result["Resume Name"]
            )

        else:

            bad_fit.append(
                result["Resume Name"]
            )

        progress_bar.progress(
            float(index + 1) /
            float(total_resumes)
        )

    ranking_df = pd.DataFrame(
        results
    )

    ranking_df = ranking_df.sort_values(
        by="Match Score (%)",
        ascending=False
    )

    ranking_df.index = range(
        1,
        len(ranking_df) + 1
    )

    ranking_df.index.name = "Rank"

    st.dataframe(
        ranking_df,
        use_container_width=True
    )
    st.divider()

    # ==============================================
    # DETAILED ANALYSIS
    # ==============================================

    st.subheader(
        "🔍 Detailed Candidate Analysis"
    )

    for resume in resumes:

        with st.expander(
            f"📄 {resume.name}"
        ):

            resume_text = extract_text(
                resume
            )

            score = calculate_match_score(
                resume_text,
                job_description
            )

            st.metric(
                "Match Score",
                f"{score}%"
            )

            skills = analyze_skill_gap(
                resume_text,
                job_description
            )
            
            max_len = max(
                len(
                    skills.get(
                        "resume_skills",
                        []
                    )
                ),
                len(
                    skills.get(
                        "jd_skills",
                        []
                    )
                ),
                len(
                    skills.get(
                        "missing_skills",
                        []
                    )
                )
            )

            resume_skills = (
                skills.get(
                    "resume_skills",
                    []
                )
                + [""] *
                (
                    max_len -
                    len(
                        skills.get(
                            "resume_skills",
                            []
                        )
                    )
                )
            )

            jd_skills = (
                skills.get(
                    "jd_skills",
                    []
                )
                + [""] *
                (
                    max_len -
                    len(
                        skills.get(
                            "jd_skills",
                            []
                        )
                    )
                )
            )

            missing_skills = (
                skills.get(
                    "missing_skills",
                    []
                )
                + [""] *
                (
                    max_len -
                    len(
                        skills.get(
                            "missing_skills",
                            []
                        )
                    )
                )
            )

            skill_df = pd.DataFrame(
                {
                    "Resume Skills": resume_skills,
                    "JD Skills": jd_skills,
                    "Missing Skills": missing_skills
                }
            )

            st.dataframe(
                skill_df,
                use_container_width=True
            )

            if score >= 70:

                st.success(
                    "Strong Match"
                )

            elif score >= 50:

                st.warning(
                    "Moderate Match"
                )

            else:

                st.error(
                    "Low Match"
                )

    st.divider()
    st.subheader(
            "📋 Candidate Categorization"
        )

    max_len = max(
        1,
        len(good_fit),
        len(moderate_fit),
        len(bad_fit)
    )

    good_fit += [""] * (
        max_len - len(good_fit)
    )

    moderate_fit += [""] * (
        max_len - len(moderate_fit)
    )

    bad_fit += [""] * (
        max_len - len(bad_fit)
    )

    classification_df = pd.DataFrame(
        {
            "🟢 Good Fit": good_fit,
            "🟡 Moderate Fit": moderate_fit,
            "🔴 Bad Fit": bad_fit
        }
    )

    st.dataframe(
        classification_df,
        use_container_width=True
    )
st.caption(
    "Built using Streamlit, Sentence Transformers, Ollama Llama 3.2, Pandas and Scikit-Learn."
)