// Sample fixtures so the testing dashboard has data on first run.
// Add to / edit these inline via the UI; they are persisted to
// localStorage under the "testing.fixtures" key.

export const SAMPLE_FIXTURES = [
  {
    id: "fx-strong-match",
    label: "Strong match (Python / FastAPI)",
    job: "Senior Python developer with FastAPI and PostgreSQL experience. 5+ years required.",
    resume: "Backend engineer with 6 years building APIs in Python, FastAPI, and PostgreSQL. Owned the payments service.",
  },
  {
    id: "fx-weak-match",
    label: "Weak match (Java, not Python)",
    job: "Senior Python developer with FastAPI and PostgreSQL experience. 5+ years required.",
    resume: "Java backend developer with Spring Boot and Oracle. 4 years of experience.",
  },
  {
    id: "fx-partial-match",
    label: "Partial match (Python, no FastAPI)",
    job: "Senior Python developer with FastAPI and PostgreSQL experience. 5+ years required.",
    resume: "Python developer with 3 years on Django and MySQL. Comfortable with REST APIs.",
  },
];
