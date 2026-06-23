import json
import random
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
QUIZ_DATA_FILE = ROOT_DIR / "data" / "quizes" / "quizes.json"
QUESTION_COUNT = 10_000
RANDOM_SEED = 1447
QURAN_METADATA_URL = "https://tanzil.net/res/text/metadata/quran-data.xml"

ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
QUESTION_TYPES = ["single_selection", "multiple_selection", "true_false", "ordering", "matching"]


GENERAL_SOURCE = {
    "name": "حقائق إسلامية عامة",
    "references": [
        "https://mawdoo3.com/أسئلة_عامة_دينية_وأجوبتها",
        "https://islamic-relief.org/five-pillars-of-islam/",
        "https://aboutislam.net/counseling/ask-about-islam/what-are-the-6-articles-of-faith/",
    ],
}

QURAN_SOURCE = {
    "name": "بيانات القرآن الكريم",
    "references": [
        "https://tanzil.net/docs/quran_metadata",
        QURAN_METADATA_URL,
    ],
}

GENERAL_FACTS = [
    {
        "question": "كم عدد أركان الإسلام؟",
        "answer": "خمسة",
        "wrongs": ["ثلاثة", "أربعة", "ستة"],
        "category": "أركان الإسلام",
    },
    {
        "question": "ما أول أركان الإسلام؟",
        "answer": "الشهادتان",
        "wrongs": ["الصلاة", "الزكاة", "الصوم"],
        "category": "أركان الإسلام",
    },
    {
        "question": "أي عبادة هي الركن الثاني من أركان الإسلام؟",
        "answer": "الصلاة",
        "wrongs": ["الصوم", "الحج", "الزكاة"],
        "category": "أركان الإسلام",
    },
    {
        "question": "في أي شهر يصوم المسلمون رمضان؟",
        "answer": "رمضان",
        "wrongs": ["شعبان", "محرم", "ذو الحجة"],
        "category": "الصوم",
    },
    {
        "question": "ما الركن المرتبط بإخراج المال للفقراء والمستحقين؟",
        "answer": "الزكاة",
        "wrongs": ["الصوم", "الحج", "الوضوء"],
        "category": "أركان الإسلام",
    },
    {
        "question": "ما الركن المرتبط بزيارة البيت الحرام لمن استطاع؟",
        "answer": "الحج",
        "wrongs": ["الصوم", "الزكاة", "الأذان"],
        "category": "الحج",
    },
    {
        "question": "كم عدد أركان الإيمان؟",
        "answer": "ستة",
        "wrongs": ["خمسة", "سبعة", "أربعة"],
        "category": "أركان الإيمان",
    },
    {
        "question": "ما اسم كتاب المسلمين المقدس؟",
        "answer": "القرآن الكريم",
        "wrongs": ["الزبور", "التوراة", "الإنجيل"],
        "category": "القرآن الكريم",
    },
    {
        "question": "على من نزل القرآن الكريم؟",
        "answer": "النبي محمد صلى الله عليه وسلم",
        "wrongs": ["النبي موسى عليه السلام", "النبي عيسى عليه السلام", "النبي داود عليه السلام"],
        "category": "القرآن الكريم",
    },
    {
        "question": "من هو خاتم الأنبياء والمرسلين؟",
        "answer": "النبي محمد صلى الله عليه وسلم",
        "wrongs": ["النبي إبراهيم عليه السلام", "النبي موسى عليه السلام", "النبي عيسى عليه السلام"],
        "category": "الأنبياء",
    },
    {
        "question": "ما قبلة المسلمين في الصلاة؟",
        "answer": "الكعبة المشرفة",
        "wrongs": ["المسجد الأقصى", "المسجد النبوي", "غار حراء"],
        "category": "الصلاة",
    },
    {
        "question": "كم عدد الصلوات المفروضة في اليوم والليلة؟",
        "answer": "خمس صلوات",
        "wrongs": ["ثلاث صلوات", "أربع صلوات", "ست صلوات"],
        "category": "الصلاة",
    },
    {
        "question": "كم عدد ركعات صلاة الفجر المفروضة؟",
        "answer": "ركعتان",
        "wrongs": ["ثلاث ركعات", "أربع ركعات", "خمس ركعات"],
        "category": "الصلاة",
    },
    {
        "question": "كم عدد ركعات صلاة المغرب المفروضة؟",
        "answer": "ثلاث ركعات",
        "wrongs": ["ركعتان", "أربع ركعات", "خمس ركعات"],
        "category": "الصلاة",
    },
    {
        "question": "ما اسم النداء إلى الصلاة؟",
        "answer": "الأذان",
        "wrongs": ["الإقامة", "الخطبة", "التكبير"],
        "category": "الصلاة",
    },
    {
        "question": "ما الصلاة الأسبوعية التي يجتمع لها المسلمون يوم الجمعة؟",
        "answer": "صلاة الجمعة",
        "wrongs": ["صلاة العيد", "صلاة الوتر", "صلاة التراويح"],
        "category": "الصلاة",
    },
    {
        "question": "ما الشهر الذي يأتي بعد رمضان مباشرة؟",
        "answer": "شوال",
        "wrongs": ["شعبان", "ذو القعدة", "محرم"],
        "category": "الشهور الهجرية",
    },
    {
        "question": "ما أول شهر في السنة الهجرية؟",
        "answer": "محرم",
        "wrongs": ["رمضان", "رجب", "ذو الحجة"],
        "category": "الشهور الهجرية",
    },
    {
        "question": "ما الشهر الذي يؤدي فيه المسلمون الحج؟",
        "answer": "ذو الحجة",
        "wrongs": ["رمضان", "شعبان", "محرم"],
        "category": "الحج",
    },
    {
        "question": "ما العيد الذي يأتي بعد رمضان؟",
        "answer": "عيد الفطر",
        "wrongs": ["عيد الأضحى", "يوم عرفة", "ليلة القدر"],
        "category": "الأعياد",
    },
    {
        "question": "ما العيد المرتبط بموسم الحج؟",
        "answer": "عيد الأضحى",
        "wrongs": ["عيد الفطر", "ليلة القدر", "يوم الجمعة"],
        "category": "الأعياد",
    },
    {
        "question": "ما اسم السورة التي تسمى أم الكتاب؟",
        "answer": "الفاتحة",
        "wrongs": ["البقرة", "الإخلاص", "الناس"],
        "category": "القرآن الكريم",
    },
    {
        "question": "ما السورة التي لا تبدأ بالبسملة في المصحف؟",
        "answer": "التوبة",
        "wrongs": ["الفاتحة", "الإخلاص", "الكوثر"],
        "category": "القرآن الكريم",
    },
    {
        "question": "ما أطول سورة في القرآن الكريم؟",
        "answer": "البقرة",
        "wrongs": ["آل عمران", "النساء", "الأعراف"],
        "category": "القرآن الكريم",
    },
    {
        "question": "ما أقصر سورة في القرآن الكريم؟",
        "answer": "الكوثر",
        "wrongs": ["الإخلاص", "الفلق", "العصر"],
        "category": "القرآن الكريم",
    },
    {
        "question": "كم عدد سور القرآن الكريم؟",
        "answer": "مئة وأربع عشرة سورة",
        "wrongs": ["مئة سورة", "مئة وعشر سور", "مئة وعشرون سورة"],
        "category": "القرآن الكريم",
    },
    {
        "question": "كم عدد أجزاء القرآن الكريم؟",
        "answer": "ثلاثون جزءا",
        "wrongs": ["عشرون جزءا", "أربعون جزءا", "ستون جزءا"],
        "category": "القرآن الكريم",
    },
    {
        "question": "ما أول سورة في ترتيب المصحف؟",
        "answer": "الفاتحة",
        "wrongs": ["البقرة", "العلق", "الناس"],
        "category": "القرآن الكريم",
    },
    {
        "question": "ما آخر سورة في ترتيب المصحف؟",
        "answer": "الناس",
        "wrongs": ["الفلق", "الإخلاص", "المسد"],
        "category": "القرآن الكريم",
    },
    {
        "question": "ما اسم السورتين الأخيرتين اللتين تسميان المعوذتين؟",
        "answer": "الفلق والناس",
        "wrongs": ["الإخلاص والفلق", "الكوثر والكافرون", "الفاتحة والناس"],
        "category": "القرآن الكريم",
    },
    {
        "question": "من هو النبي الذي ابتلعه الحوت؟",
        "answer": "يونس عليه السلام",
        "wrongs": ["موسى عليه السلام", "نوح عليه السلام", "إبراهيم عليه السلام"],
        "category": "الأنبياء",
    },
    {
        "question": "من هي أم النبي عيسى عليه السلام؟",
        "answer": "مريم عليها السلام",
        "wrongs": ["آسية", "هاجر", "خديجة"],
        "category": "الأنبياء",
    },
    {
        "question": "من هو النبي الذي كلمه الله؟",
        "answer": "موسى عليه السلام",
        "wrongs": ["يونس عليه السلام", "يوسف عليه السلام", "صالح عليه السلام"],
        "category": "الأنبياء",
    },
    {
        "question": "من هو النبي الذي بنى الكعبة مع ابنه إسماعيل عليهما السلام؟",
        "answer": "إبراهيم عليه السلام",
        "wrongs": ["يعقوب عليه السلام", "داود عليه السلام", "زكريا عليه السلام"],
        "category": "الأنبياء",
    },
    {
        "question": "من هو الملك الذي نزل بالوحي على النبي محمد صلى الله عليه وسلم؟",
        "answer": "جبريل عليه السلام",
        "wrongs": ["ميكائيل عليه السلام", "إسرافيل عليه السلام", "مالك عليه السلام"],
        "category": "الملائكة",
    },
    {
        "question": "إلى أي مدينة هاجر النبي محمد صلى الله عليه وسلم؟",
        "answer": "المدينة المنورة",
        "wrongs": ["الطائف", "القدس", "بدر"],
        "category": "السيرة النبوية",
    },
    {
        "question": "ما اسم الغار الذي كان يتعبد فيه النبي محمد صلى الله عليه وسلم قبل البعثة؟",
        "answer": "غار حراء",
        "wrongs": ["غار ثور", "غار أحد", "غار بدر"],
        "category": "السيرة النبوية",
    },
    {
        "question": "ما اسم الغار الذي اختبأ فيه النبي صلى الله عليه وسلم وصاحبه في الهجرة؟",
        "answer": "غار ثور",
        "wrongs": ["غار حراء", "غار أحد", "غار بدر"],
        "category": "السيرة النبوية",
    },
]

GROUPS = [
    {
        "name": "أركان الإسلام",
        "items": ["الشهادتان", "الصلاة", "الزكاة", "الصوم", "الحج"],
        "distractors": ["الوضوء", "الأذان", "الخطبة", "التهجد", "الاعتكاف"],
        "source": GENERAL_SOURCE,
    },
    {
        "name": "أركان الإيمان",
        "items": [
            "الإيمان بالله",
            "الإيمان بالملائكة",
            "الإيمان بالكتب",
            "الإيمان بالرسل",
            "الإيمان باليوم الآخر",
            "الإيمان بالقدر خيره وشره",
        ],
        "distractors": ["الأذان", "الزكاة", "الطواف", "السعي", "صلاة الجمعة"],
        "source": GENERAL_SOURCE,
    },
    {
        "name": "الصلوات المفروضة",
        "items": ["الفجر", "الظهر", "العصر", "المغرب", "العشاء"],
        "distractors": ["الضحى", "الوتر", "العيد", "التراويح", "الاستسقاء"],
        "source": GENERAL_SOURCE,
    },
    {
        "name": "المعوذتان",
        "items": ["الفلق", "الناس"],
        "distractors": ["الإخلاص", "الكوثر", "العصر", "المسد"],
        "source": GENERAL_SOURCE,
    },
]

ORDERED_LISTS = [
    {
        "question": "رتب الصلوات المفروضة حسب وقتها في اليوم.",
        "answers": ["الفجر", "الظهر", "العصر", "المغرب", "العشاء"],
        "category": "الصلاة",
        "source": GENERAL_SOURCE,
    },
    {
        "question": "رتب أركان الإسلام حسب ورودها المشهور.",
        "answers": ["الشهادتان", "الصلاة", "الزكاة", "الصوم", "الحج"],
        "category": "أركان الإسلام",
        "source": GENERAL_SOURCE,
    },
    {
        "question": "رتب هذه الشهور الهجرية حسب تسلسلها.",
        "answers": ["محرم", "صفر", "ربيع الأول", "ربيع الآخر"],
        "category": "الشهور الهجرية",
        "source": GENERAL_SOURCE,
    },
    {
        "question": "رتب هذه الشهور الهجرية حسب تسلسلها.",
        "answers": ["رجب", "شعبان", "رمضان", "شوال"],
        "category": "الشهور الهجرية",
        "source": GENERAL_SOURCE,
    },
    {
        "question": "رتب السور الثلاث الأخيرة في المصحف.",
        "answers": ["الإخلاص", "الفلق", "الناس"],
        "category": "القرآن الكريم",
        "source": QURAN_SOURCE,
    },
]

MATCHING_FACTS = [
    ("صلاة الفجر", "ركعتان", "الصلاة"),
    ("صلاة الظهر", "أربع ركعات", "الصلاة"),
    ("صلاة العصر", "أربع ركعات", "الصلاة"),
    ("صلاة المغرب", "ثلاث ركعات", "الصلاة"),
    ("صلاة العشاء", "أربع ركعات", "الصلاة"),
    ("رمضان", "شهر الصيام", "الصوم"),
    ("ذو الحجة", "شهر الحج", "الحج"),
    ("الفاتحة", "أم الكتاب", "القرآن الكريم"),
    ("البقرة", "أطول سورة", "القرآن الكريم"),
    ("الكوثر", "أقصر سورة", "القرآن الكريم"),
    ("التوبة", "السورة التي لا تبدأ بالبسملة", "القرآن الكريم"),
    ("جبريل عليه السلام", "ملك الوحي", "الملائكة"),
    ("يونس عليه السلام", "النبي الذي ابتلعه الحوت", "الأنبياء"),
    ("مريم عليها السلام", "أم عيسى عليه السلام", "الأنبياء"),
]


def arabic_number(value):
    return str(value).translate(ARABIC_DIGITS)


def shuffled(rng, values):
    values = list(values)
    rng.shuffle(values)
    return values


def unique_values(values):
    return list(dict.fromkeys(values))


def load_surahs():
    with urlopen(QURAN_METADATA_URL, timeout=30) as response:
        root = ET.fromstring(response.read())

    surahs = []
    for item in root.find("suras").findall("sura"):
        surahs.append(
            {
                "index": int(item.attrib["index"]),
                "ayas": int(item.attrib["ayas"]),
                "name": item.attrib["name"],
                "type": "مكية" if item.attrib["type"] == "Meccan" else "مدنية",
                "order": int(item.attrib["order"]),
            }
        )
    return surahs


def with_id(question, quiz_number):
    question["id"] = f"quiz-{quiz_number:05d}"
    return question


def single_question(rng, fact):
    options = shuffled(rng, [fact["answer"], *fact["wrongs"]])
    return {
        "question": fact["question"],
        "options": options,
        "type": "single_selection",
        "answers": [fact["answer"]],
        "category": fact["category"],
        "source": GENERAL_SOURCE,
    }


def true_false_from_fact(rng, fact):
    is_true = rng.choice([True, False])
    chosen = fact["answer"] if is_true else rng.choice(fact["wrongs"])
    return {
        "question": f"هل العبارة صحيحة؟ {fact['question']} الإجابة: {chosen}.",
        "options": ["صحيح", "خطأ"],
        "type": "true_false",
        "answers": ["صحيح" if is_true else "خطأ"],
        "category": fact["category"],
        "source": GENERAL_SOURCE,
    }


def multiple_from_group(rng, group):
    answer_count = min(len(group["items"]), rng.choice([2, 3]))
    answers = rng.sample(group["items"], answer_count)
    wrongs = rng.sample(group["distractors"], 4 - answer_count)
    return {
        "question": f"اختر الإجابات التي تعد من {group['name']}.",
        "options": shuffled(rng, [*answers, *wrongs]),
        "type": "multiple_selection",
        "answers": answers,
        "category": group["name"],
        "source": group["source"],
    }


def ordering_from_list(rng, item):
    answers = item["answers"]
    return {
        "question": item["question"],
        "options": shuffled(rng, answers),
        "type": "ordering",
        "answers": answers,
        "category": item["category"],
        "source": item["source"],
    }


def matching_from_facts(rng):
    correct = rng.choice(MATCHING_FACTS)
    wrong_pool = [item for item in MATCHING_FACTS if item != correct]
    wrongs = rng.sample(wrong_pool, 3)
    correct_option = f"{correct[0]}: {correct[1]}"
    wrong_options = [f"{left}: {right}" for left, right, _ in wrongs]
    return {
        "question": "أي مطابقة صحيحة؟",
        "options": shuffled(rng, [correct_option, *wrong_options]),
        "type": "matching",
        "answers": [correct_option],
        "category": correct[2],
        "source": GENERAL_SOURCE,
    }


def surah_by_number(rng, surah, surahs):
    wrongs = rng.sample([item["name"] for item in surahs if item["index"] != surah["index"]], 3)
    return {
        "question": f"ما اسم السورة رقم {arabic_number(surah['index'])} في المصحف؟",
        "options": shuffled(rng, [surah["name"], *wrongs]),
        "type": "single_selection",
        "answers": [surah["name"]],
        "category": "القرآن الكريم",
        "source": QURAN_SOURCE,
    }


def surah_number(rng, surah, surahs):
    correct = arabic_number(surah["index"])
    wrongs = rng.sample([arabic_number(item["index"]) for item in surahs if item["index"] != surah["index"]], 3)
    return {
        "question": f"ما ترتيب سورة {surah['name']} في المصحف؟",
        "options": shuffled(rng, [correct, *wrongs]),
        "type": "single_selection",
        "answers": [correct],
        "category": "القرآن الكريم",
        "source": QURAN_SOURCE,
    }


def surah_ayas(rng, surah, surahs):
    correct = arabic_number(surah["ayas"])
    wrongs = rng.sample(unique_values([arabic_number(item["ayas"]) for item in surahs if item["ayas"] != surah["ayas"]]), 3)
    return {
        "question": f"كم عدد آيات سورة {surah['name']}؟",
        "options": shuffled(rng, [correct, *wrongs]),
        "type": "single_selection",
        "answers": [correct],
        "category": "القرآن الكريم",
        "source": QURAN_SOURCE,
    }


def surah_type(rng, surah):
    return {
        "question": f"هل سورة {surah['name']} مكية أم مدنية؟",
        "options": ["مكية", "مدنية"],
        "type": "single_selection",
        "answers": [surah["type"]],
        "category": "القرآن الكريم",
        "source": QURAN_SOURCE,
    }


def surah_true_false(rng, surah, surahs):
    variants = [
        ("عدد آيات", arabic_number(surah["ayas"]), unique_values([arabic_number(item["ayas"]) for item in surahs if item["ayas"] != surah["ayas"]])),
        ("ترتيب", arabic_number(surah["index"]), [arabic_number(item["index"]) for item in surahs if item["index"] != surah["index"]]),
        ("نوع", surah["type"], ["مكية" if surah["type"] == "مدنية" else "مدنية"]),
    ]
    label, correct, wrongs = rng.choice(variants)
    is_true = rng.choice([True, False])
    value = correct if is_true else rng.choice(wrongs)
    if label == "عدد آيات":
        statement = f"عدد آيات سورة {surah['name']} هو {value}."
    elif label == "ترتيب":
        statement = f"ترتيب سورة {surah['name']} في المصحف هو {value}."
    else:
        statement = f"سورة {surah['name']} {value}."
    return {
        "question": f"هل العبارة صحيحة؟ {statement}",
        "options": ["صحيح", "خطأ"],
        "type": "true_false",
        "answers": ["صحيح" if is_true else "خطأ"],
        "category": "القرآن الكريم",
        "source": QURAN_SOURCE,
    }


def surah_multiple(rng, surah, surahs):
    wrong_surah = rng.choice([item for item in surahs if item["index"] != surah["index"] and item["ayas"] != surah["ayas"]])
    answers = [
        f"ترتيبها في المصحف {arabic_number(surah['index'])}",
        f"عدد آياتها {arabic_number(surah['ayas'])}",
    ]
    wrongs = [
        f"ترتيبها في المصحف {arabic_number(wrong_surah['index'])}",
        f"عدد آياتها {arabic_number(wrong_surah['ayas'])}",
    ]
    return {
        "question": f"اختر العبارتين الصحيحتين عن سورة {surah['name']}.",
        "options": shuffled(rng, [*answers, *wrongs]),
        "type": "multiple_selection",
        "answers": answers,
        "category": "القرآن الكريم",
        "source": QURAN_SOURCE,
    }


def surah_ordering(rng, surahs):
    selected = rng.sample(surahs, 4)
    answers = [item["name"] for item in sorted(selected, key=lambda item: item["index"])]
    return {
        "question": "رتب هذه السور حسب ترتيبها في المصحف.",
        "options": shuffled(rng, answers),
        "type": "ordering",
        "answers": answers,
        "category": "القرآن الكريم",
        "source": QURAN_SOURCE,
    }


def surah_matching(rng, surahs):
    correct = rng.choice(surahs)
    wrongs = rng.sample([item for item in surahs if item["index"] != correct["index"]], 3)
    correct_option = f"سورة {correct['name']}: ترتيبها {arabic_number(correct['index'])}"
    wrong_options = [f"سورة {item['name']}: ترتيبها {arabic_number(rng.choice([s['index'] for s in surahs if s['index'] != item['index']]))}" for item in wrongs]
    return {
        "question": "أي مطابقة صحيحة بين اسم السورة وترتيبها؟",
        "options": shuffled(rng, [correct_option, *wrong_options]),
        "type": "matching",
        "answers": [correct_option],
        "category": "القرآن الكريم",
        "source": QURAN_SOURCE,
    }


def build_quizes():
    rng = random.Random(RANDOM_SEED)
    surahs = load_surahs()
    quizes = []
    makers = [
        lambda: single_question(rng, rng.choice(GENERAL_FACTS)),
        lambda: true_false_from_fact(rng, rng.choice(GENERAL_FACTS)),
        lambda: multiple_from_group(rng, rng.choice(GROUPS)),
        lambda: ordering_from_list(rng, rng.choice(ORDERED_LISTS)),
        lambda: matching_from_facts(rng),
        lambda: surah_by_number(rng, rng.choice(surahs), surahs),
        lambda: surah_number(rng, rng.choice(surahs), surahs),
        lambda: surah_ayas(rng, rng.choice(surahs), surahs),
        lambda: surah_type(rng, rng.choice(surahs)),
        lambda: surah_true_false(rng, rng.choice(surahs), surahs),
        lambda: surah_multiple(rng, rng.choice(surahs), surahs),
        lambda: surah_ordering(rng, surahs),
        lambda: surah_matching(rng, surahs),
    ]

    while len(quizes) < QUESTION_COUNT:
        question_number = len(quizes) + 1
        maker = makers[(question_number - 1) % len(makers)]
        quizes.append(with_id(maker(), question_number))

    QUIZ_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUIZ_DATA_FILE.write_text(
        json.dumps(
            {
                "metadata": {
                    "count": len(quizes),
                    "language": "ar",
                    "source": "حقائق إسلامية عامة وبيانات القرآن الكريم",
                    "question_types": QUESTION_TYPES,
                    "references": [
                        "https://mawdoo3.com/أسئلة_عامة_دينية_وأجوبتها",
                        "https://tanzil.net/docs/quran_metadata",
                        "https://islamic-relief.org/five-pillars-of-islam/",
                        "https://aboutislam.net/counseling/ask-about-islam/what-are-the-6-articles-of-faith/",
                    ],
                },
                "quizes": quizes,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build_quizes()
