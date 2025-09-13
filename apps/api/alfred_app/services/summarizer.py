def summarize_lines(lines: list[str], max_bullets: int = 7) -> str:
    out = []
    for ln in lines:
        first = ln.strip().split(". ")[0]
        if first:
            out.append(f"- {first.strip()}.")
        if len(out) >= max_bullets:
            break
    return "\n".join(out)
