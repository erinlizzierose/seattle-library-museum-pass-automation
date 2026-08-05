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
from src.main import SUPPORTED_PROVIDERS, compute_target_dates, get_provider_schedule, run_once
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


def _next_priority(bookings: list[dict[str, object]], provider: str, target_date: str) -> int:
    priorities = [
        int(item.get("priority", 0))
        for item in bookings
        if item.get("provider", "kcls") == provider and item.get("date") == target_date
    ]
    return max(priorities, default=0) + 1


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
    .rules {{
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      margin-top: 18px;
    }}
    .provider-summary {{
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }}
    .provider-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
      padding: 18px;
    }}
    .provider-card h2 {{
      margin-bottom: 14px;
    }}
    .metric {{
      background: #0a2427;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .rule {{
      border-top: 1px solid var(--line);
      padding-top: 16px;
    }}
    .rule h3 {{
      margin: 0 0 8px;
      color: var(--accent-strong);
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .rule ul {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.5;
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
    all_attempts = load_attempts()
    attempts = all_attempts[:12]

    provider_labels = {
        "kcls": "King County Library System",
        "spl": "Seattle Public Library",
    }
    provider_rules = {
        "kcls": [
            "New passes are released daily at 2 p.m.",
            "Passes are available 2 weeks into the future.",
            "You can reserve one museum pass per calendar month, counted by visit date.",
            "A reserved but unused pass still counts against that monthly limit.",
        ],
        "spl": [
            "New passes are available daily after 12 p.m.",
            "The reservation system shows available passes for the next 30 days.",
            "Each library card holder can reserve one pass per calendar month, counted by visit date.",
            "Bring the printed or electronic pass and photo ID on the selected visit date.",
        ],
    }
    pass_provider_lookup = {item.get("name", ""): item.get("provider", "kcls") for item in passes}

    def attempt_provider(pass_name: str, provider: str = "") -> str:
        return provider or str(pass_provider_lookup.get(pass_name, "kcls"))

    upcoming_by_key = {}
    today = datetime.now().date()
    for item in all_attempts:
        if not item.success or item.dry_run:
            continue
        try:
            visit_date = datetime.fromisoformat(item.target_date).date()
        except ValueError:
            continue
        if visit_date < today:
            continue
        provider_key = attempt_provider(item.pass_name, item.provider)
        key = (provider_key, item.pass_name, item.target_date)
        upcoming_by_key.setdefault(key, item)

    upcoming_passes = sorted(
        upcoming_by_key.values(),
        key=lambda item: (item.target_date, attempt_provider(item.pass_name, item.provider), item.pass_name),
    )

    def provider_summary(provider: str) -> str:
        schedule = get_provider_schedule(config, provider)
        provider_dates = [
            str(item.get("date", ""))
            for item in desired_bookings
            if item.get("date") and item.get("provider", "kcls") == provider
        ]
        target_dates = compute_target_dates(provider_dates, schedule.days_ahead)
        next_release = datetime.now().date() + timedelta(days=schedule.days_ahead)
        rules = "\n".join(f"<li>{escape(rule)}</li>" for rule in provider_rules[provider])
        return f"""
    <div class="provider-card">
      <h2>{escape(provider_labels[provider])}</h2>
      <div class="summary">
        <div class="metric"><span>Daily run time</span><strong>{escape(schedule.run_time)}</strong></div>
        <div class="metric"><span>Booking window</span><strong>{schedule.days_ahead} days ahead</strong></div>
        <div class="metric"><span>Next target date</span><strong>{next_release.isoformat()}</strong></div>
        <div class="metric"><span>Matching bookings</span><strong>{len(target_dates)}</strong></div>
      </div>
      <div class="rule">
        <h3>{provider.upper()} Rules</h3>
        <ul>{rules}</ul>
      </div>
      <form class="inline" method="post" action="/run-dry">
        <input type="hidden" name="provider" value="{provider}">
        <button type="submit">Run {provider.upper()} Dry Booking</button>
      </form>
    </div>"""

    provider_summary_cards = "\n".join(provider_summary(provider) for provider in SUPPORTED_PROVIDERS)

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

    def pass_options_for(provider: str) -> str:
        return "\n".join(
            f"""<option value="{escape(item.get("name", ""))}">{escape(item.get("name", ""))}</option>"""
            for item in passes if item.get("provider", "kcls") == provider
        )

    kcls_pass_options = pass_options_for("kcls")
    spl_pass_options = pass_options_for("spl")

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

    def next_target_date_for(provider: str) -> str:
        schedule = get_provider_schedule(config, provider)
        return (datetime.now().date() + timedelta(days=schedule.days_ahead)).isoformat()

    def next_priority_for(provider: str, target_date: str) -> int:
        return _next_priority(desired_bookings, provider, target_date)

    def booking_form(provider: str, pass_options: str) -> str:
        if not pass_options:
            return f"""<p class="muted">No {provider.upper()} passes loaded yet. Refresh that provider's pass list from the CLI first.</p>"""
        default_date = next_target_date_for(provider)
        default_priority = next_priority_for(provider, default_date)
        return f"""
  <form class="inline" method="post" action="/desired-bookings/add">
    <input type="hidden" name="provider" value="{provider}">
    <label>Pass
      <select name="pass_name" required>
        {pass_options}
      </select>
    </label>
    <label>Date<input type="date" name="date" value="{default_date}" required></label>
    <label>Priority<input type="number" name="priority" value="{default_priority}" min="1" required></label>
    <button type="submit">Add Booking</button>
  </form>"""

    attempt_rows = "\n".join(
        f"""<tr>
  <td>{escape(item.attempted_at)}</td>
  <td>{escape(attempt_provider(item.pass_name, item.provider).upper())}</td>
  <td>{escape(item.pass_name)}</td>
  <td>{escape(item.target_date)}</td>
  <td class="{'status-ok' if item.success else 'status-fail'}">{'Success' if item.success else 'Failed'}</td>
  <td>{'Dry-run' if item.dry_run else 'Live'}</td>
  <td>{escape(item.message)}</td>
</tr>"""
        for item in attempts
    ) or "<tr><td colspan='7'>No attempts logged yet.</td></tr>"

    upcoming_rows = "\n".join(
        f"""<tr>
  <td>{escape(attempt_provider(item.pass_name, item.provider).upper())}</td>
  <td>{escape(item.pass_name)}</td>
  <td>{escape(item.target_date)}</td>
  <td>{escape(item.attempted_at)}</td>
  <td class="status-ok">Booked</td>
</tr>"""
        for item in upcoming_passes
    ) or "<tr><td colspan='5'>No upcoming passes logged yet.</td></tr>"

    content = f"""
<section class="full">
  <h2>Upcoming Passes</h2>
  <table>
    <thead><tr><th>Provider</th><th>Pass</th><th>Visit Date</th><th>Booked At</th><th>Status</th></tr></thead>
    <tbody>{upcoming_rows}</tbody>
  </table>
</section>

<section class="full">
  <div class="provider-summary">{provider_summary_cards}</div>
</section>

<section>
  <h2>King County Library System Desired Bookings</h2>
  {booking_form("kcls", kcls_pass_options)}
  <table>
    <thead><tr><th>Priority</th><th>Visit Date</th><th>Pass</th><th></th></tr></thead>
    <tbody>{booking_rows(kcls_bookings)}</tbody>
  </table>
</section>

<section>
  <h2>Seattle Public Library Desired Bookings</h2>
  {booking_form("spl", spl_pass_options)}
  <table>
    <thead><tr><th>Priority</th><th>Visit Date</th><th>Pass</th><th></th></tr></thead>
    <tbody>{booking_rows(spl_bookings)}</tbody>
  </table>
</section>

<section>
  <h2>Passes</h2>
  <form class="inline" method="post" action="/passes/add">
    <label>Provider
      <select name="provider">
        <option value="kcls">KCLS</option>
        <option value="spl">SPL</option>
      </select>
    </label>
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
    <thead><tr><th>Time</th><th>Provider</th><th>Pass</th><th>Date</th><th>Status</th><th>Mode</th><th>Message</th></tr></thead>
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
            bookings = load_desired_bookings()
            provider = _form_value(form, "provider") or "kcls"
            target_date = _form_value(form, "date")
            requested_priority = int(_form_value(form, "priority") or "1")
            used_priorities = {
                int(item.get("priority", 0))
                for item in bookings
                if item.get("provider", "kcls") == provider and item.get("date") == target_date
            }
            priority = _next_priority(bookings, provider, target_date) if requested_priority in used_priorities else requested_priority
            booking = {
                "provider": provider,
                "pass_name": _form_value(form, "pass_name"),
                "date": target_date,
                "priority": priority,
            }
            datetime.fromisoformat(booking["date"])
            save_desired_bookings(bookings + [booking])
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
                    "provider": _form_value(form, "provider") or "kcls",
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
            provider = _form_value(form, "provider") or None
            output = StringIO()
            with contextlib.redirect_stdout(output):
                run_once(load_config(), dry_run=True, provider=provider)
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
