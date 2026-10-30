# Kavach SOP rules catalogue

**Source:** [Government-hosted SOP for NCRP-CFCFRMS, Custody, Restoration of Money and Grievance Redressal](https://cdnbbsr.s3waas.gov.in/s3ec03936824c0191953647ec609b4f49b/uploads/2026/06/2026061955.pdf), dated 02.01.2026, 98 numbered pages (the PDF viewer reports 100 pages because of cover/scan pages). Source reviewed 2026-10-29. These rules are an engineering aid, not legal advice.

| Rule ID | Paragraph | Scope / required facts | Responsible party / trigger | Prototype treatment |
|---|---|---|---|---|
| `PA-ESCROW-9.5.i` | 9.5(i) | Reported funds remain in a PA escrow or pool account and have not settled to the merchant; amount and intended beneficiary are identified. | PA/intermediary; CFCFRMS notice received by PA. | Hold reported amount and update intended-beneficiary details. Requires source evidence for fund location; otherwise `Unknown`. |
| `PA-SETTLED-9.5.ii` | 9.5(ii) | Goods/services delivered and amount settled to merchant bank account; settlement record exists. | PA/intermediary uploads settlement transactions/details; affected holder follows bank-side path. | Distinct from escrow route. It does not assume the PA can itself release or adjudicate merchant-bank funds. |
| `BANK-HOLD-10.1` | 10.1(a)–(f) | CFCFRMS amount hold contested by affected account holder; bank complaint date is known. | Affected person approaches bank; bank performs CDD/EDD and, if satisfied, submits GRM grievance within 7 calendar days of the bank complaint. | Track complaint-to-bank and bank-to-module events separately. IO/Police Officer and DGO process remains human-led. |
| `SUSPENSION-SEIZURE-10.2` | 10.2(a)–(h) | Suspension of digital banking services or seizure based on CFCFRMS information; action document is reviewed. | Affected person approaches bank; bank submits grievance within 7 calendar days of complaint. Issuing IO/Police Officer, DGO and SGO have distinct review stages. | A different route from an amount-only hold. Does not declare the action unlawful or promise restoration. |
| `PA-REPEAT-UPI-9.5.iv` | 9.5(iv) | A single UPI ID/account is reported in multiple CFCFRMS cases. | TPAP/PA carries out EDD; account may be suspended and UPI ID escalated to linked bank. | SQL count is a review signal only. UI masks identities; no guilt conclusion. |

## Clock interpretation and unresolved text

- SOP para 10.1(a) says the bank/FI should submit a grievance at the earliest and no later than **7 calendar days from the day the aggrieved person complains to the bank**. Para 10.2(b) uses the day the account holder/aggrieved person complains. A voice note or first report to Kavach is not this event.
- Kavach tracks `bank_grievance_received` separately from `bank_submission_to_grievance_module`. The 7-day clock starts from the former. The GRM submission event is not inferred from a draft or from merchant contact.
- Para 10.1(f), pages 39–40, describes 90 calendar days from the grievance **being submitted by the bank**. Annexure I, page 61, includes notice-template wording for 90 calendar days from the **date the amount was put on hold**. These are different anchors. Kavach displays both, labels them separately, requires confirmation, and blocks automated breach conclusions.
- Dates sourced only from a merchant statement are `Merchant-reported — indicative`. The built-in demo trigger is explicitly `SYNTHETIC / SIMULATED`, not an actual bank/GRM receipt.
- The underlying 15-day response/review and 2-day follow-up stages are human/authority actions. The prototype records them only when a corresponding event is entered; it does not infer decisions.

## Notice checks

The SOP complaint-registration description gives a 14-digit acknowledgement format beginning with `2` for portal complaints (para 6.1) and beginning with `3` for the 1930 flow (para 6.2). Kavach checks that shape as a format check only; it does not authenticate an acknowledgement. Annexure II is a Section 106(1) BNSS notice format; the prototype requests human review of action documents and does not claim to validate every statutory notice requirement.

## Sources

- [Official SOP PDF](https://cdnbbsr.s3waas.gov.in/s3ec03936824c0191953647ec609b4f49b/uploads/2026/06/2026061955.pdf)
- Paragraph 9.5(i)–(iv): PDF pages 30–32.
- Paragraph 10.1(a)–(f): PDF pages 38–40.
- Paragraph 10.2(a)–(h): PDF pages 40–43.
- Complaint acknowledgement formats: paras 6.1 and 6.2, PDF pages 16 and 19.
- Section 106 BNSS notice template: Annexure II, PDF pages 61–62.
