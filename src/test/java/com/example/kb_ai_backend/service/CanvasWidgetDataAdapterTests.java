package com.example.kb_ai_backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class CanvasWidgetDataAdapterTests {
    @Test void usesServerQuoteAndExplicitCurrencyWithoutInventingBalance() throws Exception {
        var http=new RestTemplate();var mock=MockRestServiceServer.bindTo(http).build();
        mock.expect(requestTo(ExchangeRateService.API_URL)).andRespond(withSuccess(ExchangeRateServiceTests.QUOTES,MediaType.APPLICATION_JSON));
        var adapter=new CanvasWidgetDataAdapter(new ExchangeRateService(http,1000,500,()->100L));
        var input=new ObjectMapper().readTree("{\"status\":\"completed\",\"result\":{\"widgets\":[{\"type\":\"travel_card_charge_widget\",\"data\":{\"currency\":\"JPY\",\"requested_amount\":{\"value\":\"20000\",\"currency\":\"JPY\"}}}]}}");
        var result=adapter.enrich(input).path("result").path("widgets").get(0).path("data");
        assertEquals("200000",result.path("fx_quote").path("estimated_krw").asText());
        assertFalse(result.has("cardBalance"));mock.verify();
    }
}
