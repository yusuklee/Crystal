(async function () {
  document.getElementById("hdr").innerHTML = C.header();
  const aid = decodeURIComponent(location.pathname.split("/").pop());
  const uid = C.q().get("user_id") || "";
  const wrap = document.getElementById("wrap");
  const main = document.getElementById("main");
  const side = document.getElementById("side");
  const panel = document.getElementById("panel");
  const settings = await C.get("/api/settings");
  const art = await C.get(`/api/article/${encodeURIComponent(aid)}`);
  const label = art.final_label;
  const userQ = uid ? `?user_id=${encodeURIComponent(uid)}` : "";

  function renderMain(compact) {
    const meta = compact
      ? `${C.chip(label, art.pred_prob_fake)}<span class="prob">${C.pct(art.prob)}</span>`
      : `${C.chip(label, art.pred_prob_fake)}<span>Predicted veracity · click a highlighted phrase to see why it signals the verdict</span>`;
    main.innerHTML = `<h1 class="${art.title.length > 90 ? "long" : ""}">${C.highlight(art.title, art.keywords, "title", label)}</h1><div class="meta">${meta}</div>${C.highlight(art.body, art.keywords, "body", label)}`;
    C.bindKeywords(main, art, label);
  }

  function renderSide() {
    const i = C.levelIdx(art.pred_prob_fake);
    const conf = art.pred_prob_fake == null ? null : 1 - art.pred_prob_fake;
    const bar = `<div class="vbar lv${i == null ? (label === 1 ? 4 : 0) : i}"><span>${C.level(art.pred_prob_fake) || C.name(label)}</span>${conf == null ? "" : `<span class="pc">${C.pct(conf, 2)}</span>`}</div>`;
    const bins = C.LEVELS.map(() => []);
    for (const c of art.counterparts) { const j = C.levelIdx(c.pred_prob_fake); if (j != null && !bins[j].length) bins[j].push(c); }
    const cps = [4, 3, 2, 1, 0].map(j => { const items = bins[j]; return `<div class="bin l${j}">${items.length
      ? items.map(c => `<div class="cp" data-id="${C.esc(c.article_id)}"><div class="t">${C.esc(c.title)}</div></div>`).join("")
      : `<div class="none">no articles available</div>`}</div>`; }).join("");
    side.innerHTML = `<div class="card"><h3>Predicted Veracity</h3>${bar}
        <button class="why-toggle">Why this verdict? <span class="car">▾</span></button><p class="why-text" hidden></p></div>
      <div class="card"><h3>Explore Related Articles</h3>${cps}</div>`;
    side.querySelectorAll(".cp").forEach(el => el.addEventListener("click", () => openSplit(el.dataset.id, true)));
    const tg = side.querySelector(".why-toggle"), wt = side.querySelector(".why-text");
    tg.addEventListener("click", () => {
      wt.hidden = !wt.hidden;
      tg.querySelector(".car").textContent = wt.hidden ? "▾" : "▴";
      if (!wt.hidden && !wt.textContent) {
        if (art.verdict_rationale && art.verdict_status !== "pending") {
          wt.innerHTML = C.esc(art.verdict_rationale).replace(/(Fake|True)/, "<b>$1</b>");
          return;
        }
        wt.textContent = "Analyzing context..."; wt.classList.add("pending");
        C.post("/api/rationale", { article_id: aid, kind: "verdict", key: "" }).then(r => {
          if (r.status === "pending") return;
          art.verdict_rationale = r.text; art.verdict_status = r.status;
          wt.innerHTML = C.esc(r.text).replace(/(Fake|True)/, "<b>$1</b>"); wt.classList.remove("pending");
        }).catch(() => {});
      }
    });
  }

  async function openSplit(bid, push) {
    const cmp = await C.get(`/api/compare?a=${encodeURIComponent(aid)}&b=${encodeURIComponent(bid)}`);
    const b = cmp.b, bl = b.final_label, cc = cmp.claim_contrast || {};
    const pend = cmp.contrast_status === "pending" ? "pending" : "";
    document.title = `CRYSTAL · ${settings.goals.event}`;
    document.getElementById("goal").textContent = settings.goals.event;
    wrap.classList.add("split");
    side.hidden = true;
    panel.hidden = false;
    panel.innerHTML = `<div class="panel-top"><a href="/article/${encodeURIComponent(bid)}${userQ}">View Full Page ↗</a><button class="x" aria-label="close">×</button></div>
      <div class="contrast"><div class="why"><span class="star">✦</span>Claim contrast on this event</div>
        <div class="row"><span class="k">${C.chip(label, art.pred_prob_fake)}</span><span class="v ${pend}">${C.esc(cc.this || "")}</span></div>
        <div class="row"><span class="k">${C.chip(bl, b.pred_prob_fake)}</span><span class="v ${pend}">${C.esc(cc.related || "")}</span></div></div>
      <div class="article"><h1 class="${b.title.length > 90 ? "long" : ""}">${C.highlight(b.title, b.keywords, "title", bl)}</h1><div class="meta">${C.chip(bl, b.pred_prob_fake)}<span class="prob">${C.pct(b.prob)}</span></div>${C.highlight(b.body, b.keywords, "body", bl)}</div>`;
    C.bindKeywords(panel.querySelector(".article"), b, bl);
    panel.querySelector(".x").onclick = closeSplit;
    if (pend) {
      C.post("/api/rationale", { article_id: aid, kind: "contrast", key: bid }).then(r => {
        if (r.status === "pending" || !r.text || typeof r.text !== "object") return;
        const rows = panel.querySelectorAll(".contrast .row .v");
        if (rows.length === 2) { rows[0].textContent = r.text.this || ""; rows[1].textContent = r.text.related || ""; rows.forEach(x => x.classList.remove("pending")); }
      }).catch(() => {});
    }
    renderMain(true);
    window.scrollTo(0, 0);
    if (push) history.pushState({ b: bid }, "", `${location.pathname}?${new URLSearchParams({ ...(uid ? { user_id: uid } : {}), compare: bid })}`);
  }

  function closeSplit() {
    wrap.classList.remove("split");
    panel.hidden = true;
    panel.innerHTML = "";
    side.hidden = false;
    document.title = `CRYSTAL · ${settings.goals.article}`;
    document.getElementById("goal").textContent = settings.goals.article;
    renderMain(false);
    history.pushState({}, "", `${location.pathname}${userQ}`);
  }

  window.addEventListener("popstate", () => {
    const b = C.q().get("compare");
    if (b) openSplit(b, false); else closeSplit();
  });

  document.title = `CRYSTAL · ${settings.goals.article}`;
  document.getElementById("goal").textContent = settings.goals.article;
  document.getElementById("goal").hidden = !settings.show_level_caption;
  renderMain(false);
  renderSide();
  const b0 = C.q().get("compare");
  if (b0) openSplit(b0, false);
})();
