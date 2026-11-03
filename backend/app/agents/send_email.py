"""send_email agent (LLM summary + SMTP): write and send the daily report."""
import asyncio
import html
import json
import logging
import smtplib
from email.message import EmailMessage

from pydantic import BaseModel

from app.agents.llm import ask
from app.agents.state import PipelineState, compact
from app.config import get_settings

log = logging.getLogger(__name__)


class EmailSummary(BaseModel):
    subject: str
    summary: str


EMAIL_FIELDS = ("rank", "title", "price_lkr", "year", "mileage_km", "location", "rank_reason", "red_flags")
SENT_FIELDS = ("title", "price_lkr", "sent_price", "price_change")

SYSTEM = (
    "You write a short daily email for a vehicle buyer. The report has three sections: new vehicles found "
    "today (ranked), vehicles from earlier emails that are still for sale, and earlier ones that are no longer "
    "available. Plain text, 3-6 sentences: the standout new pick and why, any price drops on vehicles they "
    "already saw, anything to watch out for. The tables are attached below your text, so don't repeat every vehicle."
)


def _price(p: int | None) -> str:
    return f"Rs. {p:,}" if p else "—"


def _change(t: dict) -> str:
    c = t.get("price_change")
    if not c:
        return ""
    color = "#1D9E75" if c < 0 else "#B4332B"
    return f'<br><small style="color:{color}">{"▼" if c < 0 else "▲"} Rs. {abs(c):,} since sent</small>'


def _link(t: dict) -> str:
    return f"<a href=\"{html.escape(t['url'])}\">{html.escape(t.get('title', ''))}</a><br><small>{t.get('site', '')}</small>"


def _table(head: list[str], rows: list[str]) -> str:
    th = "".join(f"<th align=\"left\">{h}</th>" for h in head)
    return ('<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:sans-serif;font-size:13px">'
            f"<tr>{th}</tr>{''.join(rows)}</table>")


def _html(summary: str, top: list[dict], still: list[dict], gone: list[dict]) -> str:
    parts = [f"<p>{html.escape(summary).replace(chr(10), '<br>')}</p>"]

    parts.append(f"<h3>New today ({len(top)})</h3>")
    parts.append(_table(["#", "Vehicle", "Price", "Year", "Condition", "Value", "Why"], [
        f"<tr><td>{t['rank']}</td><td>{_link(t)}</td><td>{_price(t.get('price_lkr'))}</td><td>{t.get('year') or '—'}</td>"
        f"<td>{t.get('condition_score', '—')}/10</td><td>{t.get('value_score', '—')}/10</td>"
        f"<td>{html.escape(t.get('rank_reason', ''))}</td></tr>"
        for t in top
    ]) if top else "<p>No new vehicles matched today.</p>")

    if still:
        parts.append(f"<h3>Still available from earlier emails ({len(still)})</h3>")
        parts.append(_table(["Vehicle", "Price now", "Year", "First sent"], [
            f"<tr><td>{_link(t)}</td><td>{_price(t.get('price_lkr'))}{_change(t)}</td><td>{t.get('year') or '—'}</td>"
            f"<td>{(t.get('sent_at') or '')[:10]}</td></tr>"
            for t in still
        ]))

    if gone:
        parts.append(f"<h3>No longer available ({len(gone)})</h3>")
        parts.append(_table(["Vehicle", "Last price", "First sent"], [
            f"<tr><td><s>{html.escape(t.get('title', ''))}</s><br><small>{t.get('site', '')}</small></td>"
            f"<td>{_price(t.get('price_lkr'))}</td><td>{(t.get('sent_at') or '')[:10]}</td></tr>"
            for t in gone
        ]))
    return "".join(parts)


def _send(to: str, subject: str, text: str, html_body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, s.email_from or s.smtp_user, to
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(s.smtp_host, s.smtp_port) as smtp:
        smtp.starttls()
        smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)


async def send_email(state: PipelineState) -> dict:
    top = state.get("top_listings", [])
    still = state.get("still_available", [])
    gone = state.get("unavailable", [])
    price_drops = [t for t in still if (t.get("price_change") or 0) < 0]

    if top or price_drops or gone:
        lines = lambda items, fields: "\n".join(json.dumps(compact(t, fields), ensure_ascii=False) for t in items)
        report = await ask(
            SYSTEM,
            f"Buyer request: {state['vehicle_query']}\n\n"
            f"New today, ranked:\n{lines(top, EMAIL_FIELDS) or 'none'}\n\n"
            f"Still available from earlier emails: {len(still)}. Price drops:\n{lines(price_drops, SENT_FIELDS) or 'none'}\n\n"
            f"No longer available: {len(gone)}",
            EmailSummary,
            effort="low",
        )
        subject, summary = report.subject, report.summary
    else:
        subject = f"No new vehicles today: {state['vehicle_query']}"
        summary = ("No new vehicles matched your search today. "
                   + (f"{len(still)} from earlier emails are still available. " if still else "")
                   + "We'll check again tomorrow.")

    settings = get_settings()
    if not (settings.smtp_user and settings.smtp_password):
        log.warning("SMTP not configured; skipping email to %s", state["email"])
        return {"summary": summary, "email_sent": False}

    try:
        await asyncio.to_thread(_send, state["email"], subject, summary, _html(summary, top, still, gone))
    except Exception as e:
        # Keep the analysed results even if the email can't be delivered.
        log.exception("sending email to %s failed", state["email"])
        return {"summary": summary, "email_sent": False, "email_error": str(e)}
    return {"summary": summary, "email_sent": True}
