import React, { useEffect, useMemo, useState } from "react";
import { FileText, Loader2, Save, RotateCcw, UploadCloud } from "lucide-react";
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

function App() {
  const [activePage, setActivePage] = useState("analyzer");
  const [providers, setProviders] = useState(defaultProviders);
  const [ollamaModels, setOllamaModels] = useState(defaultOllamaModels);
  const [geminiModels, setGeminiModels] = useState(defaultGeminiModels);
  const [config, setConfig] = useState(emptyConfig);
  const [provider, setProvider] = useState("Gemini");
  const [model, setModel] = useState(defaultGeminiModels[0]);
  const [jobDescription, setJobDescription] = useState("");
  const [resumes, setResumes] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    loadConfiguration();
  }, []);

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
        throw new Error(data.detail || "Could not load configuration.");
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

    if (resumes.length === 0) {
      setError("Upload at least one PDF or DOCX resume.");
      return;
    }

    const formData = new FormData();
    formData.append("job_description", jobDescription);
    formData.append("provider", provider);
    formData.append("model_name", model);

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
        throw new Error(data.detail || "Analysis failed.");
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
        throw new Error(data.detail || "Could not save configuration.");
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
        throw new Error(data.detail || "Could not reset configuration.");
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
            className={activePage === "config" ? "tab active" : "tab"}
            onClick={() => setActivePage("config")}
            type="button"
          >
            Configurations
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
          jobDescription={jobDescription}
          model={model}
          modelOptions={modelOptions}
          notice={notice}
          provider={provider}
          providers={providers}
          result={result}
          resumes={resumes}
          setJobDescription={setJobDescription}
          setResumes={setResumes}
        />
      ) : (
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
      )}
    </main>
  );
}

function AnalyzerPage({
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
        </div>

        <label className="upload-zone">
          <UploadCloud size={24} />
          <span>{resumes.length || "Upload resumes"}</span>
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

  return (
    <div className="results-stack">
      {runtimeStatus.last_ai_error ? (
        <div className="error">
          AI analysis warning: {runtimeStatus.last_ai_error}
        </div>
      ) : null}

      {runtimeStatus.last_vector_store_error ? (
        <div className="error">
          Vector store warning: {runtimeStatus.last_vector_store_error}
        </div>
      ) : null}

      <section>
        <h2>Job Description</h2>
        <div className="jd-grid">
          {Object.entries(result.job_description).map(([key, value]) => (
            <div key={key}>
              <span>{key.replaceAll("_", " ")}</span>
              <strong>{value}</strong>
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
            </tr>
          </thead>
          <tbody>
            {result.ranking.map((row) => (
              <tr key={row.resume_id}>
                <td>{row.resume_name}</td>
                <td>{row.match_score}%</td>
                <td>{row.fit}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Top Details</h2>
        <div className="detail-list">
          {result.top_details.map((detail) => (
            <article key={detail.resume_id} className="detail-item">
              <div className="detail-header">
                <strong>{detail.resume_name}</strong>
                <span>{detail.match_score}%</span>
              </div>
              <p>{detail.justification}</p>
              <div className="skills">
                <SkillColumn title="Matching" items={detail.matching_skills} />
                <SkillColumn title="Missing" items={detail.missing_skills} />
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function SkillColumn({ title, items }) {
  return (
    <div>
      <span>{title}</span>
      <ul>
        {(items.length ? items : ["Not Found"]).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export default App;
