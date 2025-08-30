import requests
from .constants import DORAR_API_LINK
import json, re
from scrapy.selector import Selector

def parseHadith():
    pass

def generateMockData():
    return {
        "ahadith": {
            "result": "<head>\n    <link rel=\"canonical\" href=\"https://dorar.net/dorar_api.json\">\n</head>\n<div class=\"hadith\" style=\"text-align:justify;\">1 -  <span class=\"search-keys\">مَن</span> <span class=\"search-keys\">صَلَّى</span> <span class=\"search-keys\">عَلَيَّ</span> <span class=\"search-keys\">واحِدَةً</span> <span class=\"search-keys\">صَلَّى</span> اللَّهُ عليه عَشْرًا.  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أبو هريرة</span>\n    <span class=\"info-subtitle\">المحدث:</span> مسلم\n    <span class=\"info-subtitle\">المصدر:</span>  صحيح مسلم\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  408\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >[صحيح]</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">2 -   <span class=\"search-keys\">من</span> <span class=\"search-keys\">صلَّى</span> <span class=\"search-keys\">عليَّ</span> <span class=\"search-keys\">واحدةً</span> <span class=\"search-keys\">صلَّى</span> اللهُ عليه عشرًا  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أبو هريرة</span>\n    <span class=\"info-subtitle\">المحدث:</span> أبو داود\n    <span class=\"info-subtitle\">المصدر:</span>  سنن أبي داود\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  1530\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >سكت عنه [وقد قال في رسالته لأهل مكة كل ما سكت عنه فهو صالح]</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">3 -  <span class=\"search-keys\">مَن</span> <span class=\"search-keys\">صلَّى</span> <span class=\"search-keys\">علَيَّ</span> <span class=\"search-keys\">واحدةً</span> <span class=\"search-keys\">صلَّى</span> اللهُ عليه عَشْرًا )  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أبو هريرة</span>\n    <span class=\"info-subtitle\">المحدث:</span> ابن حبان\n    <span class=\"info-subtitle\">المصدر:</span>  صحيح ابن حبان\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  906\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >أخرجه في صحيحه</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">4 -  <span class=\"search-keys\">من</span> <span class=\"search-keys\">صلَّى</span> <span class=\"search-keys\">عليَّ</span> <span class=\"search-keys\">واحدةً</span> <span class=\"search-keys\">صلَّى</span> اللَّه عليهِ عشرًا  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أبو هريرة</span>\n    <span class=\"info-subtitle\">المحدث:</span> الألباني\n    <span class=\"info-subtitle\">المصدر:</span>  صحيح النسائي\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  1295\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >صحيح</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">5 -  <span class=\"search-keys\">مَن</span> <span class=\"search-keys\">صلَّى</span> <span class=\"search-keys\">عليَّ</span> <span class=\"search-keys\">واحدةً</span> <span class=\"search-keys\">صلَّى</span> اللَّه علَيهِ عشرًا  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أبو هريرة</span>\n    <span class=\"info-subtitle\">المحدث:</span> الألباني\n    <span class=\"info-subtitle\">المصدر:</span>  صحيح أبي داود\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  1530\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >صحيح</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">6 -   <span class=\"search-keys\">من</span> <span class=\"search-keys\">صلَّى</span> <span class=\"search-keys\">عليَّ</span> <span class=\"search-keys\">واحدةً</span> <span class=\"search-keys\">صلَّى</span> اللهُ عليه عشرًا  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أبو هريرة</span>\n    <span class=\"info-subtitle\">المحدث:</span> الألباني\n    <span class=\"info-subtitle\">المصدر:</span>  فضل الصلاة\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  9\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >صحيح</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">7 -   <span class=\"search-keys\">مَن</span> <span class=\"search-keys\">صلَّى</span> <span class=\"search-keys\">عليَّ</span> <span class=\"search-keys\">واحِدةً</span> ، <span class=\"search-keys\">صلَّى</span> اللهُ عليهِ عَشرًا  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أبو هريرة</span>\n    <span class=\"info-subtitle\">المحدث:</span> الألباني\n    <span class=\"info-subtitle\">المصدر:</span>  صحيح الأدب المفرد\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  501\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >صحيح</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">8 -  <span class=\"search-keys\">مَن</span> <span class=\"search-keys\">صلَّى</span> <span class=\"search-keys\">علَيَّ</span> <span class=\"search-keys\">واحِدةً</span> <span class=\"search-keys\">صلَّى</span> اللهُ عليه عَشْرًا.  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أبو هريرة</span>\n    <span class=\"info-subtitle\">المحدث:</span> شعيب الأرناؤوط\n    <span class=\"info-subtitle\">المصدر:</span>  تخريج المسند لشعيب\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  10287\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >إسناده صحيح على شرط مسلم</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">9 -  <span class=\"search-keys\">مَن</span> <span class=\"search-keys\">صلَّى</span> <span class=\"search-keys\">علَيَّ</span> <span class=\"search-keys\">واحدةً</span> <span class=\"search-keys\">صلَّى</span> اللهُ عليه عَشْرًا )  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أبو هريرة</span>\n    <span class=\"info-subtitle\">المحدث:</span> شعيب الأرناؤوط\n    <span class=\"info-subtitle\">المصدر:</span>  تخريج صحيح ابن حبان\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  906\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >صحيح</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">10 -   <span class=\"search-keys\">مَن</span> <span class=\"search-keys\">صلى</span> <span class=\"search-keys\">عَلَيَّ</span> <span class=\"search-keys\">واحدةً</span> ، <span class=\"search-keys\">صلى</span> اللهُ عليه بها عَشْرًا  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أبو هريرة</span>\n    <span class=\"info-subtitle\">المحدث:</span> الألباني\n    <span class=\"info-subtitle\">المصدر:</span>  صحيح الجامع\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  6358\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >صحيح</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">11 -  <span class=\"search-keys\">مَن</span> <span class=\"search-keys\">صَلَّى</span> <span class=\"search-keys\">علَيَّ</span> <span class=\"search-keys\">واحدةً</span> يُصَلِّي اللهُ عليه عَشْرًا.   .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أبو هريرة</span>\n    <span class=\"info-subtitle\">المحدث:</span> شعيب الأرناؤوط\n    <span class=\"info-subtitle\">المصدر:</span>  تخريج المسند لشعيب\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  8882\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >إسناده صحيح</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">12 -   <span class=\"search-keys\">من</span> <span class=\"search-keys\">صلى</span> <span class=\"search-keys\">عليّ</span> <span class=\"search-keys\">واحدةً</span> <span class=\"search-keys\">صلى</span> الله عليه عشرا ، وكتب له عشرَ حسناتٍ  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> -</span>\n    <span class=\"info-subtitle\">المحدث:</span> ابن حجر العسقلاني\n    <span class=\"info-subtitle\">المصدر:</span>  نتائج الأفكار\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  3/293\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >الرواية التي فيها لفظ بها جاءت من وجهين آخرين عن العلاء. وجاء عنه من وجه آخر كتب الله إلى آخره</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">13 -  <span class=\"search-keys\">من</span> <span class=\"search-keys\">صلَّى</span> <span class=\"search-keys\">عليَّ</span> <span class=\"search-keys\">واحدةً</span> <span class=\"search-keys\">صلَّى</span> اللَّهُ علَيهِ عشرًا وحطَّ عنْهُ عشرَ خطيئاتٍ .  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أنس بن مالك</span>\n    <span class=\"info-subtitle\">المحدث:</span> الوادعي\n    <span class=\"info-subtitle\">المصدر:</span>  الصحيح المسند\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  89\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >حسن</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">14 -   <span class=\"search-keys\">من</span> <span class=\"search-keys\">صلَّى</span> <span class=\"search-keys\">عليَّ</span> <span class=\"search-keys\">واحدةً</span> <span class=\"search-keys\">صلَّى</span> اللهُ عليه عشرَ صلواتٍ وحطَّ عنه عشرَ خطيئاتٍ  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أنس بن مالك</span>\n    <span class=\"info-subtitle\">المحدث:</span> المنذري\n    <span class=\"info-subtitle\">المصدر:</span>  الترغيب والترهيب\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  2/399\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >[إسناده صحيح أو حسن أو ما قاربهما]</span>\n</div>\n--------------\n<br/>\n<div class=\"hadith\" style=\"text-align:justify;\">15 -   <span class=\"search-keys\">مَن</span> <span class=\"search-keys\">صلَّى</span> <span class=\"search-keys\">عليَّ</span> <span class=\"search-keys\">واحدةً</span> <span class=\"search-keys\">صلَّى</span> اللهُ عليه عَشْرًا بها مَلَكٌ مُوَكَّلٌ حتَّى يُبَلِّغَنيها  .</div>\n\n<div class=\"hadith-info\">\n    <span class=\"info-subtitle\">الراوي:</span> أبو أمامة الباهلي</span>\n    <span class=\"info-subtitle\">المحدث:</span> الهيثمي\n    <span class=\"info-subtitle\">المصدر:</span>  مجمع الزوائد\n    <span class=\"info-subtitle\">الصفحة أو الرقم:</span>  10/165\n    <span class=\"info-subtitle\">خلاصة حكم المحدث:</span>  <span >فيه موسى بن عمير القرشي الأعمى وهو ضعيف جدا‏‏</span>\n</div>\n--------------\n<br/>\n<br/><br/>\n<a href=\"https://dorar.net/hadith/search?q=من صلى على واحده\">المزيد</a>\n"
            }
        }
def generateEmptyResponse():
    return {
        "ahadith": {
            "result": "<head>\n    <link rel=\"canonical\" href=\"https://dorar.net/dorar_api.json\">\n</head>\n<br/><br/>\n<a href=\"https://dorar.net/hadith/search?q=Asdasda\">المزيد</a>\n"
        }
    }

def getSimilarHadiths(query: str) -> dict:
    try:
        r = requests.get(DORAR_API_LINK, params={"skey": query})
        if r.status_code != 200:
            print(f"Error: Received status code {r.status_code} from Dorar API")
            return {}
        data = r.json()
        return data
            
    except Exception as e:
        print(f"Something went wrong while getting similar hadiths: {str(e)}")
        return {}

def cleanSimilarHadithResults(results: str) -> list:
    if results is None or results.strip() == "":
        return []
    info_data = []
    selector = Selector(text=results)
    ahadith_list = []
    ahadith_divs = selector.css('div.hadith')
    for element in ahadith_divs:
        # Extract text and clean it
        hadith_text = element.css('*::text').getall()
        hadith_text = ' '.join(hadith_text)
        hadith_text = hadith_text.replace("\n", " ").strip()
        hadith_text = ' '.join(hadith_text.split())
        hadith_text = clean_arabic_text(hadith_text)
        ahadith_list.append(hadith_text)
    
    if ahadith_list is None or len(ahadith_list) == 0:
        return []
    ahadith_info = selector.css('div.hadith-info')
    for info in ahadith_info:
        titles = info.css("span.info-subtitle::text").getall()
        set_titles = set(titles)
        values = info.css("::text").getall()
        cleaned_values = []
        for item in values:
            if item not in set_titles:
                item = item.replace('\n', '').strip()
                if item:
                    cleaned_values.append(item)
        info_dict = dict(zip(titles, cleaned_values))
        info_data.append(info_dict)
    if len(ahadith_list) != len(info_data):
        print(f"Warning: Mismatch in number of hadiths and info entries, received {results}")
        return []
    reformatHadithResults(ahadiths=ahadith_list, info=info_data)
    return info_data

def clean_arabic_text(text):
    """
    Clean Arabic text by removing:
    - Leading numbers and dashes
    - Unnecessary dots at the end
    - Unnecessary closing parentheses
    - Extra whitespace
    
    Args:
        text (str): The Arabic text to clean
        
    Returns:
        str: Cleaned Arabic text
    """
    # Remove leading number pattern (digit(s) followed by space and dash)
    text = re.sub(r'^\d+\s*-\s*', '', text)
    
    # Remove unnecessary closing parentheses
    text = re.sub(r'\s*\)\s*', ' ', text)
    
    # Remove multiple dots at the end (keeping single dots if they're meaningful)
    text = re.sub(r'\.{2,}$', '.', text)  # Multiple dots become single dot
    text = re.sub(r'\s*\.\s*$', '', text)  # Remove trailing single dot with spaces
    
    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces become single space
    text = text.strip()  # Remove leading/trailing whitespace
    
    return text

def reformatHadithResults(ahadiths: list, info: list):
    if ahadiths is None or info is None or len(ahadiths) == 0 or len(info) == 0 or len(ahadiths) != len(info):
        return []
    for index in range(len(info)):
        if info[index].get("الراوي:") is not None:
            info[index]["narrator"] = info[index].pop("الراوي:")
        else:
            info[index]["narrator"] = "-"
        
        if info[index].get("المحدث:") is not None:
            info[index]["muhaddith"] = info[index].pop("المحدث:")
        else:
            info[index]["muhaddith"] = "-"
        
        if info[index].get("المصدر:") is not None:
            info[index]["source"] = info[index].pop("المصدر:")
        else:
            info[index]["source"] = "-"
        
        if info[index].get("الصفحة أو الرقم:") is not None:
            info[index]["page"] = info[index].pop("الصفحة أو الرقم:")
        else:
            info[index]["page"] = "-"
        
        if info[index].get("خلاصة حكم المحدث:") is not None:
            info[index]["ruling"] = info[index].pop("خلاصة حكم المحدث:")
        else:
            info[index]["ruling"] = "-"
        info[index]["hadith"] = ahadiths[index]