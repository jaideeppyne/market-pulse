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
    const q = (symbolSearch?.value || "").trim();
    if (!q) return;
    // If it looks like a ticker, force full analysis (even if not in current hot list)
    const looksLikeTicker = /^[A-Za-z0-9.]{1,12}$/.test(q);
    try {
      // fetchFullSymbol will call /api/symbol which now does on-demand analysis for unknowns
      const full = await fetchFullSymbol(q.toUpperCase());
      // Make it available in current view
      if (lastData) {
        lastData.symbols = lastData.symbols || {};
        lastData.symbols[full.symbol] = full;
      }
      selectSymbol(full.symbol, lastData || {});
      // Optional: clear the input after successful analyze so filter doesn't stay stuck
      if (symbolSearch) symbolSearch.value = "";
      renderHot(lastData);
    } catch (e) {
      alert(`Could not analyze "${q}". ${e.message || "Check ticker spelling or try again in a moment."}`);
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

  /* --- Factor modal --- */
  document.querySelectorAll("[data-close='factorModal']").forEach((el) => {
    el.addEventListener("click", () => closeFactorModal());
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && factorModal && !factorModal.hidden) closeFactorModal();
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

      factorModalBody.innerHTML = summary + topBlock + sections;
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
    statsBar.innerHTML = `
      <div class="stat-card"><div class="label">Tracked</div><div class="value">${s.symbols_tracked || 0}</div></div>
      <div class="stat-card"><div class="label">Hot</div><div class="value">${s.hot_count || 0}</div></div>
      <div class="stat-card"><div class="label">Sectors</div><div class="value">${s.sector_count || 0}</div></div>
      <div class="stat-card"><div class="label">Earnings 7d</div><div class="value">${s.earnings_upcoming || 0}</div></div>
      <div class="stat-card"><div class="label">Full scan</div><div class="value" style="font-size:0.72rem">${fullScan}</div></div>
      <div class="stat-card"><div class="label">Price tick</div><div class="value" style="font-size:0.72rem">${quickPx}</div></div>
    `;
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
        return `<tr class="${sel} ${flash}${whale ? " row-whale" : ""}" data-symbol="${attrEsc(r.symbol)}">
          <td><span class="rank-num">${idx + 1}</span> <strong>${r.symbol}</strong>${ext}${whale}<br><span class="sym-name">${escapeHtml(m.name || "")}</span></td>
          <td><span class="score-pill">${buy}</span></td>
          <td><span class="qual-pill">${qual}</span></td>
          <td class="factor-cell">${factorPill(r)}</td>
          <td class="${cls}">${day > 0 ? "+" : ""}${day}%</td>
          <td>${m.rvol ?? "—"}x</td>
          <td>${sparklineSvg(r.sparkline)}</td>
        </tr>`;
      })
      .join("");

    hotBody.querySelectorAll("tr").forEach((tr) => {
      tr.addEventListener("click", (ev) => {
        if (ev.target.closest(".factor-pill")) return;
        selectSymbol(tr.dataset.symbol, data);
      });
    });
    hotBody.querySelectorAll(".factor-pill").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        openFactorModal(btn.dataset.symbol, data);
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
    detailEl.innerHTML = `<div class="detail">
      <h3>${row.symbol} ${isAdHoc ? '<span class="chip" style="font-size:0.65rem; padding:1px 6px; vertical-align:middle;">ad-hoc analysis</span>' : ''}</h3>
      <div class="meta-line">${escapeHtml(m.name || "")} · ${escapeHtml(m.sector || "")} · ${row.market.toUpperCase()}</div>
      ${smBlock}
      <div class="detail-score-row">Buy <strong class="big-score">${m.buy_score ?? row.score}</strong>
        <span class="qual-pill">Qual ${m.quality_score ?? "—"}</span>
        ${m.is_extended ? '<span class="ext-badge">Extended — late chase</span>' : ""}
        <button type="button" class="factor-pill detail-factor-btn" data-symbol="${attrEsc(row.symbol)}">${hit}/${total} factors</button>
      </div>
      ${m.pct_52w_range != null ? `<div class="meta-line">52w range position: ${m.pct_52w_range}% · entry checks: ${m.entry_factors ?? 0}</div>` : ""}
      <div class="spark-large">${sparklineSvg(row.sparkline, 300, 72)}</div>
      <div class="meta-line">$${m.price} · Day ${m.day_chg_pct}% · 5d ${m.ret5d_pct}% · RVOL ${m.rvol}x · RSI ${m.rsi ?? "—"}</div>
      <div class="meta-line">P/E ${m.pe ?? "—"} · P/B ${m.pb ?? "—"} · FCF ${m.fcf ? "✓" : "—"}</div>
      ${alerts ? `<ul class="alerts">${alerts}</ul>` : ""}
      <p class="muted section-label">Passed checks</p>
      <div class="factor-chips">${factorChips || '<span class="muted">None yet</span>'}${more}</div>
    </div>`;

    detailEl.querySelector(".detail-factor-btn")?.addEventListener("click", () => {
      openFactorModal(row.symbol, lastData);
    });
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
})();