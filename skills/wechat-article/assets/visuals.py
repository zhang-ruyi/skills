"""Inline-CSS building blocks for WeChat-native articles.

Use these inside a `:::html` block (or paste the returned HTML). Do not use
classes or a <style> tag: WeChat strips them. `scripts/build_html.py` bumps
font sizes one notch and converts Chinese punctuation after these blocks are
emitted.

    from visuals import panel, card, pill, down, field_cards

    inner = card("GPU HBM", "paged KV block", pill("B0", "blue") + pill("B1", "blue"), "blue")
    inner += down("store_kv · GPU→CPU 拷贝")
    inner += card("L1 DRAM", "MemoryObj", pill("c0/g0/r0", "violet"), "violet")
    print(panel("block → MemoryObj → 文件/slot", "同一段 KV 的不同视图", inner))
"""
import html

TONES = {
    "blue":   {"solid": "#3b82f6", "border": "#bfdbfe", "bg": "#eff6ff", "text": "#1d4ed8"},
    "violet": {"solid": "#8b5cf6", "border": "#ddd6fe", "bg": "#f5f3ff", "text": "#6d28d9"},
    "green":  {"solid": "#22c55e", "border": "#bbf7d0", "bg": "#f0fdf4", "text": "#15803d"},
    "amber":  {"solid": "#f59e0b", "border": "#fde68a", "bg": "#fffbeb", "text": "#b45309"},
    "rose":   {"solid": "#ef4444", "border": "#fecaca", "bg": "#fef2f2", "text": "#b91c1c"},
    "teal":   {"solid": "#14b8a6", "border": "#99f6e4", "bg": "#f0fdfa", "text": "#0f766e"},
    "slate":  {"solid": "#64748b", "border": "#cbd5e1", "bg": "#f8fafc", "text": "#334155"},
}
MONO = "Menlo,Consolas,'Courier New',monospace"


def esc(text):
    return html.escape(str(text).replace("`", ""), quote=False)


def pill(text, tone="slate"):
    c = TONES[tone]
    return (
        f'<span style="display:inline-block;font-family:{MONO};font-size:10.5px;'
        f'line-height:1.5;padding:2px 6px;border-radius:4px;border:1px solid {c["border"]};'
        f'background:{c["bg"]};color:{c["text"]};margin:0 4px 4px 0;vertical-align:middle;'
        f'white-space:normal;word-break:break-word;">{text}</span>'
    )


def arrow(label="→"):
    return (
        f'<span style="display:inline-block;font-size:11px;color:#94a3b8;'
        f'margin:0 2px;vertical-align:middle;">{label}</span>'
    )


def down(label=""):
    label = f" {label}" if label else ""
    return (
        f'<div style="text-align:center;color:#94a3b8;font-size:11px;'
        f'line-height:1.3;padding:5px 0;">↓{label}</div>'
    )


def note(text, mt="6px"):
    return (
        f'<div style="font-size:11.5px;color:#475569;line-height:1.65;'
        f'margin-top:{mt};word-break:break-word;">{text}</div>'
    )


def card(label, title, body, tone="slate", extra=""):
    c = TONES[tone]
    head = ""
    if label:
        head += (
            f'<div style="font-size:10px;letter-spacing:.08em;text-transform:uppercase;'
            f'color:#64748b;line-height:1.5;">{label}</div>'
        )
    if title:
        head += (
            f'<div style="font-size:13.5px;font-weight:700;color:#0f172a;'
            f'line-height:1.45;margin-top:2px;word-break:break-word;">{title}</div>'
        )
    return (
        f'<div style="border:1px solid #e2e8f0;border-left:4px solid {c["solid"]};'
        f'border-radius:10px;background:#fff;padding:10px 12px;{extra}">{head}{body}</div>'
    )


def panel(title, subtitle, inner):
    sub = (
        f'<div style="font-size:11.5px;color:#64748b;line-height:1.5;'
        f'margin-top:2px;">{subtitle}</div>' if subtitle else ""
    )
    return (
        f'<div style="margin:18px 0;padding:14px 14px 16px;border:1px solid #e2e8f0;'
        f'border-radius:14px;background:#fbfdff;">'
        f'<div style="font-size:15px;font-weight:700;color:#0f172a;line-height:1.4;">{title}</div>'
        f'{sub}<div style="margin-top:12px;">{inner}</div></div>'
    )


def field_cards(rows, tone):
    tones = tone if isinstance(tone, list) else [tone] * len(rows)
    out = []
    for (k, v), t in zip(rows, tones):
        c = TONES[t]
        out.append(
            f'<div style="margin-top:7px;padding:8px 10px;border:1px solid #e2e8f0;'
            f'border-left:3px solid {c["solid"]};border-radius:8px;background:#fff;">'
            f'<div style="font-family:{MONO};font-size:10.5px;font-weight:600;color:{c["text"]};'
            f'line-height:1.5;word-break:break-word;">{esc(k)}</div>'
            f'<div style="font-size:11.5px;color:#334155;line-height:1.65;margin-top:2px;'
            f'word-break:break-word;">{v}</div></div>'
        )
    return "".join(out)


def chain(parts, tones=None):
    """Horizontal mapping: pill → pill → pill. Keep parts short."""
    tones = tones or ["blue", "slate", "violet"]
    bits = []
    for i, part in enumerate(parts):
        bits.append(pill(esc(part), tones[i % len(tones)]))
        if i < len(parts) - 1:
            bits.append(arrow())
    return "".join(bits)


def strip(label, text, tone):
    """READ/WRITE style two-state strip inside a card."""
    c = TONES[tone]
    return (
        f'<div style="margin-top:6px;padding:7px 9px;border-radius:6px;'
        f'border:1px solid {c["border"]};background:{c["bg"]};">'
        f'<span style="font-size:10px;font-weight:700;letter-spacing:.06em;'
        f'color:{c["text"]};">{label}</span>'
        f'<span style="font-size:11.5px;color:#334155;margin-left:6px;'
        f'line-height:1.6;">{text}</span></div>'
    )
