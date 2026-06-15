(() => {
  const hotBody = document.querySelector("#hotTable tbody");
  const earningsBody = document.querySelector("#earningsTable tbody");
  const earningsCount = document.getElementById("earningsCount");
  const newsList = document.getElementById("newsList");
  const statsBar = document.getElementById("statsBar");
  const connStatus = document.getElementById("connStatus");
  const detailEl = document.getElementById("detail");
  const detailTitle = document.getElementById("detailTitle");
  const hotCount = document.getElementById("hotCount");
  const symbolSearch = document.getElementById("symbolSearch");
  const sortBy = document.getElementById("sortBy");
  const factorModal = document.getElementById("factorModal");
  const factorModalTitle = document.getElementById("factorModalTitle");
  const factorModalSub = document.getElementById("factorModalSub");
  const factorModalBody = document.getElementById("factorModalBody");
  const factorCountLabel = document.getElementById("factorCountLabel");
  const livePill = document.getElementById("livePill");
  const hotHint = document.getElementById("hotHint");
  const cycleStrip = document.getElementById("cycleStrip");
  const sectorList = document.getElementById("sectorList");
  const sectorDetail = document.getElementById("sectorDetail");
  const sectorSummaryHint = document.getElementById("sectorSummaryHint");
  const sectorFilterBadge = document.getElementById("sectorFilterBadge");

  const alertBell = document.getElementById("alertBell");
  const alertCountEl = document.getElementById("alertCount");

  let marketFilter = "all";
  let sectorMarketFilter = "all";
  let selectedSector = null;
  let lastSectorFingerprint = "";
  let selectedSymbol = null;
  let lastData = null;
  let activeTab = "hot";
  let factorCatalogTotal = 76;
  let factorFilter = "all";
  let modalSymbol = null;
  let earlyOnly = false;
  let whaleOnly = false;
  let sectorFilter = null;
  let lastScanGeneration = 0;
  let lastHotFingerprint = "";
  let wsConnected = false;
  const symbolCache = new Map();
  const modalFullCache = new Map();
  const prevRankBySymbol = new Map();
  const DISPLAY_LIMIT = 200;

  let lastRegime = null; // populated by light regime stub (VIX + trend) for pills + edge notes

  // New features state
  let watchlist = []; // [{symbol, addedAt, lastScore, lastBuy, addedScore}]
  let recentAlerts = []; // [{type, symbol, msg, ts, score}]
  let seenSmartMoney = new Set();
  let alertsEnabled = true;

  // Portfolio / Paper Journal (server persisted)
  let portfolioData = null; // {positions, stats, count}
  let journalData = [];

  const UI_HELP = {
    hot: "Top stocks that pass the current buy-score threshold. Ranked by next-entry quality, not just raw momentum.",
    watch: "Server-persisted My List (shared across devices/restarts). Rules for personalized alerts (score>65 + rvol>2, exact S+ investor etc) evaluated live. Use ★ Watch + Alert buttons.",
    radar: "Named high-signal investors, politicians, FIIs, promoters, and insider-style events detected from filings/news.",
    sectors: "Sector rotation view. Shows where early buy setups are clustering across US and India.",
    earnings: "Companies with upcoming results or strong earnings/news buzz in the next window.",
    news: "Latest RSS/Google News headlines matched to tracked symbols.",
    guide: "Short reference for the scanner workflow.",
    portfolio: "Paper positions + journal. Server-stored (survives refresh). Log buys using live engine data; close records realized PnL + thesis snapshot (positives vs negatives).",
    highconv: "Count of hot-list names with buy score at or above 70. Click to focus on cleaner early setups.",
    whale: "Count of hot-list names with S+ smart-money style signals. Click to toggle whale/politician filtering.",
    reset: "Resets filters and returns the hot list to the default all-market view.",
    tracked: "Number of symbols already processed in the current scan cycle. This grows while scanning batches.",
    news_hits: "Number of recent headlines in the live news panel.",
    full_scan: "Time of the last completed full factor scan.",
    price_tick: "Time of the latest quick price-only refresh for hot names.",
  };

  const CONTROL_HELP = {
    alertBell: "Recent high-score, S+ smart-money, and pre-earnings alerts.",
    symbolSearch: "Filter the current hot list, or type any ticker and press Enter to run full analysis.",
    analyzeBtn: "Run the full factor engine on the ticker in the search box.",
    discoverBtn: "Scan broader US and India symbol pools for additional high-conviction names.",
    fullScanBtn: "Start the slow exhaustive scan across the widest reachable market universe.",
    loadFullScanBtn: "Load saved results from the most recent exhaustive scan.",
    sortBy: "Change the hot-list ranking without changing the underlying scan data.",
    exportHotBtn: "Download the currently visible hot-list data as CSV.",
    exportWatchBtn: "Download My List as CSV.",
    clearWatchBtn: "Remove every symbol from My List on this device.",
    manageAlertRulesBtn: "Open alert rules manager (server-persisted conditions for score/investor/earnings). Matches push rich alerts immediately.",
    refreshServerWatchBtn: "Force sync watchlist + recent alerts from server (for multi-device).",
  };

  let helpPopover = null;

  function showHelpPopover(anchor, text) {
    if (!anchor || !text) return;
    hideHelpPopover();
    const rect = anchor.getBoundingClientRect();
    helpPopover = document.createElement("div");
    helpPopover.className = "help-popover";
    helpPopover.textContent = text;
    document.body.appendChild(helpPopover);
    const pop = helpPopover.getBoundingClientRect();
    const left = Math.min(window.innerWidth - pop.width - 12, Math.max(12, rect.left));
    const below = rect.bottom + 8;
    const above = rect.top - pop.height - 8;
    const top =
      below + pop.height + 12 <= window.innerHeight
        ? below
        : Math.max(12, above);
    helpPopover.style.left = `${left}px`;
    helpPopover.style.top = `${top}px`;
  }

  function hideHelpPopover() {
    if (helpPopover) {
      helpPopover.remove();
      helpPopover = null;
    }
  }

  function bindHelp(root = document) {
    root.querySelectorAll("[data-help]").forEach((el) => {
      if (el.dataset.helpBound === "1") return;
      el.dataset.helpBound = "1";
      el.addEventListener("mouseenter", () => showHelpPopover(el, el.dataset.help));
      el.addEventListener("focus", () => showHelpPopover(el, el.dataset.help));
      el.addEventListener("mouseleave", hideHelpPopover);
      el.addEventListener("blur", hideHelpPopover);
      el.addEventListener("pointerdown", () => {
        showHelpPopover(el, el.dataset.help);
        window.setTimeout(hideHelpPopover, 1800);
      });
    });
  }

  function syncStickyOffsets() {
    const topbar = document.querySelector(".topbar");
    if (!topbar) return;
    document.documentElement.style.setProperty(
      "--topbar-height",
      `${Math.ceil(topbar.getBoundingClientRect().height)}px`
    );
  }

  function applyStaticHelp() {
    Object.entries(CONTROL_HELP).forEach(([id, text]) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.dataset.help = text;
      el.title = text;
    });
    document.querySelectorAll(".chip[data-market]").forEach((btn) => {
      const market = btn.dataset.market;
      btn.dataset.help =
        market === "all"
          ? "Show US and India names together."
          : `Show ${market.toUpperCase()} names only.`;
    });
    document.getElementById("earlyOnlyChip")?.setAttribute(
      "data-help",
      "Keep only non-extended setups with cleaner entry conditions."
    );
    document.getElementById("whaleOnlyChip")?.setAttribute(
      "data-help",
      "Toggle S+ smart-money, politician, FII, or named investor signals."
    );
    document.querySelectorAll("[data-sector-market]").forEach((btn) => {
      const market = btn.dataset.sectorMarket;
      btn.dataset.help =
        market === "all"
          ? "Show sector breadth across both markets."
          : `Show sector breadth for ${market.toUpperCase()} names only.`;
    });
    bindHelp(document);
  }

  // Load persisted watchlist (local fallback + server sync for multi-device/restart)
  let serverWatchesLoaded = false;
  try {
    const saved = localStorage.getItem("marketpulse_watchlist");
    if (saved) watchlist = JSON.parse(saved);
  } catch (e) {}

  async function loadServerWatches() {
    try {
      const res = await fetch("/api/watchlist");
      if (res.ok) {
        const j = await res.json();
        const srv = (j.watches || []).map(w => ({ symbol: w.symbol, addedAt: w.added_at, notes: w.notes, server: true }));
        // Once the server responds, make it authoritative so deleted server items do not linger locally.
        watchlist = srv;
        serverWatchesLoaded = true;
      }
    } catch (e) {
      // offline: use local
    }
    try { localStorage.setItem("marketpulse_watchlist", JSON.stringify(watchlist)); } catch(e){}
  }

  async function addToServerWatch(symbol, notes="") {
    try {
      const res = await fetch("/api/watchlist", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({symbol, notes})});
      if (res.ok) {
        await loadServerWatches();
        return true;
      }
    } catch(e){}
    return false;
  }

  async function removeFromServerWatch(symbol) {
    try {
      await fetch(`/api/watchlist/${encodeURIComponent(symbol)}`, {method:"DELETE"});
      await loadServerWatches();
      return true;
    } catch(e){}
    return false;
  }

  async function loadServerAlertRules() {
    try {
      const res = await fetch("/api/alert_rules");
      if (res.ok) return (await res.json()).rules || [];
    } catch(e){}
    return [];
  }

  async function createServerAlertRule(rule_type, condition, enabled=true) {
    try {
      const res = await fetch("/api/alert_rules", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({rule_type, condition, enabled})});
      if (res.ok) return await res.json();
    } catch(e){}
    return null;
  }

  async function deleteServerAlertRule(id) {
    try { await fetch(`/api/alert_rules/${id}`, {method:"DELETE"}); } catch(e){}
  }

  async function fetchRecentServerAlerts() {
    try {
      const res = await fetch("/api/alerts/recent?limit=40");
      if (res.ok) return (await res.json()).alerts || [];
    } catch(e){}
    return [];
  }

  const CATEGORY_SORT = [
    "entry",
    "catalyst",
    "news",
    "fundamental",
    "valuation",
    "calendar",
    "technical",
    "volume",
    "momentum",
    "ownership",
    "health",
    "income",
    "sector",
    "risk",
  ];

  function mergeScanRow(symbol, incoming) {
    if (!incoming) return symbolCache.get(symbol);
    const prev = symbolCache.get(symbol);
    if (!prev) {
      symbolCache.set(symbol, incoming);
      return incoming;
    }
    const merged = { ...prev, ...incoming };
    merged.metrics = { ...(prev.metrics || {}), ...(incoming.metrics || {}) };
    if (!incoming.factor_breakdown?.length && prev.factor_breakdown?.length) {
      merged.factor_breakdown = prev.factor_breakdown;
    }
    if (!incoming.top_factors?.length && prev.top_factors?.length) {
      merged.top_factors = prev.top_factors;
    }
    symbolCache.set(symbol, merged);
    return merged;
  }

  function ingestHotRows(data) {
    const pools = [
      ...(data?.hot || []),
      ...(data?.hot_by_market?.us || []),
      ...(data?.hot_by_market?.india || []),
    ];
    for (const r of pools) {
      if (r?.symbol) mergeScanRow(r.symbol, r);
    }
  }

  function getHotPool(data) {
    if (!data) return [];
    const market = marketFilter;
    if (market === "us" && data.hot_by_market?.us?.length) {
      return data.hot_by_market.us;
    }
    if (market === "india" && data.hot_by_market?.india?.length) {
      return data.hot_by_market.india;
    }
    // Fallback / improved per-market view:
    // When the strict global "hot" list has few or no names for the chosen market
    // (very common early in a scan batch or when global hot is small / US-heavy),
    // collect the best available scored symbols for that market from:
    // - the main hot list
    // - symbolCache (previous ad-hoc analyzes / full scan injections)
    // This makes the India (or US) tab useful instead of showing 0 even when
    // India names have been scored (often at 30-50 range, below the global hot bar).
    let pool = (data.hot || []).slice();
    // pull from symbolCache too (these come from Analyze, Discover, Full Scan results, etc.)
    if (symbolCache && symbolCache.size) {
      for (const [sym, row] of symbolCache) {
        if (row) pool.push(row);
      }
    }
    if (market !== "all") {
      pool = pool.filter((r) => {
        if (!r) return false;
        const m = (r.market || "").toLowerCase();
        if (m === market) return true;
        // fallback heuristic for India (in case market field not set on some cached rows)
        const sym = r.symbol || "";
        if (market === "india" && sym.match(/\.(NS|BO)$/i)) return true;
        return false;
      });
    }
    // dedup + sort by score (best first)
    const seen = new Set();
    pool = pool.filter(r => {
      const s = r.symbol;
      if (!s || seen.has(s)) return false;
      seen.add(s);
      return true;
    }).sort((a, b) => rankScore(b) - rankScore(a));
    return pool;
  }

  function findRow(symbol, data) {
    if (!symbol) return null;
    if (modalSymbol === symbol && modalFullCache.has(symbol)) {
      return modalFullCache.get(symbol);
    }
    const fromHot =
      getHotPool(data).find((x) => x.symbol === symbol) ||
      (data?.hot || []).find((x) => x.symbol === symbol);
    if (fromHot) return mergeScanRow(symbol, fromHot);
    return (
      symbolCache.get(symbol) ||
      (data?.earnings || []).find((x) => x.symbol === symbol)
    );
  }

  function factorsDisplay(row) {
    const hit = row.factors_hit ?? row.metrics?.factors_hit ?? 0;
    const total = row.factors_total ?? row.metrics?.factors_total ?? factorCatalogTotal;
    return { hit, total };
  }

  function smartMoneyBadges(row) {
    const sm = row.metrics?.smart_money;
    if (!sm?.hits?.length && !row.alerts?.some((a) => /LEGEND|WHALE|POLITICIAN|FOREIGN BUY/i.test(a))) {
      return "";
    }
    const hits = sm?.hits || [];
    const primary = sm?.primary_alert || row.alerts?.find((a) => /LEGEND|WHALE|POLITICIAN|FOREIGN/i.test(a));
    if (primary) {
      const short = primary.length > 42 ? `${primary.slice(0, 40)}…` : primary;
      return `<span class="whale-badge" title="${escapeHtml(primary)}">${escapeHtml(short)}</span>`;
    }
    const name = hits[0]?.name || "Smart money";
    const kind = hits[0]?.kind || "";
    const cls =
      kind === "india_legend"
        ? "india"
        : kind === "us_legend"
          ? "us"
          : kind.includes("politician")
            ? "pol"
            : "foreign";
    return `<span class="whale-badge whale-${cls}" title="${escapeHtml(name)}">${escapeHtml(name)}</span>`;
  }

  function factorPill(row) {
    const { hit, total } = factorsDisplay(row);
    return `<button type="button" class="factor-pill" data-symbol="${attrEsc(row.symbol)}" title="View all factors">${hit}/${total}</button>`;
  }

  function rankScore(row) {
    const m = row?.metrics || {};
    return Number(row?.buy_score ?? m.buy_score ?? row?.score ?? 0) || 0;
  }

  // Prominent confidence pills (wired in hot rows + detail). Color + always visible when present.
  // Reuses the confidence_score populated by price_crawler (regular + full scans) + now promoted via /api/edge snapshots.
  function confPill(c) {
    if (c == null) return "";
    const cls = c >= 80 ? "conf-high" : (c >= 60 ? "conf-med" : "conf-low");
    const label = `Data confidence ${c} (crawler: info completeness, hist length, volume, news/earnings coverage, market)`;
    return `<span class="conf-pill ${cls}" title="${attrEsc(label)}">${c}</span>`;
  }

  /* --- Tab navigation --- */
  document.querySelectorAll(".tab").forEach((btn) => {
    const tab = btn.dataset.tab;
    if (UI_HELP[tab]) {
      btn.dataset.help = UI_HELP[tab];
      btn.title = UI_HELP[tab];
    }
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".tab-panel").forEach((p) => {
        p.hidden = true;
        p.classList.remove("active");
      });
      const panel = document.getElementById(`panel-${tab}`);
      if (panel) {
        panel.hidden = false;
        panel.classList.add("active");
      }
      activeTab = tab;
      const titles = {hot:"Command Center", watch:"Watchlist", portfolio:"Portfolio", radar:"S+ Radar", sectors:"Sector Map", earnings:"Earnings", news:"Live News", guide:"Edge & Guide"};
      const vt = document.getElementById("viewTitle");
      if (vt && titles[tab]) vt.textContent = titles[tab];
      if (tab === "sectors") renderSectors(lastData);
      if (tab === "radar") renderRadar(lastData);
    });
  });
  applyStaticHelp();

  document.querySelectorAll("[data-sector-market]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document
        .querySelectorAll("[data-sector-market]")
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      sectorMarketFilter = btn.dataset.sectorMarket || "all";
      renderSectors(lastData);
    });
  });

  document.querySelectorAll(".chip[data-market]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".chip[data-market]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      marketFilter = btn.dataset.market;
      // Reset extra filters when explicitly choosing a market (All/US/India) so user sees the actual hot list for that market.
      // Otherwise "India + Early only" or "India + Whale only" could easily result in empty results even when India names exist.
      earlyOnly = false;
      whaleOnly = false;
      const eChip = document.getElementById("earlyOnlyChip");
      if (eChip) { eChip.classList.remove("active"); eChip.dataset.early = "0"; }
      const wChip = document.getElementById("whaleOnlyChip");
      if (wChip) { wChip.classList.remove("active"); wChip.dataset.whale = "0"; }
      renderHot(lastData);
    });
  });

  document.getElementById("earlyOnlyChip")?.addEventListener("click", (btn) => {
    btn = btn.currentTarget;
    earlyOnly = !earlyOnly;
    btn.classList.toggle("active", earlyOnly);
    btn.dataset.early = earlyOnly ? "1" : "0";
    renderHot(lastData);
  });

  document.getElementById("whaleOnlyChip")?.addEventListener("click", (btn) => {
    btn = btn.currentTarget;
    whaleOnly = !whaleOnly;
    btn.classList.toggle("active", whaleOnly);
    btn.dataset.whale = whaleOnly ? "1" : "0";
    renderHot(lastData);
  });

  // New buttons & bell
  document.getElementById("exportHotBtn")?.addEventListener("click", () => {
    const pool = getHotPool(lastData || {});
    exportCSV(pool, "market_pulse_hot.csv");
  });
  document.getElementById("exportWatchBtn")?.addEventListener("click", () => {
    const rows = watchlist.map(w => ({symbol: w.symbol, buy_score: w.lastBuy, quality_score: w.lastQuality}));
    exportCSV(rows, "market_pulse_watchlist.csv");
  });
  document.getElementById("clearWatchBtn")?.addEventListener("click", async () => {
    if (confirm("Clear your entire My List?")) {
      const old = [...watchlist];
      watchlist = [];
      saveWatch();
      await Promise.allSettled(old.map(w => removeFromServerWatch(w.symbol)));
      renderWatch(lastData);
    }
  });
  document.getElementById("manageAlertRulesBtn")?.addEventListener("click", async () => {
    const sec = document.getElementById("alertRulesSection");
    if (sec) sec.style.display = "block";
    await refreshAlertRulesUI();
  });
  document.getElementById("refreshServerWatchBtn")?.addEventListener("click", async () => {
    await loadServerWatches();
    await fetchRecentServerAlerts();
    renderWatch(lastData);
    renderAlertBell();
  });
  document.getElementById("refreshPortfolioBtn")?.addEventListener("click", () => renderPortfolio(true));
  document.getElementById("exportJournalBtn")?.addEventListener("click", () => {
    if (!journalData.length) { alert("No journal entries to export yet."); return; }
    exportCSV(journalData, "market_pulse_journal.csv");
  });
  document.getElementById("logPaperBuyBtn")?.addEventListener("click", async () => {
    const sym = (document.getElementById("portSymbol")?.value || selectedSymbol || "").trim().toUpperCase();
    if (!sym) { alert("Enter a symbol first, e.g. NVDA or RELIANCE.NS."); return; }
    const qty = parseFloat(document.getElementById("portQty")?.value || "100") || 100;
    const sl = parseFloat(document.getElementById("portSL")?.value || "") || null;
    const target = parseFloat(document.getElementById("portTarget")?.value || "") || null;
    const notes = (document.getElementById("portNotes")?.value || "").trim();
    try {
      await addToPortfolio(sym, {qty, sl, target, notes});
      await renderPortfolio(true);
    } catch (err) {
      alert("Paper buy failed: " + (err.message || err));
    }
  });
  alertBell?.addEventListener("click", () => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission().then(p => { if (p === "granted") alertsEnabled = true; });
    }
    showAlertsPanel();
  });

  // Inline rules UI bindings (in watch panel)
  const addRuleBtn = document.getElementById("addRuleBtn");
  addRuleBtn?.addEventListener("click", async () => {
    const rtype = document.getElementById("ruleTypeSel")?.value || "score";
    const minScore = parseFloat(document.getElementById("ruleMinScore")?.value || "0") || null;
    const minRvol = parseFloat(document.getElementById("ruleMinRvol")?.value || "0") || null;
    const hasInv = !!document.getElementById("ruleHasInvestor")?.checked;
    const cond = {};
    if (minScore) cond.min_buy_score = minScore;
    if (minRvol) cond.min_rvol = minRvol;
    if (hasInv) cond.has_investor = true;
    if (rtype === "earnings") cond.earnings_within_days = 3;
    const created = await createServerAlertRule(rtype, cond);
    if (created) {
      await refreshAlertRulesUI();
      pushAlert("rule", "SYSTEM", `Alert rule #${created.id} (${rtype}) added on server`, null);
    }
  });
  document.getElementById("hideRulesBtn")?.addEventListener("click", () => {
    const sec = document.getElementById("alertRulesSection"); if (sec) sec.style.display = "none";
  });

  function hasSmartMoneySignal(row) {
    if (row.metrics?.has_smart_money || row.metrics?.smart_money?.hits?.length) return true;
    return (row.alerts || []).some((a) => /LEGEND|WHALE|POLITICIAN|FOREIGN BUY|SMART MONEY/i.test(a));
  }

  symbolSearch?.addEventListener("input", () => renderHot(lastData));
  sortBy?.addEventListener("change", () => renderHot(lastData));

  // Powerful "analyze any stock" via the search box + dedicated button.
  // Uses the upgraded /api/symbol (and /api/analyze) which runs the *exact same*
  // full factor registry, scoring, smart money, news catalysts, etc. as the live scanner.
  async function runAnalyzeFromSearch() {
    const q = (symbolSearch?.value || "").trim().toUpperCase();
    if (!q) return;

    // Immediate visible feedback so the "analyze" feels responsive
    // (on-demand fetch can take several seconds)
    detailTitle.textContent = q;
    detailEl.innerHTML = `<div class="detail-empty"><p>Deep-analyzing ${escapeHtml(q)} with the full 140-factor engine…</p><p class="muted">yfinance history + info (fundamentals, targets, margins, etc) + live news titles + smart money registry + sector valuation + technical indicators + weighted buy/quality scoring. Positives, risks, and conviction verdict will appear below + full factors modal will open.</p></div>`;

    if (activeTab !== "hot") {
      document.querySelector('.tab[data-tab="hot"]')?.click();
    }
    document.querySelector(".sticky-detail")?.scrollIntoView({ behavior: "smooth", block: "nearest" });

    try {
      const full = await fetchFullSymbol(q);
      if (lastData) {
        lastData.symbols = lastData.symbols || {};
        lastData.symbols[full.symbol] = full;
      }
      renderDetail(full);
      if (lastData) renderHot(lastData);
      if (symbolSearch) symbolSearch.value = "";
      // Open the full factor checklist (the "analysis box") automatically for the analyzed ticker
      openFactorModal(q, lastData || {});
    } catch (e) {
      detailEl.innerHTML = `<div class="detail-empty"><p>Could not analyze ${escapeHtml(q)}</p><p class="muted">${escapeHtml(e.message || e)}</p></div>`;
    }
  }

  symbolSearch?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      runAnalyzeFromSearch();
    }
  });

  const analyzeBtn = document.getElementById("analyzeBtn");
  analyzeBtn?.addEventListener("click", () => {
    const q = (symbolSearch?.value || "").trim();
    if (q) {
      runAnalyzeFromSearch();
    } else {
      // Prompt if empty
      const t = prompt("Enter any ticker to analyze with the full engine (e.g. NVDA, RELIANCE, AAPL, SBIN):");
      if (t) {
        if (symbolSearch) symbolSearch.value = t;
        runAnalyzeFromSearch();
      }
    }
  });

  // New "Scan More / Full Discovery" - scrapes multiple sites + large pools, runs deep engine on extra listed names
  const discoverBtn = document.getElementById("discoverBtn");
  discoverBtn?.addEventListener("click", async () => {
    if (!discoverBtn) return;
    const origText = discoverBtn.textContent;
    discoverBtn.textContent = "Scanning many sites + pools…";
    discoverBtn.disabled = true;
    try {
      const res = await fetch("/api/discover?limit=60&min_score=32&extra=200");
      const data = await res.json();
      if (data && data.discovered && data.discovered.length) {
        // Merge into current hot pool so they appear in the table (marked as discovered)
        if (!lastData) lastData = {};
        lastData.hot = lastData.hot || [];
        const existing = new Set(lastData.hot.map(r => r.symbol));
        let added = 0;
        for (const d of data.discovered) {
          if (!existing.has(d.symbol)) {
            lastData.hot.push(d);
            added++;
          }
        }
        // Re-ingest and re-render
        ingestHotRows(lastData);
        renderHot(lastData);
        const hint = document.getElementById("hotHint");
        if (hint) hint.textContent = `Discovery added ${added} new names from multi-source larger pool (wiki scrapes + big lists + extras). Click rows/factors as usual.`;
        // Scroll to table
        document.querySelector(".table-wrap")?.scrollIntoView({behavior: "smooth", block: "start"});
      } else {
        alert("No new high-conviction discoveries right now (or rate limited). Try Analyze on specific names or wait a bit.");
      }
    } catch (e) {
      alert("Discovery scan failed: " + (e.message || e));
    } finally {
      discoverBtn.textContent = origText;
      discoverBtn.disabled = false;
    }
  });

  // Full Exhaustive Scan: Scans ALL India + US stocks with max data for full accuracy. Time no object.
  const fullScanBtn = document.getElementById("fullScanBtn");
  fullScanBtn?.addEventListener("click", async () => {
    if (!fullScanBtn) return;
    if (!confirm("Start FULL EXHAUSTIVE SCAN over the complete multi-source universe (all reachable US + India listed stocks)? This will take a VERY long time (hours) for maximum coverage and accuracy. It will find opportunities literally everywhere. Continue?")) return;
    const orig = fullScanBtn.textContent;
    fullScanBtn.textContent = "Scanning EVERYTHING (slow & thorough for full accuracy)…";
    fullScanBtn.disabled = true;
    try {
      const res = await fetch("/api/full_exhaustive_scan", {method: "POST"});
      const data = await res.json();
      if (data && data.top_opportunities) {
        alert(`Full exhaustive scan complete!\nScanned ${data.scanned} symbols.\nFound ${data.opportunities_found} opportunities.\nTop ones loaded into view. Use "Load Last Full Scan Results" to see them again.`);
        // Inject top into hot for immediate view (tagged)
        if (!lastData) lastData = {};
        lastData.hot = lastData.hot || [];
        const existing = new Set(lastData.hot.map(r => r.symbol));
        for (const r of data.top_opportunities) {
          if (!existing.has(r.symbol)) {
            r.full_exhaustive = true;
            lastData.hot.unshift(r);  // put at top
          }
        }
        ingestHotRows(lastData);
        renderHot(lastData);
        const hint = document.getElementById("hotHint");
        if (hint) hint.textContent = `Full Exhaustive Scan results injected (top opportunities from scanning EVERY stock). Tagged items are from the complete no-stone-unturned pass.`;
      } else {
        alert("Full scan started in background (will take hours). Use 'Load Last Full Scan Results' button later to view top opportunities from the complete universe.");
      }
    } catch (e) {
      alert("Full exhaustive scan trigger failed: " + (e.message || e) + " (may still be running in background - check logs or reload later)");
    } finally {
      fullScanBtn.textContent = orig;
      fullScanBtn.disabled = false;
    }
  });

  const loadFullScanBtn = document.getElementById("loadFullScanBtn");
  loadFullScanBtn?.addEventListener("click", async () => {
    if (!loadFullScanBtn) return;
    const orig = loadFullScanBtn.textContent;
    loadFullScanBtn.textContent = "Loading last full scan...";
    try {
      const res = await fetch("/api/last_full_scan");
      const data = await res.json();
      if (data.status === "none") {
        alert(data.message || "No full scan yet. Click the Exhaustive Scan button first.");
      } else if (data.results && data.results.length) {
        if (!lastData) lastData = {};
        lastData.hot = lastData.hot || [];
        const existing = new Set(lastData.hot.map(r => r.symbol));
        let added = 0;
        for (const r of data.results) {
          if (!existing.has(r.symbol)) {
            r.full_exhaustive = true;
            lastData.hot.unshift(r);
            added++;
          }
        }
        ingestHotRows(lastData);
        renderHot(lastData);
        alert(`Loaded ${added} opportunities from last full exhaustive scan (scanned ${data.symbols_attempted}, ${data.high_quality_opportunities} high quality). These are ranked by the engine across the entire market.`);
        const hint = document.getElementById("hotHint");
        if (hint) hint.textContent = `Last Full Exhaustive Scan results (${data.timestamp}). Full accuracy mode - every stock evaluated.`;
      } else {
        alert("Last full scan data incomplete. Run a new full exhaustive scan.");
      }
    } catch (e) {
      alert("Failed to load last full scan: " + (e.message || e));
    } finally {
      loadFullScanBtn.textContent = orig;
    }
  });

  /* --- Factor modal --- */
  document.querySelectorAll("[data-close='factorModal']").forEach((el) => {
    el.addEventListener("click", () => closeFactorModal());
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && factorModal && !factorModal.hidden) closeFactorModal();
    if (e.key === "/" && document.activeElement && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
      e.preventDefault();
      symbolSearch && symbolSearch.focus();
    }
    if ((e.key.toLowerCase() === "w") && selectedSymbol) {
      const row = findRow(selectedSymbol, lastData);
      if (watchlist.some(ww => ww.symbol === selectedSymbol)) removeFromWatch(selectedSymbol); else addToWatch(selectedSymbol, row);
      renderWatch(lastData);
    }
    if ((e.key.toLowerCase() === "a") && selectedSymbol) {
      const row = findRow(selectedSymbol, lastData);
      addToWatchWithAlert(selectedSymbol, row);
      renderWatch(lastData);
    }
    if (e.key.toLowerCase() === "f" && selectedSymbol) {
      openFactorModal(selectedSymbol, lastData);
    }
    if (e.key.toLowerCase() === "e") {
      const pool = getHotPool(lastData || {});
      if (pool.length) exportCSV(pool, "market_pulse_hot.csv");
    }
  });

  document.querySelectorAll("[data-factor-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-factor-filter]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      factorFilter = btn.dataset.factorFilter;
      renderFactorModalBody(modalFullCache.get(modalSymbol));
    });
  });

  async function openFactorModal(symbol, data) {
    modalSymbol = symbol;
    factorFilter = "all";
    document.querySelectorAll("[data-factor-filter]").forEach((b) => {
      b.classList.toggle("active", b.dataset.factorFilter === "all");
    });
    let row = findRow(symbol, data);
    if (!row) return;
    selectedSymbol = symbol;
    factorModalTitle.textContent = `${symbol} · Factor checklist`;
    factorModal.hidden = false;
    factorModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    factorModalBody.innerHTML = '<p class="muted">Loading weighted checklist…</p>';
    try {
      row = await fetchFullSymbol(symbol);
    } catch (e) {
      if (!(row?.factor_breakdown?.length)) {
        factorModalBody.innerHTML = `<p class="modal-err">Could not load factors for ${escapeHtml(symbol)}: ${escapeHtml(e.message)}</p>`;
        factorModalSub.textContent = "Load failed";
        return;
      }
    }
    const { hit, total } = factorsDisplay(row);
    const m = row.metrics || {};
    const catalog = m.factors_catalog_total || factorCatalogTotal;
    factorModalSub.textContent = `${hit} passed · ${total} applicable (${catalog} total) · buy ${m.buy_score ?? row.score} · ${m.name || ""}`;
    await renderFactorModalBody(row);
    renderHot(data);
    renderDetail(row);
    detailTitle.textContent = symbol;
  }

  function closeFactorModal() {
    if (!factorModal) return;
    factorModal.hidden = true;
    factorModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    modalSymbol = null;
  }

  async function fetchFullSymbol(symbol) {
    const res = await fetch(`/api/symbol/${encodeURIComponent(symbol)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const full = await res.json();
    if (full.error) throw new Error(full.error);
    modalFullCache.set(symbol, full);
    mergeScanRow(symbol, full);
    return full;
  }

  async function renderFactorModalBody(rowOverride) {
    if (!factorModalBody || !modalSymbol) return;
    try {
      let row =
        rowOverride ||
        modalFullCache.get(modalSymbol) ||
        symbolCache.get(modalSymbol);
      let breakdown =
        row?.factor_breakdown ||
        row?.metrics?.factor_breakdown ||
        [];
      if (!breakdown.length) {
        factorModalBody.innerHTML =
          '<p class="muted">Loading factor checklist…</p>';
        try {
          row = await fetchFullSymbol(modalSymbol);
          breakdown = row.factor_breakdown || row.metrics?.factor_breakdown || [];
        } catch (err) {
          factorModalBody.innerHTML = `<p class="modal-err">Could not load factors for ${escapeHtml(modalSymbol)}: ${escapeHtml(err.message)}</p>`;
          return;
        }
      }
      const passed = breakdown.filter((x) => x.status === "pass");
      const failed = breakdown.filter((x) => x.status === "fail");
      const risk = breakdown.filter((x) => x.status === "risk");
      const na = breakdown.filter((x) => x.status === "na");

      let list = breakdown;
      if (factorFilter === "pass") list = passed;
      else if (factorFilter === "fail") list = failed;
      else if (factorFilter === "risk") list = risk;

      if (!list.length) {
        factorModalBody.innerHTML = `<div class="factor-summary">
          <span class="fs pass">${passed.length} passed</span>
          <span class="fs fail">${failed.length} failed</span>
        </div><p class="muted">No factors in this filter.</p>`;
        return;
      }

      const top = (row.metrics?.top_weighted_factors || [])
        .slice(0, 8)
        .map(
          (f) =>
            `<span class="chip-pass tier-${f.tier || "C"}" title="+${f.weighted_points} wt">` +
            `${escapeHtml(f.label || f.id)} (+${f.weighted_points})</span>`
        )
        .join("");

      const byCat = {};
      for (const f of list) {
        const cat = f.category || "other";
        (byCat[cat] ||= []).push(f);
      }
      const cats = Object.keys(byCat).sort(
        (a, b) =>
          (CATEGORY_SORT.indexOf(a) === -1 ? 99 : CATEGORY_SORT.indexOf(a)) -
          (CATEGORY_SORT.indexOf(b) === -1 ? 99 : CATEGORY_SORT.indexOf(b))
      );

      // New: conviction summary at top of modal so Analyze feels insightful immediately
      const pn = buildPositivesAndNegatives(row);
      const verdict = getConvictionVerdict(row);
      const modalConv = `<div class="conviction-verdict ${verdict.cls}" style="margin-bottom:0.5rem">${escapeHtml(verdict.text)}</div>`;
      const modalPos = pn.positives.length ? `<div class="positives" style="margin-bottom:0.3rem"><h4>✓ Positives</h4><ul style="margin:0;padding-left:1rem;font-size:0.78rem">${pn.positives.map(p=>`<li>${escapeHtml(p)}</li>`).join("")}</ul></div>` : "";
      const modalNeg = pn.negatives.length ? `<div class="negatives" style="margin-bottom:0.4rem"><h4>✗ Risks</h4><ul style="margin:0;padding-left:1rem;font-size:0.78rem">${pn.negatives.map(n=>`<li>${escapeHtml(n)}</li>`).join("")}</ul></div>` : "";

      const summary = `<div class="factor-summary">
        <span class="fs pass">${passed.length} passed</span>
        <span class="fs fail">${failed.length} failed</span>
        <span class="fs risk">${risk.length} risk</span>
        ${na.length ? `<span class="fs na">${na.length} n/a</span>` : ""}
      </div>`;
      const topBlock = top
        ? `<p class="muted section-label">Top weighted hits</p><div class="factor-chips">${top}</div>`
        : "";

      const sections = cats
        .map((cat) => {
          const items = byCat[cat]
            .sort((a, b) => (b.weighted_points || 0) - (a.weighted_points || 0))
            .map((f) => factorRowHtml(f))
            .join("");
          return `<section class="factor-cat"><h3>${escapeHtml(cat)}</h3><ul class="factor-checklist">${items}</ul></section>`;
        })
        .join("");

      factorModalBody.innerHTML = modalConv + modalPos + modalNeg + summary + topBlock + sections;
    } catch (err) {
      console.error("factor modal render", err);
      factorModalBody.innerHTML = `<p class="modal-err">Error rendering factors: ${escapeHtml(String(err.message || err))}</p>`;
    }
  }

  function factorRowHtml(f) {
    const status = f.status || "fail";
    const detail = f.label ? `<span class="factor-hit-label">${escapeHtml(f.label)}</span>` : "";
    const tierCls = (f.tier || "").replace("+", "\\+");
    const tier = f.tier ? `<span class="tier-badge tier-${tierCls}">${escapeHtml(f.tier)}</span>` : "";
    const wpVal = Number(f.weighted_points);
    const wp =
      status === "pass" && wpVal > 0
        ? `<span class="factor-pts" title="weight ×${f.weight || 1}">+${wpVal}</span>`
        : status === "pass" && f.points > 0
          ? `<span class="factor-pts muted-pts">+${f.points}</span>`
          : "";
    return `<li class="factor-item ${status}">
      <span class="factor-status" aria-label="${status}"></span>
      <div class="factor-info">
        <strong>${escapeHtml(f.name || f.id || "Factor")}</strong> ${tier}
        <span class="factor-desc">${escapeHtml(f.description || "")}</span>
        ${detail}
      </div>
      ${wp}
    </li>`;
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** Safe for HTML attributes (fixes M&M.NS → was parsed as "M" only). */
  function attrEsc(s) {
    return escapeHtml(s);
  }

  let _sparkSeq = 0;
  function sparklineSvg(values, w = 88, h = 30) {
    if (!values || values.length < 2) return "";
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const pad = 2;
    const coords = values.map((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = pad + (h - pad * 2) - ((v - min) / range) * (h - pad * 2);
      return [x, y];
    });
    const line = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
    const area = `M${coords[0][0].toFixed(1)},${h} L` + line.replace(/ /g, " L") + ` L${w},${h} Z`;
    const color = values[values.length - 1] >= values[0] ? "#34D77F" : "#F08585";
    const gid = `sg${_sparkSeq++}`;
    return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
      <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="${color}" stop-opacity="0.28"/>
        <stop offset="1" stop-color="${color}" stop-opacity="0"/>
      </linearGradient></defs>
      <path d="${area}" fill="url(#${gid})"/>
      <polyline fill="none" stroke="${color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" points="${line}"/>
    </svg>`;
  }

  /* ========== NEW: Thesis, Alerts, Watch, Radar, Export helpers ========== */

  function generateThesis(row) {
    if (!row) return { bullets: [], archetype: "Setup", risks: [] };
    const m = row.metrics || {};
    const breakdown = row.factor_breakdown || m.factor_breakdown || [];
    const top = (m.top_weighted_factors || row.top_factors || []).slice(0, 6);
    const alerts = (row.alerts || []).filter(a => /SMART|LEGEND|WHALE|POLITICIAN|FII|NEWS|RVOL|BASE|PRE-EARNINGS/i.test(a));

    const passedEntry = breakdown.filter(f => f.category === "entry" && f.status === "pass").length;
    const hasSM = (m.smart_money && m.smart_money.hits && m.smart_money.hits.length) || hasSmartMoneySignal(row);
    const hasCatalyst = breakdown.some(f => (f.category === "catalyst" || f.category === "news") && f.status === "pass");
    const isBase = breakdown.some(f => ["base_compression", "cup_forming", "pullback_50dma", "higher_lows"].includes(f.id) && f.status === "pass");
    const nearHighRisk = breakdown.some(f => ["already_at_high", "extended_run", "chase_risk"].includes(f.id) && (f.status === "risk" || f.status === "pass"));

    let archetype = "Multi-factor Setup";
    if (hasSM) archetype = "Smart Money + Catalyst";
    else if (passedEntry >= 2 && isBase) archetype = "Early Base / Coiling";
    else if (row.earnings_soon || breakdown.some(f => f.id && f.id.includes("earnings") && f.status === "pass")) archetype = "Pre-Earnings Catalyst";
    else if (hasCatalyst && (m.rvol || 0) > 1.5) archetype = "News + Volume Catalyst";

    const bullets = [];
    // Super heavy: if big investor, lead thesis with exact name + quality
    if (hasSM && m.smart_money && m.smart_money.hits && m.smart_money.hits.length) {
      const hit = m.smart_money.hits[0];
      const q = hit.quality ? ` (${hit.quality})` : "";
      bullets.unshift(`🚨 EXACT INVESTOR: ${hit.name}${q} — S+ heavy weight, monitor closely`);
    }

    if (hasSM) bullets.push("S+ tier named smart money / politician / FII buy context in recent news");
    if (passedEntry) bullets.push(`${passedEntry} entry-setup factors (room to run, pullback, higher lows, compression)`);
    if (hasCatalyst) bullets.push("Clear catalyst(s): contracts, policy, earnings tone, guidance, or sector tailwind");
    if ((m.buy_score || row.score || 0) > 70) bullets.push("High buy score — engine sees favorable risk/reward for next entry (penalizes extensions)");
    if (top.length) bullets.push("Top drivers: " + top.map(t => (t.label || t.id)).slice(0,3).join(" · "));
    if (alerts.length) bullets.push("Live alerts: " + alerts.slice(0,2).join(" | "));

    const risks = [];
    if (nearHighRisk) risks.push("Extension / chase risk detected — price near 52w high or parabolic move");
    if (breakdown.some(f => f.id === "rsi_overbought" && f.status === "risk")) risks.push("RSI overbought zone");
    if (breakdown.some(f => f.id === "high_short" && f.status === "risk")) risks.push("Elevated short interest");
    if (!hasCatalyst && !hasSM) risks.push("Limited fresh catalyst in current news window");

    return { bullets: bullets.slice(0,5), archetype, risks: risks.slice(0,3) };
  }

  /** Build clear positives vs negatives for conviction (used in detail + modal summary) */
  function buildPositivesAndNegatives(row) {
    if (!row) return { positives: [], negatives: [] };
    const m = row.metrics || {};
    const bd = row.factor_breakdown || m.factor_breakdown || [];
    const pos = [];
    const neg = [];

    // S+ / smart money is the strongest positive signal
    if (m.smart_money?.hits?.length) {
      const names = m.smart_money.hits.map(h => h.name).slice(0,4).join(", ");
      pos.push(`S+ smart money: ${names} (heavy 6.5× weight in buy score)`);
    } else if (hasSmartMoneySignal(row)) {
      pos.push("Named whale / politician / FII buy context detected in news");
    }

    // Strong entry setups
    const entryHits = bd.filter(f => f.category === "entry" && f.status === "pass");
    if (entryHits.length >= 2) pos.push(`${entryHits.length} entry factors (room to run, base, higher lows, pullback, compression)`);
    else if (entryHits.length === 1) pos.push("At least one clean entry setup (not chasing highs)");

    // Catalysts
    const catHits = bd.filter(f => (f.category === "catalyst" || f.category === "news") && f.status === "pass");
    if (catHits.length) pos.push(`Catalyst(s): ${catHits.slice(0,3).map(f=>f.name||f.id).join(" · ")}`);

    // Quality fundamentals / valuation
    const fundHits = bd.filter(f => (f.category === "fundamental" || f.category === "valuation") && f.status === "pass");
    if (fundHits.length >= 3) pos.push("Solid fundamentals + sector-reasonable valuation");
    else if (fundHits.length) pos.push("Multiple fundamental / valuation checks passing");

    // Technical health
    if (bd.some(f => ["ma_bull_stack","rsi_bull_zone","macd_bullish","golden_cross_zone"].includes(f.id) && f.status==="pass"))
      pos.push("Constructive technicals (MA stack / momentum turning)");

    // High buy score
    const bs = m.buy_score ?? row.score ?? 0;
    if (bs >= 72) pos.push("High buy score – engine sees favorable next-entry risk/reward");
    else if (bs >= 55) pos.push("Decent buy score with some supporting factors");

    // === NEGATIVES / RISKS ===
    const riskHits = bd.filter(f => f.status === "risk" || f.category === "risk");
    riskHits.forEach(f => {
      if (["extended_run","chase_risk","already_at_high","parabolic_move"].includes(f.id))
        neg.push("Extended / near 52w high – limited upside, chase risk");
      else if (f.id === "rsi_overbought") neg.push("RSI overbought – momentum exhaustion risk");
      else if (f.id === "high_short") neg.push("Elevated short interest – potential squeeze or overhang");
      else if (f.id === "distribution_day") neg.push("Distribution day (down on heavy volume)");
      else neg.push(f.name || f.id);
    });

    if (m.is_extended) neg.push("Price extended – engine applies penalty to buy score");
    if ((m.pct_52w_range || 0) > 92) neg.push("Trading in top ~8% of 52-week range");

    const failCount = bd.filter(f => f.status === "fail").length;
    if (failCount > 8) neg.push(`${failCount} checklist items not met (many fundamentals or technicals missing)`);

    if (!catHits.length && !m.smart_money?.hits?.length) neg.push("No fresh named catalyst or smart-money signal in recent headlines");

    // Dedup + limit for UI
    const uniqPos = [...new Set(pos)].slice(0, 6);
    const uniqNeg = [...new Set(neg)].slice(0, 5);
    return { positives: uniqPos, negatives: uniqNeg };
  }

  /** Plain-English verdict to help decide buy / watch / avoid */
  function getConvictionVerdict(row) {
    if (!row) return { text: "No data", cls: "watch" };
    const m = row.metrics || {};
    const bs = m.buy_score ?? row.score ?? 0;
    const qs = m.quality_score ?? 0;
    const sm = !!(m.smart_money?.hits?.length || hasSmartMoneySignal(row));
    const ext = !!m.is_extended;
    const entry = (row.factor_breakdown || []).filter(f => f.category === "entry" && f.status === "pass").length;

    if (sm && bs >= 65 && !ext && entry >= 1) {
      return { text: "Strong S+ early setup – favor on pullbacks or confirmation. High-conviction candidate for small starter position.", cls: "bull" };
    }
    if (sm && bs >= 50) {
      return { text: "Whale / politician activity + decent setup. Watch closely for entry; size small because of news sensitivity.", cls: "bull" };
    }
    if (bs >= 72 && !ext) {
      return { text: "High buy score, clean entry zone – engine likes risk/reward for next leg. Consider scaling in on dips.", cls: "bull" };
    }
    if (bs >= 55 && qs >= 60 && !ext) {
      return { text: "Solid multi-factor setup with acceptable quality. Good for watchlist; wait for better entry or more catalyst.", cls: "watch" };
    }
    if (ext || (m.pct_52w_range || 0) > 93) {
      return { text: "Extended near highs – buy score penalized. Better to wait for base / pullback or avoid new adds.", cls: "avoid" };
    }
    if (bs < 40) {
      return { text: "Low conviction on current data. Weak entry factors or many risks. Skip or deep research only.", cls: "avoid" };
    }
    return { text: "Mixed signals. Quality name or some catalysts but entry not ideal yet. Add to My List and monitor.", cls: "watch" };
  }

  /** Rich whale / S+ details modal or inline panel (click any whale badge) */
  function showSmartMoneyDetails(symbol, row) {
    const m = (row && row.metrics) || {};
    const hits = m.smart_money?.hits || [];
    const primary = m.smart_money?.primary_alert || (row && row.alerts && row.alerts.find(a => /LEGEND|WHALE|POLITICIAN|FOREIGN/i.test(a))) || "Smart money signal";

    let html = `<div class="whale-intel"><h4>🐳 S+ Smart Money Intel — ${escapeHtml(symbol)}</h4>`;
    if (hits.length) {
      hits.forEach(h => {
        html += `<div class="whale-hit">
          <span class="name">${escapeHtml(h.name)}</span> <span class="muted">(${escapeHtml(h.kind || "")}, tier ${escapeHtml(h.tier || "S+")})</span>
          <span class="ctx">${escapeHtml(h.headline || "Matched in recent news with buy context")}</span>
        </div>`;
      });
    } else {
      html += `<div class="muted">Named smart money / politician / FII buy context flagged in headlines (S+ tier in engine).</div>`;
    }
    html += `<div style="margin-top:0.35rem;font-size:0.72rem;color:var(--muted)">S+ names multiply their factor weight by 6.5× in the buy_score calculation. This is the single heaviest boost the algorithm applies. Click “Analyze” or “Full factors” for the complete weighted breakdown.</div>`;
    html += `<div style="margin-top:0.3rem;display:flex;gap:0.35rem;flex-wrap:wrap">`;
    html += `<button class="tiny" data-act="analyze">Full Analyze</button>`;
    html += `<button class="tiny" data-act="factors">Full factors checklist</button>`;
    html += `<button class="tiny" data-act="watch">★ Watch</button>`;
    html += `</div></div>`;

    // Reuse alerts-panel style or create a floating intel card
    const card = document.createElement("div");
    card.className = "alerts-panel";
    card.style.bottom = "auto";
    card.style.top = "90px";
    card.innerHTML = `<div class="ap-header"><strong>Whale / S+ Details</strong> <button class="close-x">×</button></div><div class="ap-body">${html}</div>`;
    document.body.appendChild(card);

    card.querySelector(".close-x").onclick = () => card.remove();
    card.onclick = (e) => { if (e.target === card) card.remove(); };

    const sym = symbol;
    card.querySelectorAll("button").forEach(btn => {
      btn.onclick = (ev) => {
        ev.stopPropagation();
        const act = btn.dataset.act;
        card.remove();
        if (act === "analyze") {
          document.querySelector('.tab[data-tab="hot"]')?.click();
          fetchFullSymbol(sym).then(full => { renderDetail(full); openFactorModal(sym, lastData); }).catch(()=>{});
        } else if (act === "factors") {
          openFactorModal(sym, lastData);
        } else if (act === "watch") {
          const r = findRow(sym, lastData);
          if (watchlist.some(w => w.symbol === sym)) removeFromWatch(sym); else addToWatch(sym, r || {symbol: sym});
          renderWatch(lastData);
        } else if (act === "watch-alert") {
          const r = findRow(sym, lastData);
          addToWatchWithAlert(sym, r || {symbol: sym});
          renderWatch(lastData);
        }
      };
    });
  }

  function pushAlert(type, symbol, msg, score) {
    const a = { type, symbol, msg, ts: new Date().toISOString(), score: score || null };
    recentAlerts.unshift(a);
    if (recentAlerts.length > 30) recentAlerts.pop();
    renderAlertBell();
    // Browser notification (best effort)
    if (alertsEnabled && "Notification" in window && Notification.permission === "granted") {
      try { new Notification(`Market Pulse • ${symbol}`, { body: msg.slice(0, 120), tag: symbol }); } catch(e){}
    }
    // Also surface in radar if smart money
    if (type === "smart_money") {
      renderRadar(lastData);
    }
  }

  function renderAlertBell() {
    if (alertCountEl && alertBell) {
      const n = recentAlerts.length;
      alertCountEl.textContent = n > 9 ? "9+" : n;
      alertBell.classList.toggle("has-alerts", n > 0);
    }
    renderIntelFeed();
  }

  function timeAgo(ts) {
    if (!ts) return "";
    const t = new Date(ts).getTime();
    if (!t) return "";
    const diff = Math.max(0, (new Date().getTime() - t) / 1000);
    if (diff < 60) return `${Math.round(diff)}s`;
    if (diff < 3600) return `${Math.round(diff / 60)}m`;
    if (diff < 86400) return `${Math.round(diff / 3600)}h`;
    return `${Math.round(diff / 86400)}d`;
  }

  const FEED_STYLE = {
    high_score: {accent: "#34D77F", iconbg: "rgba(34,197,94,.14)", icon: "📈"},
    smart_money: {accent: "#FACC15", iconbg: "rgba(250,204,21,.14)", icon: "💎"},
    pre_earnings: {accent: "#B49BF5", iconbg: "rgba(139,92,246,.14)", icon: "📅"},
    risk: {accent: "#F08585", iconbg: "rgba(239,68,68,.14)", icon: "⚠"},
    news: {accent: "#7DB4F7", iconbg: "rgba(96,165,250,.14)", icon: "📰"},
  };
  function renderIntelFeed() {
    const feed = document.getElementById("intelFeed");
    if (!feed) return;
    feed.innerHTML = recentAlerts.slice(0, 14).map(a => {
      const st = FEED_STYLE[a.type] || {accent: "#38BDF8", iconbg: "rgba(56,189,248,.14)", icon: "⚡"};
      const sym = a.symbol ? `<span class="fa-sym">${escapeHtml(a.symbol)}</span>` : "";
      return `<div class="feed-alert clickable" data-sym="${attrEsc(a.symbol || "")}" style="--accent:${st.accent};--iconbg:${st.iconbg}">
        <span class="fa-icon">${st.icon}</span>
        <span class="fa-main">
          <span class="fa-title">${escapeHtml((a.msg || a.type || "Signal").split(" — ")[0].slice(0, 40))}${sym}</span>
          <span class="fa-text">${escapeHtml(a.msg || "")}</span>
        </span>
        <span class="fa-time">${timeAgo(a.ts)}</span>
      </div>`;
    }).join("");
    feed.querySelectorAll(".feed-alert[data-sym]").forEach(el => {
      el.addEventListener("click", () => {
        const sym = el.dataset.sym;
        if (sym) selectSymbol(sym, lastData);
      });
    });
  }

  async function refreshAlertRulesUI() {
    const listEl = document.getElementById("alertRulesList");
    if (!listEl) return;
    const rules = await loadServerAlertRules();
    if (!rules.length) {
      listEl.innerHTML = '<span class="muted">No rules yet. Add via form (e.g. min_buy_score 65 + rvol 2 or has_investor).</span>';
      return;
    }
    listEl.innerHTML = rules.map(r => {
      const c = r.condition || {};
      const condStr = Object.entries(c).map(([k,v])=>`${k}:${v}`).join(" & ") || "default";
      return `<div style="margin:2px 0;padding:2px 4px;background:#0f172a;border-radius:3px;display:flex;justify-content:space-between;align-items:center">
        <span><strong>#${r.id}</strong> ${escapeHtml(r.rule_type)}: ${escapeHtml(condStr)} ${r.enabled?"✓":"(off)"} ${r.last_triggered? "· last:"+new Date(r.last_triggered).toLocaleDateString() : ""}</span>
        <button class="tiny danger" data-del-rule="${r.id}">del</button>
      </div>`;
    }).join("");
    // bind dels
    listEl.querySelectorAll("[data-del-rule]").forEach(btn => {
      btn.onclick = async (ev) => {
        ev.stopImmediatePropagation();
        const id = parseInt(btn.dataset.delRule);
        await deleteServerAlertRule(id);
        await refreshAlertRulesUI();
      };
    });
  }

  function showAlertRulesModal() {
    // Fallback full modal if inline hidden
    const rulesP = document.createElement("div");
    rulesP.className = "alerts-panel";
    rulesP.innerHTML = `<div class="ap-header"><strong>Alert Rules (server persisted)</strong> <button class="close-x">×</button></div>
      <div class="ap-body"><p class="muted">Rules run on every scan using same analyze_symbol + smart_money_intel. Create via the form in ★ My List panel for best UX. Click bell for live alerts with 🚨 exact investor names.</p><div id="modalRulesList"></div></div>`;
    document.body.appendChild(rulesP);
    rulesP.querySelector(".close-x").onclick = () => rulesP.remove();
    // populate
    (async () => {
      const ls = rulesP.querySelector("#modalRulesList");
      const rs = await loadServerAlertRules();
      ls.innerHTML = rs.map(r=> `<div>#${r.id} ${r.rule_type} ${JSON.stringify(r.condition||{})} <button data-del="${r.id}">x</button></div>`).join("") || "None";
      ls.querySelectorAll("button[data-del]").forEach(b=> b.onclick= async ()=>{ await deleteServerAlertRule(b.dataset.del); ls.innerHTML="deleted; reload panel"; });
    })();
  }

  function showAlertsPanel() {
    // Merge client + fetch latest server for rich display (investor exact names etc)
    (async () => {
      const srv = await fetchRecentServerAlerts();
      const merged = [...recentAlerts];
      srv.forEach(sa => {
        if (!merged.some(m => m.symbol === sa.symbol && (m.msg || "").includes(sa.message?.slice(0,30) || ""))) {
          merged.unshift({type: sa.rule_type || "server", symbol: sa.symbol, msg: sa.message, ts: sa.triggered_at || new Date().toISOString(), score: sa.buy_score, server: true, details: sa.details});
        }
      });
      const html = merged.length
        ? merged.slice(0,25).map(a => {
            const isSrv = a.server || a.msg?.includes("🚨 Investor");
            const clickHint = `data-sym="${attrEsc(a.symbol)}" style="cursor:pointer" title="Click to analyze ${a.symbol}"`;
            return `<div class="alert-item" ${clickHint}><strong>${escapeHtml(a.symbol)}</strong> <span class="muted">${escapeHtml(a.type)}</span>${isSrv?' <span style="color:#eab308">[server]</span>':''}<br><span>${escapeHtml(a.msg)}</span><div class="muted" style="font-size:0.7rem">${new Date(a.ts).toLocaleTimeString()} ${a.score? "· score "+a.score : ""}</div></div>`;
          }).join("")
        : '<p class="muted">No alerts yet. Server rules (buy_score>65 AND rvol>2, has S+ whale exact name, earnings+score) + local high-score/S+ will appear. Matches from smart_money_intel include full "🚨 Investor: Name (Quality)".</p>';
      const panel = document.createElement("div");
      panel.className = "alerts-panel";
      panel.innerHTML = `<div class="ap-header"><strong>Recent Alerts (in-app + server)</strong> <button class="close-x">×</button></div><div class="ap-body">${html}</div>`;
      document.body.appendChild(panel);
      // make alert items clickable -> analyze
      panel.querySelectorAll(".alert-item[data-sym]").forEach(item => {
        item.onclick = (ev) => {
          if (ev.target.closest("button")) return;
          const sym = item.dataset.sym;
          if (sym) {
            panel.remove();
            document.querySelector('.tab[data-tab="hot"]')?.click();
            if (symbolSearch) symbolSearch.value = sym;
            fetchFullSymbol(sym).then(full => { renderDetail(full); openFactorModal(sym, lastData||{}); }).catch(()=>{});
          }
        };
      });
      panel.querySelector(".close-x").onclick = () => panel.remove();
      panel.onclick = (e) => { if (e.target === panel) panel.remove(); };
    })();
  }

  function addToWatch(symbol, row, alsoCreateDefaultAlert=false) {
    symbol = symbol.toUpperCase();
    if (watchlist.find(w => w.symbol === symbol)) return;
    const m = row && row.metrics ? row.metrics : {};
    const entry = {
      symbol,
      addedAt: new Date().toISOString(),
      addedScore: Math.round(row ? (row.buy_score ?? row.score ?? 0) : 0),
      lastScore: Math.round(row ? (row.buy_score ?? row.score ?? 0) : 0),
      lastBuy: Math.round(m.buy_score ?? row?.score ?? 0),
      lastQuality: Math.round(m.quality_score ?? 0),
    };
    watchlist.unshift(entry);
    saveWatch();
    // Server persist (best effort, non-blocking for UI speed)
    addToServerWatch(symbol, alsoCreateDefaultAlert ? "added+alert" : "").then(() => {
      if (activeTab === "watch") renderWatch(lastData);
    });
    renderWatch(lastData);
    // gentle nudge
    if (alertBell) {
      alertBell.style.transform = "scale(1.2)";
      setTimeout(() => { if (alertBell) alertBell.style.transform = ""; }, 400);
    }
    // Optional quick "set alert" nudge: user can use Manage panel for full rules; auto for high conv done server-side
    if (alsoCreateDefaultAlert) {
      // fire a client hint; real rule eval is server on next scan
      pushAlert("watch", symbol, "Added to server watch + monitoring for matching rules", entry.lastBuy);
    }
  }

  function removeFromWatch(symbol) {
    watchlist = watchlist.filter(w => w.symbol !== symbol.toUpperCase());
    saveWatch();
    removeFromServerWatch(symbol).then(()=>{ if (activeTab==="watch") renderWatch(lastData); });
    renderWatch(lastData);
  }

  function saveWatch() {
    try { localStorage.setItem("marketpulse_watchlist", JSON.stringify(watchlist)); } catch(e){}
  }

  // "Add to My List + set alert" convenience (used from hot rows / detail)
  function addToWatchWithAlert(symbol, row) {
    addToWatch(symbol, row, true);
  }

  function updateWatchFromRow(symbol, row) {
    const w = watchlist.find(x => x.symbol === symbol.toUpperCase());
    if (!w || !row) return;
    const m = row.metrics || {};
    w.lastScore = Math.round(row.buy_score ?? row.score ?? w.lastScore ?? 0);
    w.lastBuy = Math.round(m.buy_score ?? row.score ?? 0);
    w.lastQuality = Math.round(m.quality_score ?? 0);
    saveWatch();
  }

  function hasSmartMoneySignal(row) {
    if (!row) return false;
    if (row.metrics?.has_smart_money || row.metrics?.smart_money?.hits?.length) return true;
    return (row.alerts || []).some((a) => /LEGEND|WHALE|POLITICIAN|FOREIGN BUY|SMART MONEY/i.test(a));
  }

  function renderRadar(data) {
    const el = document.getElementById("radarList");
    if (!el) return;
    const pool = (data && (data.hot || [])) || [];
    const hits = pool.filter(r => hasSmartMoneySignal(r) || (r.metrics && r.metrics.smart_money));
    // Also pull recent from alerts we generated
    const fromAlerts = recentAlerts.filter(a => a.type === "smart_money").slice(0,5).map(a => ({symbol: a.symbol, _fromAlert: true}));
    if (!hits.length && !fromAlerts.length) {
      el.innerHTML = '<p class="muted">No named smart money hits in current hot list. New S+ detections (legends, politicians, credible FII) will surface here instantly via the live WS feed and broad news aggregation.</p>';
      return;
    }
    let html = hits.slice(0,12).map(r => {
      const sm = r.metrics?.smart_money || {};
      const primary = sm.primary_alert || (r.alerts || []).find(a => /LEGEND|WHALE|POLITICIAN/i.test(a)) || "Smart money signal";
      return `<div class="radar-row" data-symbol="${attrEsc(r.symbol)}">
        <strong>${escapeHtml(r.symbol)}</strong> <span class="whale-badge">${escapeHtml(primary).slice(0,48)}</span>
        <span class="muted">buy ${r.buy_score ?? r.score ?? "—"}</span>
        <button class="tiny" data-act="analyze">Analyze</button>
        <button class="tiny" data-act="watch">★ Watch</button>
      </div>`;
    }).join("");
    // merge alert-only
    fromAlerts.forEach(a => {
      if (!hits.find(h => h.symbol === a.symbol)) {
        html += `<div class="radar-row" data-symbol="${attrEsc(a.symbol)}"><strong>${escapeHtml(a.symbol)}</strong> <span class="whale-badge">Recent S+ hit</span> <button class="tiny" data-act="analyze">Analyze</button></div>`;
      }
    });
    el.innerHTML = html;
    el.querySelectorAll(".radar-row").forEach(row => {
      row.onclick = (e) => {
        const sym = row.dataset.symbol;
        if (e.target.dataset.act === "watch") { addToWatch(sym, findRow(sym, data)); return; }
        if (e.target.dataset.act === "analyze" || !e.target.dataset.act) {
          document.querySelector('.tab[data-tab="hot"]')?.click();
          if (symbolSearch) symbolSearch.value = sym;
          fetchFullSymbol(sym).then(full => {
            renderDetail(full);
            openFactorModal(sym, data || lastData);
          }).catch(()=>{});
        }
      };
      // Click whale badge text in radar → rich S+ details
      const badge = row.querySelector(".whale-badge");
      if (badge) {
        badge.style.cursor = "pointer";
        badge.onclick = (ev) => { ev.stopPropagation(); showSmartMoneyDetails(row.dataset.symbol, findRow(row.dataset.symbol, data) || {symbol: row.dataset.symbol}); };
      }
    });
  }

  function exportCSV(rows, filename = "market_pulse_export.csv") {
    if (!rows || !rows.length) return;
    const headers = ["symbol","buy_score","quality_score","factors_hit","day_chg","rvol","market"];
    const lines = [headers.join(",")];
    rows.forEach(r => {
      const m = r.metrics || {};
      lines.push([
        r.symbol,
        r.buy_score ?? r.score ?? "",
        m.quality_score ?? "",
        r.factors_hit ?? "",
        m.day_chg_pct ?? "",
        m.rvol ?? "",
        r.market ?? ""
      ].join(","));
    });
    const blob = new Blob([lines.join("\n")], {type: "text/csv"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  }

  function buildMarkdownThesis(symbol, row) {
    const t = generateThesis(row);
    const m = row.metrics || {};
    let md = `# ${symbol} — Market Pulse Thesis\n\n`;
    md += `**Buy score**: ${row.buy_score ?? row.score ?? "—"}  |  **Quality**: ${m.quality_score ?? "—"}  |  **Factors**: ${(row.factors_hit ?? "?")}/${row.factors_total ?? "?"}\n\n`;
    md += `**Archetype**: ${t.archetype}\n\n`;
    md += `## Why this scores now\n`;
    t.bullets.forEach(b => md += `- ${b}\n`);
    if (t.risks.length) {
      md += `\n## Key risks to watch\n`;
      t.risks.forEach(r => md += `- ${r}\n`);
    }
    md += `\n*Generated by Market Pulse 100+ factor engine (same logic as live hot list). Not financial advice.*\n`;
    return md;
  }

  function copyThesis(symbol, row) {
    const md = buildMarkdownThesis(symbol, row);
    navigator.clipboard.writeText(md).then(() => {
      document.querySelectorAll('[data-act="thesis"]').forEach(btn => {
        const old = btn.textContent;
        btn.textContent = "Copied ✓";
        setTimeout(() => { btn.textContent = old; }, 1200);
      });
      // non-blocking toast
      const t = document.createElement("span");
      t.textContent = " Thesis copied as Markdown ";
      t.style.cssText = "position:fixed;bottom:12px;right:12px;background:#111827;color:#e0f0ff;padding:4px 10px;border-radius:4px;font-size:0.8rem";
      document.body.appendChild(t);
      setTimeout(() => t.remove(), 1400);
    }).catch(() => {
      prompt("Copy this thesis Markdown:", md);
    });
  }

  function hotFingerprint(data) {
    const pool = getHotPool(data).slice(0, 80);
    return pool
      .map((r) => {
        const m = r.metrics || {};
        return `${r.symbol}:${rankScore(r)}:${m.day_chg_pct}:${m.price}`;
      })
      .join("|");
  }

  function filterSectorStocks(stocks) {
    if (!stocks?.length) return [];
    if (sectorMarketFilter === "all") return stocks;
    return stocks.filter((s) => s.market === sectorMarketFilter);
  }

  function filterSectorRow(sec) {
    const stocks = filterSectorStocks(sec.stocks || sec.top_picks || []);
    if (!stocks.length && sectorMarketFilter !== "all") return null;
    const hot = stocks.filter((s) => (s.buy_score ?? s.score ?? 0) >= 38);
    const early = stocks.filter((s) => !s.is_extended && (s.buy_score ?? s.score ?? 0) >= 38);
    const avgBuy =
      stocks.reduce((a, s) => a + (s.buy_score ?? s.score ?? 0), 0) / (stocks.length || 1);
    const avgDay =
      stocks.reduce((a, s) => a + (s.day_chg_pct || 0), 0) / (stocks.length || 1);
    return {
      ...sec,
      stock_count: stocks.length,
      hot_count: hot.length,
      early_buy_count: early.length,
      avg_buy_score: Math.round(avgBuy * 10) / 10,
      avg_day_chg_pct: Math.round(avgDay * 100) / 100,
      top_picks: (sec.top_picks || stocks).filter((p) =>
        sectorMarketFilter === "all" ? true : p.market === sectorMarketFilter
      ),
      stocks,
    };
  }

  function sectorFingerprint(data) {
    const sectors = data?.sectors || [];
    return sectors
      .map(
        (s) =>
          `${s.sector}:${s.stock_count}:${s.hot_count}:${s.early_buy_count}:${s.avg_buy_score}`
      )
      .join("|");
  }

  function setSectorHotFilter(sectorName) {
    sectorFilter = sectorName || null;
    if (!sectorFilterBadge) return;
    if (sectorFilter) {
      sectorFilterBadge.hidden = false;
      sectorFilterBadge.innerHTML = `Sector: ${escapeHtml(sectorFilter)} <button type="button" title="Clear sector filter" aria-label="Clear">×</button>`;
    } else {
      sectorFilterBadge.hidden = true;
      sectorFilterBadge.innerHTML = "";
    }
  }

  sectorFilterBadge?.addEventListener("click", (e) => {
    if (e.target.closest("button")) {
      setSectorHotFilter(null);
      renderHot(lastData);
    }
  });

  function goToHotWithSector(sectorName) {
    setSectorHotFilter(sectorName);
    document.querySelector('.tab[data-tab="hot"]')?.click();
    renderHot(lastData);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function renderCycleStrip(data) {
    if (!cycleStrip) return;
    const groups = data?.cycle_overview || [];
    if (!groups.length) {
      cycleStrip.innerHTML = '<span class="muted">Cyclical overview loads after first full scan…</span>';
      return;
    }
    cycleStrip.innerHTML = groups
      .map((g) => {
        const c = g.cycle || "mixed";
        return `<div class="cycle-card clickable" data-cycle="${escapeHtml(c)}" title="Click to view Sectors tab (filter to this cycle)">
          <div class="cycle-title">${escapeHtml(g.label || c)}</div>
          <div class="cycle-stats">
            <strong>${g.sector_count}</strong> sectors ·
            <strong>${g.stock_count}</strong> stocks ·
            <strong>${g.early_buy_count}</strong> early buys ·
            avg buy <strong>${g.avg_buy_score}</strong>
          </div>
        </div>`;
      })
      .join("");

    cycleStrip.querySelectorAll(".cycle-card").forEach(card => {
      card.addEventListener("click", () => {
        // Switch to sectors tab; user can further filter. Could enhance with cycleFilter state.
        document.querySelector('.tab[data-tab="sectors"]')?.click();
      });
    });
  }

  function renderSectorList(data) {
    if (!sectorList) return;
    const raw = data?.sectors || [];
    const filtered = raw.map(filterSectorRow).filter(Boolean);
    filtered.sort(
      (a, b) =>
        b.early_buy_count - a.early_buy_count ||
        b.avg_buy_score - a.avg_buy_score ||
        b.hot_count - a.hot_count
    );
    if (!filtered.length) {
      sectorList.innerHTML =
        '<p class="muted" style="padding:1rem">No sector data yet — wait for first scan (~90s).</p>';
      return;
    }
    const marketLabel =
      sectorMarketFilter === "all" ? "" : ` · ${sectorMarketFilter.toUpperCase()} only`;
    if (sectorSummaryHint) {
      const totalStocks = filtered.reduce((a, s) => a + s.stock_count, 0);
      const totalEarly = filtered.reduce((a, s) => a + s.early_buy_count, 0);
      sectorSummaryHint.textContent = `${filtered.length} sectors · ${totalStocks} stocks${marketLabel} · ${totalEarly} early buys`;
    }
    sectorList.innerHTML = filtered
      .map((s) => {
        const sel = s.sector === selectedSector ? "selected" : "";
        const cycle = s.cycle || "mixed";
        const rot = s.rotation || "neutral";
        return `<button type="button" class="sector-row ${sel}" data-sector="${attrEsc(s.sector)}">
          <span class="sector-name">${escapeHtml(s.sector)}</span>
          <span class="sector-counts">${s.stock_count} stocks · ${s.hot_count} hot · ${s.early_buy_count} early</span>
          <span class="sector-meta">Avg buy ${s.avg_buy_score} · day ${s.avg_day_chg_pct > 0 ? "+" : ""}${s.avg_day_chg_pct}%</span>
          <span class="sector-badges">
            <span class="cycle-tag ${escapeHtml(cycle)}">${escapeHtml(s.cycle_label || cycle)}</span>
            <span class="rotation-tag ${escapeHtml(rot)}">${escapeHtml(rot)}</span>
          </span>
        </button>`;
      })
      .join("");
    sectorList.querySelectorAll(".sector-row").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedSector = btn.dataset.sector;
        renderSectorList(data);
        renderSectorDetail(data);
      });
    });
  }

  function renderSectorDetail(data) {
    if (!sectorDetail) return;
    if (!selectedSector) {
      sectorDetail.innerHTML =
        '<p class="muted">Select a sector to see top picks and all stocks ranked by buy score.</p>';
      return;
    }
    const raw = (data?.sectors || []).find((s) => s.sector === selectedSector);
    const sec = raw ? filterSectorRow(raw) : null;
    if (!sec) {
      sectorDetail.innerHTML = "<p class=\"muted\">Sector not found.</p>";
      return;
    }
    const picks = sec.top_picks?.length ? sec.top_picks : (sec.stocks || []).slice(0, 12);
    const all = sec.stocks || picks;

    const pickRows = picks
      .map((p) => sectorStockRowHtml(p, true))
      .join("");
    const allRows = all.map((p) => sectorStockRowHtml(p, false)).join("");

    sectorDetail.innerHTML = `
      <h3>${escapeHtml(sec.sector)}</h3>
      <p class="muted">${escapeHtml(sec.cycle_label || "")} · bucket ${escapeHtml(sec.sector_bucket || "")} · rotation <strong>${escapeHtml(sec.rotation || "neutral")}</strong></p>
      <p class="meta-line">${sec.stock_count} tracked · ${sec.hot_count} hot (score ≥38) · ${sec.early_buy_count} early (non-extended) · ${sec.extended_count ?? 0} extended</p>
      <p class="meta-line">US ${sec.us_count ?? "—"} · India ${sec.india_count ?? "—"} · avg buy ${sec.avg_buy_score} · avg day ${sec.avg_day_chg_pct}%</p>
      <button type="button" class="chip active sector-hot-btn" data-sector="${attrEsc(sec.sector)}">View hot list in this sector</button>
      <p class="muted section-label">Best buys (early / high buy score)</p>
      <table class="sector-picks-table"><thead><tr><th>Symbol</th><th>Buy</th><th>Factors</th><th>Day%</th></tr></thead><tbody>${pickRows || '<tr><td colspan="4" class="muted">No picks</td></tr>'}</tbody></table>
      <p class="muted section-label">All stocks in sector (${all.length})</p>
      <table class="sector-picks-table"><thead><tr><th>Symbol</th><th>Buy</th><th>Factors</th><th>Day%</th></tr></thead><tbody>${allRows}</tbody></table>
    `;

    sectorDetail.querySelector(".sector-hot-btn")?.addEventListener("click", () => {
      goToHotWithSector(sec.sector);
    });
    sectorDetail.querySelectorAll("tr[data-symbol]").forEach((tr) => {
      tr.addEventListener("click", () => {
        const sym = tr.dataset.symbol;
        openFactorModal(sym, data);
        selectSymbol(sym, data);
      });
    });
  }

  function sectorStockRowHtml(p, isPickSection) {
    const buy = p.buy_score ?? p.score ?? "—";
    const day = p.day_chg_pct ?? 0;
    const cls = day >= 0 ? "pos" : "neg";
    const ext = p.is_extended ? '<span class="ext-badge">EXT</span>' : "";
    const early =
      !p.is_extended && Number(buy) >= 38 ? ' class="pick-early"' : isPickSection ? ' class="pick-early"' : "";
    const fh = p.factors_hit ?? "—";
    const ft = p.factors_total ?? "";
    return `<tr${early} data-symbol="${attrEsc(p.symbol)}">
      <td><strong>${escapeHtml(p.symbol)}</strong>${ext}<br><span class="sym-name">${escapeHtml(p.name || "")}</span></td>
      <td><span class="score-pill">${buy}</span></td>
      <td>${fh}/${ft}</td>
      <td class="${cls}">${day > 0 ? "+" : ""}${day}%</td>
    </tr>`;
  }

  function renderSectors(data) {
    if (!sectorList && !cycleStrip) return;
    renderCycleStrip(data);
    renderSectorList(data);
    if (selectedSector) renderSectorDetail(data);
  }

  function filterAndSort(rows) {
    let list = [...rows];
    if (sectorFilter) {
      list = list.filter((r) => (r.metrics || {}).sector === sectorFilter);
    }
    if (earlyOnly) {
      list = list.filter((r) => !(r.metrics || {}).is_extended);
    }
    if (whaleOnly) {
      list = list.filter((r) => hasSmartMoneySignal(r));
    }
    const q = (symbolSearch?.value || "").trim().toUpperCase();
    if (q) {
      list = list.filter((r) => {
        const m = r.metrics || {};
        return (
          r.symbol.toUpperCase().includes(q) ||
          (m.name || "").toUpperCase().includes(q)
        );
      });
    }
    const sort = sortBy?.value || "score";
    list.sort((a, b) => {
      const ma = a.metrics || {};
      const mb = b.metrics || {};
      if (sort === "quality") {
        return ((mb.quality_score || 0) - (ma.quality_score || 0));
      }
      if (sort === "factors") {
        return (b.factors_hit || 0) - (a.factors_hit || 0);
      }
      if (sort === "day") {
        return (mb.day_chg_pct || 0) - (ma.day_chg_pct || 0);
      }
      if (sort === "rvol") {
        return (mb.rvol || 0) - (ma.rvol || 0);
      }
      return rankScore(b) - rankScore(a);
    });
    return list;
  }

  function selectSymbol(sym, data) {
    selectedSymbol = sym;
    let row = findRow(sym, data);
    if (row && row.metrics) {
      renderDetail(row);
    } else {
      // Unknown to current hot list / cache → fetch on-demand full analysis
      // (the backend /api/symbol now runs the complete factor engine for any ticker)
      detailTitle.textContent = sym;
      detailEl.innerHTML = `<div class="detail-empty"><p>Analyzing ${escapeHtml(sym)} with the full engine…</p><p class="muted">Fetching 6mo history, fundamentals, running 100+ factors, news intel, etc.</p></div>`;
      fetchFullSymbol(sym).then(full => {
        renderDetail(full);
        // also re-render hot so the new row can participate in filters if user wants
        renderHot(lastData);
      }).catch(err => {
        detailEl.innerHTML = `<div class="detail-empty"><p>Could not analyze ${escapeHtml(sym)}</p><p class="muted">${escapeHtml(err.message || err)}</p></div>`;
      });
    }
    detailTitle.textContent = sym;
    if (activeTab !== "hot") {
      document.querySelector('.tab[data-tab="hot"]')?.click();
    }
    renderHot(data);
    renderEarnings(data);
    document.querySelector(".sticky-detail")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderStats(data) {
    const s = data?.stats || {};
    const fullScan = (s.last_price_scan || s.last_price_tick || "—").slice(11, 19);
    const quickPx = (s.last_quick_price || "—").slice(11, 19);
    const scanning = s.scan_in_progress;
    if (livePill) {
      if (scanning) {
        livePill.hidden = false;
        livePill.className = "live-pill scanning";
        livePill.textContent = `Scanning ${s.scan_batch || "?"}/${s.scan_batches_total || "?"}`;
      } else {
        livePill.hidden = true;
      }
    }
    // Compute live gauges from hot for conviction / S+
    const hotPool = getHotPool(data || {});
    const highConv = hotPool.filter(r => rankScore(r) >= 70).length;
    const smCount = hotPool.filter(r => hasSmartMoneySignal(r)).length;
    const newsBurst = (data?.news || []).length;
    const earningsCnt = (data?.earnings || []).length;
    const scanSecs = (() => {
      const t = s.last_price_scan || s.last_price_tick;
      return t ? t.slice(11, 19) : "—";
    })();
    const health = (() => {
      const got = Number(s.last_full_price_scan_result_count ?? s.last_price_batch_result_count ?? 0);
      const tried = Number(s.last_full_price_scan_attempted ?? s.last_price_batch_attempted ?? 0);
      if (tried > 0) return `${Math.round((got / tried) * 1000) / 10}%`;
      return s.symbols_tracked ? `${s.symbols_tracked}` : "—";
    })();
    // Update topbar scan pill
    const scanPillVal = document.getElementById("scanPillValue");
    if (scanPillVal) scanPillVal.textContent = scanning ? "live" : scanSecs;

    const statCard = (stat, label, value, sub, subColor, accent, iconBg, iconPath) => `
      <div class="stat-card clickable" data-stat="${stat}" title="Click to filter / open">
        <span class="accent" style="background:${accent}"></span>
        <div class="stat-head">
          <span class="label">${label}</span>
          <span class="stat-icon" style="background:${iconBg};color:${accent}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="${iconPath}"/></svg>
          </span>
        </div>
        <div class="value">${value}</div>
        <div class="sub" style="color:${subColor}">${sub}</div>
      </div>`;

    statsBar.innerHTML =
      statCard("reset", "Hot Movers", hotPool.length, `${highConv} high-conviction`, "#34D77F", "#38BDF8", "rgba(56,189,248,.12)", "M3 17l6-6 4 4 8-8M21 7v6") +
      statCard("whale", "S+ / Smart Money", smCount, "named investor signals", "#E5C158", "#FACC15", "rgba(250,204,21,.12)", "M3 7l4 12h10l4-12-5 4-4-7-4 7z") +
      statCard("news", "News Activity", newsBurst, "headlines tracked", "#7DB4F7", "#60A5FA", "rgba(96,165,250,.12)", "M4 5h16v14H4zM8 9h8M8 13h5") +
      statCard("earnings", "Earnings", earningsCnt, "reporting soon", "#B49BF5", "#8B5CF6", "rgba(139,92,246,.12)", "M3 4h18v17H3zM3 9h18M8 2v4M16 2v4") +
      statCard("edge", "Scan Health", health, scanning ? `scanning ${s.scan_batch || "?"}/${s.scan_batches_total || "?"}` : "live coverage", "#E8B873", "#22C55E", "rgba(34,197,94,.12)", "M3 12h4l2.5 7 5-14L17 12h4");
    bindHelp(statsBar);

    // Quick filter actions from stats
    statsBar.querySelectorAll(".stat-card.clickable").forEach(card => {
      card.addEventListener("click", () => {
        const st = card.dataset.stat;
        if (st === "whale") {
          whaleOnly = !whaleOnly;
          const chip = document.getElementById("whaleOnlyChip");
          if (chip) { chip.classList.toggle("active", whaleOnly); chip.dataset.whale = whaleOnly ? "1" : "0"; }
          renderHot(lastData);
        } else if (st === "highconv") {
          // temporary earlyOnly + high filter via search hint
          const q = symbolSearch; if (q) q.value = "";
          earlyOnly = true;
          const eChip = document.getElementById("earlyOnlyChip");
          if (eChip) { eChip.classList.add("active"); eChip.dataset.early = "1"; }
          renderHot(lastData);
        } else if (st === "sectors") {
          document.querySelector('.tab[data-tab="sectors"]')?.click();
        } else if (st === "news") {
          document.querySelector('.tab[data-tab="news"]')?.click();
        } else if (st === "earnings") {
          document.querySelector('.tab[data-tab="earnings"]')?.click();
        } else if (st === "edge") {
          // Prominent entry to the Backtest Edge / Historical Performance section
          document.querySelector('.tab[data-tab="guide"]')?.click();
          loadEdgeStats();
        } else if (st === "reset") {
          earlyOnly = false;
          whaleOnly = false;
          marketFilter = "all";
          sectorFilter = null;
          if (symbolSearch) symbolSearch.value = "";
          document.querySelectorAll(".chip[data-market]").forEach(b => b.classList.remove("active"));
          document.querySelector('.chip[data-market="all"]')?.classList.add("active");
          const eChip = document.getElementById("earlyOnlyChip"); if (eChip) { eChip.classList.remove("active"); eChip.dataset.early = "0"; }
          const wChip = document.getElementById("whaleOnlyChip"); if (wChip) { wChip.classList.remove("active"); wChip.dataset.whale = "0"; }
          renderHot(lastData);
        }
      });
    });
  }

  function rowFlashClass(symbol, rank, score) {
    const prev = prevRankBySymbol.get(symbol);
    prevRankBySymbol.set(symbol, { rank, score });
    if (prev === undefined) return "row-new";
    if (rank < prev.rank) return "row-up";
    if (rank > prev.rank) return "row-down";
    if (score > prev.score + 0.5) return "row-up";
    if (score < prev.score - 0.5) return "row-down";
    return "";
  }

  function renderHot(data) {
    lastData = data;
    ingestHotRows(data);
    const pool = getHotPool(data);
    const rows = filterAndSort(pool).slice(0, DISPLAY_LIMIT);
    const marketLabel =
      marketFilter === "all" ? "all markets" : marketFilter.toUpperCase();
    const poolTotal = pool.length;
    hotCount.textContent = `Showing ${rows.length} of ${poolTotal} hot (${marketLabel}) · live sort`;
    if (hotHint) {
      if (rows.length === 0 && pool.length > 0) {
        const activeExtras = [];
        if (earlyOnly) activeExtras.push("Early buys only");
        if (whaleOnly) activeExtras.push("Whale/Politician");
        hotHint.textContent = `No ${marketLabel} names match the current filters (${activeExtras.join(" + ") || "search/sector"}). Click the active filter chip(s) above or the "Hot" stat card to clear.`;
      } else if (sectorFilter) {
        hotHint.textContent = `Filtered to sector: ${sectorFilter}. Clear via badge above table.`;
      } else {
        hotHint.textContent = "Ranking updates automatically during each scan batch. Stocks leave the list when score drops below threshold.";
      }
    }

    // Prune rank map for symbols no longer in list
    const visible = new Set(rows.map((r) => r.symbol));
    for (const sym of prevRankBySymbol.keys()) {
      if (!visible.has(sym)) prevRankBySymbol.delete(sym);
    }

    hotBody.innerHTML = rows
      .map((r, idx) => {
        const m = r.metrics || {};
        const day = Number(m.day_chg_pct ?? 0);
        const dayCls = day >= 0 ? "pos" : "neg";
        const sel = r.symbol === selectedSymbol ? "selected" : "";
        const flash = rowFlashClass(r.symbol, idx, rankScore(r));
        const buy = Number(m.buy_score ?? r.score ?? 0);
        const qual = m.quality_score ?? "—";
        const sym = String(r.symbol || "");
        const isIndia = (r.market || m.market || "").toLowerCase() === "india" || /\.(NS|BO)$/i.test(sym);
        const mkt = isIndia ? "in" : "us";
        const cur = isIndia ? "₹" : "$";
        const price = m.price != null ? `${cur}${m.price}` : "";
        const watched = watchlist.some(w => w.symbol === r.symbol) ? "★" : "☆";

        // --- Buy score tier ---
        const tier = buy >= 90 ? ["buy-sp", "S+"] : buy >= 80 ? ["buy-a", "A"]
          : buy >= 70 ? ["buy-b", "B"] : buy >= 55 ? ["buy-c", "C"] : ["buy-d", "D"];

        // --- Catalyst badges ---
        const sm = m.smart_money;
        const cats = [];
        if (sm?.hits?.length || smartMoneyBadges(r)) {
          const sTier = (sm?.hits?.[0]?.tier || "").toUpperCase();
          if (sTier.includes("S") || buy >= 90) cats.push('<span class="cat-badge sp clickable" data-whale-sym="' + attrEsc(sym) + '">S+</span>');
          else cats.push('<span class="cat-badge sm clickable" data-whale-sym="' + attrEsc(sym) + '">Smart Money</span>');
        }
        if ((r.news && r.news.length) || m.news_count || (r.alerts || []).some(a => /news|headline/i.test(a)))
          cats.push('<span class="cat-badge news">News</span>');
        if (r.earnings || m.earnings_pre || r.earnings_soon || m.days_until_earnings != null)
          cats.push('<span class="cat-badge earn">Earnings</span>');
        if (m.is_extended) cats.push('<span class="cat-badge risk" title="Near 52w high / extended">Extended</span>');
        if (r.discovered) cats.push('<span class="cat-badge sm" title="From discovery scan">DISC</span>');
        if (r.full_exhaustive) cats.push('<span class="cat-badge news" title="From full exhaustive scan">FULL</span>');
        cats.push(factorPill(r));
        const reason = escapeHtml(sm?.primary_alert || (r.alerts || [])[0] || m.sector || m.name || "");

        // --- Rel vol ---
        const rvol = m.rvol;
        const rvCls = rvol >= 2.5 ? "hi" : rvol >= 1.5 ? "mid" : "lo";

        // --- Confidence ---
        const c = m.confidence_score;
        const confHtml = c == null ? '<span class="muted">—</span>'
          : `<span class="conf ${c >= 80 ? "hi" : c >= 65 ? "mid" : "lo"}">${c}</span>`;

        return `<tr class="${sel} ${flash}" data-symbol="${attrEsc(sym)}">
          <td class="col-sym">
            <div class="sym">
              <span class="mkt ${mkt}">${mkt.toUpperCase()}</span>
              <button class="tiny tiny-watch" data-watch="${attrEsc(sym)}" title="${watched === "★" ? "Remove from My List" : "Add to My List"}">${watched}</button>
              <button class="tiny" data-paper="${attrEsc(sym)}" title="One-click paper buy into Portfolio">📁</button>
              <span class="sym-main">
                <span class="sym__ticker">${escapeHtml(sym)}</span><span class="sym__price ${dayCls}">${price}</span>
                <br><span class="sym__name">${escapeHtml(m.name || m.sector || mkt.toUpperCase())}</span>
              </span>
            </div>
          </td>
          <td class="col-trend">${sparklineSvg(r.sparkline, 88, 30)}</td>
          <td class="col-cats">
            <div class="cats__badges">${cats.join("")}</div>
            ${reason ? `<div class="cats__reason">${reason}</div>` : ""}
          </td>
          <td class="col-rvol"><span class="rvol ${rvCls}">${rvol != null ? rvol + "×" : "—"}</span></td>
          <td class="col-conf">${confHtml}</td>
          <td class="col-day"><span class="day ${dayCls}">${day > 0 ? "▲ +" : day < 0 ? "▼ " : ""}${day}%</span></td>
          <td class="col-buy">
            <div class="buy ${tier[0]} clickable" data-act="factors" title="Buy score — click for weighted factor breakdown">
              <span class="buy__meta"><span class="buy__tier">${tier[1]}</span><div class="buy__q">Q ${qual}</div></span>
              <span class="buy__pill"><span>${Math.round(buy)}</span></span>
            </div>
          </td>
        </tr>`;
      })
      .join("");

    hotBody.querySelectorAll("tr").forEach((tr) => {
      tr.addEventListener("click", (ev) => {
        selectSymbol(tr.dataset.symbol, data);
      });
    });
    hotBody.querySelectorAll(".factor-pill").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        openFactorModal(btn.dataset.symbol, data);
      });
    });
    hotBody.querySelectorAll(".tiny-watch").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const sym = btn.dataset.watch;
        const row = findRow(sym, data);
        if (watchlist.some(w => w.symbol === sym)) removeFromWatch(sym);
        else addToWatch(sym, row || {symbol: sym});
        renderHot(data);
        if (activeTab === "watch") renderWatch(data);
      });
    });
    hotBody.querySelectorAll("[data-paper]").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const sym = btn.dataset.paper;
        addToPortfolio(sym, {qty: 100}).catch(err => alert("Paper buy failed: " + (err.message || err)));
      });
    });
    // New: score / day / rvol / spark clicks → factors or re-analyze
    hotBody.querySelectorAll("[data-act]").forEach(el => {
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const sym = el.closest("tr")?.dataset.symbol;
        const act = el.dataset.act;
        if (act === "factors") openFactorModal(sym, data);
        else if (act === "reanalyze" && sym) {
          fetchFullSymbol(sym).then(full => { renderDetail(full); renderHot(data); }).catch(()=>{});
        } else if (act === "select" && sym) {
          selectSymbol(sym, data);
        }
      });
    });
    // Whale badges in table now open rich details
    hotBody.querySelectorAll("[data-whale-sym]").forEach(el => {
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const sym = el.dataset.whaleSym;
        const r = findRow(sym, data);
        showSmartMoneyDetails(sym, r || {symbol: sym});
      });
    });
  }

  function renderDetail(row) {
    if (!row || !row.metrics) {
      detailEl.innerHTML = `<div class="detail-empty"><p>No scan data yet for ${selectedSymbol || ""}</p><p class="muted">Wait for next price scan (~90s)</p></div>`;
      return;
    }
    const m = row.metrics || {};
    const { hit, total } = factorsDisplay(row);
    const alerts = (row.alerts || []).map((a) => `<li>${escapeHtml(a)}</li>`).join("");
    const passed = (row.factor_breakdown || []).filter((x) => x.status === "pass");
    const factorChips = passed
      .slice(0, 12)
      .map(
        (f) =>
          `<span class="chip-pass" title="${escapeHtml(f.description)}">${escapeHtml(f.name)}</span>`
      )
      .join("");
    const more = passed.length > 12 ? `<span class="chip-more">+${passed.length - 12} more</span>` : "";

    const smBlock = m.smart_money?.hits?.length
      ? `<div class="smart-money-block">${m.smart_money.hits
          .map(
            (h) =>
              `<span class="whale-badge whale-${escapeHtml((h.kind || "").replace("_", "-"))}" title="${escapeHtml(h.headline || "")}">${escapeHtml(h.name)} <small>(${escapeHtml(h.tier || "S")})</small></span>`
          )
          .join("")}</div>`
      : "";

    const isAdHoc = row.ad_hoc || m.ad_hoc;
    const thesis = generateThesis(row);
    const isWatched = watchlist.some(w => w.symbol === row.symbol);
    const thesisHtml = `
      <div class="thesis-block">
        <div class="thesis-head"><strong>${escapeHtml(thesis.archetype)}</strong> <button class="tiny" data-act="watch">${isWatched ? "✓ Watched" : "★ Watch"}</button> <button class="tiny" data-act="paper">📁 Paper</button> <button class="tiny" data-act="thesis">Copy thesis</button></div>
        <ul class="thesis-bullets">${thesis.bullets.map(b => `<li>${escapeHtml(b)}</li>`).join("")}</ul>
        ${thesis.risks.length ? `<div class="risks"><strong>Risks:</strong> ${thesis.risks.map(r=>escapeHtml(r)).join(" · ")}</div>` : ""}
      </div>`;

    // tiny position sizer (local only)
    const sizerHtml = `
      <div class="sizer">
        <span class="muted">Position sizer (local):</span>
        <input type="number" id="acctSize" value="50000" style="width:82px" /> acct
        <input type="number" id="riskPct" value="1.0" step="0.1" style="width:56px" /> % risk
        <span id="sizerOut" class="muted"></span>
      </div>`;

    const pn = buildPositivesAndNegatives(row);
    const verdict = getConvictionVerdict(row);
    const posHtml = pn.positives.length ? `<div class="positives"><h4>✓ Positives (engine drivers)</h4><ul>${pn.positives.map(p=>`<li>${escapeHtml(p)}</li>`).join("")}</ul></div>` : "";
    const negHtml = pn.negatives.length ? `<div class="negatives"><h4>✗ Risks / Negatives (penalties & gaps)</h4><ul>${pn.negatives.map(n=>`<li>${escapeHtml(n)}</li>`).join("")}</ul></div>` : "";
    const verdictHtml = `<div class="conviction-verdict ${verdict.cls}">${escapeHtml(verdict.text)}</div>`;

    // Make whale block itself clickable for rich details
    const clickableSmBlock = m.smart_money?.hits?.length || hasSmartMoneySignal(row)
      ? `<div class="smart-money-block clickable" data-whale-sym="${attrEsc(row.symbol)}" title="Click for full whale / politician / FII details and why S+ matters">${smBlock}</div>`
      : "";

    detailEl.innerHTML = `<div class="detail">
      <h3 class="clickable" data-act="factors" title="Click for full factors checklist">${row.symbol} ${isAdHoc ? '<span class="chip" style="font-size:0.65rem; padding:1px 6px; vertical-align:middle;">ad-hoc deep analysis</span>' : ''}</h3>
      <div class="meta-line clickable" data-act="factors" title="Click for full analysis">${escapeHtml(m.name || "")} · ${escapeHtml(m.sector || "")} · ${escapeHtml((row.market || m.market || "—").toUpperCase())}</div>
      ${clickableSmBlock}
      <!-- Super prominent immediate smart money display: exact name + how good (quality) -->
      ${(() => {
        const sm = m.smart_money;
        if (sm && sm.hits && sm.hits.length) {
          const hit = sm.hits[0];
          const q = hit.quality ? ` — ${escapeHtml(hit.quality)}` : "";
          return `<div style="background:#fef3c7;border:2px solid #f59e0b;border-radius:6px;padding:0.4rem 0.6rem;margin:0.3rem 0;font-weight:700;color:#92400e">🚨 BIG INVESTOR: ${escapeHtml(hit.name)}${q} (S+ tier — heavy weight in engine)</div>`;
        }
        return "";
      })()}
      <div class="detail-score-row">
        Buy <strong class="big-score clickable" data-act="factors" title="Click to see exactly which factors drove this buy score (weighted) and the full checklist">${m.buy_score ?? row.score}</strong>
        <span class="qual-pill clickable" data-act="factors" title="Quality score = broad checklist health (fundamentals + valuation + technicals). Click for breakdown">${m.quality_score ?? "—"}</span>
        ${confPill(m.confidence_score)}
        ${m.is_extended ? '<span class="ext-badge">Extended — late chase</span>' : ""}
        <button type="button" class="factor-pill detail-factor-btn" data-symbol="${attrEsc(row.symbol)}" title="Open the complete 100+ factor pass/fail with weights and tiers">${hit}/${total} factors</button>
      </div>
      ${verdictHtml}
      ${posHtml}
      ${negHtml}
      ${thesisHtml}
      ${sizerHtml}
      ${m.pct_52w_range != null ? `<div class="meta-line">52w range position: ${m.pct_52w_range}% · entry checks: ${m.entry_factors ?? 0} <span class="muted">(higher = more room before extension penalty)</span></div>` : ""}
      <div class="spark-large" title="Click sparkline to re-analyze this symbol with latest data">${sparklineSvg(row.sparkline, 300, 72)}</div>
      <div class="meta-line clickable" data-act="factors" title="Core price/volume snapshot used by the algorithm">$${m.price} · Day ${m.day_chg_pct}% · 5d ${m.ret5d_pct}% · RVOL ${m.rvol}x · RSI ${m.rsi ?? "—"}</div>
      <div class="meta-line">P/E ${m.pe ?? "—"} · P/B ${m.pb ?? "—"} · FCF ${m.fcf ? "✓" : "—"} · 52w pos ${m.pct_52w_range ?? "—"}%</div>
      <!-- Simple DMA/EMA support/resistance levels (technical signals that work a lot - shown plainly) -->
      ${(() => {
        const t = m.key_ma_support_res || (m.tech_levels ? {levels: m.tech_levels, signal: m.tech_signal} : null);
        if (!t || !t.levels) return "";
        const l = t.levels || {};
        let txt = Object.entries(l).filter(([k]) => !k.includes("dist") && !k.includes("pct")).map(([k,v]) => `${k} ~${v}`).join(" · ");
        const sig = t.signal || m.tech_signal || "";
        const sigHelp = sig.includes("support") || sig.includes("bull") ? " — bullish support (simple buy zone)" : sig.includes("near") ? " — watch level for bounce/rejection" : sig.includes("bear") ? " — below key MAs (caution)" : "";
        return txt ? `<div class="meta-line" style="background:rgba(56,189,248,0.06);padding:2px 6px;border-radius:3px;font-size:0.78rem"><strong>Key DMA/EMA Levels:</strong> ${txt}${sigHelp} <span class="muted">(proven simple signals)</span></div>` : "";
      })()}
      ${alerts ? `<ul class="alerts">${alerts}</ul>` : ""}
      <p class="muted section-label">Top passed checks (click factors button for all + weights)</p>
      <div class="factor-chips">${factorChips || '<span class="muted">None yet</span>'}${more}</div>
    </div>`;

    detailEl.querySelector(".detail-factor-btn")?.addEventListener("click", () => {
      openFactorModal(row.symbol, lastData);
    });

    // New conviction surfaces + everything clickable
    detailEl.querySelectorAll(".clickable").forEach(el => {
      el.addEventListener("click", (e) => {
        const act = el.dataset.act;
        if (act === "factors" || el.classList.contains("big-score") || el.classList.contains("qual-pill")) {
          openFactorModal(row.symbol, lastData);
        }
      });
    });

    detailEl.querySelector('[data-whale-sym]')?.addEventListener("click", () => {
      showSmartMoneyDetails(row.symbol, row);
    });

    detailEl.querySelector(".spark-large")?.addEventListener("click", () => {
      fetchFullSymbol(row.symbol).then(full => renderDetail(full)).catch(()=>{});
    });

    // Extra action row buttons
    const extraBar = detailEl.querySelector('div[style*="margin-top:0.4rem"]');
    extraBar?.querySelector('[data-act="factors"]')?.addEventListener("click", () => openFactorModal(row.symbol, lastData));
    extraBar?.querySelector('[data-act="whale"]')?.addEventListener("click", () => showSmartMoneyDetails(row.symbol, row));
    extraBar?.querySelector('[data-act="thesis"]')?.addEventListener("click", () => copyThesis(row.symbol, row));
    extraBar?.querySelector('[data-act="watch"]')?.addEventListener("click", (e) => {
      if (isWatched) removeFromWatch(row.symbol); else addToWatch(row.symbol, row);
      renderDetail(row);
      renderWatch(lastData);
    });

    // thesis / watch actions (legacy thesis block)
    const thesisBlock = detailEl.querySelector(".thesis-block");
    thesisBlock?.querySelector('[data-act="watch"]')?.addEventListener("click", (e) => {
      if (isWatched) removeFromWatch(row.symbol); else addToWatch(row.symbol, row);
      renderDetail(row); // refresh
      renderWatch(lastData);
    });
    thesisBlock?.querySelector('[data-act="thesis"]')?.addEventListener("click", () => copyThesis(row.symbol, row));
    thesisBlock?.querySelector('[data-act="paper"]')?.addEventListener("click", () => {
      addToPortfolio(row.symbol, {qty: 100}).catch(err => alert("Paper buy failed: " + (err.message || err)));
    });

    // live sizer calc
    const acct = detailEl.querySelector("#acctSize");
    const rp = detailEl.querySelector("#riskPct");
    const out = detailEl.querySelector("#sizerOut");
    function recalc() {
      const a = parseFloat(acct?.value || "0");
      const r = parseFloat(rp?.value || "0") / 100;
      const price = parseFloat(m.price || 0);
      if (!a || !r || !price) { out.textContent = ""; return; }
      // crude: use recent ATR proxy from spark range or 3% default
      const hist = row.sparkline || [];
      let vol = 0.03;
      if (hist.length > 5) {
        const hi = Math.max(...hist), lo = Math.min(...hist);
        vol = Math.max(0.01, Math.min(0.12, (hi - lo) / ((hi+lo)/2 || 1)));
      }
      const riskAmt = a * r;
      const shares = Math.floor(riskAmt / (price * vol));
      out.textContent = `~${shares} sh @ ~${(riskAmt).toFixed(0)} risk (vol~${(vol*100).toFixed(1)}%)`;
    }
    acct?.addEventListener("input", recalc);
    rp?.addEventListener("input", recalc);
    setTimeout(recalc, 50);
  }

  function renderEarnings(data) {
    const rows = data?.earnings || [];
    earningsCount.textContent = rows.length ? `(${rows.length})` : "(loading…)";
    earningsBody.innerHTML = rows
      .slice(0, 60)
      .map((e) => {
        const d = e.days_until;
        let badge = "";
        if (d === 0) badge = '<span class="day-badge today">TODAY</span>';
        else if (d != null && d > 0) badge = `<span class="day-badge soon">${d}d</span>`;
        else if (e.from_news) badge = '<span class="day-badge soon" style="background:#334">NEWS MENTION</span>';
        else badge = '<span class="day-badge soon">—</span>';
        const day = e.day_chg_pct;
        const cls = day > 0 ? "pos" : day < 0 ? "neg" : "";
        const eps = e.eps_avg != null ? Number(e.eps_avg).toFixed(2) : "—";
        const sel = e.symbol === selectedSymbol ? "selected" : "";
        const dateCell = e.from_news ? (e.news_title || "Recent news") : (e.earnings_date || "").slice(0, 10);
        return `<tr class="${sel}" data-symbol="${attrEsc(e.symbol)}">
          <td><strong>${e.symbol}</strong></td>
          <td>${dateCell}</td>
          <td>${badge}</td>
          <td>${eps}</td>
          <td>${e.score != null ? `<span class="score-pill">${e.score}</span>` : "—"}</td>
          <td class="${cls}">${day != null ? (day > 0 ? "+" : "") + day + "%" : "—"}</td>
        </tr>`;
      })
      .join("");

    earningsBody.querySelectorAll("tr").forEach((tr) => {
      tr.addEventListener("click", () => selectSymbol(tr.dataset.symbol, data));
    });
  }

  function renderNews(data) {
    const items = data?.news || [];
    newsList.innerHTML =
      items.length === 0
        ? '<li class="muted">Loading headlines…</li>'
        : items
            .slice(0, 50)
            .map((n) => {
              const tags = (n.symbols || []).slice(0, 5).join(", ");
              return `<li>
          <a href="${n.link}" target="_blank" rel="noopener">${escapeHtml(n.title)}</a>
          <div class="meta">${escapeHtml(n.source)} · ${(n.published_at || "").slice(0, 16)}</div>
          ${tags ? `<div class="tags">${escapeHtml(tags)}</div>` : ""}
        </li>`;
            })
            .join("");
  }

  async function renderWatch(data) {
    const tbody = document.querySelector("#watchTable tbody");
    const countEl = document.getElementById("watchCount");
    if (!tbody) return;
    if (!watchlist.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="muted">Your watchlist is empty (server + local fallback). Use the search box to Analyze any ticker, then click ★ Watch or ★ Watch + Alert in the detail panel, or the ☆ / +A in Hot rows. Server rules (e.g. buy_score&gt;65 AND rvol&gt;2) auto-add high-conviction names on match.</td></tr>`;
      if (countEl) countEl.textContent = "0 symbols";
      return;
    }
    const htmlParts = [];
    for (const w of watchlist) {
      let row = findRow(w.symbol, data) || symbolCache.get(w.symbol);
      if (!row || !row.metrics) {
        // fire non-blocking refresh for full current engine data
        fetch(`/api/symbol/${encodeURIComponent(w.symbol)}`).then(r=>r.json()).then(full => {
          if (full && !full.error) {
            mergeScanRow(w.symbol, full);
            if (activeTab === "watch") renderWatch(lastData);
          }
        }).catch(()=>{});
      }
      const m = (row && row.metrics) || {};
      const buy = w.lastBuy || m.buy_score || row?.score || w.addedScore || "—";
      const qual = w.lastQuality || m.quality_score || "—";
      const fh = row ? (row.factors_hit ?? m.factors_hit ?? "—") : "—";
      const ft = row ? (row.factors_total ?? m.factors_total ?? "—") : "—";
      const added = w.addedAt ? new Date(w.addedAt).toLocaleDateString() : "—";
      const srvBadge = w.server || w.notes ? ` <span class="muted" style="font-size:0.65rem;color:#eab308" title="server persisted">srv</span>` : "";
      htmlParts.push(`<tr data-symbol="${attrEsc(w.symbol)}">
        <td><strong>${w.symbol}</strong>${srvBadge}<br><span class="muted" style="font-size:0.7rem">added ${added} @ ${w.addedScore}</span></td>
        <td><span class="score-pill">${buy}</span></td>
        <td><span class="qual-pill">${qual}</span></td>
        <td>${fh}/${ft}</td>
        <td><span class="muted" style="font-size:0.75rem">last ${w.lastScore || buy}</span></td>
        <td>
          <button class="tiny" data-act="analyze">Analyze</button>
          <button class="tiny" data-act="watch-alert" title="Re-add with alert monitoring">+Alert</button>
          <button class="tiny danger" data-act="remove">Remove</button>
          <button class="tiny" data-act="paper">📁</button>
        </td>
      </tr>`);
    }
    tbody.innerHTML = htmlParts.join("");
    if (countEl) countEl.textContent = `${watchlist.length} symbols`;
    tbody.querySelectorAll("tr").forEach(tr => {
      tr.addEventListener("click", (e) => {
        const sym = tr.dataset.symbol;
        if (e.target.dataset.act === "remove") {
          removeFromWatch(sym); return;
        }
        if (e.target.dataset.act === "watch-alert") {
          const row = findRow(sym, data) || {symbol: sym};
          addToWatchWithAlert(sym, row);
          renderWatch(data);
          return;
        }
        if (e.target.dataset.act === "paper") {
          addToPortfolio(sym, {qty: 100}).catch(err => alert("Paper buy failed: " + (err.message || err)));
          return;
        }
        if (e.target.dataset.act === "analyze" || !e.target.dataset.act) {
          document.querySelector('.tab[data-tab="hot"]')?.click();
          fetchFullSymbol(sym).then(full => { renderDetail(full); openFactorModal(sym, data); }).catch(()=>{});
        }
      });
    });
  }

  /* ========== PORTFOLIO / PAPER JOURNAL (first-class, server-backed, ties to engine thesis) ========== */

  async function fetchPortfolio() {
    try {
      const res = await fetch("/api/portfolio");
      if (!res.ok) throw new Error("portfolio fetch failed");
      portfolioData = await res.json();
      // also fetch journal for list
      const jres = await fetch("/api/journal?limit=60");
      if (jres.ok) {
        const jd = await jres.json();
        journalData = jd.journal || [];
      }
      return portfolioData;
    } catch (e) {
      console.warn("portfolio fetch", e);
      portfolioData = {positions: [], stats: {}, count: 0};
      journalData = [];
      return portfolioData;
    }
  }

  async function renderPortfolio(force = false) {
    const sumEl = document.getElementById("portfolioSummary");
    const tbody = document.querySelector("#portfolioTable tbody");
    const countEl = document.getElementById("portfolioCount");
    const jEl = document.getElementById("journalList");
    if (!sumEl || !tbody) return;
    if (!portfolioData || force) {
      await fetchPortfolio();
    }
    const p = portfolioData || {positions: [], stats: {}};
    const stats = p.stats || {};
    sumEl.innerHTML = `
      <div class="stat-row" style="display:flex;gap:0.6rem;flex-wrap:wrap">
        <div class="stat-card"><span class="label">Open positions</span><span class="value">${p.count || 0}</span></div>
        <div class="stat-card"><span class="label">Win rate (closed)</span><span class="value">${stats.winrate ?? 0}%</span></div>
        <div class="stat-card"><span class="label">Realized PnL</span><span class="value ${ (stats.total_realized_pnl||0)>=0 ? 'pos':'neg'}">${stats.total_realized_pnl ?? 0}</span></div>
        <div class="stat-card"><span class="label">Paper equity (entry + est open)</span><span class="value">$${stats.total_paper_value_est ?? stats.paper_equity_entry ?? 0}</span></div>
        <div class="stat-card"><span class="label">Open PnL est</span><span class="value ${ (stats.open_pnl_est||0)>=0 ? 'pos':'neg'}">${stats.open_pnl_est ?? 0}</span></div>
      </div>
    `;
    if (countEl) countEl.textContent = `${p.count || 0} open`;

    // positions table w/ live + actions + editable notes
    const rowsHtml = (p.positions || []).map(pos => {
      const ep = pos.entry_price ? Number(pos.entry_price).toFixed(2) : "—";
      const buy = pos.current_buy != null ? pos.current_buy : "—";
      const qual = pos.current_qual != null ? pos.current_qual : "—";
      const pnl = pos.est_pnl != null ? `${pos.est_pnl} (${pos.est_pnl_pct}%)` : "—";
      const pnlCls = (pos.est_pnl||0) >= 0 ? "pos" : "neg";
      const slt = [pos.sl ? `SL ${pos.sl}` : "", pos.target ? `T ${pos.target}` : ""].filter(Boolean).join(" / ") || "—";
      const notesVal = (pos.notes || "").replace(/"/g, '&quot;');
      return `<tr data-symbol="${attrEsc(pos.symbol)}" data-id="${pos.id || ''}">
        <td><strong class="clickable" data-act="detail">${escapeHtml(pos.symbol)}</strong><br><span class="muted" style="font-size:0.7rem">entry @${ep} / ${pos.entry_score ?? ''}</span></td>
        <td><span class="muted">${ep}</span></td>
        <td><span class="score-pill">${buy}</span></td>
        <td><span class="qual-pill">${qual}</span></td>
        <td>${pos.qty ?? "—"}</td>
        <td class="${pnlCls}">${pnl}</td>
        <td class="muted" style="font-size:0.75rem">${slt}</td>
        <td><input type="text" class="port-notes" data-sym="${attrEsc(pos.symbol)}" value="${notesVal}" style="width:140px;font-size:0.78rem" placeholder="thesis / notes" /></td>
        <td>
          <button class="tiny" data-act="analyze">Analyze</button>
          <button class="tiny" data-act="close">Close</button>
          <button class="tiny" data-act="detail">Detail</button>
        </td>
      </tr>`;
    }).join("") || `<tr><td colspan="9" class="muted">No open paper positions. Use "📁 Log Paper Buy" or click 📁 in Hot/Detail/Watch rows.</td></tr>`;

    tbody.innerHTML = rowsHtml;

    // wire row clicks + actions + live note save on blur
    tbody.querySelectorAll("tr[data-symbol]").forEach(tr => {
      const sym = tr.dataset.symbol;
      tr.addEventListener("click", (e) => {
        if (e.target.closest("input,button")) return;
        const act = e.target.closest("[data-act]")?.dataset.act;
        if (act === "detail" || act === "analyze" || !act) {
          document.querySelector('.tab[data-tab="hot"]')?.click();
          fetchFullSymbol(sym).then(full => { renderDetail(full); openFactorModal(sym, lastData); }).catch(()=>{});
        }
      });
      tr.querySelectorAll("[data-act]").forEach(btn => {
        btn.addEventListener("click", async (ev) => {
          ev.stopPropagation();
          const a = btn.dataset.act;
          if (a === "analyze" || a === "detail") {
            document.querySelector('.tab[data-tab="hot"]')?.click();
            const full = await fetchFullSymbol(sym); renderDetail(full); openFactorModal(sym, lastData);
          } else if (a === "close") {
            if (confirm(`Close paper position in ${sym} and record realized PnL?`)) {
              try {
                await closePosition(sym);
                await renderPortfolio(true);
              } catch(err){ alert("Close failed: "+err); }
            }
          }
        });
      });
      // editable notes persist on server
      const inp = tr.querySelector(".port-notes");
      if (inp) {
        inp.addEventListener("blur", async () => {
          const val = inp.value.trim();
          try {
            await fetch(`/api/position/${encodeURIComponent(sym)}/update`, {
              method: "POST", headers: {"Content-Type":"application/json"},
              body: JSON.stringify({notes: val || null})
            });
          } catch(_) {}
        });
        inp.addEventListener("keydown", e => { if (e.key==="Enter") inp.blur(); });
      }
    });

    // render journal list w/ thesis + outcome (insightful)
    if (jEl) {
      jEl.innerHTML = (journalData || []).length ? (journalData.map(j => {
        const d = (j.created_at || "").slice(0,16).replace("T"," ");
        const pnl = j.outcome_pnl != null ? `<span class="${j.outcome_pnl>=0?'pos':'neg'}">${j.outcome_pnl}</span>` : "";
        const thesis = (j.thesis_pos || j.thesis_neg) ? `<div class="muted" style="font-size:0.7rem;margin-top:1px">+ ${escapeHtml((j.thesis_pos||"").slice(0,90))}<br>− ${escapeHtml((j.thesis_neg||"").slice(0,80))}</div>` : "";
        return `<div class="journal-row" data-symbol="${attrEsc(j.symbol)}" style="padding:0.25rem 0.35rem;border-bottom:1px solid var(--border);cursor:pointer">
          <strong>${escapeHtml(j.symbol)}</strong> <span class="muted">${j.action}</span> @${j.price ?? ""} ×${j.qty ?? ""} ${pnl} <span class="muted" style="font-size:0.7rem">${d}</span>
          ${thesis}
          ${j.notes ? `<div style="font-size:0.72rem;color:#9ca3af">${escapeHtml(j.notes)}</div>` : ""}
        </div>`;
      }).join("")) : '<p class="muted" style="padding:0.4rem">No journal entries yet. Log buys and closes to build your performance + learning history.</p>';

      jEl.querySelectorAll(".journal-row").forEach(row => {
        row.addEventListener("click", () => {
          const sym = row.dataset.symbol;
          document.querySelector('.tab[data-tab="hot"]')?.click();
          fetchFullSymbol(sym).then(full => { renderDetail(full); openFactorModal(sym, lastData); }).catch(()=>{});
        });
      });
    }
  }

  async function addToPortfolio(symbol, extra = {}) {
    symbol = symbol.toUpperCase();
    // Pull best available entry data from cache or force quick analyze (reuse existing)
    let row = findRow(symbol, lastData) || symbolCache.get(symbol);
    let entryPrice = extra.entry_price, entryScore = extra.entry_score;
    if (!entryPrice || !entryScore) {
      if (row && row.metrics) {
        entryPrice = entryPrice || row.metrics.price;
        entryScore = entryScore || row.metrics.buy_score || row.score;
      }
    }
    if (!entryPrice) {
      // fallback: ensure we have fresh via existing pipeline
      try {
        const full = await fetchFullSymbol(symbol);
        entryPrice = entryPrice || (full.metrics && full.metrics.price);
        entryScore = entryScore || full.metrics?.buy_score || full.score;
        row = full;
      } catch(_) {}
    }
    const body = {
      symbol,
      qty: extra.qty || 100,
      notes: extra.notes || (row ? (buildPositivesAndNegatives(row).positives.slice(0,2).join(" · ")) : null),
      sl: extra.sl || null,
      target: extra.target || null,
      entry_price: entryPrice,
      entry_score: entryScore,
    };
    const res = await fetch("/api/portfolio", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body) });
    if (!res.ok) throw new Error(await res.text());
    const created = await res.json();
    portfolioData = {positions: created.positions || [], stats: created.stats || {}, count: created.count || 0};
    // auto switch + immediately render fresh server response so one-click paper buys never show stale portfolio state
    if (activeTab !== "portfolio") {
      document.querySelector('.tab[data-tab="portfolio"]')?.click();
    }
    journalData = (await fetch("/api/journal?limit=60").then(r => r.ok ? r.json() : {journal: []}).catch(() => ({journal: []}))).journal || journalData;
    await renderPortfolio(false);
    return created;
  }

  async function closePosition(symbol) {
    const res = await fetch(`/api/position/${encodeURIComponent(symbol)}/close`, {method: "POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({})});
    if (!res.ok) throw new Error("close failed");
    return res.json();
  }

  // One-click paper trade integration: called from hot rows, detail, watch (reuse watch pattern)
  function makePaperAddButton(sym, row) {
    const b = document.createElement("button");
    b.className = "tiny";
    b.textContent = "📁";
    b.title = "Add as paper position (log buy + entry thesis)";
    b.onclick = (e) => { e.stopPropagation(); addToPortfolio(sym, {qty: 100}).catch(()=>{}); };
    return b;
  }

  async function loadFactorCatalog() {
    try {
      const res = await fetch("/api/factors");
      const data = await res.json();
      if (data.total) {
        factorCatalogTotal = data.total;
        if (factorCountLabel) {
          factorCountLabel.textContent = `US + India · ${data.total} factors · live`;
        }
      }
    } catch (_) {
      /* ignore */
    }
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);

    ws.onopen = () => {
      wsConnected = true;
      connStatus.textContent = "● Live";
      connStatus.className = "pill status-pill live";
    };
    ws.onclose = () => {
      wsConnected = false;
      connStatus.textContent = "Reconnecting…";
      connStatus.className = "pill status-pill down";
      setTimeout(connect, 2000);
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "update" && msg.data) {
          applyUpdate(msg.data);
        } else if (msg.type === "alert" && msg.alert) {
          // Server-pushed personalized rule alert: rich text e.g. with exact "🚨 Investor: ..."
          const a = msg.alert;
          pushAlert(a.rule_type || "server_rule", a.symbol, a.message || a.msg, a.buy_score);
          // Also surface in recent server list
          recentAlerts.unshift({type: a.rule_type||"server", symbol:a.symbol, msg: a.message, ts: a.triggered_at || a.ts || new Date().toISOString(), score: a.buy_score, server:true});
          if (recentAlerts.length > 30) recentAlerts.pop();
          renderAlertBell();
          // If high priority (investor), optionally auto flash
          if ((a.message || "").includes("🚨 Investor") || (a.details && a.details.has_investor)) {
            if (alertBell) {
              alertBell.style.background = "#eab308";
              setTimeout(()=>{ if(alertBell) alertBell.style.background=""; }, 900);
            }
          }
          // sync watches if server may have auto-added
          loadServerWatches().then(() => { if (activeTab === "watch") renderWatch(lastData); });
        }
      } catch (e) {
        console.error(e);
      }
    };
  }

  function applyUpdate(data) {
    const gen = data.scan_generation || 0;
    const fp = hotFingerprint(data);
    const rankingsChanged = gen !== lastScanGeneration || fp !== lastHotFingerprint;
    if (rankingsChanged) {
      lastScanGeneration = gen;
      lastHotFingerprint = fp;
    }
    // === ALERTS & SMART MONEY DETECTION (fires on new high conv or S+ ) ===
    if (data.hot) {
      (data.hot || []).forEach(r => {
        const score = r.buy_score ?? r.score ?? 0;
        const key = r.symbol;
        if (score >= 78 && !seenSmartMoney.has("high:"+key)) {
          seenSmartMoney.add("high:"+key);
          pushAlert("high_score", r.symbol, `Buy score ${Math.round(score)} — strong setup`, score);
        }
        if (hasSmartMoneySignal(r) && !seenSmartMoney.has("sm:"+key)) {
          seenSmartMoney.add("sm:"+key);
          const primary = (r.metrics?.smart_money?.primary_alert) || (r.alerts||[]).find(a=>/LEGEND|WHALE|POLITICIAN/i.test(a)) || "Named smart money buy";
          pushAlert("smart_money", r.symbol, primary, score);
        }
        // pre-earnings + decent score
        if ((r.earnings_soon || (r.metrics && r.metrics.earnings_pre)) && score > 55 && !seenSmartMoney.has("earn:"+key)) {
          seenSmartMoney.add("earn:"+key);
          pushAlert("pre_earnings", r.symbol, "Pre-earnings setup + base/catalyst factors", score);
        }
        // keep watch scores fresh
        updateWatchFromRow(r.symbol, r);
      });
    }
    renderAlertBell();
    // Ingest server alerts from snapshot (for restart / multi dev replay of rich investor alerts)
    if (data.alerts && Array.isArray(data.alerts)) {
      data.alerts.forEach(sa => {
        if (!recentAlerts.some(ra => ra.symbol === sa.symbol && ra.msg === sa.message)) {
          recentAlerts.unshift({type: sa.rule_type || "server", symbol: sa.symbol, msg: sa.message, ts: sa.triggered_at, score: sa.buy_score, server: true});
        }
      });
      if (recentAlerts.length > 30) recentAlerts.length = 30;
      renderAlertBell();
    }
    renderRadar(data);

    renderStats(data);
    if (rankingsChanged) {
      renderHot(data);
      if (connStatus) {
        connStatus.textContent = "● Rankings updated";
        connStatus.className = "pill status-pill live";
        setTimeout(() => {
          if (connStatus && wsConnected) {
            connStatus.textContent = "● Live";
          }
        }, 2500);
      }
    }
    renderEarnings(data);
    renderNews(data);
    const secFp = sectorFingerprint(data);
    if (secFp !== lastSectorFingerprint || activeTab === "sectors") {
      lastSectorFingerprint = secFp;
      renderSectors(data);
    }
    if (selectedSymbol && rankingsChanged) {
      const row = findRow(selectedSymbol, data);
      if (row) renderDetail(row);
    }
    if (modalSymbol && modalFullCache.has(modalSymbol)) {
      const row = modalFullCache.get(modalSymbol);
      const m = row.metrics || {};
      const { hit, total } = factorsDisplay(row);
      factorModalSub.textContent = `${hit} passed · ${total} applicable · buy ${m.buy_score ?? row.score} · ${m.name || ""}`;
      if (rankingsChanged) void renderFactorModalBody(row);
    }
    if (activeTab === "watch") renderWatch(data);
  }

  async function pollSnapshot() {
    if (wsConnected) return;
    try {
      const res = await fetch("/api/snapshot?light=true");
      if (res.ok) applyUpdate(await res.json());
    } catch (_) {
      /* ignore */
    }
  }

  loadFactorCatalog();
  syncStickyOffsets();
  window.addEventListener("resize", syncStickyOffsets);
  if ("ResizeObserver" in window) {
    const topbar = document.querySelector(".topbar");
    if (topbar) new ResizeObserver(syncStickyOffsets).observe(topbar);
  }
  connect();
  setInterval(pollSnapshot, 15000);

  // Initial empty renders for new panels (populated on first WS/snapshot)
  setTimeout(async () => {
    await loadServerWatches();
    const initSrvAlerts = await fetchRecentServerAlerts();
    initSrvAlerts.slice(0,10).forEach(sa => {
      if (!recentAlerts.some(a=>a.symbol===sa.symbol && a.msg && a.msg.includes((sa.message||"").slice(0,20)))) {
        recentAlerts.unshift({type:sa.rule_type||"server", symbol:sa.symbol, msg:sa.message, ts:sa.triggered_at, score:sa.buy_score, server:true});
      }
    });
    if (document.getElementById("panel-watch")) renderWatch(null);
    if (document.getElementById("panel-portfolio")) renderPortfolio();
    if (document.getElementById("radarList")) renderRadar(null);
    renderAlertBell();
    // seed rules UI if panel open later
  }, 800);

  // === Backtest Edge / Historical Performance + regime wiring ===
  // Visible section via guide tab (new card + load button) + statsBar "📊 Backtest Edge" card.
  // Shows: "If buy_score >70 historically returned X% avg in 7d (hit rate Y% over Z samples)" etc for all buckets/horizons,
  // confidence breakdowns, max DD, and "Factor performance" mini table from snapshot payloads (reused from engine factor_breakdown).
  async function loadEdgeStats() {
    const container = document.getElementById("edgeResults");
    if (!container) return;
    container.innerHTML = `<p class="muted">Loading live backtest edge from snapshots + forward yf outcomes… (reuses /api/edge + recent_strong_snapshots_with_outcomes)</p>`;
    try {
      const res = await fetch("/api/edge?days=3&min_score=55");
      const data = await res.json();
      renderEdgePanel(data, container);
      // also refresh regime pill if present
      if (data.regime) {
        lastRegime = data.regime;
        if (lastData) renderStats(lastData); // refresh statsBar pills
      }
    } catch (e) {
      container.innerHTML = `<p class="muted">Edge stats unavailable: ${escapeHtml(e.message || e)}</p>`;
    }
  }

  function renderEdgePanel(edgeData, container) {
    if (!edgeData || !edgeData.summary) {
      container.innerHTML = `<p class="muted">No edge data yet (need recent snapshots with outcomes).</p>`;
      return;
    }
    const sum = edgeData.summary || {};
    const o = sum.overall || {};
    const bkt = sum.bucket_stats_by_horizon || sum.bucket_stats || {};
    const confB = sum.confidence_breakdown || {};
    const factors = sum.top_factor_edge || [];
    const mdd = sum.mdd_summary || {};
    const reg = sum.regime || edgeData.regime || lastRegime || {};

    let html = `<div class="edge-panel">`;
    html += `<h4 style="margin:0.2rem 0">📊 Backtest Edge — Historical Performance (signals last ${sum.days||2}d, min score ${sum.min_score||55})</h4>`;
    if (reg && reg.note) {
      html += `<div style="background:#111827;padding:4px 8px;border-radius:4px;margin:4px 0;font-size:0.8rem"><strong>Regime:</strong> ${escapeHtml(reg.note)} <span class="muted">(VIX ${reg.vix||'—'} · ${reg.trend||''})</span></div>`;
    }
    // Key callout like task spec
    const b70 = bkt["70+"] || {};
    html += `<div style="font-weight:600;margin:0.3rem 0 0.5rem">If buy_score &gt;70 historically returned <strong>${b70["ret_7d"] ? b70["ret_7d"].avg_ret : (o["7d"]?o["7d"].avg_ret:'?')}%</strong> avg in 7d (hit rate <strong>${b70["ret_7d"] ? b70["ret_7d"].hit_rate : (o["7d"]?o["7d"].hit_rate:'?')}%</strong> over ${b70["ret_7d"]?b70["ret_7d"].n : (o["7d"]?o["7d"].n:sum.valid_with_outcomes||0)} samples)</div>`;

    // Overall horizons table
    html += `<table style="width:100%;font-size:0.78rem;margin:0.3rem 0;border-collapse:collapse"><thead><tr><th>Horizon</th><th>Samples</th><th>Hit rate</th><th>Avg ret %</th></tr></thead><tbody>`;
    ["1d","3d","7d","14d"].forEach(h => {
      const st = o[h] || {};
      html += `<tr><td>${h}</td><td>${st.n||0}</td><td>${st.hit_rate||0}%</td><td>${st.avg_ret||0}</td></tr>`;
    });
    html += `</tbody></table>`;

    // Bucket stats (rich)
    html += `<div style="margin-top:0.4rem"><strong>By buy_score bucket (multi-horizon + DD)</strong></div>`;
    html += `<table style="width:100%;font-size:0.72rem;margin:0.2rem 0"><thead><tr><th>Bucket</th><th>N</th><th>1d hit/avg</th><th>7d hit/avg</th><th>14d hit/avg</th><th>avg maxDD</th></tr></thead><tbody>`;
    Object.keys(bkt).forEach(b => {
      const bs = bkt[b] || {};
      const h1 = bs.ret_1d || {};
      const h7 = bs.ret_7d || {};
      const h14 = bs.ret_14d || {};
      html += `<tr><td>${b}</td><td>${bs.n||0}</td><td>${h1.hit_rate||'-'}/${h1.avg_ret||'-'}</td><td>${h7.hit_rate||'-'}/${h7.avg_ret||'-'}</td><td>${h14.hit_rate||'-'}/${h14.avg_ret||'-'}</td><td>${bs.avg_max_dd_14d||mdd.avg_max_dd_14d||'-'}</td></tr>`;
    });
    html += `</tbody></table>`;

    // Confidence breakdowns
    html += `<div style="margin-top:0.4rem"><strong>By confidence_score (from price_crawler heuristics)</strong></div>`;
    html += `<table style="width:100%;font-size:0.72rem;margin:0.2rem 0"><thead><tr><th>Conf bucket</th><th>N</th><th>7d hit/avg</th><th>avg maxDD</th></tr></thead><tbody>`;
    Object.keys(confB).forEach(cb => {
      const c = confB[cb] || {};
      html += `<tr><td>${cb}</td><td>${c.n||0}</td><td>${c.hit_7d||'-'}/${c.avg_ret7d||'-'}</td><td>${c.avg_max_dd||'-'}</td></tr>`;
    });
    html += `</tbody></table>`;

    // Factor performance mini table (optional per task)
    if (factors.length) {
      html += `<div style="margin-top:0.4rem"><strong>Factor performance (top passed factors by historical edge in these snapshots)</strong> <span class="muted" style="font-size:0.65rem">(reused factor_breakdown from engine snapshots)</span></div>`;
      html += `<table style="width:100%;font-size:0.68rem;margin:0.2rem 0"><thead><tr><th>Factor</th><th>N</th><th>7d hit%</th><th>avg ret7d</th><th>avg DD</th></tr></thead><tbody>`;
      factors.forEach(f => {
        html += `<tr><td>${escapeHtml(f.factor)}</td><td>${f.n}</td><td>${f.hit_rate_7d}</td><td>${f.avg_ret_7d}</td><td>${f.avg_max_dd}</td></tr>`;
      });
      html += `</tbody></table>`;
    }

    html += `<div class="muted" style="font-size:0.65rem;margin-top:0.3rem">valid outcomes: ${sum.valid_with_outcomes||0} / ${sum.total_signals||0} signals · max DD avg: ${mdd.avg_max_dd_14d||'—'}% (over ${mdd.n||0}). Data from SQLite snapshots + yf forward at query time. Not advice.</div>`;
    html += `</div>`;
    container.innerHTML = html;
  }

  // Fetch regime on startup + periodically (light, for pills)
  async function refreshRegime() {
    try {
      const r = await fetch("/api/regime");
      if (r.ok) {
        lastRegime = await r.json();
        if (lastData) renderStats(lastData);
      }
    } catch (_) {}
  }
  refreshRegime();
  setInterval(refreshRegime, 180000); // every 3min

  // Wire the load button that will be in guide (added to index.html)
  setTimeout(() => {
    const btn = document.getElementById("loadEdgeBtn");
    if (btn) btn.addEventListener("click", loadEdgeStats);
    // also auto-hint load once in guide if user visits
    const guideTab = document.querySelector('.tab[data-tab="guide"]');
    if (guideTab) {
      guideTab.addEventListener("click", () => {
        const c = document.getElementById("edgeResults");
        if (c && !c.dataset.loaded) {
          c.dataset.loaded = "1";
          setTimeout(() => { if (c.innerHTML.includes("Load live")) loadEdgeStats(); }, 400);
        }
      }, {once: true});
    }
  }, 1200);

  // Make all "boxes" (guide cards, etc.) clickable with useful actions
  document.querySelectorAll(".guide-card").forEach(card => {
    const h3 = card.querySelector("h3")?.textContent || "";
    card.style.cursor = "pointer";
    card.title = "Click to switch to the relevant section";
    card.addEventListener("click", () => {
      if (h3.includes("Hot Movers")) {
        document.querySelector('.tab[data-tab="hot"]')?.click();
      } else if (h3.includes("Whale") || h3.includes("S+")) {
        document.querySelector('.tab[data-tab="radar"]')?.click();
      } else if (h3.includes("Earnings")) {
        document.querySelector('.tab[data-tab="earnings"]')?.click();
      } else if (h3.includes("Sectors")) {
        document.querySelector('.tab[data-tab="sectors"]')?.click();
      } else if (h3.includes("My List")) {
        document.querySelector('.tab[data-tab="watch"]')?.click();
      } else if (h3.includes("Live updates") || h3.includes("Thesis")) {
        // no-op or scroll to top
        window.scrollTo({ top: 0, behavior: "smooth" });
      } else if (h3.includes("Backtest") || h3.includes("Historical") || h3.includes("Edge")) {
        const c = document.getElementById("edgeResults");
        if (c) { document.querySelector('.tab[data-tab="guide"]')?.click(); loadEdgeStats(); }
      }
    });
  });
})();
