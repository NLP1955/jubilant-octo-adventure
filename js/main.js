// ===== STATE DATA =====
const stateData = {
  FL: {
    name: "Florida", flag: "🌴",
    agency: "Clerk of Court (per county)",
    deadline: "7 years from sale date",
    claimForm: "Motion to Disburse Surplus Funds",
    filingFee: "None (typically)",
    notes: "Florida is one of the most active states for surplus funds. Court retains funds; heirs can also claim.",
    difficulty: "medium",
    link: "https://www.myfloridacounty.com"
  },
  TX: {
    name: "Texas", flag: "⭐",
    agency: "County Tax Assessor-Collector",
    deadline: "2 years from deed recording",
    claimForm: "Application for Tax Sale Surplus",
    filingFee: "$0–$50 depending on county",
    notes: "Texas has a short 2-year window. Act fast. Heirs must provide probate documentation.",
    difficulty: "hard",
    link: "https://comptroller.texas.gov"
  },
  CA: {
    name: "California", flag: "🌅",
    agency: "County Tax Collector",
    deadline: "1 year from sale date",
    claimForm: "Claim for Excess Proceeds",
    filingFee: "None",
    notes: "California's deadline is strict at 1 year. Lienholders get priority over former owners.",
    difficulty: "hard",
    link: "https://www.boe.ca.gov"
  },
  GA: {
    name: "Georgia", flag: "🍑",
    agency: "Superior Court Clerk",
    deadline: "5 years",
    claimForm: "Petition for Excess Funds",
    filingFee: "Filing fee varies by county",
    notes: "Georgia requires a petition to the Superior Court. Many counties post excess funds lists online.",
    difficulty: "medium",
    link: "https://georgia.gov/taxes"
  },
  OH: {
    name: "Ohio", flag: "🌻",
    agency: "County Auditor / Common Pleas Court",
    deadline: "Indefinite (varies by county)",
    claimForm: "Application for Distribution of Excess Proceeds",
    filingFee: "Small court filing fee",
    notes: "Ohio counties hold surplus funds until claimed. Some post lists on county websites.",
    difficulty: "easy",
    link: "https://ohio.gov"
  },
  NC: {
    name: "North Carolina", flag: "🌲",
    agency: "County Finance Office",
    deadline: "No statutory limit",
    claimForm: "Application for Surplus Funds",
    filingFee: "None typically",
    notes: "NC is very claimant-friendly. Surplus funds are held indefinitely in most counties.",
    difficulty: "easy",
    link: "https://www.ncdor.gov"
  },
  NY: {
    name: "New York", flag: "🗽",
    agency: "County Treasurer / Supreme Court",
    deadline: "6 years (varies)",
    claimForm: "Petition for Surplus Money",
    filingFee: "Court filing fee required",
    notes: "NY has a complex court process. Legal assistance is highly recommended.",
    difficulty: "hard",
    link: "https://www.tax.ny.gov"
  },
  IL: {
    name: "Illinois", flag: "🌽",
    agency: "County Clerk or Circuit Court",
    deadline: "5 years from auction",
    claimForm: "Petition for Payment of Surplus",
    filingFee: "Circuit court filing fee",
    notes: "Illinois requires a court petition. Heirs must open probate if owner is deceased.",
    difficulty: "medium",
    link: "https://www.revenue.state.il.us"
  },
  AZ: {
    name: "Arizona", flag: "🌵",
    agency: "County Treasurer",
    deadline: "3 years",
    claimForm: "Application for Excess Proceeds",
    filingFee: "None",
    notes: "Arizona process is relatively straightforward. County treasurer holds excess proceeds.",
    difficulty: "easy",
    link: "https://azdor.gov"
  },
  MI: {
    name: "Michigan", flag: "⚓",
    agency: "County Treasurer",
    deadline: "6 months from sale (act fast!)",
    claimForm: "Claim for Excess Proceeds",
    filingFee: "None",
    notes: "Michigan has one of the shortest windows — only 6 months. Prichard v. Wayne County applies.",
    difficulty: "hard",
    link: "https://www.michigan.gov/treasury"
  }
};

const difficultyLabel = { easy: ["Easy", "green"], medium: ["Moderate", "gold"], hard: ["Complex", "red"] };

// ===== POPULATE STATE SELECT =====
function populateStateSelect() {
  const select = document.getElementById("stateSelect");
  if (!select) return;
  const sorted = Object.entries(stateData).sort((a, b) => a[1].name.localeCompare(b[1].name));
  sorted.forEach(([code, info]) => {
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = `${info.flag} ${info.name}`;
    select.appendChild(opt);
  });
  select.addEventListener("change", () => showStateResult(select.value));
}

function showStateResult(code) {
  const container = document.getElementById("stateResult");
  if (!container) return;
  if (!code) { container.classList.remove("active"); return; }
  const s = stateData[code];
  const [label, color] = difficultyLabel[s.difficulty];
  container.innerHTML = `
    <div class="state-result__header">
      <span style="font-size:2rem">${s.flag}</span>
      <div>
        <div class="state-result__name">${s.name}</div>
        <span class="badge badge--${color}">${label} Process</span>
      </div>
    </div>
    <table>
      <tr><th>Claim Deadline</th><td>${s.deadline}</td></tr>
      <tr><th>Filing Agency</th><td>${s.agency}</td></tr>
      <tr><th>Form / Petition</th><td>${s.claimForm}</td></tr>
      <tr><th>Filing Fee</th><td>${s.filingFee}</td></tr>
      <tr><th>Key Notes</th><td>${s.notes}</td></tr>
    </table>
    <p style="margin-top:1rem;font-size:.85rem;color:#555">
      <a href="${s.link}" target="_blank" rel="noopener" style="color:#1a7a4a;font-weight:600">
        → Visit ${s.name} Official Site
      </a>
    </p>
  `;
  container.classList.add("active");
}

// ===== EMAIL FORM =====
function initSubscribeForm() {
  const form = document.getElementById("subscribeForm");
  const msg  = document.getElementById("formMessage");
  if (!form) return;
  form.addEventListener("submit", e => {
    e.preventDefault();
    const name  = form.name.value.trim();
    const email = form.email.value.trim();
    if (!name || !email) return;
    // TODO: wire to MailerLite / your email provider
    msg.textContent = `Thanks ${name}! Check ${email} for your free guide. 🎉`;
    msg.className = "subscribe-form__message success";
    form.reset();
  });
}

// ===== MOBILE NAV =====
function initMobileNav() {
  const burger = document.querySelector(".nav__hamburger");
  const links  = document.querySelector(".nav__links");
  if (!burger || !links) return;
  burger.addEventListener("click", () => {
    const open = links.style.display === "flex";
    links.style.display = open ? "" : "flex";
    links.style.flexDirection = "column";
    links.style.position = "absolute";
    links.style.top = "60px";
    links.style.right = "1.5rem";
    links.style.background = "#fff";
    links.style.padding = "1rem";
    links.style.boxShadow = "0 4px 20px rgba(0,0,0,.12)";
    links.style.borderRadius = "8px";
    links.style.zIndex = "200";
  });
}

// ===== INIT =====
document.addEventListener("DOMContentLoaded", () => {
  populateStateSelect();
  initSubscribeForm();
  initMobileNav();
});
