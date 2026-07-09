import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Award,
  BriefcaseBusiness,
  CalendarDays,
  CheckCircle2,
  Database,
  FileText,
  Info,
  Loader2,
  RefreshCw,
  Save,
  RotateCcw,
  Search,
  X,
  UploadCloud,
} from "lucide-react";
import {
  defaultClaudeModels,
  defaultGeminiModels,
  defaultOllamaModels,
  defaultProviders,
} from "./defaultModels";
import { defaultPrompts } from "./defaultPrompts";
import SkillsPage from "./pages/dashboard/SkillsPage";
import "./styles.css";

const API_BASE_URL = "http://127.0.0.1:8000";

const defaultGradingWeights = {
  skill_gap: 50,
  years_experience: 20,
  project_experience: 15,
  education: 5,
  seniority: 10,
};

const emptyConfig = {
  ai_provider: "Gemini",
  ollama_model: defaultOllamaModels[0],
  gemini_model: defaultGeminiModels[0],
  claude_model: defaultClaudeModels[0],
  candidate_grading_weights: defaultGradingWeights,
  ...defaultPrompts,
};

function normalizeGradingWeights(weights) {
  const source = weights || {};
  const expectedKeys = Object.keys(defaultGradingWeights);

  if (!expectedKeys.every((key) => Object.hasOwn(source, key))) {
    return { ...defaultGradingWeights };
  }

  const normalized = Object.fromEntries(
    Object.entries(defaultGradingWeights).map(([key, fallback]) => {
      const parsed = Number(source[key]);
      const value = Number.isFinite(parsed) ? Math.round(parsed) : fallback;
      return [key, Math.max(0, Math.min(100, value))];
    }),
  );

  const isLegacyExpandedRubric =
    normalized.skill_gap === 50 &&
    normalized.years_experience === 25 &&
    normalized.project_experience === 25 &&
    normalized.education === 5 &&
    normalized.seniority === 10;

  return isLegacyExpandedRubric ? { ...defaultGradingWeights } : normalized;
}

function getGradingWeightTotal(weights) {
  return Object.values(normalizeGradingWeights(weights)).reduce(
    (total, value) => total + value,
    0,
  );
}

function normalizeConfig(config) {
  const normalizedConfig = {
    ...emptyConfig,
    ...(config || {}),
  };

  normalizedConfig.candidate_grading_weights = normalizeGradingWeights(
    normalizedConfig.candidate_grading_weights,
  );

  for (const key of Object.keys(defaultPrompts)) {
    if (!String(normalizedConfig[key] || "").trim()) {
      normalizedConfig[key] = defaultPrompts[key];
    }
  }

  return normalizedConfig;
}

function getModelConfigKey(provider) {
  if (provider === "Gemini") {
    return "gemini_model";
  }

  if (provider === "Claude") {
    return "claude_model";
  }

  return "ollama_model";
}

function getConfiguredModel(config, provider) {
  return config[getModelConfigKey(provider)];
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

function cleanList(items) {
  if (!Array.isArray(items)) {
    return [];
  }

  return items
    .map((item) => formatDisplayValue(item, ""))
    .filter((item) => item && item.toLowerCase() !== "not found");
}

function formatInsightLabel(key) {
  return String(key)
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function cleanAdditionalInsights(...sources) {
  const insights = [];

  for (const source of sources) {
    if (
      !source ||
      typeof source !== "object" ||
      Array.isArray(source)
    ) {
      continue;
    }

    for (const [key, value] of Object.entries(source)) {
      const displayValue = formatDisplayValue(value, "");

      if (!displayValue || displayValue === "Not Found") {
        continue;
      }

      insights.push({
        label: formatInsightLabel(key),
        value: displayValue,
      });
    }
  }

  return insights;
}

function cleanTimeline(timeline) {
  if (!timeline || !Array.isArray(timeline.timeline)) {
    return {
      totalExperience: formatDisplayValue(timeline?.total_experience),
      rows: [],
    };
  }

  return {
    totalExperience: formatDisplayValue(timeline.total_experience),
    rows: timeline.timeline.filter((item) =>
      Boolean(item && (item.role || item.company || item.summary)),
    ),
  };
}

function cleanSnapshot(snapshot, detail, timeline) {
  const latestRole = timeline.rows[0] || {};
  const safeSnapshot = snapshot || {};
  const currentTitle = formatDisplayValue(
    safeSnapshot.current_title || latestRole.role,
  );
  const currentCompany = formatDisplayValue(
    safeSnapshot.current_company || latestRole.company,
  );
  let current = "Not Found";

  if (currentTitle !== "Not Found" && currentCompany !== "Not Found") {
    current = `${currentTitle} at ${currentCompany}`;
  } else if (currentTitle !== "Not Found") {
    current = currentTitle;
  } else if (currentCompany !== "Not Found") {
    current = currentCompany;
  }

  return {
    candidateName: formatDisplayValue(
      safeSnapshot.candidate_name,
      formatDisplayValue(detail.resume_name),
    ),
    likelyRole: formatDisplayValue(
      safeSnapshot.likely_role || currentTitle,
    ),
    current,
    location: formatDisplayValue(safeSnapshot.location),
    totalExperience: formatDisplayValue(
      safeSnapshot.total_experience,
      timeline.totalExperience,
    ),
  };
}

function isUsableGrading(grading) {
  return Boolean(
    grading &&
      getGradingPercentage(grading) !== null &&
      grading.summary &&
      grading.summary !== "Candidate grading could not be generated.",
  );
}

function getGradingPercentage(grading) {
  if (!grading) return null;

  const rawPercentage =
    grading.grade_percentage ??
    grading.percentage ??
    grading.score ??
    grading.candidate_score ??
    grading.fit_percentage ??
    grading.fit_score;

  if (rawPercentage !== undefined && rawPercentage !== null) {
    const parsed = Number(String(rawPercentage).replace("%", "").trim());
    if (Number.isFinite(parsed)) {
      return Math.max(0, Math.min(100, Math.round(parsed)));
    }
  }

  const grade = String(grading.grade || "").trim().toUpperCase();
  const letterFallback = {
    A: 90,
    B: 80,
    C: 65,
    D: 45,
    F: 25,
  };

  return letterFallback[grade] ?? null;
}

function normalizeCriteriaScores(scores) {
  const source = scores || {};
  return Object.fromEntries(
    Object.keys(defaultGradingWeights).map((key) => {
      const parsed = Number(source[key]);
      return [key, Number.isFinite(parsed) ? Math.round(parsed) : null];
    }),
  );
}

function buildDisplayGradingFallback(detail) {
  const matchingSkills = cleanList(detail.matching_skills);
  const missingSkills = cleanList(detail.missing_skills);
  const totalSignals = matchingSkills.length + missingSkills.length;
  const ratio = totalSignals ? matchingSkills.length / totalSignals : 0;
  let gradePercentage = Math.round(ratio * 70);

  if (matchingSkills.length) {
    gradePercentage += 10;
  }

  gradePercentage = Math.max(0, Math.min(100, gradePercentage));
  let grade = "F";

  if (gradePercentage >= 90) {
    grade = "A";
  } else if (gradePercentage >= 75) {
    grade = "B";
  } else if (gradePercentage >= 55) {
    grade = "C";
  } else if (gradePercentage >= 35) {
    grade = "D";
  }

  return {
    grade,
    grade_percentage: gradePercentage,
    summary:
      `Grade ${gradePercentage}% is a display fallback based on ` +
      `${matchingSkills.length} matching skill(s) and ` +
      `${missingSkills.length} missing skill(s). ` +
      "It does not use the generated match score.",
    strengths: matchingSkills.length
      ? [`Matches ${matchingSkills.slice(0, 4).join(", ")}.`]
      : ["Resume context is available, but strong matched skills were not returned."],
    concerns: missingSkills.length
      ? [`Missing or unclear skills include ${missingSkills.slice(0, 4).join(", ")}.`]
      : ["No missing skills were returned for this candidate."],
  };
}

function App() {
  const [activePage, setActivePage] = useState("analyzer");
  const [providers, setProviders] = useState(defaultProviders);
  const [ollamaModels, setOllamaModels] = useState(defaultOllamaModels);
  const [geminiModels, setGeminiModels] = useState(defaultGeminiModels);
  const [claudeModels, setClaudeModels] = useState(defaultClaudeModels);
  const [config, setConfig] = useState(emptyConfig);
  const [provider, setProvider] = useState("Gemini");
  const [model, setModel] = useState(defaultGeminiModels[0]);
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

    if (provider === "Claude") {
      return claudeModels.length ? claudeModels : defaultClaudeModels;
    }

    return ollamaModels.length ? ollamaModels : defaultOllamaModels;
  }, [provider, geminiModels, claudeModels, ollamaModels]);

  useEffect(() => {
    if (modelOptions.length > 0 && !modelOptions.includes(model)) {
      const fallbackModel = modelOptions[0];
      setModel(fallbackModel);
      setConfig((current) => ({
        ...current,
        [getModelConfigKey(provider)]: fallbackModel,
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
      const loadedClaudeModels = data.claude_models?.length
        ? data.claude_models
        : defaultClaudeModels;
      const nextProvider = loadedConfig.ai_provider || defaultProviders[0];
      const nextModelOptions =
        nextProvider === "Ollama"
          ? loadedOllamaModels
          : nextProvider === "Claude"
            ? loadedClaudeModels
            : loadedGeminiModels;
      const configuredModel = getConfiguredModel(loadedConfig, nextProvider);
      const nextModel = nextModelOptions.includes(configuredModel)
        ? configuredModel
        : nextModelOptions[0];

      setProviders(loadedProviders);
      setOllamaModels(loadedOllamaModels);
      setGeminiModels(loadedGeminiModels);
      setClaudeModels(loadedClaudeModels);
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
        : nextProvider === "Claude"
          ? config.claude_model || claudeModels[0] || defaultClaudeModels[0]
          : config.ollama_model || ollamaModels[0] || defaultOllamaModels[0],
    );
  }

  function handleModelChange(nextModel) {
    setModel(nextModel);
    setConfig((current) => ({
      ...current,
      [getModelConfigKey(provider)]: nextModel,
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
    const gradingWeights = normalizeGradingWeights(
      config.candidate_grading_weights,
    );
    formData.append("skill_gap_weight", String(gradingWeights.skill_gap));
    formData.append(
      "years_experience_weight",
      String(gradingWeights.years_experience),
    );
    formData.append(
      "project_experience_weight",
      String(gradingWeights.project_experience),
    );
    formData.append("education_weight", String(gradingWeights.education));
    formData.append("seniority_weight", String(gradingWeights.seniority));

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

  async function saveConfiguration(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setIsSaving(true);

    const payload = {
      ...config,
      ai_provider: provider,
      gemini_model: provider === "Gemini" ? model : config.gemini_model,
      claude_model: provider === "Claude" ? model : config.claude_model,
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
        getConfiguredModel(savedConfig, savedConfig.ai_provider),
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
        getConfiguredModel(resetConfig, resetConfig.ai_provider),
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
        </div>
      </section>

      {activePage === "analyzer" ? (
        <AnalyzerPage
          config={config}
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
          setConfig={setConfig}
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
  config,
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
  setConfig,
  setJobDescription,
  setResumes,
}) {
  const gradingWeights = normalizeGradingWeights(
    config?.candidate_grading_weights,
  );
  const gradingWeightTotal = getGradingWeightTotal(gradingWeights);

  function updateGradingWeight(key, value) {
    setConfig((current) => ({
      ...current,
      candidate_grading_weights: normalizeGradingWeights({
        ...current.candidate_grading_weights,
        [key]: value,
      }),
    }));
  }

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

        <GradingRubricCard
          weights={gradingWeights}
          total={gradingWeightTotal}
          onChange={updateGradingWeight}
          helperText="Edits here apply to the next analysis run."
        />

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

  function updateGradingWeight(key, value) {
    setConfig((current) => ({
      ...current,
      candidate_grading_weights: normalizeGradingWeights({
        ...current.candidate_grading_weights,
        [key]: value,
      }),
    }));
  }

  const gradingWeights = normalizeGradingWeights(
    config.candidate_grading_weights,
  );
  const gradingWeightTotal = getGradingWeightTotal(gradingWeights);

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

        <GradingRubricCard
          weights={gradingWeights}
          total={gradingWeightTotal}
          onChange={updateGradingWeight}
        />

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
          label="Experience Timeline Prompt"
          value={config.experience_timeline_prompt_template}
          onChange={(value) =>
            updatePrompt("experience_timeline_prompt_template", value)
          }
        />
        <PromptEditor
          label="Candidate Snapshot Prompt"
          value={config.candidate_snapshot_prompt_template}
          onChange={(value) =>
            updatePrompt("candidate_snapshot_prompt_template", value)
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

function GradingRubricCard({
  weights,
  total,
  onChange,
  readonly = false,
  helperText = "Grade uses only these weighted criteria.",
}) {
  const rows = [
    ["skill_gap", "Skill Gap"],
    ["years_experience", "Years Experience"],
    ["project_experience", "Hands-on Projects"],
    ["education", "Education"],
    ["seniority", "Seniority"],
  ];

  return (
    <section className="grading-rubric">
      <div className="rubric-header">
        <div>
          <span>Candidate Grade Rubric</span>
          <p>{helperText}</p>
        </div>
        <strong className={total === 100 ? "ok" : "warn"}>
          {total}% total
        </strong>
      </div>
      <div className="rubric-grid">
        {rows.map(([key, label]) => (
          <label key={key}>
            {label}
            {readonly ? (
              <strong>{weights[key]}%</strong>
            ) : (
              <input
                min="0"
                max="100"
                type="number"
                value={weights[key]}
                onChange={(event) => onChange(key, event.target.value)}
              />
            )}
          </label>
        ))}
      </div>
    </section>
  );
}

function GradingBreakdown({ scores, weights }) {
  const rows = [
    ["skill_gap", "Skill Gap"],
    ["years_experience", "Years"],
    ["project_experience", "Projects"],
    ["education", "Education"],
    ["seniority", "Seniority"],
  ];

  return (
    <div className="grading-breakdown">
      {rows.map(([key, label]) => (
        <div key={key}>
          <span>{label}</span>
          <strong>
            {scores[key] === null ? "Not Found" : `${scores[key]}/100`}
          </strong>
          <small>{weights[key]}% weight</small>
        </div>
      ))}
    </div>
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
  const jdInfo = result.job_description || {};
  const jdCoreEntries = Object.entries(jdInfo).filter(
    ([key]) => key !== "additional_insights",
  );
  const jdAdditionalInsights = cleanAdditionalInsights(
    jdInfo.additional_insights,
  );
  const detailMap = useMemo(() => {
    return new Map(
      (result.top_details || []).map((detail) => [detail.resume_id, detail]),
    );
  }, [result.top_details]);

  if (selectedDetail) {
    return (
      <DetailPage
        detail={selectedDetail}
        onBack={() => setSelectedDetail(null)}
      />
    );
  }

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

      <section>
        <h2>Job Description</h2>
        <div className="jd-grid">
          {jdCoreEntries.map(([key, value]) => (
            <div key={key}>
              <span>{key.replaceAll("_", " ")}</span>
              <strong>{formatDisplayValue(value)}</strong>
            </div>
          ))}
        </div>
        {jdAdditionalInsights.length ? (
          <div className="additional-insights-grid jd-insights-grid">
            {jdAdditionalInsights.map((item) => (
              <article
                className="additional-insight-card"
                key={`${item.label}-${item.value}`}
              >
                <span>{item.label}</span>
                <p>{item.value}</p>
              </article>
            ))}
          </div>
        ) : null}
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

    </div>
  );
}

function DetailPage({ detail, onBack }) {
  const evidence = Array.isArray(detail.matching_evidence)
    ? detail.matching_evidence
    : [];
  const grading = isUsableGrading(detail.candidate_grading)
    ? detail.candidate_grading
    : buildDisplayGradingFallback(detail);
  const [showEvidence, setShowEvidence] = useState(false);
  const matchingCount = cleanList(detail.matching_skills).length;
  const missingCount = cleanList(detail.missing_skills).length;
  const strengthCount = cleanList(grading.strengths).length;
  const concernCount = cleanList(grading.concerns).length;
  const timeline = cleanTimeline(detail.experience_timeline);
  const timelineDebug = detail.experience_timeline_debug || {};
  const snapshot = cleanSnapshot(detail.candidate_snapshot, detail, timeline);
  const gradingPercentage = getGradingPercentage(grading);
  const gradingCriteriaScores = normalizeCriteriaScores(
    grading.criteria_scores,
  );
  const appliedGradingWeights = normalizeGradingWeights(grading.weights);
  const additionalInsights = cleanAdditionalInsights(
    detail.additional_insights,
    grading.additional_insights,
    detail.experience_timeline?.additional_insights,
    detail.candidate_snapshot?.additional_insights,
  );
  const gradeMeterStyle = {
    "--grade-percent": `${gradingPercentage ?? 0}%`,
  };

  return (
    <section className="detail-page" aria-labelledby="detail-page-title">
        <div className="detail-header">
          <div>
            <h2 id="detail-page-title">
              {formatDisplayValue(detail.resume_name)}
            </h2>
            <span>Detailed candidate analysis</span>
          </div>
          <button
            className="secondary"
            onClick={onBack}
            title="Back to results"
            type="button"
          >
            <ArrowLeft size={18} />
            Back to Results
          </button>
        </div>

        <section className="candidate-snapshot">
          <div>
            <span>Candidate</span>
            <h3>{snapshot.candidateName}</h3>
            <p>{formatDisplayValue(detail.resume_name)}</p>
          </div>
          <div>
            <span>Likely Role</span>
            <strong>{snapshot.likelyRole}</strong>
          </div>
          <div>
            <span>Current</span>
            <strong>{snapshot.current}</strong>
          </div>
          <div>
            <span>Experience</span>
            <strong>{snapshot.totalExperience}</strong>
          </div>
          <div>
            <span>Location</span>
            <strong>{snapshot.location}</strong>
          </div>
          <div className="snapshot-score">
            <span>Match Score</span>
            <strong>{formatDisplayValue(detail.match_score)}%</strong>
          </div>
        </section>

        <div className="detail-workspace">
          <div className="detail-left-column">
            <div className="grade-card">
              <span>Candidate Grade</span>
              <div className="grade-card-main">
                <div
                  className="grade-meter"
                  style={gradeMeterStyle}
                  aria-label={`Candidate grade ${formatDisplayValue(
                    gradingPercentage,
                    "Not Found",
                  )} percent`}
                >
                  <strong>
                    {gradingPercentage !== null
                      ? `${gradingPercentage}%`
                      : "Not Found"}
                  </strong>
                </div>
                <div>
                  <strong>
                    {gradingPercentage !== null
                      ? `${gradingPercentage}/100`
                      : "Not Found"}
                  </strong>
                  <small>candidate fit grade</small>
                </div>
              </div>
              <p>{formatDisplayValue(grading.summary)}</p>
              <GradingBreakdown
                scores={gradingCriteriaScores}
                weights={appliedGradingWeights}
              />
            </div>

            <div className="detail-metrics">
              <MetricTile
                icon={<CheckCircle2 size={18} />}
                label="Matching"
                value={matchingCount}
              />
              <MetricTile
                icon={<AlertTriangle size={18} />}
                label="Missing"
                value={missingCount}
              />
              <MetricTile
                icon={<Award size={18} />}
                label="Strengths"
                value={strengthCount}
              />
              <MetricTile
                icon={<Info size={18} />}
                label="Concerns"
                value={concernCount}
              />
              <MetricTile
                icon={<BriefcaseBusiness size={18} />}
                label="Roles"
                value={timeline.rows.length}
              />
              <MetricTile
                icon={<CalendarDays size={18} />}
                label="Experience"
                value={timeline.totalExperience}
              />
            </div>

            <div className="detail-actions">
              <button
                className="secondary"
                disabled={!evidence.length}
                onClick={() => setShowEvidence(true)}
                type="button"
              >
                <Search size={17} />
                Evidence
              </button>
            </div>

            <section className="detail-section">
              <div className="section-title-row">
                <h3>Recruiter Review</h3>
              </div>
              <div className="skills modal-skills-grid grading-grid">
                <SkillColumn
                  icon={<Award size={16} />}
                  title="Strengths"
                  items={grading.strengths}
                />
                <SkillColumn
                  icon={<AlertTriangle size={16} />}
                  title="Concerns"
                  items={grading.concerns}
                />
              </div>
            </section>

            <section className="detail-section detail-skill-gap-section">
              <div className="section-title-row">
                <h3>Skill Gap</h3>
                {evidence.length ? (
                  <button
                    className="secondary compact-button"
                    onClick={() => setShowEvidence(true)}
                    type="button"
                  >
                    <Search size={16} />
                    {evidence.length} evidence notes
                  </button>
                ) : null}
              </div>
              <div className="skills modal-skills-grid">
                <SkillColumn
                  icon={<CheckCircle2 size={16} />}
                  title="Matching Skills"
                  items={detail.matching_skills}
                />
                <SkillColumn
                  icon={<AlertTriangle size={16} />}
                  title="Missing Skills"
                  items={detail.missing_skills}
                />
              </div>
            </section>

            {additionalInsights.length ? (
              <section className="detail-section">
                <div className="section-title-row">
                  <h3>Additional Insights</h3>
                  <span className="section-pill">
                    {additionalInsights.length}
                  </span>
                </div>
                <div className="additional-insights-grid">
                  {additionalInsights.map((item) => (
                    <article
                      className="additional-insight-card"
                      key={`${item.label}-${item.value}`}
                    >
                      <span>{item.label}</span>
                      <p>{item.value}</p>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}
          </div>

          <div className="detail-right-column">
            <section className="detail-section">
              <div className="section-title-row">
                <h3>Match Justification</h3>
              </div>
              <p className="detail-copy">
                {formatDisplayValue(detail.justification)}
              </p>
            </section>

            <section className="detail-section">
              <div className="section-title-row">
                <h3>Experience Timeline</h3>
                <span className="section-pill">
                  {timeline.totalExperience}
                </span>
              </div>
              {timeline.rows.length ? (
                <div className="experience-timeline">
                  {timeline.rows.map((item, index) => (
                    <article className="timeline-item" key={`${item.role}-${item.company}-${index}`}>
                      <div className="timeline-marker" />
                      <div className="timeline-card">
                        <div className="timeline-heading">
                          <div>
                            <h4>{formatDisplayValue(item.role)}</h4>
                            <p>{formatDisplayValue(item.company)}</p>
                          </div>
                          <span>
                            {formatDisplayValue(item.start_date)} -{" "}
                            {formatDisplayValue(item.end_date)}
                          </span>
                        </div>
                        <p className="detail-copy">
                          {formatDisplayValue(item.summary)}
                        </p>
                        <p className="timeline-relevance">
                          {formatDisplayValue(item.relevance)}
                        </p>
                        <div className="timeline-meta">
                          <span>{formatDisplayValue(item.duration)}</span>
                          <span>{formatDisplayValue(item.location)}</span>
                        </div>
                        {cleanList(item.technologies).length ? (
                          <div className="chip-row">
                            {cleanList(item.technologies).map((skill) => (
                              <span className="skill-chip" key={skill}>
                                {skill}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {cleanList(item.projects).length ? (
                          <div className="timeline-projects">
                            <strong>Projects</strong>
                            <p>{cleanList(item.projects).join(", ")}</p>
                          </div>
                        ) : null}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="detail-copy">
                  Experience timeline was not found for this resume.
                </p>
              )}
              {Object.keys(timelineDebug).length ? (
                <div className="timeline-debug">
                  <strong>Temporary Timeline Debug</strong>
                  <div>
                    <span>Provider</span>
                    <p>{formatDisplayValue(timelineDebug.provider)}</p>
                  </div>
                  <div>
                    <span>Model</span>
                    <p>{formatDisplayValue(timelineDebug.model)}</p>
                  </div>
                  <div>
                    <span>Resume Context</span>
                    <p>{formatDisplayValue(timelineDebug.resume_context_chars, "0")} chars</p>
                  </div>
                  <div>
                    <span>Rows</span>
                    <p>
                      model {formatDisplayValue(timelineDebug.model_rows, "0")} / local{" "}
                      {formatDisplayValue(timelineDebug.local_rows, "0")} / final{" "}
                      {formatDisplayValue(timelineDebug.final_rows, "0")}
                    </p>
                  </div>
                  <div>
                    <span>Source</span>
                    <p>{formatDisplayValue(timelineDebug.source)}</p>
                  </div>
                  {timelineDebug.error ? (
                    <div className="timeline-debug-error">
                      <span>Error</span>
                      <p>{formatDisplayValue(timelineDebug.error)}</p>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </section>
          </div>

        </div>

        {showEvidence ? (
          <EvidenceModal
            evidence={evidence}
            resumeName={detail.resume_name}
            onClose={() => setShowEvidence(false)}
          />
        ) : null}
      </section>
  );
}

function MetricTile({ icon, label, value }) {
  return (
    <div className="metric-tile">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
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

function SkillColumn({ icon, title, items }) {
  const safeItems = Array.isArray(items) ? items : [];

  return (
    <div className="skill-column">
      <span>
        {icon}
        {title}
      </span>
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

export default App;
