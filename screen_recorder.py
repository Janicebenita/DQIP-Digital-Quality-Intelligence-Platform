"""Playwright-driven, narration-aware recording of the live Streamlit UI."""

from __future__ import annotations

from pathlib import Path
import shutil
import time

from scene_manager import Scene


class RecordingError(RuntimeError):
    pass


def _inject_storytelling_ui(page) -> None:
    page.evaluate(
        """
        () => {
          if (document.getElementById('dqip-story-style')) return;
          const style = document.createElement('style');
          style.id = 'dqip-story-style';
          style.textContent = `
            #dqip-story-title { position:fixed; left:34px; bottom:34px; z-index:999999;
              padding:15px 22px; border-radius:13px; color:#fff; font:700 23px/1.2 Arial;
              background:linear-gradient(120deg,rgba(4,30,52,.96),rgba(10,100,145,.94));
              border:1px solid rgba(92,211,255,.55); box-shadow:0 14px 44px rgba(0,0,0,.28);
              opacity:0; transform:translateY(18px); transition:.45s ease; max-width:760px; }
            #dqip-story-title.show { opacity:1; transform:translateY(0); }
            #dqip-story-title small { display:block; margin-top:5px; color:#a8def4; font:500 14px Arial; }
            #dqip-cursor { position:fixed; z-index:999998; width:42px; height:42px; border-radius:50%;
              border:3px solid rgba(255,193,7,.95); box-shadow:0 0 0 9px rgba(255,193,7,.18);
              pointer-events:none; opacity:0; transition:left .25s ease,top .25s ease,opacity .2s; }
            .dqip-highlight { outline:4px solid rgba(255,181,34,.92)!important;
              box-shadow:0 0 0 9px rgba(255,181,34,.18)!important; transition:.3s ease!important; }
          `;
          document.head.appendChild(style);
          const title = document.createElement('div'); title.id='dqip-story-title'; document.body.appendChild(title);
          const cursor = document.createElement('div'); cursor.id='dqip-cursor'; document.body.appendChild(cursor);
        }
        """
    )


def _title(page, scene: Scene, detail: str = "AI-powered engineering quality intelligence") -> None:
    page.evaluate(
        """([title, detail]) => {
          const box=document.getElementById('dqip-story-title');
          box.innerHTML=title + '<small>' + detail + '</small>';
          box.classList.add('show');
          setTimeout(()=>box.classList.remove('show'), 5200);
        }""",
        [scene.title, detail],
    )


def _spotlight(page, locator, dwell: float = 1.1, click: bool = False) -> float:
    try:
        locator.scroll_into_view_if_needed(timeout=3000)
        box = locator.bounding_box(timeout=3000)
        if not box:
            return 0.0
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.evaluate("([x,y])=>{const c=document.getElementById('dqip-cursor');c.style.left=(x-21)+'px';c.style.top=(y-21)+'px';c.style.opacity='1'}", [x,y])
        page.mouse.move(x, y, steps=18)
        locator.evaluate("el=>el.classList.add('dqip-highlight')")
        page.wait_for_timeout(int(dwell * 1000))
        if click:
            locator.click(timeout=3000)
            page.wait_for_timeout(700)
        locator.evaluate("el=>el.classList.remove('dqip-highlight')")
        return dwell + (0.7 if click else 0.0)
    except Exception:
        return 0.0


def _smooth_scroll(page, y: int, seconds: float = 2.0) -> float:
    page.evaluate("([y])=>window.scrollTo({top:y,behavior:'smooth'})", [y])
    page.wait_for_timeout(int(seconds * 1000))
    return seconds


def _text(page, text: str):
    return page.get_by_text(text, exact=False).first


def _sidebar_nav(page, label: str) -> float:
    try:
        option = page.locator("[data-testid='stSidebar']").get_by_text(label, exact=True).first
        return _spotlight(page, option, 0.45, True)
    except Exception:
        return 0.0


def _select_domain(page, name: str) -> float:
    try:
        selector = page.locator("[class*='st-key-domain_selector_shell'] label").filter(has_text=name).first
        spent = _spotlight(page, selector, 0.55, True)
        page.wait_for_timeout(2600)
        return spent + 2.6
    except Exception:
        return 0.0


def _domain_walkthrough(page, name: str, deep: bool = False) -> float:
    spent = _select_domain(page, name)
    spent += _smooth_scroll(page, 760, 1.4)
    for label in ("Records evaluated", "Observed Yield", "Risk Classification"):
        spent += _spotlight(page, _text(page, label), 0.45)
    spent += _smooth_scroll(page, 1460 if not deep else 2250, 1.7)
    charts = page.locator(".js-plotly-plot")
    if charts.count():
        spent += _spotlight(page, charts.first, 0.9)
    if deep:
        spent += _smooth_scroll(page, max(0, page.evaluate("()=>document.body.scrollHeight-1100")), 1.8)
        spent += _spotlight(page, _text(page, "Corrective"), 0.8)
    return spent


def _act(page, scene: Scene, sample_excel: Path) -> float:
    action, spent = scene.action, 0.0
    if action == "opening":
        spent += _smooth_scroll(page, 0, 1.2)
        spent += _spotlight(page, page.locator(".app-header").first, 1.6)
    elif action == "cross_domain":
        spent += _smooth_scroll(page, 200, 1.0)
        spent += _spotlight(page, page.locator("[class*='st-key-domain_selector_shell']").first, 2.0)
    elif action == "construction_profile":
        spent += _select_domain(page, "Construction Quality")
        spent += _smooth_scroll(page, 700, 1.5)
        spent += _spotlight(page, _text(page, "Upload cube strength workbook"), 1.0)
        spent += _spotlight(page, _text(page, "Evaluation complete"), 0.8)
    elif action == "construction_intelligence":
        spent += _smooth_scroll(page, 1200, 1.8)
        for label in ("Average Strength", "Sigma Level", "Ppk", "SQC Control Chart"):
            spent += _spotlight(page, _text(page, label), 0.55)
        spent += _smooth_scroll(page, 2450, 1.6)
    elif action == "manufacturing":
        spent += _domain_walkthrough(page, "Manufacturing")
    elif action == "manufacturing_actions":
        spent += _domain_walkthrough(page, "Manufacturing", True)
    elif action == "laboratory":
        spent += _domain_walkthrough(page, "Laboratory QA")
    elif action == "laboratory_actions":
        spent += _domain_walkthrough(page, "Laboratory QA", True)
    elif action == "healthcare":
        spent += _domain_walkthrough(page, "Healthcare", True)
    elif action == "pharmaceuticals":
        spent += _domain_walkthrough(page, "Pharmaceuticals", True)
    elif action == "environmental":
        spent += _domain_walkthrough(page, "Environmental Monitoring", True)
    elif action == "common_intelligence":
        spent += _select_domain(page, "Manufacturing")
        spent += _select_domain(page, "Laboratory QA")
        spent += _select_domain(page, "Environmental Monitoring")
    elif action == "validation":
        spent += _smooth_scroll(page, 260, 1.5)
        spent += _spotlight(page, _text(page, "Except for Concrete Quality data"), 2.0)
    elif action == "closing":
        spent += _smooth_scroll(page, 0, 2.2)
        spent += _spotlight(page, page.locator(".app-header").first, 1.5)
    elif action == "homepage":
        spent += _spotlight(page, _text(page, "DQIP cross-domain quality profiles"), 1.0)
        spent += _spotlight(page, page.locator("[data-testid='stSidebar']").first, 1.4)
    elif action == "upload":
        spent += _sidebar_nav(page, "Data Management")
        uploader = page.locator("input[type='file']").last
        try:
            uploader.set_input_files(str(sample_excel), timeout=5000)
            page.wait_for_timeout(3000); spent += 3
        except Exception:
            spent += _spotlight(page, _text(page, "Upload cube strength workbook"), 1.5)
    elif action == "preview":
        spent += _sidebar_nav(page, "Evaluation")
        spent += _smooth_scroll(page, max(0, page.evaluate("()=>document.body.scrollHeight-1500")), 2.0)
        spent += _spotlight(page, _text(page, "Data Preview"), 0.8, True)
        spent += _spotlight(page, page.locator("[data-testid='stDataFrame']").last, 1.4)
    elif action == "filters":
        spent += _sidebar_nav(page, "Evaluation")
        spent += _smooth_scroll(page, 900, 1.8)
        grade = page.get_by_text("M10", exact=True).last
        spent += _spotlight(page, grade, 1.0, True)
    elif action == "acceptance":
        spent += _sidebar_nav(page, "Compliance")
        target = _text(page, "Risk Intelligence Engine")
        spent += _spotlight(page, target, 1.3)
        spent += _spotlight(page, page.locator("[data-testid='stDataFrame']").first, 1.3)
    elif action == "statistics":
        spent += _sidebar_nav(page, "Evaluation")
        target = _text(page, "Concrete Statistics and Process Classification")
        spent += _spotlight(page, target, 1.2)
        spent += _spotlight(page, page.locator("[data-testid='stDataFrame']").last, 1.4)
    elif action == "six_sigma":
        spent += _sidebar_nav(page, "Capability")
        target = _text(page, "Six Sigma Process Capability")
        spent += _spotlight(page, target, 1.1)
        for plot in page.locator(".js-plotly-plot").all()[:2]:
            spent += _spotlight(page, plot, 0.7)
    elif action == "control_chart":
        spent += _sidebar_nav(page, "Risk Intelligence")
        target = _text(page, "SQC Control Chart")
        spent += _spotlight(page, target, 1.0)
        charts = page.locator(".js-plotly-plot")
        if charts.count():
            spent += _spotlight(page, charts.nth(min(4, charts.count()-1)), 1.5)
    elif action == "histogram":
        spent += _sidebar_nav(page, "Abnormality Detection")
        target = _text(page, "Detailed Analytics")
        spent += _spotlight(page, _text(page, "Histogram"), 0.8, True)
        if page.locator(".js-plotly-plot").count():
            spent += _spotlight(page, page.locator(".js-plotly-plot").last, 1.4)
    elif action == "dashboard":
        spent += _sidebar_nav(page, "Domain Dashboard")
        spent += _smooth_scroll(page, 1050, 2.0)
        for label in ("Average Strength", "Compliance Rate", "Sigma Level", "Ppk"):
            spent += _spotlight(page, _text(page, label), 0.55)
    elif action == "reports":
        spent += _sidebar_nav(page, "Reports")
        spent += _smooth_scroll(page, 900, 1.5)
        for label in ("Export", "Display Report"):
            spent += _spotlight(page, page.get_by_role("button", name=label, exact=False).first, 0.9, label == "Display Report")
    return spent


def record_application(url: str, scenes: list[Scene], sample_excel: Path, workdir: Path) -> tuple[Path, float]:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RecordingError("Playwright is not installed. Install the project requirements.") from exc

    video_dir = workdir / "playwright_video"
    video_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        except Exception as exc:
            raise RecordingError("Chromium is unavailable. Run: python -m playwright install chromium") from exc
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            record_video_dir=str(video_dir),
            record_video_size={"width": 1920, "height": 1080},
            accept_downloads=True,
        )
        page_created = time.monotonic()
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=120_000)
        page.wait_for_timeout(5000)
        _inject_storytelling_ui(page)
        recording_offset = time.monotonic() - page_created
        video = page.video
        for scene in scenes:
            scene_started = time.monotonic()
            _title(page, scene)
            _act(page, scene, sample_excel)
            remaining = scene.duration - (time.monotonic() - scene_started)
            if remaining > 0:
                page.wait_for_timeout(round(remaining * 1000))
        page.wait_for_timeout(2500)
        context.close()
        browser.close()
        source = Path(video.path())
    output = workdir / "screen_recording.webm"
    shutil.copy2(source, output)
    return output, recording_offset
