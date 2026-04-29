# AI healthcare evidence intake: ambient scribes and adjacent adoption evidence

Date: 2026-04-29. Scope: peer-reviewed and systematic-review evidence, prioritizing 2020-2026, with ambient AI scribes/clinical documentation first and adjacent clinical AI adoption second. Claims below are intentionally conservative; most ambient-scribe evidence remains observational, short follow-up, US-heavy, and/or based on voluntary adopters.

## Search queries used

PubMed / NCBI E-utilities searches run 2026-04-29:
- `ambient artificial intelligence scribe clinical documentation EHR study`
- `large language model ambient clinical documentation physicians notes study`
- `AI scribes documentation burden systematic review`
- `ambient clinical documentation scribe artificial intelligence physician burnout 2020:2026`
- `generative AI clinical documentation adoption survey physicians`
- `artificial intelligence healthcare implementation adoption systematic review barriers facilitators 2020 2026`
- `clinician trust artificial intelligence healthcare adoption systematic review`
- `large language models clinical practice systematic review healthcare 2024`
- `AI healthcare Germany physicians survey artificial intelligence 2020`

## High-level synthesis for SimMed

- Best-supported near-term mechanism: documentation-assistance AI may reduce documentation time and perceived cognitive burden for some clinicians, especially frequent users in ambulatory care. The largest visible multisite cohort reported -13.4 minutes total EHR time and -16.0 minutes documentation time per 8 scheduled patient hours, plus +0.49 weekly visits, but no significant after-hours EHR-time change.
- Evidence is not yet strong enough to assume uniform burnout reduction or large capacity gains. Pediatric primary-care mixed-methods evidence found perceived benefits but no significant EHR-metric improvement.
- Note quality is promising but not risk-free: validated note-review studies report similar average quality to physician reference notes, but higher hallucination frequency in ambient notes and lower succinctness/accuracy on some dimensions. Human review remains necessary.
- Implementation/adoption determinants recur across AI evidence: workflow fit, clinician involvement, training, trust/explainability, governance, liability, privacy/security, specialty customization, and monitoring for bias/quality drift.
- Germany transferability: moderate for documentation burden and clinician acceptance mechanisms; lower for raw effect sizes because most evidence is US Epic/academic/ambulatory, relies on US billing/wRVU incentives, English-language encounters, and US consent/privacy norms. German deployment must address DSGVO/GDPR, MDR/AI Act classification, Betriebsrat/staff co-determination, German medical terminology, and integration with German PVS/KIS/ePA workflows.

## Structured bibliography: ambient AI scribes / documentation burden

1. Chen et al. “Changes in Clinician Time Expenditure and Visit Quantity With Adoption of Artificial Intelligence-Powered Scribes.” JAMA Network Open/JAMA, 2026. DOI: 10.1001/jamanetworkopen.2025.53233. URL: https://doi.org/10.1001/jamanetworkopen.2025.53233; PubMed: https://pubmed.ncbi.nlm.nih.gov/41920565/
   - Study type: Multisite longitudinal cohort, difference-in-differences; 5 US academic health systems; 8,581 clinicians, 1,809 AI-scribe adopters.
   - Outcomes/effect sizes: AI scribe adoption associated with 13.4 fewer EHR minutes per 8 scheduled patient hours (95% CI 9.1-17.7), 16.0 fewer documentation minutes (95% CI 13.7-18.3), and +0.49 weekly visits (95% CI 0.17-0.81). After-hours EHR time did not significantly change. Larger associations among primary care, APPs, female clinicians, and >=50% visit users.
   - Caveats: Observational; opt-in adoption at most sites; possible selection/confounding; US academic systems; follow-up during early rollout; “access/adoption” may not equal high use.
   - Germany transferability: Directionally relevant for ambulatory documentation-burden modeling; use effect sizes as optimistic/moderate scenario, not default. Weekly-visit and productivity effects need recalibration for EBM/GOÄ/DRG and German outpatient/inpatient workflows.

2. UCI Health team. “Evaluating ambient artificial intelligence documentation: effects on work efficiency, documentation burden, and patient-centered care.” JAMIA, 2026. DOI: 10.1093/jamia/ocaf180. URL: https://doi.org/10.1093/jamia/ocaf180; PubMed: https://pubmed.ncbi.nlm.nih.gov/41100159/
   - Study type: Quality-improvement pilot using Epic Signal metrics plus matched pre/post surveys; EHR metrics for 167 physicians; survey n=65.
   - Outcomes/effect sizes: Significant reductions in note-writing time despite longer notes; survey improvements in cognitive demand (P=.031) and documentation effort (P=.014); perceived improvements in clinical efficiency, patient-centered care, and usability.
   - Caveats: QI design, not randomized; abstract does not expose absolute time changes; possible response bias; Epic-specific metrics.
   - Germany transferability: Good for mechanisms and implementation parameters; raw magnitudes need German EHR/PVS/KIS validation and specialty adaptation.

3. “Hybrid Ambient Clinical Documentation and Physician Performance: Work Outside of Work, Documentation Delay, and Financial Productivity.” Journal of General Internal Medicine, 2026. DOI listed in PubMed metadata should be verified. PubMed: https://pubmed.ncbi.nlm.nih.gov/41249645/
   - Study type: Retrospective study; 181 clinicians across 14 adult primary-care practices; 66 voluntary hybrid ACD users; GenAI draft plus human virtual scribe.
   - Outcomes/effect sizes: Work-outside-work initially increased 32.1% by day 10, then decreased 41.7% by day 50 vs baseline. Delayed note closure odds reduced about 66% at day 10 and day 50. Financial productivity increased 12.1% by day 50.
   - Caveats: Hybrid human+AI scribe, so not pure ambient AI; voluntary enrollment; US primary care; wRVU productivity is US-specific; short follow-up.
   - Germany transferability: Useful for ramp-up dynamics and “hybrid human QA” scenarios; financial productivity metric is poorly transferable.

4. “Ambient Artificial Intelligence Scribes in Pediatric Primary Care: A Mixed Methods Study.” Applied Clinical Informatics, 2025. DOI: 10.1055/a-2625-0750. URL: https://doi.org/10.1055/a-2625-0750; PubMed: https://pubmed.ncbi.nlm.nih.gov/40456513/
   - Study type: 12-week mixed-methods study; 39 clinicians; pediatric primary-care network.
   - Outcomes/effect sizes: Used in 32% of eligible encounters (6,249/19,264). Reported benefits: reduced self-perceived cognitive burden 21/39, ability to finish sooner 18/39, enjoy clinical work more 18/39. No significant change in documentation time, after-hours EHR time, total EHR time, or visit closure rates. Patient experience/NPS unchanged.
   - Caveats: Small, short, specialty-specific; custom survey; adoption heterogeneity; pediatric preventive/behavioral visits were harder.
   - Germany transferability: Important counterweight for SimMed: do not assume benefit in all specialties. Pediatric and preventive-care content likely needs German templates and vocabulary.

5. “Assessing the quality of AI-generated clinical notes: validated evaluation of a large language model ambient scribe.” 2025. DOI: 10.1038/s41746-025-01622-1. URL: https://doi.org/10.1038/s41746-025-01622-1; PubMed: https://pubmed.ncbi.nlm.nih.gov/41199808/
   - Study type: Blinded note-quality evaluation using modified PDQI-9; 97 de-identified outpatient audio encounters across five specialties; 194 notes, 388 paired reviews.
   - Outcomes/effect sizes: Gold notes slightly higher overall quality (4.25/5 vs 4.20/5, P=.04), accuracy (P=.05), succinctness (P<.001), internal consistency (P=.004). Ambient notes higher in thoroughness (P<.001) and organization (P=.03). Hallucinations: 31% ambient vs 20% gold (P=.01). Reviewers nevertheless preferred ambient notes 47% vs 39%.
   - Caveats: Quality evaluation, not clinical outcome or workflow trial; hallucination definition and reviewer context matter; audio/transcript-only constraints.
   - Germany transferability: Strong for safety/governance: model should include mandatory clinician review, quality monitoring, and hallucination risk; German-language performance unproven.

6. “Using ChatGPT-4 to Create Structured Medical Notes From Audio Recordings of Physician-Patient Encounters: Comparative Study.” Journal of Medical Internet Research, 2024. DOI: 10.48550/arXiv.2308.02828. URL: https://doi.org/10.48550/arXiv.2308.02828; PubMed: https://pubmed.ncbi.nlm.nih.gov/38648636/
   - Study type: Comparative simulation study using simulated ambulatory encounters and SOAP-note generation.
   - Outcomes/effect sizes: Average 23.6 errors per clinical case; omissions 86%, additions 10.5%, incorrect facts 3.2%; only 52.9% of data elements reported correctly across all 3 replicates. Accuracy inversely correlated with transcript length and number of scorable data elements (P=.05 each).
   - Caveats: Simulated cases and generic ChatGPT-4, not necessarily current regulated ambient scribe products; still directly relevant to unreviewed documentation risk.
   - Germany transferability: Supports conservative safety assumptions, especially for complex or long German consultations.

7. “Evaluating the Application of Artificial Intelligence and Ambient Listening to Generate Medical Notes in Vitreoretinal Clinic Encounters.” Clinical Ophthalmology, 2025. PubMed: https://pubmed.ncbi.nlm.nih.gov/40491696/
   - Study type: Simulated vitreoretinal clinic dialogues; Gemini 1.0 Pro and ChatGPT 3.5; specialist review with PDQI-9.
   - Outcomes/effect sizes: AI documentation averaged 81.5% of total possible documentation-quality points. Transcription similarity higher for ChatGPT than Gemini (96.5% vs 90.6%, P<.01).
   - Caveats: Simulated, narrow specialty, older general models, not production workflow.
   - Germany transferability: Useful for specialty-configuration warning; ophthalmology terminology and structured findings need local validation.

8. “Enterprise-wide simultaneous deployment of ambient scribe technology: lessons learned from an academic health system.” JAMIA, 2026. PubMed: https://pubmed.ncbi.nlm.nih.gov/41175896/
   - Study type: Implementation report; >2,400 ambulatory and ED clinicians offered EHR-integrated ambient scribing.
   - Outcomes/effect sizes: By about 2.5 months, 20.1% of visit notes incorporated ambient scribing and 1,223 clinicians had used it. Survey respondents: 90.9% would be disappointed if access were lost; 84.7% positive training experience.
   - Caveats: Feasibility/satisfaction report; response rate 22.1%; no controlled clinical/economic outcomes in abstract.
   - Germany transferability: Relevant for rollout logistics and training assumptions; simultaneous deployment may be harder with fragmented German vendor landscape and co-determination requirements.

9. “Patient Attitudes Toward Ambient Voice Technology: Preimplementation Patient Survey in an Academic Medical Center.” JMIR Medical Informatics, 2025. PubMed: https://pubmed.ncbi.nlm.nih.gov/41308194/
   - Study type: Descriptive preimplementation survey; 1,893 respondents, 20% response rate.
   - Outcomes/effect sizes: Abstract indicates measurement of perceptions and comments but does not expose final percentages in visible abstract segment.
   - Caveats: Convenience sample, preimplementation attitudes, single US academic center; likely nonresponse bias.
   - Germany transferability: Use qualitatively for consent/transparency design; German patients may be more privacy-sensitive under DSGVO norms.

10. “Impact of artificial intelligence on electronic health record-related burnouts among healthcare professionals: systematic review.” Frontiers in Public Health, 2025. PubMed: https://pubmed.ncbi.nlm.nih.gov/40678636/; OSF protocol/materials: https://osf.io/pevfj
   - Study type: PRISMA systematic review, 2019-2025; PubMed/Scopus/Web of Science; 8 included studies.
   - Outcomes/effect sizes: Included ambient scribes, CDS, LLMs, NLP tools. Most studies reported positive outcomes such as decreased documentation time, workflow efficiency, and reduced burnout symptoms.
   - Caveats: Review itself emphasizes small samples, short follow-up, lack of control groups, and US/Canada dominance. Treat as promising but low-certainty evidence.
   - Germany transferability: High value as uncertainty framing; avoid model claims of proven burnout reduction without local trials.

## Structured bibliography: adjacent clinical AI adoption, implementation, and trust

11. “Inclusion of Clinicians in the Development and Evaluation of Clinical Artificial Intelligence Tools: A Systematic Literature Review.” Frontiers in Psychology, 2022. PubMed: https://pubmed.ncbi.nlm.nih.gov/35465567/
   - Study type: Systematic literature review; 45 articles; 24 design studies.
   - Outcomes/effect sizes: Clinician consultation occurred inconsistently and usually late in design: 82% of design studies solicited input at later stages; only 22% used human-centered approaches throughout. One-third reported clinician trust.
   - Caveats: Heterogeneous tools/settings; not specific to scribes; adoption outcomes indirect.
   - Germany transferability: Highly relevant: German deployments should include Ärzte, Pflege, Dokumentationsassistenz, Datenschutzbeauftragte, Betriebsrat, and patients early.

12. “Human Factors Influencing Trust in Healthcare Artificial Intelligence: Systematic Literature Review.” IISE Transactions on Occupational Ergonomics and Human Factors, 2026. PubMed: https://pubmed.ncbi.nlm.nih.gov/41674135/
   - Study type: Systematic literature review of trust factors.
   - Outcomes/effect sizes: PubMed summary identified human factors influencing trust; detailed effect sizes not visible in retrieved abstract.
   - Caveats: Trust literature often uses surveys/vignettes rather than real deployments.
   - Germany transferability: Relevant for acceptance parameters: explainability, accountability, training, professional autonomy, and auditability.

13. “Impact of large language model (ChatGPT) in healthcare: an umbrella review and evidence synthesis.” Journal of Biomedical Science, 2025. PubMed: https://pubmed.ncbi.nlm.nih.gov/40335969/
   - Study type: Umbrella review; 17 reviews (15 systematic reviews, 2 meta-analyses); searches through Feb 2024.
   - Outcomes/effect sizes: No meta-analysis due heterogeneity. AMSTAR-2 quality: 5 moderate-quality and 12 low-quality reviews. Major themes: diagnosis/decision-making, education, writing/review support; accuracy, ethical, legal concerns.
   - Caveats: Evidence base largely early ChatGPT studies, many low-quality reviews, task heterogeneity.
   - Germany transferability: Supports cautious LLM adoption; useful for broad SimMed adoption curves but not for quantitative documentation effect sizes.

14. “The Effectiveness of Artificial Intelligence Conversational Agents in Health Care: Systematic Review.” Journal of Medical Internet Research, 2020. PubMed: https://pubmed.ncbi.nlm.nih.gov/33090118/
   - Study type: Systematic review; 31 studies of unconstrained NLP conversational agents.
   - Outcomes/effect sizes: Usability/satisfaction generally positive or mixed (27/30 and 26/31); effectiveness positive or mixed in 23/30 studies.
   - Caveats: Many studies limited quality; broad agents, not ambient scribes; need cost-effectiveness/privacy/security research.
   - Germany transferability: Useful for patient-facing AI acceptance and usability priors, but not direct for clinician documentation.

15. “Use and Control of Artificial Intelligence in Patients Across the Medical Workflow: Single-Center Questionnaire Study of Patient Perspectives.” JMIR Medical Informatics, 2021. PubMed: https://pubmed.ncbi.nlm.nih.gov/33595451/
   - Study type: Single-center patient questionnaire; 229 imaging patients.
   - Outcomes/effect sizes: Patients favored physicians over AI for nearly all clinical tasks. In disagreement scenarios, preferred physician diagnosis/treatment planning over AI: 96.2% and 94.8% respectively. Physician-supervised AI much more acceptable than unsupervised AI for diagnosis (3.90 vs 1.64 confidence rating, P=.001) and therapy (3.77 vs 1.57, P=.001).
   - Caveats: Imaging-center sample; early-pandemic 2020 context; not Germany-specific unless institution location is verified separately.
   - Germany transferability: Strong qualitative implication: keep AI clinician-supervised and transparent.

16. “Artificial Intelligence to support ethical decision-making for incapacitated patients: a survey among German anesthesiologists and internists.” BMC Medical Ethics, 2024. PubMed: https://pubmed.ncbi.nlm.nih.gov/39026308/
   - Study type: German physician survey; 200 anesthesiologists + 200 internists sampled.
   - Outcomes/effect sizes: Respondents were hesitant toward AI-driven preference prediction, citing loss of individuality/humanity, lack of explicability, and doubts AI can encompass ethical deliberation. More positive toward Clinical Ethics Support Services; among those without CESS access, 91.8% wanted CESS.
   - Caveats: Specific to ethics/preference prediction, not documentation; descriptive survey; response details require full text.
   - Germany transferability: Direct German evidence that high-stakes AI needs explainability, human oversight, and role clarity.

## Modeling implications / suggested conservative parameterization

- Ambient scribe documentation-time reduction: use scenario bands rather than a point estimate. Conservative: 0-5 min saved per 8 scheduled patient hours or no metric change in some specialties; moderate: 5-15 min saved; optimistic/high-use ambulatory: around 13-16 min saved per 8 scheduled patient hours based on multisite cohort.
- After-hours work: do not assume automatic reduction; largest multisite cohort found no significant after-hours EHR-time change, while hybrid ACD found delayed improvement after initial worsening.
- Visit throughput: if modeled, keep modest: about +0.5 weekly visits per clinician in US cohort; transfer to Germany uncertain.
- Burnout/cognitive burden: model as perceived burden reduction with low-to-moderate evidence confidence, not proven burnout-outcome reduction.
- Safety/quality: require human sign-off; include nonzero hallucination/omission risk; risk likely grows with long, complex, multilingual, or specialty-dense encounters.
- Adoption curve modifiers: training quality, workflow integration, specialty fit, clinician trust, privacy/legal clearance, patient consent, and local language/template performance.
