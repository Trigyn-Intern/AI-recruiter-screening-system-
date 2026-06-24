export const defaultPrompts = {
  jd_prompt_template: `You are an HR Recruitment Expert.

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

JOB DESCRIPTION:

{job_text}
`,

  skill_gap_prompt_template: `You are an ATS and Technical Recruiter.

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

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_text}
`,

  candidate_detail_prompt_template: `You are an ATS and Technical Recruiter.

Compare the candidate profile against the job requirements and explain the
resume-job match score.

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
- No explanations outside JSON.
- No markdown.
- No code blocks.

MATCH SCORE:
{score}%

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_text}
`,

  resume_skill_extraction_prompt_template: `You are an ATS resume parser.

Extract the candidate's skills and role signals from the resume.

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
    "experience_summary": ""
}

Rules:
- Keep each list to a maximum of 15 items.
- Use concise skill names.
- Do not include markdown.
- Do not include text before or after JSON.

RESUME:
{resume_text}
`,
};
