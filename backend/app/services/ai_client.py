from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime

import httpx
from openai import OpenAI

from backend.app.config import settings
from backend.app.schemas import HistoryEvent
from backend.app.services.privacy import redact_text


def _extract_json_payload(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _event_lines(events: list[HistoryEvent], max_events: int) -> str:
    clipped = events[:max_events]
    lines: list[str] = []
    for event in clipped:
        safe_title = redact_text(event.title, max_len=160) or "Untitled"
        lines.append(
            f"{event.visited_at.strftime('%Y-%m-%d %I:%M %p')} | {event.browser} | {event.domain} | {safe_title}"
        )
    return "\n".join(lines)


def _safe_text(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _safe_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    clean: list[str] = []
    for item in value:
        text = _safe_text(item)
        if text:
            clean.append(text)
        if len(clean) >= limit:
            break
    return clean


def _safe_int(value: object, *, minimum: int = 0, maximum: int = 100) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(round(float(str(value).strip())))
    except (TypeError, ValueError):
        return None
    return max(minimum, min(maximum, parsed))


def _clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _merge_unique_lists(*lists: list[str], limit: int) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for values in lists:
        for value in values:
            text = _safe_text(value)
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(text)
            if len(merged) >= limit:
                return merged
    return merged


def _grade_from_score(score: int) -> str:
    bands = [
        (97, "A+"),
        (93, "A"),
        (90, "A-"),
        (87, "B+"),
        (83, "B"),
        (80, "B-"),
        (77, "C+"),
        (73, "C"),
        (70, "C-"),
        (67, "D+"),
        (63, "D"),
        (60, "D-"),
    ]
    for floor, grade in bands:
        if score >= floor:
            return grade
    return "F"


def _is_search_event(event: HistoryEvent) -> bool:
    hay = f"{event.domain} {event.url}".lower()
    return "google." in hay or "search" in hay or "query=" in hay


def _is_high_risk_event(event: HistoryEvent) -> bool:
    hay = f"{event.domain} {event.url} {event.title}".lower()
    risky_tokens = ("casino", "bet", "stake", "gambl", "porn", "xxx", "adult")
    return any(token in hay for token in risky_tokens)


def _event_category(event: HistoryEvent) -> str:
    hay = f"{event.domain} {event.title} {event.url}".lower()
    if any(token in hay for token in ("youtube", "netflix", "primevideo", "twitch", "vimeo")):
        return "Video"
    if any(token in hay for token in ("amazon", "flipkart", "ebay", "walmart", "cart", "shop")):
        return "Shopping"
    if any(token in hay for token in ("facebook", "instagram", "reddit", "linkedin", "x.com", "twitter")):
        return "Social"
    if any(token in hay for token in ("docs", "github", "stack", "notion", "developer", "api")):
        return "Work/Learning"
    return "General Web"


def _format_hour_ampm(hour: int) -> str:
    normalized = hour % 24
    suffix = "AM" if normalized < 12 else "PM"
    display = normalized % 12
    if display == 0:
        display = 12
    return f"{display}:00 {suffix}"


def _key_facts(events: list[HistoryEvent]) -> list[str]:
    if not events:
        return []

    total = len(events)
    unique_domains = len({event.domain for event in events if event.domain})
    unique_browsers = len({event.browser for event in events if event.browser})

    domains = Counter(event.domain for event in events if event.domain)
    top_domain, top_domain_count = domains.most_common(1)[0] if domains else ("unknown", 0)

    browsers = Counter(event.browser for event in events if event.browser)
    top_browser, top_browser_count = browsers.most_common(1)[0] if browsers else ("unknown", 0)

    hours = Counter(event.visited_at.hour for event in events)
    peak_hour, peak_hour_count = hours.most_common(1)[0] if hours else (0, 0)

    night_events = sum(1 for event in events if event.visited_at.hour >= 23 or event.visited_at.hour < 5)
    social_events = sum(1 for event in events if _event_category(event) == "Social")
    shopping_events = sum(1 for event in events if _event_category(event) == "Shopping")

    domain_switches = 0
    prev_domain = None
    ordered = sorted(events, key=lambda event: event.visited_at)
    for event in ordered:
        if prev_domain is not None and event.domain != prev_domain:
            domain_switches += 1
        prev_domain = event.domain

    switch_rate = round((domain_switches / max(1, total - 1)) * 100)
    return [
        f"{total} captured events across {unique_domains} unique domains and {unique_browsers} browsers.",
        f"Top domain: {top_domain} with {top_domain_count} visits.",
        f"Most-used browser: {top_browser} with {top_browser_count} events.",
        f"Peak browsing hour: {_format_hour_ampm(peak_hour)} ({peak_hour_count} events).",
        f"Late-night activity: {night_events} events between 11:00 PM and 5:00 AM.",
        f"Social activity count: {social_events}; shopping-related activity count: {shopping_events}.",
        f"Context-switch rate between domains: {switch_rate}%.",
    ]


def _fallback_time_insights(events: list[HistoryEvent]) -> list[str]:
    if not events:
        return []
    hours = Counter(event.visited_at.hour for event in events)
    top_hours = sorted(hours.items(), key=lambda pair: pair[1], reverse=True)[:3]
    insights: list[str] = []
    for hour, count in top_hours:
        insights.append(f"Peak activity around {_format_hour_ampm(hour)} with {count} events.")
    return insights


def _fallback_category_insights(events: list[HistoryEvent]) -> list[str]:
    if not events:
        return []
    categories = Counter(_event_category(event) for event in events)
    total = len(events)
    insights: list[str] = []
    for name, count in categories.most_common(4):
        pct = round((count / total) * 100)
        insights.append(f"{name}: {count} events ({pct}% of tracked activity).")
    return insights


def _fallback_behavior_patterns(events: list[HistoryEvent]) -> list[str]:
    if not events:
        return []
    domains = Counter(event.domain for event in events if event.domain)
    browsers = Counter(event.browser for event in events if event.browser)
    patterns: list[str] = []
    for domain, count in domains.most_common(3):
        patterns.append(f"High repeat browsing on {domain} ({count} visits).")
    for browser, count in browsers.most_common(2):
        patterns.append(f"{browser} contributed {count} captured events.")
    return patterns[:6]


def _fallback_recommendations(events: list[HistoryEvent]) -> list[str]:
    if not events:
        return []
    recommendations = [
        "Group repeat tabs into bookmarks to reduce context switching.",
        "Review high-traffic domains and remove low-value browsing sessions.",
        "Set two focused browsing blocks and keep distraction sites outside those windows.",
    ]
    if any(_event_category(event) == "Shopping" for event in events):
        recommendations.append("Create a dedicated shopping list to avoid repeated price checks.")
    return recommendations[:6]


def _fallback_highlights(events: list[HistoryEvent], key_facts: list[str]) -> list[str]:
    highlights = key_facts[:4]
    if any(event.domain == "facebook.com" for event in events):
        highlights.append("Frequent social media revisit pattern observed on Facebook.")
    if any(event.domain == "youtube.com" for event in events):
        highlights.append("Video consumption is a major share of browsing activity.")
    return highlights[:8]


def _fallback_important_highlights(
    *,
    highlights: list[str],
    risk_flags: list[str],
    key_facts: list[str],
) -> list[str]:
    risk_emphasis = [f"Risk priority: {item}" for item in risk_flags[:3]]
    return _merge_unique_lists(risk_emphasis, highlights[:6], key_facts[:4], limit=8)


def _fallback_intent_signals(events: list[HistoryEvent]) -> list[str]:
    if not events:
        return []

    categories = Counter(_event_category(event) for event in events)
    intents: list[str] = []
    for category, count in categories.most_common(4):
        intents.append(f"{category} intent signal: {count} events indicate repeated interest.")

    search_events = [event for event in events if "google." in event.domain or "search" in event.url.lower()]
    if search_events:
        intents.append(
            f"Discovery intent: {len(search_events)} search-oriented events suggest active exploration and comparison."
        )

    repeat_domains = Counter(event.domain for event in events if event.domain)
    repeat_count = sum(1 for _, count in repeat_domains.items() if count >= 5)
    if repeat_count:
        intents.append(
            f"Depth intent: {repeat_count} domains were revisited at least five times, showing sustained follow-through."
        )

    return intents[:8]


def _fallback_focus_gaps(events: list[HistoryEvent]) -> list[str]:
    if not events:
        return []

    gaps: list[str] = []
    ordered = sorted(events, key=lambda event: event.visited_at)
    switches = 0
    prev_domain = None
    for event in ordered:
        if prev_domain is not None and event.domain != prev_domain:
            switches += 1
        prev_domain = event.domain
    switch_rate = round((switches / max(1, len(ordered) - 1)) * 100)
    if switch_rate >= 55:
        gaps.append(
            f"High context switching: domain-switch rate is {switch_rate}%, which can reduce deep focus."
        )

    late_night = sum(1 for event in events if event.visited_at.hour >= 23 or event.visited_at.hour < 5)
    if late_night >= 8:
        gaps.append(
            f"Late-night spillover: {late_night} events occurred between 11:00 PM and 5:00 AM."
        )

    social_count = sum(1 for event in events if _event_category(event) == "Social")
    if social_count:
        social_pct = round((social_count / len(events)) * 100)
        if social_pct >= 25:
            gaps.append(
                f"Attention dilution: social activity accounts for {social_pct}% of captured activity."
            )

    if not gaps:
        gaps.append("No major focus gaps detected. Browsing pattern is relatively stable for this day.")

    return gaps[:8]


def _fallback_action_plan(events: list[HistoryEvent]) -> list[str]:
    base = [
        "Day 1: Define two focused browsing goals and pin only task-relevant tabs.",
        "Day 2: Run a 90-minute distraction-free block; postpone social/video sites until after completion.",
        "Day 3: Convert repeated lookups into bookmarks or notes to reduce re-search loops.",
        "Day 4: Batch shopping/comparison checks into one fixed 30-minute window.",
        "Day 5: Review top domains and remove low-value recurring destinations from daily flow.",
        "Day 6: Shift deep work browsing to your strongest hour block based on today's peak attention window.",
        "Day 7: Audit improvements: compare context-switch rate and late-night spillover against this report.",
    ]
    if any(_event_category(event) == "Shopping" for event in events):
        base.append("Optional: Maintain one shopping shortlist to avoid repeated price checking across multiple tabs.")
    return base[:8]


def _fallback_methodology(events: list[HistoryEvent]) -> list[str]:
    total = len(events)
    domains = len({event.domain for event in events if event.domain})
    return [
        f"Sample: {total} captured events across {domains} domains for this report date.",
        "Time references are interpreted in local time and formatted in 12-hour AM/PM style.",
        "Signals are derived from domain frequency, category mix, revisit behavior, and time-of-day clustering.",
        "Recommendations are behavior-first and tuned to reduce switching cost while preserving utility browsing.",
    ]


def _compute_examination_result(events: list[HistoryEvent], *, target_date: date) -> dict[str, object]:
    if not events:
        return {
            "examination_grade": "N/A",
            "overall_score": 0,
            "examination_summary": (
                f"Examination result for {target_date.isoformat()}: no captured events were available, "
                "so scoring is not meaningful yet."
            ),
            "scorecard": [
                "Focus Stability: 0/100 - no data available.",
                "Research Depth: 0/100 - no data available.",
                "Execution Discipline: 0/100 - no data available.",
                "Consistency Hygiene: 0/100 - no data available.",
                "Risk Hygiene: 0/100 - no data available.",
                "Learning Momentum: 0/100 - no data available.",
            ],
            "detailed_findings": [
                "No browsing events were captured for this date.",
                "Run sync first, then regenerate the report to produce a full examination result.",
            ],
        }

    ordered = sorted(events, key=lambda event: event.visited_at)
    total = len(ordered)
    domain_counts = Counter(event.domain for event in ordered if event.domain)
    category_counts = Counter(_event_category(event) for event in ordered)
    hour_counts = Counter(event.visited_at.hour for event in ordered)

    switches = 0
    for index in range(1, total):
        if ordered[index].domain != ordered[index - 1].domain:
            switches += 1
    switch_rate_pct = (switches / max(1, total - 1)) * 100

    social_count = category_counts.get("Social", 0)
    video_count = category_counts.get("Video", 0)
    work_count = category_counts.get("Work/Learning", 0)
    late_night_count = sum(1 for event in ordered if event.visited_at.hour >= 23 or event.visited_at.hour < 5)
    search_count = sum(1 for event in ordered if _is_search_event(event))
    risky_count = sum(1 for event in ordered if _is_high_risk_event(event))
    repeat_depth_domains = sum(1 for _, count in domain_counts.items() if count >= 4)

    social_pct = (social_count / total) * 100
    video_pct = (video_count / total) * 100
    work_pct = (work_count / total) * 100
    late_night_pct = (late_night_count / total) * 100
    search_pct = (search_count / total) * 100
    top_domain, top_domain_count = domain_counts.most_common(1)[0] if domain_counts else ("unknown", 0)
    top_domain_share_pct = (top_domain_count / total) * 100
    peak_hour, peak_hour_count = hour_counts.most_common(1)[0] if hour_counts else (0, 0)

    focus_stability = _clamp_score(
        100 - (switch_rate_pct * 0.55) - (social_pct * 0.22) - (video_pct * 0.14)
    )
    research_depth = _clamp_score(
        20 + min(32, search_count * 1.4) + min(22, repeat_depth_domains * 4.5) + min(26, work_pct * 0.55)
    )
    execution_discipline = _clamp_score(
        28 + min(36, work_pct * 0.65) + min(22, (100 - switch_rate_pct) * 0.25) + min(14, search_pct * 0.35)
    )
    consistency_hygiene = _clamp_score(
        100 - min(38, late_night_pct * 0.95) - min(20, abs(top_domain_share_pct - 35) * 0.35)
    )
    risk_hygiene = _clamp_score(100 - min(78, risky_count * 12) - min(24, late_night_pct * 0.45))
    learning_momentum = _clamp_score(
        18 + min(38, work_pct * 0.75) + min(24, search_count * 1.1) + min(20, repeat_depth_domains * 3.3)
    )

    score_map = {
        "Focus Stability": focus_stability,
        "Research Depth": research_depth,
        "Execution Discipline": execution_discipline,
        "Consistency Hygiene": consistency_hygiene,
        "Risk Hygiene": risk_hygiene,
        "Learning Momentum": learning_momentum,
    }
    overall_score = _clamp_score(
        focus_stability * 0.20
        + research_depth * 0.20
        + execution_discipline * 0.20
        + consistency_hygiene * 0.15
        + risk_hygiene * 0.15
        + learning_momentum * 0.10
    )
    examination_grade = _grade_from_score(overall_score)

    sorted_scores = sorted(score_map.items(), key=lambda pair: pair[1], reverse=True)
    strongest = ", ".join(f"{name} ({score}/100)" for name, score in sorted_scores[:2])
    weakest = ", ".join(f"{name} ({score}/100)" for name, score in sorted_scores[-2:])

    start_time = ordered[0].visited_at.strftime("%I:%M %p")
    end_time = ordered[-1].visited_at.strftime("%I:%M %p")
    peak_hour_label = _format_hour_ampm(peak_hour)

    examination_summary = (
        f"Examination result for {target_date.isoformat()}: Grade {examination_grade} with overall score "
        f"{overall_score}/100. Strongest dimensions were {strongest}. Lowest-scoring dimensions were {weakest}. "
        f"Captured activity ran from {start_time} to {end_time}, with a peak around {peak_hour_label} "
        f"({peak_hour_count} events)."
    )

    scorecard = [
        f"Focus Stability: {focus_stability}/100 (domain-switch rate {round(switch_rate_pct)}%).",
        f"Research Depth: {research_depth}/100 ({search_count} search events, {repeat_depth_domains} repeat-depth domains).",
        f"Execution Discipline: {execution_discipline}/100 (Work/Learning share {round(work_pct)}%).",
        f"Consistency Hygiene: {consistency_hygiene}/100 (late-night activity {late_night_count} events).",
        f"Risk Hygiene: {risk_hygiene}/100 ({risky_count} high-risk indicators detected).",
        f"Learning Momentum: {learning_momentum}/100 (search + work signals combined).",
    ]

    detailed_findings = [
        f"Activity window: {start_time} to {end_time} across {total} events.",
        f"Top domain concentration: {top_domain} at {round(top_domain_share_pct)}% of daily traffic.",
        f"Context switching was {round(switch_rate_pct)}%, indicating {'high' if switch_rate_pct >= 55 else 'moderate' if switch_rate_pct >= 35 else 'low'} fragmentation.",
        f"Search-led exploration contributed {search_count} events ({round(search_pct)}% of activity).",
        f"Repeat-depth behavior: {repeat_depth_domains} domains were revisited at least 4 times.",
        f"Category mix: Work/Learning {work_count}, Social {social_count}, Video {video_count}.",
        f"Risk exposure markers: {risky_count} events matched high-risk browsing tokens.",
        f"Late-night footprint: {late_night_count} events occurred between 11:00 PM and 5:00 AM.",
    ]

    return {
        "examination_grade": examination_grade,
        "overall_score": overall_score,
        "examination_summary": examination_summary,
        "scorecard": scorecard,
        "detailed_findings": detailed_findings,
    }


def _fallback_deep_research_paper(
    *,
    target_date: date,
    events: list[HistoryEvent],
    key_facts: list[str],
    behavior_patterns: list[str],
    time_insights: list[str],
    category_insights: list[str],
    intent_signals: list[str],
    focus_gaps: list[str],
    risk_flags: list[str],
    recommendations: list[str],
    examination_grade: str,
    overall_score: int,
    scorecard: list[str],
) -> str:
    if not events:
        return "No events available to generate a deep research paper."

    domains = Counter(event.domain for event in events if event.domain)
    top_domains = ", ".join(f"{name} ({count})" for name, count in domains.most_common(6))
    first_event = min(events, key=lambda event: event.visited_at).visited_at.strftime("%I:%M %p")
    last_event = max(events, key=lambda event: event.visited_at).visited_at.strftime("%I:%M %p")

    paragraphs = [
        (
            f"On {target_date.isoformat()}, Wave captured {len(events)} browser events with activity spanning "
            f"from {first_event} to {last_event}. The behavioral footprint suggests a mixed intent day rather "
            f"than a single-purpose browsing session. Top domain concentration was: {top_domains or 'insufficient data'}."
        ),
        (
            "The factual base indicates repeated loops around the same destinations, suggesting ongoing "
            "problem-solving or high-interest topic follow-up. Key metrics from this run include: "
            + "; ".join(key_facts[:5])
            + ". These metrics point to both deliberate revisits and opportunistic context switches."
        ),
        (
            "Pattern analysis highlights where attention was sustained versus fragmented. Core observations include: "
            + "; ".join(behavior_patterns[:5])
            + ". Time-band behavior also shows meaningful cadence: "
            + "; ".join(time_insights[:4])
            + "."
        ),
        (
            "Category distribution provides a second lens into day-level intent. "
            + "; ".join(category_insights[:4])
            + ". This mix usually reflects the balance between execution browsing (work, docs, task flow) and "
            "consumption browsing (social/video/shopping), which often predicts end-of-day perceived productivity."
        ),
        (
            "Intent signals inferred from revisit patterns and query pathways are as follows: "
            + "; ".join(intent_signals[:5])
            + ". These signals indicate where the user is trying to make progress, where decisions are still open, "
            "and where unresolved ambiguity drives repeat checking."
        ),
        (
            "Focus gap assessment reveals the primary friction points to watch: "
            + "; ".join(focus_gaps[:5])
            + ". These gaps do not necessarily indicate poor discipline; they often represent environment-level "
            "friction, unclear intermediate goals, or notification-driven interruption cost."
        ),
        (
            "Risk review remains situational rather than alarmist. Key risk markers for this day are: "
            + ("; ".join(risk_flags[:4]) if risk_flags else "no critical risk flags identified")
            + ". The practical interpretation is to monitor trend direction across multiple days rather than reacting to a single snapshot."
        ),
        (
            "Operational guidance for the next cycle should prioritize compounding gains through small structural "
            "changes. Recommended interventions are: "
            + "; ".join(recommendations[:5])
            + ". Executed consistently, these actions reduce tab churn, improve session continuity, and increase outcome quality."
        ),
        (
            "Examination-style scoring synthesizes the day into an interpretable verdict: "
            f"Grade {examination_grade} with overall score {overall_score}/100. "
            "Primary scorecard indicators include: "
            + "; ".join(scorecard[:4])
            + ". This framing helps users compare day-over-day quality trends rather than only raw event volume."
        ),
        (
            "Conclusion: today's browsing behavior shows meaningful signals that can be shaped into higher-quality "
            "digital routines. The data supports a strategy of tighter session boundaries, deliberate revisit capture "
            "via bookmarks/notes, and focused windows aligned with peak attention periods."
        ),
    ]
    return "\n\n".join(paragraphs)


def _input_statistics(events: list[HistoryEvent]) -> str:
    facts = _key_facts(events)
    if not facts:
        return "No computed statistics available."
    return "\n".join(f"- {line}" for line in facts)


def generate_daily_report(target_date: date, events: list[HistoryEvent]) -> dict:
    baseline_exam = _compute_examination_result(events, target_date=target_date)

    system_prompt = (
        "You are Wave, an internet activity analyst. "
        "Return valid JSON only with this schema: "
        '{"summary": string, "narrative": string, "deep_research_paper": string, '
        '"highlights": string[4-12], "risk_flags": string[0-8], '
        '"important_highlights": string[4-10], "key_facts": string[6-12], '
        '"behavior_patterns": string[4-10], "time_insights": string[4-10], '
        '"category_insights": string[4-10], "intent_signals": string[4-10], '
        '"focus_gaps": string[3-10], "action_plan_7d": string[7-10], '
        '"methodology_notes": string[3-8], "recommendations": string[4-10], '
        '"examination_summary": string, "examination_grade": string, '
        '"overall_score": number(0-100), "scorecard": string[6-12], '
        '"detailed_findings": string[6-14]}. '
        "Write a deep, long-form research report grounded only in provided events. "
        "The deep_research_paper must be 8-16 paragraphs and richly analytical. "
        "Use concrete observations, browsing rhythms, and practical recommendations. "
        "Include an examination-result style verdict with grading and score interpretation. "
        "Use 12-hour clock format with AM/PM for every time reference. "
        "Put the most important items first in important_highlights. "
        "Mention privacy or security concerns only when strongly justified."
    )
    user_prompt = (
        f"Date: {target_date.isoformat()}\n"
        f"Total events: {len(events)}\n"
        "Deterministic examination baseline:\n"
        f"- Grade: {baseline_exam.get('examination_grade')}\n"
        f"- Overall score: {baseline_exam.get('overall_score')}/100\n"
        f"- Key scorecard signals: {'; '.join((baseline_exam.get('scorecard') or [])[:4])}\n"
        "Computed statistics:\n"
        f"{_input_statistics(events)}\n"
        "Events (newest first):\n"
        f"{_event_lines(events, settings.report_max_events)}"
    )

    reasoning_chunks: list[str] = []
    answer_chunks: list[str] = []
    parsed: dict = {}
    model_warning: str | None = None

    if settings.ai_api_key:
        try:
            client = OpenAI(
                base_url=settings.ai_base_url,
                api_key=settings.ai_api_key,
                timeout=httpx.Timeout(
                    connect=settings.ai_connect_timeout_sec,
                    read=settings.ai_read_timeout_sec,
                    write=max(5.0, settings.ai_connect_timeout_sec),
                    pool=max(5.0, settings.ai_connect_timeout_sec),
                ),
                max_retries=0,
            )

            completion = client.chat.completions.create(
                model=settings.ai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=settings.ai_temperature,
                top_p=settings.ai_top_p,
                max_tokens=settings.ai_max_tokens,
                stream=False,
            )
            if getattr(completion, "choices", None):
                message = completion.choices[0].message
                reasoning = getattr(message, "reasoning_content", None)
                if reasoning:
                    reasoning_chunks.append(str(reasoning))
                content = getattr(message, "content", "")
                if isinstance(content, str):
                    answer_chunks.append(content)
                elif content is not None:
                    answer_chunks.append(str(content))
        except Exception as exc:
            model_warning = (
                "AI model response timed out or failed. "
                f"Wave used deterministic deep analysis. ({exc.__class__.__name__})"
            )
    else:
        model_warning = "AI API key missing. Wave used deterministic deep analysis."

    raw = "".join(answer_chunks).strip()
    if raw:
        try:
            parsed = _extract_json_payload(raw)
        except Exception as exc:
            parsed = {}
            model_warning = (
                "AI output could not be parsed as JSON. "
                f"Wave used deterministic deep analysis. ({exc.__class__.__name__})"
            )

    key_facts = _merge_unique_lists(
        _safe_list(parsed.get("key_facts"), limit=12),
        _key_facts(events),
        limit=12,
    )
    highlights = _merge_unique_lists(
        _safe_list(parsed.get("highlights"), limit=12),
        _fallback_highlights(events, key_facts),
        limit=12,
    )
    risk_flags = _safe_list(parsed.get("risk_flags"), limit=8)[:8]
    important_highlights = _merge_unique_lists(
        _safe_list(parsed.get("important_highlights"), limit=10),
        _fallback_important_highlights(
            highlights=highlights,
            risk_flags=risk_flags,
            key_facts=key_facts,
        ),
        limit=10,
    )
    behavior_patterns = _safe_list(parsed.get("behavior_patterns"), limit=10) or _fallback_behavior_patterns(events)
    time_insights = _safe_list(parsed.get("time_insights"), limit=10) or _fallback_time_insights(events)
    category_insights = _safe_list(parsed.get("category_insights"), limit=10) or _fallback_category_insights(events)
    recommendations = _safe_list(parsed.get("recommendations"), limit=10) or _fallback_recommendations(events)
    intent_signals = _safe_list(parsed.get("intent_signals"), limit=10) or _fallback_intent_signals(events)
    focus_gaps = _safe_list(parsed.get("focus_gaps"), limit=10) or _fallback_focus_gaps(events)
    action_plan_7d = _safe_list(parsed.get("action_plan_7d"), limit=10) or _fallback_action_plan(events)
    overall_score = _safe_int(parsed.get("overall_score"), minimum=0, maximum=100)
    if overall_score is None:
        overall_score = int(baseline_exam.get("overall_score") or 0)

    examination_grade = _grade_from_score(overall_score)
    examination_summary = _safe_text(parsed.get("examination_summary"))
    if len(examination_summary) < 140:
        examination_summary = str(baseline_exam.get("examination_summary") or "")

    scorecard = _merge_unique_lists(
        _safe_list(parsed.get("scorecard"), limit=12),
        list(baseline_exam.get("scorecard") or []),
        limit=12,
    )
    detailed_findings = _merge_unique_lists(
        _safe_list(parsed.get("detailed_findings"), limit=14),
        list(baseline_exam.get("detailed_findings") or []),
        limit=14,
    )

    deep_research_paper = _safe_text(parsed.get("deep_research_paper"))
    if len(deep_research_paper) < 900:
        deep_research_paper = _fallback_deep_research_paper(
            target_date=target_date,
            events=events,
            key_facts=key_facts,
            behavior_patterns=behavior_patterns,
            time_insights=time_insights,
            category_insights=category_insights,
            intent_signals=intent_signals,
            focus_gaps=focus_gaps,
            risk_flags=risk_flags,
            recommendations=recommendations,
            examination_grade=examination_grade,
            overall_score=overall_score,
            scorecard=scorecard,
        )
    summary = _safe_text(parsed.get("summary"))
    if len(summary) < 120:
        summary = (
            f"Wave examination result for {target_date.isoformat()}: Grade {examination_grade} "
            f"with overall score {overall_score}/100. "
            f"{key_facts[0] if key_facts else 'No key facts were available.'}"
        )

    narrative = _safe_text(parsed.get("narrative"))
    if len(narrative) < 300:
        narrative = f"{examination_summary}\n\n{deep_research_paper[:2800]}"

    methodology_notes = _safe_list(parsed.get("methodology_notes"), limit=8) or _fallback_methodology(events)
    if model_warning:
        methodology_notes = _merge_unique_lists(
            methodology_notes,
            [model_warning],
            limit=8,
        )

    return {
        "date": target_date.isoformat(),
        "model": settings.ai_model,
        "summary": summary,
        "highlights": highlights,
        "risk_flags": risk_flags,
        "details": {
            "narrative": narrative,
            "deep_research_paper": deep_research_paper,
            "examination_summary": examination_summary,
            "examination_grade": examination_grade,
            "overall_score": overall_score,
            "scorecard": scorecard,
            "detailed_findings": detailed_findings,
            "important_highlights": important_highlights,
            "key_facts": key_facts,
            "behavior_patterns": behavior_patterns,
            "time_insights": time_insights,
            "category_insights": category_insights,
            "intent_signals": intent_signals,
            "focus_gaps": focus_gaps,
            "action_plan_7d": action_plan_7d,
            "methodology_notes": methodology_notes,
            "recommendations": recommendations,
        },
        "reasoning_trace": "".join(reasoning_chunks).strip() or model_warning,
        "source_events": len(events),
        "generated_at": datetime.now(),
    }
