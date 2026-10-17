"""Explanations. The LLM only ever sees the token (Applicant_XXXX), the decision and the reasons.

Engine:
  - IBM Granite through Ollama on the same server, when CLEARLOAN_OLLAMA_URL is set
  - built-in templates otherwise (and as a fallback if the LLM is slow or returns bad output)
"""
import json
import urllib.request

from . import config

LANG_NAMES = {"en": "English", "ar": "Arabic", "ur": "Urdu", "hi": "Hindi", "fr": "French"}


def money(n: float, lang: str = "en") -> str:
    text = f"{n:,.0f}"
    return text.replace(",", " ") if lang == "fr" else text   # French: 50 000


# ---------- Prompt

def build_prompt(token: str, result: dict, f: dict, language: str) -> str:
    reasons = "; ".join(
        f"{r['feature']} = {r['value']} ({r['direction']} risk, {r['impact']})" for r in result["top_reasons"])
    decision = "approved" if result["decision"] == "approved" else "not approved"
    return (
        "SYSTEM  You explain loan decisions in simple, kind words. Never invent facts. "
        "Address the applicant by their code. Answer as JSON: {\"explanation\": str, \"steps\": [str, str, str]}.\n"
        f"USER    {token} was {decision} for AED {money(f['loan_amount'])} "
        f"(risk {result['risk_score']}/100, limit {config.APPROVAL_LIMIT}).\n"
        f"        Top reasons: {reasons}.\n"
        f"        Write a short explanation in {LANG_NAMES[language]} and 3 steps to improve."
    )


def _ollama(prompt: str) -> dict | None:
    body = json.dumps({"model": config.GRANITE_MODEL, "prompt": prompt, "stream": False, "format": "json",
                       "options": {"temperature": 0.2}}).encode()
    req = urllib.request.Request(config.OLLAMA_URL.rstrip("/") + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT) as res:
            out = json.loads(json.loads(res.read())["response"])
        steps = [str(s) for s in out.get("steps", [])][:3]
        if isinstance(out.get("explanation"), str) and len(steps) == 3:
            return {"explanation": out["explanation"].strip(), "steps": steps}
    except Exception:   # network, timeout, bad JSON: fall back to the templates
        return None
    return None


# ---------- Templates (one entry per language)

T = {
    "en": {
        "hello": "Hello {name}, ",
        "approved": "good news: your loan of AED {amount} is approved. {good} Please keep paying on time.",
        "good": "Your monthly payments and your bills are in a healthy balance.",
        "rejected": "thank you for applying. For now, we can't approve a loan of AED {amount}. The main reason: {why}.{extra} "
                    "This is not a final answer: you can improve your chances, or ask a person to review your application.",
        "extra_first": " Because this is your first loan, we also have less information about you.",
        "why": {
            "payment_ratio": "your monthly payments cover only {pct}% of your monthly bills",
            "loan_amount": "the amount is large compared with your bills (about {months} months of bills)",
            "credit_history": "this is your first loan, so we have little information about you",
            "repayment_record": "you had {late} late payment(s) in the last 6 months",
            "other": "your overall profile is close to the limit",
        },
        "steps_ok": ["Keep paying your bills on time.", "Set up an automatic monthly payment.",
                     "Contact us if your income changes."],
        "max_loan": "Ask for a smaller amount: up to AED {loan} would be approved today.",
        "min_payment": "Pay more of your monthly bills: about AED {pay} a month ({pct}% of your bills) would be enough.",
        "combo": "Combine both: for example AED {loan} with monthly payments of about AED {pay}.",
        "smaller": "Ask for a smaller amount: the lower it is compared with your bills, the better.",
        "pay_more": "Pay more of your monthly bills. Paying more than 35% of them makes a big difference.",
        "first": "Come back after 3 months of on-time payments. We can then use the full model.",
        "late": "Avoid late payments for the next 3 months.",
    },
    "fr": {
        "hello": "Bonjour {name}, ",
        "approved": "bonne nouvelle : votre prêt de {amount} AED est accepté. {good} Continuez à payer à temps.",
        "good": "Vos paiements mensuels et vos factures sont bien équilibrés.",
        "rejected": "merci pour votre demande. Pour l'instant, nous ne pouvons pas accepter un prêt de {amount} AED. "
                    "La raison principale : {why}.{extra} Ce n'est pas une réponse définitive : vous pouvez améliorer "
                    "vos chances ou demander une révision par une personne.",
        "extra_first": " Comme c'est votre premier prêt, nous avons aussi moins d'informations sur vous.",
        "why": {
            "payment_ratio": "vos paiements mensuels ne couvrent que {pct} % de vos factures",
            "loan_amount": "le montant est élevé par rapport à vos factures (environ {months} mois de factures)",
            "credit_history": "c'est votre premier prêt, nous avons donc peu d'informations sur vous",
            "repayment_record": "vous avez eu {late} retard(s) de paiement sur les 6 derniers mois",
            "other": "votre profil global est proche de la limite",
        },
        "steps_ok": ["Continuez à payer vos factures à temps.", "Mettez en place un paiement mensuel automatique.",
                     "Contactez-nous si vos revenus changent."],
        "max_loan": "Demandez un montant plus petit : jusqu'à {loan} AED serait accepté aujourd'hui.",
        "min_payment": "Payez une plus grande part de vos factures : environ {pay} AED par mois ({pct} % de vos factures) suffirait.",
        "combo": "Combinez les deux : par exemple {loan} AED avec des paiements d'environ {pay} AED par mois.",
        "smaller": "Demandez un montant plus petit : plus il est faible par rapport à vos factures, mieux c'est.",
        "pay_more": "Payez une plus grande part de vos factures. Au-delà de 35 %, cela change beaucoup.",
        "first": "Revenez après 3 mois de paiements à temps. Nous pourrons alors utiliser le modèle complet.",
        "late": "Évitez tout retard de paiement pendant les 3 prochains mois.",
    },
    "ar": {
        "hello": "مرحباً {name}، ",
        "approved": "خبر سار: تمت الموافقة على قرضك بقيمة {amount} درهم. {good} يرجى الاستمرار في الدفع في الوقت المحدد.",
        "good": "دفعاتك الشهرية متوازنة مع فواتيرك.",
        "rejected": "شكراً لتقديم طلبك. لا يمكننا حالياً الموافقة على قرض بقيمة {amount} درهم. السبب الرئيسي: {why}.{extra} "
                    "هذا ليس قراراً نهائياً: يمكنك تحسين فرصك، أو طلب مراجعة طلبك من قِبل موظف.",
        "extra_first": " ولأن هذا قرضك الأول، لدينا معلومات أقل عنك.",
        "why": {
            "payment_ratio": "دفعاتك الشهرية تغطي {pct}% فقط من فواتيرك الشهرية",
            "loan_amount": "المبلغ كبير مقارنة بفواتيرك (حوالي {months} شهراً من الفواتير)",
            "credit_history": "هذا قرضك الأول، لذلك لدينا معلومات قليلة عنك",
            "repayment_record": "تأخرت في الدفع {late} مرة خلال الأشهر الستة الماضية",
            "other": "ملفك العام قريب من الحد المطلوب",
        },
        "steps_ok": ["استمر في دفع فواتيرك في الوقت المحدد.", "فعّل الدفع الشهري التلقائي.", "تواصل معنا إذا تغيّر دخلك."],
        "max_loan": "اطلب مبلغاً أصغر: حتى {loan} درهم يمكن الموافقة عليه اليوم.",
        "min_payment": "ادفع جزءاً أكبر من فواتيرك: حوالي {pay} درهم شهرياً ({pct}% من فواتيرك) سيكون كافياً.",
        "combo": "اجمع بين الأمرين: مثلاً {loan} درهم مع دفعات شهرية بحوالي {pay} درهم.",
        "smaller": "اطلب مبلغاً أصغر: كلما كان أقل مقارنة بفواتيرك كان أفضل.",
        "pay_more": "ادفع جزءاً أكبر من فواتيرك الشهرية. دفع أكثر من 35% منها يُحدث فرقاً كبيراً.",
        "first": "عُد بعد 3 أشهر من الدفع في الوقت المحدد، وعندها يمكننا استخدام النموذج الكامل.",
        "late": "تجنّب التأخر في الدفع خلال الأشهر الثلاثة القادمة.",
    },
    "ur": {
        "hello": "السلام علیکم {name}، ",
        "approved": "خوشخبری: آپ کا {amount} درہم کا قرض منظور ہو گیا ہے۔ {good} براہ کرم وقت پر ادائیگی جاری رکھیں۔",
        "good": "آپ کی ماہانہ ادائیگیاں اور بل اچھے توازن میں ہیں۔",
        "rejected": "درخواست دینے کا شکریہ۔ فی الحال ہم {amount} درہم کا قرض منظور نہیں کر سکتے۔ بنیادی وجہ: {why}۔{extra} "
                    "یہ حتمی جواب نہیں ہے: آپ اپنے امکانات بہتر بنا سکتے ہیں، یا کسی فرد سے اپنی درخواست کا جائزہ لینے کو کہہ سکتے ہیں۔",
        "extra_first": " چونکہ یہ آپ کا پہلا قرض ہے، ہمارے پاس آپ کے بارے میں معلومات بھی کم ہیں۔",
        "why": {
            "payment_ratio": "آپ کی ماہانہ ادائیگیاں آپ کے ماہانہ بلوں کا صرف {pct}% پورا کرتی ہیں",
            "loan_amount": "رقم آپ کے بلوں کے مقابلے میں زیادہ ہے (تقریباً {months} ماہ کے بل)",
            "credit_history": "یہ آپ کا پہلا قرض ہے، اس لیے ہمارے پاس آپ کے بارے میں کم معلومات ہیں",
            "repayment_record": "پچھلے 6 ماہ میں آپ کی {late} ادائیگیاں تاخیر سے ہوئیں",
            "other": "آپ کا مجموعی پروفائل حد کے قریب ہے",
        },
        "steps_ok": ["اپنے بل وقت پر ادا کرتے رہیں۔", "خودکار ماہانہ ادائیگی ترتیب دیں۔", "اگر آپ کی آمدنی بدلے تو ہم سے رابطہ کریں۔"],
        "max_loan": "کم رقم کی درخواست کریں: {loan} درہم تک آج منظور ہو سکتا ہے۔",
        "min_payment": "اپنے بلوں کا زیادہ حصہ ادا کریں: تقریباً {pay} درہم ماہانہ (بلوں کا {pct}%) کافی ہوگا۔",
        "combo": "دونوں کو ملائیں: مثلاً {loan} درہم کے ساتھ تقریباً {pay} درہم ماہانہ ادائیگی۔",
        "smaller": "کم رقم کی درخواست کریں: بلوں کے مقابلے میں جتنی کم ہو، اتنا بہتر۔",
        "pay_more": "اپنے ماہانہ بلوں کا زیادہ حصہ ادا کریں۔ 35% سے زیادہ ادا کرنا بڑا فرق ڈالتا ہے۔",
        "first": "3 ماہ تک وقت پر ادائیگی کے بعد دوبارہ آئیں۔ پھر ہم مکمل ماڈل استعمال کر سکیں گے۔",
        "late": "اگلے 3 ماہ تک ادائیگی میں تاخیر سے بچیں۔",
    },
    "hi": {
        "hello": "नमस्ते {name}, ",
        "approved": "अच्छी खबर: आपका {amount} दिरहम का ऋण स्वीकृत हो गया है। {good} कृपया समय पर भुगतान करते रहें।",
        "good": "आपके मासिक भुगतान और बिल अच्छे संतुलन में हैं।",
        "rejected": "आवेदन करने के लिए धन्यवाद। अभी हम {amount} दिरहम का ऋण स्वीकृत नहीं कर सकते। मुख्य कारण: {why}।{extra} "
                    "यह अंतिम उत्तर नहीं है: आप अपनी संभावनाएँ बेहतर कर सकते हैं, या किसी व्यक्ति से अपने आवेदन की समीक्षा करवा सकते हैं।",
        "extra_first": " क्योंकि यह आपका पहला ऋण है, हमारे पास आपके बारे में जानकारी भी कम है।",
        "why": {
            "payment_ratio": "आपके मासिक भुगतान आपके मासिक बिलों का केवल {pct}% ही चुकाते हैं",
            "loan_amount": "राशि आपके बिलों की तुलना में बड़ी है (लगभग {months} महीने के बिल)",
            "credit_history": "यह आपका पहला ऋण है, इसलिए हमारे पास आपके बारे में कम जानकारी है",
            "repayment_record": "पिछले 6 महीनों में आपके {late} भुगतान देर से हुए",
            "other": "आपकी कुल प्रोफ़ाइल सीमा के करीब है",
        },
        "steps_ok": ["अपने बिल समय पर चुकाते रहें।", "स्वचालित मासिक भुगतान सेट करें।", "अगर आपकी आय बदले तो हमसे संपर्क करें।"],
        "max_loan": "कम राशि माँगें: {loan} दिरहम तक आज स्वीकृत हो सकता है।",
        "min_payment": "अपने बिलों का अधिक हिस्सा चुकाएँ: लगभग {pay} दिरहम प्रति माह (बिलों का {pct}%) पर्याप्त होगा।",
        "combo": "दोनों को मिलाएँ: जैसे {loan} दिरहम, लगभग {pay} दिरहम मासिक भुगतान के साथ।",
        "smaller": "कम राशि माँगें: बिलों की तुलना में जितनी कम हो, उतना अच्छा।",
        "pay_more": "अपने मासिक बिलों का अधिक हिस्सा चुकाएँ। 35% से अधिक चुकाने से बड़ा फर्क पड़ता है।",
        "first": "3 महीने समय पर भुगतान के बाद फिर आएँ। तब हम पूरा मॉडल इस्तेमाल कर सकेंगे।",
        "late": "अगले 3 महीनों तक भुगतान में देरी से बचें।",
    },
}


def _why(lang: str, result: dict, f: dict) -> tuple[str, bool]:
    t = T[lang]["why"]
    raising = [r for r in result["top_reasons"] if r["direction"] == "raises"]
    main = raising[0] if raising else None
    pct = round((f["avg_payment"] / f["avg_bill"]) * 100) if f["avg_bill"] else 100
    months = round(f["loan_amount"] / max(f["avg_bill"], 500))
    if not main or main["feature"] not in t:
        return t["other"], False
    text = t[main["feature"]].format(pct=pct, months=months, late=main["value"])
    # Add the "first loan" sentence only when it is not already the main reason
    first_extra = not f["credit_history"] and main["feature"] != "credit_history"
    return text, first_extra


def template_explanation(lang: str, token: str, result: dict, f: dict) -> str:
    t = T[lang]
    amount = money(f["loan_amount"], lang)
    if result["decision"] == "approved":
        body = t["approved"].format(amount=amount, good=t["good"])
    else:
        why, first_extra = _why(lang, result, f)
        body = t["rejected"].format(amount=amount, why=why, extra=t["extra_first"] if first_extra else "")
    return t["hello"].format(name=token) + body


def template_steps(lang: str, result: dict, f: dict, cf: dict) -> list[str]:
    t = T[lang]
    if result["decision"] == "approved":
        return list(t["steps_ok"])
    steps = []
    if cf["max_loan"]:
        steps.append(t["max_loan"].format(loan=money(cf["max_loan"], lang)))
    if cf["min_payment"]:
        pct = round(cf["min_payment"] / f["avg_bill"] * 100) if f["avg_bill"] else 100
        steps.append(t["min_payment"].format(pay=money(cf["min_payment"], lang), pct=pct))
    if cf["combo"]:
        steps.append(t["combo"].format(loan=money(cf["combo"]["loan"], lang), pay=money(cf["combo"]["payment"], lang)))
    # Fill up with general advice the numbers above don't already cover
    if not cf["max_loan"]:
        steps.append(t["smaller"])
    if not cf["min_payment"]:
        steps.append(t["pay_more"])
    return steps[:2] + [t["first"] if not f["credit_history"] else t["late"]]


def appeal_draft(app_id: str, first_name: str) -> str:
    return (f"Dear ClearLoan team,\nI would like a person to review my application {app_id}.\n"
            "[Add your reason here, for example a new job or a higher salary.]\n"
            f"I can share documents to support this.\nThank you,\n{first_name}")


def explain(token: str, result: dict, f: dict, cf: dict, language: str, prompt: str) -> dict:
    """Explanation + steps, written with the token only. The gateway puts the first name back later."""
    out = _ollama(prompt) if config.OLLAMA_URL else None
    engine = f"IBM Granite ({config.GRANITE_MODEL})" if out else "ClearLoan explainer (templates)"
    if not out:
        out = {"explanation": template_explanation(language, token, result, f),
               "steps": template_steps(language, result, f, cf)}
    return {
        "explanation": out["explanation"],
        "explanation_en": None if language == "en" else template_explanation("en", token, result, f),
        "steps": out["steps"],
        "language": language,
        "engine": engine,
    }
