/* ══════════════════════════════════════
   VEKTOR — MAIN JAVASCRIPT
   Edit behaviour/logic here
══════════════════════════════════════ */

/* ── CART STATE ── */
let cart = [];
let cartTotal = 0;

/* ─────────────────────────────────────
   LOADER  ✅ FIXED — was never hiding on back navigation
───────────────────────────────────── */
function hideLoader() {
  const loader = document.getElementById('loader');
  if (loader) {
    loader.style.opacity = '0';
    loader.style.transition = 'opacity 0.5s ease';
    setTimeout(() => {
      loader.style.display = 'none';
      loader.classList.add('gone');
    }, 500);
  }
}

// ✅ Fires on normal page load
window.addEventListener('load', () => {
  setTimeout(hideLoader, 1500);
});

// ✅ Fires when user navigates BACK (bfcache restore)
window.addEventListener('pageshow', (e) => {
  if (e.persisted) {
    // Page was restored from back/forward cache
    hideLoader();
    // Also remove page-transition overlay if stuck
    const pt = document.querySelector('.page-transition');
    if (pt) pt.classList.remove('active');
  }
});

// ✅ Safety net — if loader is still visible after 4s, force hide it
setTimeout(() => {
  const loader = document.getElementById('loader');
  if (loader && loader.style.display !== 'none') {
    hideLoader();
  }
}, 4000);

/* ─────────────────────────────────────
   CUSTOM CURSOR
───────────────────────────────────── */
const cur  = document.getElementById('cursor');
const ring = document.getElementById('cursorRing');
const lbl  = document.getElementById('cursorLabel');
let mx = 0, my = 0, rx = 0, ry = 0;

document.addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; });

(function cursorLoop() {
  if (cur)  { cur.style.left  = mx + 'px'; cur.style.top   = my + 'px'; }
  if (ring) {
    rx += (mx - rx) * .1;
    ry += (my - ry) * .1;
    ring.style.left = rx + 'px';
    ring.style.top  = ry + 'px';
  }
  if (lbl)  { lbl.style.left  = rx + 'px'; lbl.style.top   = ry + 'px'; }
  requestAnimationFrame(cursorLoop);
})();

/* Hover effects — product cards show "ADD TO CART" label */
document.querySelectorAll('.prod-card, .prod-qa, .prod-add-mini, .lb-card, .lb-overlay-btn').forEach(el => {
  el.addEventListener('mouseenter', () => { cur?.classList.add('hover'); ring?.classList.add('hover'); lbl?.classList.add('show'); });
  el.addEventListener('mouseleave', () => { cur?.classList.remove('hover'); ring?.classList.remove('hover'); lbl?.classList.remove('show'); });
});

/* Hover effects — general clickable elements */
document.querySelectorAll('a, button, .cat-card, .why-item, .mc-card, .coll-card, .coll-side-card, .story-val, .story-team-card, .testi-card, .pride-row, .sidebar-opt').forEach(el => {
  el.addEventListener('mouseenter', () => { cur?.classList.add('hover'); ring?.classList.add('hover'); });
  el.addEventListener('mouseleave', () => { cur?.classList.remove('hover'); ring?.classList.remove('hover'); });
});

/* ─────────────────────────────────────
   SCROLL PROGRESS BAR
───────────────────────────────────── */
window.addEventListener('scroll', () => {
  const prog = document.getElementById('scrollProg');
  if (prog) {
    const pct = (window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100;
    prog.style.width = pct + '%';
  }
  // Also update scroll-bar element
  const sb = document.querySelector('.scroll-bar');
  if (sb) {
    const scroll = document.documentElement.scrollTop;
    const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
    sb.style.width = ((scroll / height) * 100) + '%';
  }
});

/* ─────────────────────────────────────
   COUNTDOWN TIMER
───────────────────────────────────── */
let total = 2 * 3600 + 47 * 60 + 33;

function tick() {
  if (total <= 0) total = 3 * 3600;
  total--;
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = n => String(n).padStart(2, '0');

  ['fh', 'fm', 'fs'].forEach((id, i) => {
    const el = document.getElementById(id);
    if (el) el.textContent = pad([h, m, s][i]);
  });

  const ut = document.getElementById('urgTimer');
  if (ut) ut.textContent = `${pad(h)}:${pad(m)}:${pad(s)}`;
}
setInterval(tick, 1000);

/* ─────────────────────────────────────
   SCROLL REVEAL (Intersection Observer)
───────────────────────────────────── */
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach((e, i) => {
    if (e.isIntersecting) {
      setTimeout(() => e.target.classList.add('vis'), i * 70);
      revealObserver.unobserve(e.target);
    }
  });
}, { threshold: .1 });

function setupReveal() {
  document.querySelectorAll('.reveal, .reveal-l, .reveal-r').forEach(el => {
    if (!el.classList.contains('vis')) revealObserver.observe(el);
    // Also support old .active class style
    if (el.getBoundingClientRect().top < window.innerHeight - 100) {
      el.classList.add('active');
    }
  });
}
setupReveal();

window.addEventListener('scroll', () => {
  document.querySelectorAll('.reveal').forEach(el => {
    if (el.getBoundingClientRect().top < window.innerHeight - 100) {
      el.classList.add('active');
    }
  });
});

/* ─────────────────────────────────────
   HERO PARALLAX (mouse-based tilt)
───────────────────────────────────── */
document.addEventListener('mousemove', e => {
  const hl = document.getElementById('heroLeft');
  if (!hl) return;
  const rx2 = (e.clientX / window.innerWidth - .5) * 14;
  const ry2 = (e.clientY / window.innerHeight - .5) * 10;
  hl.style.transform = `perspective(1200px) rotateY(${rx2 * .25}deg) rotateX(${-ry2 * .18}deg)`;
});

/* ─────────────────────────────────────
   PAGE NAVIGATION (SPA style)
───────────────────────────────────── */
function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const target = document.getElementById('page-' + page);
  if (target) target.classList.add('active');
  document.querySelectorAll('.nav-links a').forEach(a => a.classList.remove('active'));
  const navEl = document.getElementById('nav-' + page);
  if (navEl) navEl.classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
  setTimeout(setupReveal, 100);
  return false;
}

/* ─────────────────────────────────────
   CART LOGIC
───────────────────────────────────── */
function addToCart(en, mr, price) {
  const existing = cart.find(i => i.en === en);
  if (existing) {
    existing.qty++;
  } else {
    cart.push({ en, mr, price, qty: 1 });
  }
  cartTotal = cart.reduce((s, i) => s + i.price * i.qty, 0);
  updateCartUI();
  showToast('Added: ' + en, 'कार्टमध्ये जोडले: ' + mr);

  const cc = document.getElementById('cartCount');
  if (cc) {
    cc.style.transform = 'scale(1.5)';
    setTimeout(() => cc.style.transform = 'scale(1)', 250);
  }
}

function removeFromCart(en) {
  cart = cart.filter(i => i.en !== en);
  cartTotal = cart.reduce((s, i) => s + i.price * i.qty, 0);
  updateCartUI();
}

function updateCartUI() {
  const totalItems = cart.reduce((s, i) => s + i.qty, 0);
  const cc   = document.getElementById('cartCount');
  const body = document.getElementById('cartBody');
  const foot = document.getElementById('cartFoot');
  const amt  = document.getElementById('cartTotal');

  if (cc) cc.textContent = totalItems;

  if (!body) return;

  if (cart.length === 0) {
    body.innerHTML = `
      <div class="cart-empty">
        <div class="cart-empty-sk">कार्ट रिकामी आहे</div>
        <div class="cart-empty-en">Your cart is empty</div>
        <button class="cart-empty-btn" onclick="closeCart()">खरेदी करा — Shop Now</button>
      </div>`;
    if (foot) foot.style.display = 'none';
  } else {
    body.innerHTML = cart.map(i => `
      <div class="cart-item">
        <div class="cart-item-img">VK</div>
        <div class="cart-item-info">
          <div class="cart-item-name">${i.en}</div>
          <div class="cart-item-mr">${i.mr}</div>
          <div class="cart-item-price">₹${(i.price * i.qty).toLocaleString('en-IN')}</div>
          <div class="cart-item-size">Qty: ${i.qty} · Size: M</div>
        </div>
        <button class="cart-item-remove" onclick="removeFromCart('${i.en}')">✕</button>
      </div>`).join('');
    if (foot) foot.style.display = 'flex';
    if (amt)  amt.textContent = '₹' + cartTotal.toLocaleString('en-IN');
  }
}

function openCart()  {
  document.getElementById('cartSidebar')?.classList.add('open');
  document.getElementById('cartBg')?.classList.add('open');
}
function closeCart() {
  document.getElementById('cartSidebar')?.classList.remove('open');
  document.getElementById('cartBg')?.classList.remove('open');
}

function checkout() {
  if (cart.length === 0) return;
  showToast('Checkout coming soon!', 'लवकरच येत आहे!');
}

/* ─────────────────────────────────────
   SEARCH OVERLAY
───────────────────────────────────── */
function openSearch()  {
  document.getElementById('searchOverlay')?.classList.add('open');
  setTimeout(() => document.getElementById('searchInput')?.focus(), 300);
}
function closeSearch() {
  document.getElementById('searchOverlay')?.classList.remove('open');
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeSearch(); closeLogin(); }
});

function doSearch() {
  const q = document.getElementById('searchInput')?.value;
  if (q) { closeSearch(); showToast('Searching: ' + q, 'शोधत आहे: ' + q); }
}
function searchTerm(t) {
  const si = document.getElementById('searchInput');
  if (si) si.value = t;
  doSearch();
}

/* ─────────────────────────────────────
   LOGIN MODAL
───────────────────────────────────── */
function openLogin()  { document.getElementById('loginOverlay')?.classList.add('open'); }
function closeLogin() { document.getElementById('loginOverlay')?.classList.remove('open'); }

function loginTab(btn, tab) {
  document.querySelectorAll('.ltab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const signInForm = document.getElementById('formSignIn');
  const signUpForm = document.getElementById('formSignUp');
  if (tab === 'signin') {
    if (signInForm) signInForm.style.display = 'flex';
    if (signUpForm) signUpForm.style.display = 'none';
  } else {
    if (signInForm) signInForm.style.display = 'none';
    if (signUpForm) signUpForm.style.display = 'flex';
  }
}

function handleLogin(e) {
  e.preventDefault();
  showToast('Logging in...', 'साइन इन होत आहे...');
  setTimeout(() => { closeLogin(); showToast('Welcome back! 🙏', 'स्वागत आहे!'); }, 1200);
}

function handleSignUp(e) {
  e.preventDefault();
  showToast('Creating account...', 'खाते तयार होत आहे...');
  setTimeout(() => { closeLogin(); showToast('Account created! 🎉', 'खाते तयार झाले!'); }, 1200);
}

function loginWithWhatsApp() {
  showToast('Opening WhatsApp...', 'WhatsApp उघडत आहे...');
}

/* ─────────────────────────────────────
   TOAST NOTIFICATION
───────────────────────────────────── */
let toastTimer;
function showToast(msg, mr) {
  clearTimeout(toastTimer);
  const tm = document.getElementById('toastMsg');
  const tmr = document.getElementById('toastMr');
  const t = document.getElementById('toast');
  if (tm) tm.textContent = msg;
  if (tmr) tmr.textContent = mr;
  if (t) {
    t.classList.add('show');
    toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
  }
}

/* ─────────────────────────────────────
   SHOP PAGE — FILTERS & SORT
   Real logic lives in shop.html inline
   <script>. These are safe stubs so
   other pages don't throw errors.
───────────────────────────────────── */
function filterCat(btn, cat) {
  // Handled by shop.html inline script
}

function updatePrice(v) {
  // Update display label only; navigation handled by shop.html
  const pv = document.getElementById('priceVal');
  if (pv) pv.textContent = '₹' + Number(v).toLocaleString('en-IN');
}

function sortProducts(v) {
  // Handled by shop.html inline script
}

function toggleSize(btn) {
  // Handled by shop.html inline script
  btn.classList.toggle('sel');
}

function filterColor(el) {
  // Handled by shop.html inline script
}

function applySortFilter(v) {
  // Handled by shop.html inline script
}

/* ─────────────────────────────────────
   LOOKBOOK — SEASON TABS
───────────────────────────────────── */
function lbTab(btn, season) {
  document.querySelectorAll('.lb-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  showToast('Season: ' + season.toUpperCase(), 'हंगाम: ' + season.toUpperCase());
}

/* ─────────────────────────────────────
   COLOR SWATCHES
   Selection + filtering handled by
   filterColor() in shop.html script.
───────────────────────────────────── */
// Swatch click logic is defined in shop.html inline script.
// No global handler needed here.

/* ─────────────────────────────────────
   MOUSE POSITION CSS VARS
───────────────────────────────────── */
document.addEventListener('mousemove', (e) => {
  document.body.style.setProperty('--x', e.clientX + 'px');
  document.body.style.setProperty('--y', e.clientY + 'px');
});

/* ─────────────────────────────────────
   PRODUCT VIEW
───────────────────────────────────── */
function viewProduct(id) {
  window.location.href = '/product?id=' + id;
}

/* ─────────────────────────────────────
   NAV USER DROPDOWN
───────────────────────────────────── */
function toggleUserMenu() {
  document.getElementById('navUserWrap')?.classList.toggle('open');
}

document.addEventListener('click', function(e) {
  const wrap = document.getElementById('navUserWrap');
  if (wrap && !wrap.contains(e.target)) {
    wrap.classList.remove('open');
  }
});

/* ─────────────────────────────────────
   LOGIN BOX 3D TILT
───────────────────────────────────── */
const card = document.querySelector('.login-box');
document.addEventListener('mousemove', (e) => {
  if (!card) return;
  const x = (window.innerWidth / 2 - e.clientX) / 25;
  const y = (window.innerHeight / 2 - e.clientY) / 25;
  card.style.transform = `rotateY(${x}deg) rotateX(${y}deg)`;
});

/* ─────────────────────────────────────
   PASSWORD TOGGLE
───────────────────────────────────── */
function togglePassword() {
  const input = document.getElementById('passwordField');
  if (input) input.type = input.type === 'password' ? 'text' : 'password';
}

/* ─────────────────────────────────────
   NAVBAR SCROLL EFFECT
───────────────────────────────────── */
window.addEventListener('scroll', () => {
  const nav = document.querySelector('nav');
  if (nav) {
    nav.classList.toggle('scrolled', window.scrollY > 50);
  }
});

/* ─────────────────────────────────────
   PAGE TRANSITION  ✅ FIXED — was causing black screen on back
───────────────────────────────────── */
document.querySelectorAll('a[href]').forEach(link => {
  link.addEventListener('click', function(e) {
    // Ignore links inside forms
    if (this.closest('form')) return;

    const href = this.getAttribute('href');

    // Ignore anchors, blank targets, javascript: links, empty
    if (!href || href.startsWith('#') || href.startsWith('javascript') || this.target === '_blank') return;

    e.preventDefault();

    const pt = document.querySelector('.page-transition');
    if (pt) pt.classList.add('active');

    setTimeout(() => {
      window.location = href;
    }, 400);
  });
});

/* ─────────────────────────────────────
   FORM SUBMIT — allow without transition warning
───────────────────────────────────── */
document.getElementById('editProductForm')?.addEventListener('submit', function () {
  window.onbeforeunload = null;
});