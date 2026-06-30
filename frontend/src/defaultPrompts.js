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

MATCH SCORE:
{score}%

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_text}
`,

  candidate_grading_prompt_template: `You are a senior technical recruiter.

Grade the candidate's fit for the job using only the resume context, matching
skills, missing skills, years of experience, hands-on project evidence, domain
fit, and role seniority signals.

Return ONLY valid JSON.

Format:

{
    "grade": "A | B | C | D | F",
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
- Do not calculate a percentage score.
- Grade A only for strong evidence across required skills, relevant experience,
  and hands-on project usage.
- Grade B for mostly strong fit with a few manageable gaps.
- Grade C for partial fit with meaningful missing skills or unclear hands-on
  evidence.
- Grade D for weak fit with major required-skill or experience gaps.
- Grade F only when the resume has almost no relevant evidence for the job.
- Write the summary in 2 to 3 short lines.
- Use strengths for evidence-backed positives.
- Use concerns for missing skills, weak experience, or unclear project evidence.
- No explanations outside JSON.
- No markdown.
- No code blocks.

RESUME CONTEXT:
{resume_text}

JOB DESCRIPTION:
{job_text}

MATCHING SKILLS:
{matching_skills}

MISSING SKILLS:
{missing_skills}
`,

  resume_skill_extraction_prompt_template: `You are an ATS resume parser.

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

RESUME:
{resume_text}
`,
};
