"""Provenance-checked conversational slots; model proposals are not trusted facts."""
from decimal import Decimal, InvalidOperation
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SlotUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    slot: Literal['destination','trip_days','amount','currency','group_name']
    value: str
    quote: str


class ContextError(ValueError):pass

DESTINATIONS={
 '일본':('JPY','international'),'도쿄':('JPY','international'),'오사카':('JPY','international'),
 '미국':('USD','international'),'뉴욕':('USD','international'),'하와이':('USD','international'),
 '중국':('CNY','international'),'상하이':('CNY','international'),'베이징':('CNY','international'),
 '영국':('GBP','international'),'런던':('GBP','international'),'태국':('THB','international'),
 '방콕':('THB','international'),'베트남':('VND','international'),'대만':('TWD','international'),
 '프랑스':('EUR','international'),'독일':('EUR','international'),'유럽':('EUR','international'),
 '제주':('KRW','domestic'),'제주도':('KRW','domestic'),'부산':('KRW','domestic'),
 '서울':('KRW','domestic'),'강릉':('KRW','domestic'),'한국':('KRW','domestic'),
}
CURRENCIES={'엔':'JPY','달러':'USD','위안':'CNY','유로':'EUR','파운드':'GBP','바트':'THB','원':'KRW'}


def parse_days(text):
    match=re.search(r'(?:(\d+)\s*박\s*)?(\d+)\s*일',text)
    if match:return int(match.group(2))
    if '일주일' in text or '한 주' in text:return 7
    if '당일' in text:return 1
    raise ContextError('trip_days_missing_explicit_duration')


def parse_amount(text):
    match=re.search(r'([0-9][0-9,]*(?:\.[0-9]+)?)\s*(억|만|천)?\s*(엔|달러|위안|유로|파운드|바트|원|JPY|USD|CNY|EUR|GBP|THB|KRW)',text,re.I)
    if not match:raise ContextError('amount_requires_number_and_currency')
    number=Decimal(match.group(1).replace(',',''))*{'억':100000000,'만':10000,'천':1000,None:1}[match.group(2)]
    if number<=0 or number>Decimal('1000000000000'):raise ContextError('amount_out_of_range')
    unit=match.group(3);currency=CURRENCIES.get(unit,unit.upper())
    return {'value':format(number,'f'),'currency':currency}


def merge_context(previous,updates,message):
    context=dict(previous or {});changes=[]
    for update in updates:
        value,quote=update.value.strip(),update.quote.strip()
        origin='user_quote'
        if not quote or len(quote)>160 or quote not in message:raise ContextError('slot_quote_not_in_current_message')
        if update.slot=='destination' and (any(w in value for w in ('카드','은행','보험','계좌','금리')) or
                (value not in DESTINATIONS and not any(w in message for w in ('여행','출장','목적지','도시','국가')))):
            changes.append('rejected_irrelevant_destination')
            continue
        if update.slot=='group_name' and not any(w in message for w in ('모임','동아리','회비','총무')):
            changes.append('rejected_irrelevant_group_name')
            continue
        if update.slot in ('destination','group_name'):
            if not value or len(value)>60 or value not in quote:raise ContextError('slot_value_not_in_quote')
            normalized=value
        elif update.slot=='trip_days':
            normalized=parse_days(quote)
            if str(normalized)!=value or not 1<=normalized<=365:raise ContextError('trip_days_value_mismatch')
        elif update.slot=='amount':
            normalized=parse_amount(quote)
            try:
                if Decimal(value.replace(',',''))!=Decimal(normalized['value']):raise ContextError('amount_value_mismatch')
            except InvalidOperation:raise ContextError('amount_value_not_numeric') from None
        else:
            normalized=value.upper()
            if normalized not in ('JPY','USD','CNY','EUR','GBP','THB','KRW','VND','TWD','HKD','SGD'):raise ContextError('unsupported_currency')
            if not any(code==normalized and word in quote for word,code in CURRENCIES.items()) and normalized not in quote.upper():
                destination=context.get('destination',{}).get('value')
                if destination and destination in quote and DESTINATIONS.get(destination,(None,None))[0]==normalized:
                    origin='destination_lookup'
                else:raise ContextError('currency_not_explicit')
        if update.slot=='destination' and context.get('destination',{}).get('value')!=normalized:
            for key in ('currency','travel_scope'):context.pop(key,None)
        context[update.slot]={'value':normalized,'quote':quote,'origin':origin}
        changes.append(update.slot)
        if update.slot=='destination':
            matched=DESTINATIONS.get(value)
            if matched:
                currency,scope=matched
                context['currency']={'value':currency,'quote':quote,'origin':'destination_lookup'}
                context['travel_scope']={'value':scope,'quote':quote,'origin':'destination_lookup'}
    return context,changes


def explicit_updates(message):
    """High-precision local normalizers; LLM handles the remaining quoted slot proposals."""
    updates=[]
    places=sorted(DESTINATIONS,key=len,reverse=True)
    for place in places:
        # Only infer a destination if a travel/change phrase is present; not arbitrary city mentions.
        if place in message and any(s in message for s in ('여행','갈','가려','목적지','바꿔','변경','출장','가요','가려고')):
            updates.append(SlotUpdate(slot='destination',value=place,quote=place));break
    duration=re.search(r'(?:\d+\s*박\s*)?\d+\s*일|일주일|당일치기',message)
    if duration:
        quote=duration.group();updates.append(SlotUpdate(slot='trip_days',value=str(parse_days(quote)),quote=quote))
    amount=re.search(r'[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:억|만|천)?\s*(?:엔|달러|위안|유로|파운드|바트|원|JPY|USD|CNY|EUR|GBP|THB|KRW)',message,re.I)
    if amount:
        quote=amount.group();updates.append(SlotUpdate(slot='amount',value=parse_amount(quote)['value'],quote=quote))
    return updates
