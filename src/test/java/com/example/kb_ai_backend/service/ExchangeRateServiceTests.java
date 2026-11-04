package com.example.kb_ai_backend.service;

import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class ExchangeRateServiceTests {
    static final String QUOTES="{\"result\":\"success\",\"base_code\":\"KRW\",\"rates\":{\"KRW\":1,\"JPY\":0.1}}";
    @Test void concurrentRequestsShareOneSnapshot() throws Exception {
        var http=new RestTemplate();var mock=MockRestServiceServer.bindTo(http).build();
        mock.expect(requestTo(ExchangeRateService.API_URL)).andRespond(withSuccess(QUOTES,MediaType.APPLICATION_JSON));
        var rates=new ExchangeRateService(http,1000,500,()->100L);var pool=Executors.newFixedThreadPool(6);
        try {
            var tasks=new java.util.ArrayList<java.util.concurrent.Callable<Double>>();for(int i=0;i<12;i++)tasks.add(()->rates.getKrwRateFor("JPY"));
            for(var value:pool.invokeAll(tasks))assertEquals(10.0,value.get());
            mock.verify();
        }finally {pool.shutdownNow();}
    }
    @Test void failureKeepsStaleQuoteAndBacksOff() {
        var http=new RestTemplate();var mock=MockRestServiceServer.bindTo(http).build();var time=new AtomicLong(100);
        mock.expect(requestTo(ExchangeRateService.API_URL)).andRespond(withSuccess(QUOTES,MediaType.APPLICATION_JSON));
        mock.expect(requestTo(ExchangeRateService.API_URL)).andRespond(withServerError());
        var rates=new ExchangeRateService(http,1000,500,time::get);
        assertFalse(rates.getQuote("JPY").stale());time.set(1101);
        assertTrue(rates.getQuote("JPY").stale());assertEquals(10.0,rates.getKrwRateFor("JPY"));
        assertEquals(10.0,rates.getKrwRateFor("JPY"));mock.verify();
    }
    @Test void rejectsInvalidCodesWithoutCallingProvider() {
        var http=new RestTemplate();var mock=MockRestServiceServer.bindTo(http).build();
        var rates=new ExchangeRateService(http,1000,500,()->100L);
        assertNull(rates.getQuote("https://attacker.invalid"));assertNull(rates.getQuote(null));mock.verify();
    }
}
