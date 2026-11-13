package com.example.kb_ai_backend.config;

import com.nimbusds.jose.jwk.source.ImmutableSecret;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.security.SecureRandom;
import java.util.Base64;

@Configuration
@Profile("presentation & !oidc-demo")
public class PresentationTokenConfig {
    public static final String ISSUER = "urn:kkbb:presentation";
    public static final String AUDIENCE = "kkbb-actions";

    @Bean
    SecretKey presentationSigningKey(@Value("${app.action.presentation-signing-key:}") String configuredKey) {
        byte[] key;
        if (configuredKey.isBlank()) {
            key = new byte[32];
            new SecureRandom().nextBytes(key);
        } else {
            key = Base64.getDecoder().decode(configuredKey);
            if (key.length < 32) throw new IllegalArgumentException("발표 토큰 서명 키는 32바이트 이상이어야 합니다.");
        }
        return new SecretKeySpec(key, "HmacSHA256");
    }

    @Bean
    JwtDecoder presentationJwtDecoder(SecretKey key) {
        var decoder = NimbusJwtDecoder.withSecretKey(key).macAlgorithm(MacAlgorithm.HS256).build();
        decoder.setJwtValidator(ActionSecurityConfig.actionClaims(ISSUER, AUDIENCE));
        return decoder;
    }

    @Bean
    JwtEncoder presentationJwtEncoder(SecretKey key) {
        return new NimbusJwtEncoder(new ImmutableSecret<>(key));
    }
}
