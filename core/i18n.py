"""
core/i18n.py
------------
English by default, French and Arabic as switches. Arabic turns the page
right to left.

Coverage: the navigation (spaces and screens), the "Ask Tawzia" bar, the
decision inbox, the employee desk and agent names. A missing key falls back to
English, then to the key itself, never to an empty string.
"""

from __future__ import annotations

import streamlit as st

LANGS = {"en": "EN", "fr": "FR", "ar": "AR"}
DEFAULT = "en"

# key -> (English, French, Arabic). Page titles are the internal ids (French)
# used by the navigation, so they are keys here too.
T = {
    # Spaces
    "Décisions": ("Decisions", "Décisions", "القرارات"),
    "Personnel": ("People", "Personnel", "الموظفون"),
    "Planning": ("Planning", "Planning", "التخطيط"),
    "Recrutement": ("Hiring", "Recrutement", "التوظيف"),
    "Paie & déclarations": ("Payroll & filings", "Paie & déclarations", "الأجور والتصريحات"),
    "Réglages": ("Settings", "Réglages", "الإعدادات"),
    # Screens
    "Boîte de décisions": ("Decision inbox", "Boîte de décisions", "صندوق القرارات"),
    "Guichet salarié": ("Employee desk", "Guichet salarié", "شباك الموظف"),
    "Employés": ("Employees", "Employés", "الموظفون"),
    "Demandes & présence": ("Requests & attendance", "Demandes & présence", "الطلبات والحضور"),
    "Compétences & mobilité": ("Skills & mobility", "Compétences & mobilité", "الكفاءات والتنقل"),
    "Rétention": ("Retention", "Rétention", "الاحتفاظ بالموظفين"),
    "Planning de la semaine": ("This week's schedule", "Planning de la semaine", "جدول الأسبوع"),
    "Prévision de la demande": ("Demand forecast", "Prévision de la demande", "توقع الطلب"),
    "Planning & coût": ("Schedule & cost", "Planning & coût", "الجدول والتكلفة"),
    "Analyse sectorielle": ("Sector analysis", "Analyse sectorielle", "تحليل القطاع"),
    "Aéroport": ("Airport", "Aéroport", "المطار"),
    "Rédiger une offre": ("Write a job post", "Rédiger une offre", "تحرير عرض عمل"),
    "Canaux de sourcing": ("Sourcing channels", "Canaux de sourcing", "قنوات الاستقطاب"),
    "Candidats": ("Candidates", "Candidats", "المترشحون"),
    "Intégration": ("Onboarding", "Intégration", "الإدماج"),
    "Paie": ("Payroll", "Paie", "الأجور"),
    "Échéances & déclarations": ("Deadlines & filings", "Échéances & déclarations", "الآجال والتصريحات"),
    "Détection d'anomalies": ("Anomaly detection", "Détection d'anomalies", "كشف الأخطاء"),
    "Simulateur d'inspection": ("Inspection simulator", "Simulateur d'inspection", "محاكاة التفتيش"),
    "Veille Journal Officiel": ("Official Journal watch", "Veille Journal Officiel", "رصد الجريدة الرسمية"),
    "Demander à Tawzia": ("Ask Tawzia", "Demander à Tawzia", "اسأل توزيع"),
    "PDF vers texte IA": ("PDF to AI text", "PDF vers texte IA", "تحويل PDF إلى نص"),
    "Données de l'entreprise": ("Company data", "Données de l'entreprise", "بيانات المؤسسة"),
    "Confidentialité": ("Privacy", "Confidentialité", "الخصوصية"),
    "Simulateur de scénarios": ("Scenario simulator", "Simulateur de scénarios", "محاكاة السيناريوهات"),
    "Tableau de bord": ("Dashboard", "Tableau de bord", "لوحة القيادة"),
    "Preuves": ("Evidence", "Preuves", "الأدلة"),
    "Calendrier algérien": ("Algerian calendar", "Calendrier algérien", "التقويم الجزائري"),
    "Analyse économique": ("Business case", "Analyse économique", "التحليل الاقتصادي"),
    "Sources & hypothèses": ("Sources & assumptions", "Sources & hypothèses", "المصادر والفرضيات"),
    # Agents (internal ids are French)
    "agent:Présence": ("Attendance", "Présence", "الحضور"),
    "agent:Paie": ("Payroll", "Paie", "الأجور"),
    "agent:Déclarations": ("Filings", "Déclarations", "التصريحات"),
    "agent:Conformité": ("Compliance", "Conformité", "المطابقة"),
    "agent:Rétention": ("Retention", "Rétention", "الاحتفاظ"),
    "agent:Recrutement": ("Hiring", "Recrutement", "التوظيف"),
    "agent:Guichet": ("Employee desk", "Guichet", "الشباك"),
    "agent:Intégration": ("Onboarding", "Intégration", "الإدماج"),
    "agent:Planning": ("Planning", "Planning", "التخطيط"),
    "agent:Affiliations": ("Affiliations", "Affiliations", "الانتساب"),
    "agent:ANEM": ("ANEM", "ANEM", "الوكالة الوطنية للتشغيل"),
    # Command bar
    "ask_placeholder": ("Ask Tawzia: « work certificate for Amina Belkacem », « payroll », a question…",
                        "Demander à Tawzia : « attestation de travail pour Amina Belkacem », « paie », une question…",
                        "اسأل توزيع: « شهادة عمل لأمينة بلقاسم »، « الأجور »، أو سؤال…"),
    # Inbox
    "agents_running": ("The agents are going over today's files…", "Les agents passent sur les dossiers du jour…",
                       "الوكلاء يراجعون ملفات اليوم…"),
    "today_h": ("{n} decisions are waiting, <em>{u} urgent</em>", "{n} décisions vous attendent, <em>{u} urgentes</em>",
                "{n} قرارًا في انتظارك، <em>{u} عاجلة</em>"),
    "today_h0": ("{n} decisions are waiting", "{n} décisions vous attendent", "{n} قرارًا في انتظارك"),
    "today_none": ("Inbox clear. Nothing is waiting for you.", "Boîte vide. Rien ne vous attend.",
                   "الصندوق فارغ. لا شيء ينتظرك."),
    "today_s": ("{d}. The agents reviewed {n} employee files, requests, payroll and deadlines and prepared {h} h of work. Read the why, then approve.",
                "{d}. Les agents ont passé en revue {n} dossiers, les demandes, la paie et les échéances, et préparé {h} h de travail. Lisez le pourquoi, puis approuvez.",
                "{d}. راجع الوكلاء {n} ملفًا والطلبات والأجور والآجال وأعدوا {h} ساعة من العمل. اقرأ السبب ثم صادق."),
    "cleared": ("{c} of {n} cleared today", "{c} sur {n} traitées aujourd'hui", "{c} من {n} تمت معالجتها اليوم"),
    "hours_est": ("hours are an estimate", "heures estimées", "الساعات تقديرية"),
    "agents_prepared": ("What each agent prepared", "Ce que chaque agent a préparé", "ما أعده كل وكيل"),
    "filter": ("Filter", "Filtrer", "تصفية"),
    "f_all": ("All · {n}", "Tout · {n}", "الكل · {n}"),
    "f_urgent": ("Urgent · {n}", "Urgent · {n}", "عاجل · {n}"),
    "inbox_empty": ("Inbox clear. The agents will write as soon as a decision comes back to you.",
                    "Boîte vide. Les agents vous écriront dès qu'une décision vous revient.",
                    "الصندوق فارغ. سيكتب لك الوكلاء عند ظهور قرار جديد."),
    "n_replies": ("{n} replies", "{n} réponses", "{n} ردود"),
    "batch_t": ("{n} compliant requests, replies ready", "{n} demandes conformes, réponses prêtes",
                "{n} طلبات مطابقة، الردود جاهزة"),
    "batch_why": ("Enough leave balance, notice respected, no forecast peak on the requested dates.",
                  "Solde suffisant, préavis respecté, aucun pic de charge prévu sur les dates demandées.",
                  "رصيد كافٍ، مهلة محترمة، ولا ذروة متوقعة في التواريخ المطلوبة."),
    "see_replies": ("See the replies", "Voir les réponses", "عرض الردود"),
    "approve_n": ("Approve all {n}", "Approuver les {n}", "المصادقة على {n}"),
    "edit_one_by_one": ("Review one by one", "Modifier une par une", "مراجعة واحدًا واحدًا"),
    "urgent": ("URGENT", "URGENT", "عاجل"),
    "why": ("Why", "Pourquoi", "السبب"),
    "what_approval_does": ("What approval triggers", "Ce que l'approbation déclenche", "ما الذي تطلقه المصادقة"),
    "approve": ("Approve", "Approuver", "مصادقة"),
    "edit": ("Edit", "Modifier", "تعديل"),
    "reject": ("Reject", "Rejeter", "رفض"),
    "approve_all": ("Approve everything ({n})", "Tout approuver ({n})", "المصادقة على الكل ({n})"),
    "more_cards": ("{n} more, less urgent, follow.", "{n} autres, moins urgentes, suivent.", "{n} أخرى أقل استعجالًا."),
    "hire_launched": ("Hire approved: {n} tasks launched.", "Embauche approuvée : {n} tâches lancées.",
                      "تمت المصادقة على التوظيف: أُطلقت {n} مهمة."),
    "see_file": ("See the file", "Voir le dossier", "عرض الملف"),
    "next_deadline": ("Next legal deadline", "Prochaine échéance légale", "الأجل القانوني القادم"),
    "overdue": ("Overdue, settle it now", "En retard, à régulariser", "متأخر، يجب التسوية"),
    "in_days": ("Due in {n} day(s)", "Dans {n} jour(s)", "بعد {n} يوم"),
    "open_filing": ("Open the prepared filing", "Ouvrir le brouillon préparé", "فتح المسودة"),
    "brief": ("Summary for management", "Résumé pour la direction", "ملخص للإدارة"),
    "write_brief": ("Write the summary", "Rédiger le résumé", "كتابة الملخص"),
    "brief_hint": ("Five lines written from the agents' facts only.", "Cinq lignes écrites à partir des seuls faits relevés.",
                   "خمسة أسطر من وقائع الوكلاء فقط."),
    "no_ai_key": ("No AI key configured: here are the raw facts.", "Aucune clé IA configurée : voici les faits bruts.",
                  "لا يوجد مفتاح ذكاء اصطناعي: هذه الوقائع الخام."),
    "action_log": ("Action log", "Journal des actions", "سجل الإجراءات"),
    "approved": ("approved", "approuvé", "تمت المصادقة"),
    "rejected": ("rejected", "rejeté", "مرفوض"),
    "log_empty": ("Nothing yet.", "Rien encore.", "لا شيء بعد."),
    "log_note": ("Every decision is logged: who, what, when. Nothing leaves without a human click.",
                 "Chaque décision est tracée : qui, quoi, quand. Rien ne part sans un clic humain.",
                 "كل قرار مسجل: من، ماذا، متى. لا شيء يُرسل دون نقرة بشرية."),
    "undo": ("Undo my decisions", "Annuler mes décisions", "التراجع عن قراراتي"),
    "you": ("You", "Vous", "أنت"),
    "cert_signed": ("{name}, your work certificate is signed. Here it is.", "{name}, votre attestation est signée. La voici.",
                    "{name}، شهادة العمل موقعة. ها هي."),
    # Employee desk
    "desk_title": ("Employee desk", "Guichet salarié", "شباك الموظف"),
    "desk_sub": ("Work certificate, leave balance, payslip, leave request: employees write the way they speak, in French, Arabic or Darija, and get their answer <b>without going to the HR office</b>.",
                 "Attestation de travail, solde de congés, bulletin, demande de congé : le salarié écrit comme il parle, en français, en arabe ou en darija, et reçoit sa réponse <b>sans passer par le bureau RH</b>.",
                 "شهادة عمل، رصيد العطل، كشف الراتب، طلب عطلة: يكتب الموظف كما يتكلم، بالفرنسية أو العربية أو الدارجة، ويتلقى الرد <b>دون المرور بمكتب الموارد البشرية</b>."),
    "logged_as": ("Signed in as", "Connecté en tant que", "متصل باسم"),
    "type_request": ("Type your request…", "Écrivez votre demande…", "اكتب طلبك…"),
}

_NAMES = {"en": "English", "fr": "French", "ar": "Arabic"}


def lang() -> str:
    return st.session_state.get("lang") or DEFAULT


def lang_name() -> str:
    return _NAMES[lang()]


def t(key: str, **kw) -> str:
    """The text in the chosen language; English, then the key, as fallbacks."""
    row = T.get(key)
    text = key.split(":", 1)[-1] if row is None else row[("en", "fr", "ar").index(lang())]
    return text.format(**kw) if kw else text


def rtl_css() -> str:
    """In Arabic the whole page runs right to left."""
    if lang() != "ar":
        return ""
    return ("<style>[data-testid='stMain'] { direction: rtl; } "
            "[data-testid='stMain'] [data-testid='stDataFrame'] { direction: ltr; }</style>")


if __name__ == "__main__":
    st.session_state["lang"] = "ar"
    assert t("Paie") == "الأجور" and t("approve") == "مصادقة"
    st.session_state["lang"] = "fr"
    assert t("Paie") == "Paie" and t("approve") == "Approuver"
    st.session_state["lang"] = "en"
    assert t("Paie") == "Payroll" and t("agent:Présence") == "Attendance"
    assert t("f_all", n=3) == "All · 3" and t("unknown key") == "unknown key"
    assert all(len(v) == 3 for v in T.values())
    print("  languages: ok")
