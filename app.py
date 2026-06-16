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
    return SentenceTransformer("BAAI/bge-large-en-v1.5")


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

    resume_embedding = model.encode(
        [
            "Represent this resume for retrieval:"
            +resume_text
        ],
        normalize_embeddings=True
    )

    job_embedding = model.encode(
        [
            "Represent this description for matching:"
            +job_text
        ],
        normalize_embeddings=True
    )

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

1. Matching Skills
   (Skills present in both Resume and JD)
2. Missing Skills
   (Skills required in JD but absent in Resume)
3. Match Reason
   (Professional recruiter-style explanation explaining why this candidate received the match score.)

Return ONLY valid JSON.
Do not include markdown.
Do not include explanations.
Do not include text before or after the JSON.
Ensure all strings are properly escaped.

Format:

{{
    "matching_skills": [],
    "missing_skills": [],
    "match_reason": ""
}}

Match Reason Rules:

- Use professional recruiter language.
- Maximum 2 sentences.
- Explain strengths and skill gaps.
- Consider matching skills and missing skills.
- Do not mention percentages.
- Do not use bullet points.

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
        print(json_text)

        print(result)

        return json.loads(json_text)

    except Exception as e:
        print("ERROR:", e)

        return {
            "matching_skills": [],
            "missing_skills": [],
            "match_reason": "Unable to generate match explanation."
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
    
    top_5_names = ranking_df.head(5)[
        "Resume Name"
    ].tolist()

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
        "⭐ Top 5 Candidate Detailed Analysis"
    )

    for resume in resumes:

        if resume.name not in top_5_names:
            continue

        with st.expander(
            f"📄 {resume.name}"
        ):

            resume_text = extract_text(
                resume
            )

            score = ranking_df.loc[
                ranking_df["Resume Name"]
                == resume.name,
                "Match Score (%)"
            ].values[0]

            skills = analyze_skill_gap(
                resume_text,
                job_description
            )

            st.metric(
                "Match Score",
                f"{score}%"
            )
            
            st.info(
                skills.get(
                    "match_reason",
                    ""
                )
            )
            
            max_len = max(
                len(
                    skills.get(
                        "matching_skills",
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

            matching_skills = (
                skills.get(
                    "matching_skills",
                    []
                )
                + [""] *
                (
                    max_len -
                    len(
                        skills.get(
                            "matching_skills",
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
                    "✅ Matching Skills": matching_skills,
                    "❌ Missing Skills": missing_skills
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