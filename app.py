from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import json
import os
import secrets
import threading
import time
from pathlib import Path

from security import IAMService, can


HTML = r'''<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="format-detection" content="telephone=no" />
  <meta name="theme-color" content="#103b3e" />
  <meta name="color-scheme" content="light" />
  <meta name="application-name" content="عزوتك" />
  <meta name="description" content="منصة أردنية لحجز الخدمات المنزلية الموثوقة في عمّان وإربد والزرقاء." />
  <link rel="manifest" href="/manifest.webmanifest" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <title>عزوتك | خدماتك أقرب</title>
  <style nonce="__CSP_NONCE__">
    :root {
      --ink: #153d40;
      --ink-2: #356064;
      --muted: #7d9290;
      --line: #e7ece9;
      --paper: #fbfcfa;
      --surface: #ffffff;
      --mint: #dff1e8;
      --teal: #138a7d;
      --teal-dark: #0e6f68;
      --amber: #ef9b4b;
      --amber-soft: #fff0dc;
      --lavender: #eae8fa;
      --blue-soft: #e6f0fa;
      --shadow: 0 18px 45px rgba(31, 70, 70, .08);
      --shadow-small: 0 8px 20px rgba(31, 70, 70, .07);
      --radius-xl: 28px;
      --radius-lg: 20px;
      --radius-md: 14px;
      font-family: "Tajawal", "Noto Kufi Arabic", "Segoe UI", Tahoma, Arial, sans-serif;
    }

    * { box-sizing: border-box; }
    [hidden] { display: none !important; }
    :focus-visible { outline: 3px solid rgba(19,138,125,.42); outline-offset: 3px; }
    html { min-width: 320px; scroll-behavior: smooth; }
    body {
      margin: 0;
      background: #edf3f0;
      color: var(--ink);
      font-size: 14px;
      -webkit-font-smoothing: antialiased;
    }
    body.modal-open { overflow: hidden; }
    .skip-link { position: fixed; z-index: 200; top: 10px; right: 10px; padding: 9px 13px; border-radius: 9px; color: #fff; background: var(--ink); transform: translateY(-150%); transition: transform .2s; }
    .skip-link:focus { transform: translateY(0); }
    button, input { font: inherit; }
    button { cursor: pointer; }
    a { color: inherit; text-decoration: none; }
    ::selection { background: #bde5d6; color: var(--ink); }

    .app-shell {
      width: min(100%, 1480px);
      min-height: 100vh;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 252px minmax(0, 1fr);
      direction: rtl;
      background: var(--paper);
      box-shadow: 0 0 65px rgba(35, 78, 75, .09);
    }

    /* Sidebar */
    .sidebar {
      min-height: 100vh;
      padding: 27px 18px 22px;
      display: flex;
      flex-direction: column;
      gap: 26px;
      background: #fcfdfb;
      border-left: 1px solid var(--line);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 0 8px;
      min-height: 42px;
    }
    .brand-mark {
      width: 38px;
      height: 38px;
      border-radius: 13px;
      display: grid;
      place-items: center;
      color: #fff;
      background: var(--teal);
      box-shadow: 0 7px 15px rgba(19, 138, 125, .22);
      position: relative;
      overflow: hidden;
    }
    .brand-mark::after {
      content: "";
      position: absolute;
      width: 26px;
      height: 26px;
      border: 1.5px solid rgba(255,255,255,.34);
      border-radius: 50%;
      top: -10px;
      left: -8px;
    }
    .brand-mark .icon { width: 22px; height: 22px; position: relative; z-index: 1; }
    .brand-name { font-weight: 900; font-size: 20px; letter-spacing: -.6px; line-height: 1; }
    .brand-sub { display: block; color: var(--muted); font-size: 10px; margin-top: 4px; font-weight: 700; }

    .location-switcher {
      width: 100%;
      border: 1px solid var(--line);
      background: #f8faf8;
      color: var(--ink);
      padding: 11px 12px;
      border-radius: 13px;
      display: flex;
      align-items: center;
      gap: 9px;
      text-align: right;
    }
    .location-switcher .icon { width: 17px; height: 17px; color: var(--teal); flex: 0 0 auto; }
    .location-copy { min-width: 0; flex: 1; }
    .location-copy small { display: block; color: var(--muted); font-size: 10px; font-weight: 700; margin-bottom: 2px; }
    .location-copy strong { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 12px; }
    .location-switcher > .icon:last-child { color: #a0b1ae; width: 14px; height: 14px; }

    .nav-label {
      color: #a0aeac;
      font-weight: 800;
      font-size: 10px;
      padding: 0 12px;
      margin-bottom: 7px;
    }
    .nav-list { display: flex; flex-direction: column; gap: 4px; }
    .nav-item {
      width: 100%;
      border: 0;
      background: transparent;
      color: #718684;
      padding: 12px 13px;
      border-radius: 13px;
      display: flex;
      align-items: center;
      gap: 12px;
      text-align: right;
      transition: background .2s, color .2s, transform .2s;
      position: relative;
    }
    .nav-item:hover { color: var(--teal); background: #f1f7f4; transform: translateX(-2px); }
    .nav-item.active { color: var(--teal-dark); background: #e6f5ef; font-weight: 800; }
    .nav-item.active::before {
      content: "";
      position: absolute;
      right: -18px;
      width: 3px;
      height: 22px;
      border-radius: 5px 0 0 5px;
      background: var(--teal);
    }
    .nav-item .icon { width: 19px; height: 19px; flex: 0 0 auto; }
    .nav-item span:not(.icon):not(.nav-count) { flex: 1; }
    .nav-count { min-width: 21px; height: 21px; padding: 0 5px; display: grid; place-items: center; border-radius: 7px; font-size: 10px; color: #fff; background: var(--amber); font-weight: 800; }
    .admin-access { color: #5e6d9f; }
    .admin-access:hover { color: #4d5a93; background: #f0f1fb; }
    .admin-access .icon { color: #6c73b1; }
    .admin-chip { color: #6b72a6; background: #ececfa; border: 1px solid #dddef4; border-radius: 6px; padding: 4px 5px; font-size: 8px; letter-spacing: .4px; font-weight: 900; }
    .side-divider { height: 1px; background: var(--line); margin: -8px 10px 0; }
    .sidebar-spacer { flex: 1; }
    .support-card {
      padding: 15px;
      border-radius: 17px;
      background: #fff8ed;
      border: 1px solid #f8e7cd;
      overflow: hidden;
      position: relative;
    }
    .support-card::before { content: ""; width: 72px; height: 72px; border: 1px solid #f6d9b0; border-radius: 50%; position: absolute; left: -25px; bottom: -25px; }
    .support-card .mini-icon { width: 30px; height: 30px; display: grid; place-items: center; color: #c87924; background: #fff0d8; border-radius: 10px; margin-bottom: 10px; }
    .support-card .mini-icon .icon { width: 16px; height: 16px; }
    .support-card strong { display: block; font-size: 12px; margin-bottom: 5px; }
    .support-card p { color: #91785d; font-size: 10px; line-height: 1.7; margin: 0 0 11px; }
    .support-card button { border: 0; background: transparent; color: #ad6b24; padding: 0; font-size: 11px; font-weight: 800; }
    .profile-mini { display: flex; align-items: center; gap: 10px; padding: 4px 7px 0; }
    .avatar { width: 35px; height: 35px; border-radius: 12px; display: grid; place-items: center; color: #fff; background: linear-gradient(145deg, #d99261, #a95d4a); font-weight: 900; font-size: 12px; flex: 0 0 auto; }
    .profile-mini-copy { min-width: 0; flex: 1; }
    .profile-mini-copy strong { display: block; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .profile-mini-copy small { color: var(--muted); font-size: 10px; }
    .profile-mini > .icon { width: 16px; height: 16px; color: #a6b5b1; }

    /* Main layout */
    .main-content { min-width: 0; padding: 27px 37px 42px; overflow: hidden; }
    .topbar { min-height: 44px; display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-bottom: 27px; }
    .date-label { color: var(--muted); font-size: 11px; font-weight: 700; margin: 0 0 4px; }
    .date-label strong { color: var(--ink-2); font-weight: 800; }
    .topbar-actions { display: flex; align-items: center; gap: 11px; }
    .round-button {
      width: 40px;
      height: 40px;
      border: 1px solid var(--line);
      border-radius: 13px;
      background: var(--surface);
      color: #6c8582;
      display: grid;
      place-items: center;
      position: relative;
      transition: border .2s, color .2s, box-shadow .2s, transform .2s;
    }
    .round-button:hover { color: var(--teal); border-color: #b9ded3; box-shadow: var(--shadow-small); transform: translateY(-1px); }
    .round-button .icon { width: 18px; height: 18px; }
    .notification-dot { position: absolute; width: 7px; height: 7px; border-radius: 50%; background: var(--amber); border: 2px solid #fff; top: 8px; left: 9px; }
    .top-profile { display: flex; align-items: center; gap: 9px; padding-right: 8px; border-right: 1px solid var(--line); cursor: pointer; border-radius: 13px; transition: opacity .2s; }
    .top-profile:hover { opacity: .8; }
    .top-profile .avatar { width: 39px; height: 39px; border-radius: 14px; }
    .top-profile-copy strong { display: block; font-size: 12px; }
    .top-profile-copy small { color: var(--muted); font-size: 10px; }

    .view { display: none; animation: viewIn .32s ease both; }
    .view.active { display: block; }
    @keyframes viewIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: none; } }
    .welcome-row { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 20px; }
    .welcome-copy h1 { font-size: clamp(24px, 2.4vw, 31px); letter-spacing: -.8px; margin: 0 0 7px; line-height: 1.25; font-weight: 900; }
    .welcome-copy h1 .sparkle { color: var(--amber); font-size: .7em; vertical-align: top; margin-right: 3px; }
    .welcome-copy p { color: var(--muted); margin: 0; font-size: 13px; }
    .welcome-row .new-service-btn { margin-bottom: 2px; }

    .primary-button, .ghost-button {
      border-radius: 12px;
      border: 1px solid transparent;
      padding: 11px 16px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      font-weight: 800;
      font-size: 12px;
      white-space: nowrap;
      transition: transform .2s, box-shadow .2s, background .2s;
    }
    .primary-button { background: var(--teal); color: #fff; box-shadow: 0 7px 15px rgba(19,138,125,.18); }
    .primary-button:hover { background: var(--teal-dark); transform: translateY(-2px); box-shadow: 0 11px 21px rgba(19,138,125,.23); }
    .primary-button .icon, .ghost-button .icon { width: 16px; height: 16px; }
    .ghost-button { color: var(--teal-dark); background: transparent; border-color: #bfe0d6; }
    .ghost-button:hover { background: #edf8f4; transform: translateY(-1px); }
    .text-button { border: 0; color: var(--teal); background: transparent; padding: 4px; font-size: 11px; font-weight: 800; display: inline-flex; align-items: center; gap: 5px; }
    .text-button .icon { width: 14px; height: 14px; }

    /* Hero */
    .hero-card {
      min-height: 253px;
      padding: 28px 30px;
      border-radius: var(--radius-xl);
      position: relative;
      overflow: hidden;
      color: #fff;
      background: linear-gradient(111deg, #154348 0%, #10373d 62%, #0d3036 100%);
      display: flex;
      align-items: center;
      margin-bottom: 23px;
    }
    .hero-card::before { content: ""; position: absolute; width: 400px; height: 400px; border: 1px solid rgba(189, 231, 215, .12); border-radius: 50%; top: -252px; left: -70px; }
    .hero-card::after { content: ""; position: absolute; width: 310px; height: 310px; border: 1px solid rgba(189, 231, 215, .08); border-radius: 50%; bottom: -230px; right: 29%; }
    .hero-content { width: 55%; position: relative; z-index: 2; }
    .hero-eyebrow { color: #b9e3d2; font-size: 11px; font-weight: 800; display: inline-flex; align-items: center; gap: 6px; margin-bottom: 14px; }
    .hero-eyebrow .icon { width: 14px; height: 14px; }
    .hero-card h2 { max-width: 440px; font-size: clamp(23px, 3vw, 34px); line-height: 1.32; letter-spacing: -1px; margin: 0 0 9px; font-weight: 900; }
    .hero-card p { color: #b5cdca; margin: 0; font-size: 12px; line-height: 1.85; max-width: 430px; }
    .hero-actions { display: flex; gap: 9px; align-items: center; margin-top: 20px; }
    .hero-actions .primary-button { color: var(--ink); background: #f5ca90; box-shadow: 0 8px 18px rgba(0,0,0,.14); }
    .hero-actions .primary-button:hover { background: #ffd59e; }
    .hero-actions .hero-link { color: #d0e6de; border: 0; background: transparent; font-size: 11px; font-weight: 800; padding: 10px; }
    .hero-actions .hero-link:hover { color: #fff; }
    .hero-art { position: absolute; z-index: 1; left: 4%; bottom: -5px; width: 38%; max-width: 350px; min-width: 220px; height: 245px; }
    .hero-art .art-glow { fill: #1d5558; opacity: .8; }
    .hero-art .art-window { fill: #b7e1d3; opacity: .9; }
    .hero-art .art-paper { fill: #f7d29d; }
    .hero-art .art-line { fill: none; stroke: #edb46e; stroke-width: 4; stroke-linecap: round; }
    .hero-art .art-person { fill: #e8b47c; }
    .hero-art .art-clothes { fill: #d4ece1; }
    .hero-art .art-dark { fill: #0c2d35; }
    .hero-float {
      position: absolute;
      z-index: 3;
      left: 9%;
      top: 26px;
      padding: 9px 12px;
      border-radius: 12px;
      background: rgba(252,255,251,.96);
      color: var(--ink);
      box-shadow: 0 10px 25px rgba(0,0,0,.13);
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 10px;
      font-weight: 800;
    }
    .hero-float .float-check { width: 19px; height: 19px; display: grid; place-items: center; color: #fff; border-radius: 7px; background: var(--teal); }
    .hero-float .icon { width: 12px; height: 12px; }
    .hero-stat {
      position: absolute;
      z-index: 3;
      left: 28%;
      bottom: 25px;
      padding: 10px 12px;
      min-width: 123px;
      border-radius: 13px;
      background: rgba(31, 77, 78, .9);
      border: 1px solid rgba(212, 237, 226, .16);
      font-size: 10px;
    }
    .hero-stat strong { display: block; color: #fff; font-size: 14px; margin-bottom: 2px; }
    .hero-stat span { color: #a9cbc1; }

    /* Search and section headers */
    .search-row { display: flex; align-items: center; gap: 12px; margin-bottom: 26px; }
    .search-box { position: relative; flex: 1; }
    .search-box > .icon { position: absolute; right: 15px; top: 50%; transform: translateY(-50%); width: 18px; height: 18px; color: #91a7a3; pointer-events: none; }
    .search-box input { width: 100%; height: 49px; border: 1px solid var(--line); border-radius: 14px; outline: 0; color: var(--ink); background: #fff; padding: 0 45px 0 42px; font-size: 12px; transition: border .2s, box-shadow .2s; }
    .search-box input::placeholder { color: #a7b6b3; }
    .search-box input:focus { border-color: #96d0c2; box-shadow: 0 0 0 4px rgba(19,138,125,.08); }
    .search-shortcut { position: absolute; left: 13px; top: 50%; transform: translateY(-50%); border: 1px solid var(--line); color: #a5b3b0; border-radius: 6px; font-size: 9px; padding: 3px 5px; direction: ltr; }
    .filter-button { height: 49px; min-width: 49px; border: 1px solid var(--line); border-radius: 14px; background: #fff; color: var(--ink-2); display: grid; place-items: center; }
    .filter-button:hover { color: var(--teal); border-color: #b9ded3; }
    .filter-button .icon { width: 18px; height: 18px; }
    .section-heading { display: flex; align-items: center; justify-content: space-between; gap: 15px; margin-bottom: 14px; }
    .section-heading h2 { font-size: 16px; letter-spacing: -.3px; margin: 0; font-weight: 900; }
    .section-heading p { color: var(--muted); margin: 4px 0 0; font-size: 11px; }

    /* Service cards */
    .service-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 11px; margin-bottom: 28px; }
    .service-card { border: 1px solid var(--line); background: #fff; border-radius: 17px; padding: 14px; text-align: right; min-width: 0; transition: transform .2s, box-shadow .2s, border .2s; }
    .service-card:hover { transform: translateY(-4px); border-color: #b7ddd1; box-shadow: var(--shadow-small); }
    .service-icon { width: 39px; height: 39px; display: grid; place-items: center; border-radius: 12px; margin-bottom: 12px; }
    .service-icon .icon { width: 19px; height: 19px; }
    .service-icon.green { color: #168374; background: var(--mint); }
    .service-icon.amber { color: #bd731e; background: var(--amber-soft); }
    .service-icon.purple { color: #7064b2; background: var(--lavender); }
    .service-icon.blue { color: #4b7cad; background: var(--blue-soft); }
    .service-card strong { display: block; font-size: 12px; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .service-card small { color: var(--muted); font-size: 10px; }
    .service-card .service-arrow { float: left; color: #b4c0bd; width: 14px; height: 14px; margin-top: 2px; }
    .no-results { grid-column: 1 / -1; text-align: center; padding: 26px; color: var(--muted); border: 1px dashed #d5e1dd; border-radius: 16px; display: none; }

    /* Lower dashboard cards */
    .dashboard-columns { display: grid; grid-template-columns: minmax(0, 1.42fr) minmax(250px, .78fr); gap: 16px; align-items: stretch; margin-bottom: 27px; }
    .panel { background: #fff; border: 1px solid var(--line); border-radius: 20px; padding: 20px; min-width: 0; }
    .panel-header { display: flex; align-items: start; justify-content: space-between; gap: 10px; margin-bottom: 17px; }
    .panel-header h3 { font-size: 14px; margin: 0 0 4px; font-weight: 900; }
    .panel-header p { color: var(--muted); font-size: 10px; margin: 0; }
    .status-pill { border-radius: 8px; padding: 6px 8px; color: #21816e; background: #e4f5ee; font-size: 10px; font-weight: 800; white-space: nowrap; }
    .status-pill.pending { color: #b87523; background: #fff0dd; }
    .status-pill.done { color: #5d65a6; background: #ecebfa; }
    .order-summary { display: flex; align-items: center; gap: 11px; padding-bottom: 17px; border-bottom: 1px solid #eff3f0; }
    .provider-avatar { width: 42px; height: 42px; border-radius: 13px; background: linear-gradient(145deg, #77b9a9, #236d6b); color: white; display: grid; place-items: center; font-weight: 900; font-size: 14px; flex: 0 0 auto; }
    .provider-avatar.avatar-warm { background: linear-gradient(145deg, #caa36c, #895d46); }
    .provider-avatar.avatar-indigo { background: linear-gradient(145deg, #7c8cc2, #4c568f); }
    .order-summary-copy { min-width: 0; flex: 1; }
    .order-summary-copy strong { display: block; font-size: 12px; margin-bottom: 3px; }
    .order-summary-copy small { display: block; color: var(--muted); font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .order-price { text-align: left; }
    .order-price strong { display: block; color: var(--ink); font-size: 13px; }
    .order-price small { color: var(--muted); font-size: 9px; }
    .track-area { padding-top: 17px; display: flex; gap: 12px; }
    .fake-map { height: 91px; flex: 1; border-radius: 14px; overflow: hidden; position: relative; background: #eaf3ed; border: 1px solid #dfece5; }
    .fake-map::before, .fake-map::after { content: ""; position: absolute; background: #fff; opacity: .8; transform: rotate(-28deg); }
    .fake-map::before { width: 150%; height: 10px; top: 31px; right: -20px; box-shadow: 0 24px 0 #fff; }
    .fake-map::after { width: 125%; height: 7px; top: 58px; left: -20px; transform: rotate(29deg); }
    .map-route { position: absolute; inset: 12px 28px; border-top: 3px dashed #f0a15b; transform: rotate(-18deg); z-index: 2; }
    .map-route::before, .map-route::after { content: ""; position: absolute; width: 10px; height: 10px; border: 3px solid #fff; border-radius: 50%; background: var(--teal); top: -7px; }
    .map-route::before { right: -4px; } .map-route::after { left: -4px; background: var(--amber); }
    .map-label { position: absolute; z-index: 3; right: 9px; bottom: 7px; font-size: 9px; padding: 4px 6px; border-radius: 5px; color: #456664; background: rgba(255,255,255,.82); }
    .track-side { width: 124px; display: flex; flex-direction: column; justify-content: center; gap: 12px; }
    .track-step { display: flex; align-items: center; gap: 8px; color: #a2b1ae; font-size: 10px; white-space: nowrap; }
    .track-step.current { color: var(--teal-dark); font-weight: 800; }
    .step-dot { width: 9px; height: 9px; border-radius: 50%; background: #d5e1dd; flex: 0 0 auto; position: relative; }
    .track-step:not(:last-child) .step-dot::after { content: ""; position: absolute; top: 10px; right: 3px; height: 11px; border-right: 1px dashed #cbdad4; }
    .track-step.complete .step-dot { background: var(--teal); }
    .track-step.current .step-dot { background: #fff; border: 3px solid var(--teal); box-shadow: 0 0 0 3px #d9f2e8; }
    .order-footer { display: flex; justify-content: flex-end; margin-top: 17px; }

    .trust-panel { background: #eff8f4; border-color: #d8eee5; position: relative; overflow: hidden; }
    .trust-panel::after { content: ""; width: 174px; height: 174px; position: absolute; left: -76px; bottom: -98px; border: 1px solid #cce7db; border-radius: 50%; }
    .trust-panel .panel-header { position: relative; z-index: 1; }
    .trust-symbol { width: 47px; height: 47px; background: #d6eee3; color: var(--teal); border-radius: 15px; display: grid; place-items: center; margin-bottom: 18px; }
    .trust-symbol .icon { width: 24px; height: 24px; }
    .trust-points { display: flex; flex-direction: column; gap: 13px; position: relative; z-index: 1; }
    .trust-point { display: flex; align-items: center; gap: 9px; color: #47716b; font-size: 10px; }
    .trust-point .check { width: 17px; height: 17px; display: grid; place-items: center; color: var(--teal); border-radius: 6px; background: #d8eee4; }
    .trust-point .icon { width: 11px; height: 11px; }
    .trust-footer { margin-top: 20px; padding-top: 14px; border-top: 1px solid #d5eae1; color: #6f928b; font-size: 10px; line-height: 1.65; position: relative; z-index: 1; }
    .trust-footer strong { color: var(--teal-dark); }

    /* Provider row */
    .provider-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
    .provider-card { border: 1px solid var(--line); border-radius: 17px; padding: 14px; background: #fff; display: flex; gap: 11px; align-items: center; min-width: 0; transition: transform .2s, box-shadow .2s; }
    .provider-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-small); }
    .provider-logo { width: 41px; height: 41px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 13px; font-size: 13px; font-weight: 900; }
    .provider-logo.one { color: #9a5d2a; background: #f9e8d4; } .provider-logo.two { color: #4d6695; background: #e7ecfa; } .provider-logo.three { color: #3b8069; background: #dff2e8; }
    .provider-copy { min-width: 0; flex: 1; }
    .provider-copy strong { display: block; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 4px; }
    .provider-meta { color: var(--muted); font-size: 9px; display: flex; gap: 5px; align-items: center; white-space: nowrap; }
    .provider-meta .star { color: var(--amber); font-size: 12px; }
    .provider-card > .icon { width: 15px; height: 15px; color: #b6c4c0; }

    /* General manager command center */
    .admin-view { color: #18353f; }
    .admin-heading { display: flex; align-items: end; justify-content: space-between; gap: 18px; margin: 5px 0 21px; }
    .admin-eyebrow { display: inline-flex; align-items: center; gap: 7px; color: #6978b1; font-size: 10px; font-weight: 900; margin-bottom: 8px; }
    .admin-eyebrow .icon { width: 14px; height: 14px; }
    .admin-heading h1 { margin: 0 0 6px; font-size: clamp(23px, 2.3vw, 30px); letter-spacing: -.8px; line-height: 1.25; }
    .admin-heading h1 strong { color: #5b68a5; }
    .admin-heading p { color: #83949a; font-size: 11px; margin: 0; }
    .admin-heading-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .admin-live { display: inline-flex; align-items: center; gap: 6px; padding: 9px 11px; border-radius: 10px; color: #237a68; background: #e6f6ef; font-size: 10px; font-weight: 900; }
    .admin-live-dot { width: 7px; height: 7px; border-radius: 50%; background: #2ab88d; box-shadow: 0 0 0 4px rgba(42,184,141,.13); }
    .admin-heading-actions .ghost-button, .admin-heading-actions .primary-button { padding: 9px 12px; font-size: 10px; }
    .admin-security-banner { display: flex; align-items: center; gap: 16px; padding: 17px 19px; margin-bottom: 17px; border: 1px solid #dce1f6; border-radius: 18px; color: #3f4a86; background: linear-gradient(105deg, #f3f4ff, #f7fbfa); position: relative; overflow: hidden; }
    .admin-security-banner::after { content: ""; width: 190px; height: 190px; position: absolute; left: -70px; top: -130px; border: 1px solid rgba(113,123,191,.15); border-radius: 50%; }
    .security-shield { width: 43px; height: 43px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 14px; color: #6371b0; background: #e6e7fa; position: relative; z-index: 1; }
    .security-shield .icon { width: 22px; height: 22px; }
    .security-banner-copy { min-width: 180px; flex: 1; position: relative; z-index: 1; }
    .security-banner-copy strong { display: block; color: #344278; font-size: 12px; margin-bottom: 4px; }
    .security-banner-copy p { margin: 0; color: #7a86a9; font-size: 10px; line-height: 1.7; }
    .security-metrics { display: flex; align-items: center; gap: 7px; position: relative; z-index: 1; }
    .security-metric { min-width: 86px; padding: 8px 10px; border-right: 1px solid #e0e3f3; }
    .security-metric:first-child { border-right: 0; }
    .security-metric strong { display: block; color: #3d4a84; font-size: 12px; margin-bottom: 2px; }
    .security-metric span { color: #8992b1; font-size: 8px; white-space: nowrap; }
    .admin-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-bottom: 17px; }
    .admin-kpi { padding: 14px; border: 1px solid #e5eaed; border-radius: 17px; background: #fff; min-width: 0; transition: transform .2s, box-shadow .2s; }
    .admin-kpi:hover { transform: translateY(-3px); box-shadow: 0 9px 23px rgba(36,64,78,.08); }
    .admin-kpi-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 13px; }
    .admin-kpi-icon { width: 31px; height: 31px; display: grid; place-items: center; border-radius: 10px; color: #6372b3; background: #edf0fc; }
    .admin-kpi-icon.green { color: #24846f; background: #e4f5ed; }
    .admin-kpi-icon.amber { color: #bd781f; background: #fff0dc; }
    .admin-kpi-icon.blue { color: #4b81a8; background: #e7f1fb; }
    .admin-kpi-icon .icon { width: 16px; height: 16px; }
    .kpi-trend { color: #2a9278; font-size: 9px; font-weight: 900; }
    .kpi-trend.down { color: #b87039; }
    .admin-kpi label { display: block; color: #84969c; font-size: 9px; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .admin-kpi strong { display: block; color: #1e3d49; font-size: 20px; line-height: 1; letter-spacing: -.5px; }
    .admin-kpi strong small { color: #7d9298; font-size: 9px; font-weight: 800; letter-spacing: 0; }
    .admin-content-grid { display: grid; grid-template-columns: minmax(0, 1.46fr) minmax(270px, .74fr); gap: 14px; margin-bottom: 15px; }
    .admin-panel { border: 1px solid #e5eaed; border-radius: 19px; padding: 18px; background: #fff; min-width: 0; }
    .admin-panel-head { display: flex; align-items: start; justify-content: space-between; gap: 12px; margin-bottom: 15px; }
    .admin-panel-head h3 { margin: 0 0 4px; color: #24434d; font-size: 13px; }
    .admin-panel-head p { margin: 0; color: #8c9ba0; font-size: 9px; }
    .admin-panel-head .text-button { color: #6371af; font-size: 10px; }
    .chart-tabs { display: flex; align-items: center; gap: 4px; padding: 3px; border-radius: 9px; background: #f3f6f6; }
    .chart-tab { border: 0; border-radius: 7px; background: transparent; color: #8a9a9d; font-size: 9px; padding: 6px 8px; }
    .chart-tab.active { color: #5364a7; background: #fff; box-shadow: 0 2px 7px rgba(58,77,96,.08); font-weight: 900; }
    .revenue-summary { display: flex; align-items: baseline; gap: 8px; margin: 0 0 4px; }
    .revenue-summary strong { color: #243f4a; font-size: 22px; letter-spacing: -.5px; }
    .revenue-summary span { color: #2b9277; font-size: 9px; font-weight: 900; }
    .chart-wrap { height: 170px; margin: 1px -4px -4px; position: relative; }
    .chart-svg { width: 100%; height: 100%; overflow: visible; }
    .chart-grid-line { stroke: #edf1f2; stroke-width: 1; stroke-dasharray: 3 4; }
    .chart-area { fill: url(#adminArea); }
    .chart-line { fill: none; stroke: #6574b4; stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
    .chart-point { fill: #fff; stroke: #6574b4; stroke-width: 2; }
    .chart-label { fill: #9aa8aa; font-size: 9px; font-family: "Tajawal", "Segoe UI", sans-serif; }
    .risk-panel { background: linear-gradient(150deg, #202c50, #394478); color: #fff; border-color: transparent; position: relative; overflow: hidden; }
    .risk-panel::after { content: ""; position: absolute; width: 190px; height: 190px; left: -86px; bottom: -122px; border: 1px solid rgba(255,255,255,.12); border-radius: 50%; }
    .risk-panel .admin-panel-head h3 { color: #fff; }
    .risk-panel .admin-panel-head p { color: #bdc6e0; }
    .risk-panel .text-button { color: #e1e7ff; }
    .risk-score { display: flex; align-items: center; gap: 16px; position: relative; z-index: 1; margin: 2px 0 17px; }
    .score-ring { width: 92px; height: 92px; flex: 0 0 auto; border-radius: 50%; display: grid; place-items: center; background: conic-gradient(#78d7ad 0 96%, rgba(255,255,255,.16) 96% 100%); position: relative; }
    .score-ring::before { content: ""; position: absolute; inset: 8px; border-radius: 50%; background: #28345d; }
    .score-ring div { position: relative; text-align: center; }
    .score-ring strong { display: block; font-size: 22px; line-height: 1; }
    .score-ring span { color: #b9c7df; font-size: 8px; }
    .risk-copy strong { display: block; color: #eaf1ff; font-size: 12px; margin-bottom: 5px; }
    .risk-copy p { color: #b6c2df; font-size: 9px; line-height: 1.7; margin: 0; }
    .risk-list { display: flex; flex-direction: column; gap: 10px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,.13); position: relative; z-index: 1; }
    .risk-row { display: flex; align-items: center; gap: 8px; color: #dce4f7; font-size: 9px; }
    .risk-row .risk-check { width: 17px; height: 17px; display: grid; place-items: center; border-radius: 6px; color: #86deb4; background: rgba(123,217,174,.14); }
    .risk-row .risk-check .icon { width: 11px; height: 11px; }
    .risk-row .risk-value { margin-right: auto; color: #8de0b9; font-size: 8px; font-weight: 900; }
    .admin-lower-grid { display: grid; grid-template-columns: minmax(0, 1.46fr) minmax(270px, .74fr); gap: 14px; margin-bottom: 15px; }
    .ops-filter { display: flex; gap: 4px; padding: 3px; border-radius: 9px; background: #f4f7f7; }
    .ops-filter button { border: 0; border-radius: 7px; padding: 5px 7px; color: #88989c; background: transparent; font-size: 8px; }
    .ops-filter button.active { color: #5264a7; background: #fff; font-weight: 900; box-shadow: 0 2px 7px rgba(58,77,96,.07); }
    .operations-table-wrap { overflow-x: auto; }
    .operations-table { width: 100%; min-width: 520px; border-collapse: collapse; text-align: right; }
    .operations-table th { color: #9aa7aa; font-size: 8px; font-weight: 800; padding: 0 8px 10px; white-space: nowrap; }
    .operations-table td { color: #52696f; font-size: 9px; padding: 11px 8px; border-top: 1px solid #eef2f2; white-space: nowrap; }
    .operations-table td:first-child { color: #34505c; font-weight: 900; }
    .ops-service { display: flex; align-items: center; gap: 7px; }
    .ops-service-icon { width: 25px; height: 25px; display: grid; place-items: center; border-radius: 8px; color: #6371b0; background: #eef0fc; }
    .ops-service-icon .icon { width: 12px; height: 12px; }
    .ops-status { display: inline-flex; align-items: center; gap: 4px; padding: 5px 7px; border-radius: 7px; color: #25816d; background: #e7f5ee; font-size: 8px; font-weight: 900; }
    .ops-status.pending { color: #b57827; background: #fff1df; }
    .ops-status .status-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
    .queue-panel { background: #fafbff; border-color: #e2e5f5; }
    .queue-count { min-width: 22px; height: 22px; display: grid; place-items: center; border-radius: 7px; color: #626eb0; background: #e9eafd; font-size: 10px; font-weight: 900; }
    .approval-list { display: flex; flex-direction: column; gap: 8px; }
    .approval-item { display: flex; align-items: center; gap: 8px; padding: 9px; border: 1px solid #e9ebf5; border-radius: 11px; background: #fff; }
    .approval-avatar { width: 31px; height: 31px; display: grid; place-items: center; flex: 0 0 auto; border-radius: 10px; color: #5e6aa7; background: #e9eafd; font-size: 10px; font-weight: 900; }
    .approval-copy { min-width: 0; flex: 1; }
    .approval-copy strong { display: block; color: #435267; font-size: 9px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 3px; }
    .approval-copy span { color: #9ca7b0; font-size: 8px; }
    .approval-actions { display: flex; gap: 3px; }
    .approval-actions button { width: 25px; height: 25px; display: grid; place-items: center; border: 0; border-radius: 7px; color: #fff; background: #6f7cbe; }
    .approval-actions button.reject { color: #ad6570; background: #fff0f1; }
    .approval-actions .icon { width: 12px; height: 12px; }
    .admin-audit-grid { display: grid; grid-template-columns: minmax(0, 1.06fr) minmax(0, .94fr); gap: 14px; }
    .audit-list { display: flex; flex-direction: column; gap: 0; }
    .audit-item { display: flex; align-items: center; gap: 9px; padding: 10px 0; border-top: 1px solid #eef2f2; }
    .audit-item:first-child { border-top: 0; padding-top: 0; }
    .audit-icon { width: 27px; height: 27px; display: grid; place-items: center; flex: 0 0 auto; border-radius: 8px; color: #6573b0; background: #edf0fc; }
    .audit-icon.green { color: #28826e; background: #e5f5ed; }
    .audit-icon.orange { color: #b47427; background: #fff0dd; }
    .audit-icon .icon { width: 13px; height: 13px; }
    .audit-copy { min-width: 0; flex: 1; }
    .audit-copy strong { display: block; color: #53696f; font-size: 9px; margin-bottom: 3px; }
    .audit-copy span { color: #a0adb0; font-size: 8px; }
    .audit-time { color: #9ba9ac; font-size: 8px; white-space: nowrap; }
    .coverage-row { display: grid; grid-template-columns: 42px 1fr 31px; gap: 9px; align-items: center; margin: 13px 0; color: #70858a; font-size: 9px; }
    .coverage-row:first-child { margin-top: 2px; }
    .coverage-track { height: 7px; border-radius: 8px; background: #edf1f1; overflow: hidden; }
    .coverage-fill { height: 100%; border-radius: inherit; background: linear-gradient(90deg, #7c86c1, #80cba9); }
    .coverage-fill.w68 { width: 68%; } .coverage-fill.w19 { width: 19%; } .coverage-fill.w9 { width: 9%; } .coverage-fill.w4 { width: 4%; }
    .coverage-row strong { color: #526a70; font-size: 9px; text-align: left; }

    /* Other views */
    .page-title { display: flex; align-items: end; justify-content: space-between; gap: 15px; margin: 6px 0 24px; }
    .page-title h1 { font-size: 26px; margin: 0 0 6px; letter-spacing: -.7px; }
    .page-title p { color: var(--muted); margin: 0; font-size: 12px; }
    .filter-pills { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 16px; }
    .filter-pill { border: 1px solid var(--line); background: #fff; color: var(--muted); border-radius: 9px; padding: 8px 12px; font-size: 10px; font-weight: 800; }
    .filter-pill.active { color: var(--teal-dark); border-color: #b8ddcf; background: #e9f7f1; }
    .orders-list { display: flex; flex-direction: column; gap: 11px; }
    .order-row { display: flex; align-items: center; gap: 15px; border: 1px solid var(--line); background: #fff; border-radius: 17px; padding: 15px 17px; }
    .order-row .provider-avatar { width: 43px; height: 43px; }
    .order-row-copy { flex: 1; min-width: 0; }
    .order-row-copy strong { display: block; font-size: 12px; margin-bottom: 5px; }
    .order-row-copy p { color: var(--muted); font-size: 10px; margin: 0; }
    .order-row-date { text-align: left; color: var(--muted); font-size: 10px; line-height: 1.65; }
    .order-row-date strong { display: block; color: var(--ink-2); font-size: 11px; }
    .order-row-action { border: 0; background: transparent; color: var(--teal); font-size: 10px; font-weight: 800; white-space: nowrap; }

    .all-services-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 13px; }
    .large-service { min-height: 145px; padding: 19px; position: relative; overflow: hidden; }
    .large-service::after { content: ""; position: absolute; width: 70px; height: 70px; border: 1px solid #e5efeb; border-radius: 50%; left: -25px; bottom: -26px; }
    .large-service .service-icon { width: 45px; height: 45px; }
    .large-service strong { font-size: 13px; }
    .large-service small { font-size: 10px; }
    .favorite-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 13px; }
    .favorite-card { padding: 20px; border: 1px solid var(--line); background: #fff; border-radius: 19px; display: flex; gap: 13px; align-items: center; }
    .favorite-card .provider-logo { width: 51px; height: 51px; }
    .favorite-card .provider-copy strong { font-size: 13px; }
    .favorite-card button { border: 0; background: transparent; color: var(--amber); margin-right: auto; }
    .favorite-card button .icon { width: 18px; height: 18px; fill: currentColor; }
    .payment-layout { display: grid; grid-template-columns: 1.05fr .95fr; gap: 16px; }
    .payment-card { min-height: 170px; border-radius: 20px; padding: 23px; color: #fff; background: linear-gradient(130deg, #154a4b, #102f39); position: relative; overflow: hidden; }
    .payment-card::after { content: ""; width: 180px; height: 180px; border: 1px solid rgba(255,255,255,.11); border-radius: 50%; position: absolute; bottom: -101px; left: -35px; }
    .payment-card .card-label { color: #a7d5c5; font-size: 10px; }
    .payment-card .card-number { direction: ltr; text-align: left; font-size: 17px; letter-spacing: 2px; margin-top: 30px; }
    .payment-card .card-bottom { display: flex; justify-content: space-between; align-items: end; margin-top: 15px; }
    .payment-card .card-bottom span { font-size: 9px; color: #b2ceca; }
    .payment-card .card-bottom strong { font-size: 12px; }
    .payment-methods { display: flex; flex-direction: column; gap: 10px; }
    .method-row { display: flex; align-items: center; gap: 10px; padding: 13px; border: 1px solid var(--line); border-radius: 13px; background: #fff; }
    .method-icon { width: 33px; height: 33px; display: grid; place-items: center; color: var(--teal); background: var(--mint); border-radius: 10px; }
    .method-icon.cliq { color: #b8741f; background: #fff1dc; }
    .method-icon.cash { color: #6b67a9; background: #ecebfa; }
    .method-icon .icon { width: 16px; height: 16px; }
    .method-row strong { font-size: 11px; }
    .method-row small { display: block; color: var(--muted); font-size: 9px; margin-top: 3px; }
    .method-row > .icon { margin-right: auto; width: 15px; color: #acbcb8; }
    .settings-list { max-width: 720px; border: 1px solid var(--line); background: #fff; border-radius: 20px; overflow: hidden; }
    .setting-row { display: flex; align-items: center; gap: 12px; padding: 17px 19px; border-bottom: 1px solid #edf2ef; }
    .setting-row:last-child { border-bottom: 0; }
    .setting-icon { width: 35px; height: 35px; display: grid; place-items: center; background: #f0f6f3; color: var(--teal); border-radius: 11px; }
    .setting-icon .icon { width: 17px; height: 17px; }
    .setting-copy { flex: 1; }
    .setting-copy strong { font-size: 12px; display: block; margin-bottom: 3px; }
    .setting-copy small { color: var(--muted); font-size: 10px; }
    .toggle { width: 36px; height: 21px; border: 0; border-radius: 20px; padding: 3px; background: #d9e3df; display: flex; justify-content: flex-start; }
    .toggle.on { background: var(--teal); justify-content: flex-end; }
    .toggle span { width: 15px; height: 15px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.18); }

    /* Mobile bottom nav */
    .mobile-nav { display: none; }

    /* Overlays / modal */
    .overlay { position: fixed; inset: 0; z-index: 50; display: none; align-items: center; justify-content: center; padding: 20px; background: rgba(18, 51, 52, .48); backdrop-filter: blur(5px); }
    .overlay.open { display: flex; animation: fadeIn .2s ease both; }
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    .modal-card { width: min(100%, 488px); max-height: min(700px, calc(100vh - 40px)); overflow: auto; border-radius: 24px; background: #fff; box-shadow: 0 22px 80px rgba(7, 40, 40, .24); animation: modalIn .25s ease both; }
    @keyframes modalIn { from { opacity: 0; transform: translateY(13px) scale(.98); } to { opacity: 1; transform: none; } }
    .modal-head { display: flex; align-items: start; justify-content: space-between; padding: 23px 24px 0; }
    .modal-kicker { color: var(--teal); font-size: 10px; font-weight: 900; margin: 0 0 6px; }
    .modal-head h2 { font-size: 20px; letter-spacing: -.4px; margin: 0; }
    .close-button { width: 31px; height: 31px; border: 0; border-radius: 9px; background: #f2f6f4; color: #839b96; display: grid; place-items: center; }
    .close-button:hover { background: #e7f1ed; color: var(--ink); }
    .auth-close { margin-right: auto; }
    .close-button .icon { width: 16px; height: 16px; }
    .modal-body { padding: 19px 24px 24px; }
    .booking-service-line { display: flex; align-items: center; gap: 11px; padding: 12px; border-radius: 14px; border: 1px solid #dcece5; background: #f4faf7; margin-bottom: 19px; }
    .booking-service-line .service-icon { width: 37px; height: 37px; margin: 0; }
    .booking-service-copy { flex: 1; }
    .booking-service-copy small { color: var(--muted); display: block; font-size: 9px; margin-bottom: 3px; }
    .booking-service-copy strong { font-size: 12px; }
    .change-service { border: 0; color: var(--teal); background: transparent; padding: 5px; font-size: 10px; font-weight: 800; }
    .form-field { margin-bottom: 15px; }
    .form-field label { display: flex; justify-content: space-between; color: #59716f; font-size: 10px; font-weight: 800; margin-bottom: 8px; }
    .form-field label span { color: #a0afac; font-weight: 600; }
    .input-shell { display: flex; align-items: center; gap: 9px; border: 1px solid var(--line); border-radius: 12px; height: 43px; padding: 0 12px; color: var(--teal); background: #fff; }
    .input-shell:focus-within { border-color: #9ed2c5; box-shadow: 0 0 0 3px rgba(19,138,125,.07); }
    .input-shell .icon { width: 16px; height: 16px; flex: 0 0 auto; }
    .input-shell input { width: 100%; min-width: 0; border: 0; outline: 0; color: var(--ink); background: transparent; font-size: 11px; }
    .date-options { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; }
    .date-option { border: 1px solid var(--line); border-radius: 11px; background: #fff; color: #7b928e; padding: 9px 5px; text-align: center; font-size: 10px; }
    .date-option strong { display: block; color: var(--ink); font-size: 11px; margin-bottom: 2px; }
    .date-option.selected { border-color: #8ccabb; background: #eaf8f2; color: var(--teal-dark); }
    .date-option.selected strong { color: var(--teal-dark); }
    .summary-strip { display: flex; justify-content: space-between; align-items: center; padding: 13px 0; border-top: 1px solid #eef3f0; border-bottom: 1px solid #eef3f0; margin: 4px 0 17px; }
    .summary-strip span { color: var(--muted); font-size: 10px; }
    .summary-strip strong { font-size: 14px; }
    .summary-strip strong small { font-size: 9px; font-weight: 700; }
    .safe-note { color: #70928b; font-size: 9px; display: flex; align-items: center; gap: 5px; margin: 12px 0 17px; }
    .safe-note .icon { color: var(--teal); width: 14px; height: 14px; }
    .full-button { width: 100%; }
    .confirm-view { display: none; }
    .confirm-view.show { display: block; }
    .booking-view.hide { display: none; }
    .confirm-list { border: 1px solid var(--line); border-radius: 14px; overflow: hidden; margin: 2px 0 17px; }
    .confirm-item { display: flex; justify-content: space-between; gap: 10px; padding: 12px 13px; border-bottom: 1px solid #eff3f1; font-size: 10px; }
    .confirm-item:last-child { border-bottom: 0; }
    .confirm-item span { color: var(--muted); } .confirm-item strong { font-size: 10px; }
    .back-link { border: 0; background: transparent; color: var(--muted); font-size: 10px; font-weight: 800; padding: 0; margin-top: 12px; }
    .back-link:hover { color: var(--teal); }

    .success-modal { width: min(100%, 420px); text-align: center; padding: 33px 30px 29px; }
    .success-mark { width: 70px; height: 70px; border-radius: 23px; display: grid; place-items: center; margin: 0 auto 19px; color: var(--teal); background: #e3f5ed; position: relative; }
    .success-mark::before { content: ""; position: absolute; inset: -8px; border: 1px solid #ccebe0; border-radius: 29px; }
    .success-mark .icon { width: 31px; height: 31px; }
    .success-modal h2 { margin: 0 0 9px; font-size: 21px; }
    .success-modal p { color: var(--muted); font-size: 11px; line-height: 1.8; margin: 0 auto 21px; max-width: 300px; }
    .success-order-id { color: #6d8985; background: #f4f8f6; border-radius: 10px; padding: 9px; font-size: 10px; margin-bottom: 17px; }
    .success-order-id strong { color: var(--ink); margin-right: 5px; direction: ltr; display: inline-block; }
    .success-actions { display: flex; gap: 8px; justify-content: center; }
    .success-actions > * { flex: 1; }

    .intro-modal { width: min(100%, 570px); overflow: hidden; }
    .intro-visual { height: 160px; position: relative; background: linear-gradient(135deg, #e3f4ec, #f8f2e5); display: grid; place-items: center; overflow: hidden; }
    .intro-visual::before, .intro-visual::after { content: ""; position: absolute; border: 1px solid rgba(19,138,125,.13); border-radius: 50%; }
    .intro-visual::before { width: 270px; height: 270px; top: -166px; right: -45px; }
    .intro-visual::after { width: 180px; height: 180px; bottom: -122px; left: -25px; }
    .intro-icon { width: 76px; height: 76px; border-radius: 26px; display: grid; place-items: center; color: #fff; background: var(--teal); box-shadow: 0 14px 25px rgba(19,138,125,.23); position: relative; z-index: 1; }
    .intro-icon .icon { width: 34px; height: 34px; }
    .intro-content { padding: 22px 27px 25px; text-align: center; }
    .intro-content h2 { font-size: 21px; margin: 0 0 9px; }
    .intro-content p { max-width: 390px; color: var(--muted); line-height: 1.9; font-size: 11px; margin: 0 auto 20px; }
    .intro-progress { display: flex; justify-content: center; gap: 5px; margin: 0 0 18px; }
    .intro-progress span { width: 6px; height: 6px; border-radius: 50%; background: #d5e2de; transition: all .2s; }
    .intro-progress span.active { width: 20px; border-radius: 7px; background: var(--teal); }
    .intro-content .primary-button { min-width: 150px; }

    .auth-modal { width: min(100%, 410px); padding: 29px 28px 24px; text-align: center; }
    .auth-brand { width: 49px; height: 49px; margin: 0 auto 16px; border-radius: 16px; display: grid; place-items: center; color: #fff; background: var(--teal); box-shadow: 0 9px 18px rgba(19,138,125,.2); }
    .auth-brand .icon { width: 24px; height: 24px; }
    .auth-modal h2 { font-size: 21px; margin: 0 0 8px; }
    .auth-modal > p { color: var(--muted); font-size: 11px; line-height: 1.8; margin: 0 auto 19px; max-width: 290px; }
    .auth-field { display: flex; align-items: center; gap: 8px; height: 45px; border: 1px solid var(--line); border-radius: 12px; padding: 0 11px; margin-bottom: 10px; text-align: right; }
    .auth-field:focus-within { border-color: #9ed2c5; box-shadow: 0 0 0 3px rgba(19,138,125,.07); }
    .auth-field span { color: var(--teal); font-size: 11px; direction: ltr; padding-left: 8px; border-left: 1px solid var(--line); }
    .auth-field input { width: 100%; min-width: 0; border: 0; outline: 0; color: var(--ink); background: transparent; font-size: 11px; direction: ltr; text-align: right; }
    .auth-field input::placeholder { color: #a7b6b3; }
    .auth-field.invalid { border-color: #d68181; box-shadow: 0 0 0 3px rgba(214,129,129,.1); }
    .auth-error { color: #b85e62; font-size: 9px; text-align: right; margin: -3px 0 9px; }
    .auth-footnote { color: #a0afac; font-size: 9px; line-height: 1.7; margin: 13px 0 0; }
    .auth-footnote strong { color: var(--teal); }
    .auth-divider { display: flex; align-items: center; gap: 9px; color: #a7b5b2; font-size: 9px; margin: 18px 0 12px; }
    .auth-divider::before, .auth-divider::after { content: ""; height: 1px; flex: 1; background: var(--line); }
    .auth-secondary { width: 100%; border: 1px solid var(--line); color: var(--ink-2); background: #fff; border-radius: 11px; padding: 10px; font-size: 10px; font-weight: 800; }
    .auth-secondary:hover { background: #f4faf7; border-color: #b9ded3; }
    .admin-auth-modal { width: min(100%, 430px); }
    .admin-auth-badge { width: 52px; height: 52px; display: grid; place-items: center; color: #6875b4; background: #eceefc; border-radius: 17px; margin: 0 auto 14px; }
    .admin-auth-badge .icon { width: 25px; height: 25px; }
    .admin-auth-modal .modal-head { padding-bottom: 5px; }
    .admin-auth-modal .modal-head h2 { font-size: 18px; }
    .admin-auth-copy { color: var(--muted); font-size: 10px; line-height: 1.8; text-align: center; margin: 0 auto 17px; max-width: 300px; }
    .admin-auth-field { display: flex; align-items: center; gap: 9px; height: 44px; padding: 0 11px; border: 1px solid var(--line); border-radius: 12px; margin-bottom: 9px; }
    .admin-auth-field:focus-within { border-color: #9eabd7; box-shadow: 0 0 0 3px rgba(99,113,180,.1); }
    .admin-auth-field .icon { width: 16px; height: 16px; color: #6875b4; flex: 0 0 auto; }
    .admin-auth-field input { width: 100%; min-width: 0; border: 0; outline: 0; color: var(--ink); background: transparent; font-size: 11px; direction: ltr; text-align: right; }
    .admin-auth-error { color: #b85e62; text-align: center; font-size: 9px; margin: 4px 0 11px; }
    .admin-auth-note { display: flex; align-items: center; gap: 6px; color: #83919a; font-size: 9px; line-height: 1.7; margin: 13px 0 0; }
    .admin-auth-note .icon { width: 14px; height: 14px; color: #2d9078; flex: 0 0 auto; }
    .security-modal { width: min(100%, 610px); }
    .security-modal-body { padding: 19px 24px 24px; }
    .security-modal-intro { display: flex; align-items: center; gap: 12px; padding: 13px; border: 1px solid #dce4f5; border-radius: 14px; background: #f5f7ff; color: #4b5b98; margin-bottom: 15px; }
    .security-modal-intro .security-shield { width: 37px; height: 37px; background: #e4e7fb; }
    .security-modal-intro strong { display: block; color: #39487f; font-size: 11px; margin-bottom: 3px; }
    .security-modal-intro span { display: block; color: #8792b1; font-size: 9px; }
    .security-detail-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; margin-bottom: 15px; }
    .security-detail { padding: 12px; border: 1px solid var(--line); border-radius: 12px; }
    .security-detail strong { display: block; color: var(--ink); font-size: 12px; margin-bottom: 4px; }
    .security-detail span { color: var(--muted); font-size: 9px; }
    .security-detail .secure-value { color: #27836f; font-weight: 900; }
    .security-modal-note { padding: 11px 12px; color: #7d8f94; background: #f7faf9; border-radius: 11px; font-size: 9px; line-height: 1.7; margin-bottom: 17px; }
    .security-modal-actions { display: flex; gap: 8px; }
    .security-modal-actions > * { flex: 1; }
    .notification-panel { position: fixed; z-index: 45; display: none; width: min(350px, calc(100vw - 30px)); top: 79px; left: max(25px, calc((100vw - 1480px) / 2 + 272px)); border: 1px solid var(--line); border-radius: 17px; overflow: hidden; background: #fff; box-shadow: 0 18px 45px rgba(26,66,66,.15); }
    .notification-panel.open { display: block; animation: dropIn .2s ease both; }
    @keyframes dropIn { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }
    .notification-head { display: flex; justify-content: space-between; align-items: center; padding: 15px 16px 12px; border-bottom: 1px solid #eef3f1; }
    .notification-head strong { font-size: 12px; }
    .notification-head button { color: var(--teal); background: transparent; border: 0; font-size: 9px; font-weight: 800; }
    .notification-item { display: flex; gap: 10px; padding: 13px 16px; border-bottom: 1px solid #f0f4f2; }
    .notification-item:last-child { border: 0; }
    .notification-item.unread { background: #f7fbf9; }
    .notification-icon { width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center; flex: 0 0 auto; color: var(--teal); background: var(--mint); }
    .notification-icon.orange { color: #b86e20; background: var(--amber-soft); }
    .notification-icon .icon { width: 15px; height: 15px; }
    .notification-copy { min-width: 0; }
    .notification-copy strong { display: block; font-size: 10px; margin-bottom: 4px; }
    .notification-copy p { margin: 0; color: var(--muted); font-size: 9px; line-height: 1.6; }
    .notification-copy time { display: block; color: #a9b7b4; font-size: 8px; margin-top: 5px; }

    .toast { position: fixed; z-index: 100; left: 50%; bottom: 28px; transform: translate(-50%, 18px); opacity: 0; pointer-events: none; background: #133d3f; color: #fff; border-radius: 12px; padding: 12px 16px; display: flex; align-items: center; gap: 8px; box-shadow: 0 12px 30px rgba(9,43,43,.22); font-size: 11px; transition: opacity .25s, transform .25s; }
    .toast.show { opacity: 1; transform: translate(-50%, 0); }
    .toast .icon { width: 16px; height: 16px; color: #a6e1c9; }

    @media (max-width: 1120px) {
      .main-content { padding-right: 27px; padding-left: 27px; }
      .hero-content { width: 62%; }
      .hero-art { left: 0; width: 39%; }
      .provider-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .service-grid { gap: 8px; }
    }
    @media (max-width: 900px) {
      .app-shell { display: block; }
      .sidebar { display: none; }
      .main-content { padding: 22px 22px 84px; }
      .mobile-nav { position: fixed; z-index: 30; display: flex; right: 12px; left: 12px; bottom: max(12px, env(safe-area-inset-bottom)); height: 63px; padding: 7px 9px; border: 1px solid rgba(214,228,222,.9); border-radius: 19px; background: rgba(255,255,255,.94); box-shadow: 0 12px 35px rgba(17,56,58,.14); backdrop-filter: blur(12px); justify-content: space-around; }
      .mobile-nav .nav-item { width: auto; min-width: 54px; padding: 6px 10px; flex-direction: column; gap: 4px; justify-content: center; text-align: center; border-radius: 12px; }
      .mobile-nav .nav-item.active::before { display: none; }
      .mobile-nav .nav-item span:not(.icon):not(.nav-count) { flex: initial; font-size: 9px; }
      .mobile-nav .nav-count { position: absolute; top: 3px; left: 8px; min-width: 15px; height: 15px; font-size: 8px; border-radius: 5px; }
      .mobile-nav .nav-item:nth-child(n+7) { display: none; }
      .notification-panel { top: 72px; left: 17px; }
      .hero-card { min-height: 268px; }
      .hero-content { width: 70%; }
      .hero-art { opacity: .78; width: 38%; left: -3%; }
    }
    @media (max-width: 680px) {
      body { background: var(--paper); }
      .main-content { padding: 17px 15px max(90px, calc(78px + env(safe-area-inset-bottom))); }
      .topbar { margin-bottom: 22px; }
      .top-profile-copy, .date-label { display: none; }
      .top-profile { border: 0; padding: 0; }
      .top-profile .avatar { width: 37px; height: 37px; }
      .welcome-row { align-items: start; margin-bottom: 17px; }
      .welcome-copy h1 { font-size: 24px; }
      .welcome-copy p { font-size: 11px; }
      .new-service-btn { padding: 10px 11px; }
      .new-service-btn span:not(.icon) { display: none; }
      .hero-card { min-height: 310px; padding: 24px 21px; align-items: start; }
      .hero-content { width: 100%; }
      .hero-card h2 { max-width: 250px; font-size: 25px; }
      .hero-card p { max-width: 270px; font-size: 11px; }
      .hero-art { width: 230px; height: 180px; left: -22px; bottom: -5px; opacity: .66; }
      .hero-float { left: 17px; top: auto; bottom: 28px; transform: scale(.9); transform-origin: left bottom; }
      .hero-stat { left: auto; right: 18px; bottom: 24px; transform: scale(.88); transform-origin: right bottom; }
      .hero-actions { margin-top: 17px; }
      .hero-actions .hero-link { display: none; }
      .search-row { margin-bottom: 22px; gap: 8px; }
      .search-shortcut { display: none; }
      .search-box input { padding-left: 12px; height: 46px; }
      .filter-button { height: 46px; min-width: 44px; }
      .section-heading { margin-bottom: 11px; }
      .section-heading h2 { font-size: 15px; }
      .section-heading p { font-size: 10px; }
      .service-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-bottom: 21px; }
      .service-card { padding: 12px; }
      .service-icon { margin-bottom: 9px; }
      .dashboard-columns { grid-template-columns: 1fr; gap: 11px; }
      .panel { padding: 16px; }
      .track-area { gap: 8px; }
      .track-side { width: 110px; }
      .provider-grid { grid-template-columns: 1fr; gap: 8px; }
      .provider-card { padding: 12px; }
      .page-title { align-items: start; margin-top: 5px; margin-bottom: 19px; }
      .page-title h1 { font-size: 24px; }
      .page-title .primary-button { padding: 9px 11px; }
      .order-row { gap: 9px; padding: 13px 11px; flex-wrap: wrap; }
      .order-row-date { margin-right: auto; }
      .order-row-action { width: 100%; padding-top: 9px; border-top: 1px solid #eef3f1; text-align: right; }
      .all-services-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
      .large-service { min-height: 132px; padding: 14px; }
      .favorite-grid, .payment-layout { grid-template-columns: 1fr; }
      .notification-panel { top: 67px; left: 15px; right: 15px; width: auto; }
      .modal-card { border-radius: 20px; }
      .modal-head { padding: 20px 18px 0; }
      .modal-body { padding: 17px 18px 20px; }
      .success-modal { padding: 28px 19px 23px; }
    }
    @media (max-width: 390px) {
      .track-side { width: 98px; }
      .track-step { font-size: 9px; }
      .order-price { display: none; }
      .topbar-actions { gap: 7px; }
      .round-button { width: 37px; height: 37px; }
    }
    @media (max-width: 1120px) {
      .admin-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    }
    @media (max-width: 900px) {
      .admin-heading { align-items: start; flex-direction: column; }
      .admin-heading-actions { width: 100%; }
      .admin-content-grid, .admin-lower-grid { grid-template-columns: 1fr; }
      .admin-audit-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 680px) {
      .admin-security-banner { align-items: start; flex-wrap: wrap; padding: 14px; }
      .security-metrics { width: 100%; justify-content: space-between; }
      .security-metric { flex: 1; min-width: 0; }
      .admin-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
      .admin-kpi { padding: 12px; }
      .admin-kpi strong { font-size: 18px; }
      .admin-panel { padding: 14px; }
      .admin-panel-head { flex-wrap: wrap; }
      .chart-tabs { margin-right: auto; }
      .admin-heading-actions .admin-live { order: 3; }
      .admin-heading-actions .primary-button, .admin-heading-actions .ghost-button { flex: 1; }
    }
  </style>
</head>
<body>
  <a class="skip-link" href="#mainContent">تجاوز إلى المحتوى الرئيسي</a>
  <div class="app-shell">
    <aside class="sidebar" aria-label="القائمة الرئيسية">
      <a class="brand" href="#" data-view="home" aria-label="عزوتك - الرئيسية">
        <span class="brand-mark"><span class="icon" data-icon="sparkles"></span></span>
        <span><span class="brand-name">عزوتك</span><span class="brand-sub">عزوة من أهل البلد</span></span>
      </a>

      <button class="location-switcher" type="button" id="locationButton">
        <span class="icon" data-icon="location"></span>
        <span class="location-copy"><small>موقعك الحالي</small><strong>عمّان، الأردن</strong></span>
        <span class="icon" data-icon="chevron-down"></span>
      </button>

      <nav>
        <div class="nav-label">القائمة</div>
        <div class="nav-list">
          <button class="nav-item active" data-view="home" type="button"><span class="icon" data-icon="home"></span><span>الرئيسية</span></button>
          <button class="nav-item" data-view="orders" type="button"><span class="icon" data-icon="clipboard"></span><span>طلباتي</span><span class="nav-count" id="ordersBadge">2</span></button>
          <button class="nav-item" data-view="services" type="button"><span class="icon" data-icon="grid"></span><span>الخدمات</span></button>
          <button class="nav-item" data-view="favorites" type="button"><span class="icon" data-icon="heart"></span><span>المفضلة</span></button>
          <button class="nav-item" data-view="payments" type="button"><span class="icon" data-icon="wallet"></span><span>المدفوعات</span></button>
        </div>
      </nav>
      <div class="side-divider"></div>
      <nav>
        <div class="nav-label">المساعدة</div>
        <div class="nav-list">
          <button class="nav-item" data-action="help" type="button"><span class="icon" data-icon="help"></span><span>مركز المساعدة</span></button>
          <button class="nav-item" data-view="settings" type="button"><span class="icon" data-icon="settings"></span><span>الإعدادات</span></button>
        </div>
      </nav>
      <!-- ADMIN_UI_START -->
      <div class="side-divider"></div>
      <nav>
        <div class="nav-label">الإدارة</div>
        <div class="nav-list">
          <button class="nav-item admin-access" data-view="admin" type="button"><span class="icon" data-icon="shield"></span><span>لوحة المدير العام</span><span class="admin-chip">ADMIN</span></button>
        </div>
      </nav>
      <!-- ADMIN_UI_END -->
      <div class="sidebar-spacer"></div>
      <div class="support-card">
        <div class="mini-icon"><span class="icon" data-icon="headphones"></span></div>
        <strong>محتاج مساعدة؟</strong>
        <p>فريق عزوتك معك من ٨ صباحاً حتى ١٠ مساءً.</p>
        <button type="button" data-action="help">تواصل معنا ←</button>
      </div>
      <div class="profile-mini">
        <div class="avatar">ل</div>
        <div class="profile-mini-copy"><strong>ليان أحمد</strong><small>الحساب الشخصي</small></div>
        <span class="icon" data-icon="more"></span>
      </div>
    </aside>

    <main class="main-content" id="mainContent" tabindex="-1">
      <header class="topbar">
        <div class="date-label">الإثنين، <strong>٢٦ أكتوبر ٢٠٢٦</strong></div>
        <div class="topbar-actions">
          <button class="round-button" type="button" id="notificationButton" aria-label="الإشعارات" aria-expanded="false"><span class="icon" data-icon="bell"></span><i class="notification-dot"></i></button>
          <div class="top-profile" id="profileButton" role="button" tabindex="0" aria-label="فتح الحساب"><div class="top-profile-copy"><strong>ليان أحمد</strong><small>آخر دخول: الآن</small></div><div class="avatar">ل</div></div>
        </div>
      </header>

      <!-- Home -->
      <section class="view active" id="home-view" data-page="home">
        <div class="welcome-row">
          <div class="welcome-copy">
            <h1>مساء الخير، ليان <span class="sparkle">✦</span></h1>
            <p>شو حابة ننجز لك اليوم؟</p>
          </div>
          <button class="primary-button new-service-btn" type="button" data-book="تنظيف وتعقيم"><span class="icon" data-icon="plus"></span><span>اطلب خدمة</span></button>
        </div>

        <article class="hero-card">
          <div class="hero-content">
            <div class="hero-eyebrow"><span class="icon" data-icon="sparkles"></span> عزوة من أهل الأردن</div>
            <h2>خليها علينا، وخلّي وقتك إلك.</h2>
            <p>من صيانة البيت لتنظيفه ونقل أغراضك — بنوصلك بمزوّدين موثوقين في عمّان وكل الأردن.</p>
            <div class="hero-actions"><button class="primary-button" type="button" data-book="تنظيف وتعقيم">احجز خدمة الآن <span class="icon" data-icon="arrow-left"></span></button><button class="hero-link" type="button" data-action="intro">كيف بتشتغل عزوتك؟</button></div>
          </div>
          <div class="hero-float"><span class="float-check"><span class="icon" data-icon="check"></span></span> مزوّدون موثّقون</div>
          <div class="hero-stat"><strong>+ ٤,٨٠٠</strong><span>طلب تم إنجازه بأمان</span></div>
          <svg class="hero-art" viewBox="0 0 350 245" aria-hidden="true">
            <circle class="art-glow" cx="212" cy="145" r="111"/>
            <path class="art-dark" d="M88 224h199c5 0 9 4 9 9v12H78v-12c0-5 4-9 10-9Z"/>
            <path class="art-paper" d="M143 79h126v146H143z" opacity=".95"/>
            <path class="art-dark" d="m132 82 73-53 75 53-8 10-67-47-65 47Z"/>
            <path class="art-window" d="M163 106h35v37h-35zM215 106h35v37h-35z"/>
            <path class="art-line" d="M180 106v37M232 106v37M163 124h87" opacity=".32"/>
            <path class="art-paper" d="M184 173h42v52h-42z"/>
            <circle class="art-person" cx="102" cy="129" r="18"/>
            <path class="art-person" d="M76 224c2-42 13-66 27-66s26 24 28 66Z"/>
            <path class="art-clothes" d="M79 184c10-14 36-14 47 0l-5 40H82Z"/>
            <path class="art-dark" d="M94 111c7-13 28-10 30 4-8 4-18 6-30 4Z"/>
            <path class="art-paper" d="M69 171c12 3 17 9 18 17l-23 9c-5 2-10-2-8-7l13-19Z"/>
            <path class="art-line" d="m56 194 22-9" opacity=".7"/>
          </svg>
        </article>

        <div class="search-row">
          <div class="search-box"><span class="icon" data-icon="search"></span><input id="serviceSearch" type="search" placeholder="شو الخدمة اللي بتدوري عليها؟" autocomplete="off" /><span class="search-shortcut">/</span></div>
          <button class="filter-button" type="button" id="filterButton" aria-label="تصفية الخدمات"><span class="icon" data-icon="sliders"></span></button>
        </div>

        <div class="section-heading"><div><h2>شو بدك ننجز لك اليوم؟</h2><p>خدمات أساسية بلمسة واحدة</p></div><button class="text-button" type="button" data-view="services">كل الخدمات <span class="icon" data-icon="arrow-left"></span></button></div>
        <div class="service-grid" id="homeServices">
          <button class="service-card" type="button" data-service-card data-service="صيانة منزلية" data-search="صيانة منزلية تصليح فني سباكة كهرباء">
            <span class="service-icon green"><span class="icon" data-icon="wrench"></span></span><strong>صيانة منزلية</strong><small>+ ٢٤ مزوّداً</small><span class="icon service-arrow" data-icon="arrow-left"></span>
          </button>
          <button class="service-card" type="button" data-service-card data-service="تنظيف وتعقيم" data-search="تنظيف تعقيم بيت مكتب">
            <span class="service-icon amber"><span class="icon" data-icon="sparkles"></span></span><strong>تنظيف وتعقيم</strong><small>+ ١٨ مزوّداً</small><span class="icon service-arrow" data-icon="arrow-left"></span>
          </button>
          <button class="service-card" type="button" data-service-card data-service="نقل وشحن" data-search="نقل شحن عفش توصيل">
            <span class="service-icon purple"><span class="icon" data-icon="truck"></span></span><strong>نقل وشحن</strong><small>+ ١٢ مزوّداً</small><span class="icon service-arrow" data-icon="arrow-left"></span>
          </button>
          <button class="service-card" type="button" data-service-card data-service="كهرباء وسباكة" data-search="كهرباء سباكة طوارئ">
            <span class="service-icon blue"><span class="icon" data-icon="bolt"></span></span><strong>كهرباء وسباكة</strong><small>+ ٣١ مزوّداً</small><span class="icon service-arrow" data-icon="arrow-left"></span>
          </button>
          <div class="no-results" id="homeNoResults">ما لقينا خدمة بهالاسم. جرّبي كلمة ثانية.</div>
        </div>

        <div class="dashboard-columns">
          <article class="panel order-panel">
            <div class="panel-header"><div><h3>طلبك الحالي</h3><p id="orderMeta">آخر تحديث منذ ٣ دقائق</p></div><span class="status-pill" id="orderStatus">قيد التنفيذ</span></div>
            <div class="order-summary"><div class="provider-avatar">ي</div><div class="order-summary-copy"><strong id="orderTitle">صيانة تكييف سبليت</strong><small id="orderProvider">مع يوسف للخدمات المنزلية · طلب #SN-2841</small></div><div class="order-price"><strong>١٨ د.أ</strong><small>تقديري</small></div></div>
            <div class="track-area"><div class="fake-map"><div class="map-route"></div><span class="map-label">الدوار السابع، عمّان</span></div><div class="track-side"><div class="track-step complete"><span class="step-dot"></span><span>تم قبول الطلب</span></div><div class="track-step current"><span class="step-dot"></span><span>الفني بالطريق</span></div><div class="track-step"><span class="step-dot"></span><span>اكتملت الخدمة</span></div></div></div>
            <div class="order-footer"><button class="text-button" type="button" data-action="track">تتبع الطلب <span class="icon" data-icon="arrow-left"></span></button></div>
          </article>
          <article class="panel trust-panel">
            <div class="trust-symbol"><span class="icon" data-icon="shield"></span></div>
            <div class="panel-header"><div><h3>كل شيء واضح من البداية</h3><p>راحة بالك أولويتنا</p></div></div>
            <div class="trust-points"><div class="trust-point"><span class="check"><span class="icon" data-icon="check"></span></span><span>أسعار واضحة قبل تأكيد الطلب</span></div><div class="trust-point"><span class="check"><span class="icon" data-icon="check"></span></span><span>مزوّدون تم التحقق منهم</span></div><div class="trust-point"><span class="check"><span class="icon" data-icon="check"></span></span><span>دعم محلي داخل الأردن</span></div></div>
            <div class="trust-footer">ادفع بالطريقة اللي تناسبك: <strong>CliQ، بطاقة، أو عند الإنجاز.</strong></div>
          </article>
        </div>

        <div class="section-heading"><div><h2>مزوّدون قريبون منك</h2><p>اختيارات أهل عمّان المفضّلة</p></div><button class="text-button" type="button" data-view="favorites">شوف المفضلة <span class="icon" data-icon="arrow-left"></span></button></div>
        <div class="provider-grid">
          <button class="provider-card" type="button" data-book="تنظيف وتعقيم"><span class="provider-logo one">ل ب</span><span class="provider-copy"><strong>لمسة بيتك</strong><span class="provider-meta"><span class="star">★</span> ٤.٩ · تنظيف منازل</span></span><span class="icon" data-icon="chevron-left"></span></button>
          <button class="provider-card" type="button" data-book="صيانة منزلية"><span class="provider-logo two">ف م</span><span class="provider-copy"><strong>الفني الماهر</strong><span class="provider-meta"><span class="star">★</span> ٤.٨ · صيانة عامة</span></span><span class="icon" data-icon="chevron-left"></span></button>
          <button class="provider-card" type="button" data-book="نقل وشحن"><span class="provider-logo three">ن</span><span class="provider-copy"><strong>النشامى للنقل</strong><span class="provider-meta"><span class="star">★</span> ٤.٩ · نقل وشحن</span></span><span class="icon" data-icon="chevron-left"></span></button>
        </div>
      </section>

      <!-- Orders -->
      <section class="view" id="orders-view" data-page="orders">
        <div class="page-title"><div><h1>طلباتي</h1><p>تابعي كل خدماتك من مكان واحد.</p></div><button class="primary-button" type="button" data-book="تنظيف وتعقيم"><span class="icon" data-icon="plus"></span> طلب جديد</button></div>
        <div class="filter-pills"><button class="filter-pill active" type="button">الكل (٣)</button><button class="filter-pill" type="button">قيد التنفيذ (١)</button><button class="filter-pill" type="button">مكتملة (٢)</button></div>
        <div class="orders-list">
          <article class="order-row"><div class="provider-avatar">ي</div><div class="order-row-copy"><strong>صيانة تكييف سبليت</strong><p>مع يوسف للخدمات المنزلية · #SN-2841</p></div><div class="order-row-date"><strong>اليوم، ٥:٣٠ م</strong>الدوار السابع</div><span class="status-pill">قيد التنفيذ</span><button class="order-row-action" type="button" data-action="track">تتبع الطلب ←</button></article>
          <article class="order-row"><div class="provider-avatar avatar-warm">ر</div><div class="order-row-copy"><strong>تنظيف شقة كاملة</strong><p>مع راحة ونظافة · #SN-2798</p></div><div class="order-row-date"><strong>١٩ أكتوبر ٢٠٢٦</strong>خلدا، عمّان</div><span class="status-pill done">مكتمل</span><button class="order-row-action" type="button" data-action="rate">قيّمي الخدمة ★</button></article>
          <article class="order-row"><div class="provider-avatar avatar-indigo">ن</div><div class="order-row-copy"><strong>نقل أغراض</strong><p>مع النشامى للنقل · #SN-2713</p></div><div class="order-row-date"><strong>٧ أكتوبر ٢٠٢٦</strong>إربد، الأردن</div><span class="status-pill done">مكتمل</span><button class="order-row-action" type="button" data-action="rate">قيّمي الخدمة ★</button></article>
        </div>
      </section>

      <!-- Services -->
      <section class="view" id="services-view" data-page="services">
        <div class="page-title"><div><h1>كل الخدمات</h1><p>اختاري الخدمة المناسبة وخلّي الباقي علينا.</p></div><button class="ghost-button" type="button" data-action="intro"><span class="icon" data-icon="sparkles"></span> كيف بتشتغل عزوتك؟</button></div>
        <div class="search-row"><div class="search-box"><span class="icon" data-icon="search"></span><input class="service-page-search" type="search" placeholder="ابحثي عن خدمة..." autocomplete="off" /></div><button class="filter-button" type="button" data-action="filter"><span class="icon" data-icon="sliders"></span></button></div>
        <div class="all-services-grid">
          <button class="service-card large-service" type="button" data-service-card data-service="صيانة منزلية" data-search="صيانة منزلية تصليح"><span class="service-icon green"><span class="icon" data-icon="wrench"></span></span><strong>صيانة منزلية</strong><small>سباكة، نجارة، أجهزة</small></button>
          <button class="service-card large-service" type="button" data-service-card data-service="تنظيف وتعقيم" data-search="تنظيف تعقيم"><span class="service-icon amber"><span class="icon" data-icon="sparkles"></span></span><strong>تنظيف وتعقيم</strong><small>للبيت والمكتب</small></button>
          <button class="service-card large-service" type="button" data-service-card data-service="نقل وشحن" data-search="نقل شحن"><span class="service-icon purple"><span class="icon" data-icon="truck"></span></span><strong>نقل وشحن</strong><small>عفش، طرود، توصيل</small></button>
          <button class="service-card large-service" type="button" data-service-card data-service="كهرباء وسباكة" data-search="كهرباء سباكة"><span class="service-icon blue"><span class="icon" data-icon="bolt"></span></span><strong>كهرباء وسباكة</strong><small>خدمة طوارئ ٢٤/٧</small></button>
          <button class="service-card large-service" type="button" data-service-card data-service="دهان وترميم" data-search="دهان ترميم ديكور"><span class="service-icon green"><span class="icon" data-icon="paint"></span></span><strong>دهان وترميم</strong><small>جدّدي مساحة بيتك</small></button>
          <button class="service-card large-service" type="button" data-service-card data-service="صيانة سيارات" data-search="سيارات غيار زيت"><span class="service-icon amber"><span class="icon" data-icon="car"></span></span><strong>صيانة سيارات</strong><small>لحد باب البيت</small></button>
          <button class="service-card large-service" type="button" data-service-card data-service="حدائق ومسابح" data-search="حدائق مسابح زراعة"><span class="service-icon purple"><span class="icon" data-icon="leaf"></span></span><strong>حدائق ومسابح</strong><small>عناية موسمية</small></button>
          <button class="service-card large-service" type="button" data-service-card data-service="خدمات المناسبات" data-search="مناسبات ضيافة"><span class="service-icon blue"><span class="icon" data-icon="gift"></span></span><strong>خدمات المناسبات</strong><small>خلّي مناسبتك أسهل</small></button>
        </div>
      </section>

      <!-- Favorites -->
      <section class="view" id="favorites-view" data-page="favorites">
        <div class="page-title"><div><h1>المفضلة</h1><p>مزودوك المفضلون دائماً على بُعد لمسة.</p></div><button class="ghost-button" type="button" data-view="services">اكتشفي مزودين</button></div>
        <div class="favorite-grid">
          <article class="favorite-card"><span class="provider-logo one">ل ب</span><span class="provider-copy"><strong>لمسة بيتك</strong><span class="provider-meta"><span class="star">★</span> ٤.٩ · ١٢ خدمة سابقة</span></span><button type="button" aria-label="إزالة من المفضلة" data-action="favorite"><span class="icon" data-icon="heart"></span></button></article>
          <article class="favorite-card"><span class="provider-logo two">ف م</span><span class="provider-copy"><strong>الفني الماهر</strong><span class="provider-meta"><span class="star">★</span> ٤.٨ · ٨ خدمات سابقة</span></span><button type="button" aria-label="إزالة من المفضلة" data-action="favorite"><span class="icon" data-icon="heart"></span></button></article>
          <article class="favorite-card"><span class="provider-logo three">ن</span><span class="provider-copy"><strong>النشامى للنقل</strong><span class="provider-meta"><span class="star">★</span> ٤.٩ · ٣ خدمات سابقة</span></span><button type="button" aria-label="إزالة من المفضلة" data-action="favorite"><span class="icon" data-icon="heart"></span></button></article>
        </div>
      </section>

      <!-- Payments -->
      <section class="view" id="payments-view" data-page="payments">
        <div class="page-title"><div><h1>المدفوعات</h1><p>خيارات دفع بسيطة وآمنة في الأردن.</p></div><button class="primary-button" type="button" data-action="payment"><span class="icon" data-icon="plus"></span> إضافة طريقة</button></div>
        <div class="payment-layout"><article class="payment-card"><span class="card-label">بطاقة الدفع الأساسية</span><div class="card-number">••••  4821</div><div class="card-bottom"><span>LIAN AHMAD</span><strong>VISA</strong></div></article><div class="payment-methods"><div class="method-row"><span class="method-icon"><span class="icon" data-icon="credit-card"></span></span><span><strong>بطاقة بنكية</strong><small>Visa تنتهي بـ ٤٨٢١</small></span><span class="icon" data-icon="check"></span></div><div class="method-row"><span class="method-icon cliq"><span class="icon" data-icon="zap"></span></span><span><strong>CliQ</strong><small>الدفع الفوري من بنكك</small></span><span class="icon" data-icon="chevron-left"></span></div><div class="method-row"><span class="method-icon cash"><span class="icon" data-icon="hand"></span></span><span><strong>الدفع عند الإنجاز</strong><small>كاش أو بطاقة للمزوّد</small></span><span class="icon" data-icon="chevron-left"></span></div></div></div>
      </section>

      <!-- ADMIN_UI_START -->
      <!-- General manager command center -->
      <section class="view admin-view" id="admin-view" data-page="admin">
        <div class="admin-heading">
          <div>
            <div class="admin-eyebrow"><span class="icon" data-icon="shield"></span> مركز القيادة · إدارة عزوتك</div>
            <h1>صباح العمليات، <strong>أستاذ سامر</strong></h1>
            <p>صورة موحّدة للطلبات، الأداء، والمخاطر — بقرار أسرع وأوضح.</p>
          </div>
          <div class="admin-heading-actions">
            <span class="admin-live"><span class="admin-live-dot"></span> مراقبة مباشرة</span>
            <button class="ghost-button" type="button" data-action="admin-login"><span class="icon" data-icon="lock"></span> دخول المدير</button>
            <button class="ghost-button" type="button" data-action="export"><span class="icon" data-icon="download"></span> تصدير التقرير</button>
            <button class="primary-button" type="button" data-action="security"><span class="icon" data-icon="shield"></span> مركز الحماية</button>
          </div>
        </div>

        <div class="admin-security-banner">
          <div class="security-shield"><span class="icon" data-icon="shield"></span></div>
          <div class="security-banner-copy"><strong>طبقة الحماية نشطة — لا توجد حوادث حرجة</strong><p>آخر فحص آلي منذ ٤ دقائق · كل الجلسات الإدارية محمية بالمصادقة متعددة العوامل.</p></div>
          <div class="security-metrics"><div class="security-metric"><strong>٩٨.٤٪</strong><span>تغطية MFA</span></div><div class="security-metric"><strong>٢٧</strong><span>تهديداً محظوراً</span></div><div class="security-metric"><strong>٩٩.٩٨٪</strong><span>جاهزية API</span></div></div>
        </div>

        <div class="admin-kpis">
          <article class="admin-kpi"><div class="admin-kpi-top"><span class="admin-kpi-icon"><span class="icon" data-icon="clipboard"></span></span><span class="kpi-trend">+١٨.٦٪</span></div><label>الطلبات اليوم</label><strong>١,٢٨٤</strong></article>
          <article class="admin-kpi"><div class="admin-kpi-top"><span class="admin-kpi-icon green"><span class="icon" data-icon="wallet"></span></span><span class="kpi-trend">+١٢.٤٪</span></div><label>حجم الخدمات</label><strong>٢٤,٦٨٠ <small>د.أ</small></strong></article>
          <article class="admin-kpi"><div class="admin-kpi-top"><span class="admin-kpi-icon blue"><span class="icon" data-icon="user"></span></span><span class="kpi-trend">+٣.٢٪</span></div><label>المزوّدون النشطون</label><strong>٣١٨</strong></article>
          <article class="admin-kpi"><div class="admin-kpi-top"><span class="admin-kpi-icon amber"><span class="icon" data-icon="star"></span></span><span class="kpi-trend">+٠.٢</span></div><label>رضا العملاء</label><strong>٤.٩ <small>/ ٥</small></strong></article>
          <article class="admin-kpi"><div class="admin-kpi-top"><span class="admin-kpi-icon green"><span class="icon" data-icon="shield"></span></span><span class="kpi-trend down">-١٢.٨٪</span></div><label>محاولات مشبوهة</label><strong>٢٧</strong></article>
        </div>

        <div class="admin-content-grid">
          <article class="admin-panel">
            <div class="admin-panel-head"><div><h3>الأداء المالي</h3><p>حجم الخدمات المكتملة خلال الفترة</p></div><div class="chart-tabs"><button class="chart-tab active" type="button" data-chart-tab="7">٧ أيام</button><button class="chart-tab" type="button" data-chart-tab="30">٣٠ يوماً</button><button class="chart-tab" type="button" data-chart-tab="90">ربع سنوي</button></div></div>
            <div class="revenue-summary"><strong id="adminRevenue">٢٤,٦٨٠ د.أ</strong><span id="adminRevenueTrend">↑ ١٢.٤٪ عن الأسبوع الماضي</span></div>
            <div class="chart-wrap"><svg class="chart-svg" viewBox="0 0 620 178" preserveAspectRatio="none" role="img" aria-label="رسم بياني للأداء المالي"><defs><linearGradient id="adminArea" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#7180bc" stop-opacity=".28"/><stop offset="1" stop-color="#7180bc" stop-opacity=".02"/></linearGradient></defs><line class="chart-grid-line" x1="32" y1="24" x2="606" y2="24"/><line class="chart-grid-line" x1="32" y1="64" x2="606" y2="64"/><line class="chart-grid-line" x1="32" y1="104" x2="606" y2="104"/><line class="chart-grid-line" x1="32" y1="144" x2="606" y2="144"/><path class="chart-area" d="M32 137 C72 124 91 129 125 112 S183 116 207 91 S267 108 295 74 S351 92 378 62 S430 74 459 52 S514 60 536 39 S576 46 606 26 L606 160 L32 160Z"/><path class="chart-line" d="M32 137 C72 124 91 129 125 112 S183 116 207 91 S267 108 295 74 S351 92 378 62 S430 74 459 52 S514 60 536 39 S576 46 606 26"/><circle class="chart-point" cx="32" cy="137" r="3.3"/><circle class="chart-point" cx="125" cy="112" r="3.3"/><circle class="chart-point" cx="207" cy="91" r="3.3"/><circle class="chart-point" cx="295" cy="74" r="3.3"/><circle class="chart-point" cx="378" cy="62" r="3.3"/><circle class="chart-point" cx="459" cy="52" r="3.3"/><circle class="chart-point" cx="536" cy="39" r="3.3"/><circle class="chart-point" cx="606" cy="26" r="3.3"/><text class="chart-label" x="32" y="174">السبت</text><text class="chart-label" x="125" y="174">الأحد</text><text class="chart-label" x="207" y="174">الإثنين</text><text class="chart-label" x="295" y="174">الثلاثاء</text><text class="chart-label" x="388" y="174">الأربعاء</text><text class="chart-label" x="480" y="174">الخميس</text><text class="chart-label" x="570" y="174">اليوم</text></svg></div>
          </article>
          <article class="admin-panel risk-panel">
            <div class="admin-panel-head"><div><h3>مركز المخاطر</h3><p>درجة الأمان التشغيلية الآن</p></div><button class="text-button" type="button" data-action="security">التفاصيل <span class="icon" data-icon="arrow-left"></span></button></div>
            <div class="risk-score"><div class="score-ring"><div><strong>٩٦</strong><span>/ ١٠٠</span></div></div><div class="risk-copy"><strong>الوضع مطمئن</strong><p>تم احتواء كل المحاولات غير المعتادة دون أثر على العملاء.</p></div></div>
            <div class="risk-list"><div class="risk-row"><span class="risk-check"><span class="icon" data-icon="check"></span></span><span>تسجيل دخول المديرين</span><span class="risk-value">MFA نشط</span></div><div class="risk-row"><span class="risk-check"><span class="icon" data-icon="check"></span></span><span>صلاحيات أقل ما يلزم</span><span class="risk-value">مراجعة اليوم</span></div><div class="risk-row"><span class="risk-check"><span class="icon" data-icon="check"></span></span><span>نسخ احتياطية مشفّرة</span><span class="risk-value">منذ ١٢ د</span></div></div>
          </article>
        </div>

        <div class="admin-lower-grid">
          <article class="admin-panel">
            <div class="admin-panel-head"><div><h3>العمليات الحية</h3><p>آخر تحديث: قبل ٣٠ ثانية</p></div><div class="ops-filter"><button class="active" type="button" data-ops-filter="all">الكل</button><button type="button" data-ops-filter="active">نشط</button><button type="button" data-ops-filter="pending">معلّق</button></div></div>
            <div class="operations-table-wrap"><table class="operations-table"><thead><tr><th>الطلب</th><th>الخدمة</th><th>المنطقة</th><th>القيمة</th><th>الحالة</th><th>الوقت</th></tr></thead><tbody><tr><td>#SN-2841</td><td><span class="ops-service"><span class="ops-service-icon"><span class="icon" data-icon="wrench"></span></span>صيانة تكييف</span></td><td>عمّان · السابع</td><td>١٨ د.أ</td><td><span class="ops-status"><i class="status-dot"></i>قيد التنفيذ</span></td><td>الآن</td></tr><tr><td>#SN-2840</td><td><span class="ops-service"><span class="ops-service-icon"><span class="icon" data-icon="sparkles"></span></span>تنظيف منزل</span></td><td>إربد · الحي الشرقي</td><td>٢٢ د.أ</td><td><span class="ops-status"><i class="status-dot"></i>تم التعيين</span></td><td>منذ ٢ د</td></tr><tr><td>#SN-2839</td><td><span class="ops-service"><span class="ops-service-icon"><span class="icon" data-icon="truck"></span></span>نقل أثاث</span></td><td>الزرقاء · الجديدة</td><td>٤٥ د.أ</td><td><span class="ops-status pending"><i class="status-dot"></i>بانتظار مزوّد</span></td><td>منذ ٤ د</td></tr><tr><td>#SN-2838</td><td><span class="ops-service"><span class="ops-service-icon"><span class="icon" data-icon="bolt"></span></span>كهرباء طارئة</span></td><td>عمّان · خلدا</td><td>١٤ د.أ</td><td><span class="ops-status"><i class="status-dot"></i>وصل الفني</span></td><td>منذ ٦ د</td></tr></tbody></table></div>
          </article>
          <article class="admin-panel queue-panel">
            <div class="admin-panel-head"><div><h3>طابور يحتاج قرار</h3><p>طلبات مزودي الخدمة الجدد</p></div><span class="queue-count" id="approvalCount" data-count="3">٣</span></div>
            <div class="approval-list"><div class="approval-item" data-approval-row><span class="approval-avatar">م ن</span><span class="approval-copy"><strong>مؤسسة النخبة للصيانة</strong><span>عمّان · مستندات مكتملة</span></span><span class="approval-actions"><button type="button" data-action="approve" aria-label="اعتماد المزود"><span class="icon" data-icon="check"></span></button><button class="reject" type="button" data-action="reject" aria-label="رفض المزود"><span class="icon" data-icon="x"></span></button></span></div><div class="approval-item" data-approval-row><span class="approval-avatar">ب ع</span><span class="approval-copy"><strong>بيت الراحة للتنظيف</strong><span>إربد · بانتظار الهوية</span></span><span class="approval-actions"><button type="button" data-action="approve" aria-label="اعتماد المزود"><span class="icon" data-icon="check"></span></button><button class="reject" type="button" data-action="reject" aria-label="رفض المزود"><span class="icon" data-icon="x"></span></button></span></div><div class="approval-item" data-approval-row><span class="approval-avatar">س ش</span><span class="approval-copy"><strong>سريع للشحن والنقل</strong><span>الزرقاء · مراجعة يدوية</span></span><span class="approval-actions"><button type="button" data-action="approve" aria-label="اعتماد المزود"><span class="icon" data-icon="check"></span></button><button class="reject" type="button" data-action="reject" aria-label="رفض المزود"><span class="icon" data-icon="x"></span></button></span></div></div>
          </article>
        </div>

        <div class="admin-audit-grid">
          <article class="admin-panel"><div class="admin-panel-head"><div><h3>سجل التدقيق</h3><p>أحداث حساسة مسجلة وغير قابلة للتلاعب</p></div><button class="text-button" type="button" data-action="audit">عرض السجل الكامل <span class="icon" data-icon="arrow-left"></span></button></div><div class="audit-list"><div class="audit-item"><span class="audit-icon green"><span class="icon" data-icon="lock"></span></span><span class="audit-copy"><strong>تم حظر جلسة غير معتادة</strong><span>محاولة من جهاز غير معروف · 185.23.*.*</span></span><span class="audit-time">منذ ٤ د</span></div><div class="audit-item"><span class="audit-icon"><span class="icon" data-icon="user"></span></span><span class="audit-copy"><strong>اعتماد صلاحية مشرف عمليات</strong><span>بواسطة المدير العام · نطاق الطلبات فقط</span></span><span class="audit-time">منذ ٢١ د</span></div><div class="audit-item"><span class="audit-icon orange"><span class="icon" data-icon="settings"></span></span><span class="audit-copy"><strong>تعديل سياسة الإشعارات</strong><span>تغيير مسجل مع سبب وتذكرة #SEC-102</span></span><span class="audit-time">منذ ساعة</span></div></div></article>
          <article class="admin-panel"><div class="admin-panel-head"><div><h3>التغطية التشغيلية</h3><p>توزيع الطلبات حسب المدينة</p></div><span class="admin-live">+ ٨.٢٪ هذا الأسبوع</span></div><div class="coverage-row"><span>عمّان</span><div class="coverage-track"><div class="coverage-fill w68"></div></div><strong>٦٨٪</strong></div><div class="coverage-row"><span>إربد</span><div class="coverage-track"><div class="coverage-fill w19"></div></div><strong>١٩٪</strong></div><div class="coverage-row"><span>الزرقاء</span><div class="coverage-track"><div class="coverage-fill w9"></div></div><strong>٩٪</strong></div><div class="coverage-row"><span>العقبة</span><div class="coverage-track"><div class="coverage-fill w4"></div></div><strong>٤٪</strong></div></article>
        </div>
      </section>
      <!-- ADMIN_UI_END -->

      <!-- Settings -->
      <section class="view" id="settings-view" data-page="settings">
        <div class="page-title"><div><h1>الإعدادات</h1><p>عدّلي تفضيلاتك بالطريقة اللي بتناسبك.</p></div></div>
        <div class="settings-list"><div class="setting-row"><span class="setting-icon"><span class="icon" data-icon="user"></span></span><span class="setting-copy"><strong>البيانات الشخصية</strong><small>ليان أحمد · 079 123 4567</small></span><span class="icon" data-icon="chevron-left"></span></div><div class="setting-row"><span class="setting-icon"><span class="icon" data-icon="bell"></span></span><span class="setting-copy"><strong>التنبيهات</strong><small>تحديثات الطلب والعروض</small></span><button class="toggle on" type="button"><span></span></button></div><div class="setting-row"><span class="setting-icon"><span class="icon" data-icon="location"></span></span><span class="setting-copy"><strong>العناوين المحفوظة</strong><small>الدوار السابع، عمّان</small></span><span class="icon" data-icon="chevron-left"></span></div><div class="setting-row"><span class="setting-icon"><span class="icon" data-icon="lock"></span></span><span class="setting-copy"><strong>الخصوصية والأمان</strong><small>حسابك وبياناتك محمية</small></span><span class="icon" data-icon="chevron-left"></span></div></div>
      </section>
    </main>

    <nav class="mobile-nav" aria-label="التنقل السريع">
      <button class="nav-item active" data-view="home" type="button"><span class="icon" data-icon="home"></span><span>الرئيسية</span></button>
      <button class="nav-item" data-view="orders" type="button"><span class="icon" data-icon="clipboard"></span><span>طلباتي</span><span class="nav-count">2</span></button>
      <button class="nav-item" data-view="services" type="button"><span class="icon" data-icon="grid"></span><span>الخدمات</span></button>
      <button class="nav-item" data-view="favorites" type="button"><span class="icon" data-icon="heart"></span><span>المفضلة</span></button>
      <button class="nav-item" data-view="settings" type="button"><span class="icon" data-icon="settings"></span><span>حسابي</span></button>
      <!-- ADMIN_UI_START -->
      <button class="nav-item admin-access" data-view="admin" type="button"><span class="icon" data-icon="shield"></span><span>إدارة</span></button>
      <!-- ADMIN_UI_END -->
    </nav>
  </div>

  <!-- Booking modal -->
  <div class="overlay" id="bookingModal" role="dialog" aria-modal="true" aria-labelledby="bookingHeading">
    <div class="modal-card">
      <div class="modal-head"><div><p class="modal-kicker">خطوة بسيطة وتبدأ الخدمة</p><h2 id="bookingHeading">احجزي خدمتك</h2></div><button class="close-button" type="button" data-close="bookingModal" aria-label="إغلاق"><span class="icon" data-icon="x"></span></button></div>
      <div class="modal-body">
        <div class="booking-view" id="bookingFormView">
          <div class="booking-service-line"><span class="service-icon green" id="bookingIcon"><span class="icon" data-icon="wrench"></span></span><span class="booking-service-copy"><small>الخدمة المختارة</small><strong id="bookingServiceName">صيانة منزلية</strong></span><button class="change-service" type="button" id="changeService">تغيير</button></div>
          <div class="form-field"><label>وين نوصلك؟ <span>الموقع الافتراضي</span></label><div class="input-shell"><span class="icon" data-icon="location"></span><input id="bookingLocation" value="الدوار السابع، عمّان" /></div></div>
          <div class="form-field"><label>متى يناسبك؟ <span>اختاري اليوم والوقت</span></label><div class="date-options"><button class="date-option selected" type="button"><strong>اليوم</strong>من ٥ - ٧ م</button><button class="date-option" type="button"><strong>غداً</strong>من ١٠ - ١٢ ص</button><button class="date-option" type="button"><strong>لاحقاً</strong>اختاري وقتاً</button></div></div>
          <div class="summary-strip"><span>التكلفة التقديرية تبدأ من</span><strong id="bookingPrice">١٢ <small>د.أ</small></strong></div>
          <div class="safe-note"><span class="icon" data-icon="shield"></span> لا توجد رسوم خفية — السعر النهائي يظهر قبل بدء الخدمة.</div>
          <button class="primary-button full-button" type="button" id="continueBooking">متابعة للتأكيد <span class="icon" data-icon="arrow-left"></span></button>
        </div>
        <div class="confirm-view" id="confirmView">
          <div class="booking-service-line"><span class="service-icon green"><span class="icon" data-icon="check"></span></span><span class="booking-service-copy"><small>راجعي تفاصيل طلبك</small><strong id="confirmService">صيانة منزلية</strong></span></div>
          <div class="confirm-list"><div class="confirm-item"><span>العنوان</span><strong id="confirmLocation">الدوار السابع، عمّان</strong></div><div class="confirm-item"><span>الوقت</span><strong id="confirmTime">اليوم، من ٥ - ٧ م</strong></div><div class="confirm-item"><span>التكلفة التقديرية</span><strong id="confirmPrice">١٢ د.أ</strong></div></div>
          <div class="safe-note"><span class="icon" data-icon="lock"></span> بياناتك وطلبك محميان مع عزوتك.</div>
          <button class="primary-button full-button" type="button" id="confirmBooking">تأكيد الطلب <span class="icon" data-icon="check"></span></button>
          <button class="back-link" type="button" id="backToBooking">← تعديل التفاصيل</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Success modal -->
  <div class="overlay" id="successModal" role="dialog" aria-modal="true" aria-labelledby="successTitle">
    <div class="modal-card success-modal"><div class="success-mark"><span class="icon" data-icon="check"></span></div><h2 id="successTitle">تم تأكيد طلبك بنجاح!</h2><p>يقوم فريقنا الآن بالتنسيق مع أفضل مزود خدمة قريب منك. يمكنك تتبع حالة الطلب من صفحة «طلباتي».</p><div class="success-order-id">رقم الطلب <strong id="successOrderId">#SN-2857</strong></div><div class="success-actions"><button class="primary-button" type="button" id="trackSuccess">تتبع الطلب</button><button class="ghost-button" type="button" id="homeSuccess">الرئيسية</button></div></div>
  </div>

  <!-- Intro modal -->
  <div class="overlay" id="introModal" role="dialog" aria-modal="true" aria-labelledby="introTitle">
    <div class="modal-card intro-modal"><div class="intro-visual"><div class="intro-icon" id="introIcon"><span class="icon" data-icon="sparkles"></span></div></div><div class="intro-content"><div class="intro-progress"><span class="active"></span><span></span><span></span></div><h2 id="introTitle">كل خدماتك بضغطة زر</h2><p id="introText">ابحثي عن أفضل الفنيين ومزودي الخدمات في منطقتك بكل سهولة — من عمّان لإربد والزرقاء.</p><button class="primary-button" type="button" id="introNext">التالي <span class="icon" data-icon="arrow-left"></span></button><br /><button class="back-link" type="button" data-close="introModal">تخطي التعريف</button></div></div>
  </div>

  <!-- Login / sign up -->
  <div class="overlay" id="authModal" role="dialog" aria-modal="true" aria-labelledby="authTitle">
    <div class="modal-card auth-modal">
      <button class="close-button auth-close" type="button" data-close="authModal" aria-label="إغلاق"><span class="icon" data-icon="x"></span></button>
      <div class="auth-brand"><span class="icon" data-icon="sparkles"></span></div>
      <h2 id="authTitle">مرحباً بك في الأفضل!</h2>
      <p>سجّل الآن لتستمتع بتجربة خدمات سلسة وموثوقة في كل أنحاء الأردن.</p>
      <div class="auth-field" id="phoneField"><span>+962</span><input id="phoneInput" inputmode="tel" autocomplete="tel-national" placeholder="رقم الموبايل" aria-label="رقم الموبايل الأردني" aria-describedby="phoneError" /></div>
      <p class="auth-error" id="phoneError" hidden>اكتبي رقم موبايل أردني صحيح من ٩ أرقام.</p>
      <button class="primary-button full-button" type="button" id="authContinue">ابدأ رحلتك الآن <span class="icon" data-icon="arrow-left"></span></button>
      <p class="auth-footnote">بالمتابعة، أنت توافق على <strong>شروط الاستخدام</strong> و<strong>سياسة الخصوصية</strong>.</p>
      <div class="auth-divider">أو</div>
      <button class="auth-secondary" type="button" id="guestExplore">استكشف التطبيق كزائر</button>
    </div>
  </div>

  <!-- ADMIN_UI_START -->
  <!-- Admin IAM + MFA login -->
  <div class="overlay" id="adminAuthModal" role="dialog" aria-modal="true" aria-labelledby="adminAuthTitle">
    <div class="modal-card admin-auth-modal">
      <div class="modal-head"><div><p class="modal-kicker">IAM · MFA · RBAC</p><h2 id="adminAuthTitle">دخول المدير العام</h2></div><button class="close-button" type="button" data-close="adminAuthModal" aria-label="إغلاق"><span class="icon" data-icon="x"></span></button></div>
      <div class="modal-body"><div class="admin-auth-badge"><span class="icon" data-icon="shield"></span></div><p class="admin-auth-copy">هذه منطقة محمية. استخدم حساباً إدارياً مفعّلاً مع كلمة مرور ورمز تطبيق المصادقة.</p><div class="admin-auth-field"><span class="icon" data-icon="user"></span><input id="adminUsername" autocomplete="username" placeholder="اسم المستخدم الإداري" aria-label="اسم المستخدم الإداري" /></div><div class="admin-auth-field"><span class="icon" data-icon="lock"></span><input id="adminPassword" type="password" autocomplete="current-password" placeholder="كلمة المرور" aria-label="كلمة المرور" /></div><div class="admin-auth-field"><span class="icon" data-icon="shield"></span><input id="adminMfaCode" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="رمز MFA من ٦ أرقام" aria-label="رمز MFA" /></div><p class="admin-auth-error" id="adminAuthError" hidden>تعذر تسجيل الدخول. تحقّق من البيانات ورمز المصادقة.</p><button class="primary-button full-button" type="button" id="adminLoginButton">تسجيل دخول آمن <span class="icon" data-icon="arrow-left"></span></button><p class="admin-auth-note"><span class="icon" data-icon="lock"></span> الجلسة HttpOnly، والصلاحيات تُفحص على الخادم لا على الواجهة.</p></div>
    </div>
  </div>

  <!-- Security operations modal -->
  <div class="overlay" id="securityModal" role="dialog" aria-modal="true" aria-labelledby="securityModalTitle">
    <div class="modal-card security-modal">
      <div class="modal-head"><div><p class="modal-kicker">Security Operations Center</p><h2 id="securityModalTitle">مركز الحماية</h2></div><button class="close-button" type="button" data-close="securityModal" aria-label="إغلاق"><span class="icon" data-icon="x"></span></button></div>
      <div class="security-modal-body"><div class="security-modal-intro"><div class="security-shield"><span class="icon" data-icon="shield"></span></div><div><strong>الحالة العامة: محمية</strong><span>لا توجد حوادث حرجة مفتوحة · آخر تقييم ٢٦ أكتوبر ٢٠٢٦</span></div></div><div class="security-detail-list"><div class="security-detail"><strong>٩٨.٤٪</strong><span class="secure-value">تغطية المصادقة متعددة العوامل</span></div><div class="security-detail"><strong>٢٧</strong><span>محاولات مشبوهة محظورة اليوم</span></div><div class="security-detail"><strong>١٢ دقيقة</strong><span>منذ آخر نسخة احتياطية مشفّرة</span></div><div class="security-detail"><strong>٠</strong><span class="secure-value">ثغرات حرجة غير معالجة</span></div></div><div class="security-modal-note"><strong>ملاحظة تشغيلية:</strong> هذه الواجهة جزء من طبقات الحماية ولا تستبدل جدار حماية تطبيقات الويب، إدارة الهوية، مراقبة السجلات، واختبارات الاختراق في بيئة الإنتاج.</div><div class="security-modal-actions"><button class="primary-button" type="button" id="reviewSessions"><span class="icon" data-icon="lock"></span> مراجعة الجلسات</button><button class="ghost-button" type="button" id="rotateKeys"><span class="icon" data-icon="settings"></span> طلب تدوير المفاتيح</button></div></div>
    </div>
  </div>
  <!-- ADMIN_UI_END -->

  <!-- Notifications -->
  <div class="notification-panel" id="notificationPanel" aria-label="الإشعارات"><div class="notification-head"><strong>الإشعارات</strong><button type="button" id="markRead">تحديد الكل كمقروء</button></div><div class="notification-item unread"><span class="notification-icon"><span class="icon" data-icon="truck"></span></span><span class="notification-copy"><strong>الفني بالطريق إليك 🚗</strong><p>يوسف من «الفني الماهر» سيصل خلال ١٢ دقيقة.</p><time>منذ ٣ دقائق</time></span></div><div class="notification-item unread"><span class="notification-icon orange"><span class="icon" data-icon="star"></span></span><span class="notification-copy"><strong>رأيك يهمنا ⭐</strong><p>كيف كانت تجربتك مع عزوتك اليوم؟ قيّمي الخدمة الآن.</p><time>منذ ساعة</time></span></div><div class="notification-item"><span class="notification-icon"><span class="icon" data-icon="gift"></span></span><span class="notification-copy"><strong>عرض خاص لك</strong><p>خصم ١٥٪ على أول طلب تنظيف هذا الشهر.</p><time>أمس</time></span></div></div>

  <div class="toast" id="toast" role="status" aria-live="polite"><span class="icon" data-icon="check"></span><span id="toastText">تم حفظ التغييرات</span></div>

  <script nonce="__CSP_NONCE__">
    const iconPaths = {
      sparkles: '<path d="m12 3-1.25 4.1L7 8.5l3.75 1.4L12 14l1.25-4.1L17 8.5l-3.75-1.4L12 3Z"/><path d="m19 14-.65 2.1L16.3 17l2.05.9L19 20l.65-2.1 2.05-.9-2.05-.9L19 14ZM5 14l-.6 1.8L2.6 17l1.8.7L5 19.5l.6-1.8 1.8-.7-1.8-.7L5 14Z"/>',
      home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1V10Z"/>',
      clipboard: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4.5V3h6v1.5M8 9h8M8 13h6M8 17h3"/>',
      grid: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
      heart: '<path d="M20.8 8.7c0 5.2-8.8 10.4-8.8 10.4S3.2 13.9 3.2 8.7A4.7 4.7 0 0 1 12 6.3a4.7 4.7 0 0 1 8.8 2.4Z"/>',
      wallet: '<path d="M4 6.5A2.5 2.5 0 0 1 6.5 4H19v16H6.5A2.5 2.5 0 0 1 4 17.5v-11Z"/><path d="M4 7h15M15 13h4M16 13a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z"/>',
      help: '<circle cx="12" cy="12" r="9"/><path d="M9.7 9a2.4 2.4 0 1 1 4 1.8c-1.2 1-1.7 1.3-1.7 2.7M12 17h.01"/>',
      settings: '<path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z"/><path d="m19.4 15 .1.1a1.7 1.7 0 0 1-2.4 2.4l-.1-.1a1.7 1.7 0 0 0-2.9 1.2v.2a1.7 1.7 0 0 1-3.4 0v-.2a1.7 1.7 0 0 0-2.9-1.2l-.1.1a1.7 1.7 0 0 1-2.4-2.4l.1-.1a1.7 1.7 0 0 0-1.2-2.9h-.2a1.7 1.7 0 0 1 0-3.4h.2a1.7 1.7 0 0 0 1.2-2.9l-.1-.1a1.7 1.7 0 0 1 2.4-2.4l.1.1a1.7 1.7 0 0 0 2.9-1.2V2a1.7 1.7 0 0 1 3.4 0v.2a1.7 1.7 0 0 0 2.9 1.2l.1-.1a1.7 1.7 0 0 1 2.4 2.4l-.1.1a1.7 1.7 0 0 0 1.2 2.9h.2a1.7 1.7 0 0 1 0 3.4h-.2a1.7 1.7 0 0 0-1.2 2.9Z" transform="scale(.65) translate(6.5 6.5)"/>',
      location: '<path d="M20 10.5c0 5.2-8 10.2-8 10.2s-8-5-8-10.2a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10.5" r="2.5"/>',
      'chevron-down': '<path d="m6 9 6 6 6-6"/>',
      'chevron-left': '<path d="m14 6-6 6 6 6"/>',
      'arrow-left': '<path d="M5 12h14M13 6l6 6-6 6"/>',
      download: '<path d="M12 3v12M7 11l5 5 5-5M4 20h16"/>',
      search: '<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/>',
      sliders: '<path d="M4 6h7M15 6h5M4 12h3M11 12h9M4 18h9M17 18h3"/><circle cx="13" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="15" cy="18" r="2"/>',
      wrench: '<path d="M14.5 6.2a4.3 4.3 0 0 0-5.4 5.4L4 16.7a1.7 1.7 0 0 0 2.4 2.4l5.1-5.1a4.3 4.3 0 0 0 5.4-5.4l-2.8 2.8-2.8-2.8 3.2-2.4Z"/>',
      truck: '<path d="M3 6h11v10H3zM14 10h4l3 3v3h-7z"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
      bolt: '<path d="m13 2-9 12h7l-1 8 9-12h-7l1-8Z"/>',
      check: '<path d="m5 12 4.2 4.2L19 6.5"/>',
      shield: '<path d="M12 21s8-3.5 8-10V5l-8-3-8 3v6c0 6.5 8 10 8 10Z"/><path d="m8.5 12 2.3 2.3 4.7-5"/>',
      bell: '<path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/>',
      plus: '<path d="M12 5v14M5 12h14"/>',
      x: '<path d="m6 6 12 12M18 6 6 18"/>',
      headphones: '<path d="M4 14v-2a8 8 0 0 1 16 0v2"/><path d="M4 14h3v5H5a1 1 0 0 1-1-1v-4ZM20 14h-3v5h2a1 1 0 0 0 1-1v-4ZM12 20h3"/>',
      more: '<circle cx="5" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none"/>',
      star: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z"/>',
      paint: '<path d="M4 4h12v7H4zM8 11v9M8 20h4M16 7h2a2 2 0 0 1 2 2v5"/>',
      car: '<path d="m5 16 1.5-6h11L19 16M3 16h18v4H3zM7 20v2M17 20v2M7.5 13h.01M16.5 13h.01"/>',
      leaf: '<path d="M20 4C10 4 5 8 5 15c0 3 2 5 5 5 7 0 10-6 10-16Z"/><path d="M4 21c3-6 7-9 13-12"/>',
      gift: '<rect x="3" y="9" width="18" height="12" rx="1"/><path d="M12 9v12M3 13h18M12 9H8.5a2.5 2.5 0 1 1 2.5-2.5V9ZM12 9h3.5A2.5 2.5 0 1 0 13 6.5V9Z"/>',
      'credit-card': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M7 15h3"/>',
      zap: '<path d="m13 2-9 12h7l-1 8 9-12h-7l1-8Z"/>',
      hand: '<path d="M8 11V5a1.5 1.5 0 0 1 3 0v5-7a1.5 1.5 0 0 1 3 0v7-5a1.5 1.5 0 0 1 3 0v6l1-1a1.6 1.6 0 0 1 2.2 2.3l-3.8 5.1A5 5 0 0 1 12.4 20H10c-2 0-3-1-4.2-2.5L3.5 14a1.6 1.6 0 0 1 2.5-2L8 14V11Z"/>',
      user: '<circle cx="12" cy="8" r="3.5"/><path d="M4.5 21a7.5 7.5 0 0 1 15 0"/>',
      lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
    };

    function icon(name) {
      return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (iconPaths[name] || '') + '</svg>';
    }
    document.querySelectorAll('[data-icon]').forEach(el => { el.innerHTML = icon(el.dataset.icon); });

    const $ = (selector, scope = document) => scope.querySelector(selector);
    const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
    const bookingPrices = { 'صيانة منزلية': '١٥', 'تنظيف وتعقيم': '١٢', 'نقل وشحن': '٢٥', 'كهرباء وسباكة': '١٨', 'دهان وترميم': '٣٥', 'صيانة سيارات': '٢٠', 'حدائق ومسابح': '١٥', 'خدمات المناسبات': '٣٠' };
    let currentService = 'صيانة منزلية';
    let introStep = 0;
    let toastTimer;
    let adminCsrfToken = '';

    function showToast(message) {
      $('#toastText').textContent = message;
      $('#toast').classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 2800);
    }

    function switchView(view) {
      $$('.view').forEach(section => section.classList.toggle('active', section.dataset.page === view));
      $$('[data-view]').forEach(button => button.classList.toggle('active', button.dataset.view === view));
      $('#notificationPanel').classList.remove('open');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    $$('[data-view]').forEach(button => {
      button.addEventListener('click', event => {
        event.preventDefault();
        switchView(button.dataset.view);
      });
    });

    function openOverlay(id) {
      const overlay = $('#' + id);
      if (!overlay) return;
      overlay.classList.add('open');
      document.body.classList.add('modal-open');
    }
    function closeOverlay(id) {
      const overlay = $('#' + id);
      if (!overlay) return;
      overlay.classList.remove('open');
      if (!$('.overlay.open')) document.body.classList.remove('modal-open');
    }
    $$('[data-close]').forEach(button => button.addEventListener('click', () => closeOverlay(button.dataset.close)));
    $$('.overlay').forEach(overlay => overlay.addEventListener('click', event => { if (event.target === overlay) closeOverlay(overlay.id); }));
    document.addEventListener('keydown', event => { if (event.key === 'Escape') $$('.overlay.open').forEach(overlay => closeOverlay(overlay.id)); });

    function serviceVisual(service) {
      if (service.includes('تنظيف')) return { cls: 'amber', name: 'sparkles' };
      if (service.includes('نقل')) return { cls: 'purple', name: 'truck' };
      if (service.includes('كهرباء')) return { cls: 'blue', name: 'bolt' };
      if (service.includes('دهان')) return { cls: 'green', name: 'paint' };
      if (service.includes('سيارات')) return { cls: 'amber', name: 'car' };
      if (service.includes('حدائق')) return { cls: 'purple', name: 'leaf' };
      if (service.includes('مناسبات')) return { cls: 'blue', name: 'gift' };
      return { cls: 'green', name: 'wrench' };
    }

    function openBooking(service = 'صيانة منزلية') {
      currentService = service;
      const visual = serviceVisual(service);
      $('#bookingServiceName').textContent = service;
      $('#bookingIcon').className = 'service-icon ' + visual.cls;
      $('#bookingIcon').innerHTML = '<span class="icon" data-icon="' + visual.name + '">' + icon(visual.name) + '</span>';
      $('#bookingPrice').innerHTML = (bookingPrices[service] || '١٥') + ' <small>د.أ</small>';
      $('#bookingFormView').classList.remove('hide');
      $('#confirmView').classList.remove('show');
      openOverlay('bookingModal');
    }
    $$('[data-book]').forEach(button => button.addEventListener('click', () => openBooking(button.dataset.book)));
    $$('[data-service-card]').forEach(card => card.addEventListener('click', () => openBooking(card.dataset.service)));
    $('#changeService').addEventListener('click', () => { closeOverlay('bookingModal'); switchView('services'); showToast('اختاري الخدمة المناسبة لطلبك'); });

    function getSelectedTime() {
      const selected = $('.date-option.selected');
      return selected ? selected.innerText.replace(/\n/g, '، ') : 'اليوم، من ٥ - ٧ م';
    }
    $$('.date-option').forEach(option => option.addEventListener('click', () => {
      $$('.date-option').forEach(item => item.classList.remove('selected'));
      option.classList.add('selected');
    }));
    $('#continueBooking').addEventListener('click', () => {
      $('#confirmService').textContent = currentService;
      $('#confirmLocation').textContent = $('#bookingLocation').value || 'الدوار السابع، عمّان';
      $('#confirmTime').textContent = getSelectedTime();
      $('#confirmPrice').textContent = (bookingPrices[currentService] || '١٥') + ' د.أ';
      $('#bookingFormView').classList.add('hide');
      $('#confirmView').classList.add('show');
    });
    $('#backToBooking').addEventListener('click', () => { $('#confirmView').classList.remove('show'); $('#bookingFormView').classList.remove('hide'); });
    $('#confirmBooking').addEventListener('click', () => {
      closeOverlay('bookingModal');
      $('#successOrderId').textContent = '#SN-' + (2850 + Math.floor(Math.random() * 50));
      openOverlay('successModal');
      $('#ordersBadge').textContent = '3';
      $('#orderStatus').textContent = 'تم الإرسال';
      $('#orderStatus').classList.add('pending');
      $('#orderTitle').textContent = currentService;
      $('#orderMeta').textContent = 'تم الإرسال للتنسيق الآن';
    });
    $('#trackSuccess').addEventListener('click', () => { closeOverlay('successModal'); switchView('orders'); showToast('طلبك جاهز للمتابعة من هنا'); });
    $('#homeSuccess').addEventListener('click', () => { closeOverlay('successModal'); switchView('home'); });

    // Search the home service cards.
    function filterCards(input, cards, empty) {
      const term = input.value.trim().toLowerCase();
      let visible = 0;
      cards.forEach(card => {
        const haystack = (card.dataset.search || card.dataset.service || '').toLowerCase();
        const match = !term || haystack.includes(term);
        card.style.display = match ? '' : 'none';
        if (match) visible++;
      });
      if (empty) empty.style.display = visible ? 'none' : 'block';
    }
    const homeSearch = $('#serviceSearch');
    homeSearch.addEventListener('input', () => filterCards(homeSearch, $$('[data-service-card]', $('#homeServices')), $('#homeNoResults')));
    $('.service-page-search').addEventListener('input', event => filterCards(event.target, $$('.all-services-grid [data-service-card]')));
    document.addEventListener('keydown', event => { if (event.key === '/' && document.activeElement.tagName !== 'INPUT') { event.preventDefault(); homeSearch.focus(); } });

    // Intro carousel based on the requested onboarding copy.
    const introSlides = [
      { title: 'كل خدماتك بضغطة زر', text: 'ابحثي عن أفضل الفنيين ومزودي الخدمات في منطقتك بكل سهولة — من عمّان لإربد والزرقاء.', icon: 'sparkles' },
      { title: 'جودة نضمنها لك', text: 'نختار شركاءنا بعناية ونتحقق منهم، عشان توصلك خدمة احترافية وآمنة كل مرة.', icon: 'shield' },
      { title: 'أسعار واضحة ودفع آمن', text: 'اعرفي التكلفة مسبقاً وادفعي بالطريقة اللي تناسبك: CliQ، بطاقة، أو عند الإنجاز.', icon: 'wallet' }
    ];
    function renderIntro() {
      const slide = introSlides[introStep];
      $('#introTitle').textContent = slide.title;
      $('#introText').textContent = slide.text;
      $('#introIcon').innerHTML = '<span class="icon" data-icon="' + slide.icon + '">' + icon(slide.icon) + '</span>';
      $$('.intro-progress span').forEach((dot, i) => dot.classList.toggle('active', i === introStep));
      $('#introNext').innerHTML = (introStep === introSlides.length - 1 ? 'ابدئي الآن' : 'التالي') + ' <span class="icon" data-icon="arrow-left">' + icon('arrow-left') + '</span>';
    }
    function openIntro() { introStep = 0; renderIntro(); openOverlay('introModal'); }
    $('#introNext').addEventListener('click', () => { if (introStep < introSlides.length - 1) { introStep++; renderIntro(); } else { closeOverlay('introModal'); openBooking('تنظيف وتعقيم'); } });

    function openSecurityCenter() { openOverlay('securityModal'); }
    function openAdminAuth() { openOverlay('adminAuthModal'); setTimeout(() => $('#adminUsername').focus(), 120); }
    async function loginAdmin() {
      const error = $('#adminAuthError');
      error.hidden = true;
      const payload = {
        username: $('#adminUsername').value.trim(),
        password: $('#adminPassword').value,
        mfa_code: $('#adminMfaCode').value.trim()
      };
      try {
        const response = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'login_failed');
        adminCsrfToken = result.csrf_token || '';
        closeOverlay('adminAuthModal');
        switchView('admin');
        showToast('تم تسجيل الدخول الإداري مع MFA');
      } catch (errorValue) {
        error.hidden = false;
        $('#adminMfaCode').value = '';
      }
    }
    async function inspectAuditLog() {
      try {
        const response = await fetch('/api/admin/audit', { credentials: 'same-origin' });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'audit_failed');
        showToast('تمت قراءة ' + result.events.length + ' أحداث من سجل التدقيق');
      } catch (errorValue) {
        showToast('سجل التدقيق يتطلب جلسة مدير مصادقاً عليها');
      }
    }
    function exportAdminReport() {
      const rows = [
        ['الطلب', 'الخدمة', 'المنطقة', 'القيمة', 'الحالة'],
        ['#SN-2841', 'صيانة تكييف', 'عمّان - الدوار السابع', '18 د.أ', 'قيد التنفيذ'],
        ['#SN-2840', 'تنظيف منزل', 'إربد - الحي الشرقي', '22 د.أ', 'تم التعيين'],
        ['#SN-2839', 'نقل أثاث', 'الزرقاء - الجديدة', '45 د.أ', 'بانتظار مزود']
      ];
      const csv = '\ufeff' + rows.map(row => row.map(value => '"' + value.replaceAll('"', '""') + '"').join(',')).join('\n');
      const link = document.createElement('a');
      link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
      link.download = 'ezwatek-operations-report.csv';
      link.click();
      URL.revokeObjectURL(link.href);
      showToast('تم تجهيز تقرير العمليات للتنزيل');
    }
    function removeApprovalRow(button, message) {
      const row = button.closest('[data-approval-row]');
      if (!row) return;
      row.animate([{ opacity: 1, transform: 'translateX(0)' }, { opacity: 0, transform: 'translateX(12px)' }], { duration: 180, fill: 'forwards' });
      setTimeout(() => row.remove(), 180);
      const count = $('#approvalCount');
      const remaining = Math.max(0, Number(count.dataset.count || '0') - 1);
      count.dataset.count = String(remaining);
      count.textContent = new Intl.NumberFormat('ar', { useGrouping: false }).format(remaining);
      showToast(message);
    }
    $$('[data-action]').forEach(button => button.addEventListener('click', () => {
      const action = button.dataset.action;
      if (action === 'intro') openIntro();
      if (action === 'help') showToast('فريق عزوتك جاهز يساعدك — ٠٦ ٥٥٥ ١٢٣٤');
      if (action === 'track') { switchView('orders'); showToast('تم فتح تفاصيل الطلب'); }
      if (action === 'rate') showToast('شكراً! نافذة التقييم جاهزة لك ⭐');
      if (action === 'favorite') { button.classList.toggle('selected'); showToast(button.classList.contains('selected') ? 'تمت الإضافة للمفضلة' : 'تمت الإزالة من المفضلة'); }
      if (action === 'payment') showToast('ميزة إضافة طريقة دفع قادمة قريباً');
      if (action === 'filter') showToast('خيارات التصفية ستظهر هنا');
      if (action === 'security') openSecurityCenter();
      if (action === 'admin-login') openAdminAuth();
      if (action === 'export') exportAdminReport();
      if (action === 'audit') inspectAuditLog();
      if (action === 'approve') removeApprovalRow(button, 'تم اعتماد مزود الخدمة بعد مراجعة المستندات');
      if (action === 'reject') removeApprovalRow(button, 'تم إرسال الطلب للمراجعة والرفض الآمن');
    }));

    $$('[data-chart-tab]').forEach(tab => tab.addEventListener('click', () => {
      $$('[data-chart-tab]').forEach(item => item.classList.remove('active'));
      tab.classList.add('active');
      const values = { '7': ['٢٤,٦٨٠ د.أ', '↑ ١٢.٤٪ عن الأسبوع الماضي'], '30': ['٩٢,٤٠٠ د.أ', '↑ ١٨.١٪ عن الشهر الماضي'], '90': ['٢٨١,٣٠٠ د.أ', '↑ ٢٣.٧٪ عن الربع الماضي'] };
      $('#adminRevenue').textContent = values[tab.dataset.chartTab][0];
      $('#adminRevenueTrend').textContent = values[tab.dataset.chartTab][1];
    }));
    $$('.ops-filter button').forEach(filter => filter.addEventListener('click', () => {
      $$('.ops-filter button').forEach(item => item.classList.remove('active'));
      filter.classList.add('active');
      const selected = filter.dataset.opsFilter;
      $$('.operations-table tbody tr').forEach(row => { row.hidden = selected === 'pending' ? !row.innerText.includes('بانتظار') : selected === 'active' ? !row.innerText.includes('التنفيذ') && !row.innerText.includes('التعيين') && !row.innerText.includes('وصل') : false; });
    }));
    const adminLoginButton = $('#adminLoginButton');
    if (adminLoginButton) adminLoginButton.addEventListener('click', loginAdmin);
    const reviewSessionsButton = $('#reviewSessions');
    if (reviewSessionsButton) reviewSessionsButton.addEventListener('click', () => { closeOverlay('securityModal'); showToast('تم فتح مراجعة الجلسات الإدارية الآمنة'); });
    const rotateKeysButton = $('#rotateKeys');
    if (rotateKeysButton) rotateKeysButton.addEventListener('click', () => { closeOverlay('securityModal'); showToast('تم إنشاء طلب موافقة لتدوير المفاتيح'); });

    function openAuth() { openOverlay('authModal'); setTimeout(() => $('#phoneInput').focus(), 120); }
    $('#profileButton').addEventListener('click', openAuth);
    $('#profileButton').addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openAuth(); } });
    $('#authContinue').addEventListener('click', () => {
      const phone = $('#phoneInput').value.replace(/[^0-9]/g, '');
      const validJordanPhone = /^7[0-9]{8}$/.test(phone) || /^07[0-9]{8}$/.test(phone);
      $('#phoneError').hidden = validJordanPhone;
      $('#phoneField').classList.toggle('invalid', !validJordanPhone);
      if (!validJordanPhone) { $('#phoneInput').focus(); return; }
      closeOverlay('authModal');
      showToast('أهلاً فيك مع عزوتك — تم تجهيز حسابك');
    });
    $('#phoneInput').addEventListener('input', () => { $('#phoneError').hidden = true; $('#phoneField').classList.remove('invalid'); });
    $('#guestExplore').addEventListener('click', () => { closeOverlay('authModal'); openIntro(); });

    $('#notificationButton').addEventListener('click', event => { event.stopPropagation(); const panel = $('#notificationPanel'); panel.classList.toggle('open'); $('#notificationButton').setAttribute('aria-expanded', panel.classList.contains('open')); });
    $('#markRead').addEventListener('click', () => { $$('.notification-item').forEach(item => item.classList.remove('unread')); $('.notification-dot').style.display = 'none'; showToast('تم تحديد الإشعارات كمقروءة'); });
    document.addEventListener('click', event => { if (!event.target.closest('#notificationPanel') && !event.target.closest('#notificationButton')) $('#notificationPanel').classList.remove('open'); });
    $('#locationButton').addEventListener('click', () => showToast('الموقع الحالي: عمّان، الأردن'));
    $$('.filter-pill').forEach(pill => pill.addEventListener('click', () => { $$('.filter-pill').forEach(item => item.classList.remove('active')); pill.classList.add('active'); }));
    $$('.toggle').forEach(toggle => toggle.addEventListener('click', () => { toggle.classList.toggle('on'); showToast(toggle.classList.contains('on') ? 'تم تفعيل التنبيهات' : 'تم إيقاف التنبيهات'); }));
  </script>
</body>
</html>'''


PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_ASSETS = {
    '/manifest.webmanifest': (PROJECT_ROOT / 'manifest.webmanifest', 'application/manifest+json; charset=utf-8'),
    '/favicon.svg': (PROJECT_ROOT / 'favicon.svg', 'image/svg+xml; charset=utf-8'),
    '/robots.txt': (PROJECT_ROOT / 'robots.txt', 'text/plain; charset=utf-8'),
}


APP_VERSION = '0.6.0'
MAX_PATH_LENGTH = 2048
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 180
ADMIN_UI_START = '<!-- ADMIN_UI_START -->'
ADMIN_UI_END = '<!-- ADMIN_UI_END -->'
_rate_buckets = defaultdict(deque)
_rate_lock = threading.Lock()
API_BODY_LIMIT = 16 * 1024
IAM = IAMService()


def remove_marked_blocks(document, start_marker, end_marker):
    """Remove all complete, server-controlled marker blocks without regex parsing."""
    while start_marker in document:
        start_index = document.find(start_marker)
        end_index = document.find(end_marker, start_index + len(start_marker))
        if end_index == -1:
            break
        document = document[:start_index] + document[end_index + len(end_marker):]
    return document


class AppHandler(BaseHTTPRequestHandler):
    """Small, dependency-free static app server with secure-by-default response handling.

    Production traffic should still sit behind a managed TLS terminator, WAF and identity
    provider. Only the explicitly scoped authentication endpoints below can change state.
    """

    server_version = 'Ezwatek'
    sys_version = ''

    def _client_ip(self):
        # Do not trust a user-controlled X-Forwarded-For header by default.
        return self.client_address[0] if self.client_address else 'unknown'

    def _rate_allowed(self):
        now = time.monotonic()
        ip = self._client_ip()
        with _rate_lock:
            bucket = _rate_buckets[ip]
            cutoff = now - RATE_LIMIT_WINDOW
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            allowed = len(bucket) < RATE_LIMIT_MAX_REQUESTS
            if allowed:
                bucket.append(now)
            # Bound memory if a public listener sees many source addresses.
            if len(_rate_buckets) > 5000:
                stale = [key for key, values in _rate_buckets.items() if not values or values[-1] <= cutoff]
                for key in stale[:1000]:
                    _rate_buckets.pop(key, None)
            return allowed

    def _request_path(self):
        raw_path = self.path or ''
        lowered_path = raw_path.lower()
        suspicious_tokens = ('%00', '%2e%2e', '..%2f', '../', '<script', '${', '\\x00')
        if len(raw_path) > MAX_PATH_LENGTH or any(ord(char) < 32 for char in raw_path) or any(token in lowered_path for token in suspicious_tokens):
            return None
        try:
            parsed = urlsplit(raw_path)
        except ValueError:
            return None
        if not parsed.path or len(parsed.path) > MAX_PATH_LENGTH:
            return None
        return parsed.path

    def _security_headers(self, nonce):
        production = os.environ.get('APP_ENV', 'development').lower() == 'production'
        frame_ancestors = "'none'" if production else "'self' https://*.e2b.app http://localhost:* http://127.0.0.1:*"
        headers = {
            'Content-Security-Policy': (
                "default-src 'none'; base-uri 'none'; form-action 'self'; "
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "img-src 'self' data:; font-src 'self'; connect-src 'self'; manifest-src 'self'; "
                "object-src 'none'; worker-src 'none'; frame-ancestors " + frame_ancestors + "; "
                "block-all-mixed-content"
            ),
            'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer',
            'Permissions-Policy': 'camera=(), geolocation=(), microphone=(), payment=(), usb=()',
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Resource-Policy': 'same-origin',
            'X-DNS-Prefetch-Control': 'off',
            'X-Permitted-Cross-Domain-Policies': 'none',
            'Cache-Control': 'no-store, max-age=0',
            'Pragma': 'no-cache',
            'X-Request-ID': secrets.token_hex(12),
        }
        if production:
            headers['X-Frame-Options'] = 'DENY'
            if os.environ.get('ENABLE_HSTS', '1') == '1' or self.headers.get('X-Forwarded-Proto', '').lower() == 'https':
                headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return headers

    def _send_payload(self, body, content_type, status=200, include_body=True, extra_headers=None, nonce=None):
        nonce = nonce or secrets.token_urlsafe(18)
        headers = self._security_headers(nonce)
        headers.update(extra_headers or {})
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        for key, value in headers.items():
            if key.lower() == 'set-cookie' and isinstance(value, (tuple, list)):
                for cookie in value:
                    self.send_header(key, cookie)
            else:
                self.send_header(key, value)
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def _send_json(self, payload, status=200, include_body=True, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self._send_payload(body, 'application/json; charset=utf-8', status, include_body, extra_headers)

    @staticmethod
    def _admin_ui_enabled():
        production = os.environ.get('APP_ENV', 'development').lower() == 'production'
        return not production or os.environ.get('ADMIN_UI_ENABLED', '0') == '1'

    def _is_secure_request(self):
        production = os.environ.get('APP_ENV', 'development').lower() == 'production'
        forwarded_proto = self.headers.get('X-Forwarded-Proto', '').lower()
        return production or forwarded_proto == 'https'

    def _read_json_body(self):
        content_type = self.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
        if content_type != 'application/json':
            self._send_json({'error': 'unsupported_media_type'}, 415, True)
            return None
        try:
            content_length = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            content_length = -1
        if content_length < 0:
            self._send_json({'error': 'length_required'}, 411, True)
            return None
        if content_length > API_BODY_LIMIT:
            self._send_json({'error': 'payload_too_large'}, 413, True)
            return None
        raw_body = self.rfile.read(content_length)
        if len(raw_body) != content_length:
            self._send_json({'error': 'bad_request'}, 400, True)
            return None
        try:
            body = json.loads(raw_body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({'error': 'invalid_json'}, 400, True)
            return None
        if not isinstance(body, dict):
            self._send_json({'error': 'invalid_json'}, 400, True)
            return None
        return body

    def _current_session(self):
        return IAM.session_from_cookie(self.headers.get('Cookie'))

    def _send_unauthorized(self, include_body=True):
        self._send_json({'error': 'authentication_required'}, 401, include_body, {'Cache-Control': 'no-store'})

    def _send_forbidden(self, include_body=True):
        self._send_json({'error': 'insufficient_permissions'}, 403, include_body, {'Cache-Control': 'no-store'})

    def _serve_api(self, path, method, include_body=True):
        if path == '/api/auth/status' and method in {'GET', 'HEAD'}:
            session = self._current_session()
            payload = {'authenticated': bool(session)}
            if session:
                payload.update({
                    'user': session.identity.username,
                    'roles': list(session.identity.roles),
                    'permissions': sorted(session.identity.permissions),
                    'csrf_token': session.csrf_token,
                    'expires_at': int(session.expires_at),
                })
            self._send_json(payload, 200, include_body, {'Vary': 'Cookie', 'Cache-Control': 'no-store'})
            return

        if path == '/api/auth/login' and method == 'POST':
            body = self._read_json_body()
            if body is None:
                return
            username = body.get('username', '')
            password = body.get('password', '')
            mfa_code = body.get('mfa_code', '')
            if not isinstance(username, str) or not isinstance(password, str) or not isinstance(mfa_code, str):
                self._send_json({'error': 'invalid_credentials'}, 401, True, {'Cache-Control': 'no-store'})
                return
            session, reason = IAM.login(username, password, mfa_code, self._client_ip())
            if reason == 'rate_limited':
                self._send_json({'error': 'too_many_login_attempts'}, 429, True, {'Retry-After': '300', 'Cache-Control': 'no-store'})
                return
            if not session:
                self._send_json({'error': 'invalid_credentials'}, 401, True, {'Cache-Control': 'no-store'})
                return
            payload = {
                'authenticated': True,
                'user': session.identity.username,
                'roles': list(session.identity.roles),
                'permissions': sorted(session.identity.permissions),
                'csrf_token': session.csrf_token,
                'expires_at': int(session.expires_at),
            }
            self._send_json(payload, 200, include_body, {'Set-Cookie': IAM.session_cookie(session, self._is_secure_request()), 'Cache-Control': 'no-store'})
            return

        if path == '/api/auth/logout' and method == 'POST':
            session = self._current_session()
            if not session:
                self._send_unauthorized()
                return
            if not IAM.csrf_valid(session, self.headers.get('X-CSRF-Token')):
                IAM.audit_log.record('auth.logout.csrf_failed', actor=session.identity.username, success=False, client_ip=self._client_ip())
                self._send_forbidden()
                return
            IAM.sessions.revoke(session.token)
            IAM.audit_log.record('auth.logout', actor=session.identity.username, success=True, client_ip=self._client_ip())
            headers = {'Set-Cookie': IAM.clear_cookies(self._is_secure_request()), 'Cache-Control': 'no-store'}
            self._send_json({'authenticated': False}, 200, include_body, headers)
            return

        if path in {'/api/admin/overview', '/api/admin/security', '/api/admin/audit'} and method in {'GET', 'HEAD'}:
            session = self._current_session()
            if path.endswith('/security'):
                required_permission = 'security:read'
            elif path.endswith('/audit'):
                required_permission = 'audit:read'
            else:
                required_permission = 'admin:read'
            if not session:
                IAM.audit_log.record('admin.access.unauthenticated', success=False, client_ip=self._client_ip(), details={'resource': path})
                self._send_unauthorized(include_body)
                return
            if not can(session.identity, required_permission):
                IAM.audit_log.record('admin.access.denied', actor=session.identity.username, success=False, client_ip=self._client_ip(), details={'resource': path, 'permission': required_permission})
                self._send_forbidden(include_body)
                return
            IAM.audit_log.record('admin.access.granted', actor=session.identity.username, success=True, client_ip=self._client_ip(), details={'resource': path})
            if path.endswith('/security'):
                payload = {
                    'risk_score': 96,
                    'mfa_coverage': 98.4,
                    'blocked_attempts': 27,
                    'critical_vulnerabilities': 0,
                    'backup_age_minutes': 12,
                }
            elif path.endswith('/audit'):
                payload = {'events': IAM.audit_log.recent()}
            else:
                payload = {
                    'orders_today': 1284,
                    'service_volume_jod': 24680,
                    'active_providers': 318,
                    'customer_satisfaction': 4.9,
                }
            self._send_json(payload, 200, include_body, {'Cache-Control': 'no-store', 'Vary': 'Cookie'})
            return

        self._send_json({'error': 'not_found'}, 404, include_body)

    def _serve(self, include_body=True, method='GET'):
        if not self._rate_allowed():
            self._send_json({'error': 'too_many_requests', 'message': 'تم تجاوز عدد الطلبات المسموح مؤقتاً.'}, 429, include_body, {'Retry-After': str(RATE_LIMIT_WINDOW)})
            return
        path = self._request_path()
        if path is None:
            self._send_json({'error': 'bad_request', 'message': 'طلب غير صالح.'}, 400, include_body)
            return
        if path.startswith('/api/'):
            self._serve_api(path, method, include_body)
            return
        if path == '/health':
            self._send_json({'status': 'ok', 'app': 'ezwatek', 'version': APP_VERSION, 'security': 'headers-enabled'}, 200, include_body)
            return
        if path == '/ready':
            assets_ready = all(file_path.is_file() for file_path, _ in STATIC_ASSETS.values())
            status = 200 if assets_ready else 503
            self._send_json({'status': 'ready' if assets_ready else 'not_ready', 'app': 'ezwatek', 'version': APP_VERSION}, status, include_body)
            return
        asset = STATIC_ASSETS.get(path)
        if asset:
            file_path, content_type = asset
            try:
                body = file_path.read_bytes()
            except OSError:
                self._send_json({'error': 'asset_unavailable'}, 503, include_body)
                return
            self._send_payload(body, content_type, 200, include_body)
            return
        if path != '/':
            self._send_json({'error': 'not_found'}, 404, include_body)
            return
        nonce = secrets.token_urlsafe(18)
        rendered = HTML.replace('__CSP_NONCE__', nonce)
        if not self._admin_ui_enabled():
            rendered = remove_marked_blocks(rendered, ADMIN_UI_START, ADMIN_UI_END)
        self._send_payload(rendered.encode('utf-8'), 'text/html; charset=utf-8', 200, include_body, nonce=nonce)

    def do_GET(self):
        self._serve(include_body=True, method='GET')

    def do_HEAD(self):
        self._serve(include_body=False, method='HEAD')

    def _reject_state_change(self):
        if not self._rate_allowed():
            self._send_json({'error': 'too_many_requests'}, 429, True, {'Retry-After': str(RATE_LIMIT_WINDOW)})
            return
        self._send_json({'error': 'method_not_allowed'}, 405, True, {'Allow': 'GET, HEAD, OPTIONS'})

    def do_POST(self):
        path = self._request_path()
        if path in {'/api/auth/login', '/api/auth/logout'}:
            self._serve(include_body=True, method='POST')
            return
        self._reject_state_change()

    def do_PUT(self):
        self._reject_state_change()

    def do_DELETE(self):
        self._reject_state_change()

    def do_OPTIONS(self):
        self._send_payload(b'', 'text/plain; charset=utf-8', 204, False, {'Allow': 'GET, HEAD, POST, OPTIONS'})

    def log_message(self, format, *args):
        # Keep logs useful without echoing query strings or user-controlled values.
        status = args[1] if len(args) > 1 else '-'
        path = self._request_path()
        safe_path = path if path in {'/', '/health'} else '<other>'
        print(f"{self._client_ip()} {status} {safe_path}")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    server = ThreadingHTTPServer(('0.0.0.0', port), AppHandler)
    print(f'عزوتك is running on http://0.0.0.0:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
