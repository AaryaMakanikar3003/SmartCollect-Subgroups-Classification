// import { useState, useEffect } from "react";
// import "./App.css";

// const API_BASE = "http://127.0.0.1:8000";

// function defaultToDate() {
//   return new Date().toISOString().slice(0, 10);
// }
// function defaultFromDate() {
//   const d = new Date();
//   d.setDate(d.getDate() - 30);
//   return d.toISOString().slice(0, 10);
// }

// function sentimentOf(name) {
//   const n = (name || "").toLowerCase();
//   if (/(positive|paid|settlement|agreed|confirm)/.test(n)) return "positive";
//   if (/(negative|denied|wrong|busy|missing|refus)/.test(n)) return "negative";
//   if (/(callback|doubtful|pending|hello|saved)/.test(n)) return "info";
//   return "neutral";
// }

// // Renders one node of the dynamic tree (subgroup -> bucket -> breakdown -> ...
// // however deep it actually goes, since nothing about depth is fixed anymore).
// // Leaf nodes (no children) show sample conversations instead of a sub-list.
// function TreeNode({ node, path, openPaths, onToggle }) {
//   const key = path.join("/");
//   const isOpen = !!openPaths[key];
//   const hasChildren = node.children && node.children.length > 0;

//   return (
//     <div className="tree-node">
//       <button className="tree-toggle" onClick={() => onToggle(key)}>
//         <span className="tree-toggle-name">{node.name}</span>
//         <span className="tree-toggle-count mono">{node.count}</span>
//         <span className="tree-toggle-chevron">{isOpen ? "▾" : "▸"}</span>
//       </button>

//       {node.description && <p className="tree-node-desc">{node.description}</p>}

//       {isOpen && (
//         <div className="tree-node-body">
//           {hasChildren ? (
//             <div className="tree-children">
//               {node.children.map((child, i) => (
//                 <TreeNode
//                   key={i}
//                   node={child}
//                   path={[...path, i]}
//                   openPaths={openPaths}
//                   onToggle={onToggle}
//                 />
//               ))}
//             </div>
//           ) : (
//             <ul className="conversation-list">
//               {(node.sample_conversations || []).length === 0 && (
//                 <li className="empty-state">No sample conversations.</li>
//               )}
//               {(node.sample_conversations || []).map((ex, k) => (
//                 <details key={k} className="conversation-card">
//                   <summary>Convo ID: {ex.conversation_id}</summary>
//                   <pre>{ex.preview}</pre>
//                 </details>
//               ))}
//             </ul>
//           )}
//         </div>
//       )}
//     </div>
//   );
// }

// function App() {
//   const [banks, setBanks] = useState([]);
//   const [campaigns, setCampaigns] = useState([]);
//   const [selectedBank, setSelectedBank] = useState("");
//   const [selectedCampaign, setSelectedCampaign] = useState("");
//   const [fromDate, setFromDate] = useState(defaultFromDate());
//   const [toDate, setToDate] = useState(defaultToDate());
//   const [loadingCampaigns, setLoadingCampaigns] = useState(false);

//   const [summary, setSummary] = useState(null);
//   const [loadingSummary, setLoadingSummary] = useState(false);

//   const [progressLog, setProgressLog] = useState([]);
//   const [currentStatus, setCurrentStatus] = useState("");
//   const [isRunning, setIsRunning] = useState(false);
//   const [error, setError] = useState("");
//   const [showLog, setShowLog] = useState(false);

//   const [directResult, setDirectResult] = useState(null);
//   const [selectedCluster, setSelectedCluster] = useState(null);

//   // path (as "0/1/2" strings) -> open/closed, reset each time a new cluster modal opens
//   const [openPaths, setOpenPaths] = useState({});

//   const openCluster = (cluster) => {
//     setSelectedCluster(cluster);
//     setOpenPaths({});
//   };

//   const toggleOpenPath = (key) => {
//     setOpenPaths((prev) => ({ ...prev, [key]: !prev[key] }));
//   };

//   const [modal, setModal] = useState(null);
//   const [limitInput, setLimitInput] = useState("");

//   useEffect(() => {
//     fetch(`${API_BASE}/banks`)
//       .then((res) => res.json())
//       .then(setBanks)
//       .catch((err) => setError("Failed to load banks: " + err.message));
//   }, []);

//   useEffect(() => {
//     setCampaigns([]);
//     setSelectedCampaign("");
//     setSummary(null);
//     setDirectResult(null);
//     setProgressLog([]);
//     setCurrentStatus("");
//     setError("");
//     setShowLog(false);

//     if (!selectedBank) return;

//     setLoadingCampaigns(true);
//     fetch(`${API_BASE}/campaigns?bank_id=${selectedBank}`)
//       .then((res) => {
//         if (!res.ok) throw new Error(`No campaigns found (status ${res.status})`);
//         return res.json();
//       })
//       .then(setCampaigns)
//       .catch((err) => {
//         setCampaigns([]);
//         setError(err.message);
//       })
//       .finally(() => setLoadingCampaigns(false));
//   }, [selectedBank]);

//   useEffect(() => {
//     setSummary(null);
//     setDirectResult(null);
//   }, [selectedCampaign, fromDate, toDate]);

//   const loadCategories = () => {
//     if (!selectedCampaign || !fromDate || !toDate) return;

//     setLoadingSummary(true);
//     setError("");
//     setSummary(null);
//     setDirectResult(null);

//     const url = `${API_BASE}/conversations/summary?campaign_id=${selectedCampaign}&from_date=${fromDate}&to_date=${toDate}`;

//     fetch(url)
//       .then((res) => {
//         if (!res.ok) throw new Error(`Failed to load categories (status ${res.status})`);
//         return res.json();
//       })
//       .then(setSummary)
//       .catch((err) => setError(err.message))
//       .finally(() => setLoadingSummary(false));
//   };

//   const runDirectAnalysis = (category, limit) => {
//     setIsRunning(true);
//     setProgressLog([]);
//     setCurrentStatus("Connecting...");
//     setDirectResult(null);
//     setError("");
//     setShowLog(false);

//     const ws = new WebSocket(`ws://127.0.0.1:8000/ws/analyze-direct`);

//     ws.onopen = () => {
//       ws.send(
//         JSON.stringify({
//           campaign_id: Number(selectedCampaign),
//           from_date: fromDate,
//           to_date: toDate,
//           category,
//           limit: limit ?? null,
//         })
//       );
//     };

//     ws.onmessage = (event) => {
//       const msg = JSON.parse(event.data);
//       if (msg.status === "progress") {
//         setCurrentStatus(msg.message);
//         setProgressLog((prev) => [...prev, msg.message]);
//       } else if (msg.status === "done") {
//         setDirectResult(msg.result);
//         setIsRunning(false);
//         setCurrentStatus("");
//         ws.close();
//       } else if (msg.status === "error") {
//         setError(msg.message);
//         setIsRunning(false);
//         setCurrentStatus("");
//         ws.close();
//       }
//     };

//     ws.onerror = () => {
//       setError("WebSocket connection failed");
//       setIsRunning(false);
//       setCurrentStatus("");
//     };
//   };

//   const handleCategoryClick = (category, count) => {
//     if (isRunning) return;
//     setLimitInput(String(Math.min(1000, count)));
//     setModal({ step: "confirm-all", category, count });
//   };

//   const closeModal = () => setModal(null);

//   const handleModalConfirmAll = () => {
//     const { category } = modal;
//     closeModal();
//     runDirectAnalysis(category, null);
//   };

//   const handleModalWantsLimit = () => {
//     setModal((m) => ({ ...m, step: "ask-limit" }));
//   };

//   const handleModalLimitSubmit = () => {
//     const limit = parseInt(limitInput, 10);
//     if (!Number.isFinite(limit) || limit <= 0) {
//       setError("Please enter a valid positive number for the limit.");
//       closeModal();
//       return;
//     }
//     setModal((m) => ({ ...m, step: "confirm-limit", limit }));
//   };

//   const handleModalConfirmLimit = () => {
//     const { category, limit } = modal;
//     closeModal();
//     runDirectAnalysis(category, limit);
//   };

//   const sortedCategories = summary
//     ? Object.entries(summary.categories).sort((a, b) => b[1] - a[1])
//     : [];
//   const maxCount = sortedCategories.length ? sortedCategories[0][1] : 1;

//   return (
//     <div className="page">
//       <div className="container">
//         <header className="header">
//           <div className="eyebrow">
//             <span className="eyebrow-dot" />
//             SUBGROUP CONSOLE
//           </div>
//           <h1>SmartCollect Subgroup Classifier</h1>
//           <p className="subtitle">Discover conversation subgroups per campaign, on demand</p>
//         </header>

//         <div className="panel controls-panel">
//           <div className="controls">
//             <div className="field">
//               <label>Bank</label>
//               <select value={selectedBank} onChange={(e) => setSelectedBank(e.target.value)}>
//                 <option value="">Select a bank...</option>
//                 {banks.map((b) => (
//                   <option key={b.bank_id} value={b.bank_id}>{b.bank_name}</option>
//                 ))}
//               </select>
//             </div>

//             <div className="field">
//               <label>Campaign</label>
//               <select
//                 value={selectedCampaign}
//                 onChange={(e) => setSelectedCampaign(e.target.value)}
//                 disabled={!selectedBank || loadingCampaigns}
//               >
//                 <option value="">
//                   {loadingCampaigns ? "Loading campaigns..." : "Select a campaign..."}
//                 </option>
//                 {campaigns.map((c) => (
//                   <option key={c.campaign_id} value={c.campaign_id}>{c.campaign_name}</option>
//                 ))}
//               </select>
//             </div>

//             <div className="field field-small">
//               <label>From</label>
//               <input type="date" value={fromDate} max={toDate} onChange={(e) => setFromDate(e.target.value)} />
//             </div>

//             <div className="field field-small">
//               <label>To</label>
//               <input
//                 type="date"
//                 value={toDate}
//                 min={fromDate}
//                 max={defaultToDate()}
//                 onChange={(e) => setToDate(e.target.value)}
//               />
//             </div>

//             <button
//               className="btn-primary"
//               onClick={loadCategories}
//               disabled={!selectedCampaign || loadingSummary || isRunning}
//             >
//               {loadingSummary ? "Loading…" : "Load Categories"}
//             </button>
//           </div>
//         </div>

//         {error && <div className="panel error-panel">{error}</div>}

//         {summary && (
//           <div className="panel">
//             <div className="panel-heading">
//               <h2>Categories</h2>
//               <span className="panel-heading-sub">
//                 <span className="mono">{summary.usable_conversations}</span> of{" "}
//                 <span className="mono">{summary.total_conversations}</span> usable
//                 &nbsp;·&nbsp; click a category to analyze it
//               </span>
//             </div>

//             {sortedCategories.length === 0 ? (
//               <p className="empty-state">No categorized conversations found in this date range.</p>
//             ) : (
//               <div className="category-grid">
//                 {sortedCategories.map(([category, count]) => {
//                   const sentiment = sentimentOf(category);
//                   const pct = Math.max(4, Math.round((count / maxCount) * 100));
//                   return (
//                     <button
//                       key={category}
//                       className={`category-card cat-${sentiment}`}
//                       onClick={() => handleCategoryClick(category, count)}
//                       disabled={isRunning}
//                     >
//                       <div className="category-card-top">
//                         <span className="category-card-name">{category}</span>
//                         <span className="category-card-count mono">{count}</span>
//                       </div>
//                       <div className="category-bar-track">
//                         <div className="category-bar-fill" style={{ width: `${pct}%` }} />
//                       </div>
//                     </button>
//                   );
//                 })}
//               </div>
//             )}
//           </div>
//         )}

//         {(isRunning || progressLog.length > 0) && (
//           <div className="panel status-panel">
//             <div className="status-line">
//               {isRunning && <span className="spinner" />}
//               <span className={isRunning ? "status-text active" : "status-text"}>
//                 {isRunning ? currentStatus : "Finished"}
//               </span>
//             </div>
//             {progressLog.length > 0 && (
//               <button className="log-toggle" onClick={() => setShowLog((v) => !v)}>
//                 {showLog ? "Hide log" : "Show full log"}
//               </button>
//             )}
//             {showLog && (
//               <div className="progress-log mono">
//                 {progressLog.map((msg, i) => (
//                   <div key={i}>{msg}</div>
//                 ))}
//               </div>
//             )}
//           </div>
//         )}

//         {directResult && (
//           <div className="results">
//             <div className="panel-heading">
//               <h2>Results</h2>
//               <span className="panel-heading-sub">
//                 <span className="mono">{directResult.usable_conversations}</span> of{" "}
//                 <span className="mono">{directResult.total_conversations}</span> usable
//               </span>
//             </div>

//             {Object.keys(directResult.categories).length === 0 && (
//               <div className="panel">
//                 <p className="empty-state">No conversations found for this selection.</p>
//               </div>
//             )}

//             {Object.entries(directResult.categories).map(([category, data]) => {
//               const sentiment = sentimentOf(category);
//               return (
//                 <div key={category} className="panel">
//                   <div className="panel-heading">
//                     <h3 className={`cat-label cat-${sentiment}`}>{category}</h3>
//                     <span className="panel-heading-sub mono">{data.total}</span>
//                   </div>
//                   <div className="cluster-grid">
//                     {data.clusters.map((cluster, i) => (
//                       <div
//                         key={i}
//                         className="cluster-card clickable"
//                         onClick={() => openCluster(cluster)}
//                       >
//                         <div className="cluster-header">
//                           <strong>{cluster.name}</strong>
//                           <span className="cluster-count mono">{cluster.count}</span>
//                         </div>
//                         <p>{cluster.description}</p>
//                       </div>
//                     ))}
//                   </div>
//                 </div>
//               );
//             })}
//           </div>
//         )}
//       </div>

//       {modal && (
//         <div className="modal-overlay" onClick={closeModal}>
//           <div className="modal-box" onClick={(e) => e.stopPropagation()}>
//             <div className="modal-tag">CONFIRM</div>

//             {modal.step === "confirm-all" && (
//               <>
//                 <h3 className="modal-title">Run analysis?</h3>
//                 <p className="modal-body">
//                   Send all <strong className="mono">{modal.count}</strong> conversation(s) in{" "}
//                   <strong>"{modal.category}"</strong> to the LLM?
//                 </p>
//                 <div className="modal-actions">
//                   <button className="modal-btn modal-btn-ghost" onClick={handleModalWantsLimit}>
//                     Use a smaller batch
//                   </button>
//                   <div className="modal-actions-right">
//                     <button className="modal-btn modal-btn-secondary" onClick={closeModal}>Cancel</button>
//                     <button className="modal-btn modal-btn-primary" onClick={handleModalConfirmAll}>
//                       Run on all {modal.count}
//                     </button>
//                   </div>
//                 </div>
//               </>
//             )}

//             {modal.step === "ask-limit" && (
//               <>
//                 <h3 className="modal-title">How many conversations?</h3>
//                 <p className="modal-body">
//                   Out of <strong className="mono">{modal.count}</strong> in <strong>"{modal.category}"</strong>:
//                 </p>
//                 <input
//                   type="number"
//                   className="modal-input mono"
//                   value={limitInput}
//                   min="1"
//                   max={modal.count}
//                   autoFocus
//                   onChange={(e) => setLimitInput(e.target.value)}
//                   onKeyDown={(e) => e.key === "Enter" && handleModalLimitSubmit()}
//                 />
//                 <div className="modal-actions">
//                   <div className="modal-actions-right" style={{ marginLeft: "auto" }}>
//                     <button className="modal-btn modal-btn-secondary" onClick={closeModal}>Cancel</button>
//                     <button className="modal-btn modal-btn-primary" onClick={handleModalLimitSubmit}>Continue</button>
//                   </div>
//                 </div>
//               </>
//             )}

//             {modal.step === "confirm-limit" && (
//               <>
//                 <h3 className="modal-title">Confirm batch size</h3>
//                 <p className="modal-body">
//                   Run on the first <strong className="mono">{modal.limit}</strong> of{" "}
//                   <strong className="mono">{modal.count}</strong> conversation(s) in{" "}
//                   <strong>"{modal.category}"</strong>?
//                 </p>
//                 <div className="modal-actions">
//                   <div className="modal-actions-right" style={{ marginLeft: "auto" }}>
//                     <button className="modal-btn modal-btn-secondary" onClick={closeModal}>Cancel</button>
//                     <button className="modal-btn modal-btn-primary" onClick={handleModalConfirmLimit}>Run</button>
//                   </div>
//                 </div>
//               </>
//             )}
//           </div>
//         </div>
//       )}

//       {selectedCluster && (
//         <div className="modal-overlay" onClick={() => setSelectedCluster(null)}>
//           <div className="cluster-details-modal" onClick={(e) => e.stopPropagation()}>
//             <h2>{selectedCluster.name}</h2>
//             <p><strong>Total conversations:</strong> {selectedCluster.count}</p>
//             {selectedCluster.description && <p>{selectedCluster.description}</p>}

//             {selectedCluster.children && selectedCluster.children.length > 0 ? (
//               <>
//                 <h3>Breakdown</h3>
//                 <div className="tree-children root-tree-children">
//                   {selectedCluster.children.map((child, i) => (
//                     <TreeNode
//                       key={i}
//                       node={child}
//                       path={[i]}
//                       openPaths={openPaths}
//                       onToggle={toggleOpenPath}
//                     />
//                   ))}
//                 </div>
//               </>
//             ) : (
//               <>
//                 <h3>Sample Conversations</h3>
//                 {(selectedCluster.sample_conversations || []).map((ex, index) => (
//                   <details key={index} className="conversation-card">
//                     <summary>Conversation ID: {ex.conversation_id}</summary>
//                     <pre>{ex.preview}</pre>
//                   </details>
//                 ))}
//               </>
//             )}

//             <button
//               className="modal-btn modal-btn-primary close-btn"
//               onClick={() => setSelectedCluster(null)}
//             >
//               Close
//             </button>
//           </div>
//         </div>
//       )}
//     </div>
//   );
// }

// export default App;






















import { useState, useEffect } from "react";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

function defaultToDate() {
  return new Date().toISOString().slice(0, 10);
}
function defaultFromDate() {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().slice(0, 10);
}

function sentimentOf(name) {
  const n = (name || "").toLowerCase();
  if (/(positive|paid|settlement|agreed|confirm)/.test(n)) return "positive";
  if (/(negative|denied|wrong|busy|missing|refus)/.test(n)) return "negative";
  if (/(callback|doubtful|pending|hello|saved)/.test(n)) return "info";
  return "neutral";
}

// Renders one node of the dynamic tree (subgroup -> bucket -> breakdown -> ...
// however deep it actually goes, since nothing about depth is fixed anymore).
// Leaf nodes (no children) show sample conversations instead of a sub-list.
function TreeNode({ node, path, openPaths, onToggle }) {
  const key = path.join("/");
  const isOpen = !!openPaths[key];
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div className="tree-node">
      <button className="tree-toggle" onClick={() => onToggle(key)}>
        <span className="tree-toggle-name">{node.name}</span>
        <span className="tree-toggle-count mono">{node.count}</span>
        <span className="tree-toggle-chevron">{isOpen ? "▾" : "▸"}</span>
      </button>

      {node.description && <p className="tree-node-desc">{node.description}</p>}

      {isOpen && (
        <div className="tree-node-body">
          {hasChildren ? (
            <div className="tree-children">
              {node.children.map((child, i) => (
                <TreeNode
                  key={i}
                  node={child}
                  path={[...path, i]}
                  openPaths={openPaths}
                  onToggle={onToggle}
                />
              ))}
            </div>
          ) : (
            <ul className="conversation-list">
              {(node.sample_conversations || []).length === 0 && (
                <li className="empty-state">No sample conversations.</li>
              )}
              {(node.sample_conversations || []).map((ex, k) => (
                <details key={k} className="conversation-card">
                  <summary>Convo ID: {ex.conversation_id}</summary>
                  <pre>{ex.preview}</pre>
                </details>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function App() {
  const [banks, setBanks] = useState([]);
  const [campaigns, setCampaigns] = useState([]);

  // selectedBank now encodes "<source>:<bank_id>" so we always know which
  // DB a chosen bank/campaign lives in, since ids can collide across DBs.
  const [selectedBank, setSelectedBank] = useState("");
  const [selectedCampaign, setSelectedCampaign] = useState("");
  const [fromDate, setFromDate] = useState(defaultFromDate());
  const [toDate, setToDate] = useState(defaultToDate());
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);

  const [summary, setSummary] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  const [progressLog, setProgressLog] = useState([]);
  const [currentStatus, setCurrentStatus] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState("");
  const [showLog, setShowLog] = useState(false);

  const [directResult, setDirectResult] = useState(null);
  const [selectedCluster, setSelectedCluster] = useState(null);

  // path (as "0/1/2" strings) -> open/closed, reset each time a new cluster modal opens
  const [openPaths, setOpenPaths] = useState({});

  const openCluster = (cluster) => {
    setSelectedCluster(cluster);
    setOpenPaths({});
  };

  const toggleOpenPath = (key) => {
    setOpenPaths((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const [modal, setModal] = useState(null);
  const [limitInput, setLimitInput] = useState("");

  // derive real source + bank_id from the combined "<source>:<bank_id>" value
  const [selectedSource, selectedBankId] = selectedBank
    ? selectedBank.split(":")
    : ["", ""];

  useEffect(() => {
    fetch(`${API_BASE}/banks`)
      .then((res) => res.json())
      .then(setBanks)
      .catch((err) => setError("Failed to load banks: " + err.message));
  }, []);

  useEffect(() => {
    setCampaigns([]);
    setSelectedCampaign("");
    setSummary(null);
    setDirectResult(null);
    setProgressLog([]);
    setCurrentStatus("");
    setError("");
    setShowLog(false);

    if (!selectedBank) return;

    setLoadingCampaigns(true);
    fetch(`${API_BASE}/campaigns?bank_id=${selectedBankId}&source=${selectedSource}`)
      .then((res) => {
        if (!res.ok) throw new Error(`No campaigns found (status ${res.status})`);
        return res.json();
      })
      .then(setCampaigns)
      .catch((err) => {
        setCampaigns([]);
        setError(err.message);
      })
      .finally(() => setLoadingCampaigns(false));
  }, [selectedBank]);

  useEffect(() => {
    setSummary(null);
    setDirectResult(null);
  }, [selectedCampaign, fromDate, toDate]);

  const loadCategories = () => {
    if (!selectedCampaign || !fromDate || !toDate) return;

    setLoadingSummary(true);
    setError("");
    setSummary(null);
    setDirectResult(null);

    const url = `${API_BASE}/conversations/summary?campaign_id=${selectedCampaign}&from_date=${fromDate}&to_date=${toDate}&source=${selectedSource}`;

    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load categories (status ${res.status})`);
        return res.json();
      })
      .then(setSummary)
      .catch((err) => setError(err.message))
      .finally(() => setLoadingSummary(false));
  };

  const runDirectAnalysis = (category, limit) => {
    setIsRunning(true);
    setProgressLog([]);
    setCurrentStatus("Connecting...");
    setDirectResult(null);
    setError("");
    setShowLog(false);

    const ws = new WebSocket(`ws://127.0.0.1:8000/ws/analyze-direct`);

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          campaign_id: Number(selectedCampaign),
          from_date: fromDate,
          to_date: toDate,
          category,
          limit: limit ?? null,
          source: selectedSource,
        })
      );
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.status === "progress") {
        setCurrentStatus(msg.message);
        setProgressLog((prev) => [...prev, msg.message]);
      } else if (msg.status === "done") {
        setDirectResult(msg.result);
        setIsRunning(false);
        setCurrentStatus("");
        ws.close();
      } else if (msg.status === "error") {
        setError(msg.message);
        setIsRunning(false);
        setCurrentStatus("");
        ws.close();
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection failed");
      setIsRunning(false);
      setCurrentStatus("");
    };
  };

  const handleCategoryClick = (category, count) => {
    if (isRunning) return;
    setLimitInput(String(Math.min(1000, count)));
    setModal({ step: "confirm-all", category, count });
  };

  const closeModal = () => setModal(null);

  const handleModalConfirmAll = () => {
    const { category } = modal;
    closeModal();
    runDirectAnalysis(category, null);
  };

  const handleModalWantsLimit = () => {
    setModal((m) => ({ ...m, step: "ask-limit" }));
  };

  const handleModalLimitSubmit = () => {
    const limit = parseInt(limitInput, 10);
    if (!Number.isFinite(limit) || limit <= 0) {
      setError("Please enter a valid positive number for the limit.");
      closeModal();
      return;
    }
    setModal((m) => ({ ...m, step: "confirm-limit", limit }));
  };

  const handleModalConfirmLimit = () => {
    const { category, limit } = modal;
    closeModal();
    runDirectAnalysis(category, limit);
  };

  const sortedCategories = summary
    ? Object.entries(summary.categories).sort((a, b) => b[1] - a[1])
    : [];
  const maxCount = sortedCategories.length ? sortedCategories[0][1] : 1;

  return (
    <div className="page">
      <div className="container">
        <header className="header">
          <div className="eyebrow">
            <span className="eyebrow-dot" />
            SUBGROUP CONSOLE
          </div>
          <h1>SmartCollect Subgroup Classifier</h1>
          <p className="subtitle">Discover conversation subgroups per campaign, on demand</p>
        </header>

        <div className="panel controls-panel">
          <div className="controls">
            <div className="field">
              <label>Bank</label>
              <select value={selectedBank} onChange={(e) => setSelectedBank(e.target.value)}>
                <option value="">Select a bank...</option>
                {banks.map((b) => (
                  <option key={`${b.source}-${b.bank_id}`} value={`${b.source}:${b.bank_id}`}>
                    {b.bank_name}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label>Campaign</label>
              <select
                value={selectedCampaign}
                onChange={(e) => setSelectedCampaign(e.target.value)}
                disabled={!selectedBank || loadingCampaigns}
              >
                <option value="">
                  {loadingCampaigns ? "Loading campaigns..." : "Select a campaign..."}
                </option>
                {campaigns.map((c) => (
                  <option key={c.campaign_id} value={c.campaign_id}>{c.campaign_name}</option>
                ))}
              </select>
            </div>

            <div className="field field-small">
              <label>From</label>
              <input type="date" value={fromDate} max={toDate} onChange={(e) => setFromDate(e.target.value)} />
            </div>

            <div className="field field-small">
              <label>To</label>
              <input
                type="date"
                value={toDate}
                min={fromDate}
                max={defaultToDate()}
                onChange={(e) => setToDate(e.target.value)}
              />
            </div>

            <button
              className="btn-primary"
              onClick={loadCategories}
              disabled={!selectedCampaign || loadingSummary || isRunning}
            >
              {loadingSummary ? "Loading…" : "Load Categories"}
            </button>
          </div>
        </div>

        {error && <div className="panel error-panel">{error}</div>}

        {summary && (
          <div className="panel">
            <div className="panel-heading">
              <h2>Categories</h2>
              <span className="panel-heading-sub">
                <span className="mono">{summary.usable_conversations}</span> of{" "}
                <span className="mono">{summary.total_conversations}</span> usable
                &nbsp;·&nbsp; click a category to analyze it
              </span>
            </div>

            {sortedCategories.length === 0 ? (
              <p className="empty-state">No categorized conversations found in this date range.</p>
            ) : (
              <div className="category-grid">
                {sortedCategories.map(([category, count]) => {
                  const sentiment = sentimentOf(category);
                  const pct = Math.max(4, Math.round((count / maxCount) * 100));
                  return (
                    <button
                      key={category}
                      className={`category-card cat-${sentiment}`}
                      onClick={() => handleCategoryClick(category, count)}
                      disabled={isRunning}
                    >
                      <div className="category-card-top">
                        <span className="category-card-name">{category}</span>
                        <span className="category-card-count mono">{count}</span>
                      </div>
                      <div className="category-bar-track">
                        <div className="category-bar-fill" style={{ width: `${pct}%` }} />
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {(isRunning || progressLog.length > 0) && (
          <div className="panel status-panel">
            <div className="status-line">
              {isRunning && <span className="spinner" />}
              <span className={isRunning ? "status-text active" : "status-text"}>
                {isRunning ? currentStatus : "Finished"}
              </span>
            </div>
            {progressLog.length > 0 && (
              <button className="log-toggle" onClick={() => setShowLog((v) => !v)}>
                {showLog ? "Hide log" : "Show full log"}
              </button>
            )}
            {showLog && (
              <div className="progress-log mono">
                {progressLog.map((msg, i) => (
                  <div key={i}>{msg}</div>
                ))}
              </div>
            )}
          </div>
        )}

        {directResult && (
          <div className="results">
            <div className="panel-heading">
              <h2>Results</h2>
              <span className="panel-heading-sub">
                <span className="mono">{directResult.usable_conversations}</span> of{" "}
                <span className="mono">{directResult.total_conversations}</span> usable
              </span>
            </div>

            {Object.keys(directResult.categories).length === 0 && (
              <div className="panel">
                <p className="empty-state">No conversations found for this selection.</p>
              </div>
            )}

            {Object.entries(directResult.categories).map(([category, data]) => {
              const sentiment = sentimentOf(category);
              return (
                <div key={category} className="panel">
                  <div className="panel-heading">
                    <h3 className={`cat-label cat-${sentiment}`}>{category}</h3>
                    <span className="panel-heading-sub mono">{data.total}</span>
                  </div>
                  <div className="cluster-grid">
                    {data.clusters.map((cluster, i) => (
                      <div
                        key={i}
                        className="cluster-card clickable"
                        onClick={() => openCluster(cluster)}
                      >
                        <div className="cluster-header">
                          <strong>{cluster.name}</strong>
                          <span className="cluster-count mono">{cluster.count}</span>
                        </div>
                        <p>{cluster.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {modal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-tag">CONFIRM</div>

            {modal.step === "confirm-all" && (
              <>
                <h3 className="modal-title">Run analysis?</h3>
                <p className="modal-body">
                  Send all <strong className="mono">{modal.count}</strong> conversation(s) in{" "}
                  <strong>"{modal.category}"</strong> to the LLM?
                </p>
                <div className="modal-actions">
                  <button className="modal-btn modal-btn-ghost" onClick={handleModalWantsLimit}>
                    Use a smaller batch
                  </button>
                  <div className="modal-actions-right">
                    <button className="modal-btn modal-btn-secondary" onClick={closeModal}>Cancel</button>
                    <button className="modal-btn modal-btn-primary" onClick={handleModalConfirmAll}>
                      Run on all {modal.count}
                    </button>
                  </div>
                </div>
              </>
            )}

            {modal.step === "ask-limit" && (
              <>
                <h3 className="modal-title">How many conversations?</h3>
                <p className="modal-body">
                  Out of <strong className="mono">{modal.count}</strong> in <strong>"{modal.category}"</strong>:
                </p>
                <input
                  type="number"
                  className="modal-input mono"
                  value={limitInput}
                  min="1"
                  max={modal.count}
                  autoFocus
                  onChange={(e) => setLimitInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleModalLimitSubmit()}
                />
                <div className="modal-actions">
                  <div className="modal-actions-right" style={{ marginLeft: "auto" }}>
                    <button className="modal-btn modal-btn-secondary" onClick={closeModal}>Cancel</button>
                    <button className="modal-btn modal-btn-primary" onClick={handleModalLimitSubmit}>Continue</button>
                  </div>
                </div>
              </>
            )}

            {modal.step === "confirm-limit" && (
              <>
                <h3 className="modal-title">Confirm batch size</h3>
                <p className="modal-body">
                  Run on the first <strong className="mono">{modal.limit}</strong> of{" "}
                  <strong className="mono">{modal.count}</strong> conversation(s) in{" "}
                  <strong>"{modal.category}"</strong>?
                </p>
                <div className="modal-actions">
                  <div className="modal-actions-right" style={{ marginLeft: "auto" }}>
                    <button className="modal-btn modal-btn-secondary" onClick={closeModal}>Cancel</button>
                    <button className="modal-btn modal-btn-primary" onClick={handleModalConfirmLimit}>Run</button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {selectedCluster && (
        <div className="modal-overlay" onClick={() => setSelectedCluster(null)}>
          <div className="cluster-details-modal" onClick={(e) => e.stopPropagation()}>
            <h2>{selectedCluster.name}</h2>
            <p><strong>Total conversations:</strong> {selectedCluster.count}</p>
            {selectedCluster.description && <p>{selectedCluster.description}</p>}

            {selectedCluster.children && selectedCluster.children.length > 0 ? (
              <>
                <h3>Breakdown</h3>
                <div className="tree-children root-tree-children">
                  {selectedCluster.children.map((child, i) => (
                    <TreeNode
                      key={i}
                      node={child}
                      path={[i]}
                      openPaths={openPaths}
                      onToggle={toggleOpenPath}
                    />
                  ))}
                </div>
              </>
            ) : (
              <>
                <h3>Sample Conversations</h3>
                {(selectedCluster.sample_conversations || []).map((ex, index) => (
                  <details key={index} className="conversation-card">
                    <summary>Conversation ID: {ex.conversation_id}</summary>
                    <pre>{ex.preview}</pre>
                  </details>
                ))}
              </>
            )}

            <button
              className="modal-btn modal-btn-primary close-btn"
              onClick={() => setSelectedCluster(null)}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

