import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronRight,
  Loader2,
  RefreshCw,
  Save,
  Sparkles,
  Wand2,
} from "lucide-react";

const FASTAPI_BASE_URL =
  import.meta.env.VITE_FASTAPI_URL || "";

const PROMPT_KEYS = {
  "jd-analyzer": "jd_prompt_template",
  "skill-gap-analyzer": "skill_gap_prompt_template",
  "candidate-explainer": "candidate_detail_prompt_template",
  "resume-skill-extractor": "resume_skill_extraction_prompt_template",
};

const SAMPLE_INPUTS = {
  "jd-analyzer": {
    job_text:
      "Senior Python developer with FastAPI and PostgreSQL experience. 5+ years required.",
  },
  "skill-gap-analyzer": {
    resume_text:
      "Backend engineer with 4 years building APIs in Python, FastAPI, and PostgreSQL. Light React exposure.",
    job_text:
      "Senior Python developer with FastAPI, PostgreSQL, AWS, and Kubernetes experience. 5+ years required.",
  },
  "candidate-explainer": {
    resume_text:
      "Backend engineer with 4 years building APIs in Python, FastAPI, and PostgreSQL. Light React exposure.",
    job_text:
      "Senior Python developer with FastAPI, PostgreSQL, AWS, and Kubernetes experience. 5+ years required.",
    score: 78,
  },
  "resume-skill-extractor": {
    resume_text:
      "Backend engineer with 4 years building APIs in Python, FastAPI, and PostgreSQL. Light React exposure.",
  },
};

function SkillsPage({ config, setConfig }) {
  const [skills, setSkills] = useState([]);
  const [selectedName, setSelectedName] = useState("");
  const [editedBody, setEditedBody] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [runInputs, setRunInputs] = useState({});
  const [runProvider, setRunProvider] = useState("Ollama");
  const [runResult, setRunResult] = useState(null);

  const selectedSkill = useMemo(
    () => skills.find((skill) => skill.name === selectedName) || null,
    [skills, selectedName],
  );

  const loadSkills = useCallback(async () => {
    setIsLoading(true);
    setError("");

    try {
      const response = await fetch(`${FASTAPI_BASE_URL}/skills`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not load skills.");
      }

      const list = Array.isArray(data.skills) ? data.skills : [];
      setSkills(list);

      if (list.length > 0) {
        const next = selectedName || list[0].name;
        setSelectedName(next);
        const matched =
          config && PROMPT_KEYS[next]
            ? config[PROMPT_KEYS[next]]
            : "";
        setEditedBody(matched || list[0].instructions || "");
        setRunInputs(SAMPLE_INPUTS[next] || {});
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }, [config, selectedName]);

  useEffect(() => {
    loadSkills();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedSkill) return;

    const key = PROMPT_KEYS[selectedSkill.name];
    const fromConfig = key && config ? config[key] : "";
    setEditedBody(fromConfig || selectedSkill.instructions || "");
    setRunInputs(SAMPLE_INPUTS[selectedSkill.name] || {});
    setRunResult(null);
  }, [selectedSkill, config]);

  function updateRunInput(field, value) {
    setRunInputs((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function saveSkill() {
    if (!selectedSkill) return;

    const key = PROMPT_KEYS[selectedSkill.name];
    if (!key) {
      setError(
        `Skill "${selectedSkill.name}" is not bound to a saved prompt template.`,
      );
      return;
    }

    setIsSaving(true);
    setError("");
    setNotice("");

    try {
      const response = await fetch(`${FASTAPI_BASE_URL}/configuration`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...(config || {}),
          [key]: editedBody,
        }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not save skill body.");
      }

      const saved = data.configuration || {};
      setConfig((current) => ({ ...(current || {}), ...saved }));
      setNotice(`Saved ${selectedSkill.name}.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSaving(false);
    }
  }

  function resetSkill() {
    if (!selectedSkill) return;
    setEditedBody(selectedSkill.instructions || "");
    setNotice(`Reset ${selectedSkill.name} to its default instructions.`);
  }

  async function runSkill() {
    if (!selectedSkill) return;

    setIsRunning(true);
    setError("");
    setRunResult(null);

    try {
      const response = await fetch(
        `${FASTAPI_BASE_URL}/skills/${encodeURIComponent(selectedSkill.name)}/run`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            inputs: runInputs,
            provider: runProvider,
          }),
        },
      );
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Skill execution failed.");
      }

      setRunResult(data.result || {});
      setNotice(`Ran ${selectedSkill.name}.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsRunning(false);
    }
  }

  if (isLoading) {
    return (
      <section className="skills-layout">
        <div className="empty-state">Loading skills...</div>
      </section>
    );
  }

  if (skills.length === 0) {
    return (
      <section className="skills-layout">
        <div className="empty-state">
          No Skills found. Add a folder under the repo `skills/` directory with
          a `SKILL.md` and restart the backend.
        </div>
      </section>
    );
  }

  return (
    <section className="skills-layout">
      <aside className="skills-sidebar panel">
        <div className="skills-sidebar-header">
          <Sparkles size={18} />
          <div>
            <h2>Skills</h2>
            <p>Discovered from the `skills/` folder.</p>
          </div>
          <button
            className="secondary skills-refresh"
            type="button"
            onClick={loadSkills}
            title="Reload skills"
          >
            <RefreshCw size={16} />
          </button>
        </div>
        <ul className="skills-list">
          {skills.map((skill) => (
            <li key={skill.name}>
              <button
                type="button"
                className={
                  skill.name === selectedName
                    ? "skill-row active"
                    : "skill-row"
                }
                onClick={() => setSelectedName(skill.name)}
              >
                <div>
                  <strong>{skill.name}</strong>
                  <span>{skill.description || "No description."}</span>
                </div>
                <ChevronRight size={16} />
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="skills-detail panel">
        {selectedSkill ? (
          <>
            <header className="skills-detail-header">
              <div>
                <h2>{selectedSkill.name}</h2>
                <p>{selectedSkill.description}</p>
              </div>
              <div className="skills-detail-meta">
                <span>v{selectedSkill.version}</span>
                <span>
                  Providers: {selectedSkill.provider_compat.join(", ") || "Any"}
                </span>
              </div>
            </header>

            <section className="skills-block">
              <h3>Contract</h3>
              <dl className="skills-contract">
                <div>
                  <dt>Inputs</dt>
                  <dd>
                    {selectedSkill.inputs.length === 0 ? (
                      <em>None</em>
                    ) : (
                      <ul>
                        {selectedSkill.inputs.map((input) => (
                          <li key={input.name}>
                            <code>{input.name}</code>
                            <span>
                              {input.type}
                              {input.required ? " (required)" : ""}
                            </span>
                            <small>{input.description}</small>
                          </li>
                        ))}
                      </ul>
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Outputs</dt>
                  <dd>
                    {selectedSkill.outputs.length === 0 ? (
                      <em>None</em>
                    ) : (
                      <ul>
                        {selectedSkill.outputs.map((output) => (
                          <li key={output.schema || output.type}>
                            <code>{output.schema || output.type}</code>
                            <span>{output.type}</span>
                            <small>{output.description}</small>
                          </li>
                        ))}
                      </ul>
                    )}
                  </dd>
                </div>
              </dl>
            </section>

            <section className="skills-block">
              <div className="skills-block-header">
                <h3>Instructions</h3>
                <div className="skills-block-actions">
                  <button
                    className="secondary"
                    type="button"
                    onClick={resetSkill}
                  >
                    <RefreshCw size={16} />
                    Reset to default
                  </button>
                  <button
                    type="button"
                    onClick={saveSkill}
                    disabled={isSaving}
                  >
                    <Save size={16} />
                    Save
                  </button>
                </div>
              </div>
              <textarea
                className="skills-editor"
                rows={14}
                value={editedBody}
                onChange={(event) => setEditedBody(event.target.value)}
              />
            </section>

            <section className="skills-block">
              <div className="skills-block-header">
                <h3>Run with sample inputs</h3>
                <div className="skills-block-actions">
                  <select
                    value={runProvider}
                    onChange={(event) => setRunProvider(event.target.value)}
                  >
                    <option value="Ollama">Ollama</option>
                    <option value="Gemini">Gemini</option>
                  </select>
                  <button
                    type="button"
                    onClick={runSkill}
                    disabled={isRunning}
                  >
                    {isRunning ? (
                      <Loader2 className="spin" size={16} />
                    ) : (
                      <Wand2 size={16} />
                    )}
                    Run skill
                  </button>
                </div>
              </div>
              <div className="skills-run-inputs">
                {selectedSkill.inputs.length === 0 ? (
                  <em>No inputs required.</em>
                ) : (
                  selectedSkill.inputs.map((input) => (
                    <label key={input.name}>
                      {input.name}
                      <textarea
                        rows={4}
                        value={runInputs[input.name] ?? ""}
                        onChange={(event) =>
                          updateRunInput(input.name, event.target.value)
                        }
                      />
                    </label>
                  ))
                )}
                <label>
                  score
                  <input
                    type="number"
                    value={runInputs.score ?? ""}
                    onChange={(event) =>
                      updateRunInput("score", event.target.value)
                    }
                  />
                </label>
              </div>
              {runResult ? (
                <pre className="skills-run-output">
                  {JSON.stringify(runResult, null, 2)}
                </pre>
              ) : null}
            </section>

            {error ? <div className="error">{error}</div> : null}
            {notice ? <div className="notice">{notice}</div> : null}
          </>
        ) : (
          <div className="empty-state">Select a skill to inspect.</div>
        )}
      </section>
    </section>
  );
}

export default SkillsPage;
