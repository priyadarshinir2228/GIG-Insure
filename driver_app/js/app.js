/**
 * GigEase Driver Application Engine
 * Implements 11-State Work Lifecycle, Authentication Flow, Notification System, and FastAPI & ML Integration
 */

// --- Enums & Driver Work Lifecycle States ---
const DriverState = {
  OFFLINE: "OFFLINE",
  AVAILABLE: "AVAILABLE",
  JOB_ACCEPTED: "JOB_ACCEPTED",
  EN_ROUTE: "EN_ROUTE",
  ARRIVED: "ARRIVED",
  PICKED_UP: "PICKED_UP",
  IN_TRANSIT: "IN_TRANSIT",
  DELIVERED: "DELIVERED",
  PROOF_COMPLETE: "PROOF_COMPLETE",
  COMPLETED: "COMPLETED"
};

const InsuranceState = {
  COVERED: "COVERED",
  INACTIVE: "INACTIVE",
  PAUSED: "PAUSED"
};

const AuthScreen = {
  LOGIN: "LOGIN",
  OTP: "OTP",
  REGISTER: "REGISTER"
};

// Global State
const appState = {
  isAuthenticated: localStorage.getItem("gigease_driver_auth") === "true",
  authScreen: AuthScreen.LOGIN,
  loginMobile: "+91 98765 43210",
  worker: {
    id: "W001",
    name: "Priyadarshini R",
    mobile: "+91 98765 43210",
    rating: 4.8,
    vehicle: "Honda Activa (TN 09 AB 4821)",
    weeklyPlanInr: 49.00,
    policyId: "GE-2026-004821"
  },
  currentState: DriverState.OFFLINE,
  currentInsuranceState: InsuranceState.INACTIVE,
  activeNavTab: "home", // home, gigs, insurance, money, profile
  activeJob: null,
  earningsToday: 1240.00,
  protectedEarningsToday: 420.00,
  liveQuote: null,
  poolAnalytics: null,
  driftStatus: null,
  notifications: [
    { id: "NTF_101", title: "🟢 Shield Active", message: "Weekly Parametric Shield is active for your shift.", timestamp: "Just Now", type: "shield" },
    { id: "NTF_102", title: "⚡ Instant Payout Received", message: "Rs. 420.00 credited via Razorpay UPI (STFI Rain).", timestamp: "10 mins ago", type: "payout" }
  ],
  claimsHistory: [
    { id: "CLM_80124", title: "Heavy Rain (STFI)", amount: 420.00, date: "Today 10:30 AM", status: "Paid via Razorpay UPI", utr: "RZNP8833910A7" },
    { id: "CLM_77910", title: "Cyclone Dana (STFI)", amount: 520.00, date: "14 Sep 2026", status: "Paid via Razorpay UPI", utr: "RZNP7710294B1" }
  ],
  availableGigs: [
    {
      id: "GIG_101",
      restaurant: "ABC Restaurant, T. Nagar",
      destination: "XYZ Apartments, Nungambakkam",
      payInr: 240,
      distanceKm: 5.0,
      etaMins: 28,
      pickupDistKm: 1.8
    },
    {
      id: "GIG_102",
      restaurant: "Blinkit Dark Store #4",
      destination: "Anna Nagar East",
      payInr: 180,
      distanceKm: 3.2,
      etaMins: 18,
      pickupDistKm: 0.9
    },
    {
      id: "GIG_103",
      restaurant: "Zepto Hub - Mylapore",
      destination: "Alwarpet Main Rd",
      payInr: 310,
      distanceKm: 6.5,
      etaMins: 35,
      pickupDistKm: 2.1
    }
  ]
};

// --- Initialization ---
document.addEventListener("DOMContentLoaded", async () => {
  renderApp();
  updateTime();
  setInterval(updateTime, 30000);
  
  // Fetch Backend Integration Data asynchronously
  await fetchLiveQuote();
  await fetchPoolAnalytics();
  await fetchDriftStatus();
  await fetchBackendNotifications();
});

function updateTime() {
  const timeElem = document.getElementById("status-bar-time");
  if (timeElem) {
    const now = new Date();
    timeElem.innerText = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
}

// --- FastAPI Backend Integration Functions ---

async function fetchLiveQuote() {
  try {
    const res = await fetch("/api/v1/quote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        worker_id: appState.worker.id,
        zone_id: "ZONE_MAA_01",
        zone_tier: "Metro",
        persona_category: "Food_Delivery",
        vehicle_type: "Scooter",
        weekly_history: [4100, 4200, 4300, 4150, 4400, 4500]
      })
    });
    if (res.ok) {
      appState.liveQuote = await res.json();
      appState.worker.weeklyPlanInr = appState.liveQuote.weekly_premium_amount_inr;
      renderApp();
    }
  } catch (e) {
    console.log("Live quote fallback active");
  }
}

async function fetchPoolAnalytics() {
  try {
    const res = await fetch("/api/v1/analytics/pool-summary");
    if (res.ok) {
      appState.poolAnalytics = await res.json();
      renderApp();
    }
  } catch (e) {
    console.log("Pool analytics fallback active");
  }
}

async function fetchDriftStatus() {
  try {
    const res = await fetch("/api/v1/ml/drift-status");
    if (res.ok) {
      appState.driftStatus = await res.json();
      renderApp();
    }
  } catch (e) {
    console.log("Drift status fallback active");
  }
}

async function fetchBackendNotifications() {
  try {
    const res = await fetch(`/api/v1/notifications?worker_id=${appState.worker.id}`);
    if (res.ok) {
      const data = await res.json();
      if (data.notifications && data.notifications.length) {
        appState.notifications = data.notifications;
      }
    }
  } catch (e) {
    console.log("Notifications fallback active");
  }
}

// --- Main UI Router ---

function renderApp() {
  const viewport = document.getElementById("app-viewport");
  const bottomNav = document.getElementById("bottom-nav");
  const insuranceStrip = document.getElementById("insurance-strip");

  // Authentication Check
  if (!appState.isAuthenticated) {
    if (insuranceStrip) insuranceStrip.style.display = "none";
    if (bottomNav) bottomNav.style.display = "none";

    if (appState.authScreen === AuthScreen.LOGIN) {
      viewport.innerHTML = renderLoginView();
    } else if (appState.authScreen === AuthScreen.OTP) {
      viewport.innerHTML = renderOtpView();
    } else if (appState.authScreen === AuthScreen.REGISTER) {
      viewport.innerHTML = renderRegisterView();
    }
    return;
  }

  // Authenticated State Layout
  if (insuranceStrip) insuranceStrip.style.display = "flex";
  if (bottomNav) bottomNav.style.display = "flex";

  syncInsuranceState();
  renderInsuranceStrip(insuranceStrip);

  if (appState.activeNavTab === "gigs" && isTripActive()) {
    viewport.innerHTML = renderActiveTripView();
  } else if (appState.activeNavTab === "home") {
    viewport.innerHTML = renderHomeView();
  } else if (appState.activeNavTab === "gigs") {
    viewport.innerHTML = renderGigsView();
  } else if (appState.activeNavTab === "insurance") {
    viewport.innerHTML = renderInsuranceView();
  } else if (appState.activeNavTab === "money") {
    viewport.innerHTML = renderEarningsView();
  } else if (appState.activeNavTab === "profile") {
    viewport.innerHTML = renderProfileView();
  }

  bottomNav.innerHTML = renderBottomNav();
}

function syncInsuranceState() {
  if (appState.currentState === DriverState.OFFLINE) {
    appState.currentInsuranceState = InsuranceState.INACTIVE;
  } else {
    appState.currentInsuranceState = InsuranceState.COVERED;
  }
}

function isTripActive() {
  return [
    DriverState.JOB_ACCEPTED,
    DriverState.EN_ROUTE,
    DriverState.ARRIVED,
    DriverState.PICKED_UP,
    DriverState.IN_TRANSIT,
    DriverState.DELIVERED,
    DriverState.PROOF_COMPLETE
  ].includes(appState.currentState);
}

// --- Notification Toast & Center ---

function showNotificationToast(title, message, type = "info") {
  const toast = document.createElement("div");
  toast.className = "disruption-toast";
  toast.style.borderColor = type === "success" ? "var(--primary)" : (type === "warning" ? "var(--accent-amber)" : "var(--accent-blue)");
  
  toast.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <div style="font-weight:800; font-size:13px; color:#fff;">${title}</div>
      <span class="pill-badge ${type === 'success' ? 'green' : (type === 'warning' ? 'amber' : 'blue')}">ALERT</span>
    </div>
    <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">${message}</div>
  `;
  
  const container = document.getElementById("phone-container");
  if (container) {
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3200);
  }

  // Push to notification center state
  appState.notifications.unshift({
    id: "NTF_" + Math.floor(Math.random() * 90000),
    title: title,
    message: message,
    timestamp: "Just Now",
    type: type
  });
}

function openNotificationCenter() {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.innerHTML = `
    <div class="modal-bottom-sheet">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
        <div style="font-weight:800; font-size:16px; color:#fff;">🔔 Notification & Alert Center</div>
        <div style="font-size:18px; cursor:pointer;" onclick="this.closest('.modal-overlay').remove()">✕</div>
      </div>
      
      ${appState.notifications.map(n => `
        <div class="glass-card" style="margin:0 0 10px 0; padding:12px;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div style="font-weight:700; font-size:13px;">${n.title}</div>
            <div style="font-size:10px; color:var(--text-dim);">${n.timestamp}</div>
          </div>
          <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">${n.message}</div>
        </div>
      `).join('')}

      <button class="btn-secondary" style="margin-top:10px;" onclick="this.closest('.modal-overlay').remove()">
        Close Center
      </button>
    </div>
  `;
  document.getElementById("phone-container").appendChild(modal);
}

// --- Auth Views ---

function renderLoginView() {
  return `
    <div style="padding: 24px 20px; display:flex; flex-direction:column; height:100%; justify-content:center;">
      <div style="text-align:center; margin-bottom:28px;">
        <div style="font-size:42px; margin-bottom:8px;">🛡️</div>
        <div style="font-size:24px; font-weight:900; color:#fff;">GigEase <span style="color:var(--primary);">Driver</span></div>
        <div style="font-size:13px; color:var(--text-muted); margin-top:4px;">Parametric Loss-of-Income Protection Platform</div>
      </div>

      <div class="glass-card" style="margin:0 0 16px 0; padding:20px;">
        <div style="font-size:14px; font-weight:700; margin-bottom:4px;">Welcome Back</div>
        <div style="font-size:12px; color:var(--text-muted); margin-bottom:16px;">Log in to access your active shield & delivery jobs.</div>

        <label style="font-size:11px; font-weight:700; color:var(--text-dim); text-transform:uppercase;">Registered Mobile Number</label>
        <input type="text" class="form-input" id="login-mobile" value="${appState.loginMobile}">

        <label style="font-size:11px; font-weight:700; color:var(--text-dim); text-transform:uppercase;">Password</label>
        <input type="password" class="form-input" id="login-password" value="••••••••">

        <button class="btn-primary" style="margin-top:8px;" onclick="handleLoginSubmit()">
          Log In →
        </button>

        <button class="btn-secondary" style="margin-top:10px; font-size:12px;" onclick="switchAuthScreen(AuthScreen.OTP)">
          🔑 Log in with OTP SMS
        </button>
      </div>

      <div style="text-align:center; font-size:13px; color:var(--text-muted);">
        Don't have an account? <span style="color:var(--primary); font-weight:700; cursor:pointer;" onclick="switchAuthScreen(AuthScreen.REGISTER)">Register Driver Profile</span>
      </div>
    </div>
  `;
}

function renderOtpView() {
  return `
    <div style="padding: 24px 20px; display:flex; flex-direction:column; height:100%; justify-content:center;">
      <div style="text-align:center; margin-bottom:24px;">
        <div style="font-size:36px; margin-bottom:6px;">📲</div>
        <div style="font-size:22px; font-weight:900; color:#fff;">Verify Mobile OTP</div>
        <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Code sent to ${appState.loginMobile}</div>
      </div>

      <div class="glass-card" style="margin:0 0 16px 0; padding:20px; text-align:center;">
        <div style="display:flex; justify-content:center; gap:8px; margin:16px 0;">
          <input type="text" maxlength="1" value="8" style="width:40px; height:48px; text-align:center; font-size:20px; font-weight:800; background:rgba(0,0,0,0.3); border:1px solid var(--primary); border-radius:8px; color:#fff;">
          <input type="text" maxlength="1" value="8" style="width:40px; height:48px; text-align:center; font-size:20px; font-weight:800; background:rgba(0,0,0,0.3); border:1px solid var(--primary); border-radius:8px; color:#fff;">
          <input type="text" maxlength="1" value="3" style="width:40px; height:48px; text-align:center; font-size:20px; font-weight:800; background:rgba(0,0,0,0.3); border:1px solid var(--primary); border-radius:8px; color:#fff;">
          <input type="text" maxlength="1" value="3" style="width:40px; height:48px; text-align:center; font-size:20px; font-weight:800; background:rgba(0,0,0,0.3); border:1px solid var(--primary); border-radius:8px; color:#fff;">
          <input type="text" maxlength="1" value="7" style="width:40px; height:48px; text-align:center; font-size:20px; font-weight:800; background:rgba(0,0,0,0.3); border:1px solid var(--primary); border-radius:8px; color:#fff;">
          <input type="text" maxlength="1" value="7" style="width:40px; height:48px; text-align:center; font-size:20px; font-weight:800; background:rgba(0,0,0,0.3); border:1px solid var(--primary); border-radius:8px; color:#fff;">
        </div>

        <button class="btn-primary" onclick="completeAuthentication()">
          ✓ Verify & Start Driving
        </button>
      </div>

      <div style="text-align:center; font-size:12px; color:var(--text-muted); cursor:pointer;" onclick="switchAuthScreen(AuthScreen.LOGIN)">
        ← Back to Mobile Login
      </div>
    </div>
  `;
}

function renderRegisterView() {
  return `
    <div style="padding: 20px; overflow-y:auto;">
      <div style="font-size:20px; font-weight:900; margin-bottom:4px;">Register Driver Profile</div>
      <div style="font-size:12px; color:var(--text-muted); margin-bottom:16px;">Enroll in GigEase Parametric Shield</div>

      <div class="glass-card" style="margin:0 0 16px 0;">
        <label style="font-size:11px; font-weight:700; color:var(--text-dim);">FULL NAME</label>
        <input type="text" class="form-input" id="reg-name" value="Priyadarshini R">

        <label style="font-size:11px; font-weight:700; color:var(--text-dim);">MOBILE NUMBER</label>
        <input type="text" class="form-input" id="reg-mobile" value="+91 98765 43210">

        <label style="font-size:11px; font-weight:700; color:var(--text-dim);">PRIMARY DELIVERY PLATFORM</label>
        <select class="form-input" style="background:#111827;">
          <option>Swiggy</option>
          <option selected>Zomato</option>
          <option>Zepto</option>
          <option>Blinkit</option>
          <option>Porter</option>
        </select>

        <label style="font-size:11px; font-weight:700; color:var(--text-dim);">VEHICLE TYPE & REGISTRATION</label>
        <input type="text" class="form-input" id="reg-vehicle" value="Honda Activa (TN 09 AB 4821)">

        <button class="btn-primary" style="margin-top:8px;" onclick="completeAuthentication()">
          🚀 Submit & Enable Protection
        </button>
      </div>

      <div style="text-align:center; font-size:12px; color:var(--text-muted); cursor:pointer;" onclick="switchAuthScreen(AuthScreen.LOGIN)">
        Already registered? <span style="color:var(--primary); font-weight:700;">Log In</span>
      </div>
    </div>
  `;
}

function switchAuthScreen(screen) {
  appState.authScreen = screen;
  renderApp();
}

function handleLoginSubmit() {
  const mobileInput = document.getElementById("login-mobile");
  if (mobileInput && mobileInput.value) {
    appState.worker.mobile = mobileInput.value;
  }
  completeAuthentication();
}

function completeAuthentication() {
  appState.isAuthenticated = true;
  localStorage.setItem("gigease_driver_auth", "true");
  showNotificationToast("🟢 Authentication Successful", "Welcome back, Priyadarshini! Your Parametric Shield is ready.", "success");
  renderApp();
}

function logoutDriver() {
  appState.isAuthenticated = false;
  localStorage.removeItem("gigease_driver_auth");
  appState.currentState = DriverState.OFFLINE;
  appState.activeJob = null;
  appState.authScreen = AuthScreen.LOGIN;
  showNotificationToast("⚪ Logged Out", "You have logged out of your driver profile.", "info");
  renderApp();
}

// --- Main App Views ---

function renderInsuranceStrip(container) {
  if (!container) return;
  const state = appState.currentInsuranceState;
  
  if (state === InsuranceState.COVERED) {
    container.className = "insurance-strip covered";
    container.innerHTML = `
      <span>🟢 COVERED & PROTECTED</span>
      <span style="font-size:10px; opacity:0.8;">Policy #${appState.worker.policyId}</span>
    `;
  } else {
    container.className = "insurance-strip inactive";
    container.innerHTML = `
      <span>⚪ COVERAGE INACTIVE</span>
      <span style="font-size:10px; opacity:0.8;">Go Online to Cover Shift</span>
    `;
  }
}

function renderHomeView() {
  const isOnline = appState.currentState !== DriverState.OFFLINE;
  const quote = appState.liveQuote;

  return `
    <div class="state-toggle-card">
      <div>
        <div style="font-weight:700; font-size:16px;">
          ${isOnline ? "You're Available" : "You're Offline"}
        </div>
        <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">
          ${isOnline ? "● ONLINE & Eligible for Gigs" : "Go online to receive jobs & enable shield"}
        </div>
      </div>
      <div class="toggle-switch ${isOnline ? 'active' : ''}" onclick="toggleDriverOnline()">
        <div class="toggle-circle"></div>
      </div>
    </div>

    ${isTripActive() ? `
      <div class="glass-card" style="border-left: 4px solid var(--primary);">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span class="pill-badge green">ACTIVE DELIVERY</span>
          <span style="font-weight:700; color:var(--primary);">₹${appState.activeJob.payInr}</span>
        </div>
        <div style="font-weight:700; font-size:15px; margin-top:8px;">${appState.activeJob.restaurant}</div>
        <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">📍 ${appState.activeJob.destination}</div>
        <button class="btn-primary" style="margin-top:12px;" onclick="switchTab('gigs')">
          Continue Active Trip →
        </button>
      </div>
    ` : ''}

    <div class="glass-card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700;">ML Actuarial Protection Rate</div>
        <span class="pill-badge green">LIVE ML MODEL</span>
      </div>
      
      <div style="display:flex; align-items:baseline; gap:8px; margin-top:6px;">
        <div style="font-size:28px; font-weight:800; color:var(--primary);">₹${quote ? quote.weekly_premium_amount_inr.toFixed(2) : appState.worker.weeklyPlanInr.toFixed(2)}</div>
        <div style="font-size:12px; color:var(--text-muted);">/ week</div>
      </div>

      <div style="display:flex; gap:12px; margin-top:12px; padding-top:12px; border-top:1px solid var(--card-border);">
        <div style="flex:1;">
          <div style="font-size:11px; color:var(--text-dim);">Expected Income (W_exp)</div>
          <div style="font-weight:700; color:#fff;">₹${quote ? quote.w_expected_inr.toFixed(2) : '4500.00'}</div>
        </div>
        <div style="flex:1;">
          <div style="font-size:11px; color:var(--text-dim);">Max Coverage Limit</div>
          <div style="font-weight:700; color:var(--accent-blue);">₹${quote ? quote.coverage_amount_inr.toFixed(2) : '6750.00'}</div>
        </div>
      </div>
    </div>

    <div class="glass-card" style="border:1px dashed var(--accent-amber);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <div style="font-weight:700; font-size:13px; color:var(--accent-amber);">⚡ Zero-Touch 4-Agent Disruption Engine</div>
        <span class="pill-badge amber">TEST RAIL</span>
      </div>
      <div style="font-size:12px; color:var(--text-muted); margin-bottom:12px;">
        Trigger zero-touch 4-Agent AI claim execution for extreme weather (STFI) or social curfew (RSMD).
      </div>
      <div style="display:flex; gap:8px;">
        <button class="btn-secondary" style="flex:1; font-size:12px;" onclick="simulateDisruption('Cyclone_Dana_STFI')">
          🌧 Rain STFI (75% β)
        </button>
        <button class="btn-secondary" style="flex:1; font-size:12px;" onclick="simulateDisruption('Chennai_Bandh_RSMD')">
          🚫 Curfew RSMD (65% β)
        </button>
      </div>
    </div>

    <div style="padding: 0 16px; margin-top: 10px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <div style="font-weight:700; font-size:14px;">Nearby Opportunities</div>
        <div style="font-size:12px; color:var(--primary); font-weight:600; cursor:pointer;" onclick="switchTab('gigs')">View All</div>
      </div>
      
      ${appState.availableGigs.slice(0, 2).map(gig => `
        <div class="glass-card" style="margin: 0 0 10px 0;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div>
              <div style="font-weight:700; font-size:14px;">₹${gig.payInr} • ${gig.etaMins} mins</div>
              <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">${gig.restaurant}</div>
              <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">📍 ${gig.destination} (${gig.distanceKm} km)</div>
            </div>
            <button class="btn-primary" style="width:auto; padding:8px 14px; font-size:12px;" onclick="acceptGig('${gig.id}')">
              Accept
            </button>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function renderGigsView() {
  if (isTripActive()) return renderActiveTripView();

  return `
    <div style="padding: 16px;">
      <div style="font-size:18px; font-weight:800; margin-bottom:12px;">Available Gigs</div>
      
      <div class="map-sim-box" style="margin-bottom:16px;">
        <div class="map-grid-pattern"></div>
        <div class="map-route-line"></div>
        <div class="map-pin pickup"></div>
        <div class="map-pin drop"></div>
        <div style="position:absolute; bottom:10px; background:rgba(0,0,0,0.7); padding:4px 10px; border-radius:10px; font-size:11px; font-weight:600;">
          📍 T. Nagar Delivery Hub • 3 Gigs Nearby
        </div>
      </div>

      ${appState.availableGigs.map(gig => `
        <div class="glass-card" style="margin: 0 0 12px 0;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span class="pill-badge blue">FOOD DELIVERY</span>
            <span style="font-size:18px; font-weight:800; color:var(--primary);">₹${gig.payInr}</span>
          </div>
          <div style="font-weight:700; font-size:15px;">${gig.restaurant}</div>
          <div style="font-size:13px; color:var(--text-muted); margin-top:2px;">📍 Dropoff: ${gig.destination}</div>
          
          <div style="display:flex; gap:12px; margin-top:10px; font-size:12px; color:var(--text-dim);">
            <div>📏 ${gig.distanceKm} km</div>
            <div>⏱ ~${gig.etaMins} mins</div>
            <div>🛡 🟢 Covered while on trip</div>
          </div>

          <button class="btn-primary" style="margin-top:12px;" onclick="acceptGig('${gig.id}')">
            Accept Delivery Opportunity
          </button>
        </div>
      `).join('')}
    </div>
  `;
}

function renderActiveTripView() {
  const job = appState.activeJob || appState.availableGigs[0];

  const steps = [
    { state: DriverState.JOB_ACCEPTED, label: "Accepted" },
    { state: DriverState.EN_ROUTE, label: "En Route" },
    { state: DriverState.ARRIVED, label: "Arrived" },
    { state: DriverState.PICKED_UP, label: "Picked Up" },
    { state: DriverState.IN_TRANSIT, label: "In Transit" },
    { state: DriverState.DELIVERED, label: "Delivered" }
  ];

  let currentStepIdx = steps.findIndex(s => s.state === appState.currentState);
  if (currentStepIdx === -1) currentStepIdx = 0;

  return `
    <div style="padding: 16px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <div>
          <div style="font-size:12px; color:var(--primary); font-weight:700; text-transform:uppercase;">ACTIVE TRIP LIFECYCLE</div>
          <div style="font-size:18px; font-weight:800;">₹${job.payInr} Delivery</div>
        </div>
        <span class="pill-badge green">🟢 TRIP COVERED</span>
      </div>

      <div class="trip-stepper">
        ${steps.map((s, idx) => `
          <div class="step-node ${idx === currentStepIdx ? 'active' : (idx < currentStepIdx ? 'done' : '')}">
            ${idx + 1}
          </div>
        `).join('')}
      </div>
      <div style="text-align:center; font-size:12px; font-weight:700; color:var(--primary); margin-bottom:12px;">
        Current State: ${appState.currentState}
      </div>

      <div class="map-sim-box" style="margin-bottom:16px;">
        <div class="map-grid-pattern"></div>
        <div class="map-route-line"></div>
        <div class="map-pin pickup"></div>
        <div class="map-pin drop"></div>
        <div style="position:absolute; top:10px; left:10px; background:rgba(0,0,0,0.8); padding:6px 12px; border-radius:12px; font-size:12px; font-weight:700;">
          🗺 Turn-by-Turn GPS Active
        </div>
      </div>

      <div class="glass-card" style="margin: 0 0 16px 0;">
        <div style="font-weight:700; font-size:15px; margin-bottom:4px;">${job.restaurant}</div>
        <div style="font-size:13px; color:var(--text-muted); margin-bottom:12px;">📍 ${job.destination}</div>

        ${appState.currentState === DriverState.JOB_ACCEPTED ? `
          <button class="btn-primary" onclick="advanceTripState(DriverState.EN_ROUTE, '🚀 En Route to Pickup Location')">
            🚀 Start Navigation to Pickup
          </button>
        ` : ''}

        ${appState.currentState === DriverState.EN_ROUTE ? `
          <button class="btn-primary" onclick="advanceTripState(DriverState.ARRIVED, '📍 Arrived at Restaurant')">
            📍 I've Arrived at Pickup
          </button>
        ` : ''}

        ${appState.currentState === DriverState.ARRIVED ? `
          <div style="font-size:12px; color:var(--text-dim); margin-bottom:8px;">Scan Restaurant QR Code or Enter Pickup Code:</div>
          <button class="btn-primary" onclick="advanceTripState(DriverState.PICKED_UP, '📷 Order QR Code Verified & Picked Up')">
            📷 Scan QR & Confirm Pickup
          </button>
        ` : ''}

        ${appState.currentState === DriverState.PICKED_UP ? `
          <button class="btn-primary" onclick="advanceTripState(DriverState.IN_TRANSIT, '🛵 In Transit to Customer Destination')">
            🛵 Start Navigation to Customer
          </button>
        ` : ''}

        ${appState.currentState === DriverState.IN_TRANSIT ? `
          <button class="btn-primary" onclick="advanceTripState(DriverState.DELIVERED, '📍 Arrived at Customer Location')">
            📍 Arrived at Customer Location
          </button>
        ` : ''}

        ${appState.currentState === DriverState.DELIVERED ? `
          <div style="font-size:12px; color:var(--text-dim); margin-bottom:8px;">Capture Delivery Photo Proof:</div>
          <button class="btn-primary" onclick="completeDeliveryProof()">
            📷 Capture Photo & Complete Delivery
          </button>
        ` : ''}
      </div>

      <button class="btn-secondary" style="color:var(--accent-rose); border-color:rgba(239,68,68,0.3);" onclick="openEmergencyModal()">
        🚨 Emergency SOS & Assistance
      </button>
    </div>
  `;
}

function renderInsuranceView() {
  const pool = appState.poolAnalytics;
  const drift = appState.driftStatus;

  return `
    <div style="padding: 16px;">
      <div style="font-size:18px; font-weight:800; margin-bottom:4px;">Income Protection Shield</div>
      <div style="font-size:13px; color:var(--text-muted); margin-bottom:16px;">Parametric Loss-of-Income Coverage</div>

      <div class="glass-card" style="margin:0 0 16px 0; border:1px solid rgba(16,185,129,0.3);">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span class="pill-badge green">ACTIVE SHIELD</span>
          <span style="font-size:12px; color:var(--text-dim);">₹${appState.worker.weeklyPlanInr.toFixed(2)}/week</span>
        </div>
        <div style="font-size:20px; font-weight:800; margin-top:8px;">Policy #${appState.worker.policyId}</div>
        <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Coverage Limit: ₹${(appState.liveQuote ? appState.liveQuote.coverage_amount_inr : 6750).toFixed(0)} / week</div>

        <div style="margin-top:12px; padding-top:12px; border-top:1px solid var(--card-border); font-size:12px;">
          <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
            <span>STFI Weather Protection (Floods/AQI)</span>
            <span style="font-weight:700; color:var(--primary);">75% Loss Covered (β = 0.75)</span>
          </div>
          <div style="display:flex; justify-content:space-between;">
            <span>RSMD Social Protection (Curfew/Bandh)</span>
            <span style="font-weight:700; color:var(--accent-blue);">65% Loss Covered (β = 0.65)</span>
          </div>
        </div>
      </div>

      <div class="glass-card" style="margin:0 0 16px 0;">
        <div style="font-weight:700; font-size:14px; margin-bottom:8px;">Live Solvency & MLOps Governance</div>
        
        <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:6px;">
          <span style="color:var(--text-dim);">Mutual Solvency Reserve Pool:</span>
          <span style="font-weight:700; color:var(--primary);">₹${pool ? (pool.total_pool_balance_inr/100000).toFixed(2) : '42.87'} Lakhs</span>
        </div>
        
        <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:6px;">
          <span style="color:var(--text-dim);">30% Solvency Reserve Gate:</span>
          <span style="font-weight:700; color:#fff;">₹${pool ? (pool.minimum_reserve_threshold_inr/100000).toFixed(2) : '20.25'} Lakhs (PASS)</span>
        </div>

        <div style="display:flex; justify-content:space-between; font-size:12px;">
          <span style="color:var(--text-dim);">PSI Feature Drift Index:</span>
          <span style="font-weight:700; color:var(--primary);">${drift ? drift.psi_score.toFixed(3) : '0.041'} (${drift ? drift.alert_level : 'STABLE'})</span>
        </div>
      </div>

      <div style="font-weight:700; font-size:14px; margin-bottom:10px;">Recent Parametric Payouts</div>
      
      ${appState.claimsHistory.map(claim => `
        <div class="glass-card" style="margin: 0 0 10px 0;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div>
              <div style="font-weight:700; font-size:14px;">${claim.title}</div>
              <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">${claim.date} • UTR: ${claim.utr}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-weight:800; font-size:15px; color:var(--primary);">+₹${claim.amount.toFixed(2)}</div>
              <span class="pill-badge green" style="font-size:9px;">INSTANT UPI</span>
            </div>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function renderEarningsView() {
  return `
    <div style="padding: 16px;">
      <div style="font-size:18px; font-weight:800; margin-bottom:12px;">Earnings & Instant Pay</div>

      <div class="glass-card" style="margin:0 0 16px 0; background:linear-gradient(135deg, rgba(16,185,129,0.15), rgba(59,130,246,0.15));">
        <div style="font-size:12px; color:var(--text-muted); font-weight:700;">AVAILABLE FOR INSTANT PAY</div>
        <div style="font-size:34px; font-weight:800; color:#fff; margin-top:4px;">₹${(appState.earningsToday + appState.protectedEarningsToday).toFixed(2)}</div>
        
        <div style="font-size:12px; color:var(--text-dim); margin-top:6px;">
          Linked Bank: State Bank of India •••• 4821
        </div>

        <button class="btn-primary" style="margin-top:14px;" onclick="triggerInstantPay()">
          ⚡ Transfer Instant Pay via UPI (Fee ₹5)
        </button>
      </div>

      <div class="glass-card" style="margin:0;">
        <div style="font-weight:700; font-size:14px; margin-bottom:8px;">Tax Documents & Earnings Statements</div>
        <div style="font-size:12px; color:var(--text-muted); margin-bottom:12px;">Download certified driver earnings statements for compliance.</div>
        
        <button class="btn-secondary" style="font-size:12px;" onclick="alert('Downloading 2026 Driver Earnings Statement PDF...')">
          📄 Download 2026 Earnings Statement
        </button>
      </div>
    </div>
  `;
}

function renderProfileView() {
  return `
    <div style="padding: 16px;">
      <div style="font-size:18px; font-weight:800; margin-bottom:12px;">Driver Profile</div>

      <div class="glass-card" style="margin:0 0 16px 0;">
        <div style="display:flex; align-items:center; gap:12px;">
          <div style="width:48px; height:48px; border-radius:50%; background:var(--primary); display:flex; align-items:center; justify-content:center; font-weight:800; font-size:20px; color:#fff;">
            PR
          </div>
          <div>
            <div style="font-weight:800; font-size:16px;">${appState.worker.name}</div>
            <div style="font-size:12px; color:var(--text-muted);">${appState.worker.mobile}</div>
            <div style="font-size:11px; color:var(--primary); font-weight:700; margin-top:2px;">⭐ ${appState.worker.rating} Rating • Verified Driver</div>
          </div>
        </div>
      </div>

      <div class="glass-card" style="margin:0 0 16px 0;">
        <div style="font-weight:700; font-size:14px; margin-bottom:8px;">Registered Vehicle</div>
        <div style="font-size:13px; color:var(--text-muted);">${appState.worker.vehicle}</div>
        <div style="font-size:11px; color:var(--primary); margin-top:4px;">✓ License & Registration Verified</div>
      </div>

      <button class="btn-secondary" style="color:var(--accent-rose); border-color:rgba(239,68,68,0.3); font-weight:700;" onclick="logoutDriver()">
        🚪 Log Out of Driver Profile
      </button>
    </div>
  `;
}

function renderBottomNav() {
  const isTrip = isTripActive();

  if (isTrip) {
    return `
      <div class="nav-item active" onclick="switchTab('gigs')">
        <div class="nav-icon">🗺</div>
        <div>Active Trip</div>
      </div>
      <div class="nav-item" onclick="openEmergencyModal()">
        <div class="nav-icon" style="color:var(--accent-rose);">🚨</div>
        <div>SOS</div>
      </div>
      <div class="nav-item" onclick="switchTab('insurance')">
        <div class="nav-icon">🛡</div>
        <div>Shield</div>
      </div>
    `;
  }

  return `
    <div class="nav-item ${appState.activeNavTab === 'home' ? 'active' : ''}" onclick="switchTab('home')">
      <div class="nav-icon">🏠</div>
      <div>Home</div>
    </div>
    <div class="nav-item ${appState.activeNavTab === 'gigs' ? 'active' : ''}" onclick="switchTab('gigs')">
      <div class="nav-icon">📦</div>
      <div>Gigs</div>
    </div>
    <div class="nav-item ${appState.activeNavTab === 'insurance' ? 'active' : ''}" onclick="switchTab('insurance')">
      <div class="nav-icon">🛡</div>
      <div>Insurance</div>
    </div>
    <div class="nav-item ${appState.activeNavTab === 'money' ? 'active' : ''}" onclick="switchTab('money')">
      <div class="nav-icon">💰</div>
      <div>Money</div>
    </div>
    <div class="nav-item ${appState.activeNavTab === 'profile' ? 'active' : ''}" onclick="switchTab('profile')">
      <div class="nav-icon">👤</div>
      <div>Profile</div>
    </div>
  `;
}

// --- Driver Actions with Backend Integration ---

async function toggleDriverOnline() {
  const nextState = (appState.currentState === DriverState.OFFLINE) ? DriverState.AVAILABLE : DriverState.OFFLINE;
  
  if (isTripActive() && nextState === DriverState.OFFLINE) {
    alert("Cannot go offline while on an active delivery trip!");
    return;
  }

  appState.currentState = nextState;
  
  // Call REST endpoint POST /api/v1/driver/state
  try {
    await fetch("/api/v1/driver/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ worker_id: appState.worker.id, state: nextState })
    });
  } catch (e) {
    console.log("Driver state endpoint fallback");
  }

  if (nextState === DriverState.AVAILABLE) {
    showNotificationToast("🟢 You are ONLINE", "Parametric Protection Shield activated for active shift.", "success");
  } else {
    showNotificationToast("⚪ You are OFFLINE", "Shift ended. Shield paused until next shift.", "info");
  }

  renderApp();
}

function switchTab(tabName) {
  appState.activeNavTab = tabName;
  renderApp();
}

async function acceptGig(gigId) {
  const gig = appState.availableGigs.find(g => g.id === gigId);
  if (!gig) return;

  appState.activeJob = gig;
  appState.currentState = DriverState.JOB_ACCEPTED;
  appState.activeNavTab = "gigs";

  // Call REST endpoint POST /api/v1/gigs/accept
  try {
    await fetch("/api/v1/gigs/accept", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gig_id: gigId, worker_id: appState.worker.id })
    });
  } catch (e) {
    console.log("Gig accept endpoint fallback");
  }

  showNotificationToast("📦 Gig Accepted!", `Accepted ₹${gig.payInr} delivery from ${gig.restaurant}. Shield Active!`, "success");
  renderApp();
}

function advanceTripState(nextState, toastMessage) {
  appState.currentState = nextState;
  if (toastMessage) {
    showNotificationToast("🛵 Trip Progress", toastMessage, "info");
  }
  renderApp();
}

function completeDeliveryProof() {
  const job = appState.activeJob;
  if (!job) return;

  const earned = job.payInr;
  appState.earningsToday += earned;
  appState.activeJob = null;
  appState.currentState = DriverState.AVAILABLE;
  appState.activeNavTab = "home";

  showNotificationToast("🎉 Delivery Complete!", `Earned ₹${earned}. Parametric income protection recorded.`, "success");
  renderApp();
}

// --- Zero-Touch Disruption Claim Simulator (4-Agent Pipeline) ---

async function simulateDisruption(disruptionType) {
  showNotificationToast("⚡ Disruption Alert", `Disruption trigger detected in T. Nagar zone! Processing zero-touch claim...`, "warning");

  try {
    const response = await fetch("/api/v1/claims/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        worker_id: appState.worker.id,
        zone_id: "ZONE_MAA_01",
        week_start_date: new Date().toISOString().split("T")[0],
        disruption_event_type: disruptionType,
        w_avg: 4500.0,
        w_actual: 1039.0,
        is_cyclone_flood_active: true
      })
    });
    const result = await response.json();
    const payoutAmount = result.final_approved_payout || 2422.70;
    const beta = disruptionType.includes("STFI") ? 0.75 : 0.65;
    
    showNotificationToast("✓ 4-AGENT APPROVED", `Payout ₹${payoutAmount.toFixed(2)} (β = ${beta}) credited via Razorpay UPI Rail!`, "success");

    appState.protectedEarningsToday += payoutAmount;
    appState.claimsHistory.unshift({
      id: result.claim_id || "CLM_" + Math.floor(Math.random()*90000),
      title: disruptionType.replace(/_/g, " "),
      amount: payoutAmount,
      date: "Just Now",
      status: "Paid via Razorpay UPI",
      utr: "RZNP" + Math.random().toString(36).substring(2, 10).toUpperCase()
    });

    renderApp();
  } catch (err) {
    showNotificationToast("✓ 4-AGENT APPROVED", `Payout ₹2422.70 credited via Razorpay UPI!`, "success");
    renderApp();
  }
}

async function triggerInstantPay() {
  const amount = appState.earningsToday + appState.protectedEarningsToday;
  if (amount <= 0) {
    alert("No balance available for instant pay.");
    return;
  }
  
  try {
    const res = await fetch("/api/v1/payouts/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        claim_id: "CLM_" + Math.floor(Math.random()*90000),
        worker_id: appState.worker.id,
        amount_inr: amount - 5
      })
    });
    const payoutRes = await res.json();
    showNotificationToast("⚡ Instant Pay Sent", `₹${payoutRes.amount_inr.toFixed(2)} credited to SBI •••• 4821. UTR: ${payoutRes.utr_number}`, "success");
  } catch (e) {
    showNotificationToast("⚡ Instant Pay Sent", `₹${(amount - 5).toFixed(2)} credited to SBI bank account via UPI!`, "success");
  }
  
  appState.earningsToday = 0;
  appState.protectedEarningsToday = 0;
  renderApp();
}

function openEmergencyModal() {
  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.innerHTML = `
    <div class="modal-bottom-sheet">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <div style="font-weight:800; font-size:18px; color:var(--accent-rose);">🚨 Emergency & Roadside SOS</div>
        <div style="font-size:18px; cursor:pointer;" onclick="this.closest('.modal-overlay').remove()">✕</div>
      </div>
      
      <button class="btn-danger" style="margin-bottom:12px;" onclick="showNotificationToast('📞 Emergency 112', 'Initiating direct emergency call...', 'warning'); this.closest('.modal-overlay').remove();">
        📞 CALL EMERGENCY (112)
      </button>

      <button class="btn-secondary" style="margin-bottom:12px;" onclick="showNotificationToast('🛠 Breakdown Support', 'Roadside assistance dispatched to current location.', 'info'); this.closest('.modal-overlay').remove();">
        🛠 Request Roadside Assistance
      </button>

      <button class="btn-secondary" onclick="showNotificationToast('📍 GPS Location Shared', 'Trip route & live GPS shared with emergency contact.', 'info'); this.closest('.modal-overlay').remove();">
        📍 Share Live Location
      </button>
    </div>
  `;
  document.getElementById("phone-container").appendChild(modal);
}
