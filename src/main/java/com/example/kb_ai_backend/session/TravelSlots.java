package com.example.kb_ai_backend.session;

/**
 * 여행 위젯에 필요한 슬롯 묶음.
 * 새 발화에서 값이 나오면 덮어쓰고, 안 나오면 이전 값을 유지한다.
 */
public record TravelSlots(String currency, String destination, Integer amount, Integer tripDays) {

    public static final TravelSlots EMPTY = new TravelSlots(null, null, null, null);

    public TravelSlots mergedWith(TravelSlots newer) {
        if (newer == null) return this;
        boolean newPlace = newer.destination != null && !newer.destination.equals(destination);
        return new TravelSlots(
                newer.currency != null ? newer.currency : (newPlace ? null : currency),
                newer.destination != null ? newer.destination : destination,
                // 여행지가 바뀌면 이전 여행지 기준 금액은 버린다 (엔화 금액이 파운드로 넘어가면 안 됨)
                newer.amount != null ? newer.amount : (newPlace ? null : amount),
                newer.tripDays != null ? newer.tripDays : tripDays);
    }

    public boolean isEmpty() {
        return currency == null && destination == null && amount == null && tripDays == null;
    }
}
