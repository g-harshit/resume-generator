/**
 * Read the job posting on the current page.
 *
 * This function is injected into the page with chrome.scripting.executeScript, which
 * serialises it: it must be self-contained — no imports, no references to anything
 * outside its own body.
 *
 * In order of trust:
 *  1. JSON-LD `JobPosting` — the structured data many job sites publish for Google
 *  2. known job sites' description containers (LinkedIn, Naukri, Indeed, Greenhouse,
 *     Lever, Workday)
 *  3. the text under an "About the job" / "Job description" heading
 *  4. the page's main block of text that reads like a job description
 * or, when asked, whatever the person has selected.
 */
export type ExtractedJob = {
  source: "json-ld" | "site" | "page" | "selection";
  title: string;
  company: string;
  text: string;
  url: string;
};

export function extractJob(mode: "auto" | "selection" = "auto"): ExtractedJob | null {
  const clean = (s: string | null | undefined) =>
    (s ?? "")
      .replace(/ /g, " ")
      .replace(/[ \t]+/g, " ")
      .replace(/\s*\n\s*/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  const htmlToText = (html: string) => {
    const div = document.createElement("div");
    // Block elements become line breaks, so bullets stay one per line.
    div.innerHTML = html.replace(/<(br|\/p|\/li|\/h\d|\/div)[^>]*>/gi, "$&\n");
    return clean(div.textContent);
  };
  const textOf = (el: Element | null) => (el ? clean((el as HTMLElement).innerText ?? el.textContent) : "");
  const first = (selectors: string[]) => {
    for (const s of selectors) {
      const el = document.querySelector(s);
      if (el && textOf(el)) return el;
    }
    return null;
  };
  // The longest match: a selector can match several boxes (LinkedIn's
  // expandable-text-box holds the description, and the hiring person's bio).
  const longest = (selectors: string[]) => {
    for (const s of selectors) {
      const els = Array.from(document.querySelectorAll(s)).filter((el) => textOf(el));
      if (els.length) return els.sort((a, b) => textOf(b).length - textOf(a).length)[0]!;
    }
    return null;
  };
  // "Tech Lead | Swish | LinkedIn" (and "(3) " for unread notifications).
  const titleParts = () =>
    document.title
      .replace(/^\(\d+\+?\)\s*/, "")
      .split(/\s+[|·–-]\s+/)
      .map((p) => p.trim())
      .filter(Boolean);
  const url = location.href;
  const MIN = 200;

  if (mode === "selection") {
    const text = clean(window.getSelection()?.toString());
    return text ? { source: "selection", title: "", company: "", text, url } : null;
  }

  // 1. JSON-LD
  const postings: Record<string, unknown>[] = [];
  const collect = (node: unknown) => {
    if (Array.isArray(node)) return node.forEach(collect);
    if (!node || typeof node !== "object") return;
    const obj = node as Record<string, unknown>;
    const type = obj["@type"];
    if (type === "JobPosting" || (Array.isArray(type) && type.includes("JobPosting"))) postings.push(obj);
    if (obj["@graph"]) collect(obj["@graph"]);
  };
  document.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
    try {
      collect(JSON.parse(s.textContent ?? ""));
    } catch {
      // Malformed JSON-LD is common; skip it.
    }
  });
  for (const p of postings) {
    const text = htmlToText(String(p.description ?? ""));
    if (text.length >= MIN) {
      const org = p.hiringOrganization as { name?: string } | string | undefined;
      return {
        source: "json-ld",
        title: clean(String(p.title ?? "")),
        company: clean(typeof org === "string" ? org : (org?.name ?? "")),
        text: [clean(String(p.title ?? "")), text].filter(Boolean).join("\n\n"),
        url,
      };
    }
  }

  // 2. Known job sites. Class names change; each list goes from the most specific to
  // broader fallbacks.
  const host = location.hostname;
  const sites: { match: RegExp; body: string[]; title: string[]; company: string[] }[] = [
    {
      match: /linkedin\.com$/,
      // 2026 layout first: the description in an expandable-text-box under "About the job".
      body: [
        "[data-testid='expandable-text-box']",
        ".jobs-description__content",
        ".jobs-box__html-content",
        "#job-details",
        ".description__text",
      ],
      title: [".job-details-jobs-unified-top-card__job-title", ".top-card-layout__title", "h1"],
      company: [".job-details-jobs-unified-top-card__company-name", ".topcard__org-name-link"],
    },
    {
      match: /naukri\.com$/,
      body: ['[class*="dang-inner-html"]', '[class*="job-desc"]', ".job-desc"],
      title: ['[class*="jd-header-title"]', "h1"],
      company: ['[class*="jd-header-comp-name"] a', '[class*="comp-name"]'],
    },
    {
      match: /indeed\.(com|co\.\w+)$/,
      body: ["#jobDescriptionText"],
      title: ['[data-testid="jobsearch-JobInfoHeader-title"]', "h1"],
      company: ['[data-testid="inlineHeader-companyName"]', '[data-company-name="true"]'],
    },
    {
      match: /greenhouse\.io$/,
      body: [".job__description", "#content", "#app_body"],
      title: [".job__title h1", ".app-title", "h1"],
      company: [".company-name"],
    },
    {
      match: /lever\.co$/,
      body: [".posting-page .content", ".section-wrapper.page-full-width"],
      title: [".posting-headline h2", "h2"],
      company: [".main-header-logo img"],
    },
    {
      match: /myworkdayjobs\.com$/,
      body: ['[data-automation-id="jobPostingDescription"]'],
      title: ['[data-automation-id="jobPostingHeader"]', "h2"],
      company: [],
    },
  ];
  const site = sites.find((s) => s.match.test(host));
  if (site) {
    const body = textOf(longest(site.body));
    if (body.length >= MIN) {
      let title = textOf(first(site.title));
      const companyEl = first(site.company);
      let company = companyEl?.tagName === "IMG" ? clean(companyEl.getAttribute("alt")) : textOf(companyEl);
      // LinkedIn's 2026 layout has no stable title/company markup (its only h1 can be the
      // search box's "Search for more than just job titles"); its page title,
      // "Title | Company | LinkedIn", always names the job on screen.
      const parts = titleParts();
      if (/linkedin/i.test(parts.at(-1) ?? "") && parts.length >= 3) {
        title = parts[0]!;
        company = parts[1]!;
      }
      return { source: "site", title, company, text: [title, company, body].filter(Boolean).join("\n\n"), url };
    }
  }

  // 3. A heading that says "this is the job": the smallest block around it that holds
  // a description's worth of text.
  const jobHeading = Array.from(document.querySelectorAll("h1, h2, h3, h4")).find((h) =>
    /^(about (the|this) (job|role|position|opportunity)|job description|role description|the role|description)$/i.test(
      textOf(h),
    ),
  );
  if (jobHeading) {
    let el: Element | null = jobHeading.parentElement;
    while (el && el !== document.body && textOf(el).length < textOf(jobHeading).length + MIN) el = el.parentElement;
    const text = el && el !== document.body ? textOf(el) : "";
    if (text.length >= MIN && text.length <= 30000) {
      const parts = titleParts();
      return {
        source: "page",
        title: textOf(document.querySelector("h1")) || parts[0] || "",
        company: parts.length >= 3 ? parts[1]! : "",
        text,
        url,
      };
    }
  }

  // 4. The page's main text block that reads like a job description: the largest
  // candidate that mentions what a posting always does.
  const looksLikeJob = /responsibilit|requirement|qualification|what you('|’)ll|experience|you will|we('|’)re looking/i;
  const candidates = Array.from(document.querySelectorAll("main, article, [role=main], section, div"))
    .map((el) => ({ el, text: textOf(el) }))
    .filter((c) => c.text.length >= MIN && c.text.length <= 30000 && looksLikeJob.test(c.text));
  if (candidates.length) {
    // Prefer the smallest block that still holds most of the job text, not <body>.
    candidates.sort((a, b) => b.text.length - a.text.length);
    const largest = candidates[0]!.text.length;
    const best = candidates.filter((c) => c.text.length >= largest * 0.6).at(-1)!;
    const title = textOf(document.querySelector("h1"));
    return { source: "page", title, company: "", text: best.text, url };
  }
  return null;
}
