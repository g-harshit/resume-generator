# Chrome Web Store listing — QuickFit CV

Everything the Developer Dashboard asks for, ready to paste. Upload
`apps/extension/dist/1.0.0/quickfitcv-chrome-store-1.0.0.zip`
(rebuild with `pnpm zip:extension:store`).

## Store listing tab

**Name:** QuickFit CV *(from the manifest)*

**Summary** (≤132 characters):
> Tailor your resume to the job you're looking at: one click, an ATS-ready PDF, and nothing added that isn't in your profile.

**Description:**
> QuickFit CV turns the resume you already have into one tailored to each job — right from the job posting.
>
> HOW IT WORKS
> 1. Open any job posting: LinkedIn, Naukri, Indeed, Greenhouse, Lever, Workday or a company's careers page.
> 2. Click the QuickFit CV icon. The side panel finds the job description on the page.
> 3. Pick a template and click "Tailor my resume". In about half a minute you have an ATS-friendly PDF.
>
> NOTHING INVENTED
> QuickFit CV only reorders, selects and rewords what's already in your profile. It never adds a skill, employer, date or number you didn't give it — every change is checked against your profile, and anything it can't verify stays in your own words.
>
> ALSO
> • See which of the job's skills your resume covers, and which it doesn't.
> • Open the resume in the editor on quickfitcv.com to adjust it, fit it to one page, or write a cover letter.
> • Four clean, single-column templates that applicant tracking systems read correctly.
>
> You'll need a free QuickFit CV account (sign in with Google or email). Your profile comes from the resume you upload on quickfitcv.com.
>
> Privacy: the extension only reads the page you open it on, and only to find the job description. Details: https://quickfitcv.com/privacy

**Category:** Productivity → Tools  
**Language:** English

**Graphics** (all in `apps/extension/store/`):
| Asset | File |
|---|---|
| Store icon 128×128 | `icon-128.png` |
| Screenshot 1 (1280×800) | `screenshot-1-job-found.png` |
| Screenshot 2 (1280×800) | `screenshot-2-ready.png` |
| Small promo tile 440×280 | `promo-small-440x280.png` |

**Official URL / Homepage:** https://quickfitcv.com  
**Support URL:** https://quickfitcv.com/privacy *(has the contact email)*

## Privacy practices tab

**Single purpose:**
> Tailor the user's resume to the job posting open in the current tab: read the job description from the page and send it to the user's QuickFit CV account to produce a tailored resume.

**Permission justifications:**
| Permission | Justification |
|---|---|
| `sidePanel` | The extension's whole interface is a side panel shown beside the job posting. |
| `storage` | Keeps the user signed in: stores the sign-in token the QuickFit CV website hands to the extension. |
| `activeTab` | Reads the job posting in the tab where the user clicked the icon — only that tab, only then. |
| `scripting` | Runs the function that finds the job description on that page (structured job data, or the main job text). No remote code. |
| Host permissions (optional, `http://*/*`, `https://*/*`) | Not granted at install. Only requested, per site, when the user clicks "Allow on this site" so the panel can follow them to job pages on that site. |

**Remote code:** No, I am not using remote code. *(All code ships in the package.)*

**Data usage — what is collected:**
- [x] Personally identifiable information — name and email of the user's account (shown in the panel).
- [x] Authentication information — the sign-in token, stored in the extension.
- [x] Website content — the text of the job posting on the page the user opens the panel on.
- Everything else: **not collected** (health, financial, location, web history, user activity, personal communications).

**Certify** (all three, which are true):
- I do not sell or transfer user data to third parties, outside of the approved use cases.
- I do not use or transfer user data for purposes that are unrelated to my item's single purpose.
- I do not use or transfer user data to determine creditworthiness or for lending purposes.

**Privacy policy URL:** https://quickfitcv.com/privacy

## Distribution

**Visibility:** Public · **Regions:** All regions (or India first, if you prefer)

## After it's published

The Store gives the extension its own ID (32 letters, in the item's URL). Send it over:
it must be added to `NEXT_PUBLIC_EXTENSION_IDS` (website, for the sign-in handoff) and
`CORS_ORIGINS` (API) in `render.yaml`, then deployed. Until then the published extension
can't sign in. The unpacked build keeps working alongside it.
