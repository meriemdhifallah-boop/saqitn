# -*- coding: utf-8 -*-
"""
SaqiTN (سقي) - Conseiller d'irrigation pour agriculteurs tunisiens
Méthode FAO-56 : ETc = ET0 x Kc  +  bilan hydrique du sol  +  prévisions Open-Meteo
Langues : Français / العربية / تونسي
"""
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="SaqiTN - سقي", page_icon="💧", layout="centered")

# ------------------------------------------------------------------ DONNÉES
# (fr, ar, lat, lon)
GOV = {
    "tunis": ("Tunis", "تونس", 36.80, 10.18), "ariana": ("Ariana", "أريانة", 36.86, 10.19),
    "benarous": ("Ben Arous", "بن عروس", 36.75, 10.23), "manouba": ("La Manouba", "منوبة", 36.81, 10.09),
    "nabeul": ("Nabeul", "نابل", 36.45, 10.74), "zaghouan": ("Zaghouan", "زغوان", 36.40, 10.14),
    "bizerte": ("Bizerte", "بنزرت", 37.27, 9.87), "beja": ("Béja", "باجة", 36.73, 9.18),
    "jendouba": ("Jendouba", "جندوبة", 36.50, 8.78), "kef": ("Le Kef", "الكاف", 36.17, 8.71),
    "siliana": ("Siliana", "سليانة", 36.08, 9.37), "sousse": ("Sousse", "سوسة", 35.83, 10.64),
    "monastir": ("Monastir", "المنستير", 35.78, 10.83), "mahdia": ("Mahdia", "المهدية", 35.50, 11.06),
    "sfax": ("Sfax", "صفاقس", 34.74, 10.76), "kairouan": ("Kairouan", "القيروان", 35.68, 10.10),
    "kasserine": ("Kasserine", "القصرين", 35.17, 8.83), "sidibouzid": ("Sidi Bouzid", "سيدي بوزيد", 35.04, 9.49),
    "gabes": ("Gabès", "قابس", 33.88, 10.10), "medenine": ("Médenine", "مدنين", 33.35, 10.50),
    "tataouine": ("Tataouine", "تطاوين", 32.93, 10.45), "gafsa": ("Gafsa", "قفصة", 34.43, 8.78),
    "tozeur": ("Tozeur", "توزر", 33.92, 8.13), "kebili": ("Kébili", "قبلي", 33.70, 8.97),
}

# kc = (début, mi-saison, fin) approx. FAO-56 ; root = profondeur racinaire (m) ; p = fraction d'épuisement admissible
# names = (fr, ar, tn)
CROPS = {
    "tomato":  dict(kc=(0.60, 1.15, 0.80), root=0.7, p=0.40, names=("Tomate", "الطماطم", "الطماطم")),
    "potato":  dict(kc=(0.50, 1.15, 0.75), root=0.5, p=0.35, names=("Pomme de terre", "البطاطا", "البطاطا")),
    "pepper":  dict(kc=(0.60, 1.05, 0.90), root=0.5, p=0.30, names=("Piment / poivron", "الفلفل", "الفلفل")),
    "melon":   dict(kc=(0.40, 1.00, 0.75), root=0.8, p=0.40, names=("Pastèque", "البطيخ الأحمر", "الدلاع")),
    "wheat":   dict(kc=(0.35, 1.15, 0.40), root=1.0, p=0.55, names=("Blé / céréales", "القمح والحبوب", "القمح والشعير")),
    "olive":   dict(kc=(0.65, 0.70, 0.70), root=1.2, p=0.65, names=("Olivier", "الزيتون", "الزيتون")),
    "citrus":  dict(kc=(0.70, 0.65, 0.70), root=1.1, p=0.50, names=("Agrumes", "الحمضيات", "الحمضيات (برتقال، ليمون)")),
    "date":    dict(kc=(0.90, 0.95, 0.95), root=1.5, p=0.50, names=("Palmier dattier", "نخيل التمر", "النخل (دقلة)")),
}
SOILS = {  # eau utile (mm par m de sol) ; noms (fr, ar, tn)
    "sand": dict(taw=80, names=("Sableux (léger)", "رملية", "رملية")),
    "loam": dict(taw=140, names=("Limoneux (moyen)", "متوسطة (طميية)", "متوسطة")),
    "clay": dict(taw=180, names=("Argileux (lourd)", "طينية", "طينية (طين)")),
}
METHODS = {  # efficience, fraction de sol mouillé ; noms
    "drip":      dict(eff=0.90, fw=0.5, names=("Goutte-à-goutte", "التنقيط", "القطرة قطرة (التنقيط)")),
    "sprinkler": dict(eff=0.75, fw=1.0, names=("Aspersion", "الرش", "الرش")),
    "gravity":   dict(eff=0.55, fw=1.0, names=("Gravitaire (seguia)", "السقي بالغمر (السواقي)", "الغمر (السواقي)")),
}
STAGES = ["ini", "mid", "end"]
IDX = {"fr": 0, "ar": 1, "tn": 2}
WD = {
    "fr": ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
    "ar": ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"],
    "tn": ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"],
}

# ------------------------------------------------------------------ TEXTES (fr, ar, tn)
T = {
    "title": ("💧 SaqiTN", "💧 سقي", "💧 سقي"),
    "sub": ("De quelle quantité d'eau vos cultures ont-elles besoin aujourd'hui ?",
            "كم تحتاج مزروعاتك من الماء اليوم؟",
            "قدّاش تحتاج الزريعة متاعك من الماء اليوم؟"),
    "s1": ("1️⃣ Où est votre champ ?", "١. أين يقع حقلك؟", "1️⃣ وين الحقل متاعك؟"),
    "gov": ("Gouvernorat", "الولاية", "الولاية"),
    "s2": ("2️⃣ Que cultivez-vous ?", "٢. ماذا تزرع؟", "2️⃣ شنوّة تزرع؟"),
    "crop": ("Culture", "المحصول", "الزريعة"),
    "stage": ("Stade de la culture", "مرحلة نمو المحصول", "في أنهي مرحلة الزريعة؟"),
    "ini": ("🌱 Début / jeune plantation", "🌱 البداية / نبتة صغيرة", "🌱 في الأول / صغيرة"),
    "mid": ("🌿 Pleine croissance / floraison / fruits", "🌿 نمو كامل / إزهار / ثمار", "🌿 كبرت / تزهر / تثمر"),
    "end": ("🍂 Fin de cycle / maturité", "🍂 نهاية الموسم / نضج", "🍂 في الآخر / تنضج"),
    "s3": ("3️⃣ Sol et arrosage", "٣. التربة وطريقة السقي", "3️⃣ التربة وطريقة السقي"),
    "soil": ("Type de sol", "نوع التربة", "نوع التربة"),
    "method": ("Méthode d'arrosage", "طريقة السقي", "كيفاش تسقي؟"),
    "area": ("Surface (hectares)", "المساحة (بالهكتار)", "المساحة (هكتار)"),
    "s4": ("4️⃣ Dernier arrosage", "٤. آخر سقية", "4️⃣ آخر سقية"),
    "last": ("Il y a combien de jours ? (7 = 7 jours ou plus)", "منذ كم يوم؟ (7 = سبعة أيام أو أكثر)", "من قدّاش من نهار؟ (7 = سبعة أو أكثر)"),
    "res": ("📊 Ma recommandation", "📊 توصيتي", "📊 النصيحة"),
    "today_yes": ("💧 Arrosez AUJOURD'HUI", "💧 اسقِ اليوم", "💧 اسقي اليوم"),
    "today_no": ("✅ Pas besoin d'arroser aujourd'hui", "✅ لا حاجة للسقي اليوم", "✅ ما تحتاجش تسقي اليوم"),
    "amount": ("Quantité : **{mm} mm** = **{m3} m³** pour {ha} ha  \n⏱️ Pompe : environ **{h} h**",
               "الكمية: **{mm} مم** = **{m3} م³** لمساحة {ha} هكتار  \n⏱️ المضخة: حوالي **{h} ساعة**",
               "الكمية: **{mm} مم** = **{m3} م³** لمساحة {ha} هكتار  \n⏱️ المضخة: تقريبا **{h} ساعة**"),
    "next": ("📅 Prochain arrosage : **{d}** — {m3} m³ (≈ {h} h de pompe)",
             "📅 السقية القادمة: **{d}** — {m3} م³ (≈ {h} ساعة مضخة)",
             "📅 السقية الجاية: **{d}** — {m3} م³ (≈ {h} ساعة مضخة)"),
    "none": ("✅ Aucun arrosage nécessaire dans les 7 prochains jours",
             "✅ لا حاجة للسقي خلال الأيام السبعة القادمة",
             "✅ ما تحتاجش تسقي في الـ7 أيام الجايين"),
    "rain": ("🌧️ Pluie prévue : {mm} mm sur 7 jours", "🌧️ أمطار متوقعة: {mm} مم خلال 7 أيام", "🌧️ شتاء متوقع: {mm} مم في 7 أيام"),
    "wx": ("🌡️ Aujourd'hui : max {tmax}°C · évapotranspiration de référence {et0} mm",
           "🌡️ اليوم: العظمى {tmax}° · التبخر-نتح المرجعي {et0} مم",
           "🌡️ اليوم: القصوى {tmax}° · التبخر-نتح المرجعي {et0} مم"),
    "plan": ("📅 Plan des 7 prochains jours", "📅 برنامج الأيام السبعة القادمة", "📅 برنامج الـ7 أيام الجايين"),
    "c_day": ("Jour", "اليوم", "النهار"),
    "c_rain": ("Pluie (mm)", "المطر (مم)", "الشتاء (مم)"),
    "c_need": ("Besoin culture (mm)", "حاجة المحصول (مم)", "حاجة الزريعة (مم)"),
    "c_irr": ("Arrosage (m³)", "السقي (م³)", "السقي (م³)"),
    "adv": ("⚙️ Options avancées (pompe, prix)", "⚙️ خيارات متقدمة (المضخة، الأسعار)", "⚙️ خيارات متقدمة (المضخة، الأسعار)"),
    "flow": ("Débit de la pompe (m³/h)", "تدفق المضخة (م³/س)", "تدفق المضخة (م³/س)"),
    "head": ("Hauteur de pompage totale (m)", "ارتفاع الضخ الكلي (م)", "ارتفاع الضخ الكلي (م)"),
    "peff": ("Rendement de la pompe (%)", "مردود المضخة (%)", "مردود المضخة (%)"),
    "wprice": ("Prix de l'eau (TND/m³)", "سعر الماء (دينار/م³)", "سعر الماء (دينار/م³)"),
    "eprice": ("Prix de l'électricité (TND/kWh)", "سعر الكهرباء (دينار/ك.و.س)", "سعر الكهرباء (دينار/ك.و.س)"),
    "sav": ("💰 Combien j'économise ?", "💰 كم أوفّر؟", "💰 قدّاش نوفّر؟"),
    "h_times": ("Combien de fois par semaine j'arrose d'habitude", "كم مرة أسقي في الأسبوع عادة", "قدّاش من مرّة نسقي في الجمعة عادة"),
    "h_hours": ("Durée de chaque arrosage (heures)", "مدة كل سقية (ساعات)", "مدّة كل سقية (ساعات)"),
    "m_water": ("Eau économisée / semaine", "ماء موفَّر / أسبوع", "ماء موفَّر / جمعة"),
    "m_energy": ("Énergie économisée", "طاقة موفَّرة", "كهرباء موفّرة"),
    "m_money": ("Argent économisé", "مال موفَّر", "فلوس موفّرة"),
    "m_co2": ("CO₂ évité", "ثاني أكسيد الكربون المتجنَّب", "CO₂ متجنّب"),
    "under": ("⚠️ Vous arrosez moins que le besoin calculé ({need} m³/semaine) : risque de stress hydrique pour la culture.",
              "⚠️ أنت تسقي أقل من الحاجة المحسوبة ({need} م³/أسبوع): خطر عطش المحصول.",
              "⚠️ تسقي أقل من الحاجة المحسوبة ({need} م³/جمعة): فما خطر تعطش الزريعة."),
    "need_wk": ("Besoin réel de la culture : **{need} m³ / semaine**",
                "الحاجة الفعلية للمحصول: **{need} م³ / أسبوع**",
                "الحاجة الحقيقية للزريعة: **{need} م³ / جمعة**"),
    "foot": ("Estimation basée sur la méthode FAO-56 (ETc = ET0 × Kc) et les prévisions Open-Meteo. À ajuster avec l'avis d'un technicien agricole.",
             "تقدير مبني على طريقة الفاو FAO-56 (ETc = ET0 × Kc) وتوقعات Open-Meteo. يُستحسن مراجعته مع تقني فلاحي.",
             "تقدير على طريقة الفاو FAO-56 (ETc = ET0 × Kc) وتوقعات Open-Meteo. الأحسن تراجعو مع تقني فلاحي."),
    "wx_err": ("⚠️ Météo indisponible : valeurs moyennes utilisées.", "⚠️ الطقس غير متوفر: تم استعمال قيم متوسطة.", "⚠️ الطقس موش متوفر: استعملنا قيم متوسطة."),
}

# ------------------------------------------------------------------ LANGUE
LANGS = {"Français": "fr", "العربية": "ar", "تونسي": "tn"}
choice = st.radio("🌐", list(LANGS), horizontal=True, label_visibility="collapsed")
L = LANGS[choice]


def t(key, **kw):
    s = T[key][IDX[L]]
    return s.format(**kw) if kw else s


def nm(names):
    return names[IDX[L]]


st.markdown(
    """<style>
    html, body, [class*="css"] { font-size: 18px; }
    label, .stSelectbox label, .stRadio label { font-size: 1.1rem !important; font-weight: 600; }
    div[data-baseweb="select"] > div { min-height: 52px; }
    h1 { text-align: center; }
    </style>""",
    unsafe_allow_html=True,
)
if L != "fr":
    st.markdown(
        """<style>.stApp, .stMarkdown, .stAlert, label, p, h2, h3, [data-testid="stMetric"]
        { direction: rtl; text-align: right; }</style>""",
        unsafe_allow_html=True,
    )

st.title(t("title"))
st.markdown(f"<p style='text-align:center'>{t('sub')}</p>", unsafe_allow_html=True)


# ------------------------------------------------------------------ MÉTÉO
@st.cache_data(ttl=3600, show_spinner=False)
def get_weather(lat, lon):
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat, "longitude": lon,
            "daily": "et0_fao_evapotranspiration,precipitation_sum,temperature_2m_max,temperature_2m_min",
            "timezone": "Africa/Tunis", "past_days": 7, "forecast_days": 7,
        },
        timeout=10,
    )
    r.raise_for_status()
    d = r.json()["daily"]
    df = pd.DataFrame({
        "date": pd.to_datetime(d["time"]),
        "et0": d["et0_fao_evapotranspiration"],
        "rain": d["precipitation_sum"],
        "tmax": d["temperature_2m_max"],
    })
    return df.fillna(0.0)


def fallback_weather():
    today = pd.Timestamp.now(tz="Africa/Tunis").normalize().tz_localize(None)
    dates = pd.date_range(today - pd.Timedelta(days=7), periods=14)
    return pd.DataFrame({"date": dates, "et0": 4.5, "rain": 0.0, "tmax": 28.0})


# ------------------------------------------------------------------ SAISIE
st.header(t("s1"))
gov_key = st.selectbox(t("gov"), list(GOV), index=list(GOV).index("kairouan"),
                       format_func=lambda k: GOV[k][0] if L == "fr" else GOV[k][1])

st.header(t("s2"))
crop_key = st.selectbox(t("crop"), list(CROPS), format_func=lambda k: nm(CROPS[k]["names"]))
stage = st.radio(t("stage"), STAGES, index=1, format_func=lambda k: t(k))

st.header(t("s3"))
soil_key = st.radio(t("soil"), list(SOILS), index=1, horizontal=True,
                    format_func=lambda k: nm(SOILS[k]["names"]))
meth_key = st.radio(t("method"), list(METHODS), horizontal=True,
                    format_func=lambda k: nm(METHODS[k]["names"]))
area = st.number_input(t("area"), min_value=0.1, max_value=500.0, value=1.0, step=0.5)

st.header(t("s4"))
days_since = st.slider(t("last"), 1, 7, 3)

with st.expander(t("adv")):
    flow = st.number_input(t("flow"), 1.0, 500.0, 10.0, 1.0)
    head = st.number_input(t("head"), 1.0, 300.0, 40.0, 5.0)
    peff = st.number_input(t("peff"), 20.0, 90.0, 55.0, 5.0) / 100
    wprice = st.number_input(t("wprice"), 0.0, 5.0, 0.25, 0.05)
    eprice = st.number_input(t("eprice"), 0.0, 2.0, 0.30, 0.05)

# ------------------------------------------------------------------ CALCULS (FAO-56)
lat, lon = GOV[gov_key][2], GOV[gov_key][3]
try:
    df = get_weather(lat, lon)
    if len(df) < 14:
        raise ValueError("incomplete")
except Exception:
    st.warning(t("wx_err"))
    df = fallback_weather()
df = df.reset_index(drop=True)

crop, soil, meth = CROPS[crop_key], SOILS[soil_key], METHODS[meth_key]
kc = crop["kc"][STAGES.index(stage)]
taw = soil["taw"] * crop["root"] * meth["fw"]          # eau utile du sol mouillé (mm)
raw = crop["p"] * taw                                   # réserve facilement utilisable (mm)

df["etc"] = df["et0"] * kc                              # besoin de la culture (mm/j)
df["eff_rain"] = df["rain"].apply(lambda r: 0.8 * r if r >= 2 else 0.0)   # pluie efficace

dr = 0.0                                                # épuisement actuel (mm)
for i in range(7 - days_since, 7):
    dr = max(0.0, dr + df.loc[i, "etc"] - df.loc[i, "eff_rain"])

plan = []
for i in range(7, 14):
    dr = max(0.0, dr + df.loc[i, "etc"] - df.loc[i, "eff_rain"])
    net = 0.0
    if dr >= raw:
        net = dr
        dr = 0.0
    vol = net * area * 10 / meth["eff"]                 # 1 mm sur 1 ha = 10 m³
    plan.append(dict(date=df.loc[i, "date"], rain=df.loc[i, "rain"], etc=df.loc[i, "etc"], net=net, vol=vol))

# ------------------------------------------------------------------ RÉSULTATS
st.header(t("res"))
today = plan[0]
if today["vol"] > 0:
    st.error(f"## {t('today_yes')}")
    st.markdown(t("amount", mm=round(today["net"] / meth["eff"], 1), m3=round(today["vol"], 1),
                  ha=area, h=round(today["vol"] / flow, 1)))
else:
    st.success(f"## {t('today_no')}")
    nxt = next((p for p in plan if p["vol"] > 0), None)
    if nxt:
        d = nxt["date"]
        st.info(t("next", d=f"{WD[L][d.weekday()]} {d:%d/%m}", m3=round(nxt["vol"], 1),
                  h=round(nxt["vol"] / flow, 1)))
    else:
        st.info(t("none"))

st.caption(t("wx", tmax=round(df.loc[7, "tmax"]), et0=round(df.loc[7, "et0"], 1)))
st.caption(t("rain", mm=round(sum(p["rain"] for p in plan), 1)))

st.subheader(t("plan"))
table = pd.DataFrame({
    t("c_day"): [f"{WD[L][p['date'].weekday()]} {p['date']:%d/%m}" for p in plan],
    t("c_rain"): [round(p["rain"], 1) for p in plan],
    t("c_need"): [round(p["etc"], 1) for p in plan],
    t("c_irr"): [round(p["vol"], 1) for p in plan],
})
st.dataframe(table, hide_index=True, width="stretch")
st.bar_chart(table.set_index(t("c_day"))[[t("c_need"), t("c_rain")]])

# ------------------------------------------------------------------ ÉCONOMIES
st.header(t("sav"))
c1, c2 = st.columns(2)
times = c1.number_input(t("h_times"), 0, 14, 3)
hours = c2.number_input(t("h_hours"), 0.0, 24.0, 4.0, 0.5)

need_net = max(0.0, sum(p["etc"] - (0.8 * p["rain"] if p["rain"] >= 2 else 0.0) for p in plan))
need_m3 = need_net * area * 10 / meth["eff"]
habit_m3 = times * hours * flow
st.markdown(t("need_wk", need=round(need_m3, 1)))

saved = habit_m3 - need_m3
if saved > 0:
    kwh = saved * head / (367 * peff)                   # kWh = V(m³) x H(m) / (367 x rendement)
    money = saved * wprice + kwh * eprice
    co2 = kwh * 0.5                                     # ~0,5 kg CO2/kWh (ordre de grandeur réseau tunisien)
    m1, m2 = st.columns(2)
    m1.metric(t("m_water"), f"{saved:.0f} m³")
    m2.metric(t("m_energy"), f"{kwh:.0f} kWh")
    m3_, m4 = st.columns(2)
    m3_.metric(t("m_money"), f"{money:.0f} TND")
    m4.metric(t("m_co2"), f"{co2:.0f} kg")
elif habit_m3 < need_m3 * 0.9:
    st.warning(t("under", need=round(need_m3, 1)))

st.divider()
st.caption(t("foot"))
st.caption("Data: Open-Meteo · FAO Irrigation & Drainage Paper 56")
