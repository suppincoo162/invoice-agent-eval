(() => {
  "use strict";

  const data = window.INVOICE_EVAL_DATA;
  if (!data || !Array.isArray(data.cases)) {
    document.getElementById("empty-state").classList.remove("hidden");
    document.querySelector(".layout").classList.add("hidden");
    return;
  }

  const state = {
    caseId: null,
    tab: "summary",
    search: "",
  };

  const caseList = document.getElementById("case-list");
  const caseSearch = document.getElementById("case-search");
  const hero = document.getElementById("case-hero");
  const content = document.getElementById("tab-content");
  const tabs = document.getElementById("tabs");
  const evidenceContent = document.getElementById("evidence-content");

  init();

  function init() {
    const hash = parseHash();
    state.caseId =
      (hash.case && getCase(hash.case) ? hash.case : null) ||
      defaultCase()?.case_id ||
      data.cases[0].case_id;
    state.tab = validTab(hash.tab) ? hash.tab : "summary";

    renderTopbar();
    renderCaseList();
    bindEvents();
    render();
  }

  function bindEvents() {
    caseSearch.addEventListener("input", (event) => {
      state.search = event.target.value.trim().toLowerCase();
      renderCaseList();
    });

    tabs.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-tab]");
      if (!button) return;
      state.tab = button.dataset.tab;
      render();
    });

    window.addEventListener("hashchange", () => {
      const hash = parseHash();
      if (hash.case && getCase(hash.case)) state.caseId = hash.case;
      if (validTab(hash.tab)) state.tab = hash.tab;
      render();
    });
  }

  function render() {
    const item = getCase(state.caseId);
    if (!item) return;

    document.querySelectorAll("#tabs button").forEach((button) => {
      button.classList.toggle("active", button.dataset.tab === state.tab);
    });
    renderCaseList();
    renderHero(item);
    renderTab(item);
    renderEvidence(item);
    history.replaceState(
      null,
      "",
      `#case=${encodeURIComponent(item.case_id)}&tab=${state.tab}`
    );
  }

  function renderTopbar() {
    const meta = data.metadata;
    const rec = data.release_recommendation;
    document.getElementById("topbar-meta").innerHTML = [
      badge(`v${meta.evaluator_version}`, "blue"),
      badge(`${meta.case_count} Cases / ${meta.run_count} Runs`, ""),
      badge(`建议 ${rec.action}`, rec.action === "investigate" ? "red" : "amber"),
      badge(meta.code_commit + (meta.working_tree_dirty ? " dirty" : ""), ""),
    ].join("");
    document.getElementById("case-count").textContent =
      `${data.cases.length} cases`;
    document.getElementById("link-report").href =
      data.appendices.version_report;
    document.getElementById("link-four-way").href =
      data.appendices.four_way_report;
    document.getElementById("link-four-way").textContent = "四源附录";
  }

  function renderCaseList() {
    const filtered = data.cases.filter((item) => {
      if (!state.search) return true;
      return `${item.case_id} ${item.scenario || ""}`
        .toLowerCase()
        .includes(state.search);
    });
    caseList.innerHTML = filtered
      .map((item) => {
        const active = item.case_id === state.caseId ? " active" : "";
        const capped = item.runs.some(
          (run) => run.rubric && run.rubric.impact_cap != null
        );
        return `
          <button class="case-item${active}" data-case="${attr(item.case_id)}">
            <div class="case-title">
              <span>${esc(item.case_id)}</span>
              ${directionBadge(item.version_direction)}
            </div>
            <div class="case-scenario">${esc(item.scenario || "")}</div>
            <div class="case-flags">
              ${item.runs.some((run) => run.events.some((e) => e.is_first_fault))
                ? badge("存在首错", "red")
                : badge("无根因", "green")}
              ${capped ? badge("影响封顶", "amber") : ""}
            </div>
          </button>`;
      })
      .join("");

    caseList.querySelectorAll("button[data-case]").forEach((button) => {
      button.addEventListener("click", () => {
        state.caseId = button.dataset.case;
        state.tab = "summary";
        render();
      });
    });
  }

  function renderHero(item) {
    const runs = item.runs;
    hero.innerHTML = `
      <div class="hero-grid">
        <div>
          <div class="case-flags">
            ${badge(item.version_direction, directionTone(item.version_direction))}
            ${badge(recForCase(item).label, recForCase(item).tone)}
          </div>
          <h2>${esc(item.case_id)} · ${esc(item.scenario || "验证 Case")}</h2>
          <p>${esc(item.version_reason || "")}</p>
          <div class="request-box">
            <strong>用户请求</strong>
            <div>${esc(item.user_request || "—")}</div>
          </div>
        </div>
        <div class="result-grid">
          ${runs.map((run) => runResultCard(run)).join("")}
        </div>
      </div>`;
  }

  function runResultCard(run) {
    const a = run.assessment;
    const rubricScore = run.rubric
      ? `${run.rubric.rubric_score}${run.rubric.impact_cap != null
          ? `（封顶 ${run.rubric.impact_cap}）`
          : ""}`
      : "未启用";
    return `
      <article class="result-card">
        <h3>${esc(run.run_id)} ${badge(run.final_state, stateTone(run.final_state))}</h3>
        <div class="metric-line"><span>处理正确</span><span>${boolText(a.agent_task_success)}</span></div>
        <div class="metric-line"><span>实际开票</span><span>${boolText(a.business_invoice_created)}</span></div>
        <div class="metric-line"><span>质量分</span><span>${esc(a.quality_score)}</span></div>
        <div class="metric-line"><span>Rubric</span><span>${esc(rubricScore)}</span></div>
      </article>`;
  }

  function renderTab(item) {
    const renderers = {
      summary: renderSummary,
      timeline: renderTimeline,
      sources: renderSources,
      rubric: renderRubric,
      analysis: renderAnalysis,
      raw: renderRaw,
    };
    content.innerHTML = renderers[state.tab](item);
    bindEventJumps(content);
  }

  function renderSummary(item) {
    const rec = recForCase(item);
    const roots = item.runs.flatMap((run) =>
      (run.assessment.root_causes || []).map((root) => ({ run, root }))
    );
    const improvements = item.runs.filter(
      (run) => run.assessment.agent_task_success
    );
    return `
      <section class="summary-grid">
        <div class="summary-item">总体建议<strong>${esc(data.release_recommendation.action)}</strong></div>
        <div class="summary-item">本 Case 方向<strong>${esc(item.version_direction)}</strong></div>
        <div class="summary-item">风险结论<strong>${esc(rec.label)}</strong></div>
      </section>
      <section class="panel">
        <h3>业务结论</h3>
        <div class="${roots.length ? "callout danger" : "callout"}">
          ${roots.length
            ? `发现 ${roots.length} 个根因。优先关注首错事件及其传播影响。`
            : "未发现确定性根因；仍以 A/B 正式布尔值为准。"}
        </div>
        <div class="split" style="margin-top:14px">
          <div>
            <h4>A/B 结论</h4>
            <dl class="kv">
              ${item.runs.map((run) => `
                <dt>${esc(run.run_id)}</dt>
                <dd>${boolText(run.assessment.agent_task_success)}处理；
                ${boolText(run.assessment.business_invoice_created)}开票；
                质量分 ${esc(run.assessment.quality_score)}</dd>
              `).join("")}
            </dl>
          </div>
          <div>
            <h4>Rubric 影响</h4>
            <dl class="kv">
              ${item.runs.map((run) => `
                <dt>${esc(run.run_id)}</dt>
                <dd>${run.rubric
                  ? `${esc(run.assessment.quality_score)} → ${esc(run.rubric.rubric_score)}
                    ${run.rubric.cap_reasons.length
                      ? `；${esc(run.rubric.cap_reasons.map((r) => r.reason).join("、"))}`
                      : ""}`
                  : "未启用 Rubric"}</dd>
              `).join("")}
            </dl>
          </div>
        </div>
      </section>
      <section class="panel">
        <h3>根因与证据</h3>
        ${roots.length ? rootTable(roots) : "<p>当前 Case 未发现根因。</p>"}
      </section>`;
  }

  function renderTimeline(item) {
    return `
      <section class="timeline-grid">
        ${item.runs.map((run) => `
          <div class="timeline-column panel">
            <h3>${esc(run.run_id)} ${badge(run.final_state, stateTone(run.final_state))}</h3>
            <div class="timeline">
              ${run.events.map((event) => eventCard(event)).join("")}
            </div>
          </div>
        `).join("")}
      </section>`;
  }

  function eventCard(event) {
    const classes = [
      "event",
      statusClass(event.step_status),
      event.is_first_fault ? "first-fault" : "",
      event.is_evidence ? "evidence" : "",
    ].filter(Boolean).join(" ");
    return `
      <details class="${classes}" id="event-${attr(event.event_id)}">
        <summary>
          <div class="event-head">
            <span class="event-id">${esc(event.event_id)}</span>
            <span class="event-step">${esc(event.step_id)}</span>
            ${badge(event.step_status, stateTone(event.step_status))}
            ${event.is_first_fault ? badge("首错", "red") : ""}
            ${event.is_evidence ? badge("证据", "amber") : ""}
          </div>
        </summary>
        <div class="event-json">
          <div class="json-block">${esc(JSON.stringify({
            observed_input: event.observed_input,
            observed_output: event.observed_output,
            tool_calls: event.tool_calls,
          }, null, 2))}</div>
        </div>
      </details>`;
  }

  function renderSources(item) {
    const four = item.four_way;
    if (!four) return `<section class="panel"><p>未提供四方对照。</p></section>`;
    const coverage = data.source_coverage || {};
    const sourceCase = four.sources || {};
    const runs = item.runs;
    const runValues = {};
    runs.forEach((run) => {
      runValues[run.run_id] = four.runs
        ?.find((row) => row.run_id === run.run_id)?.values || {};
    });
    return `
      <section class="panel">
        <h3>来源覆盖与方向</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>来源</th><th>覆盖</th><th>本 Case 状态</th><th>方向</th><th>未知项</th></tr></thead>
            <tbody>
              ${Object.entries(sourceCase).map(([key, value]) => `
                <tr>
                  <td>${esc(sourceLabel(key))}</td>
                  <td>${coverage[key]
                    ? `${esc(coverage[key].present_count)}/${esc(coverage[key].present_count + (coverage[key].missing_cases || []).length)}`
                    : "—"}</td>
                  <td>${esc(value.status || "—")}</td>
                  <td>${directionBadge(value.direction)}</td>
                  <td>${esc((value.unknowns || []).join("；") || "—")}</td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>
      </section>
      <section class="panel">
        <h3>Run 级对照</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Run</th><th>来源</th><th>处理正确</th><th>实际开票</th><th>根因</th><th>首错</th></tr></thead>
            <tbody>
              ${runs.flatMap((run) => Object.entries(runValues[run.run_id] || {}).map(([source, value]) => `
                <tr>
                  <td>${esc(run.run_id)}</td>
                  <td>${esc(sourceLabel(source))}</td>
                  <td>${boolText(value.agent_task_success)}</td>
                  <td>${boolText(value.business_invoice_created)}</td>
                  <td>${esc((value.root_causes || []).flat().filter(Boolean).join("、") || "—")}</td>
                  <td>${esc((value.first_faults || []).flat().filter(Boolean).join("、") || "—")}</td>
                </tr>`)).join("")}
            </tbody>
          </table>
        </div>
      </section>
      ${pairwiseTable()}`;
  }

  function renderRubric(item) {
    if (!item.runs.some((run) => run.rubric)) {
      return `<section class="panel"><p>本 Case 未提供 Rubric 结果。</p></section>`;
    }
    return `
      <section class="panel">
        <h3>Rubric 双轨对照</h3>
        <div class="callout warning">
          Rubric 是可选分析旁路，不改变正式 quality_score、布尔判断或版本方向。
        </div>
        <div class="table-wrap" style="margin-top:14px">
          <table>
            <thead><tr><th>Run</th><th>旧分</th><th>Rubric</th><th>封顶</th><th>封顶原因</th><th>五维扣分</th></tr></thead>
            <tbody>
              ${item.runs.map((run) => `
                <tr>
                  <td>${esc(run.run_id)}</td>
                  <td>${esc(run.assessment.quality_score)}</td>
                  <td><strong>${esc(run.rubric?.rubric_score ?? "—")}</strong></td>
                  <td>${esc(run.rubric?.impact_cap ?? "—")}</td>
                  <td>${esc((run.rubric?.cap_reasons || []).map((reason) =>
                    `${reason.reason}（${reason.evidence_event_ids.join("、")}）`
                  ).join("；") || "—")}</td>
                  <td>${esc(Object.entries(run.rubric?.dimension_penalties || {})
                    .filter(([, value]) => value)
                    .map(([key, value]) => `${key}=${value}`)
                    .join("；") || "—")}</td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>
      </section>`;
  }

  function renderAnalysis(item) {
    const analysis = item.analysis;
    if (!analysis) {
      return `<section class="panel">
        <h3>事实 / 推断 / 未知</h3>
        <p>未提供 LLM 分析附录。</p>
        ${sourceUnknowns(item)}
      </section>`;
    }
    return `
      <section class="panel">
        <h3>事实</h3>
        ${analysisList(analysis.factual_findings, "fact")}
      </section>
      <section class="panel">
        <h3>推断</h3>
        ${analysisList(analysis.inferences, "inference")}
      </section>
      <section class="panel">
        <h3>未知</h3>
        ${analysisList(analysis.unknowns, "unknown")}
        ${sourceUnknowns(item)}
      </section>`;
  }

  function renderRaw(item) {
    const meta = data.metadata;
    return `
      <section class="panel">
        <h3>生成信息</h3>
        <dl class="kv">
          <dt>evaluator</dt><dd>${esc(meta.evaluator_version)}</dd>
          <dt>commit</dt><dd>${esc(meta.code_commit)}${meta.working_tree_dirty ? " (dirty)" : ""}</dd>
          <dt>generated at</dt><dd>${esc(meta.generated_at)}</dd>
          <dt>dataset</dt><dd>${esc(meta.dataset_version)}</dd>
          <dt>submission SHA256</dt><dd><code>${esc(meta.submission_sha256 || "—")}</code></dd>
        </dl>
      </section>
      <section class="panel">
        <h3>材料链接</h3>
        <div class="sidebar-foot">
          <a href="${attr(data.appendices.version_report)}">版本评测主报告</a>
          <a href="${attr(data.appendices.four_way_report)}">四源技术附录</a>
          ${data.appendices.llm_analysis
            ? `<a href="${attr(data.appendices.llm_analysis)}">LLM 分析附录</a>`
            : `<span>LLM 分析附录：未提供</span>`}
          <a href="${attr(data.appendices.validation_jsonl)}">validation JSONL</a>
          <a href="${attr(data.appendices.rubric_jsonl)}">Rubric JSONL</a>
        </div>
      </section>
      <section class="panel">
        <h3>原始 JSON 数据</h3>
        <div class="json-block">${esc(JSON.stringify(item, null, 2))}</div>
      </section>`;
  }

  function renderEvidence(item) {
    const groups = item.runs.map((run) => {
      const roots = run.assessment.root_causes || [];
      const evidenceIds = Array.from(new Set([
        ...roots.flatMap((root) => root.evidence_event_ids || []),
        ...(run.assessment.evidence_event_ids || []),
      ]));
      const events = evidenceIds
        .map((id) => run.events.find((event) => event.event_id === id))
        .filter(Boolean)
        .sort((left, right) => left.seq - right.seq);
      return { run, roots, events };
    });
    evidenceContent.innerHTML = groups.map(({ run, roots, events }) => `
      <section class="evidence-group">
        <h3>${esc(run.run_id)} ${badge(run.final_state, stateTone(run.final_state))}</h3>
        ${roots.length
          ? `<div class="case-flags" style="margin-bottom:8px">
              ${roots.map((root) => badge(root.label, "red")).join("")}
            </div>`
          : `<div class="evidence-note">未发现确定性根因；以下保留正式结论证据。</div>`}
        <div class="evidence-list" style="margin-top:8px">
          ${events.map((event) => `
            <a class="evidence-link" href="#" data-jump-event="${attr(event.event_id)}">
              <code>${esc(event.event_id)}</code>
              <span>${esc(event.step_id)} ${event.is_first_fault ? badge("首错", "red") : ""}</span>
              <small>${esc(event.step_status)} · ${esc(event.action || event.module || "")}</small>
            </a>`).join("") || `<div class="evidence-note">没有可回指事件。</div>`}
        </div>
      </section>`).join("");
    bindEventJumps(evidenceContent);
  }

  function bindEventJumps(root) {
    root.querySelectorAll("a[data-jump-event]").forEach((link) => {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        state.tab = "timeline";
        render();
        requestAnimationFrame(() => {
          const target = document.getElementById(
            `event-${link.dataset.jumpEvent}`
          );
          if (target) {
            target.open = true;
            target.scrollIntoView({ behavior: "smooth", block: "center" });
          }
        });
      });
    });
  }

  function rootTable(roots) {
    return `
      <div class="table-wrap"><table>
        <thead><tr><th>Run</th><th>根因</th><th>首错</th><th>解释</th><th>证据</th></tr></thead>
        <tbody>
          ${roots.map(({ run, root }) => `
            <tr>
              <td>${esc(run.run_id)}</td>
              <td>${badge(root.label, "red")}</td>
              <td><a href="#" data-jump-event="${attr(root.first_fault_event_id || "")}"><code>${esc(root.first_fault_event_id || "—")}</code></a></td>
              <td>${esc(root.explanation || "—")}</td>
              <td>${(root.evidence_event_ids || []).map((id) =>
                `<a href="#" data-jump-event="${attr(id)}"><code>${esc(id)}</code></a>`
              ).join("、") || "—"}</td>
            </tr>`).join("")}
        </tbody>
      </table></div>`;
  }

  function pairwiseTable() {
    const rows = data.pairwise || [];
    if (!rows.length) return "";
    return `
      <section class="panel">
        <h3>全局两两一致率</h3>
        <div class="table-wrap"><table>
          <thead><tr><th>来源对</th><th>方向</th><th>根因</th><th>首错</th><th>证据 Jaccard</th></tr></thead>
          <tbody>${rows.map((row) => `
            <tr>
              <td>${esc(sourceLabel(row.left))} vs ${esc(sourceLabel(row.right))}</td>
              <td>${ratio(row.direction_agreement)}</td>
              <td>${ratio(row.run_metrics?.root_causes)}</td>
              <td>${ratio(row.run_metrics?.first_faults)}</td>
              <td>${row.evidence_jaccard == null ? "—" : esc(row.evidence_jaccard)}</td>
            </tr>`).join("")}</tbody>
        </table></div>
      </section>`;
  }

  function analysisList(items, kind) {
    if (!Array.isArray(items) || !items.length) return "<p>无。</p>";
    return `<ul class="analysis-list ${kind}">${items.map((item) => `
      <li>${esc(item.statement || "")}
      ${item.confidence ? ` ${badge(`置信度 ${item.confidence}`, confidenceTone(item.confidence))}` : ""}
      ${item.basis ? `<div><small>依据：${esc(item.basis.join("；"))}</small></div>` : ""}
      ${item.missing_evidence ? `<div><small>缺少证据：${esc(item.missing_evidence)}</small></div>` : ""}
      </li>`).join("")}</ul>`;
  }

  function sourceUnknowns(item) {
    const four = item.four_way;
    if (!four) return "";
    const rows = Object.entries(four.sources || {}).flatMap(([key, value]) =>
      (value.unknowns || []).map((unknown) => [sourceLabel(key), unknown])
    );
    if (!rows.length) return "";
    return `<h4>来源未知项</h4><ul class="analysis-list unknown">${rows.map(([source, text]) =>
      `<li><strong>${esc(source)}</strong>：${esc(text)}</li>`
    ).join("")}</ul>`;
  }

  function recForCase(item) {
    const hasRoot = item.runs.some((run) => (run.assessment.root_causes || []).length);
    const capped = item.runs.some((run) => run.rubric?.impact_cap != null);
    if (capped) return { label: "高风险：影响封顶", tone: "red" };
    if (hasRoot) return { label: "存在规则违规", tone: "amber" };
    return { label: "未发现违规", tone: "green" };
  }

  function directionBadge(direction) {
    if (!direction) return badge("未提供", "");
    return badge(direction, directionTone(direction));
  }

  function directionTone(direction) {
    if (direction === "baseline_better") return "amber";
    if (direction === "candidate_better") return "blue";
    if (direction === "equal") return "green";
    return "red";
  }

  function stateTone(status) {
    if (!status) return "";
    if (status === "WAITING_USER") return "blue";
    if (status === "SUCCEEDED") return "green";
    return "red";
  }

  function confidenceTone(value) {
    if (value === "high") return "green";
    if (value === "medium") return "amber";
    return "";
  }

  function statusClass(status) {
    if (status === "SUCCEEDED") return "succeeded";
    if (status === "WAITING_USER") return "waiting";
    return "failed";
  }

  function sourceLabel(key) {
    return {
      deterministic: "确定性评测器",
      human: "独立复核",
      local_llm: "本地 LLM",
      cloud_llm: "云端 LLM",
    }[key] || key;
  }

  function ratio(value) {
    if (!value || !value.total) return "—";
    return `${value.agree}/${value.total} (${(value.rate * 100).toFixed(1)}%)`;
  }

  function boolText(value) {
    if (value === true) return badge("是", "green");
    if (value === false) return badge("否", "red");
    return badge("—", "");
  }

  function badge(text, tone = "") {
    return `<span class="badge ${tone}">${esc(text)}</span>`;
  }

  function defaultCase() {
    return data.cases.find((item) =>
      item.runs.some((run) => run.rubric?.impact_cap != null)
    ) || data.cases[0];
  }

  function validTab(value) {
    return ["summary", "timeline", "sources", "rubric", "analysis", "raw"].includes(value);
  }

  function parseHash() {
    const params = new URLSearchParams(location.hash.replace(/^#/, ""));
    return { case: params.get("case"), tab: params.get("tab") };
  }

  function getCase(caseId) {
    return data.cases.find((item) => item.case_id === caseId);
  }

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function attr(value) {
    return esc(value).replaceAll("`", "&#96;");
  }
})();
