import { useEffect, useMemo, useState } from "react";

const API = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const stages = ["acquire", "speech", "frames", "ocr", "questions", "render"];

type Job = { job_id: string; status: string; warnings?: string[]; outputs?: string[]; stages?: Record<string, { status: string }> };
type Question = { prompt: string; options: { label: string; text: string }[]; answer?: string; explanation?: string; confidence?: number; warnings?: string[] };
type Extraction = { questions?: Question[]; transcript?: { language?: string; segments?: { text: string; start_seconds: number }[] }; ocr?: { text: string; frame: { timestamp_seconds: number; path: string } }[] };
type Option = { id: string; label: string };
type Profile = { id: string; label: string; description: string };
type Provider = { id: string; label: string; configured: boolean; default_base_url?: string; default_api_key_env?: string; model_examples: string[] };
type SettingsOptions = { profiles: Profile[]; languages: Option[]; ocr_languages: Option[]; llm: Provider[] };

function App() {
  const [source, setSource] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [profile, setProfile] = useState("balanced");
  const [speech, setSpeech] = useState("auto");
  const [inputLanguage, setInputLanguage] = useState("auto");
  const [outputLanguage, setOutputLanguage] = useState("same");
  const [ocrLanguage, setOcrLanguage] = useState("eng");
  const [llmEnabled, setLlmEnabled] = useState(false);
  const [llmProvider, setLlmProvider] = useState("none");
  const [llmModel, setLlmModel] = useState("");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [llmApiKeyEnv, setLlmApiKeyEnv] = useState("");
  const [llmVision, setLlmVision] = useState(true);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [settings, setSettings] = useState<SettingsOptions | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [data, setData] = useState<Extraction | null>(null);
  const [error, setError] = useState("");
  const [events, setEvents] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/settings/options`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Could not load settings.")))
      .then((value: SettingsOptions) => setSettings(value))
      .catch(() => setError("Settings metadata could not be loaded. Defaults remain available."));
  }, []);

  useEffect(() => {
    if (!job?.job_id || ["completed", "failed", "cancelled"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`${API}/api/jobs/${job.job_id}`);
      if (response.ok) setJob(await response.json());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job?.job_id, job?.status]);

  useEffect(() => {
    if (job?.status !== "completed") return;
    fetch(`${API}/api/jobs/${job.job_id}/artifacts/extraction.json`)
      .then((response) => response.ok && response.json())
      .then((value) => value && setData(value));
  }, [job?.job_id, job?.status]);

  useEffect(() => {
    const provider = settings?.llm.find((item) => item.id === llmProvider);
    if (!provider || llmProvider === "none") return;
    if (!llmBaseUrl && provider.default_base_url) setLlmBaseUrl(provider.default_base_url);
    if (!llmApiKeyEnv && provider.default_api_key_env) setLlmApiKeyEnv(provider.default_api_key_env);
    if (!llmModel && provider.model_examples[0]) setLlmModel(provider.model_examples[0]);
  }, [llmProvider, settings]);

  const questionCount = data?.questions?.length || 0;
  const transcriptCount = data?.transcript?.segments?.length || 0;
  const hasInput = Boolean(source.trim() || file);
  const hasArtifact = (name: string) => Boolean(job?.outputs?.some((path) => path.endsWith(name)));
  const selectedProvider = settings?.llm.find((item) => item.id === llmProvider);

  async function submit() {
    if (!hasInput) return;
    setBusy(true); setError(""); setJob(null); setData(null); setEvents([]);
    const options = {
      speech: { provider: speech, language: inputLanguage === "auto" ? null : inputLanguage },
      ocr: { language: ocrLanguage },
      llm: {
        enabled: llmEnabled,
        provider: llmProvider,
        model: llmModel || null,
        base_url: llmBaseUrl || null,
        api_key_env: llmApiKeyEnv || null,
        output_language: outputLanguage,
        vision_enabled: llmVision,
      },
    };
    try {
      let response: Response;
      if (file) {
        const form = new FormData(); form.append("file", file);
        response = await fetch(`${API}/api/jobs/file`, { method: "POST", body: form });
      } else {
        response = await fetch(`${API}/api/jobs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source, profile, options }),
        });
      }
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "The API rejected this job.");
      setJob(body); setEvents([`Job ${body.job_id} queued`]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not start the job.");
    } finally { setBusy(false); }
  }

  async function cancel() {
    if (!job) return;
    await fetch(`${API}/api/jobs/${job.job_id}/cancel`, { method: "POST" });
    setEvents((current) => [...current, "Cancellation requested"]);
  }

  const visibleStages = useMemo(
    () => stages.map((name) => ({ name, status: job?.stages?.[name]?.status || "pending" })),
    [job],
  );

  return <main className="shell">
    <nav className="topbar"><div className="brand"><span className="brand-mark">✦</span><span>Exam Extractor</span></div><span className="nav-note">MULTIMODAL STUDY SYSTEM <i /></span></nav>
    <section className="hero"><div className="eyebrow">FROM LECTURE TO LEARNING</div><h1>Turn every exam-prep video<br /><em>into something you can study.</em></h1><p className="hero-copy">Capture the spoken answer, the question on screen, and the visual evidence around it—then trace every result back to its source.</p></section>
    <section className="workspace-grid">
      <div className="panel intake-panel">
        <div className="panel-heading"><div><span className="section-number">01</span><h2>Bring your material</h2></div><span className="status-dot">LOCAL-FIRST</span></div>
        <div className="input-tabs"><button className={!file ? "active" : ""} onClick={() => setFile(null)}>Video link</button><button className={file ? "active" : ""} onClick={() => document.getElementById("file-input")?.click()}>Upload file</button></div>
        <input id="file-input" className="hidden" type="file" accept="video/*,audio/*,.pdf" onChange={(event) => { setFile(event.target.files?.[0] || null); setSource(""); }} />
        <div className="source-input"><span>↗</span><input aria-label="YouTube URL" placeholder="Paste a YouTube URL or local path" value={source} disabled={Boolean(file)} onChange={(event) => setSource(event.target.value)} />{file && <strong>{file.name}</strong>}</div>
        <div className="control-row"><label>PROFILE<select value={profile} onChange={(event) => setProfile(event.target.value)}>{(settings?.profiles || [{ id: "fast", label: "Fast" }, { id: "balanced", label: "Balanced" }, { id: "high_accuracy", label: "High Accuracy" }]).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label><label>SPEECH<select value={speech} onChange={(event) => setSpeech(event.target.value)}><option value="auto">Automatic</option><option value="none">Captions only</option><option value="faster_whisper">Local Whisper</option><option value="openai_compatible">Remote API</option></select></label></div>
        <button className="advanced-toggle" onClick={() => setAdvancedOpen((value) => !value)} aria-expanded={advancedOpen}>Advanced settings <span>{advancedOpen ? "−" : "+"}</span></button>
        {advancedOpen && <div className="advanced-panel">
          <div className="settings-section"><div className="settings-title">LANGUAGE</div><div className="control-row"><label>INPUT LANGUAGE<select value={inputLanguage} onChange={(event) => setInputLanguage(event.target.value)}>{(settings?.languages || [{ id: "auto", label: "Auto-detect" }, { id: "en", label: "English" }, { id: "ar", label: "Arabic" }]).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label><label>OUTPUT LANGUAGE<select value={outputLanguage} onChange={(event) => setOutputLanguage(event.target.value)}><option value="same">Same as source</option>{(settings?.languages || []).filter((item) => item.id !== "auto").map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label></div><label>OCR LANGUAGE<select value={ocrLanguage} onChange={(event) => setOcrLanguage(event.target.value)}>{(settings?.ocr_languages || [{ id: "eng", label: "English" }, { id: "ara", label: "Arabic" }, { id: "eng+ara", label: "English + Arabic" }]).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label></div>
          <div className="settings-section"><div className="settings-title">LLM ENRICHMENT</div><label className="toggle-row"><span>Enable LLM questions and explanations</span><input type="checkbox" checked={llmEnabled} onChange={(event) => { setLlmEnabled(event.target.checked); if (!event.target.checked) setLlmProvider("none"); }} /></label><label>PROVIDER<select value={llmProvider} onChange={(event) => setLlmProvider(event.target.value)} disabled={!llmEnabled}>{(settings?.llm || [{ id: "none", label: "No LLM" }]).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label><label>MODEL<input list="llm-models" value={llmModel} disabled={!llmEnabled} onChange={(event) => setLlmModel(event.target.value)} placeholder="Provider model name" /><datalist id="llm-models">{selectedProvider?.model_examples.map((model) => <option value={model} key={model} />)}</datalist></label><div className="control-row"><label>BASE URL<input value={llmBaseUrl} disabled={!llmEnabled} onChange={(event) => setLlmBaseUrl(event.target.value)} placeholder="Optional custom endpoint" /></label><label>KEY ENVIRONMENT VARIABLE<input value={llmApiKeyEnv} disabled={!llmEnabled} onChange={(event) => setLlmApiKeyEnv(event.target.value)} placeholder="OPENAI_API_KEY" /></label></div><label className="toggle-row"><span>Send low-confidence frames for visual analysis</span><input type="checkbox" checked={llmVision} disabled={!llmEnabled} onChange={(event) => setLlmVision(event.target.checked)} /></label>{llmEnabled && selectedProvider && <small className={selectedProvider.configured ? "provider-ready" : "provider-missing"}>{selectedProvider.configured ? "Provider key appears configured on the server." : "Provider key is not configured in the container environment."}</small>}</div>
        </div>}
        <button className="primary-button" disabled={!hasInput || busy} onClick={submit}>{busy ? "Starting…" : "Extract study material"}<span>→</span></button><p className="microcopy">No LLM required · Your keys stay on the server · Resumable artifacts</p>
      </div>
      <div className="panel philosophy-panel"><span className="section-number">WHY THIS WORKS</span><h2>Evidence before inference.</h2><p>Every answer is assembled from three channels, so you can see what was heard, what was read, and what was interpreted.</p><div className="channel"><span className="channel-icon audio">◒</span><div><b>Speech</b><small>Captions or local Whisper with timestamps</small></div></div><div className="channel"><span className="channel-icon visual">▧</span><div><b>Visuals</b><small>Keyframes, OCR, diagrams, and tables</small></div></div><div className="channel"><span className="channel-icon trace">⌁</span><div><b>Traceability</b><small>Evidence links and confidence on every claim</small></div></div></div>
    </section>
    {(job || error) && <section className="results-area"><div className="panel pipeline-panel"><div className="panel-heading"><div><span className="section-number">02</span><h2>Pipeline live view</h2></div>{job && <span className={`job-state ${job.status}`}>{job.status}</span>}</div><div className="stage-list">{visibleStages.map((stage, index) => <div className={`stage ${stage.status}`} key={stage.name}><span className="stage-index">{stage.status === "completed" ? "✓" : String(index + 1).padStart(2, "0")}</span><div><b>{stage.name.replace("_", " ")}</b><small>{stage.status}</small></div><span className="stage-line" /></div>)}</div>{job && !["completed", "failed", "cancelled"].includes(job.status) && <button className="quiet-button" onClick={cancel}>Cancel job</button>}{error && <div className="error-box"><b>Could not start extraction</b><span>{error}</span></div>}{job?.warnings?.map((warning) => <div className="warning" key={warning}>⚠ {warning}</div>)}<div className="event-log">{events.slice(-4).map((event) => <span key={event}>› {event}</span>)}</div></div>{job?.status === "completed" && <div className="panel study-panel"><div className="panel-heading"><div><span className="section-number">03</span><h2>Study output</h2></div><span className="status-dot">READY</span></div><div className="metric-row"><div><strong>{questionCount}</strong><span>questions</span></div><div><strong>{transcriptCount}</strong><span>{data?.transcript?.language || "speech"} segments</span></div><div><strong>{data?.ocr?.length || 0}</strong><span>visual frames</span></div></div><div className="question-preview">{data?.questions?.slice(0, 3).map((question, index) => <article key={`${question.prompt}-${index}`}><span className="question-number">Q{String(index + 1).padStart(2, "0")}</span><h3>{question.prompt}</h3>{question.answer && <p className="answer-line"><b>Answer {question.answer}</b>{question.explanation && ` · ${question.explanation}`}</p>}</article>)}{!questionCount && <p className="empty-state">The extraction completed without detecting a structured question. Review the transcript and visual evidence.</p>}</div><div className="downloads"><a href={`${API}/api/jobs/${job.job_id}/artifacts/extraction.md`} target="_blank" rel="noreferrer">Markdown ↗</a><a href={`${API}/api/jobs/${job.job_id}/artifacts/extraction.json`} target="_blank" rel="noreferrer">JSON ↗</a>{hasArtifact("extraction.docx") && <a href={`${API}/api/jobs/${job.job_id}/artifacts/extraction.docx`} target="_blank" rel="noreferrer">Word ↗</a>}{hasArtifact("transcript.md") && <a href={`${API}/api/jobs/${job.job_id}/artifacts/transcript.md`} target="_blank" rel="noreferrer">Transcript ↗</a>}</div></div>}</section>}
    <footer><span>EXAM EXTRACTOR <b>0.1</b></span><span>OPEN SOURCE · LOCAL-FIRST · PROVIDER-ELASTIC</span></footer>
  </main>;
}

export default App;
