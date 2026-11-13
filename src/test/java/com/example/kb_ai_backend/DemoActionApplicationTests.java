package com.example.kb_ai_backend;

import com.example.kb_ai_backend.config.PresentationTokenConfig;
import com.example.kb_ai_backend.service.WidgetDataService;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nimbusds.jose.jwk.source.ImmutableSecret;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.*;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import javax.crypto.spec.SecretKeySpec;
import java.time.Instant;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("presentation")
class DemoActionApplicationTests {
    private static final String FREEZE = "{\"type\":\"CARD_FREEZE_ALL\"}";
    @Autowired MockMvc mvc;
    @Autowired WidgetDataService widgets;
    @Autowired ObjectMapper json;
    @Autowired JwtEncoder encoder;
    @Autowired JwtDecoder decoder;

    @Test void actionOwnershipComesFromTheVerifiedToken() throws Exception {
        assertTrue(widgets.buildWidget("card_freeze_all").containsKey("action"));
        String alice = issueToken();
        String bob = issueToken();
        mvc.perform(post("/api/actions").header("X-User-Id", "alice")
                        .contentType("application/json").content(FREEZE))
                .andExpect(status().isUnauthorized())
                .andExpect(header().string("WWW-Authenticate", "Bearer"));
        String id = prepare(alice);
        assertNotEquals(id, prepare(bob));
        String aliceSubject = decoder.decode(alice).getSubject();
        mvc.perform(get("/api/actions/{id}", id).header("Authorization", bearer(bob)).header("X-User-Id", aliceSubject))
                .andExpect(status().isNotFound());
        mvc.perform(post("/api/actions/{id}/confirm", id).header("Authorization", bearer(bob))
                        .header("X-User-Id", aliceSubject))
                .andExpect(status().isNotFound());
        mvc.perform(get("/api/actions/{id}", id).header("Authorization", bearer(alice)))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("AWAITING_CONFIRM"));
        mvc.perform(post("/api/actions/{id}/confirm", id).header("Authorization", bearer(alice)))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("EXECUTED"));
        mvc.perform(get("/api/audit/verify").header("Authorization", bearer(alice)))
                .andExpect(status().isForbidden());
    }

    @Test void invalidClaimsAndSignatureAreRejected() throws Exception {
        var now = Instant.now();
        var otherEncoder = new NimbusJwtEncoder(new ImmutableSecret<>(
                new SecretKeySpec(new byte[32], "HmacSHA256")));
        for (String token : List.of(
                signed(encoder, "urn:other:issuer", PresentationTokenConfig.AUDIENCE, now.plusSeconds(600)),
                signed(encoder, PresentationTokenConfig.ISSUER, "wrong-audience", now.plusSeconds(600)),
                signed(encoder, PresentationTokenConfig.ISSUER, PresentationTokenConfig.AUDIENCE, now.minusSeconds(120)),
                signed(otherEncoder, PresentationTokenConfig.ISSUER, PresentationTokenConfig.AUDIENCE, now.plusSeconds(600)))) {
            mvc.perform(get("/api/actions/unknown").header("Authorization", bearer(token)))
                    .andExpect(status().isUnauthorized());
        }
    }

    @Test void tokenIssuanceRejectsRemoteAddressesAndUntrustedOrigins() throws Exception {
        mvc.perform(post("/api/presentation/token").with(request -> {
                    request.setRemoteAddr("192.0.2.1");
                    return request;
                }))
                .andExpect(status().isForbidden());
        mvc.perform(post("/api/presentation/token").header("Origin", "https://untrusted.example"))
                .andExpect(status().isForbidden());
    }

    private String prepare(String token) throws Exception {
        var response = mvc.perform(post("/api/actions").header("Authorization", bearer(token))
                        .header("Idempotency-Key", "same-key").contentType("application/json").content(FREEZE))
                .andExpect(status().isOk()).andReturn().getResponse();
        return json.readTree(response.getContentAsByteArray()).get("actionId").asText();
    }

    private String issueToken() throws Exception {
        var response = mvc.perform(post("/api/presentation/token").header("Origin", "http://localhost:5173"))
                .andExpect(status().isOk()).andExpect(header().string("Cache-Control", "no-store"))
                .andReturn().getResponse();
        return json.readTree(response.getContentAsByteArray()).get("accessToken").asText();
    }

    private static String signed(JwtEncoder encoder, String issuer, String audience, Instant expiry) {
        var claims = JwtClaimsSet.builder().issuer(issuer).subject("owner").audience(List.of(audience))
                .expiresAt(expiry).claim("scope", "actions:execute").build();
        return encoder.encode(JwtEncoderParameters.from(JwsHeader.with(MacAlgorithm.HS256).build(), claims))
                .getTokenValue();
    }

    private static String bearer(String token) {
        return "Bearer " + token;
    }
}
