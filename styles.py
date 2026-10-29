"""Floral theme styles for the Streamlit app."""

CSS = """
<style>
:root {
  --rose: #c2185b;
  --rose-soft: #f8bbd0;
  --lavender: #b39ddb;
  --sage: #8fae8b;
  --gold: #e6b450;
  --cream: #fff8f5;
  --ink: #3b2a33;
}

.stApp {
  background:
    radial-gradient(circle at 8% 12%, rgba(248,187,208,.45) 0, transparent 28%),
    radial-gradient(circle at 92% 18%, rgba(179,157,219,.35) 0, transparent 30%),
    radial-gradient(circle at 85% 90%, rgba(143,174,139,.30) 0, transparent 32%),
    radial-gradient(circle at 10% 88%, rgba(230,180,80,.22) 0, transparent 30%),
    var(--cream);
}

/* Falling petals */
.petals { position: fixed; inset: 0; pointer-events: none; overflow: hidden; z-index: 0; }
.petals span {
  position: absolute; top: -10vh; opacity: .3;
  animation: fall linear infinite;
}
@keyframes fall {
  0%   { transform: translate(0, 0) rotate(0deg); }
  50%  { transform: translate(40px, 55vh) rotate(180deg); }
  100% { transform: translate(-20px, 115vh) rotate(360deg); }
}
@media (prefers-reduced-motion: reduce) { .petals { display: none; } }

/* Header */
.hero {
  position: relative; z-index: 1;
  text-align: center; padding: 1.6rem 1rem 1.2rem; margin-bottom: 1rem;
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(248,187,208,.85), rgba(209,196,233,.85) 55%, rgba(200,230,201,.85));
  box-shadow: 0 10px 30px rgba(194,24,91,.12);
}
.hero h1 {
  margin: 0; font-size: 2.6rem; color: var(--ink); letter-spacing: .5px;
  font-family: Georgia, "Times New Roman", serif;
}
.hero p { margin: .35rem 0 0; color: #5d4652; font-size: 1.05rem; }

.section-title {
  font-family: Georgia, serif; font-size: 1.4rem; color: var(--rose);
  margin: .6rem 0 .1rem;
}
.section-sub { color: #7a6270; margin-bottom: .8rem; }

/* Featured cards */
[class*="st-key-featcard"], [class*="st-key-card-"] {
  background: rgba(255,255,255,.82);
  border-radius: 20px; padding: 1rem .9rem .9rem;
  border-top: 6px solid var(--accent, var(--rose-soft));
  box-shadow: 0 6px 18px rgba(59,42,51,.08);
  transition: transform .25s ease, box-shadow .25s ease;
  height: 100%;
}
[class*="st-key-featcard"]:hover, [class*="st-key-card-"]:hover {
  transform: translateY(-6px) rotate(-.4deg);
  box-shadow: 0 14px 28px rgba(194,24,91,.18);
}
.st-key-featcard-0 { --accent: #e57399; }
.st-key-featcard-1 { --accent: #b39ddb; }
.st-key-featcard-2 { --accent: #f4a6c0; }
.st-key-featcard-3 { --accent: #8fae8b; }
.st-key-featcard-4 { --accent: #e6b450; }
.card-flower { font-size: 1.8rem; line-height: 1; }
.card-name { font-weight: 700; font-family: Georgia, serif; font-size: 1.05rem; margin: .3rem 0 .15rem; }
.card-meta { color: #8a6f7d; font-size: .85rem; margin-bottom: .4rem; }
.card-teaser { font-size: .92rem; color: #4a3741; }

.stButton > button {
  border-radius: 999px; border: 1px solid var(--rose-soft);
  background: linear-gradient(135deg, #fde4ec, #ede7f6);
  color: var(--rose); font-weight: 600;
  transition: transform .15s ease, box-shadow .15s ease;
}
.stButton > button:hover {
  transform: scale(1.03); color: #fff; border-color: transparent;
  background: linear-gradient(135deg, #e57399, #9575cd);
  box-shadow: 0 6px 14px rgba(194,24,91,.25);
}

/* Chat bubbles */
.chat { position: relative; z-index: 1; display: flex; flex-direction: column; gap: .9rem; margin: 1rem 0 1.5rem; }
.row { display: flex; align-items: flex-end; gap: .55rem; animation: bloom .35s ease-out both; }
.row.user { flex-direction: row-reverse; }
.chat .row, .hero { scroll-margin-top: 4.5rem; }
.avatar {
  flex: 0 0 auto; width: 2.4rem; height: 2.4rem; border-radius: 50%;
  display: grid; place-items: center; font-size: 1.3rem;
  background: #fff; box-shadow: 0 3px 8px rgba(59,42,51,.12);
}
.bubble {
  max-width: min(75%, 680px); padding: .8rem 1.05rem; line-height: 1.5;
  border-radius: 20px; box-shadow: 0 4px 14px rgba(59,42,51,.08);
  word-wrap: break-word;
}
.row.user .bubble {
  color: #fff; border-bottom-right-radius: 6px;
  background: linear-gradient(135deg, #d81b60, #8e5bd0);
}
.row.bot .bubble {
  color: var(--ink); border-bottom-left-radius: 6px;
  background: rgba(255,255,255,.92); border: 1px solid #f3d3df;
}
.typing span {
  display: inline-block; width: .5rem; height: .5rem; margin: 0 .12rem; border-radius: 50%;
  background: var(--rose-soft); animation: pulse 1s infinite ease-in-out;
}
.typing span:nth-child(2) { animation-delay: .15s; background: var(--lavender); }
.typing span:nth-child(3) { animation-delay: .3s; background: var(--sage); }
@keyframes pulse { 0%, 100% { transform: scale(.6); opacity: .5; } 50% { transform: scale(1); opacity: 1; } }
@keyframes bloom { from { opacity: 0; transform: translateY(10px) scale(.97); } to { opacity: 1; transform: none; } }

.empty {
  text-align: center; color: #8a6f7d; padding: 1.2rem; border-radius: 18px;
  border: 2px dashed #f3c6d6; background: rgba(255,255,255,.6);
}

[data-testid="stChatInput"] textarea { font-size: 1rem; }
[data-testid="stChatInput"] > div {
  border-radius: 999px !important; border: 2px solid var(--rose-soft) !important;
  box-shadow: 0 6px 18px rgba(194,24,91,.12);
}
hr { border-color: #f3d3df !important; }

/* Prominent figure cards get a gold edge and a badge */
[class*="st-key-card-prom-"] { --accent: var(--gold); background: linear-gradient(180deg, #fffaf0, rgba(255,255,255,.9)); }
[class*="st-key-card-find-"] { --accent: #f3c6d6; }
.badge {
  display: inline-block; font-size: .72rem; font-weight: 700; letter-spacing: .3px;
  padding: .12rem .55rem; border-radius: 999px; margin-bottom: .3rem;
  color: #7a5200; background: #fdeec8; border: 1px solid #f1d38b;
}
.card-tagline { font-size: .9rem; color: #4a3741; margin-bottom: .5rem; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: .4rem; flex-wrap: wrap; }
.stTabs [data-baseweb="tab"] {
  border-radius: 999px; padding: .35rem 1rem; background: rgba(255,255,255,.7);
  border: 1px solid #f3d3df;
}
.stTabs [aria-selected="true"] { background: linear-gradient(135deg, #fde4ec, #ede7f6); color: var(--rose); }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

.result-count { color: #7a6270; margin: .3rem 0 .8rem; font-size: .95rem; }

/* Sources under each answer */
.sources {
  margin-top: .7rem; padding-top: .55rem; border-top: 1px dashed #efc3d3;
  font-size: .8rem; color: #7a6270;
}
.sources-title { font-weight: 700; color: var(--rose); margin-bottom: .2rem; letter-spacing: .3px; }
.sources ol { margin: 0; padding-left: 1.1rem; }
.sources li { margin: .1rem 0; }
.sources a { color: #8e3a6a; }

/* Profile dialog */
.profile-meta { color: #7a6270; margin: -.3rem 0 .8rem; }
.profile-burial {
  background: #fff4f8; border-left: 4px solid var(--rose-soft); border-radius: 10px;
  padding: .6rem .8rem; margin: .4rem 0 1rem; font-size: .92rem;
}
.timeline { border-left: 3px solid var(--rose-soft); margin: .3rem 0 1rem .4rem; padding-left: 1rem; }
.timeline div { margin: .35rem 0; }
.timeline b { color: var(--rose); }
.cite { font-size: .72rem; color: #a07a8c; vertical-align: super; }

/* Hide the zero-height helper frame used for auto-scroll */
.st-key-autoscroll { position: absolute !important; height: 0 !important; width: 0 !important; overflow: hidden; }
</style>
"""
