import React, { useEffect, useMemo, useState } from "react";
import {
  Database,
  FileText,
  Loader2,
  RefreshCw,
  Save,
  RotateCcw,
  UploadCloud,
} from "lucide-react";
import {
  defaultGeminiModels,
  defaultOllamaModels,
  defaultProviders,
} from "./defaultModels";
import { defaultPrompts } from "./defaultPrompts";
import "./styles.css";

const API_BASE_URL = "http://127.0.0.1:8000";

const emptyConfig = {
  ai_provider: "Gemini",
  ollama_model: defaultOllamaModels[0],
  gemini_model: defaultGeminiModels[0],
  ...defaultPrompts,
};

function normalizeConfig(config) {
  const normalizedConfig = {
    ...emptyConfig,
    ...(config || {}),
  };

  for (const key of Object.keys(defaultPrompts)) {
    if (!String(normalizedConfig[key] || "").trim()) {
      normalizedConfig[key] = defaultPrompts[key];
    }
  }

  return normalizedConfig;
}

function formatDisplayValue(value, fallback = "Not Found") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  if (Array.isArray(value)) {
    const values = value
      .map((item) => formatDisplayValue(item, ""))
      .filter(Boolean);
    return values.length ? values.join(", ") : fallback;
  }

  if (typeof value === "object") {
    if (value.msg) {
      return value.loc ? `${value.loc.join(".")}: ${value.msg}` : value.msg;
    }

    if (value.message) {
      return value.message;
    }

    return JSON.stringify(value);
  }

  return String(value);
}

function getErrorMessage(data, fallback) {
  return formatDisplayValue(data?.detail || data?.error, fallback);
}

function shortenText(value, fallback = "None", maxLength = 140) {
  const text = formatDisplayValue(value, fallback);
  const upperText = text.toUpperCase();

  if (upperText.includes("429") || upperText.includes("RESOURCE_EXHAUSTED")) {
    return "Gemini quota exhausted; local fallback used.";
  }

  if (upperText.includes("503") || upperText.includes("UNAVAILABLE")) {
    return "Gemini temporarily unavailable; local fallback used.";
  }

  if (upperText.includes("GEMINI_API_KEY")) {
    return "Gemini API key missing; local fallback used.";
  }

  if (text.length <= maxLength) {
    return text;
  }

  return `${text.slice(0, maxLength)}...`;
}

function cleanList(items) {
  if (!Array.isArray(items)) {
    return [];
  }

  return items
    .map((item) => formatDisplayValue(item, ""))
    .filter((item) => item && item.toLowerCase() !== "not found");
}

function isUsableGrading(grading) {
  return Boolean(
    grading &&
      grading.grade &&
      grading.grade !== "Not Found" &&
      grading.summary &&
      grading.summary !== "Candidate grading could not be generated.",
  );
}

function buildDisplayGradingFallback(detail) {
  const matchingSkills = cleanList(detail.matching_skills);
  const missingSkills = cleanList(detail.missing_skills);
  const totalSignals = matchingSkills.length + missingSkills.length;
  const ratio = totalSignals ? matchingSkills.length / totalSignals : 0;
  let grade = "F";

  if (ratio >= 0.8) {
    grade = "A";
  } else if (ratio >= 0.65) {
    grade = "B";
  } else if (ratio >= 0.4) {
    grade = "C";
  } else if (ratio >= 0.2) {
    grade = "D";
  }

  return {
    grade,
    summary:
      `Grade ${grade} is a display fallback based on ` +
      `${matchingSkills.length} matching skill(s) and ` +
      `${missingSkills.length} missing skill(s). ` +
      "It does not use the generated match score.",
    strengths: matchingSkills.length
      ? [`Matches ${matchingSkills.slice(0, 4).join(", ")}.`]
      : ["Resume context is available, but strong matched skills were not returned."],
    concerns: missingSkills.length
      ? [`Missing or unclear skills include ${missingSkills.slice(0, 4).join(", ")}.`]
      : ["No missing skills were returned for this candidate."],
    debug: {
      source: "frontend_display_fallback",
      cache: "n/a",
      final_grade: grade,
      resume_context_chars: "unknown",
      matching_skill_count: matchingSkills.length,
      missing_skill_count: missingSkills.length,
      gemini_error: "Backend grading object was missing or unusable.",
    },
  };
}

function App() {
  const [activePage, setActivePage] = useState("analyzer");
  const [providers, setProviders] = useState(defaultProviders);
  const [ollamaModels, setOllamaModels] = useState(defaultOllamaModels);
  const [geminiModels, setGeminiModels] = useState(defaultGeminiModels);
  const [config, setConfig] = useState(emptyConfig);
  const [provider, setProvider] = useState("Gemini");
  const [model, setModel] = useState(defaultGeminiModels[0]);
  const [detailLimit, setDetailLimit] = useState(5);
  const [jobDescription, setJobDescription] = useState("");
  const [resumes, setResumes] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [codeText, setCodeText] = useState("");
  const [reviewResult, setReviewResult] = useState("");
  const [isReviewLoading, setIsReviewLoading] = useState(false); 
  const [notice, setNotice] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [resumeDb, setResumeDb] = useState({
    records: [],
    total: 0,
    fully_indexed: 0,
    embedding_indexed: 0,
    skills_indexed: 0,
  });
  const [resumeDbError, setResumeDbError] = useState("");
  const [isResumeDbLoading, setIsResumeDbLoading] = useState(false);

  useEffect(() => {
    loadConfiguration();
  }, []);

  useEffect(() => {
    if (activePage === "resume-db") {
      loadResumeDb();
    }
  }, [activePage]);

  const modelOptions = useMemo(() => {
    if (provider === "Gemini") {
      return geminiModels.length ? geminiModels : defaultGeminiModels;
    }

    return ollamaModels.length ? ollamaModels : defaultOllamaModels;
  }, [provider, geminiModels, ollamaModels]);

  useEffect(() => {
    if (modelOptions.length > 0 && !modelOptions.includes(model)) {
      const fallbackModel = modelOptions[0];
      setModel(fallbackModel);
      setConfig((current) => ({
        ...current,
        [provider === "Gemini" ? "gemini_model" : "ollama_model"]:
          fallbackModel,
      }));
    }
  }, [modelOptions, model, provider]);

  async function loadConfiguration() {
    try {
      const response = await fetch(`${API_BASE_URL}/configuration`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, "Could not load configuration."),
        );
      }

      const loadedConfig = normalizeConfig(data.configuration);
      const loadedProviders = data.providers?.length
        ? data.providers
        : defaultProviders;
      const loadedOllamaModels = data.ollama_models?.length
        ? data.ollama_models
        : defaultOllamaModels;
      const loadedGeminiModels = data.gemini_models?.length
        ? data.gemini_models
        : defaultGeminiModels;
      const nextProvider = loadedConfig.ai_provider || defaultProviders[0];
      const nextModelOptions =
        nextProvider === "Ollama"
          ? loadedOllamaModels
          : loadedGeminiModels;
      const configuredModel =
        nextProvider === "Ollama"
          ? loadedConfig.ollama_model
          : loadedConfig.gemini_model;
      const nextModel = nextModelOptions.includes(configuredModel)
        ? configuredModel
        : nextModelOptions[0];

      setProviders(loadedProviders);
      setOllamaModels(loadedOllamaModels);
      setGeminiModels(loadedGeminiModels);
      setConfig(loadedConfig);
      setProvider(nextProvider);
      setModel(nextModel);
    } catch {
      setError("FastAPI server is not reachable.");
    }
  }

  function handleProviderChange(nextProvider) {
    setProvider(nextProvider);
    setConfig((current) => ({
      ...current,
      ai_provider: nextProvider,
    }));
    setModel(
      nextProvider === "Gemini"
        ? config.gemini_model || geminiModels[0] || defaultGeminiModels[0]
        : config.ollama_model || ollamaModels[0] || defaultOllamaModels[0],
    );
  }

  function handleModelChange(nextModel) {
    setModel(nextModel);
    setConfig((current) => ({
      ...current,
      [provider === "Gemini" ? "gemini_model" : "ollama_model"]: nextModel,
    }));
  }

  async function handleAnalyze(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setResult(null);

    if (!jobDescription.trim()) {
      setError("Paste a job description before analyzing.");
      return;
    }

    const formData = new FormData();
    formData.append("job_description", jobDescription);
    formData.append("provider", provider);
    formData.append("model_name", model);
    formData.append("detail_limit", String(detailLimit));

    for (const resume of resumes) {
      formData.append("resumes", resume);
    }

    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(getErrorMessage(data, "Analysis failed."));
      }

      setResult(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleReview() {
    if (!codeText.trim()) {
      alert("Please enter some code to review first!");
      return;
    }
    setIsReviewLoading(true);
    setReviewResult("Review in Progress...");
    try {
      const response = await fetch(`${API_BASE_URL}/api/review`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          code: codeText,
          provider: provider,
          model_name: model,
          background: true,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Review failed.");
      }
      
      const jobId = data.job_id;
      const intervalId = setInterval(async () => {
        try {
          const statusRes = await fetch(`${API_BASE_URL}/api/review/status/${jobId}`);
          const statusData = await statusRes.json();
          if (!statusRes.ok) {
            throw new Error(statusData.detail || "Failed to fetch status.");
          }
          if (statusData.status === "completed") {
            clearInterval(intervalId);
            setReviewResult(statusData.review);
            setIsReviewLoading(false);
          } else if (statusData.status === "failed") {
            clearInterval(intervalId);
            setReviewResult(`Error: ${statusData.error || "Review failed."}`);
            setIsReviewLoading(false);
          }
        } catch (pollErr) {
          clearInterval(intervalId);
          setReviewResult(`Error: ${pollErr.message}`);
          setIsReviewLoading(false);
        }
      }, 3000);
    } catch (err) {
      console.error(err);
      setReviewResult(`Error: ${err.message}`);
      setIsReviewLoading(false);
    }
  }

  async function saveConfiguration(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setIsSaving(true);

    const payload = {
      ...config,
      ai_provider: provider,
      gemini_model: provider === "Gemini" ? model : config.gemini_model,
      ollama_model: provider === "Ollama" ? model : config.ollama_model,
    };

    try {
      const response = await fetch(`${API_BASE_URL}/configuration`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, "Could not save configuration."),
        );
      }

      const savedConfig = normalizeConfig(data.configuration || payload);
      setConfig(savedConfig);
      setProvider(savedConfig.ai_provider);
      setModel(
        savedConfig.ai_provider === "Ollama"
          ? savedConfig.ollama_model
          : savedConfig.gemini_model,
      );
      setNotice("Configuration saved.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSaving(false);
    }
  }

  async function resetConfiguration() {
    setError("");
    setNotice("");
    setIsSaving(true);

    try {
      const response = await fetch(`${API_BASE_URL}/configuration/reset`, {
        method: "POST",
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, "Could not reset configuration."),
        );
      }

      const resetConfig = normalizeConfig(data.configuration);
      setConfig(resetConfig);
      setProvider(resetConfig.ai_provider);
      setModel(
        resetConfig.ai_provider === "Ollama"
          ? resetConfig.ollama_model
          : resetConfig.gemini_model,
      );
      setNotice("Configuration reset.");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSaving(false);
    }
  }

  async function loadResumeDb() {
    setResumeDbError("");
    setIsResumeDbLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/resume-db`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, "Could not load resume database."),
        );
      }

      setResumeDb({
        records: data.records || [],
        total: data.total || 0,
        fully_indexed: data.fully_indexed || 0,
        embedding_indexed: data.embedding_indexed || 0,
        skills_indexed: data.skills_indexed || 0,
      });
    } catch {
      setResumeDbError("FastAPI server is not reachable.");
    } finally {
      setIsResumeDbLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="toolbar">
        <div>
          <h1>Resume Analyzer</h1>
          <p>React frontend with FastAPI analysis backend.</p>
        </div>
        <div className="nav-tabs">
          <button
            className={activePage === "analyzer" ? "tab active" : "tab"}
            onClick={() => setActivePage("analyzer")}
            type="button"
          >
            Analyzer
          </button>
          <button
            className={activePage === "skills" ? "tab active" : "tab"}
            onClick={() => setActivePage("skills")}
            type="button"
          >
            Skills
          </button>
          <button
            className={activePage === "config" ? "tab active" : "tab"}
            onClick={() => setActivePage("config")}
            type="button"
          >
            Configurations
          </button>
          <button
            className={activePage === "resume-db" ? "tab active" : "tab"}
            onClick={() => setActivePage("resume-db")}
            type="button"
          >
            Resume DB
          </button>
          <button
            className={activePage === "code-review" ? "tab active" : "tab"}
            onClick={() => setActivePage("code-review")}
            type="button"
          >
            Code Review
          </button>
        </div>
      </section>

      {activePage === "analyzer" ? (
        <AnalyzerPage
          error={error}
          handleAnalyze={handleAnalyze}
          handleModelChange={handleModelChange}
          handleProviderChange={handleProviderChange}
          isLoading={isLoading}
          detailLimit={detailLimit}
          jobDescription={jobDescription}
          model={model}
          modelOptions={modelOptions}
          notice={notice}
          provider={provider}
          providers={providers}
          result={result}
          resumes={resumes}
          setJobDescription={setJobDescription}
          setDetailLimit={setDetailLimit}
          setResumes={setResumes}
        />
      ) : activePage === "config" ? (
        <ConfigurationPage
          config={config}
          error={error}
          handleModelChange={handleModelChange}
          handleProviderChange={handleProviderChange}
          isSaving={isSaving}
          model={model}
          modelOptions={modelOptions}
          notice={notice}
          provider={provider}
          providers={providers}
          resetConfiguration={resetConfiguration}
          saveConfiguration={saveConfiguration}
          setConfig={setConfig}
        />
      ) : activePage === "code-review" ? (
        <CodeReviewPage
          codeText={codeText}
          setCodeText={setCodeText}
          handleReview={handleReview}
          isReviewLoading={isReviewLoading}
          reviewResult={reviewResult}
        />
      ) : (
        <ResumeDbPage
          error={resumeDbError}
          isLoading={isResumeDbLoading}
          onRefresh={loadResumeDb}
          resumeDb={resumeDb}
        />
      )}
    </main>
  );
}

function AnalyzerPage({
  detailLimit,
  error,
  handleAnalyze,
  handleModelChange,
  handleProviderChange,
  isLoading,
  jobDescription,
  model,
  modelOptions,
  notice,
  provider,
  providers,
  result,
  resumes,
  setDetailLimit,
  setJobDescription,
  setResumes,
}) {
  return (
    <form className="workspace" onSubmit={handleAnalyze}>
      <section className="panel input-panel">
        <div className="controls stacked">
          <label>
            Provider
            <select
              value={provider}
              onChange={(event) => handleProviderChange(event.target.value)}
            >
              {providers.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Model
            <select value={model} onChange={(event) => handleModelChange(event.target.value)}>
              {modelOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Detailed Analysis
            <select
              value={detailLimit}
              onChange={(event) => setDetailLimit(Number(event.target.value))}
            >
              {[3, 5, 10, 15, 20].map((item) => (
                <option key={item} value={item}>
                  Top {item}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="upload-zone">
          <UploadCloud size={24} />
          <span>
            {resumes.length
              ? `${resumes.length} resume${resumes.length === 1 ? "" : "s"} selected`
              : "Optional: add new resumes"}
          </span>
          <input
            multiple
            type="file"
            accept=".pdf,.docx"
            onChange={(event) => setResumes([...event.target.files])}
          />
        </label>

        <div className="file-list">
          {resumes.map((resume) => (
            <div className="file-row" key={resume.name}>
              <FileText size={16} />
              <span>{resume.name}</span>
            </div>
          ))}
        </div>

        <label className="jd-input">
          Job Description
          <textarea
            value={jobDescription}
            onChange={(event) => setJobDescription(event.target.value)}
            rows={12}
          />
        </label>

        <button disabled={isLoading} type="submit">
          {isLoading ? <Loader2 className="spin" size={18} /> : null}
          Analyze
        </button>

        <StatusMessages error={error} notice={notice} />
      </section>

      <section className="panel results-panel">
        {!result ? (
          <div className="empty-state">Results appear after analysis.</div>
        ) : (
          <Results result={result} />
        )}
      </section>
    </form>
  );
}

function ConfigurationPage({
  config,
  error,
  handleModelChange,
  handleProviderChange,
  isSaving,
  model,
  modelOptions,
  notice,
  provider,
  providers,
  resetConfiguration,
  saveConfiguration,
  setConfig,
}) {
  function updatePrompt(key, value) {
    setConfig((current) => ({
      ...current,
      [key]: value,
    }));
  }

  return (
    <form className="config-layout" onSubmit={saveConfiguration}>
      <section className="panel config-panel">
        <div className="config-header">
          <div>
            <h2>Configurations</h2>
            <p>Saved settings apply to future analysis runs.</p>
          </div>
          <div className="config-actions">
            <button disabled={isSaving} type="submit">
              <Save size={18} />
              Save
            </button>
            <button
              className="secondary"
              disabled={isSaving}
              onClick={resetConfiguration}
              type="button"
            >
              <RotateCcw size={18} />
              Reset
            </button>
          </div>
        </div>

        <div className="config-grid">
          <label>
            Default Provider
            <select
              value={provider}
              onChange={(event) => handleProviderChange(event.target.value)}
            >
              {providers.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Default Model
            <select value={model} onChange={(event) => handleModelChange(event.target.value)}>
              {modelOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>

        <PromptEditor
          label="Job Description Analysis Prompt"
          value={config.jd_prompt_template}
          onChange={(value) => updatePrompt("jd_prompt_template", value)}
        />
        <PromptEditor
          label="Skill Gap Prompt"
          value={config.skill_gap_prompt_template}
          onChange={(value) => updatePrompt("skill_gap_prompt_template", value)}
        />
        <PromptEditor
          label="Candidate Detail Prompt"
          value={config.candidate_detail_prompt_template}
          onChange={(value) =>
            updatePrompt("candidate_detail_prompt_template", value)
          }
        />
        <PromptEditor
          label="Candidate Grading Prompt"
          value={config.candidate_grading_prompt_template}
          onChange={(value) =>
            updatePrompt("candidate_grading_prompt_template", value)
          }
        />
        <PromptEditor
          label="Resume Skill Extraction Prompt"
          value={config.resume_skill_extraction_prompt_template}
          onChange={(value) =>
            updatePrompt("resume_skill_extraction_prompt_template", value)
          }
        />

        <StatusMessages error={error} notice={notice} />
      </section>
    </form>
  );
}

function PromptEditor({ label, value, onChange }) {
  return (
    <label className="prompt-editor">
      {label}
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={12}
      />
    </label>
  );
}

function ResumeDbPage({ error, isLoading, onRefresh, resumeDb }) {
  return (
    <section className="resume-db-layout">
      <div className="panel resume-db-panel">
        <div className="config-header">
          <div>
            <h2>Resume DB</h2>
            <p>Indexed resumes from the project vector store.</p>
          </div>
          <button
            className="secondary"
            disabled={isLoading}
            onClick={onRefresh}
            type="button"
          >
            {isLoading ? (
              <Loader2 className="spin" size={18} />
            ) : (
              <RefreshCw size={18} />
            )}
            Refresh
          </button>
        </div>

        {error ? <div className="error">{error}</div> : null}

        <div className="db-summary">
          <SummaryTile label="Total Resumes" value={resumeDb.total} />
          <SummaryTile label="Fully Indexed" value={resumeDb.fully_indexed} />
          <SummaryTile
            label="Embeddings"
            value={resumeDb.embedding_indexed}
          />
          <SummaryTile label="Skills" value={resumeDb.skills_indexed} />
        </div>

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Resume</th>
                <th>Status</th>
                <th>Embedding</th>
                <th>Skills</th>
                <th>FAISS Row</th>
                <th>Models</th>
              </tr>
            </thead>
            <tbody>
              {resumeDb.records.length ? (
                resumeDb.records.map((record) => (
                  <tr key={record.resume_id}>
                    <td>
                      <div className="resume-name-cell">
                        <Database size={16} />
                        <span>{record.resume_name}</span>
                      </div>
                    </td>
                    <td>
                      <StatusPill
                        active={
                          record.embedding_indexed && record.skills_indexed
                        }
                        label={record.status}
                      />
                    </td>
                    <td>
                      <StatusPill
                        active={record.embedding_indexed}
                        label={record.embedding_indexed ? "Indexed" : "Missing"}
                      />
                    </td>
                    <td>
                      <StatusPill
                        active={record.skills_indexed}
                        label={
                          record.skills_indexed
                            ? `${record.skill_count} skills`
                            : "Missing"
                        }
                      />
                    </td>
                    <td>{record.faiss_row ?? "Not Found"}</td>
                    <td>
                      <div className="model-cell">
                        <span>{record.embedding_model || "Not Found"}</span>
                        <span>{record.skills_model || "Not Found"}</span>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6">
                    <div className="empty-table-state">
                      {isLoading
                        ? "Loading resumes..."
                        : "No indexed resumes found."}
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function SummaryTile({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusPill({ active, label }) {
  return (
    <span className={active ? "status-pill good" : "status-pill missing"}>
      {label}
    </span>
  );
}

function StatusMessages({ error, notice }) {
  return (
    <>
      {error ? <div className="error">{error}</div> : null}
      {notice ? <div className="notice">{notice}</div> : null}
    </>
  );
}

function Results({ result }) {
  const runtimeStatus = result.runtime_status || {};
  const [selectedDetail, setSelectedDetail] = useState(null);
  const detailMap = useMemo(() => {
    return new Map(
      (result.top_details || []).map((detail) => [detail.resume_id, detail]),
    );
  }, [result.top_details]);

  return (
    <div className="results-stack">
      {runtimeStatus.last_ai_error ? (
        <div className="error">
          AI analysis warning: {formatDisplayValue(runtimeStatus.last_ai_error)}
        </div>
      ) : null}

      {runtimeStatus.last_vector_store_error ? (
        <div className="error">
          Vector store warning:{" "}
          {formatDisplayValue(runtimeStatus.last_vector_store_error)}
        </div>
      ) : null}

      {Array.isArray(runtimeStatus.grading_checkpoints) &&
      runtimeStatus.grading_checkpoints.length ? (
        <section className="diagnostics-panel">
          <h2>Grading Checkpoints</h2>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Resume</th>
                  <th>Source</th>
                  <th>Cache</th>
                  <th>Final Grade</th>
                  <th>Input</th>
                  <th>Gemini Error</th>
                </tr>
              </thead>
              <tbody>
                {runtimeStatus.grading_checkpoints.map((checkpoint, index) => (
                  <tr key={`${checkpoint.resume_name || "resume"}-${index}`}>
                    <td>{formatDisplayValue(checkpoint.resume_name)}</td>
                    <td>{formatDisplayValue(checkpoint.source)}</td>
                    <td>{formatDisplayValue(checkpoint.cache)}</td>
                    <td>{formatDisplayValue(checkpoint.final_grade)}</td>
                    <td>
                      {formatDisplayValue(checkpoint.resume_context_chars)} chars,
                      {` ${formatDisplayValue(checkpoint.matching_skill_count)} matching, `}
                      {`${formatDisplayValue(checkpoint.missing_skill_count)} missing`}
                    </td>
                    <td className="diagnostic-error">
                      {shortenText(checkpoint.gemini_error, "None")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section>
        <h2>Job Description</h2>
        <div className="jd-grid">
          {Object.entries(result.job_description).map(([key, value]) => (
            <div key={key}>
              <span>{key.replaceAll("_", " ")}</span>
              <strong>{formatDisplayValue(value)}</strong>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2>Ranking</h2>
        <table>
          <thead>
            <tr>
              <th>Resume</th>
              <th>Score</th>
              <th>Fit</th>
              <th>Detailed Analysis</th>
            </tr>
          </thead>
          <tbody>
            {result.ranking.map((row) => {
              const detail = detailMap.get(row.resume_id);

              return (
                <tr key={row.resume_id}>
                  <td>{row.resume_name}</td>
                  <td>{row.match_score}%</td>
                  <td>{row.fit}</td>
                  <td>
                    {detail ? (
                      <button
                        className="table-action"
                        onClick={() => setSelectedDetail(detail)}
                        type="button"
                      >
                        View
                      </button>
                    ) : (
                      <span className="muted-text">Not available</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {selectedDetail ? (
        <DetailModal
          detail={selectedDetail}
          onClose={() => setSelectedDetail(null)}
        />
      ) : null}
    </div>
  );
}

function DetailModal({ detail, onClose }) {
  const evidence = Array.isArray(detail.matching_evidence)
    ? detail.matching_evidence
    : [];
  const grading = isUsableGrading(detail.candidate_grading)
    ? detail.candidate_grading
    : buildDisplayGradingFallback(detail);
  const gradingDebug = grading.debug || {};
  const [showEvidence, setShowEvidence] = useState(false);

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="detail-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="detail-header">
          <div>
            <h2 id="detail-modal-title">
              {formatDisplayValue(detail.resume_name)}
            </h2>
            <span>{formatDisplayValue(detail.match_score)}% match</span>
          </div>
          <button className="secondary modal-close" onClick={onClose} type="button">
            Close
          </button>
        </div>
        <p>{formatDisplayValue(detail.justification)}</p>
        <div className="grading-panel">
          <div className="grade-mark">
            {formatDisplayValue(grading.grade, "Not Found")}
          </div>
          <div>
            <span>Candidate Grade</span>
            <p>{formatDisplayValue(grading.summary)}</p>
          </div>
        </div>
        <div className="skills modal-skills-grid grading-grid">
          <SkillColumn title="Strengths" items={grading.strengths} />
          <SkillColumn title="Concerns" items={grading.concerns} />
        </div>
        {Object.keys(gradingDebug).length ? (
          <div className="debug-panel">
            <span>Grading Debug</span>
            <p>
              Source: {formatDisplayValue(gradingDebug.source)} | Cache:{" "}
              {formatDisplayValue(gradingDebug.cache)} | Final grade:{" "}
              {formatDisplayValue(gradingDebug.final_grade)}
            </p>
            <p>
              Resume context:{" "}
              {formatDisplayValue(gradingDebug.resume_context_chars)} chars |
              Matching: {formatDisplayValue(gradingDebug.matching_skill_count)} |
              Missing: {formatDisplayValue(gradingDebug.missing_skill_count)}
            </p>
            <p>
              Gemini error: {shortenText(gradingDebug.gemini_error, "None")}
            </p>
          </div>
        ) : null}
        {evidence.length ? (
          <div className="evidence-summary">
            <div>
              <span>Matching Evidence</span>
              <p>{evidence.length} evidence-backed skill notes available.</p>
            </div>
            <button
              className="secondary"
              onClick={() => setShowEvidence(true)}
              type="button"
            >
              View evidence
            </button>
          </div>
        ) : null}
        <div className="skills modal-skills-grid">
          <SkillColumn title="Matching" items={detail.matching_skills} />
          <SkillColumn title="Missing" items={detail.missing_skills} />
        </div>
        {showEvidence ? (
          <EvidenceModal
            evidence={evidence}
            resumeName={detail.resume_name}
            onClose={() => setShowEvidence(false)}
          />
        ) : null}
      </section>
    </div>
  );
}

function EvidenceModal({ evidence, resumeName, onClose }) {
  const safeEvidence = Array.isArray(evidence) ? evidence : [];

  return (
    <div
      className="modal-backdrop nested-modal-backdrop"
      role="presentation"
      onClick={(event) => {
        event.stopPropagation();
        onClose();
      }}
    >
      <section
        className="detail-modal evidence-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="detail-header">
          <div>
            <h2 id="evidence-modal-title">Matching Evidence</h2>
            <span>{formatDisplayValue(resumeName)}</span>
          </div>
          <button className="secondary modal-close" onClick={onClose} type="button">
            Close
          </button>
        </div>
        <div className="evidence-list">
          {safeEvidence.map((item, index) => (
            <article
              className="evidence-item"
              key={`${formatDisplayValue(item.skill)}-${index}`}
            >
              <strong>{formatDisplayValue(item.skill)}</strong>
              <p>{formatDisplayValue(item.evidence)}</p>
              {item.source ? (
                <small>{formatDisplayValue(item.source)}</small>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function SkillColumn({ title, items }) {
  const safeItems = Array.isArray(items) ? items : [];

  return (
    <div>
      <span>{title}</span>
      <ul>
        {(safeItems.length ? safeItems : ["Not Found"]).map((item, index) => (
          <li key={`${formatDisplayValue(item)}-${index}`}>
            {formatDisplayValue(item)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CodeReviewPage({
  codeText,
  setCodeText,
  handleReview,
  isReviewLoading,
  reviewResult,
}) {
  return (
    <section className="config-layout">
      <div className="panel config-panel">
        <div className="config-header">
          <div>
            <h2>Code & Security Review</h2>
            <p>Paste your source code to run automated AI code and security reviews based on your team policies.</p>
          </div>
        </div>
        <div className="config-form" style={{ marginTop: "16px" }}>
          <div className="input-group">
            <textarea
              className="prompt-textarea"
              style={{
                fontFamily: "Courier New, monospace",
                fontSize: "14px",
                minHeight: "350px",
                width: "100%",
                padding: "12px",
                borderRadius: "6px",
                border: "1px solid #ccc",
                boxSizing: "border-box"
              }}
              placeholder="Paste your source code here..."
              value={codeText}
              onChange={(e) => setCodeText(e.target.value)}
            />
          </div>
          <div className="actions" style={{ marginTop: "16px" }}>
            <button
              className="primary"
              disabled={isReviewLoading}
              onClick={handleReview}
              type="button"
            >
              {isReviewLoading ? (
                <>
                  <Loader2 className="spin" size={18} />
                  Reviewing...
                </>
              ) : (
                "Run Review"
              )}
            </button>
          </div>
        </div>
      </div>
      {reviewResult && (
        <div className="panel response-panel" style={{ marginTop: "24px" }}>
          <h3>Review Summary</h3>
          <div style={{
            backgroundColor: "#fafafa",
            border: "1px solid #ddd",
            padding: "16px",
            borderRadius: "6px",
            whiteSpace: "pre-wrap",
            fontFamily: "sans-serif",
            marginTop: "12px"
          }}>
            {reviewResult}
          </div>
        </div>
      )}
    </section>
  );
}

export default App;


import SkillsPage from "./pages/dashboard/SkillsPage";
