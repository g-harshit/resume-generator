// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { extractJob } from "./extract";

const REQUIREMENTS = `
  <h3>What you'll need</h3>
  <ul>
    <li>5+ years building backend services, mostly in Go</li>
    <li>Deep Postgres: schema design, query plans, partitioning</li>
    <li>Services talking gRPC, deployed on Kubernetes on AWS</li>
    <li>Experience with distributed systems and on-call</li>
  </ul>
  <p>You'll own the services behind our payments platform: ledgers, settlement and payouts.</p>`;

function page(html: string, url = "https://careers.example.com/jobs/42") {
  window.history.replaceState({}, "", "/");
  Object.defineProperty(window, "location", { value: new URL(url), configurable: true });
  document.body.innerHTML = html;
}

afterEach(() => {
  document.head.innerHTML = "";
  document.body.innerHTML = "";
});

describe("extractJob", () => {
  it("prefers JSON-LD JobPosting, and keeps one bullet per line", () => {
    page(`<nav>Home · Jobs · Sign in</nav>
      <script type="application/ld+json">${JSON.stringify({
        "@context": "https://schema.org",
        "@graph": [
          { "@type": "Organization", name: "Ignore me" },
          {
            "@type": "JobPosting",
            title: "Senior Backend Engineer",
            hiringOrganization: { "@type": "Organization", name: "Northwind Labs" },
            description: REQUIREMENTS,
          },
        ],
      })}</script>`);
    const job = extractJob()!;
    expect(job.source).toBe("json-ld");
    expect(job.title).toBe("Senior Backend Engineer");
    expect(job.company).toBe("Northwind Labs");
    expect(job.text).toContain("5+ years building backend services, mostly in Go\nDeep Postgres");
    expect(job.text).not.toContain("Sign in");
  });

  it("skips malformed JSON-LD and falls through", () => {
    page(`<script type="application/ld+json">{ not json</script><main><h1>Backend Engineer</h1>${REQUIREMENTS}</main>`);
    expect(extractJob()!.source).toBe("page");
  });

  it("reads a known job site's description container", () => {
    page(
      `<div class="sidebar">Similar jobs: Frontend Engineer, Data Engineer</div>
       <h1 class="top-card-layout__title">Senior Backend Engineer</h1>
       <a class="topcard__org-name-link">Northwind Labs</a>
       <div class="description__text">${REQUIREMENTS}</div>`,
      "https://www.linkedin.com/jobs/view/123",
    );
    const job = extractJob()!;
    expect(job.source).toBe("site");
    expect(job.company).toBe("Northwind Labs");
    expect(job.text).toContain("Deep Postgres");
    expect(job.text).not.toContain("Similar jobs");
  });

  it("finds the job block on an unknown page, not the whole page", () => {
    page(`<header>Acme Careers — Home, About, Blog, Contact, Press, Investors</header>
      <main><h1>Platform Engineer</h1><div class="job">${REQUIREMENTS}</div></main>
      <footer>© Acme. Privacy. Terms. Cookies.</footer>`);
    const job = extractJob()!;
    expect(job.source).toBe("page");
    expect(job.title).toBe("Platform Engineer");
    expect(job.text).toContain("distributed systems");
    expect(job.text).not.toContain("Investors");
  });

  it("returns null when nothing reads like a job", () => {
    page(`<main><h1>Our blog</h1><p>Ten tips for better coffee.</p></main>`);
    expect(extractJob()).toBeNull();
  });

  it("uses the selection when asked", () => {
    page(`<p id="p">Senior Backend Engineer. Go, Postgres, Kubernetes.</p>`);
    const range = document.createRange();
    range.selectNodeContents(document.getElementById("p")!);
    window.getSelection()!.addRange(range);
    expect(extractJob("selection")).toMatchObject({
      source: "selection",
      text: "Senior Backend Engineer. Go, Postgres, Kubernetes.",
    });
  });
});
