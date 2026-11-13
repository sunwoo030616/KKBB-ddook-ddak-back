package com.example.kb_ai_backend.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.OAuth2TokenValidatorResult;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.server.resource.web.BearerTokenAuthenticationEntryPoint;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity
public class ActionSecurityConfig {
    @Bean
    @Order(1)
    @ConditionalOnProperty(name = "app.action.demo-enabled", havingValue = "true")
    SecurityFilterChain actionSecurity(HttpSecurity http, JwtDecoder decoder) throws Exception {
        return http.securityMatcher("/api/actions", "/api/actions/**", "/api/audit", "/api/audit/**")
                .cors(Customizer.withDefaults())
                .csrf(csrf -> csrf.disable())
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers(HttpMethod.OPTIONS, "/api/**").permitAll()
                        .requestMatchers("/api/audit", "/api/audit/**").hasAuthority("SCOPE_actions:audit")
                        .anyRequest().hasAuthority("SCOPE_actions:execute"))
                .oauth2ResourceServer(server -> server
                        .authenticationEntryPoint(new BearerTokenAuthenticationEntryPoint())
                        .jwt(jwt -> jwt.decoder(decoder)))
                .build();
    }

    @Bean
    @Profile("!presentation")
    @ConditionalOnProperty(name = "app.action.demo-enabled", havingValue = "true")
    JwtDecoder actionJwtDecoder(@Value("${app.action.auth.issuer:}") String issuer,
                                @Value("${app.action.auth.audience:}") String audience) {
        if (issuer.isBlank() || audience.isBlank()) {
            throw new IllegalArgumentException("액션 API를 사용하려면 JWT 발급자와 대상이 필요합니다.");
        }
        var decoder = NimbusJwtDecoder.withIssuerLocation(issuer).build();
        decoder.setJwtValidator(actionClaims(issuer, audience));
        return decoder;
    }

    // An explicit public chain preserves the existing canvas and disabled-action routes.
    @Bean
    @Order(2)
    SecurityFilterChain publicRoutes(HttpSecurity http) throws Exception {
        return http.csrf(csrf -> csrf.disable())
                .authorizeHttpRequests(auth -> auth.anyRequest().permitAll())
                .build();
    }

    static OAuth2TokenValidator<Jwt> actionClaims(String issuer, String audience) {
        return new DelegatingOAuth2TokenValidator<>(JwtValidators.createDefaultWithIssuer(issuer), jwt -> {
            if (jwt.getExpiresAt() != null && jwt.getSubject() != null && !jwt.getSubject().isBlank()
                    && jwt.getAudience() != null && jwt.getAudience().contains(audience)) {
                return OAuth2TokenValidatorResult.success();
            }
            return OAuth2TokenValidatorResult.failure(new OAuth2Error("invalid_token"));
        });
    }
}
