package com.example.kb_ai_backend;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("oidc-demo")
class OidcDemoApplicationTests {
    @Autowired MockMvc mvc;

    // Replace external discovery for this test, while requiring the OIDC bean and filter chain.
    @MockitoBean(name = "actionJwtDecoder", enforceOverride = true)
    JwtDecoder decoder;

    @Test void fixedCardScenarioRequiresExternalAccountToken() throws Exception {
        mvc.perform(post("/api/canvas").contentType("application/json")
                        .content("{\"message\":\"분실 카드 정지해줘\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.widgets[0].action.type").value("CARD_FREEZE_ALL"));
        mvc.perform(post("/api/presentation/token")).andExpect(status().isNotFound());

        var body = "{\"type\":\"CARD_FREEZE_ALL\",\"params\":{}}";
        mvc.perform(post("/api/actions").contentType("application/json").content(body))
                .andExpect(status().isUnauthorized());

        when(decoder.decode("external-account")).thenReturn(Jwt.withTokenValue("external-account")
                .header("alg", "RS256").subject("local-account")
                .claim("iss", "https://issuer.example.invalid")
                .claim("scope", "actions:execute").build());
        mvc.perform(post("/api/actions").header("Authorization", "Bearer external-account")
                        .header("Idempotency-Key", "oidc-test").contentType("application/json").content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.actionId").isNotEmpty());
    }
}
