import { useState, useEffect } from "react";
import TopicSelector from "./components/TopicSelector";
import DiscussionView from "./components/DiscussionView";
import AnalyticsView from "./components/AnalyticsView";
import { useDiscussion } from "./components/useDiscussion";
import { createDiscussion, fetchAnalytics, searchKnowledgeBase } from "./api/discussionApi";
import sampleAnalytics from "./data/sample_analytics.json";
import "./App.css";

const SAMPLE_TOPICS = [
  "Mexico vs South Africa — 2026 Opening Match",
  "Argentina vs Spain — 2026 FIFA World Cup Final",
  "France vs England — 2026 World Cup Third Place",
];

function App() {
  // "select" -> "creating" -> "viewing" | "sample"
  const [phase, setPhase] = useState("select");
  const [discussionId, setDiscussionId] = useState(null);
  const [createError, setCreateError] = useState(null);

  // Knowledge base drawer
  const [showRetrieval, setShowRetrieval] = useState(false);
  const [kbQuery, setKbQuery] = useState("");
  const [kbResults, setKbResults] = useState(null);
  const [kbLoading, setKbLoading] = useState(false);
  const [kbError, setKbError] = useState(null);

  async function handleStart(topic) {
    setCreateError(null);
    setPhase("creating");
    try {
      const result = await createDiscussion(topic);
      setDiscussionId(result.discussion_id);
      setPhase("viewing");
    } catch (err) {
      setCreateError(err.message || "Failed to start discussion.");
      setPhase("select");
    }
  }

  function handleViewSample() {
    setDiscussionId("disc_bc528f51d882");
    setPhase("sample");
  }

  function handleBack() {
    setPhase("select");
    setDiscussionId(null);
    setCreateError(null);
  }

  async function handleSearchKB(e) {
    e.preventDefault();
    if (!kbQuery.trim()) return;
    setKbLoading(true);
    setKbError(null);
    try {
      const res = await searchKnowledgeBase(kbQuery.trim(), 3);
      setKbResults(res);
    } catch (err) {
      setKbError(err.message || "Failed to query knowledge base.");
    } finally {
      setKbLoading(false);
    }
  }

  return (
    <div className="app-shell">
      {/* Top Header / Knowledge Base Toggle */}
      <header className="app-topbar">
        <div className="app-topbar__brand">
          <span className="brand-dot"></span>
          <span className="brand-title">Qubeterra Multi-Agent Platform</span>
          <span className="brand-tag">Production</span>
        </div>
        <div className="app-topbar__actions">
          <button
            className="topbar-btn"
            onClick={() => setShowRetrieval(!showRetrieval)}
          >
            {showRetrieval ? "✕ Close KB Search" : "🔍 Knowledge Base (RAG)"}
          </button>
        </div>
      </header>

      {/* Knowledge Base Drawer */}
      {showRetrieval && (
        <aside className="kb-drawer">
          <div className="kb-drawer__content">
            <div className="kb-drawer__header">
              <h3>Knowledge Base Retrieval</h3>
              <p>Query the embedded football domain documents directly.</p>
            </div>
            <form onSubmit={handleSearchKB} className="kb-form">
              <input
                type="text"
                placeholder="e.g. World Cup 2026 final tactics, yellow cards..."
                value={kbQuery}
                onChange={(e) => setKbQuery(e.target.value)}
                className="kb-input"
              />
              <button type="submit" disabled={kbLoading} className="kb-submit">
                {kbLoading ? "Searching…" : "Search"}
              </button>
            </form>
            {kbError && <p className="kb-error">⚠ {kbError}</p>}
            {kbResults && (
              <div className="kb-results">
                <h4>Sources Found ({kbResults.sources?.length || 0}):</h4>
                {kbResults.sources && kbResults.sources.length > 0 ? (
                  kbResults.sources.map((src, idx) => (
                    <div key={idx} className="kb-result-card">
                      <div className="kb-result-header">
                        <strong>Source {src.source_id || idx + 1}</strong>
                        {typeof src.score === "number" && (
                          <span className="kb-score">Score: {src.score.toFixed(3)}</span>
                        )}
                      </div>
                      <p className="kb-snippet">{src.content || src.snippet || JSON.stringify(src)}</p>
                    </div>
                  ))
                ) : (
                  <p className="kb-empty">No matching documents returned.</p>
                )}
              </div>
            )}
          </div>
        </aside>
      )}

      {/* Main Workflow View */}
      {phase === "select" && (
        <main className="app-main">
          <TopicSelector predefinedTopics={SAMPLE_TOPICS} onStart={handleStart} />
          {createError && <p className="app-shell__error">⚠ {createError}</p>}
          <div className="app-sample-callout">
            <p>Want to inspect precomputed results without waiting for LLM execution?</p>
            <button className="app-shell__sample-btn" onClick={handleViewSample}>
              Load Pre-Recorded 3-Round Discussion & Analytics
            </button>
          </div>
        </main>
      )}

      {phase === "creating" && (
        <main className="app-shell app-shell--centered">
          <div className="loading-card">
            <div className="loading-spinner"></div>
            <h3>Running Multi-Agent Discussion</h3>
            <p className="app-shell__loading">
              AI agents are debating across rounds using domain retrieval context…<br />
              This may take 1–2 minutes while responses are generated and opinions tracked.
            </p>
          </div>
        </main>
      )}

      {(phase === "sample" || phase === "viewing") && (
        <SampleOrLiveDiscussion
          source={phase === "sample" ? "sample" : "backend"}
          discussionId={discussionId}
          onBack={handleBack}
        />
      )}
    </div>
  );
}

function SampleOrLiveDiscussion({ source, discussionId, onBack }) {
  const [currentView, setCurrentView] = useState("discussion"); // "discussion" | "analytics"
  const { discussion, error: discError, loading: discLoading } = useDiscussion(discussionId, source);

  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState(null);

  useEffect(() => {
    if (source === "sample") {
      setAnalytics(sampleAnalytics);
      return;
    }

    if (discussionId) {
      setAnalyticsLoading(true);
      fetchAnalytics(discussionId)
        .then((data) => {
          setAnalytics(data);
          setAnalyticsError(null);
        })
        .catch((err) => {
          setAnalyticsError(err.message || "Failed to load live analytics.");
          // Fall back gracefully to sample analytics structure for visualization
          setAnalytics(sampleAnalytics);
        })
        .finally(() => {
          setAnalyticsLoading(false);
        });
    }
  }, [discussionId, source]);

  return (
    <div className="discussion-shell">
      {/* Navigation Sub-bar */}
      <div className="view-toolbar">
        <button className="app-shell__back" onClick={onBack}>
          ← Back to Topics
        </button>

        <div className="view-toggle-group">
          <button
            className={`toggle-btn ${currentView === "discussion" ? "toggle-btn--active" : ""}`}
            onClick={() => setCurrentView("discussion")}
          >
            💬 Discussion View ({discussion?.num_rounds || 3} Rounds)
          </button>
          <button
            className={`toggle-btn ${currentView === "analytics" ? "toggle-btn--active" : ""}`}
            onClick={() => setCurrentView("analytics")}
          >
            📊 Analytics Dashboard
          </button>
        </div>
      </div>

      {currentView === "discussion" ? (
        <div className="view-pane">
          {discLoading && <p className="app-shell__loading">Loading discussion…</p>}
          {discError && <p className="app-shell__error">⚠ {discError}</p>}
          {!discLoading && !discError && <DiscussionView discussion={discussion} />}
        </div>
      ) : (
        <div className="view-pane">
          {analyticsLoading && <p className="app-shell__loading">Computing analytics metrics…</p>}
          {analyticsError && (
            <div className="analytics-warning-banner">
              <span>Notice: Live analytics call failed ({analyticsError}). Showing precomputed reference analytics.</span>
            </div>
          )}
          {analytics && <AnalyticsView analytics={analytics} discussion={discussion} />}
        </div>
      )}
    </div>
  );
}

export default App;
