"""Conservative routing guard; actual mutation safety comes from tool boundaries."""
import re


def requests_catalog_mutation(question):
    # Quoted commands in a request for research remain research data. This is
    # intentionally not a general prompt-injection detector.
    if re.search(r'논문|문헌|연구|\b(?:papers?|studies|study|literature|research)\b',question,re.I):return False
    return bool(re.search(r'(?:카드|후보|지식|자료).{0,40}(?:승인|발행|삭제)(?:해|하라|하렴|하세)|'
        r'\b(?:approve|publish|delete|drop)\b.{0,40}\b(?:cards?|candidates?|knowledge|sources?|documents?|tables?)\b',question,re.I))
