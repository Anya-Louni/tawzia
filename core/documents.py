"""
core/documents.py
-----------------
The documents the platform issues: a bilingual French/Arabic payslip, as
printable HTML (the browser saves it as PDF and handles Arabic right-to-left
layout, which a PDF generator without an Arabic shaping engine does badly). The
payslip stays French and Arabic: those are the languages of Algerian payroll.

Every document carries a verification code: a short fingerprint of its
content. The same content gives the same code; one changed figure gives another.
The public verification page will read this code.
"""

from __future__ import annotations

import hashlib
import html

_MONTHS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre")
_MONTHS_AR = ("جانفي", "فيفري", "مارس", "أفريل", "ماي", "جوان", "جويلية",
              "أوت", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")


def verification_code(text: str) -> str:
    """TZ-XXXX-XXXX: truncated SHA-256 fingerprint of the document content."""
    h = hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
    return f"TZ-{h[:4]}-{h[4:8]}"


def _n(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ")


def payslip_html(emp, b: dict, year: int, month: int, company: str) -> str:
    """One month's payslip, from payroll_dz.pay_breakdown()."""
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(l['label'])}</td><td class=n>{_n(l['amount'])}</td>"
        f"<td class=ar>{e(l['label_ar'])}</td></tr>" for l in b["lines"])
    body = (
        f"{company}|{emp.emp_id}|{year}-{month:02d}|{b['gross']}|{b['cnas_employee']}"
        f"|{b['irg']}|{b['net']}|{b['config_version']}")
    code = verification_code(body)
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Bulletin {e(emp.name)} {month:02d}/{year}</title>
<style>
 body{{font-family:Inter,Arial,sans-serif;color:#0A2540;max-width:760px;margin:28px auto;padding:0 16px}}
 h1{{font-size:20px;margin:0}} .ar{{direction:rtl;text-align:right;font-family:'Noto Naskh Arabic',Tahoma,sans-serif}}
 table{{width:100%;border-collapse:collapse;margin:14px 0}} td,th{{padding:7px 8px;border-bottom:1px solid #E2E8F0;font-size:13px}}
 .n{{text-align:right;font-variant-numeric:tabular-nums}} .tot td{{font-weight:700;border-top:2px solid #0A2540}}
 .head{{display:flex;justify-content:space-between;gap:16px}} .muted{{color:#5A6B80;font-size:12px}}
 .code{{margin-top:22px;padding:10px 12px;border:1px dashed #94A3B8;border-radius:8px;font-size:12px}}
 @media print{{.code{{break-inside:avoid}}}}
</style></head><body>
<div class=head><div><h1>Bulletin de paie</h1><div class=muted>{e(company)}</div></div>
<div class=ar><h1>كشف الراتب</h1><div class=muted>{_MONTHS_AR[month - 1]} {year}</div></div></div>
<p><b>{e(emp.name)}</b> · matricule {e(emp.emp_id)} · {_MONTHS_FR[month - 1]} {year}</p>
<table><tr><th>Rubrique</th><th class=n>Montant (DA)</th><th class=ar>البيان</th></tr>
{rows}
<tr class=tot><td>Brut</td><td class=n>{_n(b['gross'])}</td><td class=ar>الأجر الإجمالي</td></tr>
<tr><td>Retenue CNAS salariale</td><td class=n>−{_n(b['cnas_employee'])}</td><td class=ar>اقتطاع الضمان الاجتماعي</td></tr>
<tr><td>Base imposable</td><td class=n>{_n(b['taxable'])}</td><td class=ar>الوعاء الخاضع للضريبة</td></tr>
<tr><td>IRG retenu</td><td class=n>−{_n(b['irg'])}</td><td class=ar>الضريبة على الدخل الإجمالي</td></tr>
<tr class=tot><td>Net à payer</td><td class=n>{_n(b['net'])}</td><td class=ar>الصافي للدفع</td></tr>
</table>
<p class=muted>Charge patronale CNAS : {_n(b['employer_cnas'])} DA · coût total employeur
{_n(b['employer_cost'])} DA · règles {e(b['config_version'])}</p>
<div class=code>Code de vérification <b>{code}</b> · رمز التحقق<br>
Document émis par Tawzia. Données de démonstration.</div>
</body></html>"""


if __name__ == "__main__":
    import datetime as dt
    from . import hr, payroll_dz
    emp = hr.Employee("E1", "Amina Belkacem", "sorter", "Alger", dt.date(2023, 3, 1))
    b = payroll_dz.pay_breakdown({"base": 60_000, "panier": 3_000})
    doc = payslip_html(emp, b, 2026, 10, "Démo Handling & Logistique")
    assert _n(b["net"]) in doc and "كشف الراتب" in doc and "TZ-" in doc
    assert verification_code("a") == verification_code("a") != verification_code("b")
    print("  bilingual payslip: ok")
