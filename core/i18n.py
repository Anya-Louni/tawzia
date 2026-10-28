"""
core/i18n.py
------------
Français d'abord, anglais et arabe en bascule (brief §0.6). L'arabe passe
l'interface de droite à gauche.

Couverture actuelle : la navigation (espaces et écrans), la barre « Demander à
Tawzia », la boîte de décisions et le guichet salarié. Les écrans de détail
restent en français pour l'instant ; une clé absente retombe sur le français,
jamais sur un vide.
"""

from __future__ import annotations

import streamlit as st

LANGS = {"fr": "FR", "en": "EN", "ar": "ع"}

T = {
    # Espaces
    "Décisions": ("Decisions", "القرارات"),
    "Personnel": ("People", "الموظفون"),
    "Planning": ("Planning", "التخطيط"),
    "Recrutement": ("Hiring", "التوظيف"),
    "Paie & déclarations": ("Payroll & filings", "الأجور والتصريحات"),
    "Réglages": ("Settings", "الإعدادات"),
    # Écrans
    "Boîte de décisions": ("Decision inbox", "صندوق القرارات"),
    "Guichet salarié": ("Employee desk", "شباك الموظف"),
    "Employés": ("Employees", "الموظفون"),
    "Demandes & présence": ("Requests & attendance", "الطلبات والحضور"),
    "Compétences & mobilité": ("Skills & mobility", "الكفاءات والتنقل"),
    "Rétention": ("Retention", "الاحتفاظ بالموظفين"),
    "Planning de la semaine": ("This week's schedule", "جدول الأسبوع"),
    "Prévision de la demande": ("Demand forecast", "توقع الطلب"),
    "Planning & coût": ("Schedule & cost", "الجدول والتكلفة"),
    "Analyse sectorielle": ("Sector analysis", "تحليل القطاع"),
    "Aéroport": ("Airport", "المطار"),
    "Rédiger une offre": ("Write a job post", "تحرير عرض عمل"),
    "Canaux de sourcing": ("Sourcing channels", "قنوات الاستقطاب"),
    "Candidats": ("Candidates", "المترشحون"),
    "Intégration": ("Onboarding", "الإدماج"),
    "Paie": ("Payroll", "الأجور"),
    "Échéances & déclarations": ("Deadlines & filings", "الآجال والتصريحات"),
    "Détection d'anomalies": ("Anomaly detection", "كشف الأخطاء"),
    "Simulateur d'inspection": ("Inspection simulator", "محاكاة التفتيش"),
    "Veille Journal Officiel": ("Official Journal watch", "رصد الجريدة الرسمية"),
    "Demander à Tawzia": ("Ask Tawzia", "اسأل توزيع"),
    "Données de l'entreprise": ("Company data", "بيانات المؤسسة"),
    "Confidentialité": ("Privacy", "الخصوصية"),
    "Simulateur de scénarios": ("Scenario simulator", "محاكاة السيناريوهات"),
    "Tableau de bord": ("Dashboard", "لوحة القيادة"),
    "Preuves": ("Evidence", "الأدلة"),
    "Calendrier algérien": ("Algerian calendar", "التقويم الجزائري"),
    "Analyse économique": ("Business case", "التحليل الاقتصادي"),
    "Sources & hypothèses": ("Sources & assumptions", "المصادر والفرضيات"),
    # Barre de commande
    "ask_placeholder": ("Ask Tawzia: « attestation de travail for Amina Belkacem », « payroll », a question…",
                        "اسأل توزيع: « شهادة عمل لأمينة بلقاسم »، « الأجور »، أو سؤال…"),
    # Boîte de décisions
    "inbox_title": ("Decision inbox", "صندوق القرارات"),
    "inbox_sub": ("The agents reviewed {n} files, requests, payroll and deadlines: {k} tasks "
                  "prepared, all that is left is to sign. {left}",
                  "راجع الوكلاء {n} ملفًا والطلبات والأجور والآجال: {k} مهمة جاهزة، لم يبق إلا التوقيع. {left}"),
    "nothing_left": ("Nothing is waiting for you.", "لا شيء ينتظرك."),
    "n_waiting": ("<b>{n} decision(s)</b> waiting for you.", "<b>{n} قرار</b> في انتظارك."),
    "to_decide": ("To decide", "للبت"),
    "prepared": ("Work prepared by the agents", "عمل أعده الوكلاء"),
    "estimate": ("estimate: average manual time per task", "تقدير: متوسط الوقت اليدوي لكل مهمة"),
    "next_deadline": ("Next legal deadline", "الأجل القانوني القادم"),
    "to_validate": ("To approve", "للمصادقة"),
    "approve": ("Approve", "مصادقة"),
    "edit": ("Edit", "تعديل"),
    "reject": ("Reject", "رفض"),
    "approve_all": ("Approve all ({n})", "المصادقة على الكل ({n})"),
    "why": ("Why", "السبب"),
    "what_approval_does": ("See what approval triggers", "ما الذي تطلقه المصادقة"),
    "agents_did": ("What the agents did", "ما قام به الوكلاء"),
    "action_log": ("Action log", "سجل الإجراءات"),
    "brief": ("Summary for management", "ملخص للإدارة"),
    # Guichet
    "desk_title": ("Employee desk", "شباك الموظف"),
    "desk_sub": ("Work certificate, leave balance, payslip, leave request: employees write the way "
                 "they speak, in French, Arabic or Darija, and get their answer <b>without going to "
                 "the HR office</b>.",
                 "شهادة عمل، رصيد العطل، كشف الراتب، طلب عطلة: يكتب الموظف كما يتكلم، بالفرنسية أو "
                 "العربية أو الدارجة، ويتلقى الرد <b>دون المرور بمكتب الموارد البشرية</b>."),
    "logged_as": ("Signed in as", "متصل باسم"),
    "type_request": ("Type your request…", "اكتب طلبك…"),
}


def lang() -> str:
    return st.session_state.get("lang", "fr")


def t(key: str, **kw) -> str:
    """Le texte dans la langue choisie ; le français est la clé et le repli."""
    row = T.get(key)
    l = lang()
    text = (row[0] if l == "en" else row[1]) if row and l != "fr" else _FR.get(key, key)
    return text.format(**kw) if kw else text


# Les clés techniques (en minuscules) ont besoin de leur texte français.
_FR = {
    "ask_placeholder": "Demander à Tawzia : « attestation de travail pour Amina Belkacem », « paie », une question…",
    "inbox_title": "Boîte de décisions",
    "inbox_sub": "Les agents ont passé en revue {n} dossiers, les demandes, la paie et les "
                 "échéances : {k} tâches préparées, il ne reste qu'à signer. {left}",
    "nothing_left": "Rien ne vous attend.",
    "n_waiting": "<b>{n} décision(s)</b> vous attend(ent).",
    "to_decide": "À décider", "prepared": "Travail préparé par les agents",
    "estimate": "estimation : temps manuel moyen par tâche",
    "next_deadline": "Prochaine échéance légale", "to_validate": "À valider",
    "approve": "Approuver", "edit": "Modifier", "reject": "Rejeter",
    "approve_all": "Tout approuver ({n})", "why": "Pourquoi",
    "what_approval_does": "Voir ce que l'approbation déclenche",
    "agents_did": "Ce que les agents ont fait", "action_log": "Journal des actions",
    "brief": "Résumé pour la direction", "desk_title": "Guichet salarié",
    "desk_sub": "Attestation de travail, solde de congés, bulletin, demande de congé : le "
                "salarié écrit comme il parle, en français, en arabe ou en darija, et reçoit "
                "sa réponse <b>sans passer par le bureau RH</b>.",
    "logged_as": "Connecté en tant que", "type_request": "Écrivez votre demande…",
}


def rtl_css() -> str:
    """En arabe, la page entière passe de droite à gauche."""
    if lang() != "ar":
        return ""
    return ("<style>[data-testid='stMain'] { direction: rtl; } "
            "[data-testid='stMain'] [data-testid='stDataFrame'] { direction: ltr; }</style>")


if __name__ == "__main__":
    st.session_state["lang"] = "ar"
    assert t("Paie") == "الأجور" and t("approve") == "مصادقة"
    st.session_state["lang"] = "fr"
    assert t("Paie") == "Paie" and t("approve") == "Approuver"
    assert t("n_waiting", n=3).startswith("<b>3")
    assert t("inconnu") == "inconnu"
    print("  langues : ok")
