import React, { useEffect, useMemo, useState } from "react";
import {
  Database,
  FileText,
  Loader2,
  RefreshCw,
  Save,
  RotateCcw,
  UploadCloud,
  Settings,
  Lightbulb,
  FileCheck,
  User,
  Shield,
  Users,
  ArrowLeft,
  Trash2,
  Briefcase,
  Award,
  ClipboardList,
  Sparkles,
} from "lucide-react";
import {
  defaultGeminiModels,
  defaultOllamaModels,
  defaultProviders,
} from "./defaultModels";
import { defaultPrompts } from "./defaultPrompts";
import SkillsPage from "./pages/dashboard/SkillsPage";
import AssessmentManagementPage from "./pages/dashboard/AssessmentManagementPage";
import { createOrUpdateAssessment } from "./utils/assessmentStore";
import "./styles.css";

const API_BASE_URL = "http://127.0.0.1:8000";

const emptyConfig = {
  ai_provider: "Ollama",
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
  const [provider, setProvider] = useState("Ollama");
  const [model, setModel] = useState(defaultOllamaModels[0]);
  const [detailLimit, setDetailLimit] = useState(5);
  const [jobDescription, setJobDescription] = useState("");
  const [resumes, setResumes] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
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
  const [analysisSessionId, setAnalysisSessionId] = useState(null);

  // Persist analysis state to localStorage
  useEffect(() => {
    if (result) {
      const sessionData = {
        result,
        timestamp: Date.now()
      };
      localStorage.setItem('currentAnalysisSession', JSON.stringify(sessionData));
      setAnalysisSessionId(Date.now().toString());
    }
  }, [result]);

  // Restore analysis state on mount
  useEffect(() => {
    const savedSession = localStorage.getItem('currentAnalysisSession');
    if (savedSession) {
      try {
        const sessionData = JSON.parse(savedSession);
        // Only restore if it's from the same browser session (recent)
        if (Date.now() - sessionData.timestamp < 24 * 60 * 60 * 1000) { // 24 hours
          setResult(sessionData.result);
          setAnalysisSessionId(sessionData.timestamp.toString());
        }
      } catch (err) {
        console.error('Failed to restore analysis session:', err);
      }
    }
  }, []);

  // Clear persisted state when analysis inputs change
  const invalidateAnalysis = () => {
    localStorage.removeItem('currentAnalysisSession');
    localStorage.removeItem('comparisonResults');
    setAnalysisSessionId(null);
  };

  // Input change handlers that invalidate analysis
  const handleJobDescriptionChange = (value) => {
    setJobDescription(value);
    invalidateAnalysis();
  };

  const handleProviderChangeInvalidate = (nextProvider) => {
    handleProviderChange(nextProvider);
    invalidateAnalysis();
  };

  const handleModelChangeInvalidate = (nextModel) => {
    setModel(nextModel);
    invalidateAnalysis();
  };

  const handleResumesChange = (newResumes) => {
    setResumes(newResumes);
    invalidateAnalysis();
  };

  const handleDetailLimitChange = (value) => {
    setDetailLimit(value);
    invalidateAnalysis();
  };

  useEffect(() => {
    loadConfiguration();
    // Do not automatically load previous analysis session on mount
    // The dashboard should start fresh without displaying old results
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

      setProviders(loadedProviders);
      setOllamaModels(loadedOllamaModels);
      setGeminiModels(loadedGeminiModels);
      setConfig(loadedConfig);
      // Do not override provider/model from saved config on fresh mount
      // Use default initial values: provider="Ollama", model="llama3.2"
    } catch {
      setError("FastAPI server is not reachable.");
    }
  }

  async function loadAnalysisSession() {
    try {
      const response = await fetch(`${API_BASE_URL}/session`);
      const data = await response.json();

      // Do not restore inputs (resumes, jobDescription, provider, model) on fresh mount
      // Only restore the result if available for viewing previous analysis
      if (response.ok && data.session && data.session.result) {
        setResult(data.session.result);
      }
    } catch (error) {
      console.error("Failed to load analysis session:", error);
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
      const rawText = await response.text();
      let data = null;

      if (rawText.trim()) {
        try {
          data = JSON.parse(rawText);
        } catch {
          data = null;
        }
      }

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data, response.statusText || `Analysis failed (${response.status}).`),
        );
      }

      if (!data) {
        throw new Error("Analysis completed without a response body.");
      }

      setResult(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  async function loadResumeDb() {
    setIsResumeDbLoading(true);
    setResumeDbError("");

    try {
      const response = await fetch(`${API_BASE_URL}/resume-db`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to load resume database");
      }

      setResumeDb(data);
    } catch (err) {
      setResumeDbError(err.message);
    } finally {
      setIsResumeDbLoading(false);
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
      <aside className="sidebar">
        <div className="sidebar-logo">
          <Database size={24} />
          Resume Analyzer
        </div>
        <div className="sidebar-subtitle">
          AI-Powered Screening System
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-title">MAIN</div>
          <nav className="sidebar-nav">
            <button
              className={`sidebar-nav-item ${activePage === "analyzer" ? "active" : ""}`}
              onClick={() => setActivePage("analyzer")}
              type="button"
            >
              <span className="sidebar-nav-icon"><FileText size={18} /></span>
              <span className="sidebar-nav-label">Analyzer</span>
            </button>
            <button
              className={`sidebar-nav-item ${activePage === "config" ? "active" : ""}`}
              onClick={() => setActivePage("config")}
              type="button"
            >
              <span className="sidebar-nav-icon"><Settings size={18} /></span>
              <span className="sidebar-nav-label">Configurations</span>
            </button>
            <button
              className={`sidebar-nav-item ${activePage === "resume-db" ? "active" : ""}`}
              onClick={() => setActivePage("resume-db")}
              type="button"
            >
              <span className="sidebar-nav-icon"><Database size={18} /></span>
              <span className="sidebar-nav-label">Resume DB</span>
            </button>
            <button
              className={`sidebar-nav-item ${activePage === "shortlist" ? "active" : ""}`}
              onClick={() => setActivePage("shortlist")}
              type="button"
            >
              <span className="sidebar-nav-icon"><FileCheck size={18} /></span>
              <span className="sidebar-nav-label">Shortlisted Candidates</span>
            </button>
            <button
              className={`sidebar-nav-item ${activePage === "assessments" ? "active" : ""}`}
              onClick={() => setActivePage("assessments")}
              type="button"
            >
              <span className="sidebar-nav-icon"><ClipboardList size={18} /></span>
              <span className="sidebar-nav-label">Assessments</span>
            </button>
          </nav>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-title">CANDIDATE PORTAL</div>
          <nav className="sidebar-nav">
            <a
              className="sidebar-nav-item"
              href="/assessment/start"
              target="_blank"
              rel="noreferrer"
            >
              <span className="sidebar-nav-icon"><Award size={18} /></span>
              <span className="sidebar-nav-label">Online Assessment</span>
            </a>
          </nav>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-title">SECURITY</div>
          <nav className="sidebar-nav">
            <button
              className={`sidebar-nav-item ${activePage === "system-status" ? "active" : ""}`}
              onClick={() => setActivePage("system-status")}
              type="button"
            >
              <span className="sidebar-nav-icon"><Shield size={18} /></span>
              <span className="sidebar-nav-label">System Status</span>
            </button>
          </nav>
        </div>

        <div className="sidebar-user">
          <div className="sidebar-user-name">Admin User</div>
          <div className="sidebar-user-role">System Administrator</div>
        </div>
      </aside>

      <div className="main-content">
        {activePage !== "shortlist" && (
          <section className="toolbar">
            <div className="toolbar-header">
              <h1>Resume Analyzer</h1>
              <p>Analyze resumes against job descriptions using AI-powered matching</p>
            </div>
            <div className="toolbar-actions">
              <div className="recruiter-workspace-badge">
                <span className="badge-title">Recruiter Workspace</span>
                <span className="badge-subtitle">AI Screening Dashboard</span>
              </div>
            </div>
          </section>
        )}

        {activePage === "analyzer" ? (
          <AnalyzerPage
            error={error}
            handleAnalyze={handleAnalyze}
            handleDetailLimitChange={handleDetailLimitChange}
            handleJobDescriptionChange={handleJobDescriptionChange}
            handleModelChangeInvalidate={handleModelChangeInvalidate}
            handleProviderChangeInvalidate={handleProviderChangeInvalidate}
            handleResumesChange={handleResumesChange}
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
        ) : activePage === "resume-db" ? (
          <ResumeDbPage
            error={resumeDbError}
            isLoading={isResumeDbLoading}
            onRefresh={loadResumeDb}
            resumeDb={resumeDb}
          />
        ) : activePage === "shortlist" ? (
          <ShortlistedCandidatesPage
            result={result}
          />
        ) : activePage === "assessments" ? (
          <AssessmentManagementPage
            result={result}
          />
        ) : null}
      </div>
    </main>
  );
}

function AnalyzerPage({
  detailLimit,
  error,
  handleAnalyze,
  handleDetailLimitChange,
  handleJobDescriptionChange,
  handleModelChangeInvalidate,
  handleProviderChangeInvalidate,
  handleResumesChange,
  isLoading,
  jobDescription,
  model,
  modelOptions,
  notice,
  provider,
  providers,
  result,
  resumes,
}) {
  return (
    <form className="workspace" onSubmit={handleAnalyze}>
      <section className="analyzer-config">
        <div className="analyzer-config-header">
          <h2>Analysis Configuration</h2>
          <p>Configure AI provider, model, and analysis parameters</p>
        </div>

        <div className="analyzer-controls">
          <label>
            Provider
            <select
              value={provider}
              onChange={(event) => handleProviderChangeInvalidate(event.target.value)}
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
            <select value={model} onChange={(event) => handleModelChangeInvalidate(event.target.value)}>
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
              onChange={(event) => handleDetailLimitChange(Number(event.target.value))}
            >
              {[3, 5, 10, 15, 20].map((item) => (
                <option key={item} value={item}>
                  Top {item}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="analyzer-input-section">
          <div className="resume-upload-section">
            <div className="section-title">Resume Upload</div>
            <label className="upload-zone">
              <UploadCloud size={20} />
              <span>
                {resumes.length
                  ? `${resumes.length} resume${resumes.length === 1 ? "" : "s"} selected`
                  : "Optional: add new resumes"}
              </span>
              <input
                multiple
                type="file"
                accept=".pdf,.docx"
                onChange={(event) => handleResumesChange([...event.target.files])}
              />
            </label>

            <div className="file-list">
              {resumes.map((resume) => (
                <div className="file-row" key={resume.name}>
                  <FileText size={14} />
                  <span>{resume.name}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="jd-section">
            <div className="section-title">Job Description</div>
            <label className="jd-input">
              <textarea
                className="jd-textarea"
                value={jobDescription}
                onChange={(event) => handleJobDescriptionChange(event.target.value)}
                rows={6}
              />
            </label>
          </div>

          <div className="analyze-button-wrapper">
            <button disabled={isLoading} type="submit">
              {isLoading ? <Loader2 className="spin" size={18} /> : null}
              Analyze
            </button>
          </div>
        </div>
      </section>

      {error && <div className="error">{error}</div>}
      {notice && <div className="notice">{notice}</div>}

      <section className={`panel results-panel ${result ? 'has-results' : ''}`}>
        {!result ? (
          <div className="empty-state">Results appear after analysis.</div>
        ) : (
          <Results result={result} />
        )}
      </section>

      <section className="reports-section">
        <div className="reports-header">
          <h2>Reports & Test Runs</h2>
        </div>
        <div className="empty-state">
          Reports and test run history will appear here.
        </div>
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
              onChange={(event) => {
                handleProviderChange(event.target.value);
                // Note: Configuration changes don't invalidate current analysis
                // They only apply to future analysis runs
              }}
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
            <select value={model} onChange={(event) => {
              handleModelChange(event.target.value);
              // Note: Configuration changes don't invalidate current analysis
              // They only apply to future analysis runs
            }}>
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
          onChange={(value) => updatePrompt("candidate_detail_prompt_template", value)}
        />
        <PromptEditor
          label="Grading Prompt"
          value={config.grading_prompt_template}
          onChange={(value) => updatePrompt("grading_prompt_template", value)}
        />
        <PromptEditor
          label="Key Matches Prompt"
          value={config.key_matches_prompt_template}
          onChange={(value) => updatePrompt("key_matches_prompt_template", value)}
        />
        <PromptEditor
          label="Key Gaps Prompt"
          value={config.key_gaps_prompt_template}
          onChange={(value) => updatePrompt("key_gaps_prompt_template", value)}
        />
        <PromptEditor
          label="Final Reason Prompt"
          value={config.final_reason_prompt_template}
          onChange={(value) => updatePrompt("final_reason_prompt_template", value)}
        />
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

function Results({ result }) {
  if (!result) {
    return <div className="empty-state">No results available.</div>;
  }

  const runtimeStatus = result.runtime_status || {};
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [selectedCandidates, setSelectedCandidates] = useState(new Set());
  const [showComparisonModal, setShowComparisonModal] = useState(false);
  const [notice, setNotice] = useState("");
  const [analysisSessionId, setAnalysisSessionId] = useState(null);

  // Persist analysis state to localStorage
  useEffect(() => {
    if (result) {
      const existingSession = localStorage.getItem('currentAnalysisSession');
      let timestamp = Date.now();
      if (existingSession) {
        try {
          const parsed = JSON.parse(existingSession);
          if (parsed.timestamp) timestamp = parsed.timestamp;
        } catch (e) { }
      }
      const sessionData = {
        result,
        selectedCandidates: Array.from(selectedCandidates),
        timestamp
      };
      localStorage.setItem('currentAnalysisSession', JSON.stringify(sessionData));
      setAnalysisSessionId(timestamp.toString());
    }
  }, [result, selectedCandidates]);

  // Restore analysis state on mount
  useEffect(() => {
    const savedSession = localStorage.getItem('currentAnalysisSession');
    if (savedSession) {
      try {
        const sessionData = JSON.parse(savedSession);
        // Only restore if it's from the same browser session (recent)
        if (Date.now() - sessionData.timestamp < 24 * 60 * 60 * 1000) { // 24 hours
          setSelectedCandidates(new Set(sessionData.selectedCandidates));
          const sessIdStr = sessionData.timestamp.toString();
          setAnalysisSessionId(sessIdStr);

          // Check if comparison modal was open for this analysis session
          const isCompOpen = localStorage.getItem('isComparisonOpen') === 'true';
          const savedComparison = localStorage.getItem('comparisonResults');
          if (savedComparison) {
            try {
              const compData = JSON.parse(savedComparison);
              if (compData.analysisSessionId === sessIdStr && (compData.isOpen || isCompOpen)) {
                setShowComparisonModal(true);
              }
            } catch (e) {
              console.error('Failed to parse saved comparison on restore:', e);
            }
          }
        }
      } catch (err) {
        console.error('Failed to restore analysis session:', err);
      }
    }
  }, []);
  const detailMap = useMemo(() => {
    return new Map(
      (result.top_details || []).map((detail) => [detail.resume_id, detail]),
    );
  }, [result.top_details]);

  const handleSelectCandidate = (resumeId) => {
    const targetId = String(resumeId || "").trim();
    if (!targetId) return;

    setSelectedCandidates((prev) => {
      const newSet = new Set(prev);
      const isChecked = !newSet.has(targetId);
      if (newSet.has(targetId)) {
        newSet.delete(targetId);
      } else {
        newSet.add(targetId);
      }
      console.log(
        "[ASSESSMENT SELECT] checkbox changed",
        targetId,
        "checked state:",
        isChecked,
        "selected IDs:",
        Array.from(newSet)
      );
      return newSet;
    });
  };

  const handleClearSelection = () => {
    setSelectedCandidates(new Set());
  };

  const handleCompare = async () => {
    if (selectedCandidates.size < 2) {
      alert('Please select at least 2 candidates to compare');
      return;
    }
    // Clear previous comparison results when opening with new selection
    localStorage.removeItem('comparisonResults');
    localStorage.setItem('isComparisonOpen', 'true');
    setShowComparisonModal(true);
  };

  const handleShortlist = async () => {
    if (selectedCandidates.size === 0) {
      alert('Please select at least 1 candidate to shortlist');
      return;
    }

    try {
      // Get current user from localStorage
      const userJson = localStorage.getItem('recruiter.user');
      const user = userJson ? JSON.parse(userJson) : null;
      const userId = user?.id || user?.email || 'demo_user';

      // First, try to find an existing shortlist for this job description
      const getShortlistsResponse = await fetch(`${API_BASE_URL}/api/shortlists?user_id=${encodeURIComponent(userId)}`);
      if (!getShortlistsResponse.ok) {
        throw new Error('Failed to fetch existing shortlists');
      }

      const shortlistsData = await getShortlistsResponse.json();
      const existingShortlists = shortlistsData.shortlists || [];

      // Find a shortlist with matching job description
      const currentJdString = JSON.stringify(result.job_description || {}, Object.keys(result.job_description || {}).sort());
      let matchingShortlist = existingShortlists.find(s =>
        JSON.stringify(s.job_description || {}, Object.keys(s.job_description || {}).sort()) === currentJdString &&
        s.status === 'active'
      );

      let shortlistId;

      if (matchingShortlist) {
        shortlistId = matchingShortlist.shortlist_id;
      } else {
        // Create a new shortlist
        const createResponse = await fetch(`${API_BASE_URL}/api/shortlists/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            job_description: result.job_description || {},
            user_id: userId,
            created_by_role: 'recruiter',
            evidence_assessment_snapshot: null
          })
        });

        if (!createResponse.ok) {
          const errorData = await createResponse.json();
          throw new Error(errorData.detail || 'Failed to create shortlist');
        }

        const createData = await createResponse.json();
        shortlistId = createData.shortlist.shortlist_id;
      }

      // Add selected candidates to the shortlist
      let addedCount = 0;
      for (const resumeId of selectedCandidates) {
        const candidateData = detailMap.get(resumeId);
        if (!candidateData) continue;

        const rankingRow = (result.ranking || []).find(r => r.resume_id === resumeId);

        const addResponse = await fetch(`${API_BASE_URL}/api/shortlists/${shortlistId}/candidates?user_id=${encodeURIComponent(userId)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            resume_id: resumeId,
            candidate_name: candidateData.resume_name || rankingRow?.resume_name || 'Unknown',
            match_score: rankingRow?.match_score || 0,
            match_position: rankingRow?.fit || 'Unknown',
            evidence_snapshot: {
              strengths: candidateData.strengths || [],
              gaps: candidateData.gaps || [],
              jd_coverage: candidateData.jd_coverage || [],
              evidence: candidateData.matching_evidence || []
            }
          })
        });

        if (addResponse.ok) {
          addedCount++;

          // 1. Un-remove candidate if previously removed from assessments
          try {
            const savedRemoved = localStorage.getItem("recruiter.assessment_removed_candidates");
            if (savedRemoved) {
              const removedArr = JSON.parse(savedRemoved);
              const nextRemoved = removedArr.filter((id) => String(id) !== String(resumeId));
              localStorage.setItem("recruiter.assessment_removed_candidates", JSON.stringify(nextRemoved));
            }
          } catch (e) {
            console.error("Failed to update removed candidates:", e);
          }

          // 2. Append/Update to assessment records in local store
          const activeJd = result?.job_description || result?.job_description_summary || {};
          const jobRole = activeJd.job_title || activeJd.title || activeJd.role || activeJd.position || "Engineer";

          createOrUpdateAssessment(resumeId, {
            resume_id: resumeId,
            candidate_name: candidateData.resume_name || rankingRow?.resume_name || 'Unknown',
            job_role: jobRole,
            shortlist_id: shortlistId,
            match_score: rankingRow?.match_score || 0,
            fit: rankingRow?.fit || 'Good Fit'
          });
        } else {
          console.warn(`Failed to add candidate ${resumeId} to shortlist`);
        }
      }

      setNotice(`Successfully added ${addedCount} candidate(s) to shortlist and assessments`);
      setTimeout(() => setNotice(""), 3000);

      // Clear selection after successful shortlist
      handleClearSelection();

    } catch (error) {
      console.error('Shortlist error:', error);
      alert(`Shortlist failed: ${error.message}`);
    }
  };

  return (
    <div className="results-content">
      {notice && <div className="notice">{notice}</div>}

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

      <section className="jd-results-section">
        <h2>Job Description</h2>
        <div className="jd-grid">
          {Object.entries(result.job_description || {}).map(([key, value]) => (
            <div className="jd-card" key={key}>
              <span className="jd-label">{key.replaceAll("_", " ")}</span>
              <strong className="jd-value">{formatDisplayValue(value)}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="ranking-section">
        <div className="ranking-header">
          <h2>Ranking</h2>
          <div className="ranking-actions">
            <button
              className="secondary"
              type="button"
              onClick={handleClearSelection}
              disabled={selectedCandidates.size === 0}
            >
              Clear Selection
            </button>
            <button
              type="button"
              onClick={handleCompare}
              disabled={selectedCandidates.size < 2}
            >
              Compare Selected Candidates ({selectedCandidates.size})
            </button>
            <button
              type="button"
              onClick={handleShortlist}
              disabled={selectedCandidates.size === 0}
            >
              Shortlist Selected Candidates ({selectedCandidates.size})
            </button>
          </div>
        </div>
        <div className="table-scroll">
          <table className="ranking-table">
            <thead>
              <tr>
                <th style={{ width: '60px', textAlign: 'center' }}>Select</th>
                <th>Resume</th>
                <th style={{ width: '130px' }}>Score</th>
                <th style={{ width: '150px' }}>Fit</th>
                <th style={{ width: '140px', textAlign: 'right' }}>Detailed Analysis</th>
              </tr>
            </thead>
            <tbody>
              {(result.ranking || []).map((row) => {
                const detail = detailMap.get(row.resume_id);

                return (
                  <tr key={row.resume_id}>
                    <td style={{ textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={selectedCandidates.has(row.resume_id)}
                        onChange={() => handleSelectCandidate(row.resume_id)}
                      />
                    </td>
                    <td>
                      <span className="candidate-name-text">{row.resume_name}</span>
                    </td>
                    <td>
                      <span className="candidate-score-badge">{row.match_score}%</span>
                    </td>
                    <td>
                      <span className={`fit-pill fit-${(row.fit || "").toLowerCase().replaceAll(" ", "-")}`}>
                        {row.fit}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
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
        </div>
      </section>

      {selectedDetail ? (
        <DetailModal
          detail={selectedDetail}
          onClose={() => setSelectedDetail(null)}
        />
      ) : null}

      {showComparisonModal && (
        <ComparisonModal
          analysisSessionId={analysisSessionId}
          selectedCandidates={selectedCandidates}
          result={result}
          detailMap={detailMap}
          onClose={() => setShowComparisonModal(false)}
          onToggleCandidate={handleSelectCandidate}
        />
      )}
    </div>
  );
}

function DetailModal({ detail, onClose }) {
  if (!detail) {
    return null;
  }

  const [activeTab, setActiveTab] = useState("evidence");
  const [resumeChunks, setResumeChunks] = useState([]);
  const [loadingResume, setLoadingResume] = useState(false);
  const [expandedGithubSection, setExpandedGithubSection] = useState(null);
  const [expandedLinkedinSection, setExpandedLinkedinSection] = useState(null);

  const evidence = Array.isArray(detail.matching_evidence)
    ? detail.matching_evidence
    : [];
  const grading = isUsableGrading(detail.candidate_grading)
    ? detail.candidate_grading
    : buildDisplayGradingFallback(detail);
  const [showEvidence, setShowEvidence] = useState(false);

  // Load resume chunks when modal opens
  useEffect(() => {
    if (detail && detail.resume_id) {
      loadResumeChunks();
    }
  }, [detail?.resume_id]);

  const loadResumeChunks = async () => {
    setLoadingResume(true);
    try {
      const response = await fetch(`${API_BASE_URL}/resume/${detail.resume_id}`);
      if (response.ok) {
        const data = await response.json();
        setResumeChunks(data.chunks || []);
      }
    } catch (error) {
      console.error('Failed to load resume chunks:', error);
    } finally {
      setLoadingResume(false);
    }
  };

  // Helper functions for chunk grouping
  const getSectionChunks = (chunks, sectionName) => {
    return chunks.filter(chunk => {
      const section = (chunk.section || "").toLowerCase();
      if (sectionName === "summary") {
        return section === "summary" || section === "professionalsummary" || section === "objective";
      }
      if (sectionName === "skills") {
        return section.includes("skill");
      }
      if (sectionName === "experience") {
        return section.includes("experience") || section.includes("employment") || section.includes("workhistory");
      }
      if (sectionName === "projects") {
        return section.includes("project");
      }
      if (sectionName === "education") {
        return section.includes("education") || section.includes("qualification");
      }
      if (sectionName === "certifications") {
        return section.includes("certificat");
      }
      return section === sectionName.toLowerCase();
    });
  };

  const sortChunksByIndex = (chunks) => {
    return [...chunks].sort((a, b) => (a.chunk_index || 0) - (b.chunk_index || 0));
  };

  // Extract contact information from Contact Information chunk
  const extractContactFromChunk = (chunks) => {
    const contactChunk = chunks.find(chunk =>
      (chunk.section || "").toLowerCase() === "contact information"
    );

    if (!contactChunk || !contactChunk.text || typeof contactChunk.text !== 'string') {
      return null;
    }

    const text = contactChunk.text;
    const result = {
      name: null,
      email: null,
      phone: null,
      linkedin: null,
      github: null,
    };

    // Extract name (first line, capitalized)
    const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
    if (lines.length > 0) {
      const firstLine = lines[0];
      // Simple heuristic: if it looks like a name (2-3 capitalized words)
      if (/^[A-Z][a-z]+(\s+[A-Z][a-z]+){1,2}$/.test(firstLine)) {
        result.name = firstLine;
      }
    }

    // Extract email
    const emailMatch = text.match(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/i);
    if (emailMatch) {
      result.email = emailMatch[0];
    }

    // Extract phone (Indian format)
    const phoneMatch = text.match(/\+91[-\s]?\d{5}[-\s]?\d{5}|\+91\s?\d{10}|91[-\s]?\d{5}[-\s]?\d{5}|\b\d{10}\b/);
    if (phoneMatch) {
      result.phone = phoneMatch[0];
    }

    // Extract LinkedIn
    const linkedinMatch = text.match(/linkedin\.com\/in\/[A-Za-z0-9-]+/i);
    if (linkedinMatch) {
      result.linkedin = linkedinMatch[0].startsWith('http') ? linkedinMatch[0] : `https://${linkedinMatch[0]}`;
    }

    // Extract GitHub
    const githubMatch = text.match(/github\.com\/[A-Za-z0-9_-]+/i);
    if (githubMatch) {
      result.github = githubMatch[0].startsWith('http') ? githubMatch[0] : `https://${githubMatch[0]}`;
    }

    return result;
  };

  // Extract professional summary from Professional Summary chunk
  const extractSummaryFromChunk = (chunks) => {
    if (!Array.isArray(chunks) || chunks.length === 0) {
      return null;
    }

    const summaryChunk = chunks.find(chunk =>
      (chunk.section || "").toLowerCase() === "professional summary"
    );

    if (!summaryChunk || !summaryChunk.text || typeof summaryChunk.text !== 'string') {
      return null;
    }

    return summaryChunk.text.trim();
  };

  // helper to extract text strings recursively from obj
  const extractAllStringsFromObject = (obj) => {
    let strings = [];
    if (!obj) return strings;
    if (typeof obj === 'string') {
      if (obj.trim().length > 1) strings.push(obj);
    } else if (Array.isArray(obj)) {
      obj.forEach(item => {
        strings.push(...extractAllStringsFromObject(item));
      });
    } else if (typeof obj === 'object') {
      Object.values(obj).forEach(val => {
        strings.push(...extractAllStringsFromObject(val));
      });
    }
    return strings;
  };

  // Build normalized evidence index from available sources (Resume, LinkedIn, GitHub)
  const evidenceIndex = useMemo(() => {
    // 1. Resume text corpus
    const resumeTextCorpus = (resumeChunks || [])
      .map(c => c.text || '')
      .filter(Boolean)
      .join('\n')
      .toLowerCase();

    // 2. LinkedIn text corpus
    const linkedinProfile = detail.linkedin_profile || {};
    const linkedinStrings = extractAllStringsFromObject(linkedinProfile);
    const linkedinTextCorpus = linkedinStrings.join('\n').toLowerCase();

    // 3. GitHub text corpus
    const githubVerification = detail.github_verification || {};
    const githubStrings = extractAllStringsFromObject(githubVerification);
    const githubTextCorpus = githubStrings.join('\n').toLowerCase();

    // Collect all candidate skills & candidate text phrases to evaluate
    const candidateSkills = [
      ...(detail.matching_skills || []),
      ...(detail.missing_skills || []),
      ...(detail.resume_skill_profile?.skills || []),
      ...(grading.strengths || []),
      ...(grading.concerns || [])
    ].map(s => (typeof s === 'string' ? s.trim() : '')).filter(Boolean);

    // Common stop words to exclude from single-word phrase highlighting
    const STOP_WORDS = new Set([
      'the', 'and', 'with', 'for', 'from', 'this', 'that', 'work', 'experience',
      'candidate', 'role', 'team', 'using', 'used', 'built', 'worked', 'project',
      'system', 'data', 'development', 'management', 'analysis', 'solution',
      'strong', 'good', 'years', 'skills', 'knowledge', 'ability', 'application',
      'developed', 'design', 'building', 'create', 'created', 'implement',
      'implemented', 'including', 'key', 'main', 'responsibilities', 'summary',
      'overview', 'profile', 'level', 'high', 'technical', 'etc', 'not', 'specified'
    ]);

    // Build phrase source map: phrase (normalized) -> { resume, linkedin, github }
    const phraseMap = new Map();

    const addPhraseToMap = (rawPhrase) => {
      if (!rawPhrase || typeof rawPhrase !== 'string') return;
      const clean = rawPhrase.trim();
      const lower = clean.toLowerCase();

      // Skip invalid or stop-word-only phrases
      if (lower.length < 2) return;
      if (!lower.includes(' ') && STOP_WORDS.has(lower)) return;
      if (phraseMap.has(lower)) return;

      const hasResume = resumeTextCorpus.length > 0 && resumeTextCorpus.includes(lower);
      const hasLinkedin = linkedinTextCorpus.length > 0 && linkedinTextCorpus.includes(lower);
      const hasGithub = githubTextCorpus.length > 0 && githubTextCorpus.includes(lower);

      if (hasResume || hasLinkedin || hasGithub) {
        phraseMap.set(lower, {
          display: clean,
          lower: lower,
          length: lower.length,
          resume: hasResume,
          linkedin: hasLinkedin,
          github: hasGithub
        });
      }
    };

    // Add candidate skills
    candidateSkills.forEach(addPhraseToMap);

    // Also extract multi-word capitalized/tech terms from chunks
    (resumeChunks || []).forEach(chunk => {
      const text = chunk.text || '';
      // Match technology terms, tech stack names, multi-word phrases
      const matches = text.match(/\b([A-Z][A-Za-z0-9+#.-]+(?:\s+[A-Z][A-Za-z0-9+#.-]+)*)\b/g);
      if (matches) {
        matches.forEach(addPhraseToMap);
      }
    });

    // Sort phrases by length DESCENDING so longest phrases match first
    const sortedPhrases = Array.from(phraseMap.values()).sort((a, b) => b.length - a.length);

    return {
      phraseMap,
      sortedPhrases,
      hasResumeData: resumeTextCorpus.length > 0,
      hasLinkedinData: linkedinTextCorpus.length > 0,
      hasGithubData: githubTextCorpus.length > 0
    };
  }, [detail, resumeChunks, grading]);

  // Helper to get exact 7-combination CSS class & source combination name
  const getEvidenceClassAndKey = (sources) => {
    const { resume, linkedin, github } = sources;
    if (resume && linkedin && github) return { className: 'evidence-all-sources', key: 'resume+linkedin+github', label: 'Resume + LinkedIn + GitHub' };
    if (resume && linkedin) return { className: 'evidence-resume-linkedin', key: 'resume+linkedin', label: 'Resume + LinkedIn' };
    if (resume && github) return { className: 'evidence-resume-github', key: 'resume+github', label: 'Resume + GitHub' };
    if (linkedin && github) return { className: 'evidence-linkedin-github', key: 'linkedin+github', label: 'LinkedIn + GitHub' };
    if (resume) return { className: 'evidence-resume', key: 'resume', label: 'Resume Only' };
    if (linkedin) return { className: 'evidence-linkedin', key: 'linkedin', label: 'LinkedIn Only' };
    if (github) return { className: 'evidence-github', key: 'github', label: 'GitHub Only' };
    return null;
  };

  // Helper to get evidence highlight for a single skill term
  const getSkillHighlightClass = (skillName) => {
    if (!skillName || typeof skillName !== 'string') return null;
    const lower = skillName.trim().toLowerCase();
    const entry = evidenceIndex.phraseMap.get(lower);
    if (entry) {
      const info = getEvidenceClassAndKey(entry);
      return info ? info.className : null;
    }
    // Fallback: check if skill substring exists in sources
    const resume = evidenceIndex.hasResumeData && (resumeChunks || []).some(c => (c.text || '').toLowerCase().includes(lower));
    const linkedin = evidenceIndex.hasLinkedinData && (detail.linkedin_profile ? JSON.stringify(detail.linkedin_profile).toLowerCase().includes(lower) : false);
    const github = evidenceIndex.hasGithubData && (detail.github_verification ? JSON.stringify(detail.github_verification).toLowerCase().includes(lower) : false);
    const info = getEvidenceClassAndKey({ resume, linkedin, github });
    return info ? info.className : null;
  };

  // Set of generic words that should NOT trigger evidence highlight by themselves
  const GENERIC_EVIDENCE_WORDS = useMemo(() => new Set([
    'ai', 'data', 'software', 'system', 'project', 'experience', 'developed',
    'worked', 'using', 'technology', 'machine', 'learning', 'the', 'and',
    'with', 'for', 'from', 'this', 'that', 'work', 'candidate', 'role', 'team',
    'built', 'solution', 'strong', 'good', 'years', 'skills', 'knowledge',
    'ability', 'application', 'design', 'building', 'create', 'created',
    'implement', 'implemented', 'including', 'key', 'main', 'responsibilities',
    'summary', 'overview', 'profile', 'level', 'high', 'technical', 'present',
    'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
    'september', 'october', 'november', 'december', 'jan', 'feb', 'mar', 'apr',
    'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
  ]), []);

  // Sentence / Block level evidence evaluator and highlighter
  const renderHighlightedText = (text) => {
    if (!text || typeof text !== 'string') {
      return text;
    }

    const renderBlockOrSentence = (blockText, blockKey) => {
      if (!blockText || !blockText.trim()) return blockText;

      const lowerBlock = blockText.toLowerCase();

      // Extract words to check meaningful tokens
      const words = lowerBlock.match(/[a-z0-9+#.-]+/g) || [];
      const meaningfulWords = words.filter(w => w.length >= 3 && !GENERIC_EVIDENCE_WORDS.has(w));
      const totalMeaningfulCount = meaningfulWords.length;

      // Check matched phrases from evidenceIndex (longest multi-word phrases & skill terms)
      const matchedPhrases = (evidenceIndex.sortedPhrases || []).filter(phrase =>
        lowerBlock.includes(phrase.lower)
      );

      // If no meaningful words and no specific matched phrases, leave text normal (unhighlighted)
      if (totalMeaningfulCount === 0 && matchedPhrases.length === 0) {
        return blockText;
      }

      // Check corpus matching for each source
      const resumeCorpus = (resumeChunks || []).map(c => c.text || '').join('\n').toLowerCase();
      const resumeMatchedWords = meaningfulWords.filter(w => resumeCorpus.includes(w)).length;
      const resumeCoverage = totalMeaningfulCount > 0 ? resumeMatchedWords / totalMeaningfulCount : 0;

      const linkedinCorpus = detail.linkedin_profile ? JSON.stringify(detail.linkedin_profile).toLowerCase() : '';
      const linkedinMatchedWords = linkedinCorpus ? meaningfulWords.filter(w => linkedinCorpus.includes(w)).length : 0;
      const linkedinCoverage = totalMeaningfulCount > 0 ? linkedinMatchedWords / totalMeaningfulCount : 0;

      const githubCorpus = detail.github_verification ? JSON.stringify(detail.github_verification).toLowerCase() : '';
      const githubMatchedWords = githubCorpus ? meaningfulWords.filter(w => githubCorpus.includes(w)).length : 0;
      const githubCoverage = totalMeaningfulCount > 0 ? githubMatchedWords / totalMeaningfulCount : 0;

      // Conservative Coverage Thresholds:
      // Require substantial evidence coverage (e.g. >=2 matched words with multi-word phrase OR >=3 matched words with >=30% coverage)
      const hasResume = evidenceIndex.hasResumeData && (
        (matchedPhrases.some(p => p.resume) && (resumeMatchedWords >= 2 || resumeCoverage >= 0.25)) ||
        (resumeMatchedWords >= 3 && resumeCoverage >= 0.30)
      );

      const hasLinkedin = evidenceIndex.hasLinkedinData && (
        (matchedPhrases.some(p => p.linkedin) && (linkedinMatchedWords >= 2 || linkedinCoverage >= 0.25)) ||
        (linkedinMatchedWords >= 3 && linkedinCoverage >= 0.30)
      );

      const hasGithub = evidenceIndex.hasGithubData && (
        (matchedPhrases.some(p => p.github) && (githubMatchedWords >= 2 || githubCoverage >= 0.25)) ||
        (githubMatchedWords >= 3 && githubCoverage >= 0.30)
      );

      // If none of the sources meet the conservative coverage threshold, leave sentence normal
      if (!hasResume && !hasLinkedin && !hasGithub) {
        return blockText;
      }

      const info = getEvidenceClassAndKey({ resume: hasResume, linkedin: hasLinkedin, github: hasGithub });

      if (info) {
        return (
          <span
            key={blockKey}
            className={`evidence-highlight ${info.className}`}
            title={`Evidence source: ${info.label}`}
          >
            {blockText}
          </span>
        );
      }

      return blockText;
    };

    // Split text by lines first (e.g. for bullet lists or newline-separated items)
    const lines = text.split('\n');
    if (lines.length > 1) {
      return lines.map((line, lineIdx) => {
        if (!line.trim()) return <React.Fragment key={lineIdx}>{"\n"}</React.Fragment>;

        // If it's a bullet line (starts with symbol or dash), treat the line as one block
        if (/^\s*[•\-*]|\d+\./.test(line)) {
          return (
            <React.Fragment key={lineIdx}>
              {renderBlockOrSentence(line, `line-${lineIdx}`)}
              {lineIdx < lines.length - 1 && "\n"}
            </React.Fragment>
          );
        }

        // Split paragraph line into sentences
        const sentences = line.match(/[^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$/g) || [line];
        const processedSentences = sentences.map((sentence, sIdx) =>
          renderBlockOrSentence(sentence, `${lineIdx}-${sIdx}`)
        );

        return (
          <React.Fragment key={lineIdx}>
            {processedSentences}
            {lineIdx < lines.length - 1 && "\n"}
          </React.Fragment>
        );
      });
    }

    // Single line: check bullet or split into sentences
    if (/^\s*[•\-*]|\d+\./.test(text)) {
      return renderBlockOrSentence(text, 0);
    }

    const sentences = text.match(/[^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$/g) || [text];
    if (sentences.length === 1) {
      return renderBlockOrSentence(text, 0);
    }

    return sentences.map((sentence, sIdx) => renderBlockOrSentence(sentence, sIdx));
  };

  // Keyword / Phrase level evidence highlighter (for Skills & Education sections)
  // Matches evidenceIndex.sortedPhrases longest-first, highlights only the matched
  // keyword/phrase inline. GENERIC_EVIDENCE_WORDS only prevents standalone single
  // generic words — multi-word phrases like "Bachelor of Computer Engineering" are
  // highlighted as complete units even if they contain generic words.
  const renderKeywordHighlightedText = (text) => {
    if (!text || typeof text !== 'string') return text;

    const lowerText = text.toLowerCase();
    const textLen = text.length;

    // Track which character positions are already claimed by a match
    const claimed = new Array(textLen).fill(false);
    // Collect matches: { start, end, info }
    const matches = [];

    // 1. Primary: match sortedPhrases (longest-first) from evidenceIndex
    for (const phrase of (evidenceIndex.sortedPhrases || [])) {
      let searchFrom = 0;
      while (searchFrom < textLen) {
        const idx = lowerText.indexOf(phrase.lower, searchFrom);
        if (idx === -1) break;

        const endIdx = idx + phrase.lower.length;

        // Word-boundary check: character before/after must not be alphanumeric
        const charBefore = idx > 0 ? lowerText[idx - 1] : ' ';
        const charAfter = endIdx < textLen ? lowerText[endIdx] : ' ';
        const atBoundary = !/[a-z0-9+#]/.test(charBefore) && !/[a-z0-9+#]/.test(charAfter);

        if (atBoundary) {
          // Ensure no overlap with already-claimed positions
          let overlaps = false;
          for (let i = idx; i < endIdx; i++) {
            if (claimed[i]) { overlaps = true; break; }
          }

          if (!overlaps) {
            const info = getEvidenceClassAndKey(phrase);
            if (info) {
              matches.push({ start: idx, end: endIdx, info });
              for (let i = idx; i < endIdx; i++) claimed[i] = true;
            }
          }
        }
        searchFrom = idx + 1;
      }
    }

    // 2. Secondary fallback: scan for remaining meaningful single words that
    //    are NOT in sortedPhrases but DO exist in at least one source corpus.
    //    Only non-generic, non-stop single words qualify.
    const singleWordRegex = /[a-zA-Z0-9+#.-]{2,}/g;
    let wordMatch;
    while ((wordMatch = singleWordRegex.exec(lowerText)) !== null) {
      const wStart = wordMatch.index;
      const wEnd = wStart + wordMatch[0].length;
      const word = wordMatch[0];

      // Skip if already claimed or generic
      if (claimed[wStart]) continue;
      if (GENERIC_EVIDENCE_WORDS.has(word)) continue;
      if (evidenceIndex.phraseMap.has(word)) continue; // already handled above

      // Check word boundaries
      const cBefore = wStart > 0 ? lowerText[wStart - 1] : ' ';
      const cAfter = wEnd < textLen ? lowerText[wEnd] : ' ';
      if (/[a-z0-9+#]/.test(cBefore) || /[a-z0-9+#]/.test(cAfter)) continue;

      // Check sources directly
      const resumeCorpus = (resumeChunks || []).map(c => c.text || '').join('\n').toLowerCase();
      const hasResume = evidenceIndex.hasResumeData && resumeCorpus.includes(word);
      const hasLinkedin = evidenceIndex.hasLinkedinData && (detail.linkedin_profile ? JSON.stringify(detail.linkedin_profile).toLowerCase().includes(word) : false);
      const hasGithub = evidenceIndex.hasGithubData && (detail.github_verification ? JSON.stringify(detail.github_verification).toLowerCase().includes(word) : false);

      if (hasResume || hasLinkedin || hasGithub) {
        const info = getEvidenceClassAndKey({ resume: hasResume, linkedin: hasLinkedin, github: hasGithub });
        if (info) {
          let overlap = false;
          for (let i = wStart; i < wEnd; i++) { if (claimed[i]) { overlap = true; break; } }
          if (!overlap) {
            matches.push({ start: wStart, end: wEnd, info });
            for (let i = wStart; i < wEnd; i++) claimed[i] = true;
          }
        }
      }
    }

    // If no matches at all, return plain text
    if (matches.length === 0) return text;

    // Sort by position and build output fragments
    matches.sort((a, b) => a.start - b.start);

    const parts = [];
    let lastEnd = 0;

    for (let m = 0; m < matches.length; m++) {
      const match = matches[m];
      // Plain text before this match
      if (match.start > lastEnd) {
        parts.push(text.substring(lastEnd, match.start));
      }
      parts.push(
        <span
          key={`kw-${match.start}`}
          className={`evidence-keyword-highlight ${match.info.className}`}
          title={`Evidence source: ${match.info.label}`}
        >
          {text.substring(match.start, match.end)}
        </span>
      );
      lastEnd = match.end;
    }

    // Trailing plain text
    if (lastEnd < textLen) {
      parts.push(text.substring(lastEnd));
    }

    return parts;
  };

  // Floating Side Legend Card Component (Rendered OUTSIDE main detail modal)
  const FloatingEvidenceLegend = () => (
    <aside className="evidence-legend-card" onClick={(e) => e.stopPropagation()}>
      <span className="evidence-legend-title">Evidence Sources</span>
      <p className="evidence-legend-subtitle">Highlight color shows which sources support the evidence.</p>
      <div className="evidence-legend-items">
        <span className="legend-chip swatch-resume"><span className="legend-swatch swatch-resume"></span> Resume</span>
        <span className="legend-chip swatch-linkedin"><span className="legend-swatch swatch-linkedin"></span> LinkedIn</span>
        <span className="legend-chip swatch-github"><span className="legend-swatch swatch-github"></span> GitHub</span>
        <span className="legend-chip swatch-resume-linkedin"><span className="legend-swatch swatch-resume-linkedin"></span> Resume + LinkedIn</span>
        <span className="legend-chip swatch-resume-github"><span className="legend-swatch swatch-resume-github"></span> Resume + GitHub</span>
        <span className="legend-chip swatch-linkedin-github"><span className="legend-swatch swatch-linkedin-github"></span> LinkedIn + GitHub</span>
        <span className="legend-chip swatch-all-sources"><span className="legend-swatch swatch-all-sources"></span> Resume + LinkedIn + GitHub</span>
      </div>
    </aside>
  );

  const groupChunksByEntity = (chunks) => {
    if (!Array.isArray(chunks)) return {};
    const grouped = {};
    chunks.forEach(chunk => {
      const key = chunk.entity_id || chunk.subsection || chunk.company || chunk.project || 'default';
      if (!grouped[key]) {
        grouped[key] = [];
      }
      grouped[key].push(chunk);
    });
    return grouped;
  };

  const getGroupDisplayName = (chunks) => {
    if (!Array.isArray(chunks) || chunks.length === 0) return 'Untitled';
    if (chunks[0]?.entity_name) return chunks[0].entity_name;
    if (chunks[0]?.company) return chunks[0].company;
    if (chunks[0]?.project) return chunks[0].project;
    if (chunks[0]?.subsection) return chunks[0].subsection;
    return 'Untitled';
  };

  // Resume content extraction
  const summaryChunks = sortChunksByIndex(getSectionChunks(resumeChunks, "summary"));
  const resumeSummary = summaryChunks
    .map(chunk => chunk.text || "")
    .filter(Boolean)
    .join("\n\n");

  // Extract contact and summary from chunks
  const chunkContact = extractContactFromChunk(resumeChunks);
  const chunkSummary = extractSummaryFromChunk(resumeChunks);

  const skillsChunks = sortChunksByIndex(getSectionChunks(resumeChunks, "skills"));
  const experienceChunks = sortChunksByIndex(getSectionChunks(resumeChunks, "experience"));
  const projectChunks = sortChunksByIndex(getSectionChunks(resumeChunks, "projects"));
  const educationChunks = sortChunksByIndex(getSectionChunks(resumeChunks, "education"));
  const certificationChunks = sortChunksByIndex(getSectionChunks(resumeChunks, "certifications"));

  // Show loading state while chunks are being fetched
  if (loadingResume) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <div className="detail-modal-overlay" onClick={(event) => event.stopPropagation()}>
          <section className="detail-modal" role="dialog" aria-modal="true">
            <div className="detail-header">
              <h2>Loading candidate details...</h2>
              <button className="secondary modal-close" onClick={onClose} type="button">Close</button>
            </div>
          </section>
        </div>
      </div>
    );
  }

  const contactInfo = detail.resume_skill_profile?.contact_info || {};

  const groupVerifItems = (items, isGithub = false) => {
    const groups = {};
    if (!Array.isArray(items)) return groups;

    items.forEach(item => {
      let cat = item.category || item.resume_section || item.type;
      const claimText = item.claim || item.evidence || item.reason || '';
      const textLower = claimText.toLowerCase();

      if (!cat) {
        if (textLower.includes('skill') || textLower.includes('python') || textLower.includes('sql') || textLower.includes('java') || textLower.includes('ml') || textLower.includes('nlp') || textLower.includes('react') || textLower.includes('node') || textLower.includes('fastapi') || textLower.includes('docker') || textLower.includes('pytorch') || textLower.includes('tensorflow')) {
          cat = 'Skills';
        } else if (textLower.includes('intern') || textLower.includes('experience') || textLower.includes('role') || textLower.includes('engineer') || textLower.includes('developer') || textLower.includes('technologies') || textLower.includes('work')) {
          cat = 'Experience';
        } else if (textLower.includes('degree') || textLower.includes('bachelor') || textLower.includes('master') || textLower.includes('education') || textLower.includes('university') || textLower.includes('college')) {
          cat = 'Education';
        } else if (textLower.includes('certif') || textLower.includes('course')) {
          cat = 'Certifications';
        } else if (isGithub && (textLower.includes('repo') || textLower.includes('project') || textLower.includes('notebook') || textLower.includes('code'))) {
          cat = 'Projects & Repositories';
        } else {
          cat = 'Claims';
        }
      } else {
        cat = String(cat).charAt(0).toUpperCase() + String(cat).slice(1).toLowerCase();
        if (cat === 'Skill') cat = 'Skills';
        if (cat === 'Project' || cat === 'Repo' || cat === 'Repository') cat = 'Projects & Repositories';
      }

      if (!groups[cat]) groups[cat] = [];
      if (claimText && !groups[cat].includes(claimText)) {
        groups[cat].push(claimText);
      }
    });
    return groups;
  };

  const renderVerifCardContent = (items, isGithub = false) => {
    const groups = groupVerifItems(items, isGithub);
    const entries = Object.entries(groups);
    if (entries.length === 0) return null;

    return (
      <div className="verif-card-groups">
        {entries.map(([catName, claimList], idx) => {
          const maxShown = 8;
          const displayed = claimList.slice(0, maxShown);
          const remaining = claimList.length - maxShown;

          return (
            <div key={idx} className="verif-group-section">
              <span className="verif-group-label">{catName}</span>
              <p className="verif-group-items">
                {displayed.join(' · ')}{remaining > 0 ? ` · +${remaining} more` : ''}
              </p>
            </div>
          );
        })}
      </div>
    );
  };

  // Normalize phone for tel: link (remove spaces, dashes, keep +91 if present)
  const normalizePhone = (phone) => {
    if (!phone) return null;
    return phone.replace(/[\s-]/g, '');
  };

  // Ensure URL has https:// prefix
  const normalizeUrl = (url) => {
    if (!url) return null;
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    return `https://${url}`;
  };

  // Extract compact display for LinkedIn/GitHub URLs
  const getCompactUrlDisplay = (url) => {
    if (!url) return null;
    // Remove https:// prefix for display
    return url.replace(/^https?:\/\//, '');
  };

  // Get contact values with better fallback: structured → LinkedIn/GitHub profile → Contact Information chunk
  const email = contactInfo.email || detail.linkedin_profile?.email || chunkContact?.email || null;
  const phone = contactInfo.phone || detail.linkedin_profile?.phone || chunkContact?.phone || null;
  const linkedin = contactInfo.linkedin || detail.linkedin_profile?.profile_url || chunkContact?.linkedin || null;
  const github = contactInfo.github || detail.github_verification?.github_profile?.html_url || chunkContact?.github || null;

  // Get candidate name: chunk contact name → resume name
  const candidateName = chunkContact?.name || detail.resume_name;

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="detail-modal-overlay" onClick={(event) => event.stopPropagation()}>
        <section
          className="detail-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="detail-modal-title"
        >
          <div className="detail-header">
            <div className="candidate-header-left">
              <div className="candidate-title-row">
                <h2 id="detail-modal-title">
                  {formatDisplayValue(candidateName)}
                </h2>
                {grading.grade && (
                  <span className="candidate-grade-badge">Grade {formatDisplayValue(grading.grade)}</span>
                )}
              </div>
              <div className="candidate-match-subtitle">
                <span className="candidate-match-percent">{formatDisplayValue(detail.match_score)}% match</span>
                {detail.resume_skill_profile?.experience_summary && (
                  <span className="candidate-role-divider">•</span>
                )}
                <span className="candidate-role">
                  {formatDisplayValue(detail.resume_skill_profile?.experience_summary?.split('\n')[0] || '')}
                </span>
              </div>
            </div>
            <div className="header-actions">
              <button className="secondary export-btn" onClick={() => console.log('Export Report')} type="button">
                Export Report
              </button>
              <button className="secondary modal-close" onClick={onClose} type="button">
                Close
              </button>
            </div>
          </div>

          <div className="detail-modal-scrollable">
            {/* Match Score & Grade Metric Cards */}
            <div className="match-score-strip">
              <div className="metric-box">
                <div className="match-score-label">Match Score</div>
                <div className="match-score-value">{formatDisplayValue(detail.match_score)}%</div>
              </div>
              <div className="metric-box">
                <div className="match-score-label">Grade</div>
                <div className="match-score-value grade-val">{formatDisplayValue(grading.grade, 'N/A')}</div>
              </div>
            </div>

            {/* Candidate Summary - from Professional Summary chunk */}
            {chunkSummary && (
              <div className="candidate-summary-section">
                <h4>Summary</h4>
                <p>{chunkSummary}</p>
              </div>
            )}

            {/* Contact Info - Clean 2-column card */}
            <div className="candidate-contact">
              <div className="contact-item">
                <span className="contact-label">Email</span>
                <div className="contact-val">
                  {email ? (
                    <a href={`mailto:${email}`}>{email}</a>
                  ) : <span className="muted-text">Not available</span>}
                </div>
              </div>
              <div className="contact-item">
                <span className="contact-label">Phone</span>
                <div className="contact-val">
                  {phone ? (
                    <a href={`tel:${normalizePhone(phone)}`}>{phone}</a>
                  ) : <span className="muted-text">Not available</span>}
                </div>
              </div>
              <div className="contact-item">
                <span className="contact-label">LinkedIn</span>
                <div className="contact-val">
                  {linkedin ? (
                    <a href={normalizeUrl(linkedin)} target="_blank" rel="noopener noreferrer">{getCompactUrlDisplay(linkedin)}</a>
                  ) : <span className="muted-text">Not available</span>}
                </div>
              </div>
              <div className="contact-item">
                <span className="contact-label">GitHub</span>
                <div className="contact-val">
                  {github ? (
                    <a href={normalizeUrl(github)} target="_blank" rel="noopener noreferrer">{getCompactUrlDisplay(github)}</a>
                  ) : <span className="muted-text">Not available</span>}
                </div>
              </div>
            </div>

            {/* Tabs */}
            <div className="modal-tabs">
              <button
                className={`tab ${activeTab === "evidence" ? "active" : ""}`}
                onClick={() => setActiveTab("evidence")}
                type="button"
              >
                Evidence & Analysis
              </button>
              <button
                className={`tab ${activeTab === "skills" ? "active" : ""}`}
                onClick={() => setActiveTab("skills")}
                type="button"
              >
                Skills
              </button>
              <button
                className={`tab ${activeTab === "profile" ? "active" : ""}`}
                onClick={() => setActiveTab("profile")}
                type="button"
              >
                Candidate Profile
              </button>
              <button
                className={`tab ${activeTab === "education" ? "active" : ""}`}
                onClick={() => setActiveTab("education")}
                type="button"
              >
                Education & Certifications
              </button>
              <button
                className={`tab ${activeTab === "github" ? "active" : ""}`}
                onClick={() => setActiveTab("github")}
                type="button"
              >
                GitHub Verification
              </button>
              <button
                className={`tab ${activeTab === "linkedin-verification" ? "active" : ""}`}
                onClick={() => setActiveTab("linkedin-verification")}
                type="button"
              >
                LinkedIn Verification
              </button>
              <button
                className={`tab ${activeTab === "linkedin" ? "active" : ""}`}
                onClick={() => setActiveTab("linkedin")}
                type="button"
              >
                LinkedIn Profile
              </button>
              <button
                className={`tab ${activeTab === "resume" ? "active" : ""}`}
                onClick={() => setActiveTab("resume")}
                type="button"
              >
                Resume Report
              </button>
            </div>

            {/* Tab Content */}
            {activeTab === "evidence" && (
              <div className="content-panel">
                <h3>Evidence & Analysis</h3>
                <p className="evidence-intro">{formatDisplayValue(detail.justification)}</p>
                <div className="skills modal-skills-grid grading-grid">
                  <SkillColumn title="Strengths" items={grading.strengths} />
                  <SkillColumn title="Concerns" items={grading.concerns} />
                </div>

                {/* Evidence Summary Section */}
                <div className="evidence-summary-card">
                  <span className="evidence-summary-title">EVIDENCE SUMMARY</span>
                  <p className="evidence-summary-text">
                    {(() => {
                      const safeEv = Array.isArray(evidence) ? evidence : [];
                      const matching = Array.isArray(detail.matching_skills) ? detail.matching_skills : [];
                      const missing = Array.isArray(detail.missing_skills) ? detail.missing_skills : [];

                      if (safeEv.length > 0) {
                        const topSkills = matching.slice(0, 5).join(", ");
                        const missingText = missing.length > 0 ? ` ${missing.join(" and ")} ${missing.length > 1 ? "are" : "is"} not supported by the indexed resume evidence.` : "";
                        return `The resume contains ${safeEv.length} verified evidence items${topSkills ? ` supporting key skills including ${topSkills}` : ""}.${missingText}`;
                      } else if (matching.length > 0) {
                        const missingText = missing.length > 0 ? ` while missing explicit evidence for ${missing.join(", ")}.` : ".";
                        return `The profile demonstrates alignment with job requirements including ${matching.join(", ")}${missingText}`;
                      }
                      return "No specific evidence summary available for this candidate profile.";
                    })()}
                  </p>
                </div>

                {/* Inline Matching & Missing Skills */}
                <div className="inline-skills-section">
                  <div className="inline-skill-group">
                    <span className="inline-skill-title matching">MATCHING</span>
                    <div className="inline-skills-container matching">
                      {Array.isArray(detail.matching_skills) && detail.matching_skills.length > 0 ? (
                        detail.matching_skills.map((skill, index) => {
                          const hClass = getSkillHighlightClass(skill);
                          return (
                            <React.Fragment key={index}>
                              <span className={`skill-pill matching-pill ${hClass ? `evidence-highlight ${hClass}` : ''}`}>
                                {formatDisplayValue(skill)}
                              </span>
                              {index < detail.matching_skills.length - 1 && <span className="skill-bullet">•</span>}
                            </React.Fragment>
                          );
                        })
                      ) : (
                        <span className="muted-text">None</span>
                      )}
                    </div>
                  </div>

                  <div className="inline-skill-group">
                    <span className="inline-skill-title missing">MISSING</span>
                    <div className="inline-skills-container missing">
                      {Array.isArray(detail.missing_skills) && detail.missing_skills.length > 0 ? (
                        detail.missing_skills.map((skill, index) => {
                          const hClass = getSkillHighlightClass(skill);
                          return (
                            <React.Fragment key={index}>
                              <span className={`skill-pill missing-pill ${hClass ? `evidence-highlight ${hClass}` : ''}`}>
                                {formatDisplayValue(skill)}
                              </span>
                              {index < detail.missing_skills.length - 1 && <span className="skill-bullet">•</span>}
                            </React.Fragment>
                          );
                        })
                      ) : (
                        <span className="muted-text">None</span>
                      )}
                    </div>
                  </div>
                </div>

                {showEvidence ? (
                  <EvidenceModal
                    evidence={evidence}
                    resumeName={detail.resume_name}
                    onClose={() => setShowEvidence(false)}
                  />
                ) : null}
              </div>
            )}

            {activeTab === "skills" && (
              <div className="content-panel">
                <h3>Skills</h3>
                {loadingResume ? (
                  <div className="empty-state">Loading skills...</div>
                ) : skillsChunks.length > 0 ? (
                  <div className="skills-list">
                    {skillsChunks.map((chunk, index) => (
                      <div key={index} className="skill-item">
                        {renderKeywordHighlightedText(chunk.text)}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">No skills information available.</div>
                )}
              </div>
            )}

            {activeTab === "profile" && (
              <div className="content-panel">
                <h3>Candidate Profile</h3>

                {/* Work Experience */}
                {experienceChunks.length > 0 && (
                  <div className="profile-section">
                    <h4>Work Experience</h4>
                    {Object.entries(groupChunksByEntity(experienceChunks)).map(([key, chunks]) => (
                      <div key={key} className="experience-card">
                        <h5>{getGroupDisplayName(chunks)}</h5>
                        {sortChunksByIndex(chunks).map((chunk, idx) => (
                          <p key={idx}>{renderHighlightedText(chunk.text, chunk.chunk_id)}</p>
                        ))}
                      </div>
                    ))}
                  </div>
                )}

                {/* Projects */}
                {projectChunks.length > 0 && (
                  <div className="profile-section">
                    <h4>Projects</h4>
                    {Object.entries(groupChunksByEntity(projectChunks)).map(([key, chunks]) => (
                      <div key={key} className="project-card">
                        <h5>{getGroupDisplayName(chunks)}</h5>
                        {sortChunksByIndex(chunks).map((chunk, idx) => (
                          <p key={idx}>{renderHighlightedText(chunk.text, chunk.chunk_id)}</p>
                        ))}
                      </div>
                    ))}
                  </div>
                )}

                {experienceChunks.length === 0 && projectChunks.length === 0 && (
                  <div className="empty-state">No work experience or project information available.</div>
                )}
              </div>
            )}

            {activeTab === "education" && (
              <div className="content-panel">
                <h3>Education & Certifications</h3>

                {/* Education */}
                {educationChunks.length > 0 && (
                  <div className="profile-section">
                    <h4>Education</h4>
                    {Object.entries(groupChunksByEntity(educationChunks)).map(([key, chunks]) => (
                      <div key={key} className="education-card">
                        <h5>{getGroupDisplayName(chunks)}</h5>
                        {sortChunksByIndex(chunks).map((chunk, idx) => (
                          <p key={idx}>{renderKeywordHighlightedText(chunk.text)}</p>
                        ))}
                      </div>
                    ))}
                  </div>
                )}

                {/* Certifications */}
                {certificationChunks.length > 0 && (
                  <div className="profile-section">
                    <h4>Certifications</h4>
                    {certificationChunks.map((chunk, index) => (
                      <div key={index} className="certification-item">
                        {renderKeywordHighlightedText(chunk.text)}
                      </div>
                    ))}
                  </div>
                )}

                {educationChunks.length === 0 && certificationChunks.length === 0 && (
                  <div className="empty-state">No education or certification information available.</div>
                )}
              </div>
            )}

            {activeTab === "github" && (
              <div className="content-panel">
                <h3>GitHub Verification</h3>
                {detail.github_verification ? (
                  <>
                    {/* Profile Header */}
                    <div className="verif-profile-header verif-github-accent">
                      <div className="verif-profile-identity">
                        <span className="verif-profile-name">{detail.github_verification.github_profile?.login || 'GitHub User'}</span>
                        {detail.github_verification.github_profile?.html_url && (
                          <a href={detail.github_verification.github_profile.html_url} target="_blank" rel="noopener noreferrer" className="verif-profile-link">View Profile ↗</a>
                        )}
                      </div>
                      {detail.github_verification.github_profile?.bio && (
                        <p className="verif-profile-headline">{detail.github_verification.github_profile.bio}</p>
                      )}
                    </div>

                    {/* Verification Status Card */}
                    {(() => {
                      const corr = detail.github_verification.corroborated || [];
                      const partial = detail.github_verification.partially_corroborated || [];
                      const unver = detail.github_verification.unverifiable || [];
                      const disc = detail.github_verification.discrepancies || [];
                      const total = corr.length + partial.length + unver.length + disc.length;
                      const statusLabel = corr.length > unver.length ? 'CORROBORATED' : unver.length > corr.length ? 'PARTIALLY VERIFIED' : 'MIXED';
                      const summaryText = total > 0
                        ? `GitHub verification analyzed ${total} claim${total !== 1 ? 's' : ''} from the resume. ${corr.length} ${corr.length === 1 ? 'was' : 'were'} corroborated by public repository evidence${partial.length > 0 ? `, ${partial.length} partially corroborated` : ''}${unver.length > 0 ? `, and ${unver.length} could not be verified from available GitHub data` : ''}.`
                        : 'No verification claims were generated for this candidate.';

                      return (
                        <div className="verif-status-card verif-github-status">
                          <div className="verif-status-card-header">
                            <span className="verif-status-label-title">VERIFICATION STATUS</span>
                            <span className={`verif-status-badge ${corr.length >= unver.length ? 'verif-status-positive' : 'verif-status-neutral'}`}>{statusLabel}</span>
                          </div>
                          <p className="verif-summary-text">{summaryText}</p>
                        </div>
                      );
                    })()}

                    {/* Verification Cards Grid */}
                    <div className="verif-cards-grid">
                      {(() => {
                        const items = detail.github_verification.corroborated || [];
                        if (items.length === 0) return null;
                        return (
                          <div className="verif-card verif-card-positive">
                            <div className="verif-card-header">
                              <span className="verif-card-title">✓ CORROBORATED</span>
                              <span className="verif-card-count">{items.length} claim{items.length !== 1 ? 's' : ''}</span>
                            </div>
                            {renderVerifCardContent(items, true)}
                          </div>
                        );
                      })()}

                      {(() => {
                        const items = detail.github_verification.partially_corroborated || [];
                        if (items.length === 0) return null;
                        return (
                          <div className="verif-card verif-card-partial">
                            <div className="verif-card-header">
                              <span className="verif-card-title">PARTIALLY CORROBORATED</span>
                              <span className="verif-card-count">{items.length} claim{items.length !== 1 ? 's' : ''}</span>
                            </div>
                            {renderVerifCardContent(items, true)}
                          </div>
                        );
                      })()}

                      {(() => {
                        const items = detail.github_verification.unverifiable || [];
                        if (items.length === 0) return null;
                        return (
                          <div className="verif-card verif-card-neutral">
                            <div className="verif-card-header">
                              <span className="verif-card-title">! UNVERIFIABLE</span>
                              <span className="verif-card-count">{items.length} claim{items.length !== 1 ? 's' : ''}</span>
                            </div>
                            {renderVerifCardContent(items, true)}
                          </div>
                        );
                      })()}

                      {(() => {
                        const items = detail.github_verification.discrepancies || [];
                        if (items.length === 0) return null;
                        return (
                          <div className="verif-card verif-card-negative">
                            <div className="verif-card-header">
                              <span className="verif-card-title">⚠ DISCREPANCIES</span>
                              <span className="verif-card-count">{items.length} claim{items.length !== 1 ? 's' : ''}</span>
                            </div>
                            {renderVerifCardContent(items, true)}
                          </div>
                        );
                      })()}
                    </div>

                    {(!detail.github_verification.corroborated || detail.github_verification.corroborated.length === 0) &&
                      (!detail.github_verification.partially_corroborated || detail.github_verification.partially_corroborated.length === 0) &&
                      (!detail.github_verification.unverifiable || detail.github_verification.unverifiable.length === 0) && (
                        <div className="empty-state">No GitHub verification data available.</div>
                      )}
                  </>
                ) : (
                  <div className="empty-state">GitHub verification not available for this candidate.</div>
                )}
              </div>
            )}

            {activeTab === "linkedin-verification" && (
              <div className="content-panel">
                <h3>LinkedIn Verification</h3>
                {detail.linkedin_verification ? (
                  <>
                    {/* Profile Header */}
                    <div className="verif-profile-header verif-linkedin-accent">
                      <div className="verif-profile-identity">
                        <span className="verif-profile-name">{detail.linkedin_profile?.name || 'LinkedIn User'}</span>
                        {detail.linkedin_profile?.profile_url && (
                          <a href={detail.linkedin_profile.profile_url} target="_blank" rel="noopener noreferrer" className="verif-profile-link">View Profile ↗</a>
                        )}
                      </div>
                      {detail.linkedin_profile?.headline && (
                        <p className="verif-profile-headline">{detail.linkedin_profile.headline}</p>
                      )}
                    </div>

                    {/* Verification Status Card */}
                    <div className="verif-status-card verif-linkedin-status">
                      <div className="verif-status-card-header">
                        <span className="verif-status-label-title">VERIFICATION STATUS</span>
                        <span className={`verif-status-badge ${detail.linkedin_verification.overall_status === 'CORROBORATED' ? 'verif-status-positive' :
                          detail.linkedin_verification.overall_status === 'DISCREPANCY' ? 'verif-status-negative' :
                            'verif-status-neutral'
                          }`}>{detail.linkedin_verification.overall_status || 'VERIFIED'}</span>
                      </div>
                      <p className="verif-summary-text">{detail.linkedin_verification.summary || 'The LinkedIn profile and resume evidence have been analyzed for consistency.'}</p>
                    </div>

                    {/* Verification Cards Grid */}
                    {detail.linkedin_verification.findings && detail.linkedin_verification.findings.length > 0 && (() => {
                      const corroborated = detail.linkedin_verification.findings.filter(f => f.status === 'CORROBORATED');
                      const partial = detail.linkedin_verification.findings.filter(f => f.status === 'PARTIALLY_CORROBORATED');
                      const unverifiable = detail.linkedin_verification.findings.filter(f => f.status === 'UNVERIFIABLE');
                      const discrepancies = detail.linkedin_verification.findings.filter(f => f.status === 'DISCREPANCY');

                      return (
                        <div className="verif-cards-grid">
                          {corroborated.length > 0 && (
                            <div className="verif-card verif-card-positive">
                              <div className="verif-card-header">
                                <span className="verif-card-title">✓ CORROBORATED</span>
                                <span className="verif-card-count">{corroborated.length} claim{corroborated.length !== 1 ? 's' : ''}</span>
                              </div>
                              {renderVerifCardContent(corroborated, false)}
                            </div>
                          )}
                          {partial.length > 0 && (
                            <div className="verif-card verif-card-partial">
                              <div className="verif-card-header">
                                <span className="verif-card-title">PARTIALLY CORROBORATED</span>
                                <span className="verif-card-count">{partial.length} claim{partial.length !== 1 ? 's' : ''}</span>
                              </div>
                              {renderVerifCardContent(partial, false)}
                            </div>
                          )}
                          {unverifiable.length > 0 && (
                            <div className="verif-card verif-card-neutral">
                              <div className="verif-card-header">
                                <span className="verif-card-title">! UNVERIFIABLE</span>
                                <span className="verif-card-count">{unverifiable.length} claim{unverifiable.length !== 1 ? 's' : ''}</span>
                              </div>
                              {renderVerifCardContent(unverifiable, false)}
                            </div>
                          )}
                          {discrepancies.length > 0 && (
                            <div className="verif-card verif-card-negative">
                              <div className="verif-card-header">
                                <span className="verif-card-title">⚠ DISCREPANCIES</span>
                                <span className="verif-card-count">{discrepancies.length} claim{discrepancies.length !== 1 ? 's' : ''}</span>
                              </div>
                              {renderVerifCardContent(discrepancies, false)}
                            </div>
                          )}
                        </div>
                      );
                    })()}

                    {(!detail.linkedin_verification.findings || detail.linkedin_verification.findings.length === 0) && (
                      <div className="empty-state">No LinkedIn verification findings available.</div>
                    )}
                  </>
                ) : (
                  <div className="empty-state">LinkedIn verification not available for this candidate.</div>
                )}
              </div>
            )}


            {activeTab === "linkedin" && (
              <div className="content-panel">
                <h3>LinkedIn Profile</h3>
                {detail.linkedin_profile ? (
                  <>
                    <div className="linkedin-overview">
                      <h4>{detail.linkedin_profile.name || 'Not specified'}</h4>
                      <p>{detail.linkedin_profile.headline || ''}</p>
                      <p><strong>Location:</strong> {detail.linkedin_profile.location || 'Not specified'}</p>
                      {detail.linkedin_profile.profile_url && (
                        <p><strong>Profile:</strong> <a href={detail.linkedin_profile.profile_url} target="_blank" rel="noopener noreferrer">{detail.linkedin_profile.profile_url}</a></p>
                      )}
                    </div>
                    {detail.linkedin_profile.about && (
                      <div className="linkedin-section">
                        <h4>About</h4>
                        <p>{detail.linkedin_profile.about}</p>
                      </div>
                    )}
                    {detail.linkedin_profile.experience && detail.linkedin_profile.experience.length > 0 && (
                      <div className="linkedin-section">
                        <h4>Experience</h4>
                        {detail.linkedin_profile.experience.map((exp, index) => (
                          <div key={index} className="linkedin-item">
                            <h5>{exp.title || exp.position || 'Not specified'}</h5>
                            <p>{exp.company_name || exp.company || 'Not specified'}</p>
                            {exp.description && <p>{exp.description}</p>}
                          </div>
                        ))}
                      </div>
                    )}
                    {detail.linkedin_profile.education && detail.linkedin_profile.education.length > 0 && (
                      <div className="linkedin-section">
                        <h4>Education</h4>
                        {detail.linkedin_profile.education.map((edu, index) => (
                          <div key={index} className="linkedin-item">
                            <h5>{edu.school_name || edu.institution || 'Not specified'}</h5>
                            <p>{edu.degree || edu.field_of_study || 'Not specified'}</p>
                          </div>
                        ))}
                      </div>
                    )}
                    {detail.linkedin_profile.skills && detail.linkedin_profile.skills.length > 0 && (
                      <div className="linkedin-section">
                        <h4>Skills</h4>
                        <div className="skills-list">
                          {detail.linkedin_profile.skills.map((skill, index) => (
                            <span key={index} className="skill-tag">{skill}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="empty-state">LinkedIn profile not available for this candidate.</div>
                )}
              </div>
            )}

            {activeTab === "resume" && (
              <div className="content-panel">
                <h3>Resume Report</h3>

                {loadingResume ? (
                  <div className="empty-state">Loading resume...</div>
                ) : resumeChunks.length > 0 ? (
                  <div className="resume-content">
                    {resumeChunks.map((chunk, index) => (
                      <div key={index} className="resume-chunk">
                        <div className="chunk-section">{formatDisplayValue(chunk.section)}</div>
                        <p>{renderHighlightedText(chunk.text, chunk.chunk_id)}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">No resume data available.</div>
                )}
              </div>
            )}

          </div>

          {/* Modal Footer */}
          <div className="modal-footer">
            <button className="secondary modal-close" onClick={onClose} type="button">
              Close
            </button>
          </div>
        </section>

        {/* Standalone Floating Evidence Legend Card (OUTSIDE main modal) */}
        <FloatingEvidenceLegend />
      </div>
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

// Helper function for rendering GPT-4 / GPT-5 Side-by-Side Comparison Matrix
function renderComparisonMatrix(resultObj, title) {
  if (!resultObj) {
    return <div className="empty-state">{title} loading or unavailable.</div>;
  }

  const candidates = resultObj.candidates || [];
  if (candidates.length === 0) {
    return (
      <div className="tab-panel">
        <div className="evidence-card summary-card">
          <div className="card-label">AI COMPARISON SUMMARY</div>
          <p className="summary-text">{resultObj.comparison_summary || "No comparison summary provided."}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="tab-panel matrix-panel">
      {/* 1. AI Comparison Summary */}
      <div className="evidence-card summary-card">
        <div className="card-label">AI COMPARISON SUMMARY</div>
        <p className="summary-text">{resultObj.comparison_summary || "No comparison summary provided."}</p>
      </div>

      {/* 2. Side-by-Side Candidate Comparison Matrix */}
      <div className="matrix-container">
        <div
          className="matrix-grid"
          style={{
            gridTemplateColumns: `repeat(${candidates.length}, minmax(260px, 1fr))`
          }}
        >
          {/* Header Row: Candidate Names */}
          <div className="matrix-row header-row">
            {candidates.map((cand, idx) => (
              <div key={`header-${cand.candidate_id || idx}`} className="matrix-cell header-cell">
                <span className="candidate-col-label">Candidate {idx + 1}</span>
                <h4 className="candidate-col-name">{cand.candidate_name || `Candidate ${idx + 1}`}</h4>
              </div>
            ))}
          </div>

          {/* Row 1: STRENGTHS */}
          <div className="matrix-row strengths-row">
            {candidates.map((cand, idx) => (
              <div key={`strength-${cand.candidate_id || idx}`} className="matrix-cell strength-cell">
                <div className="matrix-section-col-label">STRENGTHS</div>
                <div className="chips-container">
                  {(cand.strengths || []).map((point, pIdx) => (
                    <div key={pIdx} className="matrix-chip strength-chip">
                      {formatDisplayValue(point)}
                    </div>
                  ))}
                  {(!cand.strengths || cand.strengths.length === 0) && (
                    <span className="muted-text">None specified</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Row 2: GAPS */}
          <div className="matrix-row gaps-row">
            {candidates.map((cand, idx) => (
              <div key={`gap-${cand.candidate_id || idx}`} className="matrix-cell gap-cell">
                <div className="matrix-section-col-label">GAPS</div>
                <div className="chips-container">
                  {(cand.gaps || []).map((point, pIdx) => (
                    <div key={pIdx} className="matrix-chip gap-chip">
                      {formatDisplayValue(point)}
                    </div>
                  ))}
                  {(!cand.gaps || cand.gaps.length === 0) && (
                    <span className="muted-text">None specified</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Row 3: JD COVERAGE */}
          <div className="matrix-row coverage-row">
            {candidates.map((cand, idx) => {
              const coverageList = cand.jd_coverage || cand.evidence || [];
              return (
                <div key={`coverage-${cand.candidate_id || idx}`} className="matrix-cell coverage-cell">
                  <div className="matrix-section-col-label">JD COVERAGE</div>
                  <div className="chips-container">
                    {coverageList.map((point, pIdx) => (
                      <div key={pIdx} className="matrix-chip coverage-chip">
                        {formatDisplayValue(point)}
                      </div>
                    ))}
                    {coverageList.length === 0 && (
                      <span className="muted-text">None specified</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function ComparisonModal({
  analysisSessionId,
  selectedCandidates,
  result,
  detailMap,
  onClose,
  onToggleCandidate
}) {
  const [activeTab, setActiveTab] = useState("evidence");
  const [loading, setLoading] = useState(false);
  const [evidenceResult, setEvidenceResult] = useState(null);
  const [gpt4Result, setGpt4Result] = useState(null);
  const [gpt5Result, setGpt5Result] = useState(null);
  const [error, setError] = useState(null);
  const [hasRunComparisons, setHasRunComparisons] = useState(false);

  // Separate shortlist selection state (initially empty so all checkboxes start unchecked)
  const [shortlistSelected, setShortlistSelected] = useState(new Set());
  const [shortlistedIds, setShortlistedIds] = useState(new Set());
  const [isShortlisting, setIsShortlisting] = useState(false);
  const [shortlistNotice, setShortlistNotice] = useState("");

  // Persist comparison results to localStorage with isOpen flag
  useEffect(() => {
    if (evidenceResult || gpt4Result || gpt5Result) {
      const comparisonData = {
        evidenceResult,
        gpt4Result,
        gpt5Result,
        candidateIds: Array.from(selectedCandidates),
        analysisSessionId,
        timestamp: Date.now(),
        isOpen: true
      };
      localStorage.setItem('comparisonResults', JSON.stringify(comparisonData));
    }
  }, [evidenceResult, gpt4Result, gpt5Result, selectedCandidates, analysisSessionId]);

  // Restore comparison results on mount
  useEffect(() => {
    const savedComparison = localStorage.getItem('comparisonResults');
    if (savedComparison) {
      try {
        const comparisonData = JSON.parse(savedComparison);
        // Only restore if it belongs to current analysis session
        if (comparisonData.analysisSessionId === analysisSessionId &&
          Date.now() - comparisonData.timestamp < 24 * 60 * 60 * 1000) {
          setEvidenceResult(comparisonData.evidenceResult);
          setGpt4Result(comparisonData.gpt4Result);
          setGpt5Result(comparisonData.gpt5Result);
          setHasRunComparisons(true);
        }
      } catch (err) {
        console.error('Failed to restore comparison results:', err);
      }
    }
  }, [analysisSessionId]);

  // Handle closing modal while updating persistent isOpen state
  const handleCloseModal = () => {
    localStorage.setItem('isComparisonOpen', 'false');
    const savedComparison = localStorage.getItem('comparisonResults');
    if (savedComparison) {
      try {
        const compData = JSON.parse(savedComparison);
        compData.isOpen = false;
        localStorage.setItem('comparisonResults', JSON.stringify(compData));
      } catch (e) { }
    }
    onClose();
  };

  // Run comparisons only once on mount if results aren't already loaded
  useEffect(() => {
    if (candidateIds.length >= 2 && !hasRunComparisons && !evidenceResult && !gpt4Result && !gpt5Result) {
      runComparisons();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const candidateIds = useMemo(() => {
    let ids = [];
    if (selectedCandidates) {
      if (Array.isArray(selectedCandidates)) ids = selectedCandidates;
      else if (selectedCandidates instanceof Set) ids = Array.from(selectedCandidates);
    }
    if (ids.length === 0) {
      const saved = localStorage.getItem('comparisonResults');
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (parsed.candidateIds && Array.isArray(parsed.candidateIds) && parsed.candidateIds.length > 0) {
            ids = parsed.candidateIds;
          }
        } catch (e) { }
      }
    }
    if (ids.length === 0 && result?.ranking) {
      ids = result.ranking.map(r => r.resume_id);
    }
    return ids;
  }, [selectedCandidates, result]);

  const candidateDetails = useMemo(() => {
    return candidateIds.map(id => {
      const detail = detailMap?.get ? detailMap.get(id) : null;
      const rankingRow = (result?.ranking || []).find(r => r.resume_id === id);
      return {
        resume_id: id,
        name: detail?.resume_name || rankingRow?.resume_name || id,
        match_score: rankingRow?.match_score ?? (detail?.match_score || 0),
        fit: rankingRow?.fit || detail?.fit || 'Moderate',
        detail: detail || rankingRow || {}
      };
    });
  }, [candidateIds, detailMap, result]);

  const runComparisons = async () => {
    setLoading(true);
    setError(null);

    try {
      // Run all three comparison APIs in parallel
      const [evidenceRes, gpt4Res, gpt5Res] = await Promise.allSettled([
        fetch(`${API_BASE_URL}/api/evidence-assessment`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            candidate_ids: candidateIds,
            jd_info: result.job_description || {}
          })
        }),
        fetch(`${API_BASE_URL}/api/compare-candidates-gpt4`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            candidate_ids: candidateIds,
            jd_info: result.job_description || {}
          })
        }),
        fetch(`${API_BASE_URL}/api/compare-candidates`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            candidate_ids: candidateIds,
            jd_info: result.job_description || {}
          })
        })
      ]);

      // Handle evidence assessment result
      if (evidenceRes.status === 'fulfilled' && evidenceRes.value.ok) {
        const data = await evidenceRes.value.json();
        setEvidenceResult(data);
      } else {
        console.warn('Evidence assessment failed');
      }

      // Handle GPT-4 result
      if (gpt4Res.status === 'fulfilled' && gpt4Res.value.ok) {
        const data = await gpt4Res.value.json();
        setGpt4Result(data);
      } else {
        console.warn('GPT-4 comparison failed');
      }

      // Handle GPT-5 result
      if (gpt5Res.status === 'fulfilled' && gpt5Res.value.ok) {
        const data = await gpt5Res.value.json();
        setGpt5Result(data);
      } else {
        console.warn('GPT-5 comparison failed');
      }

      setHasRunComparisons(true);

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Run comparisons when modal opens with new candidates
  useEffect(() => {
    if (candidateIds.length >= 2 && !hasRunComparisons && !evidenceResult && !gpt4Result && !gpt5Result) {
      runComparisons();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Determine top candidate from GPT-4 results
  const topCandidate = useMemo(() => {
    if (!gpt4Result || !gpt4Result.candidates || gpt4Result.candidates.length === 0) {
      return null;
    }
    // Use the first candidate from GPT-4 results as top (backend may rank them)
    const topId = gpt4Result.candidates[0].candidate_id;
    return candidateDetails.find(c => c.resume_id === topId);
  }, [gpt4Result, candidateDetails]);

  const handleShortlistSelected = async () => {
    if (shortlistSelected.size === 0) {
      alert('Please select at least 1 candidate to shortlist.');
      return;
    }
    setIsShortlisting(true);
    setShortlistNotice('');

    try {
      const userJson = localStorage.getItem('recruiter.user');
      const user = userJson ? JSON.parse(userJson) : null;
      const userId = user?.id || user?.email || 'demo_user';

      // 1. Fetch existing shortlists
      const getShortlistsResponse = await fetch(`${API_BASE_URL}/api/shortlists?user_id=${encodeURIComponent(userId)}`);
      if (!getShortlistsResponse.ok) {
        throw new Error('Failed to fetch existing shortlists');
      }
      const shortlistsData = await getShortlistsResponse.json();
      const existingShortlists = shortlistsData.shortlists || [];

      // 2. Find matching shortlist or create new
      const currentJdString = JSON.stringify(result?.job_description || {}, Object.keys(result?.job_description || {}).sort());
      let matchingShortlist = existingShortlists.find(s =>
        JSON.stringify(s.job_description || {}, Object.keys(s.job_description || {}).sort()) === currentJdString &&
        s.status === 'active'
      );

      let shortlistId;
      if (matchingShortlist) {
        shortlistId = matchingShortlist.shortlist_id;
      } else {
        const createResponse = await fetch(`${API_BASE_URL}/api/shortlists/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            job_description: result?.job_description || {},
            user_id: userId,
            created_by_role: 'recruiter',
            evidence_assessment_snapshot: evidenceResult || null
          })
        });
        if (!createResponse.ok) {
          const errorData = await createResponse.json();
          throw new Error(errorData.detail || 'Failed to create shortlist');
        }
        const createData = await createResponse.json();
        shortlistId = createData.shortlist.shortlist_id;
      }

      // 3. Add selected candidates to shortlist using existing API
      let addedCount = 0;
      const newlyShortlisted = new Set(shortlistedIds);
      for (const resumeId of shortlistSelected) {
        const candidateData = detailMap.get(resumeId);
        const rankingRow = (result?.ranking || []).find(r => r.resume_id === resumeId);

        const addResponse = await fetch(`${API_BASE_URL}/api/shortlists/${shortlistId}/candidates?user_id=${encodeURIComponent(userId)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            resume_id: resumeId,
            candidate_name: candidateData?.resume_name || rankingRow?.resume_name || 'Unknown',
            match_score: rankingRow?.match_score || 0,
            match_position: rankingRow?.fit || 'Unknown',
            evidence_snapshot: {
              strengths: candidateData?.strengths || [],
              gaps: candidateData?.gaps || [],
              jd_coverage: candidateData?.jd_coverage || [],
              evidence: candidateData?.matching_evidence || []
            }
          })
        });

        if (addResponse.ok) {
          addedCount++;
          newlyShortlisted.add(resumeId);

          // 1. Un-remove candidate if previously removed from assessments
          try {
            const savedRemoved = localStorage.getItem("recruiter.assessment_removed_candidates");
            if (savedRemoved) {
              const removedArr = JSON.parse(savedRemoved);
              const nextRemoved = removedArr.filter((id) => String(id) !== String(resumeId));
              localStorage.setItem("recruiter.assessment_removed_candidates", JSON.stringify(nextRemoved));
            }
          } catch (e) {
            console.error("Failed to update removed candidates:", e);
          }

          // 2. Append/Update to assessment records in local store
          const activeJd = result?.job_description || result?.job_description_summary || {};
          const jobRole = activeJd.job_title || activeJd.title || activeJd.role || activeJd.position || "Engineer";

          createOrUpdateAssessment(resumeId, {
            resume_id: resumeId,
            candidate_name: candidateData?.resume_name || rankingRow?.resume_name || 'Unknown',
            job_role: jobRole,
            shortlist_id: shortlistId,
            match_score: rankingRow?.match_score || 0,
            fit: rankingRow?.fit || 'Good Fit'
          });
        }
      }

      setShortlistedIds(newlyShortlisted);
      setShortlistSelected(new Set());
      setShortlistNotice(`Successfully added ${addedCount} candidate(s) to Shortlisted Candidates!`);
      setTimeout(() => setShortlistNotice(''), 4000);
    } catch (err) {
      console.error('Shortlist error from Compare modal:', err);
      alert(`Shortlist failed: ${err.message}`);
    } finally {
      setIsShortlisting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={handleCloseModal}>
      <section
        className="detail-modal comparison-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="comparison-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="detail-header">
          <div>
            <h2 id="comparison-modal-title">Candidate Comparison</h2>
            <span>{candidateIds.length} candidate{candidateIds.length !== 1 ? 's' : ''} under comparison</span>
          </div>
          <button className="secondary modal-close" onClick={handleCloseModal} type="button">
            Close
          </button>
        </div>

        {loading && (
          <div className="loading-state">
            <Loader2 className="spin" size={24} />
            <p>Analyzing selected candidates...</p>
          </div>
        )}

        {error && (
          <div className="error">
            Comparison failed: {error}
          </div>
        )}

        {!loading && !error && (
          <div className="comparison-content">
            {/* Shortlist Candidates Section (Independent Selection) */}
            <div className="comparison-section shortlist-section">
              <div className="shortlist-section-header">
                <h3>Shortlist Candidates</h3>
                <button
                  className="shortlist-btn"
                  onClick={handleShortlistSelected}
                  disabled={shortlistSelected.size === 0 || isShortlisting}
                  type="button"
                >
                  {isShortlisting ? <Loader2 className="spin" size={16} /> : null}
                  Shortlist Selected ({shortlistSelected.size})
                </button>
              </div>
              {shortlistNotice && (
                <div className="shortlist-success-notice">
                  {shortlistNotice}
                </div>
              )}
              <div className="shortlist-candidate-list">
                {candidateDetails.map(candidate => (
                  <div key={`shortlist-${candidate.resume_id}`} className="shortlist-candidate-row">
                    <div className="shortlist-row-left">
                      <input
                        type="checkbox"
                        className="shortlist-checkbox-input"
                        checked={shortlistSelected.has(candidate.resume_id)}
                        onChange={() => {
                          setShortlistSelected(prev => {
                            const next = new Set(prev);
                            if (next.has(candidate.resume_id)) {
                              next.delete(candidate.resume_id);
                            } else {
                              next.add(candidate.resume_id);
                            }
                            return next;
                          });
                        }}
                      />
                      <div className="shortlist-candidate-name">
                        <strong>{candidate.name}</strong>
                        {shortlistedIds.has(candidate.resume_id) && (
                          <span className="shortlisted-badge">Shortlisted ✓</span>
                        )}
                      </div>
                    </div>
                    <div className="shortlist-candidate-score">
                      <span>Match Score {candidate.match_score}%</span>
                    </div>
                    <div className="shortlist-candidate-fit">
                      <span className={`fit-pill fit-${candidate.fit?.toLowerCase().replaceAll(' ', '-')}`}>
                        {candidate.fit}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* AI Overview (Restored Compact Summary directly below Shortlist Candidates) */}
            {evidenceResult && (
              <div className="ai-overview-card">
                <div className="ai-overview-header">
                  <h4>AI Overview</h4>
                </div>
                {(() => {
                  const strongestName = evidenceResult.strongest_candidate || evidenceResult.strongestCandidate || 'Not specified';
                  const matchedCandidate = candidateDetails.find(c =>
                    c.name === strongestName ||
                    c.resume_id === strongestName ||
                    strongestName.toLowerCase().includes(c.name.toLowerCase()) ||
                    c.name.toLowerCase().includes(strongestName.toLowerCase())
                  );
                  const displayName = matchedCandidate?.name || strongestName;
                  const matchScore = matchedCandidate?.match_score ?? null;
                  const fitLevel = matchedCandidate?.fit || null;

                  return (
                    <div className="ai-overview-body">
                      <div className="ai-overview-top-line">
                        <div className="ai-overview-candidate">
                          <span className="ai-overview-label">Strongest Candidate:</span>
                          <strong className="ai-overview-name">{displayName}</strong>
                        </div>
                        {(matchScore !== null || fitLevel !== null) && (
                          <div className="ai-overview-metrics">
                            {matchScore !== null && <span className="ai-overview-score">Match Score: {matchScore}%</span>}
                            {fitLevel !== null && (
                              <span className={`fit-pill fit-${fitLevel.toLowerCase().replaceAll(' ', '-')}`}>
                                {fitLevel}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                      {evidenceResult.assessment_summary && (
                        <p className="ai-overview-explanation">
                          {evidenceResult.assessment_summary}
                        </p>
                      )}
                    </div>
                  );
                })()}
              </div>
            )}

            {/* Four Analysis Sections */}
            <div className="comparison-tabs">
              <button
                className={activeTab === "evidence" ? "active" : ""}
                onClick={() => setActiveTab("evidence")}
                type="button"
              >
                AI Evidence Assessment
              </button>
              <button
                className={activeTab === "gpt4" ? "active" : ""}
                onClick={() => setActiveTab("gpt4")}
                type="button"
              >
                GPT-4 Assessment
              </button>
              <button
                className={activeTab === "gpt5" ? "active" : ""}
                onClick={() => setActiveTab("gpt5")}
                type="button"
              >
                GPT-5 Assessment
              </button>
              <button
                className={activeTab === "jd" ? "active" : ""}
                onClick={() => setActiveTab("jd")}
                type="button"
              >
                JD vs Resumes
              </button>
            </div>

            <div className="comparison-tab-content">
              {activeTab === "evidence" && (
                <div className="tab-panel evidence-panel">
                  <div className="evidence-header-title">
                    <h3>AI Evidence Assessment</h3>
                    <p>Evidence-grounded evaluation comparing candidate qualifications to job requirements</p>
                  </div>

                  {evidenceResult ? (
                    <>
                      {/* Section 1: Strongest Candidate */}
                      <div className="evidence-card strongest-candidate-card">
                        <div className="card-label">STRONGEST CANDIDATE</div>
                        {(() => {
                          const strongestName = evidenceResult.strongest_candidate || 'Not specified';
                          const matchedCandidate = candidateDetails.find(c =>
                            c.name === strongestName ||
                            c.resume_id === strongestName ||
                            strongestName.toLowerCase().includes(c.name.toLowerCase())
                          );
                          const displayName = matchedCandidate?.name || strongestName;
                          const matchScore = matchedCandidate?.match_score ?? 'N/A';
                          const fitLevel = matchedCandidate?.fit || 'N/A';

                          return (
                            <div className="strongest-candidate-content">
                              <div className="strongest-title-row">
                                <h4 className="candidate-name">{displayName}</h4>
                                {matchScore !== 'N/A' && (
                                  <span className="match-score-badge">Match Score: {matchScore}%</span>
                                )}
                              </div>
                              {fitLevel !== 'N/A' && (
                                <div className="fit-badge-row">
                                  <span className="fit-level-pill">Fit Level: {fitLevel}</span>
                                </div>
                              )}
                            </div>
                          );
                        })()}
                      </div>

                      {/* Section 2: Why Selected (Assessment Summary) */}
                      <div className="evidence-card assessment-summary-card">
                        <div className="card-label">ASSESSMENT SUMMARY</div>
                        <div className="summary-body">
                          <p>{evidenceResult.assessment_summary || 'No detailed assessment summary available.'}</p>
                        </div>
                      </div>

                      {/* Section 3: Supporting Points */}
                      <div className="evidence-card supporting-points-card">
                        <div className="card-label">SUPPORTING POINTS</div>
                        <div className="supporting-points-list">
                          {(evidenceResult.supporting_points || []).map((point, idx) => (
                            <div key={idx} className="supporting-point-item">
                              <div className="check-icon">✓</div>
                              <p className="point-text">{point}</p>
                            </div>
                          ))}
                          {(!evidenceResult.supporting_points || evidenceResult.supporting_points.length === 0) && (
                            <div className="empty-state">No specific supporting points provided.</div>
                          )}
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="empty-state">AI Evidence Assessment loading or unavailable.</div>
                  )}
                </div>
              )}

              {activeTab === "gpt4" && renderComparisonMatrix(gpt4Result, "GPT-4 Assessment")}

              {activeTab === "gpt5" && renderComparisonMatrix(gpt5Result, "GPT-5 Assessment")}

              {activeTab === "jd" && (() => {
                const jd = result?.job_description || {};
                const rawCriteria = new Set();

                const parseList = (val) => {
                  if (!val) return [];
                  if (Array.isArray(val)) return val.map(s => String(s).trim()).filter(Boolean);
                  return String(val).split(/[,;/]/).map(s => s.trim()).filter(Boolean);
                };

                parseList(jd.primary_skills || jd.primarySkills || jd.required_skills).forEach(s => rawCriteria.add(s));
                parseList(jd.secondary_skills || jd.secondarySkills).forEach(s => rawCriteria.add(s));

                if (jd.experience || jd.experience_required || jd.total_experience) {
                  rawCriteria.add("Experience");
                }
                if (jd.education || jd.degree) {
                  rawCriteria.add("Education");
                }

                candidateDetails.forEach(cand => {
                  const matchingEv = cand.detail?.matching_evidence || [];
                  matchingEv.forEach(item => {
                    if (item.skill) rawCriteria.add(item.skill);
                  });
                });

                if (rawCriteria.size === 0) {
                  ["Python", "SQL", "Machine Learning", "NLP", "Education", "Experience"].forEach(s => rawCriteria.add(s));
                }

                const criteriaList = Array.from(rawCriteria).filter(c => c && typeof c === 'string' && c.trim().length > 0);

                const getCandidateEvidence = (criterion, cand) => {
                  const critLower = criterion.toLowerCase().trim();
                  const detail = cand.detail || {};
                  const matchingEv = detail.matching_evidence || [];

                  const matched = matchingEv.find(ev =>
                    ev.skill && (ev.skill.toLowerCase().includes(critLower) || critLower.includes(ev.skill.toLowerCase()))
                  );

                  if (matched) {
                    const matchType = (matched.match_type || matched.status || '').toLowerCase();
                    let status = 'Strong';
                    if (matchType.includes('weak') || matchType.includes('partial') || matchType.includes('limited')) {
                      status = 'Weak';
                    } else if (matchType.includes('not') || matchType.includes('missing') || matchType.includes('unavailable') || matchType.includes('none')) {
                      status = 'Unavailable';
                    }
                    return {
                      status,
                      reason: matched.evidence || `${criterion} demonstrated in candidate evaluation.`
                    };
                  }

                  if (critLower === 'experience') {
                    const expVal = detail.total_experience || detail.experience || (cand.match_score > 50 ? 'Strong' : 'Weak');
                    const status = expVal === 'Weak' ? 'Weak' : 'Strong';
                    const reason = detail.total_experience
                      ? `${detail.total_experience} total experience.`
                      : `Relevant domain experience evaluated for job requirements.`;
                    return { status, reason };
                  }

                  if (critLower === 'education') {
                    const edu = detail.education || detail.degree;
                    if (edu) {
                      return { status: 'Strong', reason: String(edu) };
                    }
                    return { status: 'Weak', reason: 'Education background evaluated against role criteria.' };
                  }

                  const skills = parseList(detail.skills || detail.technical_skills);
                  if (skills.some(s => s.toLowerCase().includes(critLower) || critLower.includes(s.toLowerCase()))) {
                    return {
                      status: 'Strong',
                      reason: `${criterion} explicitly listed in technical skills.`
                    };
                  }

                  const gptCands = (gpt4Result?.candidates || []).concat(gpt5Result?.candidates || []);
                  const candGpt = gptCands.find(c => c.candidate_id === cand.resume_id || c.candidate_name === cand.name);
                  if (candGpt) {
                    const inStrengths = (candGpt.strengths || []).find(s => String(s).toLowerCase().includes(critLower));
                    if (inStrengths) {
                      return { status: 'Strong', reason: String(inStrengths) };
                    }
                    const inGaps = (candGpt.gaps || []).find(g => String(g).toLowerCase().includes(critLower));
                    if (inGaps) {
                      return { status: 'Weak', reason: String(inGaps) };
                    }
                  }

                  return {
                    status: 'Unavailable',
                    reason: `No evidence of ${criterion} skills found.`
                  };
                };

                return (
                  <div className="tab-panel jd-comparison-panel">
                    <div className="jd-vs-resumes-container">
                      <div className="jd-table-wrapper">
                        <table className="jd-comparison-table">
                          <thead>
                            <tr>
                              <th className="criteria-header-cell">COMPARISON CRITERIA</th>
                              {candidateDetails.map(cand => (
                                <th key={`hdr-${cand.resume_id}`} className="candidate-header-cell">
                                  <div className="candidate-header-title">{cand.name}</div>
                                  <div className="candidate-header-meta">
                                    <span className="match-score-pill">Match: {cand.match_score}%</span>
                                    <span className={`fit-pill fit-${cand.fit?.toLowerCase().replaceAll(' ', '-')}`}>
                                      {cand.fit}
                                    </span>
                                  </div>
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {criteriaList.map((criterion, idx) => (
                              <tr key={`row-${idx}`}>
                                <td className="criteria-cell">
                                  <strong>{criterion}</strong>
                                </td>
                                {candidateDetails.map(cand => {
                                  const ev = getCandidateEvidence(criterion, cand);
                                  const statusClass = `status-${ev.status.toLowerCase()}`;
                                  return (
                                    <td key={`cell-${cand.resume_id}-${idx}`} className="evidence-cell">
                                      <div className="evidence-cell-content">
                                        <span className={`status-pill ${statusClass}`}>
                                          {ev.status}
                                        </span>
                                        <p className="evidence-reason-text">{ev.reason}</p>
                                      </div>
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Selection validation message */}
            {candidateIds.length < 2 && (
              <div className="warning">
                Select at least 2 candidates to compare.
              </div>
            )}

            {/* Refresh comparison button */}
            {candidateIds.length >= 2 && (
              <div className="comparison-actions">
                <button
                  onClick={runComparisons}
                  disabled={loading}
                  type="button"
                >
                  {loading ? <Loader2 className="spin" size={16} /> : null}
                  {loading ? 'Comparing...' : 'Refresh Comparison'}
                </button>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function SkillColumn({ title, items }) {
  const safeItems = Array.isArray(items) ? items : [];
  const typeClass = (title || "").toLowerCase();

  return (
    <div className={`skill-column skill-column-${typeClass}`}>
      <span className="skill-column-title">{title}</span>
      <ul className="skill-column-list">
        {(safeItems.length ? safeItems : ["None"]).map((item, index) => (
          <li key={`${formatDisplayValue(item)}-${index}`} className="skill-column-item">
            {formatDisplayValue(item)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ShortlistedCandidatesPage({ result }) {
  const [shortlists, setShortlists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedShortlistId, setSelectedShortlistId] = useState(null);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [error, setError] = useState(null);
  const [isJdExpanded, setIsJdExpanded] = useState(true);
  const [actionNotice, setActionNotice] = useState("");
  const [selectedForAssessment, setSelectedForAssessment] = useState(new Set());

  const handleAddToAssessment = (resumeIds) => {
    if (!resumeIds || resumeIds.length === 0) return;

    let currentSelected = new Set();
    try {
      const saved = localStorage.getItem("recruiter.selected_assessment_candidates");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          parsed.forEach((id) => currentSelected.add(String(id)));
        }
      }
    } catch (err) {
      console.error("Error reading selected assessment candidates:", err);
    }

    resumeIds.forEach((id) => currentSelected.add(String(id)));
    localStorage.setItem(
      "recruiter.selected_assessment_candidates",
      JSON.stringify(Array.from(currentSelected))
    );

    setActionNotice(`Added ${resumeIds.length} candidate(s) to Assessment Management`);
    setSelectedForAssessment(new Set());
    setTimeout(() => setActionNotice(""), 3500);
  };

  const detailMap = useMemo(() => {
    if (!result?.top_details) return null;
    return new Map(
      result.top_details.map((detail) => [detail.resume_id, detail])
    );
  }, [result]);

  const userJson = localStorage.getItem("recruiter.user");
  const user = userJson ? JSON.parse(userJson) : null;
  const userId = user?.id || user?.email || "demo_user";

  const loadShortlists = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/shortlists?user_id=${encodeURIComponent(userId)}`
      );
      if (!response.ok) {
        throw new Error("Failed to fetch shortlists");
      }
      const data = await response.json();
      setShortlists(data.shortlists || []);
    } catch (err) {
      console.error("Failed to load shortlists:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadShortlists();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRemoveJob = async (shortlistId, jobTitle) => {
    const confirmed = window.confirm(
      "Remove this job shortlist and all shortlisted candidates from it?"
    );
    if (!confirmed) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/shortlists/${shortlistId}?user_id=${encodeURIComponent(userId)}`,
        { method: "DELETE" }
      );
      if (!response.ok) {
        throw new Error("Failed to delete job shortlist");
      }

      setShortlists((prev) => prev.filter((s) => s.shortlist_id !== shortlistId));
      setSelectedShortlistId(null);
      setActionNotice(`Removed job shortlist "${jobTitle || "Position"}" successfully`);
      setTimeout(() => setActionNotice(""), 3000);
    } catch (err) {
      console.error("Delete shortlist error:", err);
      alert(`Could not remove job: ${err.message}`);
    }
  };

  const handleRemoveCandidate = async (shortlistId, resumeId, candidateName) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/shortlists/${shortlistId}/candidates/${encodeURIComponent(resumeId)}?user_id=${encodeURIComponent(userId)}`,
        { method: "DELETE" }
      );
      if (!response.ok) {
        throw new Error("Failed to remove candidate from shortlist");
      }

      setShortlists((prevShortlists) => {
        return prevShortlists.map((shortlist) => {
          if (shortlist.shortlist_id === shortlistId) {
            const updatedCandidates = (
              shortlist.candidates ||
              shortlist.shortlisted_candidates ||
              []
            ).filter((c) => c.resume_id !== resumeId);
            return {
              ...shortlist,
              candidates: updatedCandidates,
              shortlisted_candidates: updatedCandidates,
            };
          }
          return shortlist;
        });
      });

      setActionNotice(`Removed ${candidateName || "candidate"} from shortlist`);
      setTimeout(() => setActionNotice(""), 3000);
    } catch (err) {
      console.error("Remove candidate error:", err);
      alert(`Could not remove candidate: ${err.message}`);
    }
  };

  const handleViewCandidate = (cand) => {
    if (detailMap && detailMap.get && detailMap.get(cand.resume_id)) {
      setSelectedDetail(detailMap.get(cand.resume_id));
      return;
    }
    const detailObj = {
      resume_id: cand.resume_id,
      resume_name: cand.candidate_name || cand.resume_name || cand.resume_id,
      match_score: cand.match_score || 0,
      fit: cand.match_position || cand.fit || "Good Fit",
      strengths: cand.strengths || [],
      gaps: cand.gaps || [],
      jd_coverage: cand.jd_coverage || [],
      matching_evidence: cand.evidence || [],
      candidate_grading: cand.candidate_grading || null,
    };
    setSelectedDetail(detailObj);
  };

  const getJdSummary = (jd) => {
    if (!jd || typeof jd !== "object") {
      return {
        title: "Job Position",
        experience: "N/A",
        primarySkills: [],
        secondarySkills: [],
        education: "N/A",
      };
    }

    const title =
      jd.title ||
      jd.role ||
      jd.job_title ||
      jd.position ||
      "Job Position";
    const experience =
      jd.experience ||
      jd.experience_required ||
      jd.total_experience ||
      "N/A";

    let primarySkills = [];
    if (jd.primary_skills || jd.primarySkills || jd.required_skills) {
      const p = jd.primary_skills || jd.primarySkills || jd.required_skills;
      primarySkills = Array.isArray(p)
        ? p
        : String(p)
          .split(/[,;/]/)
          .map((s) => s.trim())
          .filter(Boolean);
    }

    let secondarySkills = [];
    if (jd.secondary_skills || jd.secondarySkills) {
      const s = jd.secondary_skills || jd.secondarySkills;
      secondarySkills = Array.isArray(s)
        ? s
        : String(s)
          .split(/[,;/]/)
          .map((s) => s.trim())
          .filter(Boolean);
    }

    const education = jd.education || jd.degree || "N/A";

    return { title, experience, primarySkills, secondarySkills, education };
  };

  const getJdSubtitle = (jd) => {
    if (!jd || typeof jd !== "object") return "Open Position";
    const exp =
      jd.experience || jd.experience_required || jd.total_experience;
    let skills = [];
    if (jd.primary_skills || jd.primarySkills || jd.required_skills) {
      const p = jd.primary_skills || jd.primarySkills || jd.required_skills;
      skills = Array.isArray(p)
        ? p
        : String(p)
          .split(/[,;/]/)
          .map((s) => s.trim())
          .filter(Boolean);
    }

    if (exp && skills.length > 0) {
      return `${exp} exp • ${skills.slice(0, 2).join(", ")}`;
    } else if (exp) {
      return `${exp} experience`;
    } else if (skills.length > 0) {
      return skills.slice(0, 3).join(", ");
    }
    return jd.role || jd.position || "Active Position";
  };

  const activeShortlists = shortlists.filter((s) => s.status !== "archived");
  const selectedShortlist = selectedShortlistId
    ? activeShortlists.find((s) => s.shortlist_id === selectedShortlistId)
    : null;

  return (
    <div className="shortlisted-page-container">
      {/* 1. TOP PAGE HEADER */}
      <div className="shortlisted-page-header">
        <h2>Shortlisted Candidates</h2>
        <p>Review positions and manage shortlisted candidate profiles</p>
      </div>

      {actionNotice && (
        <div className="shortlist-action-notice">{actionNotice}</div>
      )}

      {loading && (
        <div className="loading-state">
          <Loader2 className="spin" size={24} />
          <p>Loading shortlisted positions...</p>
        </div>
      )}

      {error && (
        <div className="error">Failed to load shortlists: {error}</div>
      )}

      {!loading && !error && activeShortlists.length === 0 && (
        <div className="empty-state-card">
          <FileCheck size={48} className="empty-icon" />
          <h3>No Shortlisted Candidates Yet</h3>
          <p>
            You can shortlist candidates directly from the Analysis results table
            or from the Candidate Comparison modal.
          </p>
        </div>
      )}

      {/* 2. GRID OF JOB CARDS (when not viewing details) */}
      {!loading && !error && activeShortlists.length > 0 && !selectedShortlist && (
        <div className="shortlists-jobs-grid">
          {activeShortlists.map((shortlist) => {
            const jd = shortlist.job_description || {};
            const jdSummary = getJdSummary(jd);
            const candidates =
              shortlist.candidates || shortlist.shortlisted_candidates || [];
            const count = candidates.length;
            const countLabel =
              count === 1 ? "1 Candidate" : `${count} Candidates`;
            const subtitle = getJdSubtitle(jd);

            return (
              <div
                key={shortlist.shortlist_id}
                className="shortlist-job-card"
              >
                <div className="job-card-header">
                  <div className="job-card-badge">
                    <Briefcase size={14} />
                    <span>Role</span>
                  </div>
                  <h3 className="job-card-title">{jdSummary.title}</h3>
                  <p className="job-card-subtitle">{subtitle}</p>
                </div>

                <div className="job-card-stats">
                  <div className="candidate-count-badge">
                    <Users size={16} className="count-icon" />
                    <span className="count-text">{countLabel}</span>
                  </div>
                </div>

                <div className="job-card-footer">
                  <button
                    type="button"
                    className="view-job-details-btn"
                    onClick={() => {
                      setSelectedShortlistId(shortlist.shortlist_id);
                      setIsJdExpanded(true);
                    }}
                  >
                    View Details
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 3. DEDICATED JOB DETAILS VIEW (when a job is selected) */}
      {!loading && !error && selectedShortlist && (
        <div className="shortlist-job-detail-view">
          {/* Back & Action Top Bar */}
          <div className="detail-view-top-bar">
            <button
              type="button"
              className="back-to-grid-btn"
              onClick={() => setSelectedShortlistId(null)}
            >
              <ArrowLeft size={16} />
              <span>Back to All Positions</span>
            </button>
            <button
              type="button"
              className="remove-job-btn"
              onClick={() =>
                handleRemoveJob(
                  selectedShortlist.shortlist_id,
                  getJdSummary(selectedShortlist.job_description).title
                )
              }
            >
              <Trash2 size={15} />
              <span>Remove Job</span>
            </button>
          </div>

          {(() => {
            const jd = selectedShortlist.job_description || {};
            const jdSummary = getJdSummary(jd);
            const candidates =
              selectedShortlist.candidates ||
              selectedShortlist.shortlisted_candidates ||
              [];

            return (
              <>
                {/* Unified Job Requirements Card */}
                <div className="detail-jd-card">
                  <div className="detail-jd-card-header">
                    <div className="detail-jd-header-left">
                      <div className="detail-jd-badge">
                        <Briefcase size={12} />
                        <span>JOB REQUIREMENTS</span>
                      </div>
                      <h2 className="detail-jd-main-title">{jdSummary.title}</h2>
                    </div>
                    <div className="detail-jd-header-right">
                      <span className="detail-candidate-count-tag">
                        <Users size={15} />
                        {candidates.length === 1
                          ? "1 Candidate Shortlisted"
                          : `${candidates.length} Candidates Shortlisted`}
                      </span>
                      <button
                        type="button"
                        className="toggle-jd-btn"
                        onClick={() => setIsJdExpanded((prev) => !prev)}
                      >
                        {isJdExpanded ? "Hide Requirements ▲" : "Show Requirements ▼"}
                      </button>
                    </div>
                  </div>

                  {isJdExpanded ? (
                    <div className="detail-jd-content">
                      <div className="detail-jd-grid">
                        <div className="jd-grid-field">
                          <span className="jd-field-label">JOB TITLE</span>
                          <span className="jd-field-value">{jdSummary.title}</span>
                        </div>
                        <div className="jd-grid-field">
                          <span className="jd-field-label">EXPERIENCE</span>
                          <span className="jd-field-value">{jdSummary.experience}</span>
                        </div>
                        <div className="jd-grid-field jd-grid-field-full">
                          <span className="jd-field-label">PRIMARY SKILLS</span>
                          <div className="skills-pill-row">
                            {jdSummary.primarySkills.length > 0 ? (
                              jdSummary.primarySkills.map((sk, idx) => (
                                <span key={idx} className="jd-skill-pill primary">
                                  {sk}
                                </span>
                              ))
                            ) : (
                              <span className="muted-text">Not Found</span>
                            )}
                          </div>
                        </div>
                        <div className="jd-grid-field jd-grid-field-full">
                          <span className="jd-field-label">SECONDARY SKILLS</span>
                          <div className="skills-pill-row">
                            {jdSummary.secondarySkills.length > 0 ? (
                              jdSummary.secondarySkills.map((sk, idx) => (
                                <span key={idx} className="jd-skill-pill secondary">
                                  {sk}
                                </span>
                              ))
                            ) : (
                              <span className="muted-text">Not Found</span>
                            )}
                          </div>
                        </div>
                        <div className="jd-grid-field jd-grid-field-full">
                          <span className="jd-field-label">EDUCATION</span>
                          <span className="jd-field-value">{jdSummary.education}</span>
                        </div>
                        {Object.entries(jd)
                          .filter(
                            ([key]) =>
                              ![
                                "title",
                                "role",
                                "job_title",
                                "position",
                                "experience",
                                "experience_required",
                                "total_experience",
                                "primary_skills",
                                "primaryskills",
                                "required_skills",
                                "secondary_skills",
                                "secondaryskills",
                                "education",
                                "degree",
                              ].includes(key.toLowerCase())
                          )
                          .map(([key, val]) => (
                            <div key={key} className="jd-grid-field jd-grid-field-full">
                              <span className="jd-field-label">
                                {key.replaceAll("_", " ").toUpperCase()}
                              </span>
                              <span className="jd-field-value">
                                {formatDisplayValue(val)}
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  ) : (
                    <div className="detail-jd-collapsed-summary">
                      <div className="collapsed-summary-item">
                        <span className="collapsed-label">EXPERIENCE:</span>
                        <span className="collapsed-val">{jdSummary.experience}</span>
                      </div>
                      <div className="collapsed-summary-item">
                        <span className="collapsed-label">PRIMARY SKILLS:</span>
                        <span className="collapsed-val">
                          {jdSummary.primarySkills.length > 0
                            ? jdSummary.primarySkills.slice(0, 4).join(", ")
                            : "Not Found"}
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Shortlisted Candidates Section (Main Focus) */}
                <div className="detail-candidates-section">
                  <div className="detail-candidates-header">
                    <div className="detail-candidates-header-left" style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <h3 className="detail-candidates-title">
                        Shortlisted Candidates
                      </h3>
                      <span className="candidates-count-pill">
                        {candidates.length} {candidates.length === 1 ? "candidate" : "candidates"}
                      </span>
                    </div>
                    {candidates.length > 0 && (
                      <button
                        type="button"
                        className="btn-add-selected-assessment"
                        disabled={selectedForAssessment.size === 0}
                        onClick={() => handleAddToAssessment(Array.from(selectedForAssessment))}
                      >
                        <Sparkles size={14} />
                        <span>Add Selected to Assessment ({selectedForAssessment.size})</span>
                      </button>
                    )}
                  </div>

                  {candidates.length === 0 ? (
                    <div className="empty-candidates-notice">
                      <p>0 Candidates currently shortlisted for this position.</p>
                    </div>
                  ) : (
                    <div className="shortlisted-candidates-list">
                      {candidates.map((cand) => (
                        <div
                          key={cand.resume_id}
                          className="shortlisted-candidate-card"
                        >
                          {/* Column 1: Candidate Name & Checkbox */}
                          <div className="cand-col-name" style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                            <input
                              type="checkbox"
                              className="shortlist-cand-checkbox"
                              checked={selectedForAssessment.has(cand.resume_id)}
                              onChange={() => {
                                setSelectedForAssessment((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(cand.resume_id)) {
                                    next.delete(cand.resume_id);
                                  } else {
                                    next.add(cand.resume_id);
                                  }
                                  return next;
                                });
                              }}
                            />
                            <h4 className="cand-name-text">
                              {cand.candidate_name ||
                                cand.resume_name ||
                                cand.resume_id}
                            </h4>
                          </div>

                          {/* Column 2: Match Score */}
                          <div className="cand-col-metric">
                            <span className="metric-label">MATCH SCORE</span>
                            <strong className="metric-score-value">
                              {cand.match_score || 0}%
                            </strong>
                          </div>

                          {/* Column 3: Fit */}
                          <div className="cand-col-metric">
                            <span className="metric-label">FIT</span>
                            <span
                              className={`fit-pill fit-${(
                                cand.match_position ||
                                cand.fit ||
                                "Good"
                              )
                                .toLowerCase()
                                .replaceAll(" ", "-")}`}
                            >
                              {cand.match_position || cand.fit || "Good Fit"}
                            </span>
                          </div>

                          {/* Column 4: Actions */}
                          <div className="cand-col-actions">
                            <button
                              type="button"
                              className="add-to-asm-btn"
                              onClick={() => handleAddToAssessment([cand.resume_id])}
                              title="Add candidate to Assessment Management"
                            >
                              + Add to Assessment
                            </button>
                            <button
                              type="button"
                              className="view-cand-btn"
                              onClick={() => handleViewCandidate(cand)}
                            >
                              View
                            </button>
                            <button
                              type="button"
                              className="remove-cand-btn"
                              onClick={() =>
                                handleRemoveCandidate(
                                  selectedShortlist.shortlist_id,
                                  cand.resume_id,
                                  cand.candidate_name
                                )
                              }
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            );
          })()}
        </div>
      )}

      {selectedDetail && (
        <DetailModal
          detail={selectedDetail}
          onClose={() => setSelectedDetail(null)}
        />
      )}
    </div>
  );
}

export default App;
