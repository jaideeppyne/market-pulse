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

  // New features state
  let watchlist = []; // [{symbol, addedAt, lastScore, lastBuy, addedScore}]
  let recentAlerts = []; // [{type, symbol, msg, ts, score}]
  let seenSmartMoney = new Set();
  let alertsEnabled = true;

  // Load persisted watchlist (local only)
  try {
    const saved = localStorage.getItem("marketpulse_watchlist");
    if (saved) watchlist = JSON.parse(saved);
  } catch (e) {}

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
    if (marketFilter === "us" && data.hot_by_market?.us?.length) {
      return data.hot_by_market.us;
    }
    if (marketFilter === "india" && data.hot_by_market?.india?.length) {
      return data.hot_by_market.india;
    }
    let pool = data.hot || [];
    if (marketFilter !== "all") {
      pool = pool.filter((r) => r.market === marketFilter);
    }
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

  /* --- Tab navigation --- */
  document.querySelectorAll(".tab").forEach((btn) => {
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
      if (tab === "sectors") renderSectors(lastData);
      if (tab === "watch") renderWatch(lastData);
      if (tab === "radar") renderRadar(lastData);
    });
  });

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
      renderHot(lastData);
    });
  });

  document.getElementById("earlyOnlyChip")?.addEventListener("click", (btn) => {
    earlyOnly = !earlyOnly;
    btn.classList.toggle("active", earlyOnly);
    btn.dataset.early = earlyOnly ? "1" : "0";
    renderHot(lastData);
  });

  document.getElementById("whaleOnlyChip")?.addEventListener("click", (btn) => {
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
  document.getElementById("clearWatchBtn")?.addEventListener("click", () => {
    if (confirm("Clear your entire My List?")) {
      watchlist = [];
      saveWatch();
      renderWatch(lastData);
    }
  });
  alertBell?.addEventListener("click", () => {
    if (Notification && Notification.permission === "default") {
      Notification.requestPermission().then(p => { if (p === "granted") alertsEnabled = true; });
    }
    showAlertsPanel();
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

  function sparklineSvg(values, w = 72, h = 26) {
    if (!values || values.length < 2) return "";
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const pts = values
      .map((v, i) => {
        const x = (i / (values.length - 1)) * w;
        const y = h - ((v - min) / range) * h;
        return `${x},${y}`;
      })
      .join(" ");
    const color = values[values.length - 1] >= values[0] ? "#22c55e" : "#ef4444";
    return `<svg class="spark" width="${w}" height="${h}"><polyline fill="none" stroke="${color}" stroke-width="1.5" points="${pts}"/></svg>`;
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
    if (!alertCountEl || !alertBell) return;
    const n = recentAlerts.length;
    alertCountEl.textContent = n > 9 ? "9+" : n;
    alertBell.classList.toggle("has-alerts", n > 0);
  }

  function showAlertsPanel() {
    const html = recentAlerts.length
      ? recentAlerts.map(a => `<div class="alert-item"><strong>${escapeHtml(a.symbol)}</strong> <span class="muted">${escapeHtml(a.type)}</span><br><span>${escapeHtml(a.msg)}</span><div class="muted" style="font-size:0.7rem">${new Date(a.ts).toLocaleTimeString()}</div></div>`).join("")
      : '<p class="muted">No alerts yet. High buy scores, new S+ hits, and pre-earnings setups will appear here + trigger browser notifications.</p>';
    // Simple modal reuse or inline
    const panel = document.createElement("div");
    panel.className = "alerts-panel";
    panel.innerHTML = `<div class="ap-header"><strong>Recent Alerts</strong> <button class="close-x">×</button></div><div class="ap-body">${html}</div>`;
    document.body.appendChild(panel);
    panel.querySelector(".close-x").onclick = () => panel.remove();
    panel.onclick = (e) => { if (e.target === panel) panel.remove(); };
  }

  function addToWatch(symbol, row) {
    symbol = symbol.toUpperCase();
    if (watchlist.find(w => w.symbol === symbol)) return;
    const m = row && row.metrics ? row.metrics : {};
    watchlist.unshift({
      symbol,
      addedAt: new Date().toISOString(),
      addedScore: Math.round(row ? (row.buy_score ?? row.score ?? 0) : 0),
      lastScore: Math.round(row ? (row.buy_score ?? row.score ?? 0) : 0),
      lastBuy: Math.round(m.buy_score ?? row?.score ?? 0),
      lastQuality: Math.round(m.quality_score ?? 0),
    });
    saveWatch();
    renderWatch(lastData);
    // gentle nudge
    if (alertBell) {
      alertBell.style.transform = "scale(1.2)";
      setTimeout(() => { if (alertBell) alertBell.style.transform = ""; }, 400);
    }
  }

  function removeFromWatch(symbol) {
    watchlist = watchlist.filter(w => w.symbol !== symbol.toUpperCase());
    saveWatch();
    renderWatch(lastData);
  }

  function saveWatch() {
    try { localStorage.setItem("marketpulse_watchlist", JSON.stringify(watchlist)); } catch(e){}
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
      const old = event && event.target ? event.target.textContent : "";
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
        return `${r.symbol}:${r.score}:${m.day_chg_pct}:${m.price}`;
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
        return `<div class="cycle-card" data-cycle="${escapeHtml(c)}">
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
      return (b.score || 0) - (a.score || 0);
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
    const fullScan = (s.last_price_scan || "—").slice(11, 19);
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
    const highConv = hotPool.filter(r => (r.buy_score ?? r.score ?? 0) >= 70).length;
    const smCount = hotPool.filter(r => hasSmartMoneySignal(r)).length;
    const newsBurst = (data?.news || []).length;

    statsBar.innerHTML = `
      <div class="stat-card clickable" data-stat="highconv" title="Click to filter hot list to high-conviction names only"><div class="label">High Conv (≥70)</div><div class="value">${highConv}</div></div>
      <div class="stat-card clickable" data-stat="whale" title="Click to show only names with whale / politician / FII signals (S+ Radar filter)"><div class="label">S+ Smart Money</div><div class="value" style="color:#f59e0b">${smCount}</div></div>
      <div class="stat-card"><div class="label">Hot</div><div class="value">${s.hot_count || 0}</div></div>
      <div class="stat-card"><div class="label">Tracked</div><div class="value">${s.symbols_tracked || 0}</div></div>
      <div class="stat-card"><div class="label">News hits</div><div class="value">${newsBurst}</div></div>
      <div class="stat-card clickable" data-stat="sectors" title="Go to Sectors tab"><div class="label">Sectors</div><div class="value">${s.sector_count || 0}</div></div>
      <div class="stat-card"><div class="label">Earnings 7d</div><div class="value">${s.earnings_upcoming || 0}</div></div>
      <div class="stat-card"><div class="label">Full scan</div><div class="value" style="font-size:0.72rem">${fullScan}</div></div>
      <div class="stat-card"><div class="label">Price tick</div><div class="value" style="font-size:0.72rem">${quickPx}</div></div>
    `;

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
      hotHint.textContent = sectorFilter
        ? `Filtered to sector: ${sectorFilter}. Clear via badge above table.`
        : "Ranking updates automatically during each scan batch. Stocks leave the list when score drops below threshold.";
    }

    // Prune rank map for symbols no longer in list
    const visible = new Set(rows.map((r) => r.symbol));
    for (const sym of prevRankBySymbol.keys()) {
      if (!visible.has(sym)) prevRankBySymbol.delete(sym);
    }

    hotBody.innerHTML = rows
      .map((r, idx) => {
        const m = r.metrics || {};
        const day = m.day_chg_pct ?? 0;
        const cls = day >= 0 ? "pos" : "neg";
        const sel = r.symbol === selectedSymbol ? "selected" : "";
        const flash = rowFlashClass(r.symbol, idx, r.score || 0);
        const ext = m.is_extended
          ? '<span class="ext-badge" title="Near 52w high / extended — chase risk">EXT</span>'
          : "";
        const buy = m.buy_score ?? r.score;
        const qual = m.quality_score ?? "—";
        const whale = smartMoneyBadges(r);
        const watched = watchlist.some(w => w.symbol === r.symbol) ? "★" : "☆";
        const whaleClickable = whale ? ` <span class="whale-badge clickable" data-whale-sym="${attrEsc(r.symbol)}" title="Click for who / headline / why S+ 6.5× boost">${whale.replace(/<[^>]+>/g,'')}</span>` : "";
        const discBadge = r.discovered ? `<span class="ext-badge" style="background:rgba(168,85,247,0.25);color:#c084fc;border-color:#c084fc" title="From multi-website + large pool discovery scan (not regular hot)">DISC</span>` : "";
        return `<tr class="${sel} ${flash}${whale ? " row-whale" : ""}" data-symbol="${attrEsc(r.symbol)}">
          <td><span class="rank-num">${idx + 1}</span> <strong class="clickable" data-act="select">${r.symbol}</strong>${ext}${discBadge}${whaleClickable}<br><span class="sym-name">${escapeHtml(m.name || "")}</span> <button class="tiny-watch" data-watch="${attrEsc(r.symbol)}" title="Add/remove from My List">${watched}</button></td>
          <td><span class="score-pill clickable" data-act="factors" title="Click: what boosted the buy score? (entry + S+ catalyst heavy) — opens full weighted checklist">${buy}</span></td>
          <td><span class="qual-pill clickable" data-act="factors" title="Overall quality checklist score. Click to inspect all pass/fail factors.">${qual}</span></td>
          <td class="factor-cell">${factorPill(r)}</td>
          <td class="${cls} clickable" data-act="factors" title="Day % move contributes to momentum + rvol factors. Large moves with volume can create catalyst or distribution flags.">${day > 0 ? "+" : ""}${day}%</td>
          <td class="clickable" data-act="factors" title="Relative volume (today vs 10d avg). ≥1.6-2.5× surges are strong volume factors in the engine.">${m.rvol ?? "—"}x</td>
          <td class="clickable" data-act="reanalyze" title="Click chart to re-run full engine on latest prices/news">${sparklineSvg(r.sparkline)}</td>
        </tr>`;
      })
      .join("");

    hotBody.querySelectorAll("tr").forEach((tr) => {
      tr.addEventListener("click", (ev) => {
        if (ev.target.closest(".factor-pill") || ev.target.closest(".tiny-watch") || ev.target.closest("[data-whale-sym]") || ev.target.closest("[data-act]")) return;
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
        <div class="thesis-head"><strong>${escapeHtml(thesis.archetype)}</strong> <button class="tiny" data-act="watch">${isWatched ? "✓ Watched" : "★ Watch"}</button> <button class="tiny" data-act="thesis">Copy thesis</button></div>
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
      <h3>${row.symbol} ${isAdHoc ? '<span class="chip" style="font-size:0.65rem; padding:1px 6px; vertical-align:middle;">ad-hoc deep analysis</span>' : ''}</h3>
      <div class="meta-line">${escapeHtml(m.name || "")} · ${escapeHtml(m.sector || "")} · ${row.market.toUpperCase()}</div>
      ${clickableSmBlock}
      <div class="detail-score-row">
        Buy <strong class="big-score clickable" data-act="factors" title="Click to see exactly which factors drove this buy score (weighted) and the full checklist">${m.buy_score ?? row.score}</strong>
        <span class="qual-pill clickable" data-act="factors" title="Quality score = broad checklist health (fundamentals + valuation + technicals). Click for breakdown">${m.quality_score ?? "—"}</span>
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
      <div style="margin-top:0.4rem"><button class="tiny" data-act="whale">🐳 Whale details</button> <button class="tiny" data-act="thesis">Copy full thesis</button> <button class="tiny" data-act="watch">${isWatched ? "✓ Watched" : "★ Watch"}</button></div>
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
      tbody.innerHTML = `<tr><td colspan="6" class="muted">Your watchlist is empty. Use the search box to Analyze any ticker (even outside the hot list), then click ★ Watch in the detail panel, or the ☆/★ in Hot rows.</td></tr>`;
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
      htmlParts.push(`<tr data-symbol="${attrEsc(w.symbol)}">
        <td><strong>${w.symbol}</strong><br><span class="muted" style="font-size:0.7rem">added ${added} @ ${w.addedScore}</span></td>
        <td><span class="score-pill">${buy}</span></td>
        <td><span class="qual-pill">${qual}</span></td>
        <td>${fh}/${ft}</td>
        <td><span class="muted" style="font-size:0.75rem">last ${w.lastScore || buy}</span></td>
        <td>
          <button class="tiny" data-act="analyze">Analyze</button>
          <button class="tiny danger" data-act="remove">Remove</button>
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
        if (e.target.dataset.act === "analyze" || !e.target.dataset.act) {
          document.querySelector('.tab[data-tab="hot"]')?.click();
          fetchFullSymbol(sym).then(full => { renderDetail(full); openFactorModal(sym, data); }).catch(()=>{});
        }
      });
    });
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
      connStatus.className = "status live";
    };
    ws.onclose = () => {
      wsConnected = false;
      connStatus.textContent = "Reconnecting…";
      connStatus.className = "status down";
      setTimeout(connect, 2000);
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "update" && msg.data) {
          applyUpdate(msg.data);
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
    renderRadar(data);

    renderStats(data);
    if (rankingsChanged) {
      renderHot(data);
      if (connStatus) {
        connStatus.textContent = "● Rankings updated";
        connStatus.className = "status live";
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
  connect();
  setInterval(pollSnapshot, 15000);

  // Initial empty renders for new panels (populated on first WS/snapshot)
  setTimeout(() => {
    if (document.getElementById("panel-watch")) renderWatch(null);
    if (document.getElementById("radarList")) renderRadar(null);
    renderAlertBell();
  }, 800);
})();