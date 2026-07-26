import { useEffect, useMemo, useState } from "react";

const API = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const STAGES = ["acquire", "speech", "frames", "ocr", "questions", "task", "review", "render"];

type Job = { job_id: string; status: string; warnings?: string[]; outputs?: string[]; stages?: Record<string, { status: string }> };
type Question = { question_id?: string; prompt: string; options: { label: string; text: string }[]; answer?: string; explanation?: string; confidence?: number; warnings?: string[]; review_status?: string };
type Extraction = { questions?: Question[]; task?: { kind?: string; title?: string; content?: unknown; items?: unknown[] }; transcript?: { language?: string; segments?: { text: string; start_seconds: number }[] }; ocr?: { text: string; frame: { timestamp_seconds: number; path: string } }[] };
type Option = { id: string; label: string };
type Profile = { id: string; label: string; description: string };
type Provider = { id: string; label: string; configured: boolean; default_base_url?: string; default_api_key_env?: string; model_examples: string[] };
type WorkflowBlock = { id: string; kind: string; enabled: boolean; depends_on: string[]; config: Record<string, unknown> };
type Workflow = { id: string; name: string; description: string; blocks: WorkflowBlock[] };
type SettingsOptions = { profiles: Profile[]; languages: Option[]; ocr_languages: Option[]; llm: Provider[]; workflows: Workflow[] };
type ReviewItem = { question_id: string; prompt: string; options: { label: string; text: string }[]; answer?: string; explanation?: string; confidence?: number; warnings?: string[]; review_status: string; review_note?: string };
type ReviewResponse = { summary: { total: number; needs_review: number; completed: boolean; counts: Record<string, number> }; items: ReviewItem[]; completed_by_human?: boolean; status?: string };

const fallbackProfiles = [{ id: "fast", label: "Fast" }, { id: "balanced", label: "Balanced" }, { id: "high_accuracy", label: "High Accuracy" }];
const fallbackLanguages = [{ id: "auto", label: "Auto-detect" }, { id: "en", label: "English" }, { id: "ar", label: "Arabic" }];
const fallbackOcr = [{ id: "eng", label: "English" }, { id: "ara", label: "Arabic" }, { id: "eng+ara", label: "English + Arabic" }];

function App() {
  const [source, setSource] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [profile, setProfile] = useState("balanced");
  const [workflow, setWorkflow] = useState("exam_study_pack");
  const [taskKind, setTaskKind] = useState("auto");
  const [taskInstruction, setTaskInstruction] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskMaxItems, setTaskMaxItems] = useState(100);
  const [blockOverrides, setBlockOverrides] = useState<Record<string, boolean>>({});
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
  const [outputPdf, setOutputPdf] = useState(false);
  const [outputCsv, setOutputCsv] = useState(false);
  const [outputWord, setOutputWord] = useState(true);
  const [outputTranscript, setOutputTranscript] = useState(false);
  const [reviewGate, setReviewGate] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [settings, setSettings] = useState<SettingsOptions | null>(null);
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [reviewDraft, setReviewDraft] = useState({ prompt: "", answer: "", explanation: "", options: "", review_note: "" });
  const [reviewBusy, setReviewBusy] = useState(false);
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
    if (!job?.job_id || ["completed", "awaiting_review", "failed", "cancelled"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`${API}/api/jobs/${job.job_id}`);
      if (response.ok) setJob(await response.json());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job?.job_id, job?.status]);

  useEffect(() => {
    if (!job?.status || !["completed", "awaiting_review"].includes(job.status)) return;
    fetch(`${API}/api/jobs/${job.job_id}/review`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Review queue unavailable.")))
      .then((value: ReviewResponse) => {
        setReview(value);
        const first = value.items.find((item) => item.review_status === "needs_review");
        if (first) openReview(first);
      })
      .catch(() => setReview(null));
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

  const selectedProvider = settings?.llm.find((item) => item.id === llmProvider);
  const selectedWorkflow = settings?.workflows.find((item) => item.id === workflow);
  const questionCount = data?.questions?.length || 0;
  const transcriptCount = data?.transcript?.segments?.length || 0;
  const hasInput = Boolean(source.trim() || file);
  const hasArtifact = (name: string) => Boolean(job?.outputs?.some((path) => path.endsWith(name)));
  const visibleStages = useMemo(() => {
    const hasGenericTask = Boolean(job?.stages?.task);
    return STAGES.filter((name) => !job || (hasGenericTask ? name !== "questions" : name !== "task"))
      .map((name) => ({ name, status: job?.stages?.[name]?.status || "pending" }));
  }, [job]);
  const taskContent = typeof data?.task?.content === "string" ? data.task.content : data?.task?.content ? JSON.stringify(data.task.content) : "";

  function selectWorkflow(value: string) {
    setWorkflow(value);
    const preset = settings?.workflows.find((item) => item.id === value);
    setTaskKind("auto");
    setTaskInstruction("");
    setTaskTitle("");
    setBlockOverrides(Object.fromEntries((preset?.blocks || []).map((block) => [block.id, block.enabled])));
  }

  async function submit() {
    if (!hasInput) return;
    setBusy(true); setError(""); setJob(null); setData(null); setReview(null); setEvents([]);
    const options = {
      workflow: { id: workflow, blocks: Object.fromEntries(Object.entries(blockOverrides).map(([id, enabled]) => [id, { enabled }])) },
      task: { kind: taskKind, instruction: taskInstruction, title: taskTitle || null, max_items: taskMaxItems },
      speech: { provider: speech, language: inputLanguage === "auto" ? null : inputLanguage },
      ocr: { language: ocrLanguage },
      llm: { enabled: llmEnabled, provider: llmProvider, model: llmModel || null, base_url: llmBaseUrl || null, api_key_env: llmApiKeyEnv || null, output_language: outputLanguage, vision_enabled: llmVision },
      output: { pdf: outputPdf, csv: outputCsv, word: outputWord, transcript: outputTranscript },
      review: { gate_before_artifacts: reviewGate },
    };
    try {
      let response: Response;
      if (file) {
        const form = new FormData();
        form.append("file", file); form.append("profile", profile); form.append("options_json", JSON.stringify(options));
        response = await fetch(`${API}/api/jobs/file`, { method: "POST", body: form });
      } else {
        response = await fetch(`${API}/api/jobs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source, profile, workflow, options }) });
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

  function openReview(item: ReviewItem) {
    setSelectedReviewId(item.question_id);
    setReviewDraft({ prompt: item.prompt, answer: item.answer || "", explanation: item.explanation || "", options: item.options.map((option) => `${option.label}. ${option.text}`).join("\n"), review_note: item.review_note || "" });
  }

  async function saveReview(status: "approved" | "edited" | "rejected") {
    if (!job || !selectedReviewId) return;
    setReviewBusy(true);
    const options = reviewDraft.options.split("\n").map((line) => line.trim()).filter(Boolean).map((line, index) => {
      const match = line.match(/^([A-Ha-h]|[1-9])[.)\-:]?\s+(.+)$/);
      return { label: match?.[1]?.toUpperCase() || String(index + 1), text: match?.[2] || line };
    });
    try {
      const response = await fetch(`${API}/api/jobs/${job.job_id}/review/${selectedReviewId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...reviewDraft, options, status }) });
      const updated: ReviewItem & { detail?: string } = await response.json();
      if (!response.ok) throw new Error(updated.detail || "Could not save review.");
      const refreshed = await fetch(`${API}/api/jobs/${job.job_id}/review`);
      if (refreshed.ok) setReview(await refreshed.json());
      setData((current) => current && { ...current, questions: current.questions?.map((item) => item.question_id === updated.question_id ? updated : item) });
      setSelectedReviewId(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save review.");
    } finally { setReviewBusy(false); }
  }

  async function completeReview() {
    if (!job) return;
    const response = await fetch(`${API}/api/jobs/${job.job_id}/review/complete`, { method: "POST" });
    const body = await response.json();
    if (!response.ok) { setError(body.detail || "Review could not be completed."); return; }
    setReview(body);
    const refreshed = await fetch(`${API}/api/jobs/${job.job_id}`);
    if (refreshed.ok) setJob(await refreshed.json());
  }

  return <main className="shell">
    <nav className="topbar"><div className="brand"><span className="brand-mark">✦</span><span>SourceFlow</span></div><span className="nav-note">MULTIMODAL CONTENT WORKBENCH <i /></span></nav>
    <section className="hero"><div className="eyebrow">FROM SOURCE TO STRUCTURE</div><h1>Turn every source<br /><em>into something useful.</em></h1><p className="hero-copy">Capture speech, on-screen text, visual evidence, and the task you actually want—then turn them into summaries, notes, questions, or any structured output you choose.</p></section>
    <section className="workspace-grid">
      <div className="panel intake-panel">
        <div className="panel-heading"><div><span className="section-number">01</span><h2>Bring your material</h2></div><span className="status-dot">LOCAL-FIRST</span></div>
        <div className="input-tabs"><button className={!file ? "active" : ""} onClick={() => setFile(null)}>Video link</button><button className={file ? "active" : ""} onClick={() => document.getElementById("file-input")?.click()}>Upload file</button></div>
        <input id="file-input" className="hidden" type="file" accept="video/*,audio/*,.pdf" onChange={(event) => { setFile(event.target.files?.[0] || null); setSource(""); }} />
        <div className="source-input"><span>↗</span><input aria-label="YouTube URL" placeholder="Paste a YouTube URL or local path" value={source} disabled={Boolean(file)} onChange={(event) => setSource(event.target.value)} />{file && <strong>{file.name}</strong>}</div>
        <div className="control-row"><label>PROFILE<select value={profile} onChange={(event) => setProfile(event.target.value)}>{(settings?.profiles || fallbackProfiles).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label><label>SPEECH<select value={speech} onChange={(event) => setSpeech(event.target.value)}><option value="auto">Automatic</option><option value="none">Captions only</option><option value="faster_whisper">Local Whisper</option><option value="openai_compatible">Remote API</option></select></label></div>
        <button className="advanced-toggle" onClick={() => setAdvancedOpen((value) => !value)} aria-expanded={advancedOpen}>Advanced settings <span>{advancedOpen ? "−" : "+"}</span></button>
        {advancedOpen && <div className="advanced-panel">
          <div className="settings-section"><div className="settings-title">WORKFLOW / TASK</div><label>WORKFLOW<select value={workflow} onChange={(event) => selectWorkflow(event.target.value)}>{(settings?.workflows || [{ id: "exam_study_pack", name: "Exam study pack", description: "Questions and evidence", blocks: [] }]).map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>{selectedWorkflow && <small className="settings-description">{selectedWorkflow.description}</small>}<div className="control-row"><label>TASK<select value={taskKind} onChange={(event) => setTaskKind(event.target.value)}><option value="auto">Use workflow default</option><option value="questions">Questions</option><option value="summary">Summary</option><option value="visual_notes">Visual notes</option><option value="custom">Custom instruction</option></select></label><label>MAX ITEMS<input type="number" min="1" max="1000" value={taskMaxItems} onChange={(event) => setTaskMaxItems(Number(event.target.value) || 1)} /></label></div><label>TASK TITLE<input value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} placeholder="Optional output title" /></label><label>TASK INSTRUCTION<textarea className="settings-textarea" value={taskInstruction} onChange={(event) => setTaskInstruction(event.target.value)} placeholder="What should the task produce? Built-in tasks can remain empty." /></label><div className="block-grid">{(selectedWorkflow?.blocks || []).filter((block) => block.id !== "acquire").map((block) => <label className="toggle-row block-toggle" key={block.id}><span>{block.id.replace("_", " ")} <small>{block.kind}</small></span><input type="checkbox" checked={blockOverrides[block.id] ?? block.enabled} onChange={(event) => setBlockOverrides((current) => ({ ...current, [block.id]: event.target.checked }))} /></label>)}</div></div>
          <div className="settings-section"><div className="settings-title">LANGUAGE</div><div className="control-row"><label>INPUT LANGUAGE<select value={inputLanguage} onChange={(event) => setInputLanguage(event.target.value)}>{(settings?.languages || fallbackLanguages).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label><label>OUTPUT LANGUAGE<select value={outputLanguage} onChange={(event) => setOutputLanguage(event.target.value)}><option value="same">Same as source</option>{(settings?.languages || fallbackLanguages).filter((item) => item.id !== "auto").map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label></div><label>OCR LANGUAGE<select value={ocrLanguage} onChange={(event) => setOcrLanguage(event.target.value)}>{(settings?.ocr_languages || fallbackOcr).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label></div>
          <div className="settings-section"><div className="settings-title">LLM ENRICHMENT</div><label className="toggle-row"><span>Enable LLM tasks and explanations</span><input type="checkbox" checked={llmEnabled} onChange={(event) => { setLlmEnabled(event.target.checked); if (!event.target.checked) setLlmProvider("none"); }} /></label><label>PROVIDER<select value={llmProvider} onChange={(event) => setLlmProvider(event.target.value)} disabled={!llmEnabled}>{(settings?.llm || [{ id: "none", label: "No LLM" }]).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label><label>MODEL<input list="llm-models" value={llmModel} disabled={!llmEnabled} onChange={(event) => setLlmModel(event.target.value)} placeholder="Provider model name" /><datalist id="llm-models">{selectedProvider?.model_examples.map((model) => <option value={model} key={model} />)}</datalist></label><div className="control-row"><label>BASE URL<input value={llmBaseUrl} disabled={!llmEnabled} onChange={(event) => setLlmBaseUrl(event.target.value)} placeholder="Optional custom endpoint" /></label><label>KEY ENVIRONMENT VARIABLE<input value={llmApiKeyEnv} disabled={!llmEnabled} onChange={(event) => setLlmApiKeyEnv(event.target.value)} placeholder="OPENAI_API_KEY" /></label></div><label className="toggle-row"><span>Send low-confidence frames for visual analysis</span><input type="checkbox" checked={llmVision} disabled={!llmEnabled} onChange={(event) => setLlmVision(event.target.checked)} /></label>{llmEnabled && selectedProvider && <small className={selectedProvider.configured ? "provider-ready" : "provider-missing"}>{selectedProvider.configured ? "Provider key appears configured on the server." : "Provider key is not configured in the container environment."}</small>}</div>
          <div className="settings-section"><div className="settings-title">OUTPUT / REVIEW</div><div className="control-row"><label className="toggle-row"><span>Word</span><input type="checkbox" checked={outputWord} onChange={(event) => setOutputWord(event.target.checked)} /></label><label className="toggle-row"><span>PDF</span><input type="checkbox" checked={outputPdf} onChange={(event) => setOutputPdf(event.target.checked)} /></label><label className="toggle-row"><span>CSV questions</span><input type="checkbox" checked={outputCsv} onChange={(event) => setOutputCsv(event.target.checked)} /></label><label className="toggle-row"><span>Transcript file</span><input type="checkbox" checked={outputTranscript} onChange={(event) => setOutputTranscript(event.target.checked)} /></label></div><label className="toggle-row"><span>Require human review before final artifacts</span><input type="checkbox" checked={reviewGate} onChange={(event) => setReviewGate(event.target.checked)} /></label></div>
        </div>}
        <button className="primary-button" disabled={!hasInput || busy} onClick={submit}>{busy ? "Starting…" : "Process source"}<span>→</span></button><p className="microcopy">No LLM required · Your keys stay on the server · Resumable artifacts</p>
      </div>
      <div className="panel philosophy-panel"><span className="section-number">WHY THIS WORKS</span><h2>Evidence before inference.</h2><p>Every result can combine speech, OCR, visuals, and an explicit task instruction without hiding the source evidence.</p><div className="channel"><span className="channel-icon audio">◒</span><div><b>Speech</b><small>Captions or local Whisper with timestamps</small></div></div><div className="channel"><span className="channel-icon visual">▧</span><div><b>Visuals</b><small>Keyframes, OCR, diagrams, and tables</small></div></div><div className="channel"><span className="channel-icon trace">⌁</span><div><b>Traceability</b><small>Evidence links and confidence on every claim</small></div></div></div>
    </section>
    {(job || error) && <section className="results-area"><div className="panel pipeline-panel"><div className="panel-heading"><div><span className="section-number">02</span><h2>Pipeline live view</h2></div>{job && <span className={`job-state ${job.status}`}>{job.status}</span>}</div><div className="stage-list">{visibleStages.map((stage, index) => <div className={`stage ${stage.status}`} key={stage.name}><span className="stage-index">{stage.status === "completed" ? "✓" : String(index + 1).padStart(2, "0")}</span><div><b>{stage.name.replace("_", " ")}</b><small>{stage.status}</small></div><span className="stage-line" /></div>)}</div>{job && !["completed", "awaiting_review", "failed", "cancelled"].includes(job.status) && <button className="quiet-button" onClick={cancel}>Cancel job</button>}{job?.status === "awaiting_review" && <p className="review-intro">Final artifacts are paused until the human review queue is resolved.</p>}{error && <div className="error-box"><b>Could not start processing</b><span>{error}</span></div>}{job?.warnings?.map((warning) => <div className="warning" key={warning}>⚠ {warning}</div>)}<div className="event-log">{events.slice(-4).map((event) => <span key={event}>› {event}</span>)}</div></div>{job?.status === "completed" && <div className="panel study-panel"><div className="panel-heading"><div><span className="section-number">03</span><h2>Generated output</h2></div><span className="status-dot">READY</span></div><div className="metric-row"><div><strong>{questionCount}</strong><span>structured items</span></div><div><strong>{transcriptCount}</strong><span>{data?.transcript?.language || "speech"} segments</span></div><div><strong>{data?.ocr?.length || 0}</strong><span>visual frames</span></div></div><div className="question-preview">{data?.questions?.slice(0, 3).map((question, index) => <article key={`${question.prompt}-${index}`}><span className="question-number">Q{String(index + 1).padStart(2, "0")}</span><h3>{question.prompt}</h3>{question.answer && <p className="answer-line"><b>Answer {question.answer}</b>{question.explanation && ` · ${question.explanation}`}</p>}</article>)}{!questionCount && <p className="empty-state">{taskContent || "The processing completed without detecting structured items. Review the transcript and visual evidence."}</p>}</div><div className="downloads"><a href={`${API}/api/jobs/${job.job_id}/artifacts/extraction.md`} target="_blank" rel="noreferrer">Markdown ↗</a><a href={`${API}/api/jobs/${job.job_id}/artifacts/extraction.json`} target="_blank" rel="noreferrer">JSON ↗</a>{hasArtifact("extraction.docx") && <a href={`${API}/api/jobs/${job.job_id}/artifacts/extraction.docx`} target="_blank" rel="noreferrer">Word ↗</a>}{hasArtifact("extraction.pdf") && <a href={`${API}/api/jobs/${job.job_id}/artifacts/extraction.pdf`} target="_blank" rel="noreferrer">PDF ↗</a>}{hasArtifact("questions.csv") && <a href={`${API}/api/jobs/${job.job_id}/artifacts/questions.csv`} target="_blank" rel="noreferrer">CSV ↗</a>}{hasArtifact("transcript.md") && <a href={`${API}/api/jobs/${job.job_id}/artifacts/transcript.md`} target="_blank" rel="noreferrer">Transcript ↗</a>}</div></div>}</section>}
    {job && ["completed", "awaiting_review"].includes(job.status) && review && <section className="review-area"><div className="panel review-panel"><div className="panel-heading"><div><span className="section-number">04</span><h2>Human review</h2></div><span className={`job-state ${review.summary.needs_review ? "failed" : "completed"}`}>{review.summary.needs_review} need review</span></div><p className="review-intro">Review low-confidence items against their transcript and visual evidence before generating final outputs.</p><div className="review-layout"><div className="review-queue">{review.items.filter((item) => item.review_status === "needs_review").map((item) => <button className={`review-queue-item ${selectedReviewId === item.question_id ? "active" : ""}`} key={item.question_id} onClick={() => openReview(item)}><span>{item.question_id}</span><strong>{item.prompt}</strong><small>{Math.round((item.confidence || 0) * 100)}% confidence</small></button>)}{!review.summary.needs_review && <p className="empty-state">No low-confidence items are waiting for review.</p>}</div>{selectedReviewId && <div className="review-editor"><div className="review-confidence">Confidence: {Math.round(((review.items.find((item) => item.question_id === selectedReviewId)?.confidence || 0) * 100))}%</div><label>QUESTION<textarea value={reviewDraft.prompt} onChange={(event) => setReviewDraft({ ...reviewDraft, prompt: event.target.value })} /></label><label>OPTIONS<textarea value={reviewDraft.options} onChange={(event) => setReviewDraft({ ...reviewDraft, options: event.target.value })} /></label><label>ANSWER<input value={reviewDraft.answer} onChange={(event) => setReviewDraft({ ...reviewDraft, answer: event.target.value })} /></label><label>EXPLANATION<textarea value={reviewDraft.explanation} onChange={(event) => setReviewDraft({ ...reviewDraft, explanation: event.target.value })} /></label><label>REVIEW NOTE<textarea value={reviewDraft.review_note} onChange={(event) => setReviewDraft({ ...reviewDraft, review_note: event.target.value })} placeholder="Why was this approved or edited?" /></label><div className="review-actions"><button className="quiet-button" disabled={reviewBusy} onClick={() => saveReview("rejected")}>Reject</button><button className="quiet-button" disabled={reviewBusy} onClick={() => saveReview("edited")}>Save edit</button><button className="primary-button" disabled={reviewBusy} onClick={() => saveReview("approved")}>Approve <span>✓</span></button></div></div>}</div><button className="quiet-button review-complete" disabled={Boolean(review.summary.needs_review)} onClick={completeReview}>Mark review complete</button></div></section>}
    <footer><span>SOURCEFLOW <b>0.1</b></span><span>OPEN SOURCE · LOCAL-FIRST · PROVIDER-ELASTIC</span></footer>
  </main>;
}

export default App;
