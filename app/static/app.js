// Tab switching
function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach((btn) => btn.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach((content) => content.classList.remove("active"));

  if (tabId === "shorten-tab") {
    document.querySelectorAll(".tab-btn")[0].classList.add("active");
  } else {
    document.querySelectorAll(".tab-btn")[1].classList.add("active");
  }
  document.getElementById(tabId).classList.add("active");
}

// Shorten URL Form Handler
const shortenForm = document.getElementById("shorten-form");
const shortenBtn = document.getElementById("shorten-btn");
const shortenResult = document.getElementById("shorten-result");
const shortenError = document.getElementById("shorten-error");
const shortUrlOutput = document.getElementById("short-url-output");
const testRedirectLink = document.getElementById("test-redirect-link");
const shortenMeta = document.getElementById("shorten-meta");

shortenForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  shortenError.classList.add("hidden");
  shortenResult.classList.add("hidden");
  shortenBtn.disabled = true;
  shortenBtn.innerText = "Shortening...";

  const originalUrl = document.getElementById("long-url").value.trim();
  const customAlias = document.getElementById("custom-alias").value.trim() || null;
  const expiresInVal = document.getElementById("expires-in").value;
  const expiresInDays = expiresInVal ? parseInt(expiresInVal, 10) : null;

  try {
    const res = await fetch("/api/v1/shorten", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: originalUrl,
        custom_alias: customAlias,
        expires_in_days: expiresInDays,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      const msg = data.detail || (Array.isArray(data.detail) ? data.detail[0].msg : "Failed to shorten URL");
      throw new Error(msg);
    }

    // Determine short URL based on current origin
    const fullShortUrl = `${window.location.origin}/${data.short_code}`;
    shortUrlOutput.value = fullShortUrl;
    testRedirectLink.href = fullShortUrl;

    let meta = `Created at: ${new Date(data.created_at).toLocaleString()}`;
    if (data.expires_at) {
      meta += ` | Expires: ${new Date(data.expires_at).toLocaleString()}`;
    }
    shortenMeta.innerText = meta;

    shortenResult.classList.remove("hidden");
  } catch (err) {
    shortenError.innerText = err.message;
    shortenError.classList.remove("hidden");
  } finally {
    shortenBtn.disabled = false;
    shortenBtn.innerText = "Shorten URL";
  }
});

// Copy short link to clipboard
function copyShortUrl() {
  shortUrlOutput.select();
  navigator.clipboard.writeText(shortUrlOutput.value).then(() => {
    alert("Short URL copied to clipboard!");
  }).catch(() => {
    document.execCommand("copy");
    alert("Short URL copied!");
  });
}

// Analytics Form Handler
const analyticsForm = document.getElementById("analytics-form");
const analyticsError = document.getElementById("analytics-error");
const analyticsResult = document.getElementById("analytics-result");

analyticsForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  analyticsError.classList.add("hidden");
  analyticsResult.classList.add("hidden");

  let code = document.getElementById("analytics-code").value.trim();
  // Strip origin or path if full URL was pasted
  if (code.includes("/")) {
    code = code.split("/").filter(Boolean).pop();
  }

  try {
    const res = await fetch(`/api/v1/analytics/${code}`);
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Could not retrieve analytics for this code.");
    }

    document.getElementById("stat-total-clicks").innerText = data.total_clicks.toLocaleString();
    document.getElementById("stat-clicks-24h").innerText = data.clicks_last_24h.toLocaleString();

    renderBreakdown("list-referrers", data.top_referrers);
    renderBreakdown("list-browsers", data.top_browsers);
    renderBreakdown("list-os", data.top_os);

    renderRecentClicks(data.recent_clicks);

    analyticsResult.classList.remove("hidden");
  } catch (err) {
    analyticsError.innerText = err.message;
    analyticsError.classList.remove("hidden");
  }
});

function renderBreakdown(elementId, dictData) {
  const ul = document.getElementById(elementId);
  ul.innerHTML = "";
  const entries = Object.entries(dictData || {});
  if (entries.length === 0) {
    ul.innerHTML = "<li style='color: var(--text-muted)'>No data yet</li>";
    return;
  }
  for (const [key, count] of entries) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${escapeHtml(key)}</span><strong>${count}</strong>`;
    ul.appendChild(li);
  }
}

function renderRecentClicks(clicks) {
  const tbody = document.getElementById("table-recent-clicks");
  tbody.innerHTML = "";
  if (!clicks || clicks.length === 0) {
    tbody.innerHTML = "<tr><td colspan='5' style='text-align:center; color: var(--text-muted)'>No click records found</td></tr>";
    return;
  }

  clicks.forEach((c) => {
    const tr = document.createElement("tr");
    const dateStr = new Date(c.timestamp).toLocaleString();
    tr.innerHTML = `
      <td>${dateStr}</td>
      <td><code>${escapeHtml(c.ip_address || "N/A")}</code></td>
      <td>${escapeHtml(c.browser || "Unknown")}</td>
      <td>${escapeHtml(c.os || "Unknown")}</td>
      <td>${escapeHtml(c.referrer || "Direct")}</td>
    `;
    tbody.appendChild(tr);
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
