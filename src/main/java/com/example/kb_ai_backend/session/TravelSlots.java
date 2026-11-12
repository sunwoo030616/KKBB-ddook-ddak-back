package com.example.kb_ai_backend.session;

/**
 * 여행 위젯에 필요한 슬롯 묶음.
 * 새 발화에서 값이 나오면 덮어쓴다. 여행지나 통화가 바뀌면 이전 금액을 이어받지 않는다.
 */
public record TravelSlots(String currency, String destination, Integer amount, Integer tripDays) {

    public static final TravelSlots EMPTY = new TravelSlots(null, null, null, null);

    public TravelSlots mergedWith(TravelSlots newer) {
        if (newer == null) return this;
        boolean newPlace = newer.destination != null && !newer.destination.equals(destination);
        boolean newCurrency = newer.currency != null && !newer.currency.equals(currency);
        return new TravelSlots(
                newer.currency != null ? newer.currency : (newPlace ? null : currency),
                newer.destination != null ? newer.destination : destination,
                newer.amount != null ? newer.amount : (newPlace || newCurrency ? null : amount),
                newer.tripDays != null ? newer.tripDays : tripDays);
    }

    public boolean isEmpty() {
        return currency == null && destination == null && amount == null && tripDays == null;
    }
}
