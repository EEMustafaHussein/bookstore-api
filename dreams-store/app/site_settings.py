"""Shop settings the owner edits from the dashboard (name, social links, about page...)."""

import copy
import json

from sqlmodel import Session, select

from app.models import SiteSetting

SOCIAL_PLATFORMS = [
    ("instagram", "إنستغرام"),
    ("facebook", "فيسبوك"),
    ("tiktok", "تيك توك"),
    ("snapchat", "سناب شات"),
    ("telegram", "تيليغرام"),
    ("whatsapp", "واتساب"),
    ("youtube", "يوتيوب"),
    ("x", "إكس (تويتر)"),
]

MAX_WEBSITES = 6

DEFAULTS: dict = {
    "site_name": "ملابس الأحلام",
    "tagline": "أناقة تشبه أحلامكِ",
    "announcement": "توصيل لجميع محافظات العراق ✦ الدفع عند الاستلام أو بالبطاقة ✦ قطع بالة فريدة كل أسبوع",
    "hero_title": "ارتدي أحلامكِ",
    "hero_subtitle": "تشكيلة نسائية مختارة بعناية — أزياء جديدة وقطع بالة فريدة لا تتكرر، تصلكِ حتى باب البيت.",
    "contact_phone": "",
    "contact_email": "",
    "address": "بغداد، العراق",
    "shipping_fee": 5000,
    "free_shipping_over": 100000,
    "currency_symbol": "د.ع",
    # The code from Google Search Console's "HTML tag" verification method.
    "google_verification": "",
    "social": {key: "" for key, _ in SOCIAL_PLATFORMS},
    "about": {
        "name": "اسم المصمم",
        "title": "مهندس كهرباء ومطوّر مواقع",
        "bio": (
            "مهندس كهرباء خريج الجامعة المستنصرية، شغوف بعالم الكهرباء والبرمجة، "
            "أحب التعلّم وأعمل على تطوير مهاراتي باستمرار.\n"
            "صمّمت وبرمجت متجر «ملابس الأحلام» ليكون تجربة تسوّق عصرية وسهلة وآمنة."
        ),
        "photo": None,
        "phone": "",
        "whatsapp": "",
        "email": "",
        "location": "العراق",
        "skills": "هندسة كهربائية, Python, FastAPI, تصميم المواقع, قواعد البيانات",
        "websites": [],
    },
}


def load_site_settings(session: Session) -> dict:
    data = copy.deepcopy(DEFAULTS)
    for row in session.exec(select(SiteSetting)).all():
        try:
            value = json.loads(row.value)
        except ValueError:
            continue
        if isinstance(data.get(row.key), dict) and isinstance(value, dict):
            data[row.key].update(value)
        elif row.key in data:
            data[row.key] = value
    return data


def save_site_settings(session: Session, values: dict) -> None:
    for key, value in values.items():
        if key not in DEFAULTS:
            raise KeyError(key)
        row = session.get(SiteSetting, key)
        encoded = json.dumps(value, ensure_ascii=False)
        if row is None:
            session.add(SiteSetting(key=key, value=encoded))
        else:
            row.value = encoded
            session.add(row)
    session.commit()
