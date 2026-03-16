import re
import logging

logger = logging.getLogger(__name__)

PORTUGUESE_SYMBOLS = {
    "+": "mais",
    "-": "menos",
    "*": "vezes",
    "/": "dividido por",
    "=": "igual a",
    "%": "por cento",
    "°": "graus",
    "±": "mais ou menos",
    "≤": "menor ou igual a",
    "≥": "maior ou igual a",
    "≠": "diferente de",
    "→": "resulta em",
    "←": "proveniente de",
}

KNOWN_ACRONYMS = {
    "IA": "inteligência artificial",
    "AI": "inteligência artificial",
    "ML": "machine learning",
    "DL": "deep learning",
    "NLP": "processamento de linguagem natural",
    "API": "a pi i",
    "SDK": "essecêdi",
    "HTML": "aitch tê emele",
    "CSS": "cê essês",
    "JS": "jotá",
    "TS": "tê essês",
    "PDF": "pê dề effe",
    "DOC": "dóc",
    "DOCX": "dócse",
    "URL": "iurélé",
    "HTTP": "aitch tê tê pề",
    "HTTPS": "aitch tê tê pề essse",
    "SQL": "essqiélé",
    "JSON": "jeissón",
    "XML": "exemele",
    "CSV": "cessevê",
    "RGB": "arrjibî",
    "USB": "iussebî",
    "HDMI": "aitch dề emai",
    "CPU": "cêpều",
    "GPU": "jipều",
    "RAM": "râm",
    "SSD": "essessdề",
    "HDD": "aitchdềdề",
    "IoT": "aiou tì",
    "5G": "5 gâ",
    "4K": "4 câ",
    "8K": "8 câ",
    "UV": "iuvề",
    "LED": "lìd",
    "OLED": "ouled",
    "IPO": "aipiô",
    "CEO": "síou",
    "CTO": "sitiô",
    "MVP": "emvipề",
    "ROI": "roi",
    "KPI": "quipiai",
    "OKR": "oquér",
    "B2B": "bêtobê",
    "B2C": "bêtocê",
    "P2P": "pêtopê",
    "SaaS": "sáss",
    "PaaS": "páss",
    "IaaS": "iáss",
}

NUMBERS_WORDS = {
    0: "zero",
    1: "um",
    2: "dois",
    3: "três",
    4: "quatro",
    5: "cinco",
    6: "seis",
    7: "sete",
    8: "oito",
    9: "nove",
    10: "dez",
    11: "onze",
    12: "doze",
    13: "treze",
    14: "quatorze",
    15: "quinze",
    16: "dezesseis",
    17: "dezessete",
    18: "dezoito",
    19: "dezenove",
    20: "vinte",
    30: "trinta",
    40: "quarenta",
    50: "cinquenta",
    60: "sessenta",
    70: "setenta",
    80: "oitenta",
    90: "noventa",
    100: "cem",
    200: "duzentos",
    300: "trezentos",
    400: "quatrocentos",
    500: "quinhentos",
    600: "seiscentos",
    700: "setecentos",
    800: "oitocentos",
    900: "novecentos",
}


def _number_to_words(n: int) -> str:
    if n < 0:
        return f"menos {_number_to_words(-n)}"

    if n <= 19:
        return NUMBERS_WORDS[n]

    if n <= 99:
        tens = (n // 10) * 10
        units = n % 10
        result = NUMBERS_WORDS[tens]
        if units:
            result += f" e {NUMBERS_WORDS[units]}"
        return result

    if n <= 999:
        hundreds = (n // 100) * 100
        remainder = n % 100
        result = NUMBERS_WORDS[hundreds] if hundreds != 100 else "cem"
        if hundreds != 100:
            result = NUMBERS_WORDS.get(hundreds, str(hundreds))
        if remainder:
            result += f" e {_number_to_words(remainder)}"
        return result

    if n <= 999999:
        thousands = n // 1000
        remainder = n % 1000
        if thousands == 1:
            result = "mil"
        else:
            result = f"{_number_to_words(thousands)} mil"
        if remainder:
            result += f" e {_number_to_words(remainder)}"
        return result

    if n <= 999999999:
        millions = n // 1000000
        remainder = n % 1000000
        result = f"{_number_to_words(millions)} milhão"
        if millions > 1:
            result += "s"
        if remainder:
            result += f" e {_number_to_words(remainder)}"
        return result

    return str(n)


def _expand_number(text: str) -> str:
    def replace_number(match):
        num_str = match.group(0)

        try:
            num = float(num_str.replace(",", "."))
        except ValueError:
            return match.group(0)

        if "." in num_str:
            integer, decimal = num_str.replace(",", ".").split(".")
            return f"{_number_to_words(int(integer))} vírgula {' '.join(list(decimal))}"

        if 0 <= num <= 9999999999:
            return _number_to_words(int(num))

        return match.group(0)

    text = re.sub(r"\b\d{1,10}\b", replace_number, text)

    text = re.sub(
        r"(\d+),(\d+)",
        lambda m: (
            f"{_number_to_words(int(m.group(1)))} vírgula {' '.join(list(m.group(2)))}"
        ),
        text,
    )

    return text


def clean_for_tts(text: str) -> str:
    text = re.sub(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]",
        "",
        text,
    )

    for symbol, word in PORTUGUESE_SYMBOLS.items():
        text = text.replace(symbol, f" {word} ")

    for acronym, expansion in KNOWN_ACRONYMS.items():
        pattern = r"\b" + re.escape(acronym) + r"\b"
        text = re.sub(pattern, expansion, text)

    text = _expand_number(text)

    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)

    text = re.sub(r"[{}]", "", text)

    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    logger.debug(f"Texto limpo: {len(text)} caracteres")

    return text
