"""Compatibility module for legacy imports.

The Streamlit UI has been removed. Backend logic now lives in backend.py,
and the user interface lives in frontend/.
"""

from backend import *  # noqa: F401,F403

# ==================================================
# LEGACY STREAMLIT APP COPY (REFERENCE ONLY)
# ==================================================
#
# The active application is now React + FastAPI + backend.py.
# This commented block preserves the earlier Streamlit implementation for reference.
#
# import json
#
# import ollama
# import pandas as pd
# import streamlit as st
# from docx import Document
# from jsonschema import ValidationError, validate
# from pypdf import PdfReader
# from sentence_transformers import SentenceTransformer
# from sklearn.metrics.pairwise import cosine_similarity
#
#
# # ==================================================
# # PAGE CONFIG
# # ==================================================
#
# st.set_page_config(
#     page_title="AI Recruiter Screening System",
#     page_icon="📄",
#     layout="wide",
# )
#
#
# # ==================================================
# # CONFIGURATION DEFAULTS
# # ==================================================
#
# DEFAULT_OLLAMA_MODEL = "llama3.2"
#
# OLLAMA_MODEL_OPTIONS = [
#     "llama3.2",
#     "llama3.1",
#     "mistral",
#     "gemma2",
#     "qwen2.5",
# ]
#
# DEFAULT_JD_PROMPT_TEMPLATE = """You are an HR Recruitment Expert.
#
# Read the Job Description carefully.
#
# Extract:
#
# 1. Years of Experience Required
# 2. Primary Skills
# 3. Secondary Skills
# 4. Educational Qualifications
#
# Return ONLY valid JSON.
#
# Format:
#
# {
#     "experience": "",
#     "primary_skills": "",
#     "secondary_skills": "",
#     "education": ""
# }
#
# JOB DESCRIPTION:
#
# {job_text}
# """
#
# DEFAULT_SKILL_GAP_PROMPT_TEMPLATE = """You are an ATS and Technical Recruiter.
#
# Compare the candidate profile against the job requirements.
#
# Return ONLY valid JSON.
#
# Format:
#
# {
#     "matching_skills": [
#         "skill1",
#         "skill2"
#     ],
#     "missing_skills": [
#         "skill1",
#         "skill2"
#     ]
# }
#
# Rules:
# - Maximum 10 matching skills.
# - Maximum 10 missing skills.
# - No explanations.
# - No markdown.
# - No code blocks.
# - No text before or after JSON.
#
# RESUME:
# {resume_text}
#
# JOB DESCRIPTION:
# {job_text}
# """
#
# JD_SCHEMA = {
#     "type": "object",
#     "required": [
#         "experience",
#         "primary_skills",
#         "secondary_skills",
#         "education",
#     ],
#     "properties": {
#         "experience": {},
#         "primary_skills": {},
#         "secondary_skills": {},
#         "education": {},
#     },
# }
#
# JD_RESPONSE_SCHEMA = {
#     "type": "object",
# }
#
# SKILL_GAP_SCHEMA = {
#     "type": "object",
#     "properties": {
#         "matching_skills": {},
#         "missing_skills": {},
#     },
# }
#
# JD_FALLBACK = {
#     "experience": "Not Found",
#     "primary_skills": "Not Found",
#     "secondary_skills": "Not Found",
#     "education": "Not Found",
# }
#
# SKILL_GAP_FALLBACK = {
#     "matching_skills": [],
#     "missing_skills": [],
# }
#
#
# # ==================================================
# # LOAD EMBEDDING MODEL
# # ==================================================
#
# @st.cache_resource
# def load_model():
#     return SentenceTransformer("BAAI/bge-large-en-v1.5")
#
#
# @st.cache_data(ttl=30)
# def get_available_ollama_models():
#     try:
#         response = ollama.list()
#         models = getattr(response, "models", None)
#
#         if models is None and isinstance(response, dict):
#             models = response.get("models", [])
#
#         names = []
#
#         for model in models:
#             if isinstance(model, dict):
#                 name = model.get("name") or model.get("model")
#             else:
#                 name = (
#                     getattr(model, "name", None)
#                     or getattr(model, "model", None)
#                 )
#
#             if name:
#                 names.append(name)
#
#         return names
#
#     except Exception:
#         return []
#
#
# # ==================================================
# # HELPERS
# # ==================================================
#
# def init_configuration_state():
#     model_options = get_model_options()
#
#     if st.session_state.get("ollama_model") not in model_options:
#         st.session_state["ollama_model"] = model_options[0]
#
#     if not st.session_state.get("jd_prompt_template", "").strip():
#         st.session_state["jd_prompt_template"] = DEFAULT_JD_PROMPT_TEMPLATE
#
#     if not st.session_state.get("skill_gap_prompt_template", "").strip():
#         st.session_state[
#             "skill_gap_prompt_template"
#         ] = DEFAULT_SKILL_GAP_PROMPT_TEMPLATE
#
#     st.session_state.setdefault("use_custom_jd_prompt", False)
#     st.session_state.setdefault("use_custom_skill_gap_prompt", False)
#     st.session_state.setdefault(
#         "active_jd_prompt_template",
#         DEFAULT_JD_PROMPT_TEMPLATE,
#     )
#     st.session_state.setdefault(
#         "active_skill_gap_prompt_template",
#         DEFAULT_SKILL_GAP_PROMPT_TEMPLATE,
#     )
#
#     if not st.session_state["use_custom_jd_prompt"]:
#         st.session_state["active_jd_prompt_template"] = (
#             DEFAULT_JD_PROMPT_TEMPLATE
#         )
#
#     if not st.session_state["use_custom_skill_gap_prompt"]:
#         st.session_state["active_skill_gap_prompt_template"] = (
#             DEFAULT_SKILL_GAP_PROMPT_TEMPLATE
#         )
#
#
# def get_selected_model():
#     return st.session_state.get("ollama_model", DEFAULT_OLLAMA_MODEL)
#
#
# def get_model_options():
#     available_models = get_available_ollama_models()
#
#     if available_models:
#         return available_models
#
#     return OLLAMA_MODEL_OPTIONS
#
#
# def get_jd_prompt_template():
#     if not st.session_state.get("use_custom_jd_prompt", False):
#         return DEFAULT_JD_PROMPT_TEMPLATE
#
#     prompt = st.session_state.get("active_jd_prompt_template", "")
#     return prompt if prompt.strip() else DEFAULT_JD_PROMPT_TEMPLATE
#
#
# def get_skill_gap_prompt_template():
#     if not st.session_state.get("use_custom_skill_gap_prompt", False):
#         return DEFAULT_SKILL_GAP_PROMPT_TEMPLATE
#
#     prompt = st.session_state.get("active_skill_gap_prompt_template", "")
#     return prompt if prompt.strip() else DEFAULT_SKILL_GAP_PROMPT_TEMPLATE
#
#
# def apply_prompt_configuration():
#     jd_prompt = st.session_state.get("jd_prompt_template", "")
#     skill_gap_prompt = st.session_state.get("skill_gap_prompt_template", "")
#
#     st.session_state["use_custom_jd_prompt"] = (
#         jd_prompt.strip() != DEFAULT_JD_PROMPT_TEMPLATE.strip()
#     )
#     st.session_state["use_custom_skill_gap_prompt"] = (
#         skill_gap_prompt.strip() != DEFAULT_SKILL_GAP_PROMPT_TEMPLATE.strip()
#     )
#
#     st.session_state["active_jd_prompt_template"] = (
#         jd_prompt if jd_prompt.strip() else DEFAULT_JD_PROMPT_TEMPLATE
#     )
#     st.session_state["active_skill_gap_prompt_template"] = (
#         skill_gap_prompt
#         if skill_gap_prompt.strip()
#         else DEFAULT_SKILL_GAP_PROMPT_TEMPLATE
#     )
#
#
# def safe_json_extract(text):
#     cleaned = text.strip()
#     cleaned = cleaned.replace("```json", "")
#     cleaned = cleaned.replace("```", "")
#
#     start = cleaned.find("{")
#
#     if start == -1:
#         return None
#
#     try:
#         decoder = json.JSONDecoder()
#         data, _ = decoder.raw_decode(cleaned[start:])
#         return data
#     except json.JSONDecodeError:
#         return None
#
#
# def safe_ollama_json(prompt, schema, fallback, model_name=None):
#     try:
#         response = ollama.chat(
#             model=model_name or get_selected_model(),
#             format="json",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": (
#                         "You are a JSON API. Return one valid JSON object "
#                         "only. Do not include markdown or explanations."
#                     ),
#                 },
#                 {
#                     "role": "user",
#                     "content": prompt,
#                 }
#             ],
#             options={
#                 "temperature": 0,
#             },
#         )
#
#         result = response["message"]["content"]
#         data = safe_json_extract(result)
#
#         if data is None:
#             st.session_state["last_ollama_error"] = (
#                 "The model did not return valid JSON."
#             )
#             return fallback
#
#         validate(instance=data, schema=schema)
#         st.session_state["last_ollama_error"] = ""
#         return data
#
#     except (KeyError, TypeError, ValidationError, Exception) as error:
#         st.session_state["last_ollama_error"] = str(error)
#         return fallback
#
#
# def format_prompt(template, **values):
#     prompt = template
#     used_placeholder = False
#
#     for key, value in values.items():
#         placeholder = "{" + key + "}"
#
#         if placeholder in prompt:
#             used_placeholder = True
#
#         prompt = prompt.replace(
#             placeholder,
#             str(value),
#         )
#
#     if used_placeholder:
#         return prompt
#
#     return prompt + "\n\n" + "\n\n".join(
#         f"{key.upper()}:\n{value}" for key, value in values.items()
#     )
#
#
# def validate_upload(file):
#     max_size = 10 * 1024 * 1024
#     allowed_extensions = (".pdf", ".docx")
#     file_name = getattr(file, "name", "")
#     lower_name = file_name.lower()
#
#     if not lower_name.endswith(allowed_extensions):
#         return False, "Unsupported file type. Upload PDF or DOCX files only."
#
#     if hasattr(file, "seek"):
#         file.seek(0)
#
#     content = file.read()
#
#     if hasattr(file, "seek"):
#         file.seek(0)
#
#     if len(content) > max_size:
#         return False, "File is too large. Maximum size is 10 MB."
#
#     if lower_name.endswith(".pdf") and not content.startswith(b"%PDF"):
#         return False, "Invalid PDF file."
#
#     if lower_name.endswith(".docx") and not content.startswith(b"PK"):
#         return False, "Invalid DOCX file."
#
#     return True, ""
#
#
# def normalize_skill_list(value):
#     if isinstance(value, dict):
#         value = list(value.values())
#
#     if isinstance(value, str):
#         value = [
#             item.strip(" -•\t")
#             for item in value.replace("\n", ",").split(",")
#         ]
#
#     if not isinstance(value, list):
#         return []
#
#     return [
#         str(item).strip()
#         for item in value
#         if str(item).strip()
#     ][:10]
#
#
# def normalize_key(key):
#     return "".join(
#         character
#         for character in str(key).lower()
#         if character.isalnum()
#     )
#
#
# def flatten_dict(data):
#     if not isinstance(data, dict):
#         return {}
#
#     flattened = {}
#
#     for key, value in data.items():
#         flattened[key] = value
#
#         if isinstance(value, dict):
#             flattened.update(flatten_dict(value))
#
#     return flattened
#
#
# def get_first_present(data, keys, default=None):
#     if not isinstance(data, dict):
#         return default
#
#     flattened = flatten_dict(data)
#     lower_key_map = {
#         str(key).lower(): value
#         for key, value in flattened.items()
#     }
#     normalized_key_map = {
#         normalize_key(key): value
#         for key, value in flattened.items()
#     }
#
#     for key in keys:
#         if key in flattened:
#             return flattened[key]
#
#         value = lower_key_map.get(key.lower())
#
#         if value is not None:
#             return value
#
#         value = normalized_key_map.get(normalize_key(key))
#
#         if value is not None:
#             return value
#
#     return default
#
#
# def display_value(value, default="Not Found"):
#     if isinstance(value, list):
#         values = [
#             str(item).strip()
#             for item in value
#             if str(item).strip()
#         ]
#         return ", ".join(values) if values else default
#
#     if isinstance(value, dict):
#         values = [
#             str(item).strip()
#             for item in value.values()
#             if str(item).strip()
#         ]
#         return ", ".join(values) if values else default
#
#     if value is None:
#         return default
#
#     value = str(value).strip()
#     return value if value else default
#
#
# def show_ollama_warning():
#     error = st.session_state.get("last_ollama_error", "")
#
#     if error:
#         st.warning(
#             "Ollama could not return usable JSON for the selected model: "
#             f"{error}"
#         )
#
#
# # ==================================================
# # EXTRACT TEXT
# # ==================================================
#
# def extract_pdf_text(pdf_file):
#     text = ""
#     reader = PdfReader(pdf_file)
#
#     for page in reader.pages:
#         page_text = page.extract_text()
#
#         if page_text:
#             text += page_text + "\n"
#
#     return text
#
#
# def extract_docx_text(docx_file):
#     document = Document(docx_file)
#     text = ""
#
#     for paragraph in document.paragraphs:
#         text += paragraph.text + "\n"
#
#     return text
#
#
# def extract_text(file):
#     if hasattr(file, "seek"):
#         file.seek(0)
#
#     if file.name.endswith(".pdf"):
#         return extract_pdf_text(file)
#
#     if file.name.endswith(".docx"):
#         return extract_docx_text(file)
#
#     return ""
#
#
# # ==================================================
# # MATCH SCORE
# # ==================================================
#
# def calculate_match_score(resume_text, job_text):
#     embedding_model = load_model()
#
#     resume_embedding = embedding_model.encode(
#         [
#             "Represent this resume for retrieval:" + resume_text,
#         ],
#         normalize_embeddings=True,
#     )
#
#     job_embedding = embedding_model.encode(
#         [
#             "Represent this description for matching:" + job_text,
#         ],
#         normalize_embeddings=True,
#     )
#
#     similarity = cosine_similarity(
#         resume_embedding,
#         job_embedding,
#     )
#
#     score = float(similarity[0][0]) * 100
#     return round(score, 2)
#
#
# # ==================================================
# # AI ANALYSIS
# # ==================================================
#
# def analyze_job_description(job_text, model_name=None, prompt_template=None):
#     prompt = format_prompt(
#         prompt_template or DEFAULT_JD_PROMPT_TEMPLATE,
#         job_text=job_text,
#     )
#
#     data = safe_ollama_json(
#         prompt,
#         JD_RESPONSE_SCHEMA,
#         JD_FALLBACK,
#         model_name=model_name,
#     )
#
#     return {
#         "experience": get_first_present(
#             data,
#             [
#                 "experience",
#                 "years_of_experience",
#                 "years_experience",
#                 "experience_required",
#                 "years_of_experience_required",
#                 "years of experience required",
#                 "required_experience",
#             ],
#             "Not Found",
#         ),
#         "primary_skills": get_first_present(
#             data,
#             [
#                 "primary_skills",
#                 "required_skills",
#                 "skills",
#                 "technical_skills",
#                 "primary skills",
#                 "core_skills",
#                 "must_have_skills",
#             ],
#             "Not Found",
#         ),
#         "secondary_skills": get_first_present(
#             data,
#             [
#                 "secondary_skills",
#                 "preferred_skills",
#                 "nice_to_have_skills",
#                 "additional_skills",
#                 "secondary skills",
#                 "optional_skills",
#             ],
#             "Not Found",
#         ),
#         "education": get_first_present(
#             data,
#             [
#                 "education",
#                 "educational_qualifications",
#                 "qualifications",
#                 "degree",
#                 "educational qualifications",
#                 "education_required",
#             ],
#             "Not Found",
#         ),
#     }
#
#
# def analyze_skill_gap(
#     resume_text,
#     job_text,
#     model_name=None,
#     prompt_template=None,
# ):
#     prompt = format_prompt(
#         prompt_template or DEFAULT_SKILL_GAP_PROMPT_TEMPLATE,
#         resume_text=resume_text,
#         job_text=job_text,
#     )
#
#     data = safe_ollama_json(
#         prompt,
#         SKILL_GAP_SCHEMA,
#         SKILL_GAP_FALLBACK,
#         model_name=model_name,
#     )
#
#     return {
#         "matching_skills": normalize_skill_list(
#             get_first_present(
#                 data,
#                 [
#                     "matching_skills",
#                     "matched_skills",
#                     "present_skills",
#                     "skills_matched",
#                     "matching skills",
#                     "matched skills",
#                     "relevant_skills",
#                 ],
#                 [],
#             ),
#         ),
#         "missing_skills": normalize_skill_list(
#             get_first_present(
#                 data,
#                 [
#                     "missing_skills",
#                     "skill_gaps",
#                     "gaps",
#                     "skills_missing",
#                     "missing skills",
#                     "skill gaps",
#                     "required_missing_skills",
#                 ],
#                 [],
#             ),
#         ),
#     }
#
#
# # ==================================================
# # PROCESS SINGLE RESUME
# # ==================================================
#
# def process_resume(resume_file, job_description):
#     resume_text = extract_text(resume_file)
#     score = calculate_match_score(
#         resume_text,
#         job_description,
#     )
#
#     return {
#         "Resume Name": resume_file.name,
#         "Match Score (%)": score,
#     }
#
#
# # ==================================================
# # UI
# # ==================================================
#
# def render_configuration_page():
#     st.title("Configurations")
#     model_options = get_model_options()
#
#     if st.session_state.get("ollama_model") not in model_options:
#         st.session_state["ollama_model"] = model_options[0]
#
#     st.selectbox(
#         "Ollama model",
#         model_options,
#         key="ollama_model",
#     )
#
#     if model_options == OLLAMA_MODEL_OPTIONS:
#         st.warning(
#             "Could not read installed Ollama models. Showing default options."
#         )
#     else:
#         st.caption(
#             "Showing models installed locally in Ollama."
#         )
#
#     st.text_area(
#         "Job description analysis prompt",
#         key="jd_prompt_template",
#         height=360,
#     )
#
#     st.text_area(
#         "Skill gap analysis prompt",
#         key="skill_gap_prompt_template",
#         height=420,
#     )
#
#     if st.button("Apply prompt changes"):
#         apply_prompt_configuration()
#         st.success("Prompt configuration applied.")
#
#     if st.button("Reset prompts"):
#         st.session_state["jd_prompt_template"] = DEFAULT_JD_PROMPT_TEMPLATE
#         st.session_state[
#             "skill_gap_prompt_template"
#         ] = DEFAULT_SKILL_GAP_PROMPT_TEMPLATE
#         st.session_state["active_jd_prompt_template"] = (
#             DEFAULT_JD_PROMPT_TEMPLATE
#         )
#         st.session_state["active_skill_gap_prompt_template"] = (
#             DEFAULT_SKILL_GAP_PROMPT_TEMPLATE
#         )
#         st.session_state["use_custom_jd_prompt"] = False
#         st.session_state["use_custom_skill_gap_prompt"] = False
#         st.rerun()
#
#     if (
#         st.session_state.get("use_custom_jd_prompt")
#         or st.session_state.get("use_custom_skill_gap_prompt")
#     ):
#         st.caption("Custom prompt changes are active.")
#     else:
#         st.caption("Using default prompts from app.py.")
#
#     st.info(
#         "Prompt variables: {job_text} for JD analysis; "
#         "{resume_text} and {job_text} for skill gap analysis."
#     )
#
#
# def render_analyzer_page():
#     st.title("📄 AI Recruiter Screening System")
#
#     st.write(
#         "Upload multiple resumes and compare them against a Job Description "
#         "using AI."
#     )
#
#     st.caption(
#         f"Active Ollama model: {get_selected_model()}"
#     )
#
#     st.divider()
#
#     uploaded_resumes = st.file_uploader(
#         "Upload Resumes (PDF/DOCX)",
#         type=[
#             "pdf",
#             "docx",
#         ],
#         accept_multiple_files=True,
#         key="resume_uploads",
#     )
#
#     resumes = []
#
#     for resume in uploaded_resumes or []:
#         is_valid, message = validate_upload(resume)
#
#         if is_valid:
#             resumes.append(resume)
#         else:
#             st.warning(f"{resume.name}: {message}")
#
#     job_description = st.text_area(
#         "Paste Job Description",
#         height=250,
#         key="job_description",
#     )
#
#     if resumes and job_description.strip():
#         run_analysis(
#             resumes,
#             job_description,
#             get_selected_model(),
#             get_jd_prompt_template(),
#             get_skill_gap_prompt_template(),
#         )
#
#     st.caption(
#         "Built using Streamlit, Sentence Transformers, Ollama, Pandas and "
#         "Scikit-Learn."
#     )
#
#
# def run_analysis(
#     resumes,
#     job_description,
#     model_name,
#     jd_prompt_template,
#     skill_gap_prompt_template,
# ):
#     st.subheader("Job Description Analysis")
#
#     with st.spinner("Analyzing Job Description..."):
#         jd_info = analyze_job_description(
#             job_description,
#             model_name=model_name,
#             prompt_template=jd_prompt_template,
#         )
#
#     show_ollama_warning()
#
#     jd_df = pd.DataFrame(
#         {
#             "Years of Experience": [
#                 display_value(jd_info.get("experience")),
#             ],
#             "Primary Skills": [
#                 display_value(jd_info.get("primary_skills")),
#             ],
#             "Secondary Skills": [
#                 display_value(jd_info.get("secondary_skills")),
#             ],
#             "Educational Qualifications": [
#                 display_value(jd_info.get("education")),
#             ],
#         }
#     )
#
#     st.table(jd_df)
#     st.divider()
#
#     st.subheader("Candidate Ranking Dashboard")
#
#     results = []
#     good_fit = []
#     moderate_fit = []
#     bad_fit = []
#
#     progress_bar = st.progress(0)
#     total_resumes = len(resumes)
#
#     for index, resume in enumerate(resumes):
#         result = process_resume(
#             resume,
#             job_description,
#         )
#
#         results.append(result)
#         score = result["Match Score (%)"]
#
#         if score >= 70:
#             good_fit.append(result["Resume Name"])
#         elif score >= 50:
#             moderate_fit.append(result["Resume Name"])
#         else:
#             bad_fit.append(result["Resume Name"])
#
#         progress_bar.progress(
#             float(index + 1) / float(total_resumes)
#         )
#
#     ranking_df = pd.DataFrame(results)
#     ranking_df = ranking_df.sort_values(
#         by="Match Score (%)",
#         ascending=False,
#     )
#
#     top_5_names = ranking_df.head(5)["Resume Name"].tolist()
#     ranking_df.index = range(1, len(ranking_df) + 1)
#     ranking_df.index.name = "Rank"
#
#     st.dataframe(
#         ranking_df,
#         use_container_width=True,
#     )
#
#     st.divider()
#     st.subheader("Top 5 Candidate Detailed Analysis")
#
#     render_candidate_details(
#         resumes,
#         top_5_names,
#         ranking_df,
#         job_description,
#         model_name,
#         skill_gap_prompt_template,
#     )
#
#     st.divider()
#     st.subheader("Candidate Categorization")
#     render_candidate_categories(
#         good_fit,
#         moderate_fit,
#         bad_fit,
#     )
#
#
# def render_candidate_details(
#     resumes,
#     top_5_names,
#     ranking_df,
#     job_description,
#     model_name,
#     skill_gap_prompt_template,
# ):
#     for resume in resumes:
#         if resume.name not in top_5_names:
#             continue
#
#         with st.expander(f"📄 {resume.name}"):
#             try:
#                 resume.seek(0)
#                 resume_text = extract_text(resume)
#
#                 score = ranking_df.loc[
#                     ranking_df["Resume Name"] == resume.name,
#                     "Match Score (%)",
#                 ].values[0]
#
#                 skills = analyze_skill_gap(
#                     resume_text,
#                     job_description,
#                     model_name=model_name,
#                     prompt_template=skill_gap_prompt_template,
#                 )
#
#                 show_ollama_warning()
#
#                 st.metric(
#                     "Match Score",
#                     f"{score}%",
#                 )
#
#                 render_skill_table(skills)
#
#                 if score >= 70:
#                     st.success("Strong Match")
#                 elif score >= 50:
#                     st.warning("Moderate Match")
#                 else:
#                     st.error("Low Match")
#
#             except Exception as error:
#                 st.error(f"Error in analysis: {str(error)}")
#
#
# def render_skill_table(skills):
#     if not skills.get("matching_skills") and not skills.get("missing_skills"):
#         skill_df = pd.DataFrame(
#             {
#                 "Matching Skills": ["Not Found"],
#                 "Missing Skills": ["Not Found"],
#             }
#         )
#
#         st.dataframe(
#             skill_df,
#             use_container_width=True,
#         )
#         return
#
#     max_len = max(
#         1,
#         len(skills.get("matching_skills", [])),
#         len(skills.get("missing_skills", [])),
#     )
#
#     matching_skills = skills.get("matching_skills", []) + [
#         "",
#     ] * (max_len - len(skills.get("matching_skills", [])))
#
#     missing_skills = skills.get("missing_skills", []) + [
#         "",
#     ] * (max_len - len(skills.get("missing_skills", [])))
#
#     skill_df = pd.DataFrame(
#         {
#             "Matching Skills": matching_skills,
#             "Missing Skills": missing_skills,
#         }
#     )
#
#     st.dataframe(
#         skill_df,
#         use_container_width=True,
#     )
#
#
# def render_candidate_categories(good_fit, moderate_fit, bad_fit):
#     max_len = max(
#         1,
#         len(good_fit),
#         len(moderate_fit),
#         len(bad_fit),
#     )
#
#     good_fit += [""] * (max_len - len(good_fit))
#     moderate_fit += [""] * (max_len - len(moderate_fit))
#     bad_fit += [""] * (max_len - len(bad_fit))
#
#     classification_df = pd.DataFrame(
#         {
#             "Good Fit": good_fit,
#             "Moderate Fit": moderate_fit,
#             "Bad Fit": bad_fit,
#         }
#     )
#
#     st.dataframe(
#         classification_df,
#         use_container_width=True,
#     )
#
#
# def main():
#     init_configuration_state()
#
#     analyzer_tab, config_tab = st.tabs(
#         [
#             "Resume Analyzer",
#             "Configurations",
#         ],
#     )
#
#     with analyzer_tab:
#         render_analyzer_page()
#
#     with config_tab:
#         render_configuration_page()
#
#
# if __name__ == "__main__":
#     main()

