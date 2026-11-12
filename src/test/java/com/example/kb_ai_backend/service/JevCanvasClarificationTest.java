package com.example.kb_ai_backend.service;

import com.example.kb_ai_backend.session.InMemorySessionStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class JevCanvasClarificationTest {
    WidgetSelectionExperimentService selector = mock(WidgetSelectionExperimentService.class);
    WidgetDataService data = mock(WidgetDataService.class);
    JevCanvasService service;

    @BeforeEach void setup() {
        var sessions = new InMemorySessionStore(Clock.systemUTC(), Duration.ofMinutes(30), 100);
        service = new JevCanvasService(selector, new CanvasParameters(), data, sessions);
        when(data.buildWidget(anyString(), any(), any(), any(), any(), any()))
                .thenAnswer(call -> Map.of("type", call.getArgument(0)));
    }

    void selected(String message, List<String> ids) {
        when(selector.select(message, "jev")).thenReturn(new WidgetSelectionExperimentService.Result(
                "jev", "test", "widget_selection_only", ids, Map.of(), false, 200, 100L, 30L));
    }

    @SuppressWarnings("unchecked")
    static List<String> types(Map<String, Object> response) {
        return ((List<Map<String, Object>>) response.get("widgets")).stream().map(w -> (String) w.get("type")).toList();
    }

    @Test void missingCurrencyKeepsOtherWidgetsAndAsksOnlyForCurrency() {
        selected("여행 환전이랑 보험", List.of("travel_card_charge_widget", "travel_insurance_widget"));

        var response = service.compose("여행 환전이랑 보험");

        assertEquals("needs_clarification", response.get("status"));
        assertEquals(List.of("travel_insurance_widget", "clarification_widget"), types(response));
        assertNotNull(response.get("sessionId"));
        verify(data, never()).buildWidget(eq("travel_card_charge_widget"), any(), any(), any(), any(), any());
    }

    @Test void answerToClarificationCompletesPendingWidgetWithoutSecondSelection() {
        selected("여행 환전이랑 보험", List.of("travel_card_charge_widget", "travel_insurance_widget"));
        String sessionId = (String) service.compose("여행 환전이랑 보험").get("sessionId");

        var response = service.compose("엔화로 3만엔", sessionId);

        assertEquals("ready", response.get("status"));
        assertEquals(List.of("travel_card_charge_widget"), types(response));
        assertEquals(sessionId, response.get("sessionId"));
        verify(selector, times(1)).select(anyString(), eq("jev"));
        verify(data).buildWidget("travel_card_charge_widget", "JPY", null, 30000, null, null);
    }

    @Test void followUpUsesSlotsRememberedFromEarlierTurn() {
        selected("일본 3박4일 여행 보험", List.of("travel_insurance_widget"));
        String sessionId = (String) service.compose("일본 3박4일 여행 보험").get("sessionId");
        selected("환전도 해줘", List.of("travel_card_charge_widget"));

        var response = service.compose("환전도 해줘", sessionId);

        assertEquals("ready", response.get("status"));
        verify(data).buildWidget("travel_card_charge_widget", "JPY", "일본", null, null, 4);
    }

    @Test void missingInputsCanBeAnsweredInSeparateTurnsWithoutReselectingWidgets() {
        String message = "여행 환전과 QR 결제 준비해줘";
        selected(message, List.of("travel_card_charge_widget", "overseas_qr_payment_widget"));
        var initial = service.compose(message);
        String sessionId = (String) initial.get("sessionId");
        assertEquals(List.of("clarification_widget"), types(initial));

        var firstAnswer = service.compose("엔화", sessionId);
        assertEquals("needs_clarification", firstAnswer.get("status"));
        assertEquals(List.of("travel_card_charge_widget", "clarification_widget"), types(firstAnswer));

        var secondAnswer = service.compose("도쿄", sessionId);
        assertEquals("ready", secondAnswer.get("status"));
        assertEquals(List.of("overseas_qr_payment_widget"), types(secondAnswer));
        verify(data).buildWidget("overseas_qr_payment_widget", "JPY", "도쿄", null, null, null);
        verify(selector, times(1)).select(anyString(), eq("jev"));
    }

    @Test void changingCurrencyDoesNotReuseThePreviousCurrencyAmount() {
        var widget = List.of("travel_card_charge_widget");
        selected("여행 환전", widget);
        selected("달러로 환전해줘", widget);
        String sessionId = (String) service.compose("여행 환전").get("sessionId");
        assertEquals("ready", service.compose("2만엔", sessionId).get("status"));
        verify(data).buildWidget("travel_card_charge_widget", "JPY", null, 20000, null, null);

        var response = service.compose("달러로 환전해줘", sessionId);

        assertEquals("ready", response.get("status"));
        verify(data).buildWidget("travel_card_charge_widget", "USD", null, null, null, null);
    }

    @Test void unrelatedMessageWhileWaitingStartsNewSelection() {
        selected("여행 환전", List.of("travel_card_charge_widget"));
        String sessionId = (String) service.compose("여행 환전").get("sessionId");
        selected("지갑을 잃어버렸어", List.of("card_freeze_all"));

        var response = service.compose("지갑을 잃어버렸어", sessionId);

        assertEquals(List.of("card_freeze_all"), types(response));
        verify(selector).select("지갑을 잃어버렸어", "jev");
    }

    @Test void aNewRequestThatMentionsCurrencyStillGoesThroughSelection() {
        selected("여행 환전", List.of("travel_card_charge_widget"));
        String sessionId = (String) service.compose("여행 환전").get("sessionId");
        String newRequest = "엔화 말고 카드 정지해줘";
        selected(newRequest, List.of("card_freeze_all"));

        var response = service.compose(newRequest, sessionId);

        assertEquals(List.of("card_freeze_all"), types(response));
        verify(selector).select(newRequest, "jev");
    }

    @Test void answeringWithAnUnrequestedSlotDoesNotBypassSelection() {
        selected("여행 환전", List.of("travel_card_charge_widget"));
        String sessionId = (String) service.compose("여행 환전").get("sessionId");
        selected("3박4일", List.of("travel_card_charge_widget"));

        var response = service.compose("3박4일", sessionId);

        assertEquals(List.of("clarification_widget"), types(response));
        verify(selector).select("3박4일", "jev");
    }

    @Test void expiredOrUnknownSessionStartsFresh() {
        selected("지갑을 잃어버렸어", List.of("card_freeze_all"));
        var response = service.compose("지갑을 잃어버렸어", "없는-세션");
        assertNotEquals("없는-세션", response.get("sessionId"));
        assertEquals("ready", response.get("status"));
    }
}
