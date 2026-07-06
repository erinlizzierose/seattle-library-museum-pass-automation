from datetime import datetime, timedelta
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
from urllib.parse import parse_qs
import contextlib

from src.config import (
    load_config,
    load_desired_bookings,
    load_passes,
    save_desired_bookings,
    save_passes,
)
from src.main import compute_target_dates, run_once
from src.results import load_attempts


def _redirect(handler: BaseHTTPRequestHandler, path: str = "/") -> None:
    handler.send_response(303)
    handler.send_header("Location", path)
    handler.end_headers()


def _form_value(data: dict[str, list[str]], name: str) -> str:
    return data.get(name, [""])[0].strip()


def _read_form(handler: BaseHTTPRequestHandler) -> dict[str, list[str]]:
    length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(length).decode("utf-8")
    return parse_qs(body)


def _page(content: str, notice: str = "") -> bytes:
    notice_html = f"<p class='notice'>{escape(notice)}</p>" if notice else ""
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Library Ticket Booker</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #081f22;
      --panel: #0d2a2d;
      --panel-soft: #0f3033;
      --ink: #f4efe6;
      --muted: #98aaa7;
      --line: #29484b;
      --accent: #d8b77d;
      --accent-strong: #f0d39c;
      --danger: #e39b8b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background: var(--bg);
    }}
    header {{
      padding: 36px clamp(16px, 5vw, 56px) 18px;
      text-align: center;
    }}
    h1, h2 {{ margin: 0; letter-spacing: 0; }}
    h1 {{
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(34px, 6vw, 72px);
      font-weight: 500;
    }}
    h2 {{
      font-family: Georgia, "Times New Roman", serif;
      font-size: 24px;
      font-weight: 500;
    }}
    main {{
      display: grid;
      gap: 24px;
      grid-template-columns: minmax(0, 1fr);
      padding: 24px clamp(16px, 5vw, 56px) 56px;
      max-width: 1180px;
      margin: 0 auto;
    }}
    section {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 24px;
    }}
    .summary {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    }}
    .metric {{
      background: var(--panel-soft);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .metric span, .muted {{ color: var(--muted); font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 20px; }}
    form.inline {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: end;
      margin-top: 12px;
    }}
    label {{ display: grid; gap: 4px; color: var(--muted); font-size: 13px; }}
    input {{
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
      color: var(--ink);
      background: #0a2427;
    }}
    select {{
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
      color: var(--ink);
      background: #0a2427;
    }}
    button {{
      min-height: 38px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      padding: 8px 12px;
      background: var(--accent);
      color: #071a1d;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    button.secondary {{
      background: transparent;
      color: var(--accent);
    }}
    button.danger {{
      border-color: var(--danger);
      background: transparent;
      color: var(--danger);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{ color: var(--muted); font-weight: 600; }}
    .notice {{
      margin: 12px 0 0;
      color: var(--accent);
      font-weight: 600;
    }}
    .status-ok {{ color: var(--accent); font-weight: 700; }}
    .status-fail {{ color: var(--danger); font-weight: 700; }}
    @media (min-width: 880px) {{
      main {{ grid-template-columns: 1fr 1fr; }}
      section.full {{ grid-column: 1 / -1; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Library Ticket Booker</h1>
    <p class="muted">Pass priorities, release windows, and booking attempts.</p>
    {notice_html}
  </header>
  <main>{content}</main>
</body>
</html>"""
    return html.encode("utf-8")


def _render_home(notice: str = "") -> bytes:
    config = load_config()
    passes = load_passes()
    desired_bookings = load_desired_bookings()
    desired_dates = [str(item.get("date", "")) for item in desired_bookings if item.get("date")]
    target_dates = compute_target_dates(desired_dates, config.scheduler.days_ahead)
    next_release = datetime.now().date() + timedelta(days=config.scheduler.days_ahead)
    attempts = load_attempts(limit=12)

    pass_rows = "\n".join(
        f"""<tr>
  <td>{escape(item.get("provider", "kcls").upper())}</td>
  <td>{escape(item.get("name", ""))}</td>
  <td>{escape(item.get("category", ""))}</td>
  <td>{escape(item.get("url", ""))}</td>
  <td>
    <form method="post" action="/passes/delete">
      <input type="hidden" name="index" value="{index}">
      <button class="danger" type="submit">Remove</button>
    </form>
  </td>
</tr>"""
        for index, item in enumerate(passes)
    ) or "<tr><td colspan='5'>No passes configured yet.</td></tr>"

    pass_options = "\n".join(
        f"""<option value="{escape(item.get("name", ""))}" data-provider="{escape(item.get("provider", "kcls"))}">{escape(item.get("name", ""))}</option>"""
        for item in passes if item.get("provider", "kcls") == "kcls"
    )

    kcls_bookings = [item for item in desired_bookings if item.get("provider", "kcls") == "kcls"]
    spl_bookings = [item for item in desired_bookings if item.get("provider") == "spl"]

    def booking_rows(bookings: list[dict[str, object]]) -> str:
        return "\n".join(
            f"""<tr>
  <td>{escape(str(item.get("priority", "")))}</td>
  <td>{escape(item.get("date", ""))}</td>
  <td>{escape(item.get("pass_name", ""))}</td>
  <td>
    <form method="post" action="/desired-bookings/delete">
      <input type="hidden" name="index" value="{index}">
      <button class="danger" type="submit">Remove</button>
    </form>
  </td>
</tr>"""
            for index, item in enumerate(desired_bookings) if item in bookings
        ) or "<tr><td colspan='4'>No desired bookings yet.</td></tr>"

    attempt_rows = "\n".join(
        f"""<tr>
  <td>{escape(item.attempted_at)}</td>
  <td>{escape(item.pass_name)}</td>
  <td>{escape(item.target_date)}</td>
  <td class="{'status-ok' if item.success else 'status-fail'}">{'Success' if item.success else 'Failed'}</td>
  <td>{'Dry-run' if item.dry_run else 'Live'}</td>
  <td>{escape(item.message)}</td>
</tr>"""
        for item in attempts
    ) or "<tr><td colspan='6'>No attempts logged yet.</td></tr>"

    content = f"""
<section class="full">
  <div class="summary">
    <div class="metric"><span>Daily run time</span><strong>{escape(config.scheduler.run_time)}</strong></div>
    <div class="metric"><span>Booking window</span><strong>{config.scheduler.days_ahead} days ahead</strong></div>
    <div class="metric"><span>Next target date</span><strong>{next_release.isoformat()}</strong></div>
    <div class="metric"><span>Matching bookings</span><strong>{len(target_dates)}</strong></div>
  </div>
  <form class="inline" method="post" action="/run-dry">
    <button type="submit">Run Dry Booking</button>
  </form>
</section>

<section>
  <h2>KCLS Desired Bookings</h2>
  <form class="inline" method="post" action="/desired-bookings/add">
    <input type="hidden" name="provider" value="kcls">
    <label>Pass
      <select name="pass_name" required>
        {pass_options}
      </select>
    </label>
    <label>Date<input type="date" name="date" required></label>
    <label>Priority<input type="number" name="priority" value="1" min="1" required></label>
    <button type="submit">Add Booking</button>
  </form>
  <table>
    <thead><tr><th>Priority</th><th>Visit Date</th><th>Pass</th><th></th></tr></thead>
    <tbody>{booking_rows(kcls_bookings)}</tbody>
  </table>
</section>

<section>
  <h2>SPL Desired Bookings</h2>
  <p class="muted">Seattle Public Library support is separate and not wired to live booking yet.</p>
  <table>
    <thead><tr><th>Priority</th><th>Visit Date</th><th>Pass</th><th></th></tr></thead>
    <tbody>{booking_rows(spl_bookings)}</tbody>
  </table>
</section>

<section>
  <h2>Passes</h2>
  <form class="inline" method="post" action="/passes/add">
    <label>Name<input name="name" required></label>
    <label>Category<input name="category"></label>
    <label>URL<input name="url"></label>
    <button type="submit">Add Pass</button>
  </form>
  <table>
    <thead><tr><th>Provider</th><th>Name</th><th>Category</th><th>URL</th><th></th></tr></thead>
    <tbody>{pass_rows}</tbody>
  </table>
</section>

<section class="full">
  <h2>Recent Attempts</h2>
  <table>
    <thead><tr><th>Time</th><th>Pass</th><th>Date</th><th>Status</th><th>Mode</th><th>Message</th></tr></thead>
    <tbody>{attempt_rows}</tbody>
  </table>
</section>
"""
    return _page(content, notice=notice)


class LibraryToolHandler(BaseHTTPRequestHandler):
    def do_HEAD(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return

        body = _render_home()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        form = _read_form(self)

        if self.path == "/desired-bookings/add":
            booking = {
                "provider": _form_value(form, "provider") or "kcls",
                "pass_name": _form_value(form, "pass_name"),
                "date": _form_value(form, "date"),
                "priority": int(_form_value(form, "priority") or "1"),
            }
            datetime.fromisoformat(booking["date"])
            save_desired_bookings(load_desired_bookings() + [booking])
            _redirect(self)
            return

        if self.path == "/desired-bookings/delete":
            bookings = load_desired_bookings()
            index = int(_form_value(form, "index"))
            if 0 <= index < len(bookings):
                bookings.pop(index)
                save_desired_bookings(bookings)
            _redirect(self)
            return

        if self.path == "/passes/add":
            passes = load_passes()
            name = _form_value(form, "name")
            passes.append(
                {
                    "name": name,
                    "category": _form_value(form, "category"),
                    "url": _form_value(form, "url"),
                    "notes": "Added from local dashboard. Add selectors before live booking.",
                }
            )
            save_passes(passes)
            _redirect(self)
            return

        if self.path == "/passes/delete":
            passes = load_passes()
            index = int(_form_value(form, "index"))
            if 0 <= index < len(passes):
                passes.pop(index)
                save_passes(passes)
            _redirect(self)
            return

        if self.path == "/run-dry":
            output = StringIO()
            with contextlib.redirect_stdout(output):
                run_once(load_config(), dry_run=True)
            notice = output.getvalue().strip().splitlines()[-1] if output.getvalue().strip() else "Dry run finished."
            body = _render_home(notice=notice)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        return


def run_web_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = HTTPServer((host, port), LibraryToolHandler)
    print(f"Library Ticket Booker running at http://{host}:{port}")
    server.serve_forever()
