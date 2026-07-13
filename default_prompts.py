DEFAULT_JD_PROMPT_TEMPLATE = """You are an HR Recruitment Expert.

Read the Job Description carefully.

Extract:

1. Years of Experience Required
2. Primary Skills
3. Secondary Skills
4. Educational Qualifications

Return ONLY valid JSON.

Format:

{
    "experience": "",
    "primary_skills": "",
    "secondary_skills": "",
    "education": ""
}

Rules:
- Return only the keys shown above.
- Do not add extra fields unless the backend schema is updated to support them.

JOB DESCRIPTION:

{job_text}
"""

DEFAULT_SKILL_GAP_PROMPT_TEMPLATE = """You are an ATS and Technical Recruiter.

Compare the candidate profile against the job requirements.

Return ONLY valid JSON.

Format:

{
    "matching_skills": [
        "skill1",
        "skill2"
    ],
    "missing_skills": [
        "skill1",
        "skill2"
    ]
}

Rules:
- Maximum 10 matching skills.
- Maximum 10 missing skills.
- No explanations.
- No markdown.
- No code blocks.
- No text before or after JSON.
- Return only the keys shown in the JSON format.
- Do not add extra fields unless the backend schema is updated to support them.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_text}
"""

DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE = """You are an ATS and Technical Recruiter.

Compare the provided candidate resume context against the job requirements and
explain the resume-job match score.

Return ONLY valid JSON.

Format:

{
    "matching_skills": [
        "skill1",
        "skill2"
    ],
    "missing_skills": [
        "skill1",
        "skill2"
    ],
    "justification": ""
}

Rules:
- Maximum 10 matching skills.
- Maximum 10 missing skills.
- Write the justification in 2 to 3 short lines.
- Mention the strongest matching evidence.
- Mention the most important gaps if any.
- The RESUME section below is the candidate resume context. It may contain raw
  resume text, indexed resume JSON, or both.
- Never say that no resume was provided when the RESUME section has content.
- No explanations outside JSON.
- No markdown.
- No code blocks.
- Return only the keys shown in the JSON format.
- Do not add extra fields unless the backend schema is updated to support them.

MATCH SCORE:
{score}%

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_text}
"""

DEFAULT_CANDIDATE_GRADING_PROMPT_TEMPLATE = """You are a senior technical recruiter.

Grade the candidate's fit for the job using only these weighted criteria:

1. Skill gap: {skill_gap_weight}%
2. Years of experience: {years_experience_weight}%
3. Hands-on project experience: {project_experience_weight}%
4. Educational qualification: {education_weight}%
5. Seniority: {seniority_weight}%

Return ONLY valid JSON.

Format:

{
    "grade_percentage": 0,
    "criteria_scores": {
        "skill_gap": 0,
        "years_experience": 0,
        "project_experience": 0,
        "education": 0,
        "seniority": 0
    },
    "summary": "",
    "strengths": [
        "strength1",
        "strength2"
    ],
    "concerns": [
        "concern1",
        "concern2"
    ]
}

Rules:
- Do not use or mention the existing match score.
- Score each item inside criteria_scores from 0 to 100.
- Calculate the final weighted grade_percentage yourself using
  criteria_scores and GRADING WEIGHTS.
- grade_percentage must change when GRADING WEIGHTS change, even if the same
  resume and job description are used.
- Skill gap means the balance of matching skills versus missing skills, with
  extra importance for mandatory or repeated job-description skills.
- Years of experience means whether the resume shows enough relevant total and
  role-specific experience for the job description.
- Hands-on project experience means whether the resume proves practical project
  usage of the important skills through implementations, products, client work,
  responsibilities, or measurable outcomes.
- Educational qualification means whether the resume's degrees,
  certifications, or formal education satisfy explicit or implied
  job-description education requirements.
- Seniority means whether role titles, responsibility level, leadership scope,
  and years of experience align with the job's expected seniority.
- Do not grade based on domain fit, location, education, company brand, role
  seniority, or general presentation unless that evidence directly supports one
  of the weighted criteria above.
- 90 to 100 means excellent fit with strong evidence across required skills,
  relevant experience, and hands-on project usage.
- 75 to 89 means strong fit with a few manageable gaps.
- 55 to 74 means partial fit with meaningful missing skills or unclear hands-on
  evidence.
- 35 to 54 means weak fit with major required-skill or experience gaps.
- 0 to 34 means very low fit with little relevant evidence for the job.
- Write the summary in 2 to 3 short lines.
- Use strengths for evidence-backed positives.
- Use concerns for missing skills, weak experience, or unclear project evidence.
- No explanations outside JSON.
- No markdown.
- No code blocks.
- Return only the keys shown in the JSON format.
- Do not add extra fields unless the backend schema is updated to support them.

RESUME CONTEXT:
{resume_text}

JOB DESCRIPTION:
{job_text}

MATCHING SKILLS:
{matching_skills}

MISSING SKILLS:
{missing_skills}

GRADING WEIGHTS:
{grading_weights}
"""

DEFAULT_EXPERIENCE_TIMELINE_PROMPT_TEMPLATE = """You are a senior ATS resume parser and technical recruiter.

Extract the candidate's professional experience timeline from the resume with
high accuracy. Focus only on work experience, internships, apprenticeships,
freelance/contract roles, and clearly dated project-based professional work.

Return ONLY valid JSON.

Format:

{
    "total_experience": "",
    "timeline": [
        {
            "role": "",
            "company": "",
            "start_date": "",
            "end_date": "",
            "duration": "",
            "location": "",
            "summary": "",
            "technologies": [
                "technology1",
                "technology2"
            ],
            "projects": [
                "project or product name"
            ],
            "relevance": ""
        }
    ]
}

Rules:
- Read the full resume before deciding the timeline.
- Sort timeline entries from most recent to oldest.
- Extract a maximum of 8 timeline entries.
- Use the role/title exactly as written when possible.
- Use the company/client/organization exactly as written when possible.
- start_date and end_date must preserve the resume wording, such as
  "Jan 2022", "2021", "Present", or "Not Found".
- duration should be calculated only when dates are clear. Otherwise return
  "Not Found".
- summary must be 1 concise sentence describing the candidate's work in that
  role using evidence from the resume.
- technologies must include only tools, programming languages, platforms,
  frameworks, methods, or domain systems explicitly connected to that role.
- projects must include only project/product names explicitly connected to
  that role. Return an empty list if none are clear.
- relevance must explain in 1 short sentence how this role supports or does
  not support the job description.
- Do not invent dates, companies, roles, skills, projects, or responsibilities.
- If the resume has no clear dated experience, return total_experience as
  "Not Found" and timeline as an empty list.
- No markdown.
- No code blocks.
- No text before or after JSON.
- Return only the keys shown in the JSON format.
- Do not add extra fields unless the backend schema is updated to support them.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_text}
"""

DEFAULT_CANDIDATE_SNAPSHOT_PROMPT_TEMPLATE = """You are a senior ATS resume parser and recruiter.

Extract a concise candidate snapshot from the resume. The snapshot will appear
at the top of a recruiter-facing detailed analysis page, so prefer short,
high-confidence values that help identify the candidate quickly.

Return ONLY valid JSON.

Format:

{
    "candidate_name": "",
    "likely_role": "",
    "current_title": "",
    "current_company": "",
    "location": "",
    "total_experience": ""
}

Rules:
- Use only information explicitly present in the resume.
- candidate_name should be the person's name if it is clearly visible near the
  top/header of the resume. If unclear, return "Not Found".
- likely_role should summarize the candidate's professional identity using
  the strongest repeated role signals, such as "Senior Business Consultant",
  "Frontend Developer", or "Data Analyst".
- current_title and current_company should come from the most recent role or
  current employment entry. If dates are unclear, use the first clearly listed
  professional role/company.
- location should be the candidate's city/state/country if clearly present.
- total_experience should preserve explicit wording such as "8+ years" or
  "14 years". If not explicit, infer only when the resume dates are clear;
  otherwise return "Not Found".
- Keep every field concise. Do not write paragraphs.
- Do not invent names, companies, locations, dates, or experience.
- No markdown.
- No code blocks.
- No text before or after JSON.
- Return only the keys shown in the JSON format.
- Do not add extra fields unless the backend schema is updated to support them.

RESUME:
{resume_text}
"""

DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE = """You are an ATS resume parser.

Extract the candidate's skills, role signals, and evidence from the resume.

Return ONLY valid JSON.

Format:

{
    "technical_skills": [
        "skill1",
        "skill2"
    ],
    "soft_skills": [
        "skill1",
        "skill2"
    ],
    "tools": [
        "tool1",
        "tool2"
    ],
    "domains": [
        "domain1",
        "domain2"
    ],
    "experience_summary": "",
    "skill_evidence": [
        {
            "skill": "skill name",
            "evidence": "exact resume phrase, sentence, or project line",
            "source": "project, role, company, or section name if available"
        }
    ]
}

Rules:
- Keep each list to a maximum of 15 items.
- skill_evidence is optional. Include up to 10 evidence-backed skills when
  the resume has clear evidence, otherwise return an empty list.
- evidence must be copied or closely paraphrased from the resume, not invented.
- If a field is not found, return an empty list or "Not Found".
- Use concise skill names.
- Do not include markdown.
- Do not include text before or after JSON.
- Return only the keys shown in the JSON format.
- Do not add extra fields unless the backend schema is updated to support them.

RESUME:
{resume_text}
"""
