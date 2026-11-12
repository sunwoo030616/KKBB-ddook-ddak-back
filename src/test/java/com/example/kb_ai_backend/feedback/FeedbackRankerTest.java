package com.example.kb_ai_backend.feedback;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class FeedbackRankerTest {
    static final Set<String> WIDGETS = Set.of("travel_card_charge_widget", "overseas_qr_payment_widget", "travel_insurance_widget");

    static void repeat(FeedbackRanker ranker, String widget, FeedbackEvent event, int times) {
        for (int i = 0; i < times; i++) ranker.record(widget, event);
    }

    @Test void keepsOriginalOrderUntilEnoughExposures() {
        var ranker = new FeedbackRanker(WIDGETS, 20);
        repeat(ranker, "travel_insurance_widget", FeedbackEvent.SHOWN, 5);
        repeat(ranker, "travel_insurance_widget", FeedbackEvent.CLICKED, 5);
        var original = List.of("travel_card_charge_widget", "travel_insurance_widget");
        assertEquals(original, ranker.rank(original));
        assertEquals(FeedbackRanker.NEUTRAL, ranker.score("travel_insurance_widget"));
    }

    @Test void frequentlyUsedWidgetMovesUpAndDismissedMovesDown() {
        var ranker = new FeedbackRanker(WIDGETS, 20);
        repeat(ranker, "travel_card_charge_widget", FeedbackEvent.SHOWN, 30);
        repeat(ranker, "travel_card_charge_widget", FeedbackEvent.DISMISSED, 20);
        repeat(ranker, "travel_insurance_widget", FeedbackEvent.SHOWN, 30);
        repeat(ranker, "travel_insurance_widget", FeedbackEvent.CLICKED, 25);
        repeat(ranker, "travel_insurance_widget", FeedbackEvent.COMPLETED, 20);

        var ranked = ranker.rank(List.of("travel_card_charge_widget", "travel_insurance_widget", "overseas_qr_payment_widget"));
        assertEquals(List.of("travel_insurance_widget", "overseas_qr_payment_widget", "travel_card_charge_widget"), ranked);
    }

    @Test void rankingNeverAddsOrRemovesWidgets() {
        var ranker = new FeedbackRanker(WIDGETS, 0);
        repeat(ranker, "overseas_qr_payment_widget", FeedbackEvent.CLICKED, 50);
        assertEquals(List.of("travel_card_charge_widget"), ranker.rank(List.of("travel_card_charge_widget")));
    }

    @Test void scoreStaysBetweenZeroAndOne() {
        var ranker = new FeedbackRanker(WIDGETS, 0);
        repeat(ranker, "travel_card_charge_widget", FeedbackEvent.SHOWN, 10);
        repeat(ranker, "travel_card_charge_widget", FeedbackEvent.CLICKED, 10);
        repeat(ranker, "travel_card_charge_widget", FeedbackEvent.COMPLETED, 10);
        double score = ranker.score("travel_card_charge_widget");
        assertTrue(score > 0.9 && score <= 1.0, "score=" + score);
    }

    @Test void unknownWidgetIsRejected() {
        var ranker = new FeedbackRanker(WIDGETS, 0);
        assertThrows(IllegalArgumentException.class, () -> ranker.record("drop_table_widget", FeedbackEvent.CLICKED));
        assertThrows(IllegalArgumentException.class, () -> ranker.record(null, FeedbackEvent.CLICKED));
    }
}
