package com.example.kb_ai_backend.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Service;
import java.math.BigDecimal;
import java.math.RoundingMode;

/** Enrich only the approved FX widget; LLM output never supplies a quote or account balance. */
@Service
public class CanvasWidgetDataAdapter {
    private final ExchangeRateService rates;
    public CanvasWidgetDataAdapter(ExchangeRateService rates) { this.rates=rates; }
    public JsonNode enrich(JsonNode payload) {
        JsonNode screen="completed".equals(payload.path("status").asText())?payload.path("result"):payload;
        for(JsonNode widget:screen.path("widgets")) {
            if(!"travel_card_charge_widget".equals(widget.path("type").asText()) || !(widget.path("data") instanceof ObjectNode data))continue;
            String currency=data.path("currency").asText("");
            var quote=rates.getQuote(currency);if(quote==null)continue;
            var fx=data.putObject("fx_quote");fx.put("currency",quote.currency());fx.put("krw_per_unit",quote.krwPerUnit().toPlainString());
            fx.put("fetched_at",quote.fetchedAt().toString());fx.put("stale",quote.stale());fx.put("source",quote.source());
            fx.put("kind","indicative_reference_rate");
            if(quote.sourceUpdatedAt()!=null)fx.put("source_updated_at",quote.sourceUpdatedAt().toString());
            JsonNode amount=data.path("requested_amount");
            if(currency.equals(amount.path("currency").asText())) {
                try {
                    BigDecimal value=new BigDecimal(amount.path("value").asText());
                    if(value.signum()>0 && value.compareTo(new BigDecimal("1000000000000"))<=0)
                        fx.put("estimated_krw",value.multiply(quote.krwPerUnit()).setScale(0,RoundingMode.HALF_UP).toPlainString());
                }catch(NumberFormatException ignored) { /* no guessed amounts */ }
            }
        }
        return payload;
    }
}
